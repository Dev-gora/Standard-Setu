"""Build the offline embedding artifacts (run at Docker build time).

Outputs into backend/data/:
- minilm.onnx            fp32 ONNX export of all-MiniLM-L6-v2 (fallback)
- minilm_int8.onnx       int8 dynamic-quantized ONNX (preferred runtime, ~25% size)
- standards_embeddings.npy  float32 [130, 384] matrix over the registry order
- standards_embeddings.meta.json  model name, dim, row count, order of IS numbers

The runtime then encodes ONLY the user's query and dot-products against this
matrix — the heavy encoder never touches 130 texts at request time.

Usage:  python scripts/build_embeddings.py
Requires (build machine only): sentence-transformers, torch, onnx, onnxruntime
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_ROOT / "data"
sys.path.insert(0, str(BACKEND_ROOT))

MODEL = "all-MiniLM-L6-v2"


def main() -> None:
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer

    from app.services import standards_registry as registry

    records = registry.all_standards()
    if not records:
        print("registry is empty - nothing to embed")
        return

    texts = [
        f"{r['title']}. {r['scope_description']} Category: {r['category']}. {r['combined_text'][:800]}"
        for r in records
    ]
    print(f"embedding {len(texts)} registry records with {MODEL} ...")
    model = SentenceTransformer(MODEL)
    matrix = model.encode(texts, show_progress_bar=True, convert_to_numpy=True).astype("float32")
    np.save(DATA_DIR / "standards_embeddings.npy", matrix)
    (DATA_DIR / "standards_embeddings.meta.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "dim": int(matrix.shape[1]),
                "rows": int(matrix.shape[0]),
                "order": [r["is_number_clean"] for r in records],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"saved standards_embeddings.npy {matrix.shape}")

    # ---- ONNX export (fp32) -----------------------------------------------
    onnx_path = DATA_DIR / "minilm.onnx"
    if not onnx_path.exists():
        print("exporting ONNX ...")
        tokenizer = model.tokenizer
        class _Wrapper(torch.nn.Module):
            def __init__(self, m):
                super().__init__()
                self.m = m

            def forward(self, input_ids, attention_mask, token_type_ids):
                out = self.m.auto_model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    token_type_ids=token_type_ids,
                    return_dict=True,
                )
                mask = attention_mask.unsqueeze(-1).float()
                summed = (out.last_hidden_state * mask).sum(1)
                counts = mask.sum(1).clamp(min=1e-9)
                pooled = summed / counts
                return torch.nn.functional.normalize(pooled, p=2, dim=1)

        wrapper = _Wrapper(model).eval()
        batch = tokenizer(
            ["cement for construction"], padding=True, truncation=True, max_length=256, return_tensors="pt"
        )
        args = (batch["input_ids"], batch["attention_mask"], batch["token_type_ids"])
        torch.onnx.export(
            wrapper,
            args,
            str(onnx_path),
            input_names=["input_ids", "attention_mask", "token_type_ids"],
            output_names=["embedding"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "token_type_ids": {0: "batch", 1: "seq"},
                "embedding": {0: "batch"},
            },
            opset_version=14,
        )
        print(f"saved {onnx_path.name}")

    # ---- int8 dynamic quantization (preferred runtime artifact) ------------
    int8_path = DATA_DIR / "minilm_int8.onnx"
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        if not int8_path.exists():
            print("quantizing to int8 ...")
            quantize_dynamic(str(onnx_path), str(int8_path), weight_type=QuantType.QInt8)
            print(f"saved {int8_path.name}")
    except Exception as exc:
        print(f"quantization skipped ({exc}) - fp32 ONNX still available")

    # ---- sanity: ONNX parity with sentence-transformers ---------------------
    try:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        sess = ort.InferenceSession(
            str(int8_path if int8_path.exists() else onnx_path),
            sess_options=so,
            providers=["CPUExecutionProvider"],
        )
        batch = tokenizer(["reinforcement bars for concrete"], return_tensors="np")
        feeds = {
            "input_ids": batch["input_ids"].astype("int64"),
            "attention_mask": batch["attention_mask"].astype("int64"),
            "token_type_ids": batch["token_type_ids"].astype("int64"),
        }
        onnx_v = sess.run(None, feeds)[0][0]
        st_v = model.encode(["reinforcement bars for concrete"])
        cos = float(np.dot(onnx_v, st_v[0]) / (np.linalg.norm(onnx_v) * np.linalg.norm(st_v[0])))
        print(f"parity check cosine(onnx, sentence-transformers) = {cos:.4f}")
        if cos < 0.99:
            print("WARNING: parity below 0.99 - inspect pooling before deploying")
    except Exception as exc:
        print(f"parity check skipped ({exc})")


if __name__ == "__main__":
    main()
