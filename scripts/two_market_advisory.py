"""Separate, fail-closed manual advisors for broker gold and Nasdaq CFD.

Consumes a causally captured indicator signal and current bid/ask quote. Does
not read account credentials, connect to MT5, or expose order functions.
"""
import json
from pathlib import Path

from entry_quality import manual_plan


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'configs' / 'manual_advisors_v1.json'


def load_advisors(path=DEFAULT_CONFIG):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('version') != 1 or set(payload.get('advisors', {})) != {'gold', 'nasdaq'}:
        raise ValueError('Unexpected market advisor configuration')
    symbols = [row['symbol'] for row in payload['advisors'].values()]
    if len(set(symbols)) != 2:
        raise ValueError('Gold and Nasdaq must have distinct broker symbols')
    return payload['advisors']


def advise(market, signal, quote, *, advisors=None):
    """Return a human-only candidate or an explicit NO_TRADE with reasons.

    Empty/mismatched/stale/unapproved data never receive an actionable plan.
    Even an approved candidate is not a broker order.
    """
    advisors = load_advisors() if advisors is None else advisors
    if market not in advisors:
        raise ValueError('Unknown market')
    policy = advisors[market]
    base = dict(market=market, symbol=policy['symbol'],
                signal_family=policy['signal_family'],
                instrument_type=policy['instrument_type'],
                research_status=policy['research_status'],
                advisory_only=True, automatic_orders=False,
                confidence_pct=None)
    reasons = []
    if signal is None:
        reasons.append('no_certified_current_signal')
    elif signal.get('symbol') != policy['symbol']:
        reasons.append('signal_symbol_mismatch')
    elif signal.get('family') != policy['signal_family']:
        reasons.append('signal_family_mismatch')
    if quote is None:
        reasons.append('no_current_bid_ask_quote')
    elif quote.get('symbol') != policy['symbol']:
        reasons.append('quote_symbol_mismatch')
    if policy['slippage_price_per_side'] is None or policy['commission_roundtrip_per_unit'] is None:
        reasons.append('execution_costs_unknown')
    if reasons:
        return dict(base, action='NO_TRADE', entry_price=None, stop_price=None,
                    target_price=None, reasons=reasons)
    try:
        plan = manual_plan(signal, quote['bid'], quote['ask'], quote['time_msc'],
                           slippage=policy['slippage_price_per_side'],
                           commission=policy['commission_roundtrip_per_unit'],
                           min_net_rr=policy['min_net_reward_to_risk'],
                           quote_max_age_ms=policy['quote_max_age_ms'],
                           approved_for_paper=policy['approved_for_paper'],
                           broker_timezone_verified=policy['broker_timezone_verified'],
                           hold_hours=policy['max_hold_hours'])
    except (KeyError, TypeError, ValueError, OverflowError):
        return dict(base, action='NO_TRADE', entry_price=None, stop_price=None,
                    target_price=None, reasons=['invalid_signal_or_executable_quote'])
    economics = plan['economics']
    actionable = plan['action'] in {'BUY_CANDIDATE', 'SELL_CANDIDATE'}
    return dict(base, **plan,
                entry_price=economics['entry_price'] if actionable else None,
                stop_price=economics['stop_price'] if actionable else None,
                target_price=economics['target_price'] if actionable else None)
