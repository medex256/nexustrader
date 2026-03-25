import { marked } from "marked";
import type { AnalysisResult } from "../lib/types";
import { riskJudgmentLabel, parseBPlusRationale } from "../lib/format";

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
    const mainRisk = String((structured as Record<string, unknown>).main_risk || "");
    const primaryDrivers = Array.isArray((structured as Record<string, unknown>).primary_drivers)
      ? ((structured as Record<string, unknown>).primary_drivers as string[])
      : [];

    return (
      <div className="panel-section" style={{ marginTop: "1rem" }}>
        <details className="accordion" open>
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

            {primaryDrivers.length > 0 ? (
              <div className="rm-drivers-block">
                <span className="rm-section-label">Primary Drivers</span>
                <ul className="rm-drivers-list">
                  {primaryDrivers.map((driver) => (
                    <li key={driver}>{driver}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {mainRisk ? (
              <div className="rm-risk-block">
                <span className="rm-section-label">Main Risk</span>
                <p className="rm-risk-text">{mainRisk}</p>
              </div>
            ) : null}
            {rationale ? (
              <div className="rm-rationale-block">
                <span className="rm-section-label">Analysis</span>
                <MarkdownBlock content={rationale} />
              </div>
            ) : null}
            {holdGate ? (
              <div className="rm-holdgate-block">
                <span className="rm-section-label">Hold Decision Reasoning</span>
                <p className="rm-risk-text">{holdGate}</p>
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
        <details className="accordion" open>
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

/** Stage B: Bull/Bear specialist columns */
function DebatePanel({ result }: { result: AnalysisResult }) {
  const stage = result.run_config?.stage;
  if (stage !== "B" && stage !== "B+" && stage !== "C" && stage !== "D") return null;

  const debateState = (result.investment_debate_state ?? {}) as Record<string, unknown>;
  const bullHistory = String(debateState.bull_history || "").trim();
  const bearHistory = String(debateState.bear_history || "").trim();

  if (!bullHistory && !bearHistory) return null;

  // Extract a note value — tries each label in order, handles both "- LABEL:" and inline "LABEL:" formats
  function extractNote(text: string, labels: string[]): string {
    for (const label of labels) {
      const match = text.match(
        new RegExp(`(?:-\\s*)?${label}:\\s*([\\s\\S]*?)(?=\\s*(?:-\\s*)?[A-Z_]+:|$)`, "i"),
      );
      if (match && match[1].trim()) return match[1].trim();
    }
    return ""; // return empty so caller can fall back to full text
  }

  const upsideNote = bullHistory ? extractNote(bullHistory, ["UPSIDE_CORE", "UPSIDE_NOTE"]) : "";
  const upsideStrength = bullHistory ? (bullHistory.match(/(?:-\s*)?UPSIDE_STRENGTH:\s*(\w+)/i)?.[1] || "") : "";
  const downside = bearHistory ? extractNote(bearHistory, ["DOWNSIDE_CORE", "OVERRIDE_NOTE", "DOWNSIDE_NOTE"]) : "";
  const downsideStrength = bearHistory
    ? (bearHistory.match(/(?:-\s*)?(?:OVERRIDE_STRENGTH|DOWNSIDE_STRENGTH):\s*(\w+)/i)?.[1] || "")
    : "";

  return (
    <div className="panel-section" style={{ marginTop: "1rem" }}>
      <details className="accordion" open>
        <summary className="accordion-header">
          <span>⚖️</span>
          <span>Specialist Evidence Extraction</span>
          <span className="accordion-arrow">▾</span>
        </summary>
        <div className="accordion-body">
          <div className="debate-columns">
            <div className="debate-col debate-col-bull">
              <div className="debate-col-header">
                <span className="debate-col-icon">▲</span>
                <span className="debate-col-title">Upside Catalysts</span>
                {upsideStrength ? <span className="debate-strength-pill bull">{upsideStrength}</span> : null}
              </div>
              <p className="debate-col-body">{upsideNote || bullHistory}</p>
            </div>
            <div className="debate-col debate-col-bear">
              <div className="debate-col-header">
                <span className="debate-col-icon">▼</span>
                <span className="debate-col-title">Downside Risks</span>
                {downsideStrength ? <span className="debate-strength-pill bear">{downsideStrength.replace(/_/g, " ")}</span> : null}
              </div>
              <p className="debate-col-body">{downside || bearHistory}</p>
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}

function RiskPanel({ result }: { result: AnalysisResult }) {
  const riskMode = result.run_config?.risk_mode as string | undefined;
  // Hide entirely for stages with no risk gate
  if (riskMode === "off" || riskMode === undefined) {
    const stage = result.run_config?.stage;
    if (stage === "A" || stage === "B") return null;
  }

  const riskReports = (result.risk_reports ?? {}) as Record<string, unknown>;
  const decision = ((riskReports.risk_manager_decision ?? {}) as Record<string, unknown>);
  const strategy = result.trading_strategy ?? {};
  const judgment = String(decision.risk_judgment || decision.judgment || "").toUpperCase();
  const gate = String(riskReports.risk_gate || "");
  // Prefer structured decision rationale; fall back to the [TAG] rationale from trading_strategy
  const rawStrategyRationale = String(strategy.rationale || "");
  const bPlusRat = parseBPlusRationale(rawStrategyRationale);
  const rationale = String(decision.rationale || decision.reasoning || bPlusRat?.body || "");
  const positionSize = decision.position_size_pct ?? strategy.position_size_pct;
  const stopLoss = decision.stop_loss || decision.stop_loss_pct || strategy.stop_loss;
  const takeProfit = decision.take_profit || decision.take_profit_pct || strategy.take_profit;
  const hasRisk = judgment || gate || rationale || positionSize != null || stopLoss || takeProfit;

  if (!hasRisk) {
    return null;
  }

  const judgeCode = judgment || bPlusRat?.tag || "";
  const badgeClass = judgeCode === "CLEAR" || judgeCode === "APPROVE" ? "buy" : judgeCode === "BLOCK" ? "sell" : "hold";
  const judgeLabel = judgeCode ? riskJudgmentLabel(judgeCode) : "";

  const riskDebateState = (result.risk_debate_state ?? {}) as Record<string, unknown>;
  const aggressiveHistory = String(riskDebateState.aggressive_history || "").trim().replace(/^\*{0,2}\s*Aggressive\s+Analyst\s*:\**\s*/i, "");
  const conservativeHistory = String(riskDebateState.conservative_history || "").trim().replace(/^\*{0,2}\s*Conservative\s+Analyst\s*:\**\s*/i, "");
  const neutralHistory = String(riskDebateState.neutral_history || "").trim().replace(/^\*{0,2}\s*Neutral\s+Analyst\s*:\**\s*/i, "");
  const hasCommittee = Boolean(aggressiveHistory || conservativeHistory || neutralHistory);

  return (
    <div className="panel-section" style={{ marginTop: "1rem" }}>
      <details className="accordion" open>
        <summary className="accordion-header">
          <span>🛡️</span>
          <span>Risk Assessment</span>
          <span className="accordion-header-trail">
            {judgeLabel ? <span className={`badge ${badgeClass}`}>{judgeLabel}</span> : null}
            <span className="accordion-arrow">▾</span>
          </span>
        </summary>
        <div className="accordion-body">
          {gate ? (
            <div className="risk-gate-detail">
              <div className="risk-gate-flow">
                {gate.match(/Original:\s*([A-Z]+)/i)?.[1] ? (
                  <span className="risk-gate-step">
                    <span className="risk-gate-step-label">Research view</span>
                    <strong>{gate.match(/Original:\s*([A-Z]+)/i)![1]}</strong>
                  </span>
                ) : null}
                {gate.match(/Judgment:\s*([A-Z]+)/i)?.[1] ? (
                  <>
                    <span className="risk-gate-sep">→</span>
                    <span className="risk-gate-step">
                      <span className="risk-gate-step-label">Risk judgment</span>
                      <strong>{riskJudgmentLabel(gate.match(/Judgment:\s*([A-Z]+)/i)![1])}</strong>
                    </span>
                  </>
                ) : null}
                {gate.match(/Final:\s*([A-Z]+)/i)?.[1] ? (
                  <>
                    <span className="risk-gate-sep">→</span>
                    <span className="risk-gate-step">
                      <span className="risk-gate-step-label">Final action</span>
                      <strong>{gate.match(/Final:\s*([A-Z]+)/i)![1]}</strong>
                    </span>
                  </>
                ) : null}
              </div>
            </div>
          ) : null}
          {positionSize != null || stopLoss || takeProfit ? (
            <div className="strategy-grid" style={{ margin: "0.75rem 0" }}>
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
          {hasCommittee ? (
            <div className="risk-committee-section">
              <div className="risk-committee-title">Risk Committee Positions</div>
              <div className="risk-committee-columns">
                <div className="risk-committee-col risk-col-aggressive">
                  <div className="risk-committee-header">
                    <span>⚡</span>
                    <span>Aggressive</span>
                  </div>
                  <div className="risk-committee-body"><MarkdownBlock content={aggressiveHistory} /></div>
                </div>
                <div className="risk-committee-col risk-col-conservative">
                  <div className="risk-committee-header">
                    <span>🛡</span>
                    <span>Conservative</span>
                  </div>
                  <div className="risk-committee-body"><MarkdownBlock content={conservativeHistory} /></div>
                </div>
                <div className="risk-committee-col risk-col-neutral">
                  <div className="risk-committee-header">
                    <span>⚖️</span>
                    <span>Neutral</span>
                  </div>
                  <div className="risk-committee-body"><MarkdownBlock content={neutralHistory} /></div>
                </div>
              </div>
            </div>
          ) : null}
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
    return null;
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
          <div className={`memory-lean-chip ${bullHits > bearHits ? "lean-bull" : bearHits > bullHits ? "lean-bear" : "lean-neutral"}`}>
            {bullHits > bearHits ? "↑ Memory leans bullish" : bearHits > bullHits ? "↓ Memory leans bearish" : "↔ Memory signals balanced"}
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface NewsArticle {
  title: string;
  source: string;
  url?: string;
  published?: string;
  ticker_sentiment_label?: string;
  ticker_sentiment_score?: number;
}

function NewsLinksPanel({ result }: { result: AnalysisResult }) {
  const provenance = (result.provenance ?? {}) as Record<string, unknown>;
  const newsProvenance = (provenance.news ?? {}) as Record<string, unknown>;
  const articles = (newsProvenance.articles ?? []) as NewsArticle[];
  if (!articles.length) return null;

  function sentimentClass(label: string | undefined): string {
    if (!label) return "";
    const l = label.toLowerCase();
    if (l.includes("bullish")) return "buy";
    if (l.includes("bearish")) return "sell";
    return "hold";
  }

  function formatDate(raw: string | undefined): string {
    if (!raw) return "";
    // Format: 20210922T192604 → Sep 22 2021
    const m = raw.match(/^(\d{4})(\d{2})(\d{2})/);
    if (!m) return raw;
    const d = new Date(`${m[1]}-${m[2]}-${m[3]}`);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  return (
    <div className="panel-section" style={{ marginTop: "1rem" }}>
      <details className="accordion">
        <summary className="accordion-header">
          <span>🔗</span>
          <span>News Sources</span>
          <span className="news-count-badge">{articles.length}</span>
          <span className="accordion-arrow">▾</span>
        </summary>
        <div className="accordion-body">
          <div className="news-links-list">
            {articles.map((article, i) => (
              <div className="news-link-row" key={i}>
                <div className="news-link-meta">
                  <span className="news-link-source">{article.source}</span>
                  <span className="news-link-date">{formatDate(article.published)}</span>
                  {article.ticker_sentiment_label ? (
                    <span className={`badge ${sentimentClass(article.ticker_sentiment_label)} mini`}>
                      {article.ticker_sentiment_label}
                    </span>
                  ) : null}
                </div>
                {article.url ? (
                  <a className="news-link-title" href={article.url} rel="noopener noreferrer" target="_blank">
                    {article.title}
                  </a>
                ) : (
                  <span className="news-link-title no-link">{article.title}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </details>
    </div>
  );
}

/** Parses numbered tagged fields out of an analyst report and renders them as chips */
function StructuredAnalystReport({ content }: { content: string }) {
  const tagKeys = ["FINAL_VIEW", "CONFIDENCE", "TONE", "SUPPORT", "RESISTANCE", "KEY_\\w+"];
  const tagPattern = new RegExp(`^\\d+[).]\\s*(${tagKeys.join("|")}):\\s*(.+)$`, "i");

  const taggedFields: Array<{ key: string; value: string }> = [];
  const bodyLines: string[] = [];

  for (const line of content.split("\n")) {
    const m = line.match(tagPattern);
    if (m) {
      taggedFields.push({ key: m[1].toUpperCase(), value: m[2].trim() });
    } else {
      bodyLines.push(line);
    }
  }

  // Normalise the body:
  //  1) Section headers like "1) EVIDENCE:" or "2) RISKS:" → bold label
  //  2) Unicode bullet chars (•) → markdown list marker so they render as <li>
  const rawBody = bodyLines.join("\n").trimEnd();
  const body = rawBody
    .replace(/^\d+[).\s]+\s*(EVIDENCE|RISKS|CATALYSTS)\s*:?\s*$/gim, (_, label) => `\n**${label.toUpperCase()}**`)
    .replace(/^[•·\u2022]\s*/gm, "- ");

  function viewClass(val: string) {
    const v = val.toUpperCase();
    if (v === "BULLISH") return "buy";
    if (v === "BEARISH") return "sell";
    if (v === "NEUTRAL") return "hold";
    return "hold";
  }

  return (
    <div>
      {body ? <MarkdownBlock content={body} /> : null}
      {taggedFields.length > 0 ? (
        <div className="analyst-tags-row">
          {taggedFields.map(({ key, value }) => {
            if (key === "FINAL_VIEW" || key === "TONE") {
              return (
                <span key={key} className="analyst-tag-chip">
                  <span className="analyst-tag-key">{key === "FINAL_VIEW" ? "Final View" : "Tone"}</span>
                  <span className={`badge ${viewClass(value)} mini`}>{value}</span>
                </span>
              );
            }
            if (key === "CONFIDENCE") {
              return (
                <span key={key} className="analyst-tag-chip">
                  <span className="analyst-tag-key">Confidence</span>
                  <span className="analyst-tag-val conf">{value}</span>
                </span>
              );
            }
            if (key === "SUPPORT" || key === "RESISTANCE") {
              return (
                <span key={key} className="analyst-tag-chip">
                  <span className="analyst-tag-key">{key}</span>
                  <span className="analyst-tag-val price">{value}</span>
                </span>
              );
            }
            // KEY_UNCERTAINTY, KEY_EVENT_RISK, etc.
            const displayKey = key.replace(/^KEY_/, "").replace(/_/g, " ");
            return (
              <div key={key} className="analyst-tag-note">
                <span className="analyst-tag-key">{displayKey}</span>
                <span className="analyst-tag-note-text">{value}</span>
              </div>
            );
          })}
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
                  <StructuredAnalystReport content={content} />
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
      <DebatePanel result={result} />
      <RiskPanel result={result} />
      <MemoryPanel result={result} />
      <AnalystReportsPanel result={result} />
      <NewsLinksPanel result={result} />
    </>
  );
}

