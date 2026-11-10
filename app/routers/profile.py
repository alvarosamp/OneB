from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.trader_profile import analyze_trader_profile

router = APIRouter(prefix="/api/profile", tags=["profile"], dependencies=[Depends(get_current_user)])


@router.get("/trader")
def trader_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return analyze_trader_profile(db, user.id)
