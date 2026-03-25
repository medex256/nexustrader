import "./styles.css";
import { createChart, ColorType, type CandlestickData } from "lightweight-charts";
import { marked } from "marked";

const apiBaseUrl = "http://127.0.0.1:8000";

// ── Stage Configuration ──────────────────────────────────────────────────────
type StageKey = "A" | "B" | "B+" | "C" | "D";
interface AgentDef { key: string; name: string; icon: string; }

const STAGE_AGENTS: Record<StageKey, AgentDef[]> = {
  A: [
    { key: "fundamental_analyst", name: "Fundamental Analyst",     icon: "📊" },
    { key: "technical_analyst",   name: "Technical Analyst",       icon: "📈" },
    { key: "news_harvester",      name: "News Harvester",          icon: "📰" },
    { key: "research_manager",    name: "Research Manager",        icon: "🎯" },
  ],
  B: [
    { key: "fundamental_analyst", name: "Fundamental Analyst",     icon: "📊" },
    { key: "technical_analyst",   name: "Technical Analyst",       icon: "📈" },
    { key: "news_harvester",      name: "News Harvester",          icon: "📰" },
    { key: "bull_researcher",     name: "Upside Catalyst Analyst", icon: "🐂" },
    { key: "bear_researcher",     name: "Downside Risk Analyst",   icon: "🐻" },
    { key: "research_manager",    name: "Research Manager",        icon: "🎯" },
  ],
  "B+": [
    { key: "fundamental_analyst", name: "Fundamental Analyst",     icon: "📊" },
    { key: "technical_analyst",   name: "Technical Analyst",       icon: "📈" },
    { key: "news_harvester",      name: "News Harvester",          icon: "📰" },
    { key: "bull_researcher",     name: "Upside Catalyst Analyst", icon: "🐂" },
    { key: "bear_researcher",     name: "Downside Risk Analyst",   icon: "🐻" },
    { key: "research_manager",    name: "Research Manager",        icon: "🎯" },
    { key: "risk_manager",        name: "Risk Manager",            icon: "🛡️" },
  ],
  C: [
    { key: "fundamental_analyst",  name: "Fundamental Analyst",       icon: "📊" },
    { key: "technical_analyst",    name: "Technical Analyst",         icon: "📈" },
    { key: "news_harvester",       name: "News Harvester",            icon: "📰" },
    { key: "bull_researcher",      name: "Upside Catalyst Analyst",   icon: "🐂" },
    { key: "bear_researcher",      name: "Downside Risk Analyst",     icon: "🐻" },
    { key: "research_manager",     name: "Research Manager",          icon: "🎯" },
    { key: "aggressive_analyst",   name: "Aggressive Risk Analyst",   icon: "⚡" },
    { key: "conservative_analyst", name: "Conservative Risk Analyst", icon: "🔒" },
    { key: "neutral_analyst",      name: "Neutral Risk Analyst",      icon: "⚖️" },
    { key: "risk_manager",         name: "Risk Committee Judge",      icon: "🛡️" },
  ],
  D: [
    { key: "fundamental_analyst", name: "Fundamental Analyst",     icon: "📊" },
    { key: "technical_analyst",   name: "Technical Analyst",       icon: "📈" },
    { key: "news_harvester",      name: "News Harvester",          icon: "📰" },
    { key: "bull_researcher",     name: "Upside Catalyst Analyst", icon: "🐂" },
    { key: "bear_researcher",     name: "Downside Risk Analyst",   icon: "🐻" },
    { key: "research_manager",    name: "Research Manager",        icon: "🎯" },
    { key: "risk_manager",        name: "Risk Manager + Memory",   icon: "🧠" },
  ],
};

const STAGE_DESCRIPTIONS: Record<StageKey, string> = {
  A:    "Stage A — Analyst core only · 4 LLM calls · No debate · No risk",
  B:    "Stage B — + Specialist evidence extraction · 6 LLM calls",
  "B+": "Stage B+ — + Single risk judge · 7 LLM calls",
  C:    "Stage C — + Full risk committee debate · 11 LLM calls",
  D:    "Stage D — + Episodic memory · 11+ LLM calls",
};

const STAGE_TOOLTIPS: Record<StageKey, string> = {
  A: "Analyst core only",
  B: "Adds upside and downside specialist extractors",
  "B+": "Adds a single risk judge",
  C: "Adds full risk committee debate",
  D: "Adds episodic memory retrieval",
};

const STAGE_EXPLAINERS: Record<StageKey, { title: string; body: string; agents: string }> = {
  A: {
    title: "Stage A — Baseline Analyst Core",
    body: "Three domain analysts feed one Research Manager. This is the clean baseline used to test whether extra delegation helps at all.",
    agents: "Fundamental · Technical · News · Research Manager",
  },
  B: {
    title: "Stage B — Specialist Evidence Extraction",
    body: "Adds one upside specialist and one downside specialist. They do not decide the trade; they surface overlooked catalysts and risks for the Research Manager.",
    agents: "Stage A + Bull Specialist + Bear Specialist",
  },
  "B+": {
    title: "Stage B+ — Single Risk Judge",
    body: "Keeps Stage B's evidence extraction, then applies one lightweight risk layer to approve, reduce, or block the thesis.",
    agents: "Stage B + Risk Manager",
  },
  C: {
    title: "Stage C — Full Risk Committee",
    body: "Replaces the single risk pass with a small risk debate. This tests whether more adversarial challenge improves reliability or just adds noise.",
    agents: "Stage B + Aggressive / Conservative / Neutral Risk Analysts + Judge",
  },
  D: {
    title: "Stage D — Memory-Augmented Reasoning",
    body: "Adds retrieval of past lessons under strict no-leak rules. This tests whether episodic memory improves current decisions without contaminating evaluation.",
    agents: "Stage B+ + Memory Retrieval",
  },
};

