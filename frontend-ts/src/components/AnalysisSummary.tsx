import { AnalysisDetails } from "./AnalysisDetails";
import { PriceChart } from "./PriceChart";
import { formatExecutionValue, formatShortDate, getActionClass, parseRiskFlow, parseStageARationale, parseBPlusRationale, riskJudgmentLabel, stripRiskPrefix } from "../lib/format";
import type { AnalysisResult } from "../lib/types";

function ConfidenceRing({ color, percent }: { color: string; percent: number }) {
  const circumference = 2 * Math.PI * 30;
  const dash = Math.round((percent / 100) * circumference);

  return (
    <div className="confidence-ring">
      <svg height="80" viewBox="0 0 80 80" width="80">
        <circle cx="40" cy="40" fill="none" r="30" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          fill="none"
          r="30"
          stroke={color}
          strokeDasharray={`${dash} ${Math.round(circumference)}`}
          strokeLinecap="round"
          strokeWidth="7"
          transform="rotate(-90 40 40)"
        />
        <text fill={color} fontSize="15" fontWeight="700" textAnchor="middle" x="40" y="46">
          {percent}%
        </text>
      </svg>
      <span className="conf-label">confidence</span>
    </div>
  );
}

function ExecutionProfile({ result }: { result: AnalysisResult }) {
  const strategy = result.trading_strategy ?? {};
  const decisionStyle = result.run_config?.decision_style || "classification";
  const hasPriceLevels = strategy.entry_price != null || strategy.take_profit != null || strategy.stop_loss != null;

  if (!hasPriceLevels && decisionStyle === "classification") {
    return (
      <div className="exec-classification">
        <div>
          <span className="param-label">Position Size</span>
          <span className="exec-pos-val">
            {strategy.position_size_pct != null ? `${strategy.position_size_pct}%` : "—"}
          </span>
        </div>
        <span className="exec-mode-note">Directional evaluation · execution levels not generated</span>
      </div>
    );
  }

  return (
    <div className="strategy-grid">
      <div>
        <span className="param-label">Entry</span>
        <span className="param-val">{formatExecutionValue(strategy.entry_price)}</span>
      </div>
      <div>
        <span className="param-label">Take Profit</span>
        <span className="param-val tp">{formatExecutionValue(strategy.take_profit)}</span>
      </div>
      <div>
        <span className="param-label">Stop Loss</span>
        <span className="param-val sl">{formatExecutionValue(strategy.stop_loss)}</span>
      </div>
      <div>
        <span className="param-label">Position Size</span>
        <span className="param-val">{strategy.position_size_pct != null ? `${strategy.position_size_pct}%` : "-"}</span>
      </div>
    </div>
  );
}

export function AnalysisSummary({ result, showDetails = true, ticker, compact = false }: { result: AnalysisResult; showDetails?: boolean; ticker: string; compact?: boolean }) {
  const strategy = result.trading_strategy ?? {};
  const action = String(strategy.action || "HOLD").toUpperCase();
  const actionClass = getActionClass(action);
  const confidence = typeof strategy.confidence_score === "number" ? Math.round(strategy.confidence_score * 100) : null;
  const simulatedDate = result.simulated_date || result.run_config?.simulated_date || "";
  const stage = result.run_config?.stage || "";
  const horizonDays = result.horizon_days || result.run_config?.horizon_days || 10;
  const rationale = stripRiskPrefix(strategy.rationale || "");
  const parsedRationale = parseStageARationale(strategy.rationale || "");
  const bPlusRationale = !parsedRationale ? parseBPlusRationale(strategy.rationale || "") : null;
  const primaryDrivers: string[] = bPlusRationale && Array.isArray((result.investment_plan_structured as Record<string, unknown>)?.primary_drivers)
    ? ((result.investment_plan_structured as Record<string, unknown>).primary_drivers as string[])
    : [];
  const mainRisk = bPlusRationale
    ? String((result.investment_plan_structured as Record<string, unknown>)?.main_risk || "")
    : "";
  const riskFlow = parseRiskFlow(result);
  const color = action === "BUY" ? "#10b981" : action === "SELL" ? "#ef4444" : "#f59e0b";

  return (
    <>
      <section className={`card summary-shell${compact ? " summary-shell-embedded" : ""}`}>
        {!compact ? (
          <div className="summary-intro">
            <div className="summary-kicker">
              <span className="summary-kicker-dot" /> Final Decision
            </div>
            <h2 className="summary-title">Trade thesis and execution profile</h2>
            <p className="summary-caption">
              Research verdict, risk translation, and price context for this simulated run.
            </p>
          </div>
        ) : null}

        <div className="verdict-hero">
          <div className="verdict-badge-wrap">
            <div className={`verdict-action ${actionClass}`}>{action}</div>
            {confidence != null ? <ConfidenceRing color={color} percent={confidence} /> : null}
          </div>
          <div className="verdict-meta">
            <div className="verdict-meta-row">
              {stage ? <span className="stage-badge">Stage {stage}</span> : null}
              <span className="meta-chip">{ticker}</span>
              <span className="meta-chip">{formatShortDate(simulatedDate) || "live"}</span>
              <span className="meta-chip">{horizonDays} trading days forecast</span>
            </div>
            <div className="risk-strip">
              <div className="risk-strip-step">
                <span className="risk-strip-label">Original Thesis</span>
                <span className="risk-strip-value">{riskFlow.original}</span>
              </div>
              <div className="risk-strip-arrow">→</div>
              <div className="risk-strip-step">
                <span className="risk-strip-label">Risk Judgment</span>
                <span className="risk-strip-value">{riskJudgmentLabel(riskFlow.judgment)}</span>
              </div>
              <div className="risk-strip-arrow">→</div>
              <div className="risk-strip-step">
                <span className="risk-strip-label">Final Action</span>
                <span className="risk-strip-value">
                  {riskFlow.final}
                  {strategy.position_size_pct != null && action !== "HOLD" ? ` (${strategy.position_size_pct}%)` : ""}
                </span>
              </div>
            </div>
            <div className="verdict-rationale">
              {parsedRationale ? (
                <div className="stage-a-rationale">
                  <div className="rationale-row">
                    <span className="rationale-label for-label">For</span>
                    <span className="rationale-text">{parsedRationale.forText}</span>
                  </div>
                  <div className="rationale-row">
                    <span className="rationale-label against-label">Against</span>
                    <span className="rationale-text">{parsedRationale.against}</span>
                  </div>
                </div>
              ) : bPlusRationale ? (
                (primaryDrivers.length > 0 || mainRisk) ? (
                  <div className="summary-verdict-drivers">
                    {primaryDrivers.length > 0 ? (
                      <ul className="summary-drivers-list">
                        {primaryDrivers.map((d, i) => <li key={i}>{d}</li>)}
                      </ul>
                    ) : null}
                    {mainRisk ? (
                      <div className="summary-verdict-risk">
                        <span className="summary-risk-label">Key Risk</span>
                        <span className="summary-risk-text">{mainRisk}</span>
                      </div>
                    ) : null}
                  </div>
                ) : null
              ) : (
                rationale || "No rationale returned."
              )}
            </div>
          </div>
        </div>

        <div className="summary-grid">
          <div className="strategy-card strategy-card-elevated">
            <div className="section-title">Execution Profile</div>
            <ExecutionProfile result={result} />
          </div>
          <PriceChart asOf={simulatedDate || undefined} ticker={ticker} />
        </div>
      </section>
      {showDetails ? <AnalysisDetails result={result} /> : null}
    </>
  );
}