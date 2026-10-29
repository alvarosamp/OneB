from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app import analysis, scheduler
from app.reports import build_pdf_report

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


@router.get("/pdf")
def download_report(db: Session = Depends(get_db)):
    pdf_bytes = build_pdf_report(db)
    filename = f"monitor-nasdaq-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.json")
def export_json(db: Session = Depends(get_db)):
    return analysis.build_export(db)


@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db)):
    content = analysis.export_csv(analysis.build_export(db))
    filename = f"monitor-nasdaq-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.csv"
    return Response(
        # BOM para o Excel abrir acentos corretamente
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/refresh")
async def refresh_now():
    """Força coleta imediata de cotações, notícias e calendários (sem esperar o agendador)."""
    await scheduler.refresh_all()
    return {"status": "ok"}
