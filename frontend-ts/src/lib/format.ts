import type { AnalysisResult } from "./types";

export function stripRiskPrefix(text: string): string {
  return String(text || "")
    .replace(/^\s*\[[A-Z_]+\]\s*/i, "")
    .replace(/^(REDUCE|BLOCK|APPROVE|CLEAR|ADJUST|HOLD|BUY|SELL)\s*[:\-–]\s*/i, "")
    .trim();
}

/**
 * Parse the structured Stage A rationale produced by _stage_a_concise_rationale.
 * Pattern: "FOR: {text} AGAINST: {text} DECISION: ... CONFIDENCE=..."
 * Returns null if the text doesn't match this pattern.
 */
export function parseStageARationale(text: string): { forText: string; against: string } | null {
  const raw = String(text || "");
  const forMatch = raw.match(/\bFOR:\s*([\s\S]*?)(?=\s*\bAGAINST:|\s*\bDECISION:|$)/i);
  const againstMatch = raw.match(/\bAGAINST:\s*([\s\S]*?)(?=\s*\bDECISION:|$)/i);
  if (!forMatch || !againstMatch) return null;
  const forText = forMatch[1].trim();
  const against = againstMatch[1].trim().replace(/\s+CONFIDENCE=\w+\.?\s*$/i, "").trim();
  if (!forText || !against) return null;
  return { forText, against };
}

/** Maps a risk judgment code to a human-readable label. */
export function riskJudgmentLabel(code: string): string {
  switch (code.toUpperCase()) {
    case "CLEAR":    return "Risk cleared";
    case "APPROVE":  return "Approved";
    case "REDUCE":   return "Position reduced";
    case "BLOCK":    return "Trade blocked";
    case "INLINE":   return "No adjustment";
    case "ADJUST":   return "Adjusted";
    default:         return code;
  }
}

/**
 * Parses Stage B+/C/D risk rationale of the form: "[TAG] prose text"
 * Returns { tag, body } or null if no [TAG] prefix is present.
 */
export function parseBPlusRationale(text: string): { tag: string; body: string } | null {
  const m = String(text || "").match(/^\s*\[([A-Z_]+)\]\s*([\s\S]+)$/);
  if (!m) return null;
  return { tag: m[1], body: m[2].trim() };
}

export function parseRiskFlow(result: AnalysisResult) {
  const riskReports = result.risk_reports ?? {};
  const finalAction = result.trading_strategy?.action || "";
  const gate = String((riskReports as Record<string, unknown>).risk_gate || "");
  const decision = ((riskReports as Record<string, unknown>).risk_manager_decision ?? {}) as Record<string, unknown>;
  const structured = (result.investment_plan_structured ?? {}) as Record<string, unknown>;
  const inlineRisk = result.trading_strategy?.position_size_pct != null;
  const original = String(
    gate.match(/Original:\s*([A-Z]+)/i)?.[1] || structured.recommendation || finalAction || "-",
  ).toUpperCase();
  const judgment = String(
    decision.risk_judgment || gate.match(/Judgment:\s*([A-Z]+)/i)?.[1] || (inlineRisk ? "INLINE" : "-"),
  ).toUpperCase();

  return {
    final: gate.match(/Final:\s*([A-Z]+)/i)?.[1] || (finalAction || "-").toUpperCase(),
    judgment,
    original,
  };
}

export function sanitizeDisplayDateInput(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8);

  if (digits.length <= 2) {
    return digits;
  }

  if (digits.length <= 4) {
    return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  }

  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export function displayDateToIso(value: string): string | null {
  const trimmed = value.trim();

  if (!trimmed) {
    return "";
  }

  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return trimmed;
  }

  const displayMatch = trimmed.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!displayMatch) {
    return null;
  }

  const [, day, month, year] = displayMatch;
  const dayNum = Number(day);
  const monthNum = Number(month);
  const yearNum = Number(year);
  const date = new Date(Date.UTC(yearNum, monthNum - 1, dayNum));

  if (
    Number.isNaN(date.getTime()) ||
    date.getUTCFullYear() !== yearNum ||
    date.getUTCMonth() !== monthNum - 1 ||
    date.getUTCDate() !== dayNum
  ) {
    return null;
  }

  return `${year}-${month}-${day}`;
}

export function isoDateToDisplay(value: string): string {
  const isoValue = displayDateToIso(value);

  if (!isoValue) {
    return value;
  }

  const [, year, month, day] = isoValue.match(/^(\d{4})-(\d{2})-(\d{2})$/) || [];
  return year && month && day ? `${day}/${month}/${year}` : value;
}

export function formatShortDate(value: string): string {
  const trimmed = value.trim();

  if (!trimmed) {
    return "";
  }

  const isoValue = displayDateToIso(trimmed);
  const parsed = isoValue ? new Date(`${isoValue}T00:00:00Z`) : new Date(trimmed);

  if (Number.isNaN(parsed.getTime())) {
    return trimmed;
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
