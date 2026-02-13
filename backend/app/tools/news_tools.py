# In nexustrader/backend/app/tools/news_tools.py
import os
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from ..utils.cache import cache_data


# ── Frozen News Cache ──────────────────────────────────────────────────
# Pre-fetched Alpha Vantage news stored as JSON files on disk.
# Checked BEFORE any live API call for reproducibility across date ranges.
# Structure: experiments/cache/news/{TICKER}/{YYYY-MM-DD}.json
FROZEN_CACHE_DIR = Path(__file__).resolve().parents[3] / "experiments" / "cache" / "news"


def _load_frozen_news(ticker: str, as_of: str) -> list[dict] | None:
    """
    Check the frozen news cache for pre-fetched articles.
    
    Returns:
        list[dict] of articles if found, None if not cached.
    """
    # Normalize date to YYYY-MM-DD
    date_str = as_of.split("T")[0] if as_of else None
    if not date_str:
        return None
    
    cache_path = FROZEN_CACHE_DIR / ticker.upper() / f"{date_str}.json"
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        articles = data.get("articles", [])
        print(f"[FROZEN CACHE HIT] {ticker}/{date_str} — {len(articles)} articles from Alpha Vantage")
        return articles
    except (json.JSONDecodeError, IOError) as e:
        print(f"[FROZEN CACHE ERROR] {ticker}/{date_str}: {e}")
        return None


def _get_finnhub_api_key() -> str | None:
    return (
        os.getenv("FINNHUB_API_KEY")
    )


def _heuristic_sentiment(title: str, summary: str) -> tuple[float, str]:
    """Lightweight, deterministic sentiment proxy in [-1, 1]."""
    text = f"{title} {summary}".lower()
    positive = [
        "beats",
        "surge",
        "soar",
        "record",
        "upgrade",
        "strong",
        "growth",
        "profit",
        "bull",
        "bullish",
        "rally",
        "win",
        "raises",
        "raises guidance",
        "acquires",
    ]
    negative = [
        "miss",
        "slump",
        "plunge",
        "drop",
        "downgrade",
        "weak",
        "decline",
        "loss",
        "bear",
        "bearish",
        "lawsuit",
        "probe",
        "investigation",
        "cut guidance",
        "cuts guidance",
    ]

    score = 0
    for w in positive:
        if w in text:
            score += 1
    for w in negative:
        if w in text:
            score -= 1

    # Normalize to a small range and clamp.
    score_f = max(-1.0, min(1.0, score / 5.0))
    if score_f > 0.15:
        label = "Bullish"
    elif score_f < -0.15:
        label = "Bearish"
    else:
        label = "Neutral"
    return score_f, label


@cache_data(ttl_seconds=0)  # Persistent cache (never expire) for reproducibility
def search_news_finnhub(ticker: str, limit: int = 50, as_of: str | None = None, lookback_days: int = 7):
    """Fetch company news from Finnhub with a strict (from,to] window ending at as_of.

    Returns a list of articles in the same schema the agents expect.
    Finnhub free tier does not provide sentiment scores, so we add a small
    deterministic heuristic sentiment proxy to preserve downstream behavior.
    """
    print(f"Searching Finnhub news for {ticker}...")

    api_key = _get_finnhub_api_key()
    if not api_key:
        print("Warning: FINNHUB_API_KEY/FINHUB_API_KEY not found in .env")
        return []

    if as_of:
        try:
            end_dt = datetime.fromisoformat(as_of)
        except ValueError:
            end_dt = datetime.fromisoformat(as_of.split("T")[0])
    else:
        end_dt = datetime.now(timezone.utc)

    # Finnhub expects YYYY-MM-DD; clamp to date boundaries.
    end_date = end_dt.date()
    start_date = (end_dt - timedelta(days=lookback_days)).date()
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker,
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "token": api_key,
    }

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                print(f"Unexpected Finnhub response shape: {data}")
                return []

            # Sort newest-first using Finnhub's unix seconds.
            data_sorted = sorted(data, key=lambda x: x.get("datetime", 0), reverse=True)
            articles: list[dict] = []
            for item in data_sorted[: max(0, limit)]:
                headline = item.get("headline", "") or ""
                summary = item.get("summary", "") or ""
                score, label = _heuristic_sentiment(headline, summary)
                published_iso = ""
                try:
                    ts = int(item.get("datetime", 0) or 0)
                    if ts > 0:
                        published_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                except Exception:
                    published_iso = ""

                # Keep the AlphaVantage-like field names to avoid downstream churn.
                article = {
                    "title": headline,
                    "summary": summary,
                    "url": item.get("url", "") or "",
                    "source": item.get("source", "Unknown") or "Unknown",
                    "published": published_iso,
                    "overall_sentiment_score": float(score),
                    "overall_sentiment_label": label,
                    "ticker_sentiment_score": float(score),
                    "ticker_sentiment_label": label,
                    "relevance_score": 0.0,
                }
                articles.append(article)

            print(f"Found {len(articles)} articles for {ticker}")
            return articles

        except Exception as e:
            last_error = e
            time.sleep(0.5 * (attempt + 1))

    print(f"Error fetching Finnhub news: {last_error}")
    return []


def search_news(query: str, limit: int = 5, as_of: str | None = None, lookback_days: int = 7):
    """Primary news entrypoint. Checks frozen cache first, then falls back to Finnhub."""
    # 1. Try frozen cache (pre-fetched Alpha Vantage news)
    if as_of:
        frozen = _load_frozen_news(query, as_of)
        if frozen is not None:
            return frozen[:limit] if limit else frozen
    
    # 2. Fall back to Finnhub (live API)
    return search_news_finnhub(query, limit=limit, as_of=as_of, lookback_days=lookback_days)


# Backward-compat symbol name (some code imports this directly)
search_news_alpha_vantage = search_news_finnhub

