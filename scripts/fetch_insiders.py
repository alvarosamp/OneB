"""Baixa os Form 4 do SEC (compras/vendas em mercado aberto). Uso: SEC_USER_AGENT="Nome contato@email" python scripts/fetch_insiders.py"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.research import insiders

ua = os.environ.get("SEC_USER_AGENT") or settings.sec_user_agent
if not ua or "@" not in ua:
    sys.exit("Defina SEC_USER_AGENT (ou SEC_USER_AGENT no .env) com seu nome e e-mail: o SEC exige contato real.")

for q in insiders.quarters():
    try:
        n = insiders.fetch_quarter(q, ua)
        print(q, "-" if n is None else f"{n} transações", flush=True)
    except Exception as e:
        print(q, "ERRO", type(e).__name__, str(e)[:100], flush=True)
