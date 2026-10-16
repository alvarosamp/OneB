"""O app lê arquivos de configs/ em produção: a imagem Docker precisa levá-los (allowlist + COPY)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_configs_are_in_the_image():
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=app:app configs ./configs" in dockerfile
    for needed in ("!configs/preregistration/**", "!configs/broker/**", "!configs/manual_advisors_v1.json"):
        assert needed in ignore, needed
    from app.opportunity import ADVISORS_CONFIG
    from app.routers.asset_brief import BROKER_FILE
    from app.setups import LOCK_PATH

    for path in (ADVISORS_CONFIG, BROKER_FILE, LOCK_PATH):
        assert path.exists() and path.is_relative_to(ROOT / "configs"), path
