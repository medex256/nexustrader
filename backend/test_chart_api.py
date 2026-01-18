#!/usr/bin/env python3
"""
Lightweight test for the chart data endpoint.
Run the API server first, then execute this script.
"""

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_chart_endpoint(ticker: str = "AAPL", period: str = "6mo"):
    url = f"{BASE_URL}/api/chart/{ticker}?period={period}"
    print(f"Testing: {url}")

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    assert payload.get("status") == "success", payload
    data = payload.get("data", [])
    assert isinstance(data, list), payload
    assert len(data) > 0, "No chart data returned"

    first = data[0]
    for key in ("time", "open", "high", "low", "close", "volume"):
        assert key in first, f"Missing key: {key}"

    print("✅ Chart endpoint looks good.")


if __name__ == "__main__":
    test_chart_endpoint()
