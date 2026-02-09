import "./styles.css";
import { createChart, ColorType, type IChartApi, type CandlestickData } from "lightweight-charts";
import { marked } from "marked";

const apiBaseUrl = "http://127.0.0.1:8000";

const agents = [
  { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "📊" },
  { key: "technical_analyst", name: "Technical Analyst", icon: "📈" },
  { key: "sentiment_analyst", name: "Sentiment Analyst", icon: "💬" },
  { key: "news_harvester", name: "News Harvester", icon: "📰" },
  { key: "bull_researcher", name: "Bull Researcher", icon: "🐂" },
  { key: "bear_researcher", name: "Bear Researcher", icon: "🐻" },
  { key: "research_manager", name: "Research Manager", icon: "🎯" },
  { key: "strategy_synthesizer", name: "Strategy Synthesizer", icon: "⚡" },
  { key: "risk_manager", name: "Risk Manager", icon: "🛡️" },
];

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) throw new Error("App container not found");

app.innerHTML = `
  <div class="app">
    <header class="header">
      <div style="display:flex; align-items:center; gap:16px;">
        <h1>🚀 NexusTrader</h1>
        <div class="nav-links">
          <button id="navLive" class="nav-btn active">Live Analysis</button>
          <button id="navHistory" class="nav-btn">History</button>
        </div>
      </div>
      <p style="font-size: 0.9rem; color: var(--text-secondary);">Multi‑Agent Stock Analysis</p>
    </header>

    <main id="liveView">
      <section class="card">
        <div class="input-row">
          <input id="tickerInput" placeholder="Enter ticker (e.g., TSLA, AAPL, NVDA)" />
          <button id="analyzeBtn">Analyze</button>
        </div>
        <div class="input-row" style="gap:12px; flex-wrap:wrap; margin-top:10px;">
          <label>
            Debate Rounds
            <select id="debateRoundsSelect">
              <option value="0">0 (No Debate)</option>
              <option value="1" selected>1 (Default)</option>
              <option value="2">2 (Extended)</option>
            </select>
          </label>
          <div class="toggle-group">
            <label class="toggle"><input type="checkbox" id="memoryToggle" checked /> <span>Memory</span></label>
            <label class="toggle"><input type="checkbox" id="riskToggle" checked /> <span>Risk Gate</span></label>
            <label class="toggle"><input type="checkbox" id="socialToggle" /> <span>Social</span></label>
          </div>
          <label>
            Horizon
            <select id="horizonSelect">
              <option value="short" selected>Short (10d)</option>
              <option value="medium">Medium (21d)</option>
              <option value="long">Long (126d)</option>
            </select>
          </label>
          <label>
            Simulated Date
            <input type="date" id="simDateInput" />
          </label>
        </div>
        <p class="notice" style="margin-top: 8px;">Uses SSE for real‑time agent updates. Make sure the backend is running.</p>
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
        <div id="historyList" class="history-list"></div>
      </section>
      <section class="card" id="historyDetailCard" style="display:none;">
        <button id="backToHistoryBtn" style="margin-bottom:1rem;">&larr; Back to List</button>
        <div id="historyResultsContainer"></div>
      </section>
    </main>

    <footer class="footer">NexusTrader • Streaming demo</footer>
  </div>
`;

const navLive = document.querySelector<HTMLButtonElement>("#navLive")!;
const navHistory = document.querySelector<HTMLButtonElement>("#navHistory")!;
const liveView = document.querySelector<HTMLDivElement>("#liveView")!;
const historyView = document.querySelector<HTMLDivElement>("#historyView")!;
const historyList = document.querySelector<HTMLDivElement>("#historyList")!;
const historyDetailCard = document.querySelector<HTMLDivElement>("#historyDetailCard")!;
const backToHistoryBtn = document.querySelector<HTMLButtonElement>("#backToHistoryBtn")!;
const historyResultsContainer = document.querySelector<HTMLDivElement>("#historyResultsContainer")!;

const tickerInput = document.querySelector<HTMLInputElement>("#tickerInput")!;
const analyzeBtn = document.querySelector<HTMLButtonElement>("#analyzeBtn")!;
const debateRoundsSelect = document.querySelector<HTMLSelectElement>("#debateRoundsSelect")!;
const memoryToggle = document.querySelector<HTMLInputElement>("#memoryToggle")!;
const riskToggle = document.querySelector<HTMLInputElement>("#riskToggle")!;
const socialToggle = document.querySelector<HTMLInputElement>("#socialToggle")!;
const horizonSelect = document.querySelector<HTMLSelectElement>("#horizonSelect")!;
const simDateInput = document.querySelector<HTMLInputElement>("#simDateInput")!;
const statusCard = document.querySelector<HTMLDivElement>("#statusCard")!;
const resultsCard = document.querySelector<HTMLDivElement>("#resultsCard")!;
const progressFill = document.querySelector<HTMLDivElement>("#progressFill")!;
const agentList = document.querySelector<HTMLDivElement>("#agentList")!;
const logContent = document.querySelector<HTMLDivElement>("#logContent")!;

