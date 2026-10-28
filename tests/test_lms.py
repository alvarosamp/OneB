from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.lms_content import LESSON_BODIES, MATERIAL_SINAIS, TRACK_SINAIS
from app.main import app
from app.models import User
from app.routers.lms import seed_default_courses


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="aluno", password_hash="x"))
    db.commit()
    seed_default_courses(db)
    db.close()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _first_lesson(client, slug="fundamentos"):
    course = client.get(f"/api/lms/courses/{slug}").json()
    return course["modules"][0]["lessons"][0]


def test_tracks_follow_academia_order_with_new_track(client):
    slugs = [c["slug"] for c in client.get("/api/lms/courses").json()]
    assert slugs == ["fundamentos", "gestao-de-risco-e-psicologia", "analise-tecnica-avancada",
                     "processo-diario-e-revisao", "como-avaliar-um-sinal", "leitura-de-regime-e-contexto", "investir-no-brasil"]


def test_new_track_lessons_have_body_and_material(client):
    course = client.get("/api/lms/courses/como-avaliar-um-sinal").json()
    lessons = [l for m in course["modules"] for l in m["lessons"]]
    assert len(lessons) == 8  # inclui o módulo "O laboratório do OneB" (10/10/2026) e a aula de conferir o placar (16/10/2026)
    for lesson in lessons:
        assert lesson["body"], lesson["title"]
        assert lesson["exercise"] == MATERIAL_SINAIS[lesson["title"]]["exercise"]
    titles = {l for _, ls in TRACK_SINAIS[3] for l, _, _ in ls}
    assert titles <= set(LESSON_BODIES)


def test_complete_requires_quiz_answered_on_server(client):
    import json
    from pathlib import Path

    lesson = _first_lesson(client)
    lid = lesson["id"]
    assert client.post(f"/api/lms/lessons/{lid}/complete").status_code == 409
    # Atalho do exercício aberto não vale em aula com quiz.
    assert client.post(f"/api/lms/lessons/{lid}/exercise", json={"answer": "x" * 50}).status_code == 409
    quiz = client.get(f"/api/lms/lessons/{lid}/quiz").json()
    assert quiz["questions"] and all("correct" not in q for q in quiz["questions"])  # gabarito não vaza
    key = json.loads((Path(__file__).resolve().parents[1] / "app" / "academy_quizzes.json").read_text(encoding="utf-8"))[lesson["title"]]
    wrong = (key[0]["correct"] + 1) % len(key[0]["options"])
    res = client.post(f"/api/lms/lessons/{lid}/quiz/0", json={"choice": wrong}).json()
    assert res["correct"] is False and res["why"] is None
    for i, q in enumerate(key):
        res = client.post(f"/api/lms/lessons/{lid}/quiz/{i}", json={"choice": q["correct"]}).json()
        assert res["correct"] is True
    assert res["passed"] is True
    assert client.post(f"/api/lms/lessons/{lid}/complete").status_code == 204
    summary = next(c for c in client.get("/api/lms/courses").json() if c["slug"] == "fundamentos")
    assert summary["completed_count"] == 1


def test_every_lesson_has_a_quiz_on_server():
    import json
    from pathlib import Path

    from app.routers.lms import _COURSES_SEED
    quizzes = json.loads((Path(__file__).resolve().parents[1] / "app" / "academy_quizzes.json").read_text(encoding="utf-8"))
    titles = [lesson for course in _COURSES_SEED for _, lessons in course[3] for lesson, _, _ in lessons]
    assert [t for t in titles if not quizzes.get(t)] == []
    for qs in quizzes.values():
        assert all(0 <= q["correct"] < len(q["options"]) for q in qs)


def test_note_and_last_lesson_persist_on_server(client):
    lesson = _first_lesson(client, "como-avaliar-um-sinal")
    assert client.get("/api/lms/learning-state").json()["last_lesson"] is None
    client.put(f"/api/lms/lessons/{lesson['id']}/note", json={"note": "acerto não é lucro"})
    client.post(f"/api/lms/lessons/{lesson['id']}/visit")
    state = client.get(f"/api/lms/lessons/{lesson['id']}/state").json()
    assert state["note"] == "acerto não é lucro" and state["visited_at"]
    last = client.get("/api/lms/learning-state").json()["last_lesson"]
    assert last["course_slug"] == "como-avaliar-um-sinal" and last["lesson_id"] == lesson["id"]


def test_unknown_lesson_is_404(client):
    assert client.get("/api/lms/lessons/99999/state").status_code == 404
    assert client.put("/api/lms/lessons/99999/note", json={"note": "x"}).status_code == 404


def test_replays_are_served_and_slug_is_validated(client):
    index = client.get("/api/lms/replays").json()
    assert {r["slug"] for r in index} >= {"nasdaq-dia-de-tendencia", "nasdaq-dia-lateral", "ouro-rompimento-falso-londres"}
    replay = client.get("/api/lms/replays/nasdaq-dia-lateral").json()
    assert replay["bars"] and replay["captions"] and replay["spread"] > 0
    assert all(c["at"] < len(replay["bars"]) for c in replay["captions"])
    assert client.get("/api/lms/replays/..%2Fsecret").status_code == 404
    assert client.get("/api/lms/replays/nao-existe").status_code == 404


def test_every_lesson_has_body_text():
    from app.lms_content import LESSON_BODIES
    from app.routers.lms import _COURSES_SEED
    titles = [lesson for course in _COURSES_SEED for _, lessons in course[3] for lesson, _, _ in lessons]
    assert [t for t in titles if not LESSON_BODIES.get(t)] == []
