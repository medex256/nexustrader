import { useState } from "react";
import { useAnalysisStream } from "./hooks/useAnalysisStream";
import { useHistory } from "./hooks/useHistory";
import {
  STAGE_AGENTS,
  STAGE_DESCRIPTIONS,
  STAGE_EXPLAINERS,
  STAGE_MECHANISMS,
  STAGE_ORDER,
} from "./lib/stages";
import type { StageKey } from "./lib/types";

type ViewKey = "live" | "history" | "stages";

function StageFlow({ stage }: { stage: StageKey }) {
  const mechanisms = STAGE_MECHANISMS[stage];

  return (
    <div className="mechanism-chip-row">
      {mechanisms.map((mechanism) => (
        <span className="mechanism-chip" key={mechanism}>
          {mechanism}
        </span>
      ))}
    </div>
  );
}

function LiveAnalysisShell({ stage, onStageChange, onOpenGuide }: {
  stage: StageKey;
  onStageChange: (stage: StageKey) => void;
  onOpenGuide: () => void;
}) {
  const [ticker, setTicker] = useState("");
  const [horizon, setHorizon] = useState("short");
  const [simulatedDate, setSimulatedDate] = useState("");
  const { agents, activeAgentKey, error, isRunning, logs, progressPercent, result, startAnalysis, visitedAgentKeys } =
    useAnalysisStream(stage);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedTicker = ticker.trim().toUpperCase();

    if (!trimmedTicker) {
      return;
    }

    startAnalysis({
      horizon,
      simulatedDate,
      stage,
      ticker: trimmedTicker,
    });
  }

  const action = result?.trading_strategy?.action || "HOLD";
  const confidence = result?.trading_strategy?.confidence_score;

  return (
    <main>
      <section className="card">
        <div className="stage-selector-row">
          <span className="stage-label">Stage</span>
          <div className="stage-pills">
            {STAGE_ORDER.map((stageKey) => (
              <button
                key={stageKey}
                className={`stage-pill${stageKey === stage ? " active" : ""}`}
                onClick={() => onStageChange(stageKey)}
                type="button"
              >
                {stageKey}
              </button>
            ))}
          </div>
          <span className="stage-desc">{STAGE_DESCRIPTIONS[stage]}</span>
          <button className="inline-link-btn" onClick={onOpenGuide} type="button">
            What do these stages mean?
          </button>
        </div>

        <div className="stage-flow-shell" style={{ marginTop: "1rem" }}>
          <div className="section-title" style={{ marginBottom: "0.75rem" }}>
            Current Pipeline
          </div>
          <StageFlow stage={stage} />
        </div>

        <form className="input-row" onSubmit={handleSubmit} style={{ marginTop: "1rem" }}>
          <input
            onChange={(event) => setTicker(event.target.value)}
            placeholder="Ticker symbol (e.g. NVDA, TSLA, AAPL)"
            value={ticker}
          />
          <label>
            Horizon
            <select onChange={(event) => setHorizon(event.target.value)} value={horizon}>
              <option value="short">Short (10d)</option>
              <option value="medium">Medium (21d)</option>
              <option value="long">Long (126d)</option>
            </select>
          </label>
          <label>
            As-of Date
            <input
              onChange={(event) => setSimulatedDate(event.target.value)}
              type="date"
              value={simulatedDate}
            />
          </label>
          <button disabled={isRunning || ticker.trim().length === 0} type="submit">
            {isRunning ? "Analyzing..." : "Analyze"}
          </button>
        </form>
        <p className="notice">Streams real-time agent progress via SSE. Backend must be running on localhost:8000.</p>
      </section>

      {isRunning || logs.length > 0 ? (
        <section className="card">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
          <div className="grid-2">
            <div className="status-list">
              {agents.map((agent) => {
                const isActive = agent.key === activeAgentKey;
                const isVisited = visitedAgentKeys.includes(agent.key);

                return (
                  <div
                    className={`agent${isActive ? " active" : ""}${isVisited ? " visited" : ""}`}
                    key={agent.key}
                  >
                    <strong>{agent.icon}</strong>
                    <span>{agent.name}</span>
                  </div>
                );
              })}
            </div>
            <div className="activity-log">
              <div className="log-title">System Activity</div>
              <div className="log-content">
                {logs.map((entry) => (
                  <div className={`log-entry${entry.kind === "success" ? " success" : ""}`} key={entry.id}>
                    <span className="time">{entry.timestamp}</span>
                    <span className="msg">{entry.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {error ? (
        <section className="card">
          <h2 className="section-title">Stream Error</h2>
          <p className="notice">{error}</p>
        </section>
      ) : null}

      {result ? (
        <section className="card">
          <h2 className="section-title">Analysis Summary</h2>
          <div className="verdict-meta-row" style={{ marginBottom: "0.75rem" }}>
            <span className={`badge ${action.toLowerCase()}`}>{action}</span>
            <span className="stage-badge">Stage {result.run_config?.stage || stage}</span>
            {typeof confidence === "number" ? (
              <span className="meta-chip">Confidence {Math.round(confidence * 100)}%</span>
            ) : null}
          </div>
          <p className="notice">
            The SSE path is now live in React and returns the final analysis payload. Detailed result panels,
            charting, and debate/risk sections will be reattached in the next patch.
          </p>
        </section>
      ) : null}
    </main>
  );
}

function HistoryShell() {
  const { error, isLoading, items } = useHistory(true);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const selectedItem = items.find((item) => item.id === selectedItemId) ?? null;

  return (
    <main>
      <section className="card">
        <h2 className="section-title">History</h2>
        <p className="notice" style={{ marginBottom: "1rem" }}>
          Past analyses stored in episodic memory. Stage D entries can include a full saved state for richer replay.
        </p>

        {isLoading ? <p className="notice">Loading history...</p> : null}
        {error ? <p className="notice">{error}</p> : null}
        {!isLoading && !error && items.length === 0 ? <p className="notice">No past analyses found in memory.</p> : null}

        {selectedItem ? (
          <div>
            <button className="inline-link-btn" onClick={() => setSelectedItemId(null)} type="button">
              Back to list
            </button>
            <div className="card" style={{ marginTop: "1rem", marginBottom: 0 }}>
              <h3 style={{ marginBottom: "0.5rem" }}>{selectedItem.metadata.ticker}</h3>
              <p className="notice" style={{ marginBottom: "1rem" }}>
                {selectedItem.metadata.stage ? `Stage ${selectedItem.metadata.stage} · ` : ""}
                {new Date(selectedItem.metadata.timestamp).toLocaleString()}
              </p>
              <div className="report prose" style={{ whiteSpace: "pre-wrap" }}>
                {selectedItem.document}
              </div>
            </div>
          </div>
        ) : (
          <div className="history-list">
            {items.map((item) => {
              const action = item.metadata.action || "N/A";
              const stage = item.metadata.stage || "";

              return (
                <button
                  className="history-item card"
                  key={item.id}
                  onClick={() => setSelectedItemId(item.id)}
                  style={{ cursor: "pointer", textAlign: "left" }}
                  type="button"
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                    <h3 style={{ margin: 0, fontSize: "1.15rem", color: "var(--accent-color)" }}>{item.metadata.ticker}</h3>
                    <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                      {stage ? <span className="stage-badge">Stage {stage}</span> : null}
                      <span className={`badge ${action.toLowerCase()}`}>{action}</span>
                    </div>
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                    {new Date(item.metadata.timestamp).toLocaleString()}
                  </div>
                  <p
                    style={{
                      color: "var(--text-secondary)",
                      fontSize: "0.82rem",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {item.document.replace(/\n/g, " ").slice(0, 90)}...
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}

function StagesGuide() {
  return (
    <main>
      <section className="card">
        <h2 className="section-title">How NexusTrader Works</h2>
        <p className="notice" style={{ marginBottom: "1rem" }}>
          Each stage adds exactly one mechanism so the effect of debate, risk control, and memory can be
          evaluated cleanly.
        </p>

        <div className="stages-overview-grid">
          {STAGE_ORDER.map((stage) => {
            const info = STAGE_EXPLAINERS[stage];
            const agents = STAGE_AGENTS[stage];

            return (
              <article className="stage-card-guide" key={stage}>
                <div className="stage-card-top">
                  <span className="stage-badge">Stage {stage}</span>
                </div>
                <h3>{info.title}</h3>
                <p>{info.body}</p>
                <div className="guide-agents">
                  <strong>Pipeline:</strong> {info.agents}
                </div>
                <div className="guide-agents" style={{ marginTop: "0.5rem" }}>
                  <strong>Agents:</strong> {agents.map((agent) => agent.name).join(" · ")}
                </div>
                <div className="guide-flow-wrap">
                  <StageFlow stage={stage} />
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}

export function App() {
  const [view, setView] = useState<ViewKey>("live");
  const [stage, setStage] = useState<StageKey>("B+");

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>NexusTrader</h1>
          <p>Multi-Agent LLM Trading System</p>
        </div>
        <div className="nav-links">
          <button
            className={`nav-btn${view === "live" ? " active" : ""}`}
            onClick={() => setView("live")}
            type="button"
          >
            Live Analysis
          </button>
          <button
            className={`nav-btn${view === "history" ? " active" : ""}`}
            onClick={() => setView("history")}
            type="button"
          >
            History
          </button>
          <button
            className={`nav-btn${view === "stages" ? " active" : ""}`}
            onClick={() => setView("stages")}
            type="button"
          >
            How It Works
          </button>
        </div>
      </header>

      {view === "live" ? (
        <LiveAnalysisShell stage={stage} onOpenGuide={() => setView("stages")} onStageChange={setStage} />
      ) : null}
      {view === "history" ? <HistoryShell /> : null}
      {view === "stages" ? <StagesGuide /> : null}

      <footer className="footer">NexusTrader · Multi-Agent LLM Trading · FYP 2025/26</footer>
    </div>
  );
}