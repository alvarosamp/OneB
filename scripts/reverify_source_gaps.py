"""Reverifica as lacunas da fonte já registradas (source_gaps.json) com a regra nova.

Até 07/10/2026 um dia virava lacuna com UMA prova; sob limite de requisições o
dukascopy-node devolve arquivo vazio com sucesso, e o cache guardava o vazio.
Resultado: dias com dados (ex.: EURUSD 02/04/2025, 288 barras) registrados como vazios.

Para cada lacuna registrada: apaga o cache do dia e exige provas sem cache que
concordem (download_dukascopy_intraday._confirmed_day_rows).
- >= 100 barras ou provas que discordam/falham: a lacuna é removida (não confirmada).
- 0 barras ou pregão curto confirmado: mantida, com a evidência nova.
Se algo for removido, o arquivo normalizado é renomeado para *.pre_reverify
(reprodutibilidade dos relatórios antigos) e o downloader reconstrói o ativo.

    python scripts/reverify_source_gaps.py D:/OneB/market-data/dukascopy-eurusd-2019-2026 [...]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("duka", ROOT / "scripts" / "download_dukascopy_intraday.py")
duka = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(duka)

BY_SOURCE = {v["dukascopy"]: k for k, v in duka.INSTRUMENTS.items()}


def reverify(root: Path, timeframe: str = "m5") -> dict:
    gaps_path = root / duka.SOURCE_GAPS_FILE
    gaps = json.loads(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else {}
    present = {p.name.split("_")[0] for p in (root / "raw").glob(f"*_{timeframe.upper()}_*.csv")}
    for (source, side), days in duka.KNOWN_SOURCE_GAPS.items():  # estáticas também são reverificadas
        if BY_SOURCE[source] in present:
            for d in days:
                gaps.setdefault(f"{source}:{side}", {}).setdefault(d.isoformat(), {"evidence": "lista estática"})
    probe_dir = root / "raw" / "probes"
    probe_dir.mkdir(parents=True, exist_ok=True)
    report = {"kept": {}, "removed": {}}
    for key, days in gaps.items():
        source, side = key.split(":")
        instrument = BY_SOURCE[source]
        for iso in sorted(days):
            day = date.fromisoformat(iso)
            for cached in duka._cache_files(root / "raw" / "cache", instrument, side, day):
                cached.unlink(missing_ok=True)
            rows = duka._confirmed_day_rows(instrument, side, timeframe, day, probe_dir)
            if rows is None or rows >= 100:
                report["removed"].setdefault(key, {})[iso] = rows
                del days[iso]
                verdict = "REMOVIDA"
            else:
                days[iso] = {"evidence": (f"{duka.PROBE_CONFIRMATIONS} pedidos isolados sem cache, espaçados "
                                          f"{duka.PROBE_SPACING_SECONDS}s, devolveram 0 linhas") if rows == 0 else
                             f"sessão curta na fonte: {rows} barras em {duka.PROBE_CONFIRMATIONS} pedidos isolados sem cache",
                             "verified_at": date.today().isoformat()}
                report["kept"].setdefault(key, {})[iso] = rows
                verdict = "mantida"
            print(f"{root.name} {key} {iso}: {rows} barras -> {verdict}", flush=True)
            gaps_path.write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["removed"]:
        for f in (root / "normalized").glob(f"*_{timeframe.upper()}_*.csv.gz"):
            f.rename(f.with_name(f.name + ".pre_reverify"))
    (root / "reverify_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    for root in args.roots:
        r = reverify(root)
        print(root.name, {k: len(v) for k, v in r["removed"].items()}, "removidas;",
              {k: len(v) for k, v in r["kept"].items()}, "mantidas", flush=True)


if __name__ == "__main__":
    main()