const STAGE_MECHANISMS: Record<StageKey, string[]> = {
  A: ["Analyst Core", "Research Manager"],
  B: ["Analyst Core", "Specialist Extractors", "Research Manager"],
  "B+": ["Analyst Core", "Specialist Extractors", "Research Manager", "Single Risk Judge"],
  C: ["Analyst Core", "Specialist Extractors", "Research Manager", "Risk Committee"],
  D: ["Analyst Core", "Specialist Extractors", "Research Manager", "Single Risk Judge", "Memory"],
};

// Maps backend SSE display names → agent keys
const AGENT_NAME_TO_KEY: Record<string, string> = {
  "Fundamental Analyst": "fundamental_analyst",
  "Technical Analyst":   "technical_analyst",
  "News Harvester":      "news_harvester",
  "Bull Researcher":     "bull_researcher",
  "Bear Researcher":     "bear_researcher",
  "Research Manager":    "research_manager",
  "Risk Manager":        "risk_manager",
  "Aggressive Risk Analyst":   "aggressive_analyst",
  "Conservative Risk Analyst": "conservative_analyst",
  "Neutral Risk Analyst":      "neutral_analyst",
  "Strategy Synthesizer":      "research_manager",
  "Sentiment Analyst":         "fundamental_analyst",
};

// ── App State ───────────────────────────────────────────────────────────────
let currentStage: StageKey = "B+";
let activeAgents: AgentDef[] = STAGE_AGENTS["B+"];
let eventSource: EventSource | null = null;

// ── DOM Template ─────────────────────────────────────────────────────────────
const app = document.querySelector<HTMLDivElement>("#app");
if (!app) throw new Error("App container not found");

app.innerHTML = `
  <div class="app">
    <header class="header">
      <div style="display:flex; align-items:center; gap:16px;">
        <h1>NexusTrader</h1>
        <div class="nav-links">
          <button id="navLive" class="nav-btn active">Live Analysis</button>
          <button id="navHistory" class="nav-btn">History</button>
          <button id="navStages" class="nav-btn">How It Works</button>
        </div>
      </div>
      <p style="font-size: 0.9rem; color: var(--text-secondary);">Multi‑Agent LLM Trading System</p>
    </header>

    <main id="liveView">
      <section class="card">
        <div class="stage-selector-row">
          <span class="stage-label">Stage</span>
          <div class="stage-pills">
            <button class="stage-pill" data-stage="A" title="${STAGE_TOOLTIPS.A}">A</button>
            <button class="stage-pill" data-stage="B" title="${STAGE_TOOLTIPS.B}">B</button>
            <button class="stage-pill active" data-stage="B+" title="${STAGE_TOOLTIPS["B+"]}">B+</button>
            <button class="stage-pill" data-stage="C" title="${STAGE_TOOLTIPS.C}">C</button>
            <button class="stage-pill" data-stage="D" title="${STAGE_TOOLTIPS.D}">D</button>
          </div>
          <span class="stage-desc" id="stageDesc">${STAGE_DESCRIPTIONS["B+"]}</span>
          <button id="openStagesGuide" class="inline-link-btn" type="button">What do these stages mean?</button>
        </div>

        <div class="input-row" style="margin-top: 14px;">
          <input id="tickerInput" placeholder="Ticker symbol (e.g. NVDA, TSLA, AAPL)" style="flex:1; min-width:210px;" />
          <label>Horizon
            <select id="horizonSelect">
              <option value="short" selected>Short (10d)</option>
              <option value="medium">Medium (21d)</option>
              <option value="long">Long (126d)</option>
            </select>
          </label>
          <label>As-of Date
            <input type="date" id="simDateInput" />
          </label>
          <button id="analyzeBtn">▶ Analyze</button>
        </div>
        <p class="notice" style="margin-top: 8px;">Streams real‑time agent progress via SSE. Backend must be running on <strong>localhost:8000</strong>.</p>
        <div id="stageFlowPreview" class="stage-flow-shell"></div>
      </section>

      <section class="card" id="statusCard" style="display:none;">
        <div class="progress-bar">
          <div class="progress-fill" id="progressFill"></div>
        </div>
        <div class="grid-2">
          <div class="status-list" id="agentList"></div>
          <div class="activity-log" id="activityLog">
            <div class="log-title">System Activity</div>
            <div class="log-content" id="logContent"></div>
          </div>
        </div>
      </section>

      <section class="card" id="resultsCard" style="display:none;"></section>
    </main>

    <main id="historyView" style="display:none;">
      <section class="card">
        <h2 class="section-title">Past Analyses</h2>
        <p class="notice" style="margin-bottom:1rem;">Analyses stored in ChromaDB episodic memory (Stage D runs include full state replay).</p>
        <div id="historyList" class="history-list"></div>
      </section>
      <section class="card" id="historyDetailCard" style="display:none;">
        <button id="backToHistoryBtn" style="margin-bottom:1rem;">&larr; Back to List</button>
        <div id="historyResultsContainer"></div>
      </section>
    </main>

    <main id="stagesView" style="display:none;">
      <section class="card">
        <h2 class="section-title">How NexusTrader Works</h2>
        <div class="notice" style="margin-bottom:1rem;">
          NexusTrader is a controlled study of multi-agent LLM topology. Each stage adds exactly one mechanism so the impact of debate, risk control, and memory can be observed cleanly.
        </div>
        <div class="stages-overview-grid">
          ${Object.entries(STAGE_EXPLAINERS).map(([stage, info]) => `
            <article class="stage-card-guide">
              <div class="stage-card-top">
                <span class="stage-badge">Stage ${stage}</span>
              </div>
              <h3>${info.title}</h3>
              <p>${info.body}</p>
              <div class="guide-agents"><strong>Pipeline:</strong> ${info.agents}</div>
              <div class="guide-flow-wrap">${renderStageFlow(stage as StageKey, "guide")}</div>
            </article>
          `).join("")}
        </div>
        <div class="architecture-callout">
          <h3>Key Design Lesson</h3>
          <p>More agents are not automatically better. The project tests which added layers genuinely improve reasoning quality and which ones simply add latency or noise.</p>
        </div>
      </section>
    </main>

    <footer class="footer">NexusTrader · Multi-Agent LLM Trading · FYP 2025/26</footer>
  </div>
`;

