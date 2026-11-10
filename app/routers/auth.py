from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import (
    clear_failed_attempts,
    clear_refresh_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    is_locked_out,
    issue_refresh_token,
    register_failed_attempt,
    require_admin_user,
    require_refresh_request_header,
    revoke_refresh_token,
    rotate_refresh_token,
    set_refresh_cookie,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models import RefreshToken, User
from app.schemas import (
    CadastroRequest,
    LoginRequest,
    PasswordResetRequest,
    TokenResponse,
    UserOut,
    UsuarioCreateRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    username_norm = payload.username.strip().lower()

    if is_locked_out(db, username_norm):
        raise HTTPException(
            status_code=429, detail="Muitas tentativas incorretas. Aguarde alguns minutos e tente de novo."
        )

    user = db.query(User).filter(User.username == username_norm).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        register_failed_attempt(db, username_norm)
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")

    clear_failed_attempts(db, username_norm)
    set_refresh_cookie(response, issue_refresh_token(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/cadastro", response_model=TokenResponse, status_code=201)
def cadastro(payload: CadastroRequest, response: Response, db: Session = Depends(get_db)):
    username_norm = payload.username.strip().lower()
    if db.query(User).filter(User.username == username_norm).first():
        raise HTTPException(status_code=400, detail="Ja existe um usuario com esse nome.")

    # Cadastro público NUNCA concede admin — o primeiro visitante a se cadastrar não deve
    # virar administrador. O admin inicial vem de ADMIN_BOOTSTRAP_USERNAME/PASSWORD no
    # startup (app.auth.ensure_admin_bootstrap); depois, `python -m scripts.promote_admin`.
    user = User(username=username_norm, password_hash=hash_password(payload.password), is_admin=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    set_refresh_cookie(response, issue_refresh_token(db, user.id))
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    x_refresh_request: str | None = Header(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    db: Session = Depends(get_db),
):
    """Troca o refresh cookie por um access token novo, rotacionando o refresh.

    É a única rota (com /logout) autenticada por cookie, então exige o header
    X-Refresh-Request além de SameSite=strict — um site atacante não consegue
    definir header customizado em request cross-site.
    """
    require_refresh_request_header(x_refresh_request)
    user, new_refresh = rotate_refresh_token(db, refresh_cookie)
    set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    x_refresh_request: str | None = Header(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    db: Session = Depends(get_db),
):
    require_refresh_request_header(x_refresh_request)
    revoke_refresh_token(db, refresh_cookie)
    clear_refresh_cookie(response)
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/usuarios", response_model=list[UserOut])
def list_usuarios(admin: User = Depends(require_admin_user), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at).all()


@router.post("/usuarios", response_model=UserOut, status_code=201)
def create_usuario(
    payload: UsuarioCreateRequest, admin: User = Depends(require_admin_user), db: Session = Depends(get_db)
):
    username_norm = payload.username.strip().lower()
    if db.query(User).filter(User.username == username_norm).first():
        raise HTTPException(status_code=400, detail="Ja existe um usuario com esse nome.")

    user = User(username=username_norm, password_hash=hash_password(payload.password), is_admin=payload.is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/usuarios/{user_id}/senha", response_model=UserOut)
def reset_password(
    user_id: int,
    payload: PasswordResetRequest,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """Admin redefine a senha de um usuario existente.

    Substitui o fluxo anterior de "recriar o usuario no banco": o id e referenciado por
    watchlist, posicoes, alertas e historico de decisoes, entao apagar e recriar a conta
    descartava tudo isso sem aviso. Aqui a identidade e preservada e apenas o hash muda.

    Todas as sessoes do usuario sao derrubadas junto: se a senha esta sendo trocada
    porque pode ter vazado, deixar os refresh tokens antigos vivos anularia o reset.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")

    user.password_hash = hash_password(payload.password)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    clear_failed_attempts(db, user.username)
    db.commit()
    db.refresh(user)
    return user
