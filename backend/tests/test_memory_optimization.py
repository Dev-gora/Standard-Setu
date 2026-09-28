"""Tests for the Render-free memory optimization (embeddings pipeline).

The suite runs on the deterministic sentence-transformers stub (conftest), so
these tests validate the PLUMBING — precomputed-matrix load, order/model
mismatch fallback, ONNX-first routing with graceful ST fallback — not the real
MiniLM weights. Parity of the real ONNX export is checked at Docker build time
(scripts/build_embeddings.py parity gate).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.services import standards_registry as registry


@pytest.fixture
def _reset_embed_caches():
    """Isolate the module-level embedding caches between tests."""
    registry._EMBED_MATRIX = None
    registry._EMBED_ORDER = None
    registry._get_corpora_and_embeddings.cache_clear()
    yield
    registry._EMBED_MATRIX = None
    registry._EMBED_ORDER = None
    registry._get_corpora_and_embeddings.cache_clear()


@pytest.fixture
def fake_npy(tmp_path, monkeypatch):
    """A valid precomputed matrix + meta matching the registry order.

    Dimension 256 mirrors the conftest stub embedder so the query vector and
    matrix are compatible (in production both come from the same MiniLM)."""
    records = registry.all_standards()
    matrix = np.random.RandomState(7).rand(len(records), 256).astype("float32")
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    npy = tmp_path / "standards_embeddings.npy"
    meta = tmp_path / "standards_embeddings.meta.json"
    np.save(npy, matrix)
    meta.write_text(
        json.dumps(
            {
                "model": "all-MiniLM-L6-v2",
                "dim": 384,
                "rows": int(matrix.shape[0]),
                "order": [r["is_number_clean"] for r in records],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "DATA_DIR", tmp_path)
    return matrix


def test_precomputed_matrix_is_used(fake_npy, _reset_embed_caches):
    matrix, order = registry._load_precomputed_embeddings()
    assert matrix is not None
    np.testing.assert_array_equal(matrix, fake_npy)
    records, embeddings = registry._get_corpora_and_embeddings()
    assert embeddings is not None
    # The matrix object is reused (no recompute per request)
    again, _ = registry._load_precomputed_embeddings()
    assert again is matrix


def test_search_works_off_precomputed(fake_npy, _reset_embed_caches):
    from app.services.embeddings import embed_query

    results = registry.search_registry("reinforcement bars for concrete", top_k=3)
    assert results, "search must return hits with precomputed embeddings"
    top = results[0]
    assert "_semantic" in top and "_keyword" in top and "_score" in top
    # semantic score = unit-normalized dot product in [-1, 1]
    assert -1.0 <= top["_semantic"] <= 1.0


def test_model_mismatch_falls_back_to_encode(tmp_path, monkeypatch, _reset_embed_caches):
    records = registry.all_standards()
    meta = tmp_path / "standards_embeddings.meta.json"
    np.save(tmp_path / "standards_embeddings.npy", np.zeros((len(records), 256), dtype="float32"))
    meta.write_text(json.dumps({"model": "some-other-model", "order": []}), encoding="utf-8")
    monkeypatch.setattr(registry, "DATA_DIR", tmp_path)

    matrix, order = registry._load_precomputed_embeddings()
    assert matrix is None  # rejected -> caller encodes via stub ST instead
    _records, embeddings = registry._get_corpora_and_embeddings()
    assert embeddings is not None


def test_order_mismatch_falls_back(tmp_path, monkeypatch, _reset_embed_caches):
    meta = tmp_path / "standards_embeddings.meta.json"
    np.save(tmp_path / "standards_embeddings.npy", np.zeros((3, 384), dtype="float32"))
    meta.write_text(
        json.dumps({"model": "all-MiniLM-L6-v2", "order": ["IS 1", "IS 2", "IS 3"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(registry, "DATA_DIR", tmp_path)

    matrix, _ = registry._load_precomputed_embeddings()
    assert matrix is None


def test_missing_npy_falls_back(tmp_path, monkeypatch, _reset_embed_caches):
    monkeypatch.setattr(registry, "DATA_DIR", tmp_path)
    matrix, order = registry._load_precomputed_embeddings()
    assert matrix is None and order is None
    _records, embeddings = registry._get_corpora_and_embeddings()
    assert embeddings is not None  # encoded on the fly (stub)


def test_onnx_first_routing_falls_back_gracefully(_reset_embed_caches, monkeypatch):
    """No ONNX artifacts in this env: embed_texts must still answer (via ST stub)."""
    import app.services.embeddings as emb

    v = emb.embed_query("cement for a bridge deck")
    assert len(v) == 256  # stub dim; real model is 384
    assert emb.embedding_backend() in {"onnx", "sentence-transformers"}


def test_embed_query_single_and_batch_agree(_reset_embed_caches):
    from app.services.embeddings import embed_query, embed_texts

    single = embed_query("steel bars")
    batch = embed_texts(["steel bars", "cement"])
    assert single == batch[0]