// ── DOM References ───────────────────────────────────────────────────────────
const navLive = document.querySelector<HTMLButtonElement>("#navLive")!;
const navHistory = document.querySelector<HTMLButtonElement>("#navHistory")!;
const navStages = document.querySelector<HTMLButtonElement>("#navStages")!;
const liveView = document.querySelector<HTMLDivElement>("#liveView")!;
const historyView = document.querySelector<HTMLDivElement>("#historyView")!;
const stagesView = document.querySelector<HTMLDivElement>("#stagesView")!;
const historyList = document.querySelector<HTMLDivElement>("#historyList")!;
const historyDetailCard = document.querySelector<HTMLDivElement>("#historyDetailCard")!;
const backToHistoryBtn = document.querySelector<HTMLButtonElement>("#backToHistoryBtn")!;
const historyResultsContainer = document.querySelector<HTMLDivElement>("#historyResultsContainer")!;

const tickerInput = document.querySelector<HTMLInputElement>("#tickerInput")!;
const analyzeBtn = document.querySelector<HTMLButtonElement>("#analyzeBtn")!;
const horizonSelect = document.querySelector<HTMLSelectElement>("#horizonSelect")!;
const simDateInput = document.querySelector<HTMLInputElement>("#simDateInput")!;
const statusCard = document.querySelector<HTMLDivElement>("#statusCard")!;
const resultsCard = document.querySelector<HTMLDivElement>("#resultsCard")!;
const progressFill = document.querySelector<HTMLDivElement>("#progressFill")!;
const agentList = document.querySelector<HTMLDivElement>("#agentList")!;
const logContent = document.querySelector<HTMLDivElement>("#logContent")!;
const stageDescEl = document.querySelector<HTMLSpanElement>("#stageDesc")!;
const openStagesGuideBtn = document.querySelector<HTMLButtonElement>("#openStagesGuide")!;
const stageFlowPreview = document.querySelector<HTMLDivElement>("#stageFlowPreview")!;

// Set default date to today
const _today = new Date();
simDateInput.value = `${_today.getFullYear()}-${String(_today.getMonth() + 1).padStart(2, "0")}-${String(_today.getDate()).padStart(2, "0")}`;

// ── Stage Selection ──────────────────────────────────────────────────────────
function applyStage(stage: StageKey) {
  currentStage = stage;
  activeAgents = STAGE_AGENTS[stage];
  stageDescEl.textContent = STAGE_DESCRIPTIONS[stage];
  stageFlowPreview.innerHTML = renderStageFlow(stage, "compact");
  document.querySelectorAll<HTMLButtonElement>(".stage-pill").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.stage === stage);
  });
}

document.querySelectorAll<HTMLButtonElement>(".stage-pill").forEach(btn => {
  btn.addEventListener("click", () => applyStage(btn.dataset.stage as StageKey));
});

applyStage(currentStage);

function stageNode(label: string, kind: "core" | "stage" | "risk" | "memory" | "decision" = "core"): string {
  return `<div class="flow-node flow-${kind}">${label}</div>`;
}

function renderStageFlow(stage: StageKey, mode: "compact" | "guide"): string {
  const isGuide = mode === "guide";
  const baseNodes = [
    stageNode("Input", "core"),
    stageNode("Fundamental", "core"),
    stageNode("Technical", "core"),
    stageNode("News", "core"),
  ];

  const extras: string[] = [];
  if (stage !== "A") {
    extras.push(stageNode("Bull", "stage"));
    extras.push(stageNode("Bear", "stage"));
  }

  const rm = stageNode("Research Manager", "decision");

  if (stage === "B+") extras.push(stageNode("Risk Judge", "risk"));
  if (stage === "C") extras.push(stageNode("Risk Committee", "risk"));
  if (stage === "D") {
    extras.push(stageNode("Risk Judge", "risk"));
    extras.push(stageNode("Memory", "memory"));
  }

  const finalNode = stageNode("BUY / SELL / HOLD", "decision");
  const groups = isGuide
    ? [
        `<div class="flow-group"><div class="flow-group-label">Inputs</div><div class="flow-row">${baseNodes.join('<div class="flow-arrow">→</div>')}</div></div>`,
        extras.length ? `<div class="flow-group"><div class="flow-group-label">Added Mechanisms</div><div class="flow-row">${extras.join('<div class="flow-arrow">→</div>')}</div></div>` : "",
        `<div class="flow-group"><div class="flow-group-label">Decision</div><div class="flow-row">${rm}<div class="flow-arrow">→</div>${finalNode}</div></div>`,
      ]
    : [
        `<div class="flow-row compact">${baseNodes.join('<div class="flow-arrow">→</div>')}${extras.length ? `<div class="flow-arrow">→</div>${extras.join('<div class="flow-arrow">→</div>')}` : ""}<div class="flow-arrow">→</div>${rm}<div class="flow-arrow">→</div>${finalNode}</div>`,
      ];

  const badgeRow = STAGE_MECHANISMS[stage]
    .map(label => `<span class="mechanism-chip">${label}</span>`)
    .join("");

  return `<div class="stage-flow ${mode}">${groups.join("")}<div class="mechanism-chip-row">${badgeRow}</div></div>`;
}

