import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from two_market_advisory import advise, load_advisors


def _signal(symbol, family, side=1):
    return dict(name='observed_signal', symbol=symbol, family=family,
                decision=pd.Timestamp('2026-05-04'), side=side,
                stop=99 if side == 1 else 102,
                target=104 if side == 1 else 96)


def _quote(symbol):
    return dict(symbol=symbol, bid=100, ask=100.4,
                time_msc=pd.Timestamp('2026-05-04').value // 1_000_000)


def test_config_keeps_instruments_and_evidence_separate():
    configs = load_advisors()
    assert configs['gold']['symbol'] == 'XAUUSD.s'
    assert configs['nasdaq']['symbol'] == 'US100.s'
    assert configs['nasdaq']['instrument_type'] != 'NQ_FUTURE'
    assert all(not c['approved_for_paper'] for c in configs.values())


def test_gold_valid_economics_still_no_trade_without_validation():
    policy = load_advisors()['gold']
    card = advise('gold', _signal(policy['symbol'], policy['signal_family']),
                  _quote(policy['symbol']))
    assert card['action'] == 'NO_TRADE'
    assert card['economics']['allow'] is True
    assert card['entry_price'] is None
    assert 'setup_not_approved_out_of_sample' in card['reasons']
    assert card['automatic_orders'] is False
    assert card['latest_time_exit_raw']


def test_nasdaq_does_not_borrow_nq_or_gold_evidence():
    policy = load_advisors()['nasdaq']
    wrong = advise('nasdaq', _signal('NQ', policy['signal_family']),
                   _quote(policy['symbol']))
    assert wrong['action'] == 'NO_TRADE'
    assert 'signal_symbol_mismatch' in wrong['reasons']
    assert 'execution_costs_unknown' in wrong['reasons']
    absent = advise('nasdaq', None, _quote(policy['symbol']))
    assert 'no_certified_current_signal' in absent['reasons']


def test_future_approved_paper_candidate_is_still_human_only():
    policies = load_advisors()
    gold = dict(policies['gold'], approved_for_paper=True,
                broker_timezone_verified=True)
    policies = dict(policies, gold=gold)
    card = advise('gold', _signal(gold['symbol'], gold['signal_family']),
                  _quote(gold['symbol']), advisors=policies)
    assert card['action'] == 'BUY_CANDIDATE'
    assert card['entry_price'] == 100.45
    assert card['stop_price'] == 99
    assert card['target_price'] == 104
    assert card['automatic_orders'] is False
    assert card['confidence_pct'] is None


def test_invalid_quote_fails_closed():
    policy = load_advisors()['gold']
    quote = _quote(policy['symbol'])
    quote['ask'] = 99  # Crossed bid/ask is not executable evidence.
    card = advise('gold', _signal(policy['symbol'], policy['signal_family']), quote)
    assert card['action'] == 'NO_TRADE'
    assert card['entry_price'] is None
    assert card['reasons'] == ['invalid_signal_or_executable_quote']
