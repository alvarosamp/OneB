"""A ilusão da taxa de acerto: entradas ALEATÓRIAS (direção sorteada) com spread real.

    python scripts/build_win_rate_illusion.py

Conta como "acerto" qualquer toque no TP1 antes do stop (como fazem serviços de sinais que
anunciam 80%+ de acerto) e mostra, lado a lado, o resultado real em R. Stop 1,5 x ATR(14) do H1,
até 24 h, compra no ask e venda no bid, stop primeiro se os dois tocam na mesma barra.
Grava app/research_results/win_rate_illusion.json.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_trade_plan_rates import HORIZON, h1_atr, load  # noqa: E402

TP1S = (0.1, 0.2, 0.3, 0.5, 1.0)
PERIOD = ("2025-01-01", "2026-09-01")


def main() -> None:
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "period": "jan/2025 a ago/2026",
           "stop": "1,5 x ATR(14) do H1", "method": __doc__.strip(), "assets": {}}
    for asset in ("NAS100", "XAUUSD"):
        m5 = load(asset)
        atr = h1_atr(m5)
        idx = m5.index
        e = np.where((idx.minute == 0) & (idx >= pd.Timestamp(PERIOD[0], tz="UTC")) & (idx < pd.Timestamp(PERIOD[1], tz="UTC")))[0]
        e = e[e + HORIZON < len(idx)]
        a = atr.reindex(idx[e], method="ffill").to_numpy()
        ok = np.isfinite(a) & (a > 0)
        e, a = e[ok], a[ok]
        arr = {k: m5[k].to_numpy() for k in m5.columns}
        side = np.random.default_rng(7).choice([1, -1], size=len(e))  # direção sorteada: cara ou coroa
        entry = np.where(side == 1, arr["ask_open"][e], arr["bid_open"][e])
        stop = 1.5 * a
        rows = []
        for tp in TP1S:
            outcome = np.zeros(len(e))
            open_ = np.ones(len(e), dtype=bool)
            for step in range(HORIZON):
                j = e + step
                hit_stop = np.where(side == 1, arr["bid_low"][j] <= entry - stop, arr["ask_high"][j] >= entry + stop)
                hit_tp = np.where(side == 1, arr["bid_high"][j] >= entry + tp * stop, arr["ask_low"][j] <= entry - tp * stop)
                s_now, t_now = open_ & hit_stop, open_ & hit_tp & ~hit_stop
                outcome[s_now], outcome[t_now] = -1, 1
                open_ &= ~(s_now | t_now)
                if not open_.any():
                    break
            r = np.where(outcome == 1, tp, np.where(outcome == -1, -1.0, 0.0))
            rows.append({"tp1_r": tp, "win_rate": round(float(np.mean(outcome == 1)), 4), "mean_r": round(float(r.mean()), 4)})
            print(asset, f"TP1 a {tp}R: acerto {rows[-1]['win_rate'] * 100:.0f}% | resultado {rows[-1]['mean_r']:+.3f}R", flush=True)
        out["assets"][asset] = {"entries": int(len(e)), "rows": rows}
    (ROOT / "app" / "research_results" / "win_rate_illusion.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