// ── Helper: SVG Confidence Ring ──────────────────────────────────────────────
function confRingHtml(pct: number, color: string): string {
  const circumference = 2 * Math.PI * 30;
  const dash = Math.round((pct / 100) * circumference);
  return `<div class="confidence-ring">
    <svg viewBox="0 0 80 80" width="80" height="80">
      <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="7"/>
      <circle cx="40" cy="40" r="30" fill="none" stroke="${color}" stroke-width="7"
        stroke-dasharray="${dash} ${Math.round(circumference)}" stroke-linecap="round"
        transform="rotate(-90 40 40)"/>
      <text x="40" y="46" text-anchor="middle" fill="${color}" font-size="15" font-weight="700">${pct}%</text>
    </svg>
    <span class="conf-label">confidence</span>
  </div>`;
}

// ── Helper: Risk Badge ───────────────────────────────────────────────────────
function riskBadgeHtml(riskReports: Record<string, any>): string {
  const decision = riskReports?.risk_manager_decision ?? {};
  const judgment = String(decision.risk_judgment || decision.judgment || "").toUpperCase();
  if (!judgment) return "";
  const cls = judgment === "CLEAR" || judgment === "APPROVE" ? "buy" : judgment === "BLOCK" ? "sell" : "hold";
  return `<span class="badge ${cls}" style="margin-left:auto;font-size:0.65rem;">${judgment}</span>`;
}

function stripRiskPrefix(text: string): string {
  return String(text || "").replace(/^\s*\[[A-Z_]+\]\s*/i, "").trim();
}

function parseRiskFlow(riskReports: Record<string, any>, finalAction: string) {
  const gate = String(riskReports?.risk_gate || "");
  const decision = riskReports?.risk_manager_decision ?? {};
  const original = gate.match(/Original:\s*([A-Z]+)/i)?.[1] || "—";
  const judgment = String(decision.risk_judgment || gate.match(/Judgment:\s*([A-Z]+)/i)?.[1] || "—").toUpperCase();
  const final = gate.match(/Final:\s*([A-Z]+)/i)?.[1] || (finalAction || "—").toUpperCase();
  return { original, judgment, final };
}

function formatPublishedDate(value: string): string {
  if (!value) return "Unknown time";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(parsed).replace(",", "") + " UTC";
}

