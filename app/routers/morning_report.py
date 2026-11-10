from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import morning_report
from app.auth import get_current_user
from app.db import get_db
from app.models import MorningReport, User
from app.reports import build_morning_report_pdf

router = APIRouter(prefix="/api/morning-report", tags=["morning-report"], dependencies=[Depends(get_current_user)])


def _out(report: MorningReport) -> dict:
    return {
        "id": report.id,
        "generated_at": report.generated_at.isoformat(),
        "narrative": report.narrative,
        "data": report.data,
        "delivered_telegram": report.delivered_telegram,
    }


@router.get("/today")
def get_today(db: Session = Depends(get_db)):
    report = db.query(MorningReport).order_by(MorningReport.generated_at.desc()).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Nenhuma analise matinal gerada ainda")
    return _out(report)


@router.get("/history")
def get_history(limit: int = 14, db: Session = Depends(get_db)):
    reports = db.query(MorningReport).order_by(MorningReport.generated_at.desc()).limit(limit).all()
    return [_out(r) for r in reports]


@router.post("/generate")
async def generate_now(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    report = await morning_report.generate_and_store(db, user.id)
    return _out(report)


@router.get("/{report_id}/pdf")
def download_pdf(report_id: int, db: Session = Depends(get_db)):
    report = db.query(MorningReport).filter(MorningReport.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Analise matinal nao encontrada")
    pdf_bytes = build_morning_report_pdf(report)
    filename = f"analise-matinal-{report.generated_at.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
