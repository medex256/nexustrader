import { marked } from "marked";
import type { AnalysisResult } from "../lib/types";

function MarkdownBlock({ content }: { content: string }) {
  return <div className="report prose" dangerouslySetInnerHTML={{ __html: marked.parse(content) as string }} />;
}

function ResearchManagerPanel({ result }: { result: AnalysisResult }) {
  const structured = result.investment_plan_structured;
  const investmentPlan = result.investment_plan;

  if (structured && typeof structured === "object") {
    const recommendation = String((structured as Record<string, unknown>).recommendation || "");
    const priorConfirmed = (structured as Record<string, unknown>).prior_confirmed;
    const rationale = String(
      (structured as Record<string, unknown>).base_view_rationale ||
        (structured as Record<string, unknown>).override_reason ||
        (structured as Record<string, unknown>).rationale ||
        "",
    );
    const holdGate = String((structured as Record<string, unknown>).hold_gate_assessment || "");
    const primaryDrivers = Array.isArray((structured as Record<string, unknown>).primary_drivers)
      ? ((structured as Record<string, unknown>).primary_drivers as string[])
      : [];

    return (
      <div className="panel-section" style={{ marginTop: "1rem" }}>
        <details className="accordion">
          <summary className="accordion-header">
            <span>🎯</span>
            <span>Research Manager Decision</span>
            <span className="accordion-arrow">▾</span>
          </summary>
          <div className="accordion-body">
            {recommendation ? (
              <div style={{ marginBottom: "1rem" }}>
                <span className={`badge ${recommendation.toLowerCase()}`}>Recommendation: {recommendation}</span>
              </div>
            ) : null}
            {typeof priorConfirmed === "boolean" ? (
              <div style={{ marginBottom: "0.5rem" }}>
                <strong>Prior View Confirmed:</strong> {priorConfirmed ? "Yes" : "No"}
              </div>
            ) : null}
            {rationale ? <MarkdownBlock content={rationale} /> : null}
            {holdGate ? (
              <div className="notice" style={{ marginTop: "0.75rem" }}>
                <strong>Hold Gate:</strong> {holdGate}
              </div>
            ) : null}
            {primaryDrivers.length > 0 ? (
              <div style={{ marginTop: "0.75rem" }}>
                <strong>Primary Drivers:</strong>
                <ul style={{ marginTop: "0.35rem", paddingLeft: "1.2rem" }}>
                  {primaryDrivers.map((driver) => (
                    <li key={driver}>{driver}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </details>
      </div>
    );
  }

  if (investmentPlan) {
    return (
      <div className="panel-section" style={{ marginTop: "1rem" }}>
        <details className="accordion">
          <summary className="accordion-header">
            <span>🎯</span>
            <span>Research Manager Recommendation</span>
            <span className="accordion-arrow">▾</span>
          </summary>
          <div className="accordion-body">
            <MarkdownBlock content={investmentPlan} />
          </div>
        </details>
      </div>
    );
  }

  return null;
}

function RiskPanel({ result }: { result: AnalysisResult }) {
  const riskReports = (result.risk_reports ?? {}) as Record<string, unknown>;
  const decision = ((riskReports.risk_manager_decision ?? {}) as Record<string, unknown>);
  const judgment = String(decision.risk_judgment || decision.judgment || "").toUpperCase();
  const gate = String(riskReports.risk_gate || "");
  const rationale = String(decision.rationale || decision.reasoning || "");
  const positionSize = decision.position_size_pct;
  const stopLoss = decision.stop_loss || decision.stop_loss_pct;
  const takeProfit = decision.take_profit || decision.take_profit_pct;
  const hasRisk = judgment || gate || rationale || positionSize != null || stopLoss || takeProfit;

  if (!hasRisk) {
    return (
      <div className="panel-section dim-panel" style={{ marginTop: "1rem" }}>
        <div className="panel-header dim">
          <span>🛡️</span>
          <span>Risk Gate - Off or unavailable</span>
        </div>
      </div>
    );
  }

  const badgeClass = judgment === "CLEAR" || judgment === "APPROVE" ? "buy" : judgment === "BLOCK" ? "sell" : "hold";

  return (
    <div className="panel-section" style={{ marginTop: "1rem" }}>
      <details className="accordion" open>
        <summary className="accordion-header">
          <span>🛡️</span>
          <span>Risk Gate</span>
          {judgment ? <span className={`badge ${badgeClass}`} style={{ marginLeft: "auto" }}>{judgment}</span> : null}
          <span className="accordion-arrow">▾</span>
        </summary>
        <div className="accordion-body">
          {gate ? <div className="notice" style={{ marginBottom: "0.75rem" }}>{gate}</div> : null}
          {positionSize != null || stopLoss || takeProfit ? (
            <div className="strategy-grid" style={{ marginBottom: "0.75rem" }}>
              {positionSize != null ? (
                <div>
                  <span className="param-label">Adjusted Position</span>
                  <span className="param-val">{String(positionSize)}%</span>
                </div>
              ) : null}
              {stopLoss ? (
                <div>
                  <span className="param-label">Stop Loss</span>
                  <span className="param-val sl">{String(stopLoss)}</span>
                </div>
              ) : null}
              {takeProfit ? (
                <div>
                  <span className="param-label">Take Profit</span>
                  <span className="param-val tp">{String(takeProfit)}</span>
                </div>
              ) : null}
            </div>
          ) : null}
          {rationale ? <MarkdownBlock content={rationale} /> : null}
        </div>
      </details>
    </div>
  );
}

function MemoryPanel({ result }: { result: AnalysisResult }) {
  const memorySummary = result.memory_summary;
  const memoryOn = memorySummary !== undefined && memorySummary !== null;
  const bullHits = memorySummary?.bull_hits || 0;
  const bearHits = memorySummary?.bear_hits || 0;
  const totalHits = bullHits + bearHits;

  if (!memoryOn) {
    return (
      <div className="panel-section dim-panel" style={{ marginTop: "1rem" }}>
        <div className="panel-header dim">
          <span>🧠</span>
          <span>Episodic Memory - Off</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`panel-section${totalHits === 0 ? " dim-panel" : ""}`} style={{ marginTop: "1rem" }}>
      <div className={`panel-header${totalHits === 0 ? " dim" : ""}`}>
        <span>🧠</span>
        <span>
          Episodic Memory - {totalHits > 0 ? `${totalHits} past lesson${totalHits === 1 ? "" : "s"} retrieved` : "0 relevant lessons found"}
        </span>
      </div>
      {totalHits > 0 ? (
        <div className="memory-grid">
          <div className="memory-pill bull-mem">Bull hits <strong>{bullHits}</strong></div>
          <div className="memory-pill bear-mem">Bear hits <strong>{bearHits}</strong></div>
        </div>
      ) : null}
    </div>
  );
}

function AnalystReportsPanel({ result }: { result: AnalysisResult }) {
  const reports = result.reports ?? {};
  const signals = (result.signals ?? {}) as Record<string, Record<string, unknown>>;
  const defs = [
    { key: "fundamental_analyst", label: "Fundamental Analyst", icon: "📊" },
    { key: "technical_analyst", label: "Technical Analyst", icon: "📈" },
    { key: "news_harvester", label: "News Harvester", icon: "📰" },
  ];

  return (
    <div className="panel-section" style={{ marginTop: "1rem" }}>
      <details className="accordion">
        <summary className="accordion-header">
          <span>📋</span>
          <span>Analyst Reports</span>
          <span className="accordion-arrow">▾</span>
        </summary>
        <div className="accordion-body">
          {defs.map((definition) => {
            const content = reports[definition.key];

            if (!content) {
              return null;
            }

            const direction = String(signals[definition.key]?.direction || "");

            return (
              <details className="analyst-accordion" key={definition.key}>
                <summary className="analyst-summary">
                  {definition.icon} {definition.label}
                  {direction ? <span className={`badge ${direction.toLowerCase()} mini`}>{direction}</span> : null}
                  <span className="accordion-arrow">▾</span>
                </summary>
                <div className="analyst-body">
                  <MarkdownBlock content={content} />
                </div>
              </details>
            );
          })}
        </div>
      </details>
    </div>
  );
}

export function AnalysisDetails({ result }: { result: AnalysisResult }) {
  return (
    <>
      <ResearchManagerPanel result={result} />
      <RiskPanel result={result} />
      <MemoryPanel result={result} />
      <AnalystReportsPanel result={result} />
    </>
  );
}
