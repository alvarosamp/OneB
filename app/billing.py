"""Planos, limites e cobrança (Stripe).

Dois planos: **free** (monitor básico) e **pro** (alertas no Telegram, painel de risco, análise
matinal, IA, PDF). Todo usuário novo ganha `settings.trial_days` dias de Pro de teste.

`User.plan` é o que vale depois do teste: o webhook do Stripe liga/desliga "pro", e o admin
também pode ligar à mão (cliente que paga por fora, cortesia). O plano efetivo, que o resto do
app usa, é `effective_plan(user)`.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.models import User, utcnow

logger = logging.getLogger(__name__)

# Status de assinatura do Stripe que mantêm o acesso Pro (past_due = tolerância enquanto o Stripe
# tenta cobrar de novo; se falhar de vez a assinatura vira canceled e o acesso termina).
_ACTIVE_STATUSES = {"active", "trialing", "past_due"}


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite devolve datas sem fuso; marca como UTC para o JSON sair com 'Z'."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def trial_active(user: User) -> bool:
    ends = as_utc(user.trial_ends_at)
    return ends is not None and ends > utcnow()


def effective_plan(user: User) -> str:
    if user.plan == "pro" or trial_active(user):
        return "pro"
    return "free"


def limits_for(plan: str) -> dict:
    if plan == "pro":
        return {"max_symbols": settings.pro_max_symbols, "max_rules": settings.pro_max_rules}
    return {"max_symbols": settings.free_max_symbols, "max_rules": settings.free_max_rules}


def start_trial(user: User) -> None:
    if settings.trial_days > 0:
        user.trial_ends_at = utcnow() + timedelta(days=settings.trial_days)


def billing_status(user: User) -> dict:
    plan = effective_plan(user)
    ends = as_utc(user.trial_ends_at)
    return {
        "plan": plan,
        "paid": user.plan == "pro",
        "on_trial": user.plan != "pro" and trial_active(user),
        "trial_ends_at": ends.isoformat() if ends else None,
        "subscription_status": user.subscription_status,
        "current_period_end": as_utc(user.current_period_end).isoformat() if user.current_period_end else None,
        "limits": limits_for(plan),
        "checkout_enabled": stripe_enabled(),
        "has_customer": bool(user.stripe_customer_id),
    }


# --- dependências de rota -------------------------------------------------------------------


def require_pro(user: User = Depends(get_current_user)) -> User:
    """402 para recursos do plano Pro; o front transforma isso num convite para assinar."""
    if effective_plan(user) != "pro":
        raise HTTPException(status_code=402, detail="Recurso do plano Pro. Assine para liberar.")
    return user


_llm_usage: dict[tuple[int, date], int] = defaultdict(int)


def consume_llm_quota(user: User = Depends(require_pro)) -> User:
    """Limite diário de chamadas de IA por usuário (em memória, por processo) — controla o custo."""
    today = datetime.now(timezone.utc).date()
    for key in [k for k in _llm_usage if k[1] != today]:
        _llm_usage.pop(key, None)
    key = (user.id, today)
    if _llm_usage[key] >= settings.llm_daily_limit:
        raise HTTPException(
            status_code=429, detail=f"Limite diário de {settings.llm_daily_limit} consultas de IA atingido."
        )
    _llm_usage[key] += 1
    return user


_hits: dict[tuple[str, int], list[float]] = defaultdict(list)


def rate_limit(name: str, max_calls: int, per_seconds: int):
    """Dependência: no máximo `max_calls` por usuário a cada `per_seconds` (protege APIs externas)."""

    def dep(user: User = Depends(get_current_user)) -> User:
        now = time.time()
        key = (name, user.id)
        _hits[key] = [t for t in _hits[key] if now - t < per_seconds]
        if len(_hits[key]) >= max_calls:
            raise HTTPException(status_code=429, detail="Muitas requisições. Aguarde um instante.")
        _hits[key].append(now)
        return user

    return dep


def check_symbol_quota(db: Session, user: User, symbol: str) -> None:
    """Levanta 402 se adicionar `symbol` estouraria o limite de ativos do plano."""
    from app.models import WatchlistItem

    active = db.query(WatchlistItem).filter(
        WatchlistItem.user_id == user.id, WatchlistItem.active.is_(True)
    )
    if active.filter(WatchlistItem.symbol == symbol).first():
        return
    cap = limits_for(effective_plan(user))["max_symbols"]
    if active.count() >= cap:
        raise HTTPException(status_code=402, detail=f"Seu plano permite até {cap} ativos na watchlist.")


def check_rule_quota(db: Session, user: User) -> None:
    from app.models import AlertRule, WatchlistItem

    count = (
        db.query(AlertRule)
        .join(WatchlistItem, AlertRule.watchlist_item_id == WatchlistItem.id)
        .filter(WatchlistItem.user_id == user.id, AlertRule.active.is_(True))
        .count()
    )
    cap = limits_for(effective_plan(user))["max_rules"]
    if count >= cap:
        raise HTTPException(status_code=402, detail=f"Seu plano permite até {cap} regras de alerta.")


# --- Stripe ---------------------------------------------------------------------------------


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key and settings.stripe_price_id)


def _stripe():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _require_stripe() -> None:
    if not stripe_enabled():
        raise HTTPException(status_code=503, detail="Pagamento ainda não está configurado.")


def create_checkout_url(db: Session, user: User) -> str:
    _require_stripe()
    stripe = _stripe()
    if user.plan == "pro" and user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Você já tem uma assinatura ativa.")

    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email or None, metadata={"user_id": str(user.id), "username": user.username}
        )
        user.stripe_customer_id = customer["id"]
        db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=user.stripe_customer_id,
        client_reference_id=str(user.id),
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        allow_promotion_codes=True,
        success_url=f"{settings.frontend_origin}/planos?checkout=ok",
        cancel_url=f"{settings.frontend_origin}/planos?checkout=cancelado",
    )
    return session["url"]


def create_portal_url(user: User) -> str:
    _require_stripe()
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura para gerenciar.")
    session = _stripe().billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=f"{settings.frontend_origin}/planos"
    )
    return session["url"]


def _ts(value) -> datetime | None:
    return datetime.fromtimestamp(value, tz=timezone.utc) if value else None


def apply_subscription(user: User, sub: dict) -> None:
    """Espelha o estado da assinatura do Stripe no usuário (idempotente)."""
    status = sub.get("status", "")
    user.stripe_customer_id = sub.get("customer") or user.stripe_customer_id
    user.subscription_status = status
    period_end = sub.get("current_period_end")
    if period_end is None:  # versões novas da API movem o campo para o item da assinatura
        items = (sub.get("items") or {}).get("data") or []
        period_end = items[0].get("current_period_end") if items else None
    user.current_period_end = _ts(period_end)
    if status in _ACTIVE_STATUSES:
        user.plan = "pro"
        user.stripe_subscription_id = sub.get("id")
    else:
        user.plan = "free"
        user.stripe_subscription_id = None


def _plain(obj) -> dict:
    """Objetos do SDK do Stripe não são dict (sem .get); converte para dict puro."""
    return obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)


def _find_user(db: Session, customer_id: str | None, user_id: str | None = None) -> User | None:
    if user_id and str(user_id).isdigit():
        user = db.get(User, int(user_id))
        if user:
            return user
    if customer_id:
        return db.query(User).filter(User.stripe_customer_id == customer_id).first()
    return None


def handle_webhook(db: Session, payload: bytes, signature: str | None) -> str:
    """Valida a assinatura do Stripe e aplica o evento. Devolve o tipo do evento tratado."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook não configurado.")
    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(payload, signature or "", settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Assinatura do webhook inválida.")

    kind = event["type"]
    obj = _plain(event["data"]["object"])

    if kind == "checkout.session.completed" and obj.get("mode") == "subscription":
        user = _find_user(db, obj.get("customer"), obj.get("client_reference_id"))
        if user and obj.get("subscription"):
            sub = stripe.Subscription.retrieve(obj["subscription"])
            apply_subscription(user, _plain(sub))
            db.commit()
    elif kind in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
        user = _find_user(db, obj.get("customer"))
        if user:
            apply_subscription(user, obj)
            db.commit()
        else:
            logger.warning("Webhook %s para cliente desconhecido %s", kind, obj.get("customer"))
    return kind