let eventSource: EventSource | null = null;
let chart: IChartApi | null = null;

function resetUI() {
  progressFill.style.width = "0%";
  resultsCard.style.display = "none";
  resultsCard.innerHTML = "";
  statusCard.style.display = "block";
  logContent.innerHTML = "";
  
  agentList.innerHTML = agents
    .map(
      (agent) => `
        <div class="agent" id="agent-${agent.key}">
          <span>${agent.icon}</span>
          <strong>${agent.name}</strong>
        </div>
      `
    )
    .join("");
}

function updateProgress(step: number, total: number) {
  const pct = Math.min(100, Math.round((step / total) * 100));
  progressFill.style.width = `${pct}%`;
}

function markAgentActive(agentName: string) {
  // Find which agent this is
  const agentKey = agents.find(a => a.name === agentName)?.key || agentName.toLowerCase().replace(/ /g, "_");
  
  // Update the visual list
  document.querySelectorAll(".agent").forEach(el => el.classList.remove("active"));
  
  const el = document.querySelector(`#agent-${agentKey}`);
  if (el) {
     el.classList.add("active");
     el.classList.add("visited"); // Mark as having been visited at least once
  }

  // Add to activity log
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span> <span class="msg">Agent <strong>${agentName}</strong> started task...</span>`;
  logContent.prepend(entry);
}

function markAllComplete() {
  document.querySelectorAll(".agent").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("complete");
  });
  
  const entry = document.createElement("div");
  entry.className = "log-entry success";
  entry.innerHTML = `<span class="time">${new Date().toLocaleTimeString()}</span> <span class="msg">Analysis Complete.</span>`;
  logContent.prepend(entry);
}

function showError(message: string) {
  resultsCard.style.display = "block";
  resultsCard.innerHTML = `<p class="notice">⚠️ ${message}</p>`;
}

async function renderChart(ticker: string, container: HTMLElement, asOf?: string) {
  const qs = new URLSearchParams({ period: "6mo" });
  if (asOf) qs.set("as_of", asOf);
  const response = await fetch(`${apiBaseUrl}/api/chart/${ticker}?${qs.toString()}`);
  const payload = await response.json();

  if (payload.status !== "success") {
    throw new Error(payload.message || "Chart API error");
  }

  const data = payload.data as CandlestickData[];
  container.innerHTML = "";

  const newChart = createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: "#1e293b" },
      textColor: "#d1d5db",
    },
    grid: {
      vertLines: { color: "#334155" },
      horzLines: { color: "#334155" },
    },
    height: 360,
  });

  const candleSeries = newChart.addCandlestickSeries({
    upColor: "#10b981",
    downColor: "#ef4444",
    borderUpColor: "#10b981",
    borderDownColor: "#ef4444",
    wickUpColor: "#10b981",
    wickDownColor: "#ef4444",
  });

  candleSeries.setData(data);
  newChart.timeScale().fitContent();

  // Resize observer for this specific container
  const resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
      if (entry.contentBoxSize) {
        newChart.applyOptions({ width: entry.contentRect.width });
      }
    }
  });
  resizeObserver.observe(container);
  
  // If we are in the main view, we might want to track global chart variable
  // but for multiple charts (history), we just let them live in their containers.
}

function buildResults(result: any, ticker: string, container: HTMLElement = resultsCard) {
  const tradingStrategy = result?.trading_strategy || {};
  const investmentPlan = result?.investment_plan || "";
  const reports = result?.reports || {};
  const action = (tradingStrategy.action || "HOLD").toLowerCase();
  const simulatedDate = result?.simulated_date || result?.run_config?.simulated_date || "";
  const horizon = result?.horizon || result?.run_config?.horizon || "short";
  const horizonDays = result?.horizon_days || result?.run_config?.horizon_days;
  const newsProv = result?.provenance?.news;
  const analysisTime = result?.analysis_time_seconds;
  
  // Debug: log provenance data
  console.log("[DEBUG] Full result object:", result);
  console.log("[DEBUG] News provenance:", newsProv);

  container.style.display = "block";
  container.innerHTML = `
    <div class="grid grid-2">
      <div>
        <h2 style="margin-bottom: 8px;">Results for ${ticker}</h2>
        <div class="notice" style="margin: 8px 0 0;">
          <strong>As-of:</strong> ${simulatedDate || "(live)"} • <strong>Horizon:</strong> ${horizon}${horizonDays ? ` (${horizonDays} trading days)` : ""}
          ${analysisTime ? `<br/><strong>Analysis Time:</strong> ${analysisTime}s` : ""}
        </div>
        <div class="badge ${action}">
          ${action === "buy" ? "📈" : action === "sell" ? "📉" : "⏸️"}
          ${tradingStrategy.action || "HOLD"}
        </div>
        <div class="notice" style="margin-top: 12px;">${tradingStrategy.rationale || ""}</div>
      </div>
      <div class="strategy-card" style="margin:0;">
        <div class="section-title">Strategy</div>
        <div class="grid" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
          <div><strong>Entry:</strong> ${tradingStrategy.entry_price ?? "—"}</div>
          <div><strong>Take Profit:</strong> ${tradingStrategy.take_profit ?? "—"}</div>
          <div><strong>Stop Loss:</strong> ${tradingStrategy.stop_loss ?? "—"}</div>
          <div><strong>Position %:</strong> ${tradingStrategy.position_size_pct ?? "—"}</div>
        </div>
      </div>
    </div>

    <!-- Unique ID for chart container relative to this result block -->
    <div class="chart-card chart-target"></div>

    <div class="grid" style="margin-top:16px;">
      <div>
        <div class="section-title">Investment Recommendation</div>
        <div class="report prose">${marked.parse(investmentPlan || "No investment plan returned.")}</div>
      </div>
      <div>
        <div class="section-title">Fundamental Analyst</div>
        <div class="report prose">${marked.parse(reports.fundamental_analyst || "No report.")}</div>
      </div>
      <div>
        <div class="section-title">Technical Analyst</div>
        <div class="report prose">${marked.parse(reports.technical_analyst || "No report.")}</div>
      </div>
      <div>
        <div class="section-title">Sentiment Analyst</div>
        <div class="report prose">${marked.parse(reports.sentiment_analyst || "No report.")}</div>
      </div>
      <div>
        <div class="section-title">News Harvester</div>
        <div class="report prose">${marked.parse(reports.news_harvester || "No report.")}</div>
        ${newsProv ? `
          <div class="section-title" style="margin-top: 12px;">News provenance (debug)</div>
          <div class="notice">
            <div><strong>As-of:</strong> ${newsProv.as_of || "(live)"}</div>
            <div><strong>Window:</strong> ${newsProv.window_start || "?"} → ${newsProv.window_end || "?"} (${newsProv.lookback_days ?? "?"}d)</div>
            <div><strong>Articles:</strong> ${newsProv.article_count ?? 0} (showing ${Array.isArray(newsProv.articles) ? newsProv.articles.length : 0})</div>
            <div><strong>Published range:</strong> ${newsProv.min_published || "?"} → ${newsProv.max_published || "?"}</div>
          </div>
          <div class="report prose" style="margin-top: 8px;">
            <ul>
              ${(Array.isArray(newsProv.articles) ? newsProv.articles : []).map((a: any) => {
                const title = a?.title || "(untitled)";
                const source = a?.source || "";
                const published = a?.published || "";
                const url = a?.url || "";
                const label = a?.ticker_sentiment_label || "";
                return `<li><strong>${published}</strong> — ${source} — [${label}] ${url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>` : title}</li>`;
              }).join("")}
            </ul>
          </div>
        ` : ""}
      </div>
    </div>
  `;

  // Find the chart container we just created
  const chartTarget = container.querySelector<HTMLDivElement>(".chart-target");
  if (chartTarget) {
      renderChart(ticker, chartTarget, simulatedDate || undefined).catch((err) => {
        console.error(err);
        chartTarget.innerHTML = `<p class="notice">Could not load chart: ${err.message}</p>`;
      });
  }
}

