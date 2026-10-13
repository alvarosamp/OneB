"""Contrato único de oportunidade (plano §1.1).

Uma `Opportunity` é o objeto auditável que o Terminal, a OneB AI e o placar
consomem. Ela nunca é editada: cada transição de estado gera um novo evento no
ledger (app.opportunity_ledger) encadeado por hash.

`approval` vem SEMPRE da configuração versionada (configs/manual_advisors_v1.json),
nunca de um score. Enquanto um setup estiver em RESEARCH/SHADOW, níveis de
entrada/stop/alvo só podem aparecer como `research_plan`, nunca como recomendação.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

ADVISORS_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "manual_advisors_v1.json"


class SetupState(str, Enum):
    IDLE = "IDLE"
    BREAK_DETECTED = "BREAK_DETECTED"
    WAITING_CONFIRMATION_1 = "WAITING_CONFIRMATION_1"
    WAITING_CONFIRMATION_2 = "WAITING_CONFIRMATION_2"
    READY_TO_ENTER = "READY_TO_ENTER"
    POSITION_OPEN = "POSITION_OPEN"
    TARGET = "TARGET"
    STOP = "STOP"
    TIME_EXIT = "TIME_EXIT"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


TERMINAL_STATES = {SetupState.TARGET, SetupState.STOP, SetupState.TIME_EXIT, SetupState.INVALIDATED, SetupState.EXPIRED}

# Fração do caminho até READY_TO_ENTER, usada só para a barra de progresso da UI.
STATE_PROGRESS = {
    SetupState.IDLE: 0.0,
    SetupState.BREAK_DETECTED: 0.25,
    SetupState.WAITING_CONFIRMATION_1: 0.35,
    SetupState.WAITING_CONFIRMATION_2: 0.7,
    SetupState.READY_TO_ENTER: 1.0,
    SetupState.POSITION_OPEN: 1.0,
}


class Approval(str, Enum):
    RESEARCH = "RESEARCH"
    SHADOW = "SHADOW"
    PAPER = "PAPER"
    LIVE_MANUAL = "LIVE_MANUAL"


ACTIONABLE_APPROVALS = {Approval.PAPER, Approval.LIVE_MANUAL}


@dataclass(frozen=True)
class Levels:
    entry: float
    stop: float
    target: float
    time_stop_minutes: int

    @property
    def reward_to_risk(self) -> float | None:
        risk = abs(self.entry - self.stop)
        return abs(self.target - self.entry) / risk if risk else None


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    kind: str
    text: str
    value: float | str | None = None
    unit: str | None = None
    source: str = "engine"
    as_of: str | None = None


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    symbol: str
    instrument_type: str
    setup: str
    setup_version: str
    state: SetupState
    direction: str | None
    approval: Approval
    data_as_of: str
    levels: Levels | None = None
    evidence: tuple[EvidenceItem, ...] = ()
    counter_evidence: tuple[EvidenceItem, ...] = ()
    regime: str | None = None
    quality: dict | None = None
    reliability: dict | None = None

    def to_public_dict(self) -> dict:
        """Forma servida pela API. Níveis de setups não aprovados viram `research_plan`."""
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["approval"] = self.approval.value
        payload["progress"] = STATE_PROGRESS.get(self.state)
        payload["evidence"] = [asdict(item) for item in self.evidence]
        payload["counter_evidence"] = [asdict(item) for item in self.counter_evidence]
        levels = payload.pop("levels")
        payload["levels"] = None
        payload["research_plan"] = None
        if levels is not None:
            levels["reward_to_risk"] = self.levels.reward_to_risk
            if self.approval in ACTIONABLE_APPROVALS:
                payload["levels"] = levels
            else:
                payload["research_plan"] = {**levels, "notice": "Plano de pesquisa (shadow); não é recomendação."}
        return payload


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def config_hash(config: dict) -> str:
    """Hash estável de uma configuração congelada; vira o `setup_version`."""
    return sha256_text(canonical_json(config))[:16]


def load_advisors(path: Path = ADVISORS_CONFIG) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["advisors"]


def approval_for(symbol: str, path: Path = ADVISORS_CONFIG) -> Approval:
    """Aprovação vem só da configuração. Símbolo desconhecido = RESEARCH (fail-closed)."""
    try:
        advisors = load_advisors(path)
    except (OSError, ValueError, KeyError):
        return Approval.RESEARCH
    for advisor in advisors.values():
        if advisor.get("symbol") != symbol:
            continue
        explicit = advisor.get("approval")
        if explicit in Approval.__members__:
            approval = Approval(explicit)
        else:
            approval = Approval.PAPER if advisor.get("approved_for_paper") else Approval.SHADOW
        # Paper/live exigem relógio verificado; sem isso cai para SHADOW.
        if approval in ACTIONABLE_APPROVALS and not advisor.get("broker_timezone_verified"):
            return Approval.SHADOW
        return approval
    return Approval.RESEARCH


def parse_time(value: str | datetime) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@dataclass
class Transition:
    """Uma mudança de estado emitida por uma máquina de setup ou pelo executor shadow."""

    at: str
    from_state: SetupState
    to_state: SetupState
    reason: str
    direction: str | None = None
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "at": self.at,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "reason": self.reason,
            "direction": self.direction,
            "payload": self.payload,
        }
