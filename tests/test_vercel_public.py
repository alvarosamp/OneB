"""Run in a separate process: the public entrypoint must never touch the real DB."""
import os
import subprocess
import sys
from pathlib import Path


def test_public_deployment_is_anonymous_isolated_and_read_only():
    runtime = Path(__file__).resolve().parents[1] / "tmp" / "vercel-public-tests"
    runtime.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TMP=str(runtime), TEMP=str(runtime), TMPDIR=str(runtime))
    result = subprocess.run(
        [sys.executable, "-c", '''
import os
os.environ["DATABASE_URL"] = "postgresql://must-not-connect.invalid/private"
from fastapi.testclient import TestClient
from serverless import app
from app.config import settings
from app.brasil import rates
rates.current = lambda: {"selic": 13.75, "cdi": 13.65, "ipca_12m": 4.58, "stale": True, "series": {}}
assert settings.database_url.startswith("sqlite:///")
assert "must-not-connect" not in settings.database_url
assert not settings.run_embedded_scheduler
client = TestClient(app)
assert client.get("/health").status_code == 200
visitor = client.get("/api/auth/me")
assert visitor.status_code == 200, visitor.text
assert visitor.json()["username"] == "Visitante"
assert not visitor.json()["is_admin"]
course = client.get("/api/lms/courses/investir-no-brasil")
assert course.status_code == 200, course.text
assert course.json()["modules"]
assert client.get("/api/brasil/products").status_code == 200
simulation = client.post("/api/brasil/simulate", json={"initial": 1000, "months": 12, "goal": "reserva"})
assert simulation.status_code == 200, simulation.text
assert client.get("/api/auth/usuarios").status_code == 403
for path in ["/api/auth/cadastro", "/api/auth/login", "/api/watchlist", "/api/assistant/ask"]:
    assert client.post(path, json={}).status_code == 403, path
assert client.delete("/api/watchlist/1").status_code == 403
print("Public deployment checks passed")
'''],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
