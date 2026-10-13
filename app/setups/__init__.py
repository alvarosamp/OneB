"""Setups como código. Cada setup é uma máquina de estados causal (app.setups.base)."""
from __future__ import annotations

import json
from pathlib import Path

from app.opportunity import sha256_text
from app.setups.gold_fakeout import GoldFakeoutOpen

PREREGISTRATION_DIR = Path(__file__).resolve().parents[2] / "configs" / "preregistration"
LOCK_PATH = PREREGISTRATION_DIR / "LOCK.json"

SETUPS = {GoldFakeoutOpen.name: GoldFakeoutOpen}


class PreregistrationError(RuntimeError):
    pass


def load_preregistered(name: str) -> tuple[dict, str]:
    """Carrega a config congelada e confere o SHA256 contra o LOCK commitado.

    Qualquer edição no arquivo depois do registro quebra a verificação: a
    mudança tem que virar um novo arquivo/versão, e a contagem de amostra zera.
    """
    path = PREREGISTRATION_DIR / f"{name}.json"
    raw = path.read_text(encoding="utf-8")
    digest = sha256_text(raw.replace("\r\n", "\n"))
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8")) if LOCK_PATH.exists() else {}
    expected = (lock.get(name) or {}).get("sha256")
    if expected is None:
        raise PreregistrationError(f"{name} não está no LOCK de pré-registro.")
    if expected != digest:
        raise PreregistrationError(f"{name} foi alterado após o registro (sha256 {digest[:12]} != {expected[:12]}).")
    return json.loads(raw), digest


def build_setup(config: dict):
    return SETUPS[config["setup"]](config)
