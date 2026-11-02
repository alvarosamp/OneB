"""Transações de insiders (SEC Form 4) a partir dos 'Insider Transactions Data Sets' trimestrais do SEC.

Guarda só compras (P) e vendas (S) em mercado aberto de ações ordinárias. A data que importa para
negociar é a de DIVULGAÇÃO (filing_date), não a da operação: só depois dela o mercado sabe.
O SEC exige um contato real no User-Agent (variável SEC_USER_AGENT / settings.sec_user_agent).
"""
from __future__ import annotations

import io
import logging
import time
import zipfile
from pathlib import Path

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

DIR = Path("data/insiders")
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
COLUMNS = ["filing_date", "symbol", "issuer", "owner", "relationship", "title", "trans_date", "code", "shares", "price"]


def quarters(start: str = "2014q4", end: str = "2026q3") -> list[str]:
    y, q = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    out = []
    while (y, q) <= (ey, eq):
        out.append(f"{y}q{q}")
        q += 1
        if q == 5:
            y, q = y + 1, 1
    return out


def parse_zip(content: bytes) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(content))
    sub = pd.read_csv(z.open("SUBMISSION.tsv"), sep="\t", dtype=str, usecols=[
        "ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERNAME", "ISSUERTRADINGSYMBOL"])
    sub = sub[sub["DOCUMENT_TYPE"] == "4"]
    own = pd.read_csv(z.open("REPORTINGOWNER.tsv"), sep="\t", dtype=str, usecols=[
        "ACCESSION_NUMBER", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"]).drop_duplicates("ACCESSION_NUMBER")
    tr = pd.read_csv(z.open("NONDERIV_TRANS.tsv"), sep="\t", dtype=str, usecols=[
        "ACCESSION_NUMBER", "SECURITY_TITLE", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE"])
    tr = tr[tr["TRANS_CODE"].isin(["P", "S"]) & tr["SECURITY_TITLE"].fillna("").str.contains("common", case=False)]
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    out = pd.DataFrame({
        "filing_date": pd.to_datetime(df["FILING_DATE"], format="%d-%b-%Y", errors="coerce"),
        "symbol": df["ISSUERTRADINGSYMBOL"].str.upper().str.strip(),
        "issuer": df["ISSUERNAME"],
        "owner": df["RPTOWNERNAME"],
        "relationship": df["RPTOWNER_RELATIONSHIP"],
        "title": df["RPTOWNER_TITLE"],
        "trans_date": pd.to_datetime(df["TRANS_DATE"], format="%d-%b-%Y", errors="coerce"),
        "code": df["TRANS_CODE"],
        "shares": pd.to_numeric(df["TRANS_SHARES"], errors="coerce"),
        "price": pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce"),
    })
    return out.dropna(subset=["filing_date", "symbol", "shares"])[COLUMNS]


def fetch_quarter(q: str, user_agent: str, directory: Path = DIR, force: bool = False) -> int | None:
    path = directory / f"{q}.csv"
    if path.exists() and not force:
        return len(pd.read_csv(path))
    r = httpx.get(URL.format(q=q), headers={"User-Agent": user_agent}, timeout=300, follow_redirects=True)
    if r.status_code == 404:
        logger.info("Trimestre %s ainda não publicado", q)
        return None
    r.raise_for_status()
    df = parse_zip(r.content)
    directory.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    time.sleep(0.5)  # educado com o SEC (limite de 10 req/s)
    return len(df)


def load_all(directory: Path = DIR) -> pd.DataFrame:
    files = sorted(directory.glob("*q?.csv"))
    if not files:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat([pd.read_csv(f, parse_dates=["filing_date", "trans_date"]) for f in files], ignore_index=True)
    return df.drop_duplicates()
