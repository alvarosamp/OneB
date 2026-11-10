from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import billing, morning_report
from app.db import get_db
from app.models import MorningReport, User
from app.reports import build_morning_report_pdf

router = APIRouter(prefix="/api/morning-report", tags=["morning-report"])


def _out(report: MorningReport, watchlist: list[dict] | None = None) -> dict:
    data = dict(report.data or {})
    if watchlist is not None:
        data["watchlist"] = watchlist
    return {
        "id": report.id,
        "generated_at": report.generated_at.isoformat(),
        "narrative": report.narrative,
        "data": data,
        "delivered_telegram": report.delivered_telegram,
    }


@router.get("/today")
def get_today(user: User = Depends(billing.require_pro), db: Session = Depends(get_db)):
    report = db.query(MorningReport).order_by(MorningReport.generated_at.desc()).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Nenhuma analise matinal gerada ainda")
    return _out(report, morning_report.watchlist_section(db, user.id))


@router.get("/history")
def get_history(limit: int = 14, user: User = Depends(billing.require_pro), db: Session = Depends(get_db)):
    reports = db.query(MorningReport).order_by(MorningReport.generated_at.desc()).limit(limit).all()
    return [_out(r) for r in reports]


@router.post("/generate")
async def generate_now(
    user: User = Depends(billing.rate_limit("morning-generate", 3, 600)), db: Session = Depends(get_db)
):
    billing.require_pro(user)
    report = await morning_report.generate_and_store(db)
    return _out(report, morning_report.watchlist_section(db, user.id))


@router.get("/{report_id}/pdf")
def download_pdf(report_id: int, user: User = Depends(billing.require_pro), db: Session = Depends(get_db)):
    report = db.query(MorningReport).filter(MorningReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Analise matinal nao encontrada")
    data = dict(report.data or {})
    data["watchlist"] = morning_report.watchlist_section(db, user.id)
    personal = SimpleNamespace(generated_at=report.generated_at, narrative=report.narrative, data=data)
    pdf_bytes = build_morning_report_pdf(personal)
    filename = f"analise-matinal-{report.generated_at.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
