export const API_BASE_URL = "http://127.0.0.1:8000";

export function buildAnalyzeStreamUrl(params: URLSearchParams): string {
  return `${API_BASE_URL}/analyze/stream?${params.toString()}`;
}

export function buildChartUrl(ticker: string, asOf?: string): string {
  const params = new URLSearchParams({ period: "6mo" });

  if (asOf) {
    params.set("as_of", asOf);
  }

  return `${API_BASE_URL}/api/chart/${ticker}?${params.toString()}`;
}

export function buildHistoryUrl(): string {
  return `${API_BASE_URL}/memory/all`;
}
