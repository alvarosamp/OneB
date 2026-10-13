import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from backtest_original_gold_ticks import simulate
from entry_quality import assess_entry, manual_plan


def test_bidask_latency_and_actual_gap_fill():
    signal = dict(name='entry', decision=pd.Timestamp('2026-05-04'), side=1, stop=99, target=102)
    t = signal['decision'].value // 1_000_000
    ticks = pd.DataFrame(dict(time_msc=[t, t+250, t+500], bid=[100, 100.2, 98], ask=[100.3, 100.5, 98.3]))
    result = simulate([signal], ticks, latency_ms=250, slippage=.05, commission=.1)
    trade = result['trades'][0]
    assert trade['entry'] == 100.55
    assert trade['exit'] == 97.95  # Do not fill a jumped stop at 99.
    assert trade['reason'] == 'stop'
    assert abs(trade['net_pnl_per_ounce'] + 2.7) < 1e-9


def test_missing_quote_window_is_censored_not_profit():
    signal = dict(name='entry', decision=pd.Timestamp('2026-05-04'), side=-1, stop=102, target=98)
    t = signal['decision'].value // 1_000_000
    ticks = pd.DataFrame(dict(time_msc=[t, t+120000], bid=[100, 97], ask=[100.3, 97.3]))
    result = simulate([signal], ticks, latency_ms=0)
    assert not result['trades']
    assert result['excluded'][0]['reason'] == 'censored_quote_gap'


def test_entry_gate_uses_ask_and_replays_later_signal_when_first_is_rejected():
    start = pd.Timestamp('2026-05-04')
    ms = start.value // 1_000_000
    signals = [dict(name='poor', decision=start, side=1, stop=99, target=100.8),
               dict(name='later', decision=start + pd.Timedelta(seconds=1),
                    side=-1, stop=102, target=97.5)]
    ticks = pd.DataFrame(dict(time_msc=[ms, ms+1000, ms+2000],
                              bid=[100, 100, 97], ask=[100.4, 100.4, 97.4]))
    result = simulate(signals, ticks, latency_ms=0, slippage=.05,
                      commission=.1, min_net_rr=1)
    assert result['excluded'][0]['reason'] == 'insufficient_remaining_reward_to_risk'
    assert [t['name'] for t in result['trades']] == ['later']
    assert result['trades'][0]['entry_quality']['entry_price'] == 99.95


def test_short_economics_and_unapproved_manual_plan_never_order():
    quality = assess_entry(-1, 100, 100.4, 102, 97, .05, .1, 1)
    assert quality['entry_price'] == 99.95
    assert abs(quality['gross_stop_distance'] - 2.05) < 1e-9
    assert quality['net_reward_to_risk'] > 1
    decision = pd.Timestamp('2026-05-04')
    signal = dict(name='short', decision=decision, side=-1, stop=102, target=97)
    plan = manual_plan(signal, 100, 100.4, decision.value // 1_000_000)
    assert plan['action'] == 'NO_TRADE'
    assert plan['reasons'] == ['setup_not_approved_out_of_sample', 'broker_clock_unverified']
    assert plan['automatic_orders'] is False
    assert plan['confidence_pct'] is None


def test_manual_plan_rejects_stale_quote_even_when_economics_pass():
    decision = pd.Timestamp('2026-05-04')
    signal = dict(name='short', decision=decision, side=-1, stop=102, target=97)
    plan = manual_plan(signal, 100, 100.4,
                       decision.value // 1_000_000 + 6000,
                       approved_for_paper=True, broker_timezone_verified=True)
    assert plan['action'] == 'NO_TRADE'
    assert plan['reasons'] == ['stale_or_pre_signal_quote']
