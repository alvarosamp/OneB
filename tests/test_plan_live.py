from datetime import date

import numpy as np
import pandas as pd

from app import plan_live


def _bars(path: list[float], start: str = "2026-10-14 00:00") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(path), freq="5min", tz="UTC")
    p = np.asarray(path, dtype=float)
    return pd.DataFrame({"open": p, "high": p + 0.5, "low": p - 0.5, "close": p}, index=idx)


def test_target_before_stop_and_same_bar_counts_as_stop():
    bars = _bars([100, 101, 103])
    assert plan_live._resolve(bars, 100.0, 2.0, 1, 1.0, True) == "hit"
    wide = pd.DataFrame({"high": [110.0], "low": [90.0]}, index=bars.index[:1])
    assert plan_live._resolve(wide, 100.0, 2.0, 1, 1.0, True) == "stop"
    assert plan_live._resolve(bars.iloc[:1], 100.0, 5.0, 1, 1.0, False) == "open"
    assert plan_live._resolve(bars.iloc[:1], 100.0, 5.0, 1, 1.0, True) == "expired"


def test_build_plans_uses_1330_utc_and_only_past_atr():
    n = 3 * 288
    rng = np.random.default_rng(1)
    m5 = _bars(list(1000 + np.cumsum(rng.normal(0, 1, n))), start="2026-10-13 00:00")
    rows = plan_live.build_plans(m5, spread=0.5, start=date(2026, 10, 14))
    days = {r["date"] for r in rows}
    assert days == {"2026-10-14", "2026-10-15"}  # 13/10 fica antes do início
    first = [r for r in rows if r["date"] == "2026-10-14"]
    ts = pd.Timestamp("2026-10-14 13:30", tz="UTC")
    expected_atr = plan_live.h1_atr(m5)
    assert abs(first[0]["stop_distance"] - 1.5 * expected_atr[expected_atr.index <= ts].iloc[-1]) < 1e-9
    long_, short = sorted(first, key=lambda r: r["direction"])
    assert long_["entry"] == m5.loc[ts, "open"] + 0.5 and short["entry"] == m5.loc[ts, "open"] - 0.5
    # o plano de 15/10 não tem 24 h de dados depois: o que não resolveu fica em andamento, nunca 'expirou'
    assert all(v in ("hit", "stop", "open") for r in rows if r["date"] == "2026-10-15" for v in r["results"].values())


def test_summary_verdict_needs_60_and_wilson():
    rows = [{"direction": "long", "results": {"1": "hit" if i % 2 else "stop", "2": "stop", "3": "stop"}} for i in range(60)]
    s = plan_live.summarize(rows, {("long", 1.0): 0.5, ("long", 2.0): 0.28, ("long", 3.0): 0.16})
    assert s["long"]["status"] == "divergente"  # 0 de 60 no 2R não comporta 28%
    t1 = s["long"]["targets"][0]
    assert t1["hits"] == 30 and t1["consistent"] is True
    assert plan_live.summarize(rows[:10], {})["long"]["status"] == "acumulando"


def test_record_is_idempotent_and_closed_plans_never_change():
    from app.db import SessionLocal, init_db
    from app.models import PlanLiveRecord

    init_db()
    db = SessionLocal()
    asset = "TEST_PLAN"
    # compra gravada: entrada 100, stop 2 (98), alvos 102 / 104 / 106
    open_row = {"date": "2026-10-15", "direction": "long", "entry": 100.0, "stop_distance": 2.0, "results": {"1": "open", "2": "open", "3": "open"}}
    path = [100.0, 102.2] + [97.0] * 300  # bate 1R, depois o stop
    idx = pd.date_range("2026-10-15 13:30", periods=len(path), freq="5min", tz="UTC")
    p = np.asarray(path)
    m5 = pd.DataFrame({"open": p, "high": p + 0.1, "low": p - 0.1, "close": p}, index=idx)
    try:
        db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == asset).delete()
        db.commit()
        assert plan_live.record(db, asset, [open_row], "sha") == {"inserted": 1, "updated": 0}
        assert plan_live.record(db, asset, [open_row], "sha") == {"inserted": 0, "updated": 0}
        # a reconstrução diz entrada 999 (fonte corrigida): ignorada; o resultado sai da entrada e do stop GRAVADOS
        later = {**open_row, "entry": 999.0, "stop_distance": 50.0}
        assert plan_live.record(db, asset, [later], "sha", m5=m5)["updated"] == 1
        rec = db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == asset).one()
        assert rec.closed and rec.results == {"1": "hit", "2": "stop", "3": "stop"} and rec.entry == 100.0
        # encerrado: outras barras não o reescrevem
        flat = m5.assign(high=200.0)
        plan_live.record(db, asset, [later], "sha", m5=flat)
        db.refresh(rec)
        assert rec.results == {"1": "hit", "2": "stop", "3": "stop"}
        saved = plan_live.stored(db, asset, date(2026, 10, 15))
        merged = plan_live.merge(saved, [{**open_row, "results": {"1": "stop", "2": "stop", "3": "stop"}},
                                         {**open_row, "date": "2026-10-16", "results": {"1": "open", "2": "open", "3": "open"}}])
        assert [m["date"] for m in merged] == ["2026-10-15", "2026-10-16"] and merged[0]["results"]["1"] == "hit"
    finally:
        db.query(PlanLiveRecord).filter(PlanLiveRecord.asset == asset).delete()
        db.commit()
        db.close()


def test_scheduler_records_plan_live_every_hour():
    from app.scheduler import build_scheduler, record_plan_live

    job = build_scheduler(None).get_job("record_plan_live")
    assert job is not None and job.func is record_plan_live
    assert "minute='20'" in str(job.trigger) and "hour" not in str(job.trigger).replace("hour='*'", "")


def test_stored_flags_plans_recorded_after_they_closed():
    from datetime import datetime, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db import Base
    from app.models import PlanLiveRecord

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        common = dict(asset="NAS100", direction="long", entry=100.0, stop_distance=2.0, results={"1": "hit", "2": "stop", "3": "stop"},
                      closed=True, rule_sha256="x")
        db.add(PlanLiveRecord(plan_date="2026-10-19", recorded_at=datetime(2026, 10, 19, 14, 20, tzinfo=timezone.utc), **common))  # ao vivo
        db.add(PlanLiveRecord(plan_date="2026-10-20", recorded_at=datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc), **common))   # depois
        db.commit()
        flags = {r["date"]: r["recorded_live"] for r in plan_live.stored(db, "NAS100", date(2026, 10, 15))}
        assert flags == {"2026-10-19": True, "2026-10-20": False}
    finally:
        db.close()
        engine.dispose()