function formatShortDate(value: string): string {
  if (!value) return "?";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

function renderExecutionProfile(strategy: Record<string, any>, decisionStyle: string): string {
  const entry = strategy.entry_price;
  const takeProfit = strategy.take_profit;
  const stopLoss = strategy.stop_loss;
  const position = strategy.position_size_pct;
  const hasPriceLevels = entry != null || takeProfit != null || stopLoss != null;

  if (!hasPriceLevels && decisionStyle === "classification") {
    return `
      <div class="execution-mode-card">
        <div class="execution-mode-title">Directional classification mode</div>
        <div class="execution-mode-copy">This run produces a directional recommendation and a risk-adjusted position size. Entry, stop loss, and take profit are not generated in this evaluation mode.</div>
        <div class="strategy-grid" style="margin-top:1rem;">
          <div><span class="param-label">Mode</span><span class="param-val">Classification</span></div>
          <div><span class="param-label">Position Size</span><span class="param-val">${position != null ? position + "%" : "—"}</span></div>
          <div><span class="param-label">Execution Levels</span><span class="param-val subtle">Not generated</span></div>
        </div>
      </div>`;
  }

  return `
    <div class="strategy-grid">
      <div><span class="param-label">Entry</span><span class="param-val">${entry ?? "—"}</span></div>
      <div><span class="param-label">Take Profit</span><span class="param-val tp">${takeProfit ?? "—"}</span></div>
      <div><span class="param-label">Stop Loss</span><span class="param-val sl">${stopLoss ?? "—"}</span></div>
      <div><span class="param-label">Position Size</span><span class="param-val">${position != null ? position + "%" : "—"}</span></div>
    </div>`;
}

// ── Helper: Render RM Decision ───────────────────────────────────────────────
function renderRMDecision(structured: Record<string, any>): string {
  const rec: string = structured.recommendation || structured.action || "";
  const priorConfirmed: boolean | undefined = structured.prior_confirmed;
  const rationale: string = structured.base_view_rationale || structured.override_reason || structured.rationale || "";
  const holdGate: string = structured.hold_gate_assessment || "";
  const primaryDrivers: string[] = structured.primary_drivers || structured.key_factors || [];

  let html = "";
  if (rec) {
    html += `<div style="margin-bottom:1rem;"><span class="badge ${rec.toLowerCase()}" style="font-size:0.85rem;">Recommendation: ${rec}</span></div>`;
  }
  if (priorConfirmed !== undefined) {
    html += `<div style="margin-bottom:0.5rem;"><strong>Prior View Confirmed:</strong> ${priorConfirmed ? "✅ Yes" : "❌ No"}</div>`;
  }
  if (rationale) html += `<div class="prose" style="margin-bottom:0.75rem;">${marked.parse(rationale) as string}</div>`;
  if (holdGate) html += `<div class="notice" style="margin-bottom:0.5rem;"><strong>Hold Gate:</strong> ${holdGate}</div>`;
  if (primaryDrivers.length) {
    html += `<div><strong>Primary Drivers:</strong><ul style="margin-top:0.35rem;padding-left:1.2rem;">${primaryDrivers.map((d: string) => `<li>${d}</li>`).join("")}</ul></div>`;
  }
  return html || `<pre class="report" style="white-space:pre-wrap;font-size:0.78rem;">${JSON.stringify(structured, null, 2)}</pre>`;
}

// ── Helper: Render Risk Section ──────────────────────────────────────────────
function renderRiskSection(riskReports: Record<string, any>): string {
  const decision = riskReports.risk_manager_decision ?? {};
  const judgment = String(decision.risk_judgment || decision.judgment || "").toUpperCase();
  const gate: string = riskReports.risk_gate || "";
  const posSizePct = decision.position_size_pct;
  const stopLoss = decision.stop_loss || decision.stop_loss_pct;
  const takeProfit = decision.take_profit || decision.take_profit_pct;
  const rationale: string = decision.rationale || decision.reasoning || "";

  let html = "";
  if (judgment) {
    const cls = judgment === "CLEAR" || judgment === "APPROVE" ? "buy" : judgment === "BLOCK" ? "sell" : "hold";
    html += `<div style="margin-bottom:1rem;"><span class="badge ${cls}" style="font-size:0.85rem;">Risk Judgment: ${judgment}</span></div>`;
  }
  if (gate) html += `<div class="notice" style="margin-bottom:0.75rem;">${gate}</div>`;
  if (posSizePct !== undefined || stopLoss || takeProfit) {
    html += `<div class="strategy-grid" style="margin-bottom:0.75rem;">`;
    if (posSizePct !== undefined) html += `<div><span class="param-label">Adjusted Position</span><span class="param-val">${posSizePct}%</span></div>`;
    if (stopLoss)    html += `<div><span class="param-label">Stop Loss</span><span class="param-val sl">${stopLoss}</span></div>`;
    if (takeProfit)  html += `<div><span class="param-label">Take Profit</span><span class="param-val tp">${takeProfit}</span></div>`;
    html += "</div>";
  }
  if (rationale) html += `<div class="prose">${marked.parse(rationale) as string}</div>`;
  return html || `<pre class="report" style="white-space:pre-wrap;font-size:0.78rem;">${JSON.stringify(riskReports, null, 2)}</pre>`;
}

// ── Helper: Render Analyst Reports ──────────────────────────────────────────
function renderAnalystReports(reports: Record<string, any>, signals: Record<string, any>, newsProv: any): string {
  const defs = [
    { key: "fundamental_analyst", label: "Fundamental Analyst", icon: "📊" },
    { key: "technical_analyst",   label: "Technical Analyst",   icon: "📈" },
    { key: "news_harvester",      label: "News Harvester",      icon: "📰" },
  ];

  const parts = defs.map(def => {
    const content: string = reports[def.key] || "";
    if (!content) return "";
    const sig = signals[def.key] || {};
    const dir: string = sig.direction || sig.view || sig.signal || "";
    const dirBadge = dir
      ? `<span class="badge ${dir.toLowerCase()} mini" style="margin-left:8px;">${dir}</span>`
      : "";

    let extra = "";
    if (def.key === "news_harvester" && newsProv) {
      const articles: any[] = Array.isArray(newsProv.articles) ? newsProv.articles : [];
      const topArticles = articles.slice(0, 8);
      const remaining = Math.max(0, articles.length - topArticles.length);
      extra = `<div class="news-prov">
        <div><strong>Window:</strong> ${formatShortDate(newsProv.window_start || "")} → ${formatShortDate(newsProv.window_end || "")} (${newsProv.lookback_days ?? "?"}d) · ${newsProv.article_count ?? articles.length} articles</div>
        ${topArticles.length ? `<ul class="articles-list">${topArticles.map((a: any) => {
          const title = a?.title || "(untitled)";
          const source = a?.source || "";
          const published = formatPublishedDate(a?.published || "");
          const url = a?.url || "";
          const label = a?.ticker_sentiment_label || "";
          return `<li><strong>${published}</strong> [${label}] ${source}${url ? ` — <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>` : ` — ${title}`}</li>`;
        }).join("")}</ul>` : ""}
        ${remaining > 0 ? `<details class="more-articles"><summary>Show ${remaining} more article${remaining === 1 ? "" : "s"}</summary><ul class="articles-list">${articles.slice(8).map((a: any) => {
          const title = a?.title || "(untitled)";
          const source = a?.source || "";
          const published = formatPublishedDate(a?.published || "");
          const url = a?.url || "";
          const label = a?.ticker_sentiment_label || "";
          return `<li><strong>${published}</strong> [${label}] ${source}${url ? ` — <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>` : ` — ${title}`}</li>`;
        }).join("")}</ul></details>` : ""}
      </div>`;
    }

    return `<details class="analyst-accordion">
      <summary class="analyst-summary">
        ${def.icon} ${def.label}${dirBadge}
        <span class="accordion-arrow">▾</span>
      </summary>
      <div class="analyst-body report prose">${marked.parse(content) as string}</div>
      ${extra}
    </details>`;
  });

  const rendered = parts.filter(Boolean).join("");
  return rendered || `<div class="notice">No analyst reports available.</div>`;
}

// ── Core UI Functions ────────────────────────────────────────────────────────
function resetUI() {
  progressFill.style.width = "0%";
  resultsCard.style.display = "none";
  resultsCard.innerHTML = "";
  statusCard.style.display = "block";
  logContent.innerHTML = "";

  agentList.innerHTML = activeAgents
    .map(a => `<div class="agent" id="agent-${a.key}">
      <span>${a.icon}</span>
      <strong>${a.name}</strong>
    </div>`)
    .join("");
}

function updateProgress(step: number, total: number) {
  progressFill.style.width = `${Math.min(100, Math.round((step / total) * 100))}%`;
}

function markAgentActive(agentDisplayName: string) {
  const agentKey = AGENT_NAME_TO_KEY[agentDisplayName]
    || activeAgents.find(a => a.name === agentDisplayName)?.key
    || agentDisplayName.toLowerCase().replace(/ /g, "_");

  document.querySelectorAll(".agent").forEach(el => el.classList.remove("active"));
  const el = document.querySelector(`#agent-${agentKey}`);
  if (el) { el.classList.add("active"); el.classList.add("visited"); }

  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span> <span class="msg">→ <strong>${agentDisplayName}</strong></span>`;
  logContent.prepend(entry);
}

function markAllComplete() {
  document.querySelectorAll(".agent").forEach(el => { el.classList.remove("active"); el.classList.add("complete"); });
  const entry = document.createElement("div");
  entry.className = "log-entry success";
  entry.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span> <span class="msg">✅ Analysis complete</span>`;
  logContent.prepend(entry);
}

function showError(message: string) {
  resultsCard.style.display = "block";
  resultsCard.innerHTML = `<p class="notice">⚠️ ${message}</p>`;
}

async function renderChart(ticker: string, container: HTMLElement, asOf?: string) {
  const qs = new URLSearchParams({ period: "6mo" });
  if (asOf) qs.set("as_of", asOf);
  const response = await fetch(`${apiBaseUrl}/api/chart/${ticker}?${qs}`);
  const payload = await response.json();
  if (payload.status !== "success") throw new Error(payload.message || "Chart API error");

  const data = payload.data as CandlestickData[];
  container.innerHTML = "";

  const newChart = createChart(container, {
    layout: { background: { type: ColorType.Solid, color: "#1e293b" }, textColor: "#d1d5db" },
    grid: { vertLines: { color: "#334155" }, horzLines: { color: "#334155" } },
    height: 300,
  });

  const candleSeries = newChart.addCandlestickSeries({
    upColor: "#10b981", downColor: "#ef4444",
    borderUpColor: "#10b981", borderDownColor: "#ef4444",
    wickUpColor: "#10b981", wickDownColor: "#ef4444",
  });
  candleSeries.setData(data);

  if (asOf && data.length) {
    candleSeries.setMarkers([{
      time: asOf as any,
      position: "aboveBar",
      color: "#3b82f6",
      shape: "arrowDown",
      text: "Analysis Date",
    }]);
  }

  newChart.timeScale().fitContent();
  const ro = new ResizeObserver(entries => {
    for (const e of entries) newChart.applyOptions({ width: e.contentRect.width });
  });
  ro.observe(container);
}

// ── Build Results ────────────────────────────────────────────────────────────
function buildResults(result: any, ticker: string, container: HTMLElement = resultsCard) {
  const ts = result?.trading_strategy ?? {};
  const reports = result?.reports ?? {};
  const signals = result?.signals ?? {};
  const action = (ts.action || "HOLD").toLowerCase();
  const simulatedDate: string = result?.simulated_date || result?.run_config?.simulated_date || "";
  const horizonDays = result?.horizon_days || result?.run_config?.horizon_days;
  const stage: string = result?.run_config?.stage || "";
  const analysisTime = result?.analysis_time_seconds;
  const llmStats = result?.llm_stats ?? {};
  const memorySummary = result?.memory_summary;
  const investmentPlan: string = result?.investment_plan || "";
  const debateState = result?.investment_debate_state ?? {};
  const investmentPlanStructured = result?.investment_plan_structured ?? null;
  const riskReports = result?.risk_reports ?? {};
  const newsProv = result?.provenance?.news;
  const decisionStyle: string = result?.run_config?.decision_style || "classification";
  const cleanedRationale = stripRiskPrefix(ts.rationale || "");
  const riskFlow = parseRiskFlow(riskReports, ts.action || "HOLD");

  const actionColor = action === "buy" ? "#10b981" : action === "sell" ? "#ef4444" : "#f59e0b";
  const confidence = ts.confidence_score != null ? Math.round(Number(ts.confidence_score) * 100) : null;
  const hasDebate = !!(debateState.bull_history || debateState.bear_history);
  const hasRisk = !!(riskReports.risk_manager_decision || riskReports.risk_gate);
  const memoryOn = memorySummary !== undefined && memorySummary !== null;
  const hasMemory = memoryOn && ((memorySummary?.bull_hits ?? 0) + (memorySummary?.bear_hits ?? 0)) > 0;

  container.style.display = "block";
  container.innerHTML = `
    <!-- ═══ VERDICT HERO ═══ -->
    <div class="verdict-hero">
      <div class="verdict-badge-wrap">
        <div class="verdict-action ${action}">
          ${action === "buy" ? "📈 BUY" : action === "sell" ? "📉 SELL" : "⏸ HOLD"}
        </div>
        ${confidence !== null ? confRingHtml(confidence, actionColor) : ""}
      </div>
      <div class="verdict-meta">
        <div class="verdict-meta-row">
          ${stage ? `<span class="stage-badge">Stage ${stage}</span>` : ""}
          <span class="meta-chip">${ticker}</span>
          <span class="meta-chip">${formatShortDate(simulatedDate || "") || "live"}</span>
          <span class="meta-chip">k = ${horizonDays ?? 10}d</span>
        </div>
        <div class="risk-strip">
          <div class="risk-strip-step"><span class="risk-strip-label">Original Thesis</span><span class="risk-strip-value">${riskFlow.original}</span></div>
          <div class="risk-strip-arrow">→</div>
          <div class="risk-strip-step"><span class="risk-strip-label">Risk Judgment</span><span class="risk-strip-value">${riskFlow.judgment}</span></div>
          <div class="risk-strip-arrow">→</div>
          <div class="risk-strip-step"><span class="risk-strip-label">Final Action</span><span class="risk-strip-value">${riskFlow.final}${ts.position_size_pct != null && action !== "hold" ? ` (${ts.position_size_pct}%)` : ""}</span></div>
        </div>
        <div class="verdict-rationale">${cleanedRationale || "No rationale returned."}</div>
      </div>
    </div>

    <!-- ═══ POSITION PARAMS + CHART ═══ -->
    <div class="grid-2" style="margin-top:1.5rem; align-items:start;">
      <div class="strategy-card">
        <div class="section-title" style="margin-bottom:1rem;">Execution Profile</div>
        ${renderExecutionProfile(ts, decisionStyle)}
      </div>
      <div class="chart-card chart-target"><div style="padding:1rem;color:var(--text-secondary);font-size:0.85rem;">Loading chart…</div></div>
    </div>

    <!-- ═══ DEBATE PANEL ═══ -->
    ${hasDebate ? `
    <div class="panel-section" style="margin-top:1.5rem;">
      <div class="panel-header"><span>⚔️</span><span>Evidence Extraction — Bull vs Bear</span></div>
      <div class="debate-grid">
        <div class="debate-side bull-side">
          <div class="debate-side-label bull-label">🐂 Upside Catalyst Analyst</div>
          <div class="debate-content prose">${marked.parse(String(debateState.bull_history || "")) as string}</div>
        </div>
        <div class="debate-side bear-side">
          <div class="debate-side-label bear-label">🐻 Downside Risk Analyst</div>
          <div class="debate-content prose">${marked.parse(String(debateState.bear_history || "")) as string}</div>
        </div>
      </div>
    </div>` : `
    <div class="panel-section dim-panel" style="margin-top:1.5rem;">
      <div class="panel-header dim"><span>⚔️</span><span>Evidence Extraction — Off (Stage A · no specialist extractors)</span></div>
    </div>`}

    <!-- ═══ RESEARCH MANAGER ═══ -->
    ${investmentPlanStructured ? `
    <div class="panel-section" style="margin-top:1rem;">
      <details class="accordion">
        <summary class="accordion-header"><span>🎯</span><span>Research Manager Decision</span><span class="accordion-arrow">▾</span></summary>
        <div class="accordion-body">${renderRMDecision(investmentPlanStructured)}</div>
      </details>
    </div>` : investmentPlan ? `
    <div class="panel-section" style="margin-top:1rem;">
      <details class="accordion">
        <summary class="accordion-header"><span>🎯</span><span>Research Manager Recommendation</span><span class="accordion-arrow">▾</span></summary>
        <div class="accordion-body"><div class="report prose">${marked.parse(investmentPlan) as string}</div></div>
      </details>
    </div>` : ""}

    <!-- ═══ RISK GATE ═══ -->
    ${hasRisk ? `
    <div class="panel-section" style="margin-top:1rem;">
      <details class="accordion" open>
        <summary class="accordion-header">
          <span>🛡️</span><span>Risk Gate</span>
          ${riskBadgeHtml(riskReports)}
          <span class="accordion-arrow">▾</span>
        </summary>
        <div class="accordion-body">${renderRiskSection(riskReports)}</div>
      </details>
    </div>` : `
    <div class="panel-section dim-panel" style="margin-top:1rem;">
      <div class="panel-header dim"><span>🛡️</span><span>Risk Gate — Off (Stage A/B)</span></div>
    </div>`}

    <!-- ═══ MEMORY ═══ -->
    ${memoryOn ? `
    <div class="panel-section${!hasMemory ? " dim-panel" : ""}" style="margin-top:1rem;">
      <div class="panel-header${!hasMemory ? " dim" : ""}">
        <span>🧠</span>
        <span>Episodic Memory — ${hasMemory
          ? `${(memorySummary.bull_hits || 0) + (memorySummary.bear_hits || 0)} past lesson${((memorySummary.bull_hits || 0) + (memorySummary.bear_hits || 0)) !== 1 ? "s" : ""} retrieved`
          : "Stage D · 0 relevant past lessons found"}</span>
      </div>
      ${hasMemory ? `
      <div class="memory-grid">
        <div class="memory-pill bull-mem">🐂 Upside retrieved <strong>${memorySummary.bull_hits || 0}</strong> lesson${memorySummary.bull_hits !== 1 ? "s" : ""}</div>
        <div class="memory-pill bear-mem">🐻 Downside retrieved <strong>${memorySummary.bear_hits || 0}</strong> lesson${memorySummary.bear_hits !== 1 ? "s" : ""}</div>
      </div>` : ""}
    </div>` : `
    <div class="panel-section dim-panel" style="margin-top:1rem;">
      <div class="panel-header dim"><span>🧠</span><span>Episodic Memory — Off (Stage A/B/B+/C)</span></div>
    </div>`}

    <!-- ═══ ANALYST REPORTS ═══ -->
    <div class="panel-section" style="margin-top:1rem;">
      <details class="accordion">
        <summary class="accordion-header"><span>📋</span><span>Analyst Reports</span><span class="accordion-arrow">▾</span></summary>
        <div class="accordion-body">${renderAnalystReports(reports, signals, newsProv)}</div>
      </details>
    </div>

    <!-- ═══ LLM METADATA FOOTER ═══ -->
    ${Object.keys(llmStats).length ? `
    <div class="llm-meta-footer">
      ${analysisTime ? `<span>⏱ ${analysisTime}s</span>` : ""}
      <span>🤖 ${llmStats.total_calls || 0} LLM calls</span>
      <span>🔤 ${(((llmStats.total_tokens || 0)) / 1000).toFixed(1)}k tokens</span>
      ${stage ? `<span class="stage-badge" style="font-size:0.7rem;">Stage ${stage}</span>` : ""}
    </div>` : ""}
  `;

  const chartTarget = container.querySelector<HTMLDivElement>(".chart-target");
  if (chartTarget) {
    renderChart(ticker, chartTarget, simulatedDate || undefined).catch(err => {
      chartTarget.innerHTML = `<p class="notice">Chart unavailable: ${err.message}</p>`;
    });
  }
}

// ── Start Analysis ───────────────────────────────────────────────────────────
function startAnalysis() {
  const ticker = tickerInput.value.trim().toUpperCase();
  if (!ticker) { showError("Please enter a ticker symbol."); return; }

  if (eventSource) eventSource.close();

  resetUI();
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing…";

  const params = new URLSearchParams({ ticker });
  params.set("stage", currentStage);
  if (simDateInput.value) params.set("simulated_date", simDateInput.value);
  params.set("horizon", horizonSelect.value);

  eventSource = new EventSource(`${apiBaseUrl}/analyze/stream?${params.toString()}`);

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.status === "processing") {
      updateProgress(data.step, data.total);
      markAgentActive(data.agent);
    }
    if (data.status === "executing") {
      progressFill.style.width = "90%";
    }
    if (data.status === "complete") {
      progressFill.style.width = "100%";
      markAllComplete();
      buildResults(data.result, ticker);
      eventSource?.close();
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "▶ Analyze";
    }
    if (data.status === "error") {
      showError(data.message || "Stream error");
      eventSource?.close();
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "▶ Analyze";
    }
  };

  eventSource.onerror = () => {
    showError("SSE connection error. Is the backend running on localhost:8000?");
    eventSource?.close();
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "▶ Analyze";
  };
}

