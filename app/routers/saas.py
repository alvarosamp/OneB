from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ClientSegment, NotificationChannel, ReportTemplate
from app.saas import ensure_limit, get_or_create_workspace, get_plan_payload
from app.schemas import (
    ClientSegmentCreate,
    ClientSegmentOut,
    NotificationChannelCreate,
    NotificationChannelOut,
    PlanUpdate,
    ReportTemplateCreate,
    ReportTemplateOut,
    SaasOverviewOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/api/saas", tags=["saas"], dependencies=[Depends(get_current_user)])


@router.get("/overview", response_model=SaasOverviewOut)
def overview(db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    payload = get_plan_payload(db, workspace)
    return {
        **payload,
        "channels": workspace.channels,
        "segments": workspace.segments,
        "report_templates": workspace.report_templates,
    }


@router.put("/workspace")
def update_workspace(payload: WorkspaceUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    workspace.name = payload.name
    workspace.brand_name = payload.brand_name
    db.commit()
    db.refresh(workspace)
    return workspace


@router.put("/plan", response_model=SaasOverviewOut)
def update_plan(payload: PlanUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    workspace.plan = payload.plan
    db.commit()
    db.refresh(workspace)
    plan_payload = get_plan_payload(db, workspace)
    return {
        **plan_payload,
        "channels": workspace.channels,
        "segments": workspace.segments,
        "report_templates": workspace.report_templates,
    }


@router.post("/channels", response_model=NotificationChannelOut, status_code=201)
def create_channel(payload: NotificationChannelCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    ensure_limit(db, workspace, "notification_channels")
    channel = NotificationChannel(
        workspace_id=workspace.id,
        channel_type=payload.channel_type,
        destination=payload.destination.strip(),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    channel = db.get(NotificationChannel, channel_id)
    if channel is None or channel.workspace_id != workspace.id:
        raise HTTPException(status_code=404, detail="Canal nao encontrado")
    channel.active = False
    db.commit()


@router.post("/segments", response_model=ClientSegmentOut, status_code=201)
def create_segment(payload: ClientSegmentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    workspace = get_or_create_workspace(db, user)
    ensure_limit(db, workspace, "client_segments")
    segment = ClientSegment(workspace_id=workspace.id, name=payload.name, description=payload.description)
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment


@router.post("/report-templates", response_model=ReportTemplateOut, status_code=201)
def create_report_template(
    payload: ReportTemplateCreate, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    workspace = get_or_create_workspace(db, user)
    ensure_limit(db, workspace, "report_templates")
    template = ReportTemplate(
        workspace_id=workspace.id,
        title=payload.title,
        audience=payload.audience,
        include_ai_summary=payload.include_ai_summary,
        include_backtest=payload.include_backtest,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template
