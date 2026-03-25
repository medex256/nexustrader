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
    const horizonDays = result.horizon_days || result.run_config?.horizon_days || 10;
    const action = String(strategy.action || "HOLD").toUpperCase();
    const snap = result.market_snapshot;
    const currentPrice = snap?.current_price ?? null;
    const simulatedDate = result.simulated_date || result.run_config?.simulated_date || "";

    // Derive indicative TP/SL from current price + horizon + action
    let indEntry: string = "—";
    let indTp: string = "—";
    let indSl: string = "—";

    if (currentPrice != null && action !== "HOLD") {
      // Scale target % loosely by horizon
      const tpPct = horizonDays <= 15 ? 0.055 : horizonDays <= 30 ? 0.09 : 0.15;
      const slPct = horizonDays <= 15 ? 0.03 : horizonDays <= 30 ? 0.05 : 0.08;
      const isBuy = action === "BUY";
      indEntry = `$${currentPrice.toFixed(2)}`;
      indTp = isBuy
        ? `$${(currentPrice * (1 + tpPct)).toFixed(2)}`
        : `$${(currentPrice * (1 - tpPct)).toFixed(2)}`;
      indSl = isBuy
        ? `$${(currentPrice * (1 - slPct)).toFixed(2)}`
        : `$${(currentPrice * (1 + slPct)).toFixed(2)}`;
    } else if (currentPrice != null) {
      indEntry = `$${currentPrice.toFixed(2)}`;
    }

    const hasPrice = currentPrice != null;

    return (
      <div className="exec-classification">
        <div className="exec-metrics-row">
          <div className="exec-metric-tile">
            <span className="param-label">Position Size</span>
            <span className="exec-pos-val">
              {strategy.position_size_pct != null ? `${strategy.position_size_pct}%` : "—"}
            </span>
          </div>
          <div className="exec-metric-tile">
            <span className="param-label">Forecast Window</span>
            <span className="exec-metric-val">{horizonDays} days</span>
          </div>
        </div>
        <div className="exec-levels-row">
          <div className={`exec-level-tile${hasPrice ? " exec-level-live" : ""}`}>
            <span className="param-label">Entry</span>
            <span className={`exec-level-val${hasPrice ? " exec-level-val-live" : ""}`}>{indEntry}</span>
          </div>
          <div className={`exec-level-tile exec-level-tp${hasPrice && action !== "HOLD" ? " exec-level-live" : ""}`}>
            <span className="param-label">Take Profit</span>
            <span className={`exec-level-val${hasPrice && action !== "HOLD" ? " exec-level-val-tp" : ""}`}>{indTp}</span>
          </div>
          <div className={`exec-level-tile exec-level-sl${hasPrice && action !== "HOLD" ? " exec-level-live" : ""}`}>
            <span className="param-label">Stop Loss</span>
            <span className={`exec-level-val${hasPrice && action !== "HOLD" ? " exec-level-val-sl" : ""}`}>{indSl}</span>
          </div>
        </div>
        <div className="exec-context-panel">
          <div className="exec-context-row">
            <span className="exec-context-chip">Classification mode</span>
            <span className="exec-context-chip">{horizonDays} trading-day horizon</span>
            {simulatedDate ? <span className="exec-context-chip">As of {formatShortDate(simulatedDate)}</span> : null}
          </div>
          <p className="exec-mode-note">
            {hasPrice && action !== "HOLD"
              ? "Levels are indicative UI anchors derived from the latest available price context, not generated execution orders."
              : "This stage returns a directional classification and size guidance rather than explicit entry, take-profit, and stop-loss orders."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="strategy-grid strategy-grid-detailed">
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
              <div className="risk-strip-step risk-strip-step-origin">
                <span className="risk-strip-label">Original Thesis</span>
                <span className="risk-strip-value">{riskFlow.original}</span>
              </div>
              <div className="risk-strip-arrow">→</div>
              <div className="risk-strip-step risk-strip-step-judgment">
                <span className="risk-strip-label">Risk Judgment</span>
                <span className="risk-strip-value">{riskJudgmentLabel(riskFlow.judgment)}</span>
              </div>
              <div className="risk-strip-arrow">→</div>
              <div className="risk-strip-step risk-strip-step-final">
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
          <div className="strategy-card strategy-card-elevated strategy-card-execution">
            <div className="section-title section-title-accent">Execution Profile</div>
            <ExecutionProfile result={result} />
          </div>
          <PriceChart asOf={simulatedDate || undefined} ticker={ticker} />
        </div>
      </section>
      {showDetails ? <AnalysisDetails result={result} /> : null}
    </>
  );
}