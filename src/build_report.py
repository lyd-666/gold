# -*- coding: utf-8 -*-
import io
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from jinja2 import Environment, FileSystemLoader

from indicators import enrich_indicators
from news import fetch_news, now_iso_local

DEFAULT_SYMBOL = os.getenv("SYMBOL", "GC=F")
OUT_DIR = os.getenv("OUT_DIR", "docs")
NEWS_LIMIT = int(os.getenv("NEWS_LIMIT", "10"))

# -----------------------------
# Helpers
# -----------------------------
def _fmt(x):
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    if isinstance(x, (float, np.floating)):
        return f"{float(x):.2f}"
    return str(x)

# -----------------------------
# Price sources
# -----------------------------
def _download_yfinance(symbol: str, period="6mo", interval="1d") -> pd.DataFrame:
    """
    Primary source: yfinance.
    Note: may fail in GitHub Actions due to Yahoo anti-bot / rate-limit behavior.
    """
    return yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

def _download_stooq(stooq_symbol: str = "xauusd") -> pd.DataFrame:
    """
    Fallback source: Stooq daily CSV.
    Gold spot commonly: xauusd
    Returns DataFrame indexed by Date with columns: Open, High, Low, Close, Volume
    """
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    headers = {"User-Agent": "gold-premarket-plan/1.0"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()

    df = pd.read_csv(io.StringIO(r.text))
    if df.empty:
        return df

    if "Date" not in df.columns:
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date").set_index("Date")

    for c in ["Open", "High", "Low", "Close"]:
        if c not in df.columns
