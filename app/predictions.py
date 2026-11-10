from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Evidence:
    kind: str
    direction: str
    strength: float
    confidence: float
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Prediction:
    symbol: str
    horizon: str
    direction: str
    action: str
    probability: float | None
    confidence: float
    uncertainty: float
    regime: str
    model_id: str
    model_version: str
    dataset_version: str
    evidence: list[Evidence] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_as_of: datetime | None = None
    quality_score: float | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        payload["generated_at"] = self.generated_at.isoformat()
        payload["data_as_of"] = self.data_as_of.isoformat() if self.data_as_of else None
        return payload
