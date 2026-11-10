from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import billing
from app.auth import (
    clear_failed_attempts,
    create_access_token,
    get_current_user,
    hash_password,
    is_locked_out,
    register_failed_attempt,
    require_admin_user,
    verify_password,
)
from app.db import get_db
from app.models import AlertLog, Transaction, User, WatchlistItem, utcnow
from app.schemas import (
    CadastroRequest,
    LoginRequest,
    PlanUpdateRequest,
    TokenResponse,
    UserOut,
    UsuarioCreateRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def serialize_user(user: User) -> UserOut:
    plan = billing.effective_plan(user)
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        created_at=user.created_at,
        plan=plan,
        paid=user.plan == "pro",
        on_trial=user.plan != "pro" and billing.trial_active(user),
        trial_ends_at=billing.as_utc(user.trial_ends_at),
        telegram_linked=bool(user.telegram_chat_id),
    )


def _token_for(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id), user=serialize_user(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    login_norm = payload.username.strip().lower()

    if is_locked_out(login_norm):
        raise HTTPException(
            status_code=429, detail="Muitas tentativas incorretas. Aguarde alguns minutos e tente de novo."
        )

    user = db.query(User).filter(User.username == login_norm).first()
    if user is None and "@" in login_norm:
        user = db.query(User).filter(User.email == login_norm).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        register_failed_attempt(login_norm)
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    clear_failed_attempts(login_norm)
    return _token_for(user)


@router.post("/cadastro", response_model=TokenResponse, status_code=201)
def cadastro(payload: CadastroRequest, db: Session = Depends(get_db)):
    """Cadastro aberto. A primeira conta do sistema vira administradora; as demais são clientes."""
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="É preciso aceitar os Termos de Uso e a Política de Privacidade.")

    username_norm = payload.username.strip().lower()
    email_norm = payload.email.strip().lower()
    if db.query(User).filter(User.username == username_norm).first():
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse nome.")
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=400, detail="Já existe uma conta com esse e-mail.")

    first = db.query(User).count() == 0
    user = User(
        username=username_norm,
        email=email_norm,
        password_hash=hash_password(payload.password),
        is_admin=first,
        accepted_terms_at=utcnow(),
        plan="pro" if first else "free",  # o dono do sistema não paga a si mesmo
    )
    if not first:
        billing.start_trial(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return serialize_user(user)


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Apaga a conta e todos os dados do usuário (direito de exclusão da LGPD)."""
    if user.stripe_subscription_id and user.plan == "pro":
        raise HTTPException(
            status_code=400, detail="Cancele a assinatura em Planos antes de excluir a conta."
        )
    # Os itens da watchlist levam junto regras e cotações (cascade).
    for item in db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).all():
        db.delete(item)
    db.query(AlertLog).filter(AlertLog.user_id == user.id).delete()
    db.query(Transaction).filter(Transaction.user_id == user.id).delete()
    db.delete(user)
    db.commit()


# --- Telegram ---------------------------------------------------------------------------------


@router.post("/telegram/link-code")
def telegram_link_code(user: User = Depends(billing.require_pro), db: Session = Depends(get_db)):
    """Gera um código de uso único; o usuário manda `/vincular CODIGO` ao bot para ligar o chat."""
    user.telegram_link_code = secrets.token_hex(4).upper()
    db.commit()
    return {"code": user.telegram_link_code, "linked": bool(user.telegram_chat_id)}


@router.delete("/telegram", status_code=204)
def telegram_unlink(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.telegram_chat_id = None
    user.telegram_link_code = None
    db.commit()


# --- Administração ----------------------------------------------------------------------------


@router.get("/usuarios", response_model=list[UserOut])
def list_usuarios(admin: User = Depends(require_admin_user), db: Session = Depends(get_db)):
    return [serialize_user(u) for u in db.query(User).order_by(User.created_at).all()]


@router.post("/usuarios", response_model=UserOut, status_code=201)
def create_usuario(
    payload: UsuarioCreateRequest, admin: User = Depends(require_admin_user), db: Session = Depends(get_db)
):
    username_norm = payload.username.strip().lower()
    if db.query(User).filter(User.username == username_norm).first():
        raise HTTPException(status_code=400, detail="Já existe um usuário com esse nome.")

    user = User(username=username_norm, password_hash=hash_password(payload.password), is_admin=payload.is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.patch("/usuarios/{user_id}/plano", response_model=UserOut)
def set_user_plan(
    user_id: int,
    payload: PlanUpdateRequest,
    admin: User = Depends(require_admin_user),
    db: Session = Depends(get_db),
):
    """Ativação manual do plano (cliente que pagou por fora, cortesia, correção)."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    target.plan = payload.plan
    db.commit()
    db.refresh(target)
    return serialize_user(target)
