"""Pre-entry economics for manual, non-executing trade advice.

All prices are in the broker symbol's price units. The quote must be observed
at decision time; this module never fetches prices or sends an order.
"""
import math
from datetime import timedelta


def assess_entry(side, bid, ask, stop, target, slippage=0.05, commission=0.1,
                 min_net_rr=1.0):
    """Return executable entry economics and a structural allow/skip decision.

    The assumed exit pays one more adverse slippage plus round-trip commission.
    The threshold is a pre-entry risk gate, not a profitability estimate.
    """
    values = (bid, ask, stop, target, slippage, commission, min_net_rr)
    if side not in (1, -1) or not all(math.isfinite(x) for x in values):
        raise ValueError('Invalid side or non-finite price/cost')
    if bid <= 0 or ask < bid or slippage < 0 or commission < 0 or min_net_rr < 0:
        raise ValueError('Invalid executable quote or assumption')
    entry = (ask if side == 1 else bid) + side * slippage
    gross_risk = side * (entry - stop)
    gross_reward = side * (target - entry)
    net_risk = gross_risk + slippage + commission
    net_reward = gross_reward - slippage - commission
    if gross_risk <= 0 or gross_reward <= 0:
        reason = 'levels_already_crossed'
    elif net_reward <= 0:
        reason = 'target_consumed_by_costs'
    elif net_reward / net_risk < min_net_rr:
        reason = 'insufficient_remaining_reward_to_risk'
    else:
        reason = 'passes_entry_economics_only'
    return dict(allow=reason == 'passes_entry_economics_only', reason=reason,
                entry_price=entry, spread=ask-bid, stop_price=stop,
                target_price=target, gross_stop_distance=gross_risk,
                gross_remaining_reward=gross_reward, net_risk=net_risk,
                net_reward=net_reward,
                net_reward_to_risk=net_reward/net_risk if gross_risk > 0 else None,
                minimum_net_reward_to_risk=min_net_rr)


def manual_plan(signal, bid, ask, quote_time_msc, *, slippage=0.05,
                commission=0.1, min_net_rr=1.0, quote_max_age_ms=5000,
                approved_for_paper=False, broker_timezone_verified=False,
                hold_hours=4):
    """Build a human-only plan from an observed quote; default is NO_TRADE.

    `approved_for_paper` must come from a separate evidence review. Passing an
    entry ratio never promotes an unvalidated indicator to a live recommendation.
    """
    decision_msc = signal['decision'].value // 1_000_000
    age_ms = int(quote_time_msc) - decision_msc
    economics = assess_entry(signal['side'], bid, ask, signal['stop'],
                             signal['target'], slippage, commission, min_net_rr)
    reasons = []
    if age_ms < 0 or age_ms > quote_max_age_ms:
        reasons.append('stale_or_pre_signal_quote')
    if not economics['allow']:
        reasons.append(economics['reason'])
    if not approved_for_paper:
        reasons.append('setup_not_approved_out_of_sample')
    if not broker_timezone_verified:
        reasons.append('broker_clock_unverified')
    quote_time_raw = signal['decision'] + timedelta(milliseconds=age_ms)
    return dict(action='NO_TRADE' if reasons else ('BUY_CANDIDATE' if signal['side'] == 1 else 'SELL_CANDIDATE'),
                advisory_only=True, automatic_orders=False, confidence_pct=None,
                symbol=signal.get('symbol'), signal_name=signal['name'],
                decision_time_raw=str(signal['decision']), quote_time_msc=int(quote_time_msc),
                quote_time_raw=str(quote_time_raw),
                quote_age_ms=age_ms, broker_timezone_verified=broker_timezone_verified,
                entry_condition='Only at a fresh executable quote after human confirmation',
                exit_condition='Stop, target, or time limit; monitor executable opposite quote',
                latest_time_exit_msc=int(quote_time_msc + hold_hours*3600000),
                latest_time_exit_raw=str(quote_time_raw + timedelta(hours=hold_hours)),
                economics=economics, reasons=reasons)
