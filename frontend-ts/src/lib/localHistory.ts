import type { AnalysisResult } from "./types";

const STORAGE_KEY = "nexustrader_history_v1";
const MAX_ENTRIES = 60;

export interface LocalHistoryEntry {
  id: string;
  ticker: string;
  stage: string;
  action: string;
  timestamp: string;
  rationale: string;
  resultJson: string;
}

export function saveRunToHistory(result: AnalysisResult, ticker: string): void {
  const action = String(result.trading_strategy?.action ?? "HOLD").toUpperCase();
  const stage = String(result.run_config?.stage ?? "");
  const entry: LocalHistoryEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    ticker: ticker.toUpperCase(),
    stage,
    action,
    timestamp: new Date().toISOString(),
    rationale: String(result.trading_strategy?.rationale ?? "").slice(0, 220),
    resultJson: JSON.stringify(result),
  };

  const existing = loadHistory();
  const updated = [entry, ...existing].slice(0, MAX_ENTRIES);

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // quota exceeded — drop oldest half and try again
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([entry, ...existing].slice(0, MAX_ENTRIES / 2)));
    } catch {
      // give up silently
    }
  }
}

export function loadHistory(): LocalHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as LocalHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY);
}
