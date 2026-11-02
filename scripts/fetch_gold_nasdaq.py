"""Baixa os dados da pesquisa ouro/Nasdaq: diário (yfinance), macro (FRED, sem chave), H1 do ouro (MT5) e H1 de 730 dias (yfinance).

Saída em data/research/gold_nasdaq/ (fora do git). Rode com o terminal MT5 aberto para incluir o H1 longo do ouro.
"""
import io
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

OUT = Path(__file__).resolve().parents[1] / "data" / "research" / "gold_nasdaq"
OUT.mkdir(parents=True, exist_ok=True)

DAILY = {
    "gold": "GC=F", "nq": "NQ=F", "ndx": "^NDX", "spx": "^GSPC", "silver": "SI=F", "copper": "HG=F",
    "oil": "CL=F", "dxy": "DX-Y.NYB", "vix": "^VIX", "vix3m": "^VIX3M", "tnx": "^TNX", "irx": "^IRX",
    "hyg": "HYG", "ief": "IEF", "gld": "GLD", "qqq": "QQQ", "usdjpy": "JPY=X", "btc": "BTC-USD",
}
FRED = ["DFII10", "T10YIE", "DTWEXBGS", "T10Y2Y", "NFCI", "BAMLH0A0HYM2"]
INTRADAY = {"gold_1h": "GC=F", "nq_1h": "NQ=F", "qqq_1h": "QQQ"}


def fetch_daily():
    raw = yf.download(list(DAILY.values()), start="2000-01-01", progress=False, auto_adjust=True, group_by="ticker")
    for name, tk in DAILY.items():
        df = raw[tk].dropna(how="all")
        df.columns = [c.lower() for c in df.columns]
        df.index.name = "date"
        df.to_csv(OUT / f"d1_{name}.csv")
        print(f"d1 {name:8s} {len(df):6d} {df.index[0].date()} a {df.index[-1].date()}")


def fetch_fred():
    frames = []
    for sid in FRED:
        txt = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=60).text
        s = pd.read_csv(io.StringIO(txt), index_col=0, parse_dates=True, na_values=".").iloc[:, 0].rename(sid)
        frames.append(s)
    df = pd.concat(frames, axis=1)
    df.index.name = "date"
    df.to_csv(OUT / "fred.csv")
    print(f"fred {list(df.columns)} até {df.index[-1].date()}")


def fetch_intraday_yf():
    for name, tk in INTRADAY.items():
        df = yf.download(tk, period="730d", interval="1h", progress=False, auto_adjust=True)
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
        df.index = df.index.tz_convert("UTC").tz_localize(None)
        df.index.name = "time"
        df.to_csv(OUT / f"{name}_yf.csv")
        print(f"{name} yf {len(df)} {df.index[0]} a {df.index[-1]}")


def fetch_mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 não instalado; pulando H1 do MT5")
        return
    if not mt5.initialize():
        print("MT5 não inicializou:", mt5.last_error())
        return
    try:
        # XAUUSD.dk = símbolo custom com histórico longo; .s = feed da corretora (curto, serve para conferir).
        for sym, tf_name, tf in [("XAUUSD.dk", "h1", mt5.TIMEFRAME_H1), ("XAUUSD.s", "h1", mt5.TIMEFRAME_H1),
                                 ("US100.s", "h1", mt5.TIMEFRAME_H1)]:
            mt5.symbol_select(sym, True)
            r = mt5.copy_rates_from_pos(sym, tf, 0, 99000)
            if r is None or len(r) == 0:
                print(f"mt5 {sym} sem dados: {mt5.last_error()}")
                continue
            df = pd.DataFrame(r)
            df["time"] = pd.to_datetime(df["time"], unit="s")  # horário do servidor da corretora
            df = df.set_index("time").rename(columns={"tick_volume": "volume"})[["open", "high", "low", "close", "volume", "spread"]]
            df.to_csv(OUT / f"mt5_{sym.replace('.', '_')}_{tf_name}.csv")
            print(f"mt5 {sym} {len(df)} {df.index[0]} a {df.index[-1]}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    steps = sys.argv[1:] or ["daily", "fred", "intraday", "mt5"]
    if "daily" in steps:
        fetch_daily()
    if "fred" in steps:
        fetch_fred()
    if "intraday" in steps:
        fetch_intraday_yf()
    if "mt5" in steps:
        fetch_mt5()
    print("ok", datetime.now())
