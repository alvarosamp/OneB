"""Autenticação do backend (o front é um SPA separado).

Modelo de contas: cadastro público é aberto, mas NUNCA concede admin (ver
app.routers.auth.cadastro). O primeiro admin nasce do bootstrap explícito via
ADMIN_BOOTSTRAP_USERNAME/ADMIN_BOOTSTRAP_PASSWORD (ensure_admin_bootstrap); depois
disso, promoções passam por `python -m scripts.promote_admin <usuario>`.

Modelo de sessão, em duas partes:

  * access token  -- JWT curto (15 min por padrão), devolvido no corpo da resposta.
    O SPA guarda só em memória e manda em `Authorization: Bearer`. Não vai para
    localStorage: um XSS lê localStorage, e antes isso significava roubar uma
    credencial válida por sete dias, irrevogável.
  * refresh token -- string opaca de 30 dias em cookie httpOnly, guardada no banco
    apenas como hash sha256. Rotaciona a cada uso; se um token já rotacionado
    reaparecer (sinal de credencial copiada), a família inteira é revogada.

O header `Authorization: Bearer` continua sendo aceito por clientes não-browser
(scripts, testes) sem nenhum cookie envolvido.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import LoginAttempt, RefreshToken, User

logger = logging.getLogger(__name__)

# bcrypt truncates/rejects input over 72 bytes; long passwords are hashed first
# so length never causes a hard failure at hash/verify time.
_MAX_PASSWORD_BYTES = 72
_JWT_ALGORITHM = "HS256"

# Header obrigatório nas duas rotas autenticadas por cookie (/refresh e /logout).
# Um <form> ou <img> de um site atacante não consegue definir um header customizado,
# então exigir isso — junto com SameSite=strict — fecha o vetor de CSRF que voltou a
# existir no momento em que a sessão passou a depender de um cookie.
REFRESH_REQUEST_HEADER = "x-refresh-request"


def _prepare(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > _MAX_PASSWORD_BYTES:
        encoded = hashlib.sha256(encoded).digest()
    return encoded


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- Access token (JWT curto, em memória no cliente) --------------------------------


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at, "typ": "access"}
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = _decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Requer permissão de administrador")
    return user


# --- Refresh token (opaco, rotacionado, com detecção de reuso) ----------------------


def _hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_refresh_token(db: Session, user_id: int, family_id: str | None = None) -> str:
    """Cria um refresh token novo e devolve o valor em claro (só aqui ele existe em claro)."""
    raw_token = secrets.token_urlsafe(48)
    record = RefreshToken(
        user_id=user_id,
        family_id=family_id or str(uuid.uuid4()),
        token_hash=_hash_refresh_token(raw_token),
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    db.commit()
    return raw_token


def _revoke_family(db: Session, family_id: str) -> None:
    now = datetime.now(timezone.utc)
    (
        db.query(RefreshToken)
        .filter(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )
    db.commit()


def rotate_refresh_token(db: Session, raw_token: str | None) -> tuple[User, str]:
    """Troca um refresh token por um par (usuário, novo refresh token).

    Levanta 401 quando o token é desconhecido, expirado ou já foi usado. No caso de
    reuso, toda a família é revogada primeiro: se a credencial vazou, tanto a cópia do
    atacante quanto a sessão legítima morrem, e o dono é forçado a logar de novo.
    """
    if not raw_token:
        raise HTTPException(status_code=401, detail="Sessão expirada — faça login novamente.")

    record = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_refresh_token(raw_token)).first()
    if record is None:
        raise HTTPException(status_code=401, detail="Sessão expirada — faça login novamente.")

    if record.revoked_at is not None:
        logger.warning(
            "Refresh token ja rotacionado foi reapresentado (user_id=%s, family=%s) -- "
            "revogando a familia inteira por suspeita de credencial copiada.",
            record.user_id,
            record.family_id,
        )
        _revoke_family(db, record.family_id)
        raise HTTPException(status_code=401, detail="Sessão expirada — faça login novamente.")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:  # SQLite devolve naive; normaliza pra comparar
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sessão expirada — faça login novamente.")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    new_raw = issue_refresh_token(db, user.id, family_id=record.family_id)
    new_record = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_refresh_token(new_raw)).first()
    record.revoked_at = datetime.now(timezone.utc)
    record.replaced_by_id = new_record.id if new_record else None
    db.commit()
    return user, new_raw


def revoke_refresh_token(db: Session, raw_token: str | None) -> None:
    """Logout: mata a família inteira, não só o token apresentado — senão qualquer
    rotação anterior ainda válida continuaria servindo para voltar a entrar."""
    if not raw_token:
        return
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_refresh_token(raw_token)).first()
    if record is not None:
        _revoke_family(db, record.family_id)


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        # Secure só fora de desenvolvimento: o navegador descarta cookie Secure em
        # http:// puro, o que quebraria o dev local em http://localhost.
        secure=settings.environment == "production",
        samesite="strict",
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.refresh_cookie_name, path="/api/auth")


def require_refresh_request_header(x_refresh_request: str | None) -> None:
    if not x_refresh_request:
        raise HTTPException(status_code=403, detail="Requisição inválida.")


# --- Bootstrap do admin inicial ------------------------------------------------------


def ensure_admin_bootstrap(db: Session) -> None:
    """Cria o admin inicial a partir de ADMIN_BOOTSTRAP_USERNAME/PASSWORD, se configurado.

    Cadastro público nunca concede is_admin (ver app.routers.auth.cadastro) — isso antes
    era "quem se cadastrar primeiro vira admin", ou seja, qualquer um que chegasse ao
    /cadastro antes do dono num deploy novo ganhava controle total. Sem essas variáveis
    configuradas, o banco fica sem admin até alguém com acesso ao banco rodar
    `python -m scripts.promote_admin <usuario>`.
    """
    if db.query(User).count() > 0:
        return
    if not settings.admin_bootstrap_username or not settings.admin_bootstrap_password:
        logger.warning(
            "Nenhum usuario cadastrado e ADMIN_BOOTSTRAP_USERNAME/ADMIN_BOOTSTRAP_PASSWORD "
            "nao configurados no .env -- o primeiro cadastro NAO vira admin automaticamente "
            "(isso mudou de proposito). Configure essas variaveis e reinicie, ou promova um "
            "usuario depois com `python -m scripts.promote_admin <usuario>`."
        )
        return

    username_norm = settings.admin_bootstrap_username.strip().lower()
    admin = User(
        username=username_norm,
        password_hash=hash_password(settings.admin_bootstrap_password),
        is_admin=True,
    )
    db.add(admin)
    db.commit()
    logger.info("Admin inicial '%s' criado a partir de ADMIN_BOOTSTRAP_USERNAME.", username_norm)


# --- Rate limiting de login, persistido no banco (ver LoginAttempt em app/models.py) ---
# Antes era um dict em memória: zerava a cada restart/deploy e cada réplica tinha o seu,
# então bastava reiniciar o processo (ou espalhar tentativas entre réplicas) pra anular
# o bloqueio.
_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 300


def is_locked_out(db: Session, username: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_LOCKOUT_SECONDS)
    recent_failures = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.username == username, LoginAttempt.attempted_at >= cutoff)
        .count()
    )
    return recent_failures >= _MAX_ATTEMPTS


def register_failed_attempt(db: Session, username: str) -> None:
    db.add(LoginAttempt(username=username, attempted_at=datetime.now(timezone.utc)))
    db.commit()


def clear_failed_attempts(db: Session, username: str) -> None:
    db.query(LoginAttempt).filter(LoginAttempt.username == username).delete()
    db.commit()
