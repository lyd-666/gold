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
def _download_yfinance(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
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

    # Ensure required OHLC columns exist
    for c in ["Open", "High", "Low", "Close"]:
        if c not in df.columns:
            df[c] = np.nan

    if "Volume" not in df.columns:
        df["Volume"] = 0

    df = df[["Open", "High", "Low", "Close", "Volume"]]
    return df

def download_prices(symbol: str) -> tuple[pd.DataFrame, str]:
    """
    Returns (df, source_name)
    """
    # 1) Try yfinance first
    try:
        df = _download_yfinance(symbol)
        if df is not None and not df.empty:
            return df, "yfinance"
    except Exception:
        pass

    # 2) Fallback to Stooq (xauusd)
    try:
        df2 = _download_stooq("xauusd")
        if df2 is not None and not df2.empty:
            return df2, "stooq(xauusd)"
    except Exception:
        pass

    return pd.DataFrame(), "none"

# -----------------------------
# Analysis logic
# -----------------------------
def traffic_light_logic(
    df: pd.DataFrame,
    news_items: list[dict],
) -> tuple[str, str, list[str], list[dict], int]:
    last = df.iloc[-1]
    close = float(last["Close"])

    ma20 = float(last.get("MA20", np.nan)) if not pd.isna(last.get("MA20", np.nan)) else close
    ma50 = float(last.get("MA50", np.nan)) if not pd.isna(last.get("MA50", np.nan)) else close
    rsi14 = float(last.get("RSI14", np.nan)) if not pd.isna(last.get("RSI14", np.nan)) else 50.0
    macd_hist = float(last.get("MACDHist", np.nan)) if not pd.isna(last.get("MACDHist", np.nan)) else 0.0
    atr14 = float(last.get("ATR14", np.nan)) if not pd.isna(last.get("ATR14", np.nan)) else 0.0

    trend_up = close > ma20 > ma50
    trend_down = close < ma20 < ma50
    momentum_up = (rsi14 >= 55) and (macd_hist > 0)
    momentum_down = (rsi14 <= 45) and (macd_hist < 0)

    neg_kw = ["hawkish", "rate hike", "higher yields", "strong dollar", "usd rises", "risk-on"]
    pos_kw = ["dovish", "rate cut", "recession", "geopolitical", "safe haven", "inflation", "war", "conflict"]

    score = 0
    for n in news_items:
        t = (n.get("title") or "").lower()
        for k in pos_kw:
            if k in t:
                score += 1
        for k in neg_kw:
            if k in t:
                score -= 1

    if trend_up and momentum_up and score >= 0:
        tl = "GREEN"
        summary = "趋势与动量偏多，计划以回踩承接为主，严格控制波动风险。"
    elif trend_down and momentum_down and score <= 0:
        tl = "RED"
        summary = "趋势与动量偏空，计划以反弹承压做空或观望为主，避免追单。"
    else:
        tl = "NEUTRAL"
        summary = "多空信号分歧，优先等待关键位确认，控制仓位与回撤。"

    bullets = [
        f"收盘价 {close:.2f}；MA20 {ma20:.2f}；MA50 {ma50:.2f}。",
        f"RSI14 {rsi14:.1f}；MACD Hist {macd_hist:.3f}（动量参考）。",
        f"ATR14 {atr14:.2f}（波动参考，用于止损距离与仓位）。",
        f"新闻情绪粗分 score={score}（仅用于辅助，不作为单独交易依据）。",
    ]

    # Avoid crash when rows < 50
    atr_mean_50 = float(df["ATR14"].rolling(50).mean().iloc[-1]) if ("ATR14" in df.columns and len(df) >= 50) else atr14

    drivers = [
        {
            "driver": "Trend (MA20/MA50)",
            "signal": "Bullish" if trend_up else ("Bearish" if trend_down else "Mixed"),
            "note": "价格相对均线位置与多空排列。",
        },
        {
            "driver": "Momentum (RSI/MACD)",
            "signal": "Bullish" if momentum_up else ("Bearish" if momentum_down else "Mixed"),
            "note": "RSI 与 MACD 柱体方向。",
        },
        {
            "driver": "Volatility (ATR)",
            "signal": "High" if atr14 > atr_mean_50 else "Normal",
            "note": "ATR 越高，越需要降杠杆与扩大止损。",
        },
        {
            "driver": "Macro/News (headline heuristic)",
            "signal": "Supportive" if score > 0 else ("Headwind" if score < 0 else "Neutral"),
            "note": "基于关键词的粗略文本规则。",
        },
    ]

    return tl, summary, bullets, drivers, score

def build_plan_text(df: pd.DataFrame) -> tuple[str, str, list[str], list[str], list[dict]]:
    last = df.iloc[-1]
    close = float(last["Close"])
    atr = float(last.get("ATR14", 0.0)) if not pd.isna(last.get("ATR14", np.nan)) else 0.0

    r1 = close + 0.8 * atr
    s1 = close - 0.8 * atr

    base_case = (
        f"关键区间：S1≈{s1:.2f} / R1≈{r1:.2f}（基于 ATR14）。\n"
        "若价格回踩不破关键支撑并出现回升结构，可考虑分批入场；若突破关键阻力并站稳，可考虑顺势跟随。\n"
        "入场前确认：1）结构；2）波动配合；3）避免在新闻高波动时段盲目追单。"
    )

    alt_case = (
        "若出现与预期相反的快速单边（例如宏观新闻引发美元与利率大幅变动），优先停止加仓。\n"
        "等待反向信号完成后再重新评估，必要时以更小仓位或期权对冲参与。"
    )

    watchlist = [
        "美元指数 DXY（强美元通常压制黄金）。",
        "美债收益率（尤其是实际利率方向）。",
        "美联储相关讲话与通胀数据发布窗口。",
        "地缘政治与避险情绪突发事件。",
    ]

    rules = [
        "单笔风险上限：账户净值的 0.25%–1%，依据 ATR 调整仓位。",
        "止损距离建议：≥ 1.0×ATR，并在结构失效时执行。",
        "不在重大数据公布前后 5–15 分钟内追价开仓（视波动而定）。",
        "达到 1R 后可考虑移动止损或分批止盈，保持执行一致性。",
    ]

    risks = [
        {"risk": "宏观数据/央行讲话引发跳空或剧烈波动", "hedge": "降低仓位；使用期权；避免事件窗口追单。"},
        {"risk": "强美元与收益率上行压制黄金", "hedge": "观察 DXY/美债；信号转弱则收缩多头敞口。"},
        {"risk": "假突破导致来回扫损", "hedge": "等待收盘确认；用 ATR 校准止损；减少频繁交易。"},
    ]

    return base_case, alt_case, watchlist, rules, risks

# -----------------------------
# Main
# -----------------------------
def main():
    symbol = DEFAULT_SYMBOL
    os.makedirs(OUT_DIR, exist_ok=True)

    # Download prices with fallback
    df, price_source = download_prices(symbol)
    if df.empty:
        raise RuntimeError(f"No data returned for symbol={symbol} (all sources failed)")

    # Keep only required columns and clean
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    if df.empty:
        raise RuntimeError("Price dataframe became empty after cleaning")

    # Enrich indicators
    df = enrich_indicators(df)

    # News
    news_items = fetch_news(limit=NEWS_LIMIT)

    # Analysis
    tl, summary, bullets, drivers, news_score = traffic_light_logic(df, news_items)
    base_case, alt_case, watchlist, rules, risks = build_plan_text(df)

    # Last 30 rows table
    last30_df = df.tail(30).copy()
    last30_df = last30_df.reset_index().rename(columns={"index": "Date"})

    last30_rows = []
    for _, r in last30_df.iterrows():
        dt = r["Date"]
        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)
        last30_rows.append(
            {
                "Date": date_str,
                "Open": _fmt(r.get("Open")),
                "High": _fmt(r.get("High")),
                "Low": _fmt(r.get("Low")),
                "Close": _fmt(r.get("Close")),
                "Volume": _fmt(r.get("Volume")),
            }
        )

    updated = now_iso_local()
    today = datetime.now(timezone.utc).astimezone().date().isoformat()

    payload = {
        "symbol": symbol,
        "date": today,
        "updated": updated,
        "traffic_light": tl,
        "summary": summary,
        "bullets": bullets,
        "base_case": base_case,
        "alt_case": alt_case,
        "watchlist": watchlist,
        "rules": rules,
        "last30": last30_rows,
        "drivers": drivers,
        "risks": risks,
        "news": news_items,
        "debug": {
            "price_source": price_source,
            "news_score": news_score,
            "rows": int(len(df)),
        },
    }

    # Write JSON
    json_path = os.path.join(OUT_DIR, "gold_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Render HTML
    env = Environment(
        loader=FileSystemLoader(os.path.join("src", "templates")),
        autoescape=True,
    )
    tpl = env.get_template("report.html")
    html = tpl.render(**payload)

    html_path = os.path.join(OUT_DIR, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK: wrote {html_path} and {json_path} (price_source={price_source})")

if __name__ == "__main__":
    main()
