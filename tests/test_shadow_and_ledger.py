from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.baselines import ready_signals
from app.db import Base
from app.execution_sim import CostModel, replay_ready_signals
from app.models import OpportunityEvent
from app.opportunity import Approval, SetupState, Transition, approval_for
from app.opportunity_ledger import current_opportunities, diff_since, record_transition, timeline, verify_chain
from app.setups.base import resample_bars
from app.setups.gold_fakeout import GoldFakeoutOpen
from app.shadow import ShadowEngine

CONFIG = {
    "setup": "gold_fakeout_open", "symbol": "XAUUSD.s", "timeframe_minutes": 10, "trend_sma": 20,
    "break_lookback": 5, "session_window_brt": ["00:00", "23:59"], "server_utc_offset_hours": 0,
    "target_r": 1.5, "max_hold_minutes": 60, "point": 0.01,
}


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _m5(n=3000, seed=11):
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 1.2, n))
    idx = pd.date_range("2026-06-01 00:00", periods=n, freq="5min")
    opens = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(opens, close) + rng.uniform(0, 0.8, n)
    low = np.minimum(opens, close) - rng.uniform(0, 0.8, n)
    return pd.DataFrame({"open": opens, "high": high, "low": low, "close": close, "spread": 25, "tick_volume": 1}, index=idx)


def test_shadow_live_matches_replay_after_warmup():
    m5 = _m5()
    warm = 600
    engine = ShadowEngine(CONFIG)
    engine.on_bars(m5.iloc[:warm], m5.index[warm - 1] + pd.Timedelta(minutes=5))
    live = []
    for k in range(warm + 1, len(m5) + 1):
        live.extend(engine.on_bars(m5.iloc[:k], m5.index[k - 1] + pd.Timedelta(minutes=5)))

    m10 = resample_bars(m5, 10, closed_before=m5.index[-1] + pd.Timedelta(minutes=5))
    replay = GoldFakeoutOpen(CONFIG).run(m10)
    cutoff = (m5.index[warm - 1] + pd.Timedelta(minutes=5)).isoformat()
    replay_ready = [t for t in ready_signals(replay) if t["at"] > cutoff]
    live_ready = [t for t in live if t.to_state == SetupState.READY_TO_ENTER]
    assert [t["opportunity_id"] for t in replay_ready] == [t.payload["opportunity_id"] for t in live_ready]

    trades, _ = replay_ready_signals(m5, replay_ready, CostModel.from_config(CONFIG))
    replay_exits = [(t.opportunity_id, t.outcome, t.r) for t in trades if t.outcome in ("TARGET", "STOP", "TIME_EXIT")]
    live_exits = [(t.payload["opportunity_id"], t.to_state.value, t.payload["r"]) for t in live if t.to_state.value in ("TARGET", "STOP", "TIME_EXIT")]
    assert live_exits == replay_exits
    assert live_exits, "a série sintética deveria produzir ao menos um trade"


def _transition(at, to, frm=SetupState.IDLE, oid="gold:1", **payload):
    return Transition(at=at, from_state=frm, to_state=to, reason=f"{frm.value}->{to.value}", direction="long",
                      payload={"opportunity_id": oid, **payload})


def test_ledger_hash_chain_detects_tampering(db):
    for i, state in enumerate([SetupState.BREAK_DETECTED, SetupState.WAITING_CONFIRMATION_1]):
        record_transition(db, _transition(f"2026-06-01T10:0{i}:00", state), setup="gold_fakeout_open",
                          setup_version="abc", symbol="XAUUSD.s", mode="SHADOW", approval=Approval.SHADOW)
    assert verify_chain(db, "SHADOW") == {"ok": True, "checked": 2, "broken_at_id": None}
    first = db.query(OpportunityEvent).order_by(OpportunityEvent.id).first()
    first.reason = "editado depois"
    db.commit()
    result = verify_chain(db, "SHADOW")
    assert result["ok"] is False and result["broken_at_id"] == first.id


def test_research_opportunity_hides_levels_and_diff_reports_changes(db):
    now = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    steps = [
        ("2026-06-01T10:00:00+00:00", SetupState.BREAK_DETECTED, {}),
        ("2026-06-01T10:10:00+00:00", SetupState.WAITING_CONFIRMATION_2, {}),
        ("2026-06-01T10:20:00+00:00", SetupState.READY_TO_ENTER,
         {"stop": 1995.0, "reference_close": 2000.0, "target_r": 1.5, "max_hold_minutes": 240}),
    ]
    for at, state, extra in steps:
        record_transition(db, _transition(at, state, **extra), setup="gold_fakeout_open", setup_version="abc",
                          symbol="XAUUSD.s", mode="SHADOW", approval=Approval.SHADOW)
    [opp] = current_opportunities(db, now=now)
    assert opp["state"] == "READY_TO_ENTER" and opp["progress"] == 1.0
    assert opp["levels"] is None
    assert opp["research_plan"]["target"] == pytest.approx(2007.5)
    assert "não é recomendação" in opp["research_plan"]["notice"]

    diff = diff_since(db, datetime(2026, 6, 1, 10, 5, tzinfo=timezone.utc), until=now)
    assert [d["to"] for d in diff["advanced"]] == ["WAITING_CONFIRMATION_2", "READY_TO_ENTER"]
    assert diff["new_opportunities"] == []
    assert len(timeline(db, opportunity_id="gold:1")) == 3

    later = now + timedelta(days=3)
    record_transition(db, _transition("2026-06-01T11:00:00+00:00", SetupState.STOP, SetupState.POSITION_OPEN),
                      setup="gold_fakeout_open", setup_version="abc", symbol="XAUUSD.s", mode="SHADOW", approval=Approval.SHADOW)
    assert current_opportunities(db, now=later) == []


def test_approval_comes_only_from_config(tmp_path):
    cfg = tmp_path / "advisors.json"
    cfg.write_text('{"advisors": {"g": {"symbol": "XAUUSD.s", "approved_for_paper": true, "broker_timezone_verified": false}}}',
                   encoding="utf-8")
    assert approval_for("XAUUSD.s", cfg) == Approval.SHADOW  # paper exige relógio verificado
    assert approval_for("UNKNOWN", cfg) == Approval.RESEARCH
    assert approval_for("XAUUSD.s") in (Approval.SHADOW, Approval.RESEARCH)


def test_shadow_adapter_never_touches_order_functions():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "scripts" / "run_shadow.py").read_text(encoding="utf-8")
    for forbidden in ("order_send", "order_check", "positions_get", "TRADE_ACTION"):
        assert forbidden not in source
