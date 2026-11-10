from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AlertRule, SaasWorkspace, SubscriptionPlan, User, WatchlistItem


@dataclass(frozen=True)
class PlanLimits:
    watchlist_items: int
    alert_rules: int
    notification_channels: int
    report_templates: int
    client_segments: int
    ai_questions_per_month: int


PLAN_LIMITS = {
    SubscriptionPlan.FREE: PlanLimits(5, 5, 1, 1, 0, 20),
    SubscriptionPlan.PRO: PlanLimits(40, 80, 3, 5, 0, 500),
    SubscriptionPlan.ADVISOR: PlanLimits(200, 500, 10, 25, 50, 2000),
}


def user_id_or_none(user: User | object) -> int | None:
    return getattr(user, "id", None)


def get_or_create_workspace(db: Session, user: User | object) -> SaasWorkspace:
    user_id = user_id_or_none(user)
    workspace = db.query(SaasWorkspace).filter(SaasWorkspace.user_id == user_id).first()
    if workspace is not None:
        return workspace

    workspace = SaasWorkspace(user_id=user_id, name="Meu workspace")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_usage(db: Session, workspace: SaasWorkspace) -> dict[str, int]:
    return {
        "watchlist_items": (
            db.query(WatchlistItem)
            .filter(WatchlistItem.active.is_(True))
            .filter((WatchlistItem.workspace_id == workspace.id) | (WatchlistItem.workspace_id.is_(None)))
            .count()
        ),
        "alert_rules": (
            db.query(AlertRule)
            .join(WatchlistItem, AlertRule.watchlist_item_id == WatchlistItem.id)
            .filter(AlertRule.active.is_(True))
            .filter((WatchlistItem.workspace_id == workspace.id) | (WatchlistItem.workspace_id.is_(None)))
            .count()
        ),
        "notification_channels": len([channel for channel in workspace.channels if channel.active]),
        "report_templates": len(workspace.report_templates),
        "client_segments": len(workspace.segments),
        "ai_questions_per_month": 0,
    }


def get_plan_payload(db: Session, workspace: SaasWorkspace) -> dict:
    limits = PLAN_LIMITS[workspace.plan]
    usage = get_usage(db, workspace)
    return {
        "workspace": workspace,
        "limits": limits.__dict__,
        "usage": usage,
        "features": [
            "Monitoramento multiativo",
            "Alertas configuraveis",
            "Copiloto de analise",
            "Relatorios para decisao",
            "Sem execucao de ordens",
        ],
    }


def ensure_limit(db: Session, workspace: SaasWorkspace, key: str) -> None:
    limits = PLAN_LIMITS[workspace.plan].__dict__
    usage = get_usage(db, workspace)
    if usage[key] >= limits[key]:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=402,
            detail=f"Limite do plano {workspace.plan.value} atingido para {key}",
        )
