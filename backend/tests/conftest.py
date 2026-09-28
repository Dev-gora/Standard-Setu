"""Pytest fixtures — stub sentence-transformers BEFORE any app import.

Mirrors the verification pattern used during development: on machines without
the ML stack the real import fails, so we inject a deterministic hashing
embedder. Tests also redirect the JSON state/cache files to a tmp dir so the
suite never pollutes backend/data/.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _install_fake_st() -> None:
    if "sentence_transformers" in sys.modules:
        return
    fake = types.ModuleType("sentence_transformers")

    class FakeModel:
        """Deterministic hashing embedder — same text -> same vector."""

        def __init__(self, *a, **k):
            pass

        def encode(self, texts, show_progress_bar=False):
            import hashlib

            out = []
            for t in texts:
                v = [0.0] * 256
                for tok in str(t).lower().split():
                    h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                    v[h % 256] += 1.0
                n = sum(x * x for x in v) ** 0.5 or 1.0
                out.append([x / n for x in v])
            return out

    fake.SentenceTransformer = lambda *a, **k: FakeModel()
    sys.modules["sentence_transformers"] = fake


@pytest.fixture(scope="session", autouse=True)
def _stub_embeddings():
    _install_fake_st()
    yield


@pytest.fixture(autouse=True)
def _tmp_state(monkeypatch, tmp_path):
    """Point every JSON store at a per-test tmp dir."""
    import app.services.store as store_mod
    import app.services.verify as verify_mod

    monkeypatch.setattr(store_mod, "STATE_FILE", tmp_path / "app_state.json", raising=False)
    monkeypatch.setattr(verify_mod, "CACHE_FILE", tmp_path / "verify_cache.json", raising=False)
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
