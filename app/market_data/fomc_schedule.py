"""Datas de decisão do FOMC (segundo dia da reunião, 14:00 de Nova York).

Fonte: federalreserve.gov/monetarypolicy/fomccalendars.htm, consultada em 10/10/2026.
As datas de 2027 são provisórias até a reunião anterior confirmar. Revisar a cada ano.

O FRED não serve para isso: a "release" 101 (FOMC Press Release) aparece com data em
quase todos os dias, e o app mostrava um FOMC falso diariamente.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
DECISION_TIME_ET = time(14, 0)

FOMC_DECISION_DATES: tuple[date, ...] = (
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 10, 28), date(2026, 12, 9),
    # 2027: provisórias
    date(2027, 1, 27), date(2027, 3, 17), date(2027, 4, 28), date(2027, 6, 9),
    date(2027, 7, 28), date(2027, 9, 15), date(2027, 10, 27), date(2027, 12, 8),
)


def decisions_between(start: date, end: date) -> list[datetime]:
    """Instantes (UTC) das decisões do FOMC entre start e end, inclusive."""
    return [datetime.combine(d, DECISION_TIME_ET, NEW_YORK).astimezone(timezone.utc)
            for d in FOMC_DECISION_DATES if start <= d <= end]
