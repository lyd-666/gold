import pandas as pd
import yfinance as yf

def download_yf(symbol: str, period="6mo", interval="1d") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False)
    return df

def download_stooq(stooq_symbol: str) -> pd.DataFrame:
    # Stooq 日线 CSV（倒序），示例：XAUUSD
    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    df = pd.read_csv(url)
    # 列：Date,Open,High,Low,Close,Volume
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    df = df.set_index("Date")
    df = df.rename(columns={"Open":"Open","High":"High","Low":"Low","Close":"Close","Volume":"Volume"})
    return df

def download_prices(symbol: str) -> pd.DataFrame:
    # 1) yfinance
    try:
        df = download_yf(symbol)
        if df is not None and not df.empty:
            return df
    except Exception:
        pass

    # 2) fallback：Stooq
    # 黄金现货常用：XAUUSD（Stooq 代码小写）
    df2 = download_stooq("xauusd")
    return df2
