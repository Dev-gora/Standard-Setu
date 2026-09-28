"""Manual smoke check for the new P0/P1 endpoints (dev only)."""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Stub sentence_transformers so app.main imports on machines without the ML stack.
if "sentence_transformers" not in sys.modules:
    fake = types.ModuleType("sentence_transformers")

    class FakeModel:
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

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

print("health:", client.get("/api/procure/health").json())

r = client.post("/api/procure/recommend", json={"query": "Reinforcement bars for concrete in a bridge deck"})
data = r.json()
print("recommend:", r.status_code, "| history_id:", data.get("history_id"))
rec = data["recommendations"][0]
print("  top:", rec["standard"]["is_number"], "| match:", rec["match"]["score"], rec["match"]["confidence"],
      "| factors:", [f["label"] for f in rec["match"]["factors"]])

r = client.get("/api/procure/evidence/IS 1786", params={"query": "chemical composition requirements"})
ev = r.json()
print("evidence IS 1786:", r.status_code, "| claims:", [(c["kind"], c["evidence"]["clause"], c["evidence"]["page"], c["evidence"]["available"]) for c in ev])

r = client.get("/api/procure/evidence/IS 1239")
ev = r.json()
print("evidence unindexed:", [(c["evidence"]["standard"], c["evidence"]["available"], c["evidence"]["unavailable_reason"]) for c in ev][:2])

r = client.post("/api/procure/verify", json={"licence_number": "CM/L-8700123456", "supplier_name": "Test Steel", "is_number": "IS 1786"})
v = r.json()
print("verify:", r.status_code, "| status:", v["status"], "| last_verified:", v["last_verified"][:19], "| cached:", v["cached"])

r = client.post("/api/procure/verify", json={"licence_number": "bogus"})
print("verify bad format:", r.json()["status"])

r = client.post("/api/procure/watchlist", json={"is_number": "IS 1786"})
print("watch add:", r.status_code, r.json().get("is_number"))
r = client.get("/api/procure/watchlist")
wl = r.json()
print("watchlist:", r.status_code, "| items:", wl["total"])
r = client.get("/api/procure/notifications")
print("notifications:", r.status_code, "| unread:", r.json()["unread"])

r = client.post("/api/procure/compare", json={"codes": ["IS 1786", "IS 2062", "IS 9999"], "query": "reinforcement steel"})
cmp = r.json()
print("compare:", r.status_code, "| found:", [(c["code"], c["found"], c.get("match_score")) for c in cmp["columns"]])

r = client.get("/api/procure/versions/IS 694")
ver = r.json()
print("versions IS 694:", r.status_code, "| available:", ver["available"], "| msg:", ver["message"][:80])

r = client.get("/api/procure/history")
print("history:", r.status_code, "| entries:", r.json()["total"])

r = client.post("/api/procure/report", json={"query": "Reinforcement bars for concrete in a bridge deck", "code": "IS 1786"})
rep = r.json()
print("report:", r.status_code, "| std:", rep["standard"]["is_number"], "| match:", rep["match"]["score"],
      "| evidence:", len(rep["evidence"]), "| risks:", len(rep["risk_notes"]))

print("meta ocr/evidence:", client.get("/api/procure/meta").json()["ocr"], client.get("/api/procure/meta").json()["evidence_index"])
