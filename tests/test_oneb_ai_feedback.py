from fastapi.testclient import TestClient


def _client(user_id: int = 1):
    from app.auth import get_current_user
    from app.main import app

    class U:
        id = user_id

    app.dependency_overrides[get_current_user] = lambda: U()
    return app, TestClient(app)


def test_feedback_roundtrip_and_ownership():
    from app.db import SessionLocal, init_db
    from app.models import AIAnswerLog

    init_db()  # SQLite local: acrescenta as colunas novas (rating, feedback_*)
    db = SessionLocal()
    row = AIAnswerLog(user_id=1, question="O que é ATR?", answer={"headline": "ATR"}, tool_calls=[], tools_hash="x",
                      model="template", grounding_ok=True, violations=[], fallback_used=True)
    db.add(row)
    db.commit()
    rid = row.id
    db.close()
    app, client = _client(1)
    try:
        r = client.post("/api/opportunities/ai/feedback", json={"answer_id": rid, "rating": -1, "comment": "faltou exemplo"})
        assert r.status_code == 200 and r.json()["rating"] == -1
        summary = client.get("/api/opportunities/ai/feedback/summary").json()
        assert summary["not_useful"] >= 1 and any(n["comment"] == "faltou exemplo" for n in summary["recent_negative"])
        assert client.post("/api/opportunities/ai/feedback", json={"answer_id": rid, "rating": 0}).status_code == 422
    finally:
        app.dependency_overrides.clear()
    app, client = _client(999)  # outro usuário não avalia resposta alheia
    try:
        assert client.post("/api/opportunities/ai/feedback", json={"answer_id": rid, "rating": 1}).status_code == 404
    finally:
        app.dependency_overrides.clear()