analyzeBtn.addEventListener("click", startAnalysis);
tickerInput.addEventListener("keydown", (e) => { if (e.key === "Enter") startAnalysis(); });

// ── Navigation ───────────────────────────────────────────────────────────────
navLive.addEventListener("click", () => switchView("live"));
navHistory.addEventListener("click", () => { switchView("history"); loadHistory(); });
navStages.addEventListener("click", () => switchView("stages"));
openStagesGuideBtn.addEventListener("click", () => switchView("stages"));
backToHistoryBtn.addEventListener("click", () => {
  historyDetailCard.style.display = "none";
  historyList.style.display = "grid";
});

function switchView(view: "live" | "history" | "stages") {
  if (view === "live") {
    liveView.style.display = "block";
    historyView.style.display = "none";
    stagesView.style.display = "none";
    navLive.classList.add("active");
    navHistory.classList.remove("active");
    navStages.classList.remove("active");
  } else if (view === "history") {
    liveView.style.display = "none";
    historyView.style.display = "block";
    stagesView.style.display = "none";
    navLive.classList.remove("active");
    navHistory.classList.add("active");
    navStages.classList.remove("active");
    historyDetailCard.style.display = "none";
    historyList.style.display = "grid";
  } else {
    liveView.style.display = "none";
    historyView.style.display = "none";
    stagesView.style.display = "block";
    navLive.classList.remove("active");
    navHistory.classList.remove("active");
    navStages.classList.add("active");
  }
}

