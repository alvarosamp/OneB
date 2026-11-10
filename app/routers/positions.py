from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Transaction, User
from app.positions import compute_position
from app.scope import latest_snapshot_for_symbol
from app.schemas import PositionSummaryOut, TransactionCreate, TransactionOut

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _latest_price(db: Session, symbol: str) -> float | None:
    snap = latest_snapshot_for_symbol(db, symbol)
    return snap.price if snap else None


@router.get("", response_model=list[PositionSummaryOut])
def list_positions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    symbols = [s for (s,) in db.query(Transaction.symbol).filter(Transaction.user_id == user.id).distinct().all()]
    summaries = []
    for symbol in symbols:
        transactions = (
            db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.symbol == symbol).all()
        )
        current_price = _latest_price(db, symbol)
        summary = compute_position(symbol, transactions, current_price)
        summaries.append(summary)
    return summaries


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(
    payload: TransactionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    tx = Transaction(
        user_id=user.id,
        symbol=payload.symbol.upper().strip(),
        side=payload.side,
        quantity=payload.quantity,
        price=payload.price,
        executed_at=payload.executed_at,
        notes=payload.notes,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/{symbol}/transactions", response_model=list[TransactionOut])
def list_transactions(symbol: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Transaction)
        .filter(Transaction.user_id == user.id, Transaction.symbol == symbol.upper())
        .order_by(Transaction.executed_at.desc())
        .all()
    )


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = db.get(Transaction, transaction_id)
    if not tx or tx.user_id != user.id:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    db.delete(tx)
    db.commit()
