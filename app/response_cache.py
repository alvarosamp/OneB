"""Cache curto em memória para respostas caras e iguais para todos os usuários.

Evita recalcular a cada abertura de página (ex.: /api/regime/macro levava ~1,3 s
por chamada). O TTL é curto o bastante para não mostrar dado velho de verdade.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def cached(
    key: str,
    ttl_seconds: float,
    compute: Callable[[], Any],
    *,
    degraded: Callable[[Any], bool] | None = None,
    degraded_ttl_seconds: float = 600,
) -> Any:
    """`degraded(valor)` verdadeiro (ex.: fonte fora do ar, valor de reserva) faz o
    resultado valer só `degraded_ttl_seconds`: uma falha passageira não fica horas na tela."""
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit:
            ttl = degraded_ttl_seconds if degraded is not None and degraded(hit[1]) else ttl_seconds
            if now - hit[0] < ttl:
                return hit[1]
    value = compute()  # fora do lock: um cálculo lento não bloqueia outras chaves
    with _lock:
        _store[key] = (time.monotonic(), value)
    return value


def clear() -> None:
    with _lock:
        _store.clear()
