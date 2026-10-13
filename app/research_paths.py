"""Onde ficam os artefatos pesados de pesquisa.

Capturas do MT5, relatórios grandes e dados de mercado ficam no HD externo (D:)
para não ocupar o disco do PC nem passar pela sincronização do OneDrive.
Sobrescreva com a variável de ambiente ONEB_RESEARCH_ROOT. Se o HD externo não
estiver conectado, volta para a pasta antiga dentro do projeto.
"""
from __future__ import annotations

import os
from pathlib import Path

_PROJECT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = Path(os.getenv("ONEB_RESEARCH_ROOT", r"D:\OneB\research"))

if RESEARCH_ROOT.exists():
    VENDOR_RESEARCH = RESEARCH_ROOT / "vendor_indicator_research"
    EX5_CAPTURES = RESEARCH_ROOT / "ex5_dukascopy"
    LAB_OUTPUT = RESEARCH_ROOT / "lab_v1"
else:  # HD externo ausente: mantém o comportamento antigo
    VENDOR_RESEARCH = _PROJECT / "output" / "vendor_indicator_research"
    EX5_CAPTURES = _PROJECT / "output" / "ex5_dukascopy"
    LAB_OUTPUT = _PROJECT / "output" / "lab_v1"
