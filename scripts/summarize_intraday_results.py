"""Build cross-market rankings and calendar stability tables from holdout trades."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    rankings: list[pd.DataFrame] = []
    yearly: list[pd.DataFrame] = []
    holdout_paths = [
        path for path in sorted(args.input.glob("*_holdout.csv"))
        if not path.name.endswith("_regime_holdout.csv")
    ]
    for holdout_path in holdout_paths:
        market = holdout_path.name.removesuffix("_holdout.csv")
        trades_path = args.input / f"{market}_trades.csv"
        holdout = pd.read_csv(holdout_path)
        trades = pd.read_csv(trades_path)
        trades["year"] = pd.to_datetime(trades["entry_time"], utc=True).dt.year
        trades["month"] = pd.to_datetime(trades["entry_time"], utc=True).dt.strftime("%Y-%m")
        monthly = trades.groupby(["setup_id", "month"], as_index=False)["net_pnl"].sum()
        stability = monthly.groupby("setup_id")["net_pnl"].agg(
            months="size", positive_months=lambda values: int((values > 0).sum())
        ).reset_index()
        ranked = holdout.merge(stability, on="setup_id", how="left")
        ranked.insert(0, "market", market)
        ranked.insert(1, "holdout_rank", range(1, len(ranked) + 1))
        ranked["positive_month_fraction"] = ranked["positive_months"] / ranked["months"]
        rankings.append(ranked)

        annual = trades.groupby(["setup_id", "family", "year"], as_index=False).agg(
            trades=("net_pnl", "size"), net_pnl=("net_pnl", "sum"), expectancy=("net_pnl", "mean")
        )
        annual.insert(0, "market", market)
        yearly.append(annual)
    pd.concat(rankings, ignore_index=True).to_csv(args.input / "consolidated_holdout_ranking.csv", index=False)
    pd.concat(yearly, ignore_index=True).to_csv(args.input / "yearly_holdout_stability.csv", index=False)


if __name__ == "__main__":
    main()
