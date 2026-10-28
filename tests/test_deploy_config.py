"""Deploy grátis (Render + Vercel, ver docs/DEPLOY_GRATIS.md)."""
import json
from pathlib import Path

import yaml

from app.config import normalize_database_url

ROOT = Path(__file__).resolve().parents[1]


def test_neon_and_render_urls_use_psycopg3():
    assert normalize_database_url("postgres://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_vercel_proxies_api_to_the_render_service():
    service = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))["services"][0]
    vercel = json.loads((ROOT / "frontend" / "vercel.json").read_text(encoding="utf-8"))
    api_rule = vercel["rewrites"][0]
    assert api_rule["source"] == "/api/:path*"
    assert api_rule["destination"].startswith(f"https://{service['name']}.onrender.com/api/")
    assert vercel["rewrites"][-1]["destination"] == "/index.html"  # SPA por último
    # Mesmo domínio: o front chama /api relativo, e o cookie SameSite=strict funciona.
    assert vercel["buildCommand"].startswith("VITE_API_URL= ")
    env = {e["key"]: e for e in service["envVars"]}
    assert env["ENVIRONMENT"]["value"] == "production" and env["SECRET_KEY"].get("generateValue")
    assert "alembic upgrade head" in service["dockerCommand"]
