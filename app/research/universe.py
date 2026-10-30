"""Listas fixas de ativos da pesquisa (evita que novos CSVs em data/history entrem sem querer)."""

STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX", "AMD", "ADBE",
    "CSCO", "PEP", "INTC", "QCOM", "TXN", "INTU", "AMGN", "SBUX", "PYPL", "MU", "AMAT", "BKNG",
    "GILD", "ISRG", "MDLZ", "CMCSA", "TMUS", "HON",
]
# ETFs não sofrem viés de sobrevivência como a lista de ações acima
SECTOR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB"]
OTHER_ETFS = ["TLT", "IEF", "GLD", "EFA", "EEM", "IWM"]
ETF_UNIVERSE = SECTOR_ETFS + OTHER_ETFS
CASH_PROXY = "SHY"
