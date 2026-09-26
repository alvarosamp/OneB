"""Export broker-native MetaTrader 5 history without placing orders.

The script reads the already authenticated local terminal. It exports OHLCV,
the broker-reported bar spread, contract specifications, and optional bid/ask
OHLC aggregated from quote ticks when that history is retained by the broker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd


TIMEFRAMES = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5}
DISCOVERY_TERMS = ("XAU", "GOLD", "NAS", "USTEC", "US100", "NQ", "GC")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def chunks(start: datetime, end: datetime, days: int):
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=days), end)
        yield cursor, chunk_end
        cursor = chunk_end


def discover_symbols() -> list[dict[str, object]]:
    output = []
    for symbol in mt5.symbols_get() or []:
        if any(term in symbol.name.upper() for term in DISCOVERY_TERMS):
            output.append(
                {
                    "name": symbol.name,
                    "description": symbol.description,
                    "path": symbol.path,
                    "visible": bool(symbol.visible),
                }
            )
    return sorted(output, key=lambda item: str(item["name"]))


def export_rates(symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
    # MT5 may return only previously loaded chart history for copy_rates_range
    # even while current quotes are live. Requesting recent bars first prompts
    # the terminal to synchronize its local history with the broker.
    mt5.copy_rates_from_pos(symbol, TIMEFRAMES[timeframe], 0, 5000)
    parts = []
    for chunk_start, chunk_end in chunks(start, end, 90):
        values = mt5.copy_rates_range(symbol, TIMEFRAMES[timeframe], chunk_start, chunk_end)
        if values is not None and len(values):
            parts.append(pd.DataFrame(values))
    if not parts:
        raise RuntimeError(f"No {timeframe} rates returned for {symbol}: {mt5.last_error()}")
    frame = pd.concat(parts, ignore_index=True).drop_duplicates("time", keep="last").sort_values("time")
    frame["timestamp"] = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
    # MT5 timestamps denote bar opens. The currently forming bar cannot be
    # used for a decision at its own open, so exclude it from research exports.
    minutes = int(timeframe.removeprefix("M"))
    tick = mt5.symbol_info_tick(symbol)
    # Use the broker tick's own time domain to identify the forming bar. A
    # broker may encode server wall time in the timestamp despite MT5's UTC
    # documentation; comparing it to the host clock would drop valid bars.
    clock = pd.to_datetime(tick.time, unit="s", utc=True) if tick else pd.Timestamp.now(tz="UTC")
    completed_before = clock.floor(f"{minutes}min")
    frame = frame.loc[frame["timestamp"] < completed_before]
    return frame[["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]


def export_quote_bars(symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
    minutes = int(timeframe.removeprefix("M"))
    parts = []
    for chunk_start, chunk_end in chunks(start, end, 1):
        values = mt5.copy_ticks_range(symbol, chunk_start, chunk_end, mt5.COPY_TICKS_INFO)
        if values is None or not len(values):
            continue
        ticks = pd.DataFrame(values)
        ticks = ticks[(ticks["bid"] > 0) & (ticks["ask"] > 0)].copy()
        if ticks.empty:
            continue
        ticks.index = pd.to_datetime(ticks["time_msc"], unit="ms", utc=True)
        quote = ticks[["bid", "ask"]].resample(f"{minutes}min", label="left", closed="left").agg(
            {"bid": ["first", "max", "min", "last"], "ask": ["first", "max", "min", "last"]}
        )
        quote.columns = [
            "bid_open", "bid_high", "bid_low", "bid_close",
            "ask_open", "ask_high", "ask_low", "ask_close",
        ]
        parts.append(quote.dropna())
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts).sort_index()[lambda value: ~value.index.duplicated(keep="last")]


def symbol_spec(symbol: str) -> dict[str, object]:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Unknown symbol {symbol}: {mt5.last_error()}")
    fields = (
        "name", "description", "path", "currency_base", "currency_profit", "currency_margin",
        "trade_contract_size", "trade_tick_size", "trade_tick_value", "trade_tick_value_profit",
        "trade_tick_value_loss", "point", "digits", "spread", "spread_float", "volume_min",
        "volume_max", "volume_step", "trade_mode", "trade_calc_mode", "swap_long", "swap_short",
    )
    return {field: getattr(info, field, None) for field in fields} | {
        "commission": None,
        "commission_note": "MT5 symbol_info does not expose the account commission schedule; calibrate from broker statement/deals.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--timeframe", choices=sorted(TIMEFRAMES), default="M1")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--ticks", action="store_true", help="Aggregate retained quote ticks into bid/ask OHLC")
    parser.add_argument("--output", type=Path, default=Path(r"D:\OneB\market-data\mt5"))
    args = parser.parse_args()

    if not mt5.initialize(path=args.terminal, timeout=60_000):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if args.discover:
            print(json.dumps({
                "connected": bool(terminal and terminal.connected),
                "broker": getattr(account, "company", None),
                "server": getattr(account, "server", None),
                "symbols": discover_symbols(),
            }, ensure_ascii=False, indent=2))
            return
        if not account or not terminal or not terminal.connected:
            raise RuntimeError("MT5 is not connected to a broker account")
        if not args.symbol:
            raise ValueError("Use --symbol after running --discover")
        args.output.mkdir(parents=True, exist_ok=True)
        start, end = utc(args.start), utc(args.end)
        for symbol in args.symbol:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Cannot select {symbol}: {mt5.last_error()}")
            rates = export_rates(symbol, args.timeframe, start, end)
            execution_source = "bar_spread_points"
            if args.ticks:
                quotes = export_quote_bars(symbol, args.timeframe, start, end)
                if not quotes.empty:
                    rates = rates.merge(quotes, left_on="timestamp", right_index=True, how="left")
                    execution_source = "observed_quote_ticks_where_available"
            safe_symbol = "".join(char if char.isalnum() or char in "._-" else "_" for char in symbol)
            output = args.output / f"{safe_symbol}_{args.timeframe}_{start.date()}_{end.date()}.csv.gz"
            rates.to_csv(output, index=False, compression="gzip")
            manifest = {
                "symbol": symbol,
                "timeframe": args.timeframe,
                "start_requested": start.isoformat(),
                "end_requested": end.isoformat(),
                "start_returned": rates["timestamp"].min().isoformat(),
                "end_returned": rates["timestamp"].max().isoformat(),
                "rows": len(rates),
                "broker": account.company,
                "server": account.server,
                "execution_source": execution_source,
                "timestamp_basis": "MT5 raw timestamp; verify broker offset before session features",
                "live_tick_minus_host_seconds": (
                    round(mt5.symbol_info_tick(symbol).time - datetime.now(timezone.utc).timestamp(), 1)
                    if mt5.symbol_info_tick(symbol) else None
                ),
                "specification": symbol_spec(symbol),
                "output": str(output.resolve()),
                "sha256": sha256(output),
            }
            output.with_suffix(".manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
