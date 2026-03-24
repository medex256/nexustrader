import { useState } from "react";
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
      </section>

      <section className="card">
        <h2 className="section-title">Live Analysis</h2>
        <p className="notice">
          This shell is now driven by extracted stage and API contracts. The next patch reconnects the
          ticker form, SSE progress stream, and result rendering without reintroducing the monolithic DOM code.
        </p>
      </section>
    </main>
  );
}

function HistoryShell() {
  return (
    <main>
      <section className="card">
        <h2 className="section-title">History</h2>
        <p className="notice">
          History loading and detail replay are being moved behind typed history contracts next. This view
          will reuse the backend memory endpoints unchanged.
        </p>
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