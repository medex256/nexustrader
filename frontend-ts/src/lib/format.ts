import type { AnalysisResult } from "./types";

export function stripRiskPrefix(text: string): string {
  return String(text || "").replace(/^\s*\[[A-Z_]+\]\s*/i, "").trim();
}

export function parseRiskFlow(result: AnalysisResult) {
  const riskReports = result.risk_reports ?? {};
  const finalAction = result.trading_strategy?.action || "";
  const gate = String((riskReports as Record<string, unknown>).risk_gate || "");
  const decision = ((riskReports as Record<string, unknown>).risk_manager_decision ?? {}) as Record<string, unknown>;

  return {
    final: gate.match(/Final:\s*([A-Z]+)/i)?.[1] || (finalAction || "-").toUpperCase(),
    judgment: String(decision.risk_judgment || gate.match(/Judgment:\s*([A-Z]+)/i)?.[1] || "-").toUpperCase(),
    original: gate.match(/Original:\s*([A-Z]+)/i)?.[1] || "-",
  };
}

export function formatShortDate(value: string): string {
  if (!value) {
    return "?";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
    year: "numeric",
  }).format(parsed);
}

export function formatExecutionValue(value: number | null | undefined): string {
  return value == null ? "-" : String(value);
}

export function getActionClass(action: string): string {
  return action.toLowerCase();
}
