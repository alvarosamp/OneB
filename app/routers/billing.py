from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app import billing
from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import User

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
def plans():
    """Público: alimenta a página inicial e a de planos."""
    return {
        "free": {"name": "Free", **billing.limits_for("free")},
        "pro": {
            "name": "Pro",
            "price_label": settings.pro_price_label,
            "trial_days": settings.trial_days,
            **billing.limits_for("pro"),
        },
    }


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    return billing.billing_status(user)


@router.post("/checkout")
def checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"url": billing.create_checkout_url(db, user)}


@router.post("/portal")
def portal(user: User = Depends(get_current_user)):
    return {"url": billing.create_portal_url(user)}


@router.post("/webhook", include_in_schema=False)
async def webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    payload = await request.body()
    kind = billing.handle_webhook(db, payload, stripe_signature)
    return {"received": kind}
