import os
import re
import time
import requests
import feedparser
from datetime import datetime, timezone

UA = "gold-premarket-plan/1.0 (+https://github.com/)"

def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fetch_news_rss(limit: int = 10):
    """
    免费方案：抓取公开 RSS（不保证稳定、但不需要 key）。
    """
    feeds = [
        "https://www.kitco.com/rss/news",                  # Kitco
        "https://www.reutersagency.com/feed/?best-topics=commodities",  # Reuters topics (可能受限)
        "https://www.investing.com/rss/news_11.rss",       # Investing.com commodities (可能受限)
    ]

    items = []
    for url in feeds:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:limit]:
                items.append({
                    "source": d.feed.get("title", url),
                    "title": _clean(e.get("title", "")),
                    "url": e.get("link", ""),
                    "published": _clean(e.get("published", "")) or _clean(e.get("updated", "")),
                    "summary": _clean(re.sub("<[^>]+>", "", e.get("summary", "")))[:240]
                })
        except Exception:
            continue

    # 去重
    seen = set()
    out = []
    for x in items:
        k = (x["title"], x["url"])
        if k in seen or not x["title"]:
            continue
        seen.add(k)
        out.append(x)

    return out[:limit]

def fetch_news_newsapi(query: str = "gold OR XAU OR bullion OR fed OR inflation", limit: int = 10):
    """
    可选方案：使用 NewsAPI（需要环境变量 NEWSAPI_KEY）。
    """
    key = os.getenv("NEWSAPI_KEY", "").strip()
    if not key:
        return []

    endpoint = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(limit, 50),
        "apiKey": key,
    }
    headers = {"User-Agent": UA}
    r = requests.get(endpoint, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    out = []
    for a in data.get("articles", [])[:limit]:
        out.append({
            "source": (a.get("source", {}) or {}).get("name", "NewsAPI"),
            "title": _clean(a.get("title", "")),
            "url": a.get("url", ""),
            "published": _clean(a.get("publishedAt", "")),
            "summary": _clean(a.get("description", ""))[:240],
        })
    return out

def fetch_news(limit: int = 10):
    """
    自动策略：
    - 有 NEWSAPI_KEY：优先 NewsAPI
    - 否则：RSS
    """
    news = fetch_news_newsapi(limit=limit)
    if news:
        return news
    return fetch_news_rss(limit=limit)

def now_iso_local():
    # GitHub Actions 通常是 UTC，展示用 ISO
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
