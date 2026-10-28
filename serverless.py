"""Public, read-only Vercel deployment, isolated from all personal accounts.

The normal authenticated application remains app.main:app. This entrypoint always
uses a fresh disposable database and never connects to DATABASE_URL from a host.
"""
import os
import secrets
import tempfile
from pathlib import Path

_runtime = Path(tempfile.mkdtemp(prefix="oneb-public-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(_runtime / 'public.db').as_posix()}",
    "SECRET_KEY": secrets.token_hex(32),
    "ENVIRONMENT": "production",
    "RUN_EMBEDDED_SCHEDULER": "false",
    "ADMIN_BOOTSTRAP_USERNAME": "",
    "ADMIN_BOOTSTRAP_PASSWORD": "",
    "TELEGRAM_BOT_TOKEN": "",
    "MARKET_DATA_ROOT": str(_runtime / "market"),
    "YFINANCE_CACHE_DIR": str(_runtime / "yfinance"),
})

from fastapi import Depends  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

from app.auth import get_current_user  # noqa: E402
from app.db import SessionLocal, get_db, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, WatchlistItem  # noqa: E402
from app.routers import lives, lms  # noqa: E402

# Vercel does not run ASGI lifespan; initialize the disposable instance once.
init_db()
with SessionLocal() as db:
    lms.seed_default_courses(db)
    lives.seed_default_lives(db)
    guest = User(username="Visitante", password_hash="!no-login", is_admin=False)
    db.add(guest)
    db.flush()
    _guest_id = guest.id
    for symbol, label in [("QQQ", "NASDAQ 100"), ("SPY", "S&P 500"), ("AAPL", "Apple")]:
        db.add(WatchlistItem(user_id=guest.id, symbol=symbol, label=label))
    db.commit()


def public_visitor(db: Session = Depends(get_db)) -> User:
    return db.get(User, _guest_id)


app.dependency_overrides[get_current_user] = public_visitor

# Register Vite with FastAPI so Vercel can discover the generated assets even
# with application middleware; API routes always take precedence.
app.frontend("/", directory=Path(__file__).resolve().parent / "frontend" / "dist", fallback="index.html", check_dir=False)


@app.middleware("http")
async def public_access(request, call_next):
    path = request.url.path
    # Only the calculator accepts anonymous POSTs; never store a visitor's data
    # in a database shared by other visitors or invoke paid AI provider calls.
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not (
        request.method == "POST" and path == "/api/brasil/simulate"
    ):
        return JSONResponse(
            {"detail": "Modo público: alterações e dados pessoais ficam disponíveis apenas na versão com conta."},
            status_code=403,
        )
    response = await call_next(request)
    response.headers["X-OneB-Mode"] = "public"
    return response
