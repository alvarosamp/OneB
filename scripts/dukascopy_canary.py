"""Canário da fonte Dukascopy: detecta bloqueio silencioso por excesso de pedidos.

Em 08/10/2026 a fonte passou a devolver arquivo VAZIO com sucesso para qualquer
pedido (até EURUSD 10/01/2024, que tem 288 barras), por vários minutos. Nesse
estado, 'dia vazio' não prova nada. Antes de aceitar uma lacuna, os downloaders
chamam wait_until_healthy(): se o canário vier vazio, esperam; se não voltar,
falham com SourceBlocked em vez de registrar lacuna falsa.

Causa real (09/10/2026): o jetta.dukascopy.com passou a exigir desafio antirrobô (202
vazio). O canário agora usa o feed clássico (dukascopy_feed), mas a guarda continua.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dukascopy_feed as feed  # noqa: E402

CANARY = ("eurusd", "2024-01-10", "2024-01-11", "m5", "bid")  # dia conhecido: 288 barras
CANARY_MIN_ROWS = 250
_last_ok = 0.0


class SourceBlocked(RuntimeError):
    """A fonte está devolvendo vazio para um dia que sabidamente tem dados."""


def canary_rows() -> int:
    inst, start, end, tf, side = CANARY
    try:
        return len(feed.candles(inst, side, tf, start, end, use_cache=False))
    except feed.FeedUnavailable:
        return 0


def healthy(max_age_seconds: float = 120) -> bool:
    global _last_ok
    if time.monotonic() - _last_ok < max_age_seconds:
        return True
    if canary_rows() >= CANARY_MIN_ROWS:
        _last_ok = time.monotonic()
        return True
    return False


def wait_until_healthy(max_wait_seconds: float = 3600, step_seconds: float = 300) -> None:
    """Espera a fonte voltar (canário com dados). Sem volta no prazo: SourceBlocked."""
    waited = 0.0
    while not healthy():
        if waited >= max_wait_seconds:
            raise SourceBlocked(f"fonte Dukascopy devolvendo vazio para o canário há {int(waited)} s")
        print(f"fonte bloqueada (canário vazio); esperando {int(step_seconds)} s", flush=True)
        time.sleep(step_seconds)
        waited += step_seconds
