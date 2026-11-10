from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, SaasWorkspace, User
from app.saas import get_or_create_workspace, user_id_or_none


def scoped_workspace(db: Session, user: User | object) -> SaasWorkspace:
    return get_or_create_workspace(db, user)


def audit(
    db: Session,
    user: User | object,
    action: str,
    entity_type: str = "",
    entity_id: str | int = "",
    details: dict[str, Any] | None = None,
) -> None:
    workspace = scoped_workspace(db, user)
    db.add(
        AuditLog(
            user_id=user_id_or_none(user),
            workspace_id=workspace.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=json.dumps(details or {}, ensure_ascii=True),
        )
    )
