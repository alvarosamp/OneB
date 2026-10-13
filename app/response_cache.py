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


def cached(key: str, ttl_seconds: float, compute: Callable[[], Any]) -> Any:
    now = time.monotonic()
    with _lock:
        hit = _store.get(key)
        if hit and now - hit[0] < ttl_seconds:
            return hit[1]
    value = compute()  # fora do lock: um cálculo lento não bloqueia outras chaves
    with _lock:
        _store[key] = (time.monotonic(), value)
    return value


def clear() -> None:
    with _lock:
        _store.clear()
