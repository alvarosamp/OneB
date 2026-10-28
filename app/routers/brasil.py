"""Seção Brasil: investir com educação. Ver app/brasil/__init__.py."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.auth import get_current_user
from app.brasil import events, market, products, rates
from app.brasil.simulator import DISCLAIMER, SimInput, simulate

router = APIRouter(prefix="/api/brasil", tags=["brasil"], dependencies=[Depends(get_current_user)])


class SimulationIn(BaseModel):
    initial: float = Field(0, ge=0, le=100_000_000)
    monthly: float = Field(0, ge=0, le=10_000_000)
    months: int = Field(..., ge=1, le=480)
    goal: Literal["reserva", "objetivo", "aposentadoria"]
    has_reserve: bool = True
    monthly_expenses: float | None = Field(None, ge=0, le=10_000_000)
    drop_reaction: Literal["vender", "esperar", "comprar"] = "esperar"
    experience: Literal["nenhuma", "pouca", "boa"] = "nenhuma"
    ipca_real_rate: float = Field(6.5, ge=0, le=15)
    prefixado_rate: float | None = Field(None, ge=0, le=40)
    equity_premium: float | None = Field(None, ge=-10, le=15)

    @model_validator(mode="after")
    def _has_money(self):
        if self.initial <= 0 and self.monthly <= 0:
            raise ValueError("Informe um valor inicial ou um aporte mensal.")
        return self


@router.get("/rates")
async def get_rates():
    return await asyncio.to_thread(rates.current)


@router.get("/products")
def get_products():
    return {"products": products.catalog(), "disclaimer": DISCLAIMER}


@router.post("/simulate")
async def post_simulate(body: SimulationIn):
    current = await asyncio.to_thread(rates.current)
    inp = SimInput(**body.model_dump(), rates=current)
    return await asyncio.to_thread(simulate, inp)


@router.get("/market")
async def get_market():
    return await asyncio.to_thread(market.snapshot)


@router.get("/history")
async def get_history():
    return await asyncio.to_thread(market.history)


@router.get("/events")
async def get_events():
    upcoming = events.upcoming()
    impact = await asyncio.to_thread(events.impact)
    return {"upcoming": upcoming, "impact": impact}
