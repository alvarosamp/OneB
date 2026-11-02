"""Coleta manchetes agora (uso fora do app, ex: cron). Uso: python scripts/collect_news.py [TICKER ...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research import news_archive

symbols = sys.argv[1:] or news_archive.research_symbols()
print(news_archive.collect(symbols))