// ── History ──────────────────────────────────────────────────────────────────
interface BackendHistoryItem {
  id: string;
  document: string;
  metadata: {
    ticker: string;
    timestamp: string;
    action?: string;
    stage?: string;
    final_state_json?: string;
    [key: string]: any;
  };
}

async function loadHistory() {
  historyList.innerHTML = '<div class="notice">Loading history…</div>';
  try {
    const res = await fetch(`${apiBaseUrl}/memory/all`);
    const data = await res.json();
    if (data.status === "success" && Array.isArray(data.data)) {
      renderHistoryList(data.data);
    } else {
      historyList.innerHTML = '<div class="notice">No history found.</div>';
    }
  } catch {
    historyList.innerHTML = '<div class="notice">Error loading history. Is the backend running?</div>';
  }
}

function renderHistoryList(items: BackendHistoryItem[]) {
  if (!items.length) {
    historyList.innerHTML = '<div class="notice">No past analyses found in memory.</div>';
    return;
  }

  historyList.innerHTML = "";
  items
    .sort((a, b) => new Date(b.metadata.timestamp).getTime() - new Date(a.metadata.timestamp).getTime())
    .forEach(item => {
      const date = new Date(item.metadata.timestamp).toLocaleString();
      const ticker = item.metadata.ticker || "UNKNOWN";
      const action = item.metadata.action || "N/A";
      const stage = item.metadata.stage || "";

      const card = document.createElement("div");
      card.className = "history-item card";
      card.style.cursor = "pointer";
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
          <h3 style="margin:0;font-size:1.15rem;color:var(--accent-color);">${ticker}</h3>
          <div style="display:flex;gap:6px;align-items:center;">
            ${stage ? `<span class="stage-badge" style="font-size:0.65rem;">Stage ${stage}</span>` : ""}
            <span class="badge ${action.toLowerCase()}" style="font-size:0.7rem;">${action}</span>
          </div>
        </div>
        <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.5rem;">${date}</div>
        <p style="font-size:0.82rem;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
          ${item.document.replace(/\n/g, " ").substring(0, 90)}…
        </p>
      `;

      card.addEventListener("mouseenter", () => {
        card.style.backgroundColor = "var(--bg-tertiary)";
        card.style.transform = "translateY(-2px)";
      });
      card.addEventListener("mouseleave", () => {
        card.style.backgroundColor = "";
        card.style.transform = "";
      });
      card.addEventListener("click", () => showHistoryDetail(item));
      historyList.appendChild(card);
    });
}

function showHistoryDetail(item: BackendHistoryItem) {
  historyList.style.display = "none";
  historyDetailCard.style.display = "block";
  historyResultsContainer.innerHTML = "";

  if (item.metadata.final_state_json) {
    try {
      const resultData = JSON.parse(item.metadata.final_state_json);
      buildResults(resultData, item.metadata.ticker, historyResultsContainer);
      return;
    } catch (e) {
      console.warn("Failed to parse saved state JSON, falling back to text", e);
    }
  }

  // Text fallback for entries without full state
  historyResultsContainer.innerHTML = `
    <h2 class="section-title">Analysis for ${item.metadata.ticker}</h2>
    <div class="notice" style="margin-bottom:1rem;">
      Historical record — full reports available only for Stage D runs with memory storage enabled.
    </div>
    <div class="report prose" style="white-space:pre-wrap;">${item.document}</div>
  `;
}

