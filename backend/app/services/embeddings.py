"""Embedding service — ONNX Runtime primary, sentence-transformers fallback.

Render Free runs this backend in a 512 MB container. Importing
sentence-transformers pulls in PyTorch (~250 MB RSS before any weights) and
torch's OpenMP thread pools spike far beyond that on multi-core hosts, which
is exactly what killed POST /api/procure/recommend in production.

Memory strategy here:
- Preferred runtime: onnxruntime (CPUExecutionProvider only, threads capped).
  Same all-MiniLM-L6-v2 weights exported to ONNX -> identical 384-d vectors,
  no PyTorch ever imported.
- The registry embeddings are precomputed OFFLINE (scripts/build_embeddings.py)
  into data/standards_embeddings.npy + meta; at runtime we encode ONLY the
  user's query.
- If onnxruntime or the exported model is missing, we fall back to the
  original sentence-transformers path (unchanged behaviour, higher RAM) so the
  app never loses semantic search.

Thread caps matter as much as the runtime: torch/ORT spawn OpenMP arenas
sized to the host core count (Render hosts report many cores even on the
0.1-CPU free plan). We set them BEFORE the first model import and force
intra-op threads to 1-2 for this tiny model.
"""

from __future__ import annotations

import os
from functools import lru_cache
from threading import Lock

# Must run before torch/onnxruntime are first imported anywhere.
for _var, _val in (
    ("OMP_NUM_THREADS", "1"),
    ("MKL_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
    ("TOKENIZERS_PARALLELISM", "false"),
):
    os.environ.setdefault(_var, _val)

from app.config import get_settings

_EMBED_DIM = 384  # all-MiniLM-L6-v2


@lru_cache
def _get_onnx_session():
    """Load the exported ONNX MiniLM (int8 quantized preferred, fp32 fallback)."""
    import onnxruntime as ort

    from app.config import get_settings

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    model_path = None
    for name in ("minilm_int8.onnx", "minilm.onnx"):
        candidate = os.path.join(data_dir, name)
        if os.path.exists(candidate):
            model_path = candidate
            break
    if model_path is None:
        raise FileNotFoundError("No exported ONNX embedding model in backend/data (run scripts/build_embeddings.py)")

    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        model_path,
        sess_options=so,
        providers=["CPUExecutionProvider"],  # never CUDA
    )
    return session, get_settings().EMBEDDING_MODEL


def _mean_pool(last_hidden, attention_mask):
    import numpy as np

    mask = attention_mask[:, :, None].astype(last_hidden.dtype)
    summed = (last_hidden * mask).sum(axis=1)
    counts = mask.sum(axis=1).clip(min=1e-9)
    return summed / counts


def _l2_normalize(vectors):
    import numpy as np

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@lru_cache
def _get_tokenizer():
    from transformers import AutoTokenizer

    from app.config import get_settings

    return AutoTokenizer.from_pretrained(get_settings().EMBEDDING_MODEL)


@lru_cache
def _get_model():
    """Fallback path: the original sentence-transformers model (heavy)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().EMBEDDING_MODEL)


_embed_lock = Lock()
_onnx_ok: bool | None = None  # tri-state: None = not tried yet


def _try_onnx_encode(texts: list[str]) -> list[list[float]] | None:
    """Encode via ONNX Runtime; return None if unavailable (caller falls back)."""
    global _onnx_ok
    if _onnx_ok is False:
        return None
    try:
        import numpy as np

        with _embed_lock:
            session, model_name = _get_onnx_session()
            tokenizer = _get_tokenizer()
            encoded = tokenizer(
                texts, padding=True, truncation=True, max_length=256, return_tensors="np"
            )
            feeds = {
                "input_ids": encoded["input_ids"].astype("int64"),
                "attention_mask": encoded["attention_mask"].astype("int64"),
            }
            if "token_type_ids" in [i.name for i in session.get_inputs()]:
                feeds["token_type_ids"] = encoded["token_type_ids"].astype("int64")
            hidden = session.run(None, feeds)[0]
            vectors = _l2_normalize(_mean_pool(hidden, encoded["attention_mask"]))
        _onnx_ok = True
        return vectors.astype("float32").tolist()
    except Exception:
        _onnx_ok = False
        return None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts (same model as always)."""
    if not texts:
        return []
    onnx = _try_onnx_encode(texts)
    if onnx is not None:
        return onnx
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    # numpy arrays have .tolist(); some light stubs/alternative backends return
    # plain lists — accept both so the fallback path never hard-crashes.
    tolist = getattr(embeddings, "tolist", None)
    if tolist is not None:
        return tolist()
    return [[float(x) for x in vec] for vec in embeddings]


def embed_query(text: str) -> list[float]:
    """Return embedding vector for a single query string."""
    return embed_texts([text])[0]


def embedding_backend() -> str:
    """Which engine answered the last embed (observability/health)."""
    return "onnx" if _onnx_ok else "sentence-transformers"


def embed_dim() -> int:
    return _EMBED_DIM