function startAnalysis() {
  const ticker = tickerInput.value.trim().toUpperCase();
  if (!ticker) {
    showError("Please enter a ticker symbol.");
    return;
  }

  if (eventSource) {
    eventSource.close();
  }

  resetUI();
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Analyzing...";

  const params = new URLSearchParams({ ticker });
  if (simDateInput.value) {
    params.set("simulated_date", simDateInput.value);
  }
  params.set("horizon", horizonSelect.value);
  params.set("debate_rounds", debateRoundsSelect.value);
  params.set("memory_on", memoryToggle.checked ? "true" : "false");
  params.set("risk_on", riskToggle.checked ? "true" : "false");
  params.set("social_on", socialToggle.checked ? "true" : "false");

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
      analyzeBtn.textContent = "Analyze";
    }

    if (data.status === "error") {
      showError(data.message || "Stream error");
      eventSource?.close();
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Analyze";
    }
  };

  eventSource.onerror = () => {
    showError("SSE connection error. Check backend logs.");
    eventSource?.close();
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analyze";
  };
}

analyzeBtn.addEventListener("click", startAnalysis);

// --- History & Navigation Logic ---

interface BackendHistoryItem {
  id: string;
  document: string;
  metadata: {
     ticker: string;
     timestamp: string;
     action?: string;
     entry_price?: string;
     outcome?: string;
     final_state_json?: string; // We will add this to backend soon
     [key: string]: any;
  }
}

