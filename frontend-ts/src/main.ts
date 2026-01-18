import "./styles.css";
import { createChart, ColorType, type IChartApi, type CandlestickData } from "lightweight-charts";

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
      <h1>🚀 NexusTrader</h1>
      <p>Live Multi‑Agent Stock Analysis</p>
    </header>

    <section class="card">
      <div class="input-row">
        <input id="tickerInput" placeholder="Enter ticker (e.g., TSLA, AAPL, NVDA)" />
        <button id="analyzeBtn">Analyze</button>
      </div>
      <p class="notice" style="margin-top: 8px;">Uses SSE for real‑time agent updates. Make sure the backend is running.</p>
    </section>

    <section class="card" id="statusCard" style="display:none;">
      <div class="progress-bar">
        <div class="progress-fill" id="progressFill"></div>
      </div>
      <div class="status-list" id="agentList"></div>
    </section>

    <section class="card" id="resultsCard" style="display:none;"></section>

    <footer class="footer">NexusTrader • Streaming demo</footer>
  </div>
`;

const tickerInput = document.querySelector<HTMLInputElement>("#tickerInput")!;
const analyzeBtn = document.querySelector<HTMLButtonElement>("#analyzeBtn")!;
const statusCard = document.querySelector<HTMLDivElement>("#statusCard")!;
const resultsCard = document.querySelector<HTMLDivElement>("#resultsCard")!;
const progressFill = document.querySelector<HTMLDivElement>("#progressFill")!;
const agentList = document.querySelector<HTMLDivElement>("#agentList")!;

let eventSource: EventSource | null = null;
let chart: IChartApi | null = null;

function resetUI() {
  progressFill.style.width = "0%";
  resultsCard.style.display = "none";
  resultsCard.innerHTML = "";
  statusCard.style.display = "block";
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
  document.querySelectorAll(".agent.active").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("complete");
  });

  const match = agents.find((a) => a.name === agentName);
  if (!match) return;
  const element = document.querySelector<HTMLDivElement>(`#agent-${match.key}`);
  element?.classList.add("active");
}

function markAllComplete() {
  document.querySelectorAll(".agent").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("complete");
  });
}

function showError(message: string) {
  resultsCard.style.display = "block";
  resultsCard.innerHTML = `<p class="notice">⚠️ ${message}</p>`;
}

async function renderChart(ticker: string) {
  const response = await fetch(`${apiBaseUrl}/api/chart/${ticker}?period=6mo`);
  const payload = await response.json();

  if (payload.status !== "success") {
    throw new Error(payload.message || "Chart API error");
  }

  const data = payload.data as CandlestickData[];
  const chartContainer = document.querySelector<HTMLDivElement>("#chart")!;
  chartContainer.innerHTML = "";

  chart = createChart(chartContainer, {
    layout: {
      background: { type: ColorType.Solid, color: "#ffffff" },
      textColor: "#333",
    },
    grid: {
      vertLines: { color: "#f0f0f0" },
      horzLines: { color: "#f0f0f0" },
    },
    height: 360,
  });

  const candleSeries = chart.addCandlestickSeries({
    upColor: "#2e7d32",
    downColor: "#c62828",
    borderUpColor: "#2e7d32",
    borderDownColor: "#c62828",
    wickUpColor: "#2e7d32",
    wickDownColor: "#c62828",
  });

  candleSeries.setData(data);
  chart.timeScale().fitContent();

  window.addEventListener("resize", () => {
    if (!chartContainer || !chart) return;
    chart.applyOptions({ width: chartContainer.clientWidth });
  });
}

function buildResults(result: any, ticker: string) {
  const tradingStrategy = result?.trading_strategy || {};
  const investmentPlan = result?.investment_plan || "";
  const reports = result?.reports || {};
  const action = (tradingStrategy.action || "HOLD").toLowerCase();

  resultsCard.style.display = "block";
  resultsCard.innerHTML = `
    <div class="grid grid-2">
      <div>
        <h2 style="margin-bottom: 8px;">Results for ${ticker}</h2>
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

    <div class="chart-card" id="chart"></div>

    <div class="grid" style="margin-top:16px;">
      <div>
        <div class="section-title">Investment Recommendation</div>
        <div class="report">${investmentPlan || "No investment plan returned."}</div>
      </div>
      <div>
        <div class="section-title">Fundamental Analyst</div>
        <div class="report">${reports.fundamental_analyst || "No report."}</div>
      </div>
      <div>
        <div class="section-title">Technical Analyst</div>
        <div class="report">${reports.technical_analyst || "No report."}</div>
      </div>
      <div>
        <div class="section-title">Sentiment Analyst</div>
        <div class="report">${reports.sentiment_analyst || "No report."}</div>
      </div>
      <div>
        <div class="section-title">News Harvester</div>
        <div class="report">${reports.news_harvester || "No report."}</div>
      </div>
    </div>
  `;

  renderChart(ticker).catch((err) => {
    console.error(err);
  });
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

  eventSource = new EventSource(`${apiBaseUrl}/analyze/stream?ticker=${ticker}`);

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
