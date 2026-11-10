"""Pure dedup helpers, kept separate from the scheduler/DB so they're easy to
unit test without touching sqlite or the network.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def filter_new_by_key(items: Iterable[T], existing_keys: set, key_fn) -> list[T]:
    """Returns only the items whose key_fn(item) is not already in existing_keys."""
    seen = set(existing_keys)
    result = []
    for item in items:
        key = key_fn(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