// Navigation
navLive.addEventListener("click", () => {
    switchView("live");
});

navHistory.addEventListener("click", () => {
    switchView("history");
    loadHistory();
});

backToHistoryBtn.addEventListener("click", () => {
    historyDetailCard.style.display = "none";
    historyList.style.display = "grid"; 
});

function switchView(view: "live" | "history") {
    if (view === "live") {
        liveView.style.display = "block";
        historyView.style.display = "none";
        navLive.classList.add("active");
        navHistory.classList.remove("active");
    } else {
        liveView.style.display = "none";
        historyView.style.display = "block";
        navLive.classList.remove("active");
        navHistory.classList.add("active");
        
        // Reset detail view just in case
        historyDetailCard.style.display = "none";
        historyList.style.display = "grid";
    }
}

async function loadHistory() {
    historyList.innerHTML = '<div class="notice">Loading history...</div>';
    
    try {
        const res = await fetch(`${apiBaseUrl}/memory/all`);
        const data = await res.json();
        
        if (data.status === "success" && Array.isArray(data.data)) {
            renderHistoryList(data.data);
        } else {
            historyList.innerHTML = '<div class="notice">No history found or error loading.</div>';
        }
    } catch (e) {
        console.error(e);
        historyList.innerHTML = '<div class="notice">Error loading history.</div>';
    }
}

function renderHistoryList(items: BackendHistoryItem[]) {
    if (items.length === 0) {
        historyList.innerHTML = '<div class="notice">No past analyses found.</div>';
        return;
    }

    historyList.innerHTML = "";
    // sort by timestamp desc
    items.sort((a, b) => new Date(b.metadata.timestamp).getTime() - new Date(a.metadata.timestamp).getTime());

    items.forEach((item) => {
        const date = new Date(item.metadata.timestamp).toLocaleString();
        const ticker = item.metadata.ticker || "UNKNOWN";
        const action = item.metadata.action || "N/A";

        const card = document.createElement("div");
        card.className = "history-item card";
        card.style.cursor = "pointer";
        card.style.transition = "transform 0.2s, background-color 0.2s";
        
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.5rem;">
                <h3 style="margin:0; font-size:1.2rem; color: var(--accent-color);">${ticker}</h3>
                <span class="badge ${action.toLowerCase()}" style="font-size:0.7rem; padding:2px 6px;">${action}</span>
            </div>
            <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:0.5rem;">${date}</div>
            <p style="font-size:0.85rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                ${item.document.replace(/\n/g, " ").substring(0, 60)}...
            </p>
        `;
        
        card.addEventListener("mouseenter", () => {
             card.style.backgroundColor = "var(--bg-tertiary)";
             card.style.transform = "translateY(-2px)";
        });
        card.addEventListener("mouseleave", () => {
             card.style.backgroundColor = ""; // reset to default css
             card.style.transform = "";
        });

        card.addEventListener("click", () => {
             showHistoryDetail(item);
        });

        historyList.appendChild(card);
    });
}

function showHistoryDetail(item: BackendHistoryItem) {
    historyList.style.display = "none";
    historyDetailCard.style.display = "block";
    historyResultsContainer.innerHTML = "";

    // Check if we have the full JSON state saved (future proofing)
    if (item.metadata.final_state_json) {
        try {
            const resultData = JSON.parse(item.metadata.final_state_json);
            buildResults(resultData, item.metadata.ticker, historyResultsContainer);
            return;
        } catch (e) {
            console.warn("Failed to parse saved JSON state, falling back to text view", e);
        }
    }

    // Fallback: Show the text document summary
    // Since we don't have the full reports structure for old items, we just show what we have.
    historyResultsContainer.innerHTML = `
        <h2 class="section-title">Analysis for ${item.metadata.ticker}</h2>
        <div class="notice" style="margin-bottom:1rem;">
           <strong>Note:</strong> This is a historical record. Interactive charts and full reports may not be available for older sessions.
        </div>
        <div class="report prose" style="white-space: pre-wrap;">
${item.document}
        </div>
    `;
}

