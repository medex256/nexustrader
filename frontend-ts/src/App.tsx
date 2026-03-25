import { useState, useEffect, useRef } from "react";
import { AnalysisSummary } from "./components/AnalysisSummary";
import { useAnalysisStream } from "./hooks/useAnalysisStream";
import { saveRunToHistory, loadHistory, clearHistory } from "./lib/localHistory";
import type { LocalHistoryEntry } from "./lib/localHistory";
import { buildClearHistoryUrl, buildHistoryUrl } from "./lib/api";
import {
  AGENT_EXPLAINERS,
  STAGE_AGENTS,
  STAGE_DELTAS,
  STAGE_EXPLAINERS,
  STAGE_MECHANISMS,
  STAGE_ORDER,
  STAGE_TOOLTIPS,
} from "./lib/stages";
import { displayDateToIso, isoDateToDisplay, sanitizeDisplayDateInput } from "./lib/format";
import type { AnalysisResult, BackendHistoryItem, StageKey } from "./lib/types";

type ViewKey = "live" | "history" | "stages" | "agents";

type FlowTone = "core" | "stage" | "risk" | "memory" | "decision";

interface FlowStep {
  label: string;
  tone: FlowTone;
}

function getDetailedFlow(stage: StageKey): FlowStep[] {
  switch (stage) {
    case "A":
      return [
        { label: "Analyst Core", tone: "core" },
        { label: "Research Manager", tone: "decision" },
      ];
    case "B":
      return [
        { label: "Analyst Core", tone: "core" },
        { label: "Specialist Extractors", tone: "stage" },
        { label: "Research Manager", tone: "decision" },
      ];
    case "B+":
      return [
        { label: "Analyst Core", tone: "core" },
        { label: "Specialist Extractors", tone: "stage" },
        { label: "Research Manager", tone: "decision" },
        { label: "Single Risk Judge", tone: "risk" },
      ];
    case "C":
      return [
        { label: "Analyst Core", tone: "core" },
        { label: "Specialist Extractors", tone: "stage" },
        { label: "Research Manager", tone: "decision" },
        { label: "Risk Committee", tone: "risk" },
      ];
    case "D":
      return [
        { label: "Analyst Core", tone: "core" },
        { label: "Memory Retrieval", tone: "memory" },
        { label: "Specialist Extractors", tone: "stage" },
        { label: "Research Manager", tone: "decision" },
        { label: "Single Risk Judge", tone: "risk" },
      ];
  }
}

function StageFlow({ stage, variant = "chips" }: { stage: StageKey; variant?: "chips" | "detailed" }) {
  const mechanisms = STAGE_MECHANISMS[stage];
  const stageIndex = STAGE_ORDER.indexOf(stage);
  const previousStage = stageIndex > 0 ? STAGE_ORDER[stageIndex - 1] : null;
  const previousMechanisms = previousStage ? new Set(STAGE_MECHANISMS[previousStage]) : new Set<string>();

  if (variant === "detailed") {
    const steps = getDetailedFlow(stage);

    return (
      <div className="stage-flow guide" aria-label={`Stage ${stage} pipeline`}>
        <div className="flow-group">
          <div className="flow-group-label">Pipeline sequence</div>
          <div className="flow-row compact">
            {steps.map((step, index) => (
              <span className="flow-step-group" key={`${stage}-${step.label}`}>
                <span className={`flow-node flow-${step.tone}`}>
                  {step.label}
                </span>
                {index < steps.length - 1 ? <span className="flow-arrow">→</span> : null}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mechanism-chip-row">
      {mechanisms.map((mechanism) => (
        <span
          className={`mechanism-chip${previousMechanisms.has(mechanism) ? "" : " mechanism-chip-new"}`}
          key={mechanism}
        >
          {mechanism}
        </span>
      ))}
    </div>
  );
}

function StageSelectorRail({ currentStage, onStageChange }: {
  currentStage: StageKey;
  onStageChange: (stage: StageKey) => void;
}) {
  return (
    <div className="stage-tab-bar" role="group" aria-label="Choose evaluation stage">
      {STAGE_ORDER.map((stageKey) => {
        const info = STAGE_EXPLAINERS[stageKey];
        const callsNum = info.llmCalls.replace(" LLM calls", "").replace(" LLM call", "");
        return (
          <button
            key={stageKey}
            className={`stage-tab${stageKey === currentStage ? " active" : ""}`}
            onClick={() => onStageChange(stageKey)}
            title={STAGE_TOOLTIPS[stageKey]}
            type="button"
          >
            <span className="stage-tab-key">{stageKey}</span>
            <span className="stage-tab-calls">{callsNum} calls</span>
          </button>
        );
      })}
    </div>
  );
}

function getPreviousStage(stage: StageKey): StageKey | null {
  const stageIndex = STAGE_ORDER.indexOf(stage);
  return stageIndex > 0 ? STAGE_ORDER[stageIndex - 1] : null;
}

function getMechanismSnapshot(stage: StageKey) {
  const currentMechanisms = STAGE_MECHANISMS[stage];
  const previousStage = getPreviousStage(stage);
  const previousMechanisms = previousStage ? new Set(STAGE_MECHANISMS[previousStage]) : new Set<string>();

  return currentMechanisms.map((mechanism) => ({
    isNew: !previousMechanisms.has(mechanism),
    label: mechanism,
  }));
}

function MechanismComparison({ stage }: { stage: StageKey }) {
  const previousStage = getPreviousStage(stage);
  const previousMechanisms = previousStage ? STAGE_MECHANISMS[previousStage] : [];
  const currentMechanisms = STAGE_MECHANISMS[stage];
  const addedMechanisms = currentMechanisms.filter((mechanism) => !previousMechanisms.includes(mechanism));

  return (
    <div className="mechanism-compare" aria-label={`Stage ${stage} mechanism comparison`}>
      <div className="mechanism-compare-head">
        <span className="stage-added-label">Before vs After</span>
        <div className="stage-mechanism-subcopy">
          {previousStage
            ? `Stage ${stage} keeps Stage ${previousStage} and adds ${addedMechanisms.join(" + ")}.`
            : "Stage A is the baseline stack that later stages build on."}
        </div>
      </div>
      <div className="mechanism-compare-grid">
        <div className="mechanism-compare-column">
          <div className="mechanism-compare-label">{previousStage ? `Before · Stage ${previousStage}` : "Before · None"}</div>
          <div className="mechanism-compare-list">
            {(previousStage ? previousMechanisms : ["No added mechanisms yet"]).map((mechanism) => (
              <span className="mechanism-compare-pill" key={`${stage}-before-${mechanism}`}>{mechanism}</span>
            ))}
          </div>
        </div>
        <div className="mechanism-compare-arrow">→</div>
        <div className="mechanism-compare-column mechanism-compare-column-active">
          <div className="mechanism-compare-label">{`After · Stage ${stage}`}</div>
          <div className="mechanism-compare-list">
            {currentMechanisms.map((mechanism) => (
              <span
                className={`mechanism-compare-pill${addedMechanisms.includes(mechanism) ? " mechanism-compare-pill-new" : ""}`}
                key={`${stage}-after-${mechanism}`}
              >
                {mechanism}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function MechanismStack({ stage }: { stage: StageKey }) {
  const mechanisms = getMechanismSnapshot(stage);

  return (
    <div className="stage-mechanism-panel">
      <div className="stage-mechanism-head">
        <span className="stage-added-label">Mechanism Stack</span>
        <div className="stage-mechanism-subcopy">Inherited layers stay muted. The new mechanism for this stage is highlighted.</div>
      </div>
      <div className="stage-mechanism-list">
        {mechanisms.map((mechanism) => (
          <div
            className={`stage-mechanism-item${mechanism.isNew ? " is-new" : ""}`}
            key={`${stage}-${mechanism.label}`}
          >
            <span className="stage-mechanism-bullet">{mechanism.isNew ? "+" : "•"}</span>
            <span className="stage-mechanism-name">{mechanism.label}</span>
            <span className="stage-mechanism-tag">{mechanism.isNew ? "New" : "Inherited"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface PipelineGroupDef {
  id: string;
  label: string;
  icons: string[];
  tone: FlowTone;
  isDebate?: boolean;
}

const CHIP_LABELS: Record<string, string> = {
  FA: "Fundamental Analyst",
  TA: "Technical Analyst",
  NH: "News Harvester",
  UP: "Upside Catalyst Analyst",
  DN: "Downside Risk Analyst",
  RM: "Research Manager",
  RG: "Risk Judge",
  AR: "Aggressive Risk Analyst",
  CR: "Conservative Risk Analyst",
  NR: "Neutral Risk Analyst",
  MEM: "Memory Retrieval",
  OUT: "Final Decision",
};

const PIPELINE_STEPS: Record<StageKey, PipelineGroupDef[]> = {
  A: [
    { id: "analysts", label: "Core Analysts", icons: ["FA", "TA", "NH"], tone: "core" },
    { id: "manager", label: "Manager", icons: ["RM"], tone: "decision" },
    { id: "output", label: "Output", icons: ["OUT"], tone: "decision" },
  ],
  B: [
    { id: "analysts", label: "Core Analysts", icons: ["FA", "TA", "NH"], tone: "core" },
    { id: "specialists", label: "Specialists", icons: ["UP", "DN"], tone: "stage" },
    { id: "manager", label: "Manager", icons: ["RM"], tone: "decision" },
    { id: "output", label: "Output", icons: ["OUT"], tone: "decision" },
  ],
  "B+": [
    { id: "analysts", label: "Core Analysts", icons: ["FA", "TA", "NH"], tone: "core" },
    { id: "specialists", label: "Specialists", icons: ["UP", "DN"], tone: "stage" },
    { id: "manager", label: "Manager", icons: ["RM"], tone: "decision" },
    { id: "risk", label: "Risk Gate", icons: ["RG"], tone: "risk" },
    { id: "output", label: "Output", icons: ["OUT"], tone: "decision" },
  ],
  C: [
    { id: "analysts", label: "Core Analysts", icons: ["FA", "TA", "NH"], tone: "core" },
    { id: "specialists", label: "Specialists", icons: ["UP", "DN"], tone: "stage" },
    { id: "manager", label: "Manager", icons: ["RM"], tone: "decision" },
    { id: "risk-debate", label: "Risk Debate", icons: ["AR", "CR", "NR"], tone: "risk", isDebate: true },
    { id: "risk-judge", label: "Risk Judge", icons: ["RG"], tone: "risk" },
    { id: "output", label: "Output", icons: ["OUT"], tone: "decision" },
  ],
  D: [
    { id: "analysts", label: "Core Analysts", icons: ["FA", "TA", "NH"], tone: "core" },
    { id: "memory", label: "Memory", icons: ["MEM"], tone: "memory" },
    { id: "specialists", label: "Specialists", icons: ["UP", "DN"], tone: "stage" },
    { id: "manager", label: "Manager", icons: ["RM"], tone: "decision" },
    { id: "risk", label: "Risk Gate", icons: ["RG"], tone: "risk" },
    { id: "output", label: "Output", icons: ["OUT"], tone: "decision" },
  ],
};

function PipelineChip({ icon, onAgentsClick }: { icon: string; onAgentsClick?: (agentKey: string) => void }) {
  const label = CHIP_LABELS[icon] ?? icon;
  const canOpenAgent = onAgentsClick && icon !== "OUT";
  if (canOpenAgent) {
    return (
      <button
        className="pipeline-node-chip pnc-clickable"
        onClick={() => onAgentsClick(icon)}
        title={label}
        aria-label={`${label} — view agent profiles`}
        type="button"
      >
        {icon === "OUT" ? "★" : icon}
        <span className="pnc-tooltip">{label}</span>
      </button>
    );
  }
  return (
    <span
      className="pipeline-node-chip"
      title={label}
      aria-label={label}
    >
      {icon === "OUT" ? "★" : icon}
      <span className="pnc-tooltip">{label}</span>
    </span>
  );
}

function PipelineViz({ stage, onAgentsClick }: { stage: StageKey; onAgentsClick?: (agentKey: string) => void }) {
  const steps = PIPELINE_STEPS[stage];
  return (
    <div className="pipeline-viz" aria-label={`Stage ${stage} data flow`}>
      {steps.flatMap((step, i) => {
        const isDebate = step.isDebate === true;
        const node = (
          <div
            className={`pipeline-node pn-${step.tone}${step.id === "output" ? " pn-output" : ""}${isDebate ? " pn-debate" : ""}`}
            key={step.id}
          >
            {isDebate ? (
              <div className="pn-debate-stack">
                <span className="pn-debate-label">3-way debate</span>
                {step.icons.map((icon) => (
                  <PipelineChip icon={icon} key={icon} onAgentsClick={onAgentsClick} />
                ))}
                <span className="pn-debate-vs">↕</span>
              </div>
            ) : (
              <div className="pipeline-node-icons">
                {step.icons.map((icon) => (
                  <PipelineChip icon={icon} key={icon} onAgentsClick={onAgentsClick} />
                ))}
              </div>
            )}
            <span className="pipeline-node-label">{step.label}</span>
          </div>
        );
        if (i < steps.length - 1) {
          return [node, <div className="pipeline-edge" key={`edge-${step.id}`}><div className="pipeline-edge-line" /></div>];
        }
        return [node];
      })}
    </div>
  );
}

// Map icon abbreviation (e.g. "NH") → agent key (e.g. "news_harvester")
const ICON_TO_AGENT_KEY: Record<string, string> = (() => {
  const map: Record<string, string> = {};
  for (const stageKey of STAGE_ORDER) {
    for (const agent of STAGE_AGENTS[stageKey]) {
      map[agent.icon] = agent.key;
    }
  }
  return map;
})();

function AgentGuide({ targetAgentKey }: { targetAgentKey?: string | null }) {
  const [activeStage, setActiveStage] = useState<StageKey>("B+");
  const agentCardRefs = useRef<Record<string, HTMLElement | null>>({});

  type AgentEntry = { key: string; name: string; icon: string };
  const allAgents: AgentEntry[] = [];
  const seen = new Set<string>();
  for (const stageKey of STAGE_ORDER) {
    for (const agent of STAGE_AGENTS[stageKey]) {
      if (!seen.has(agent.key)) {
        seen.add(agent.key);
        allAgents.push(agent);
      }
    }
  }

  const activeAgentKeys = new Set(STAGE_AGENTS[activeStage].map((a) => a.key));

  // targetAgentKey arrives as an icon abbreviation ("NH") — resolve to the real agent key
  const resolvedKey = targetAgentKey ? (ICON_TO_AGENT_KEY[targetAgentKey] ?? targetAgentKey) : null;

  // Local highlight that auto-clears so the card doesn't stay selected forever
  const [highlightKey, setHighlightKey] = useState<string | null>(null);

  useEffect(() => {
    if (!resolvedKey) {
      return;
    }
    setHighlightKey(resolvedKey);
    // Give the DOM one frame to fully mount the roster cards before scrolling
    const scrollId = setTimeout(() => {
      const targetCard = agentCardRefs.current[resolvedKey];
      if (targetCard) {
        targetCard.scrollIntoView({ behavior: "smooth", block: "start", inline: "nearest" });
      }
    }, 80);
    // Auto-clear highlight after animation completes
    const clearId = setTimeout(() => setHighlightKey(null), 2800);
    return () => {
      clearTimeout(scrollId);
      clearTimeout(clearId);
    };
  }, [resolvedKey]);

  return (
    <main>
      <section className="card agents-guide-shell">
        <h2 className="agents-heading">Agent Directory</h2>
        <p className="agents-subtitle">
          Select a stage to see which agents run and how data flows through the pipeline.
        </p>

        <div className="pipeline-section">
          <div className="pipeline-stage-switcher">
            <span className="pipeline-stage-label">Pipeline for</span>
            {STAGE_ORDER.map((stageKey) => (
              <button
                key={stageKey}
                className={`pipeline-stage-btn${activeStage === stageKey ? " active" : ""}`}
                onClick={() => setActiveStage(stageKey)}
                type="button"
              >
                {stageKey}
              </button>
            ))}
          </div>
          <div className="pipeline-scroll">
            <PipelineViz stage={activeStage} />
          </div>
          <p className="pipeline-caption">
            {STAGE_EXPLAINERS[activeStage].added.replace("New mechanism: ", "").replace("Starting point: ", "")}
          </p>
        </div>

        <div className="roster-grid" id="roster-list">
          {allAgents.map((agent, idx) => {
            const explainer = AGENT_EXPLAINERS[agent.key];
            const isActive = activeAgentKeys.has(agent.key);
            const stagesPresent = STAGE_ORDER.filter((s) =>
              STAGE_AGENTS[s].some((a) => a.key === agent.key)
            );
            return (
              <article
                className={`roster-card${isActive ? " roster-card-lit" : ""}${highlightKey === agent.key ? " roster-card-target" : ""}${agent.key === "memory_retrieval" ? " roster-card-memory" : ""}`}
                key={agent.key}
                ref={(element) => {
                  agentCardRefs.current[agent.key] = element;
                }}
                style={{ animationDelay: `${idx * 0.04}s` }}
              >
                <div className="roster-card-top">
                  <div className="roster-icon">{agent.icon}</div>
                  <div className="roster-heading">
                    <h3 className="roster-name">{explainer?.title ?? agent.name}</h3>
                    <span className="roster-role">{explainer?.role ?? "Agent"}</span>
                  </div>
                  {agent.key === "memory_retrieval" ? (
                    <span className="roster-mechanism-badge">Mechanism</span>
                  ) : isActive ? (
                    <span className="roster-active-chip">Active</span>
                  ) : null}
                </div>
                <p className="roster-summary">{explainer?.summary ?? ""}</p>
                <div className="roster-footer">
                  <div className="roster-output-row">
                    <span className="roster-fieldlabel">Output</span>
                    <span className="roster-output-text">{explainer?.output ?? ""}</span>
                  </div>
                  <div className="roster-stage-pills">
                    {STAGE_ORDER.map((s) => (
                      <span
                        className={`roster-stage-pill${stagesPresent.includes(s) ? " on" : ""}`}
                        key={`${agent.key}-${s}`}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}

function LiveAnalysisShell({ stage, onStageChange, onOpenGuide }: {
  stage: StageKey;
  onStageChange: (stage: StageKey) => void;
  onOpenGuide: () => void;
}) {
  const [ticker, setTicker] = useState("");
  const [horizon, setHorizon] = useState("short");
  const [displayDate, setDisplayDate] = useState("");
  const [dateError, setDateError] = useState("");
  const { agents, activeAgentKey, error, isRunning, logs, progressPercent, result, startAnalysis, visitedAgentKeys } =
    useAnalysisStream(stage);
  const trimmedTicker = ticker.trim().toUpperCase();
  const activeStage = STAGE_EXPLAINERS[stage];

  // Keep a browser-side fallback history for offline/dev recovery.
  useEffect(() => {
    if (result && trimmedTicker) {
      saveRunToHistory(result, trimmedTicker);
    }
  }, [result]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!trimmedTicker) {
      return;
    }

    const normalizedDate = displayDateToIso(displayDate);
    if (normalizedDate === null) {
      setDateError("Use DD/MM/YYYY, for example 12/12/2025.");
      return;
    }

    setDateError("");

    startAnalysis({
      horizon,
      simulatedDate: normalizedDate,
      stage,
      ticker: trimmedTicker,
    });
  }
  
  const introSteps = [
    {
      body: "Open How It Works to see why stages A-D are research configurations, not product tiers.",
      label: "Understand the stages",
    },
    {
      body: "Start from Stage B+ for the clearest demo of specialist extraction plus a single risk gate.",
      label: "Use Stage B+",
    },
    {
      body: "Load NVDA on 24/03/2026 for a repeatable case, or leave the date blank for latest available context.",
      label: "Run a demo case",
    },
  ];

  return (
    <main>
      <section className="card">
        <div className="live-onboarding-block">
          <div className="live-onboarding-top">
            <div className="live-onboarding-copy">
              <div className="live-onboarding-kicker">Research FYP Demo</div>
              <h2 className="live-onboarding-title">
                NexusTrader compares multi-agent AI workflows for short-horizon <span className="live-onboarding-accent">BUY, SELL, HOLD</span> forecasts.
              </h2>
              <p className="live-onboarding-body">
                Compare how each stage changes the workflow and the final directional call.
              </p>
              <div className="live-onboarding-stage-rail" aria-label="Available stages">
                {STAGE_ORDER.map((stageKey) => (
                  <span className={`live-onboarding-stage-pill${stageKey === stage ? " active" : ""}`} key={stageKey}>
                    {stageKey}
                  </span>
                ))}
              </div>
            </div>
            <ol className="live-onboarding-steps" aria-label="Start here guide">
              {introSteps.map((step, index) => (
                <li className="live-step-card" key={step.label}>
                  <span className="live-step-index">0{index + 1}</span>
                  <span className="live-step-text">
                    <strong>{step.label}</strong>
                    <span>{step.body}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="stage-selector-row">
          <div className="stage-selector-head">
            <span className="stage-label">Stage</span>
            <button className="hiw-agents-btn live-stages-btn" onClick={onOpenGuide} type="button">
              View stage guide →
            </button>
          </div>

          <StageSelectorRail currentStage={stage} onStageChange={onStageChange} />

          <div className="stage-active-strip">
            <span className="stage-delta-pill">{STAGE_DELTAS[stage]}</span>
            <span className="stage-active-desc">{activeStage.added.replace("New mechanism: ", "").replace("Starting point: ", "")}</span>
          </div>
        </div>

        <form className="input-row analysis-form" onSubmit={handleSubmit}>
          <input
            className="ticker-input"
            onChange={(event) => setTicker(event.target.value)}
            placeholder="Ticker (e.g. NVDA, AAPL)"
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
              className={`date-text-input${dateError ? " invalid" : ""}`}
              inputMode="numeric"
              maxLength={10}
              onBlur={() => {
                const normalizedDate = displayDateToIso(displayDate);
                if (normalizedDate) {
                  setDisplayDate(isoDateToDisplay(normalizedDate));
                  setDateError("");
                }
              }}
              onChange={(event) => {
                setDisplayDate(sanitizeDisplayDateInput(event.target.value));
                if (dateError) {
                  setDateError("");
                }
              }}
              placeholder="DD/MM/YYYY"
              type="text"
              value={displayDate}
            />
          </label>
          <button disabled={isRunning || trimmedTicker.length === 0} type="submit">
            {isRunning ? "Analyzing..." : "Analyze"}
          </button>
        </form>
        {dateError ? <p className="notice input-error">{dateError}</p> : null}
        <p className="notice analysis-note">
          Start an analysis to watch the agent pipeline run in real time. Leave the date blank to use the latest available price context.
        </p>
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

      {result && trimmedTicker ? <AnalysisSummary result={result} ticker={trimmedTicker} /> : null}
    </main>
  );
}

function mapBackendRunToEntry(item: BackendHistoryItem): LocalHistoryEntry {
  return {
    id: item.id,
    ticker: String(item.ticker || "").toUpperCase(),
    stage: String(item.stage || ""),
    action: String(item.action || "HOLD").toUpperCase(),
    timestamp: String(item.timestamp || new Date().toISOString()),
    rationale: String(item.rationale || ""),
    resultJson: String(item.result_json || ""),
  };
}

function HistoryShell() {
  const [entries, setEntries] = useState<LocalHistoryEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [historySource, setHistorySource] = useState<"backend" | "local">("backend");

  useEffect(() => {
    let cancelled = false;

    async function loadEntries() {
      setIsLoading(true);
      setLoadError(null);

      try {
        const response = await fetch(buildHistoryUrl());
        const payload = (await response.json()) as { status?: string; data?: BackendHistoryItem[]; message?: string };

        if (cancelled) {
          return;
        }

        if (payload.status === "success" && Array.isArray(payload.data)) {
          if (payload.data.length > 0) {
            setEntries(payload.data.map(mapBackendRunToEntry));
            setHistorySource("backend");
          } else {
            const fallbackEntries = loadHistory();
            if (fallbackEntries.length > 0) {
              setEntries(fallbackEntries);
              setHistorySource("local");
            } else {
              setEntries([]);
              setHistorySource("backend");
            }
          }
          return;
        }

        throw new Error(payload.message || "Could not load archived runs");
      } catch {
        if (cancelled) {
          return;
        }

        const fallbackEntries = loadHistory();
        setEntries(fallbackEntries);
        setHistorySource("local");
        setLoadError(
          fallbackEntries.length > 0
            ? "Backend history unavailable. Showing browser fallback history."
            : "Backend history unavailable. No archived runs found yet."
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadEntries();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedEntry = entries.find((e) => e.id === selectedId) ?? null;
  const selectedResult: AnalysisResult | null = (() => {
    if (!selectedEntry?.resultJson) return null;
    try { return JSON.parse(selectedEntry.resultJson) as AnalysisResult; } catch { return null; }
  })();

  async function handleClear() {
    clearHistory();
    setSelectedId(null);

    if (historySource === "backend") {
      try {
        const response = await fetch(buildClearHistoryUrl(), { method: "DELETE" });
        const payload = (await response.json()) as { status?: string; message?: string };

        if (payload.status !== "success") {
          throw new Error(payload.message || "Could not clear history");
        }

        setEntries([]);
        setLoadError(null);
        return;
      } catch {
        setLoadError("Could not clear backend history.");
        return;
      }
    }

    setEntries([]);
  }

  return (
    <main>
      <section className="card history-shell">
        {selectedEntry ? (
          <div className="history-entry-preamble">
            <button className="hiw-agents-btn history-nav-btn" onClick={() => setSelectedId(null)} type="button">
              ← All Analyses
            </button>
            <div className="history-entry-ident">
              <h2 className="history-entry-ticker">{selectedEntry.ticker}</h2>
              <div className="history-entry-badges">
                {selectedEntry.stage ? <span className="stage-badge">Stage {selectedEntry.stage}</span> : null}
                <span className={`badge ${selectedEntry.action.toLowerCase()}`}>{selectedEntry.action}</span>
                <span className="history-entry-date">{new Date(selectedEntry.timestamp).toLocaleString()}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="history-header-row">
            <div>
              <h2 className="history-title">All Analyses</h2>
              <p className="notice history-intro">
                {historySource === "backend"
                  ? "Archived analyses from the backend run store. Includes all stages A–D."
                  : "Showing browser fallback history for this device only."}
              </p>
            </div>
            {entries.length > 0 ? (
              <button className="hiw-agents-btn history-nav-btn history-clear-btn" onClick={handleClear} type="button" style={{ flexShrink: 0 }}>
                Clear all
              </button>
            ) : null}
          </div>
        )}

        {loadError ? <p className="notice" style={{ marginTop: "0.75rem" }}>{loadError}</p> : null}

        {isLoading && entries.length === 0 ? (
          <p className="notice" style={{ marginTop: "1rem" }}>Loading history…</p>
        ) : null}

        {!isLoading && entries.length === 0 && !selectedEntry ? (
          <p className="notice" style={{ marginTop: "1rem" }}>No runs yet. Complete an analysis on the Live Analysis page.</p>
        ) : null}

        {selectedEntry && !selectedResult ? (
          <div className="history-detail-shell">
            <div className="card history-detail-card" style={{ marginTop: "0.75rem" }}>
              <div className="history-detail-header">
                <h3 className="history-detail-title">{selectedEntry.ticker}</h3>
                <div className="history-card-badges">
                  {selectedEntry.stage ? <span className="stage-badge">Stage {selectedEntry.stage}</span> : null}
                  <span className={`badge ${selectedEntry.action.toLowerCase()}`}>{selectedEntry.action}</span>
                </div>
              </div>
              <p className="notice history-detail-meta">{new Date(selectedEntry.timestamp).toLocaleString()}</p>
              <p className="notice">{selectedEntry.rationale}</p>
            </div>
          </div>
        ) : selectedEntry && selectedResult ? (
          <div className="history-detail-shell">
            <div className="history-result-shell">
              <AnalysisSummary compact result={selectedResult} ticker={selectedEntry.ticker} />
            </div>
          </div>
        ) : (
          <div className="history-list">
            {entries.map((entry) => (
              <button
                className="history-item"
                key={entry.id}
                onClick={() => setSelectedId(entry.id)}
                type="button"
              >
                <div className="history-card-head">
                  <h3 className="history-card-title">{entry.ticker}</h3>
                  <div className="history-card-badges">
                    {entry.stage ? <span className="stage-badge">Stage {entry.stage}</span> : null}
                    <span className={`badge ${entry.action.toLowerCase()}`}>{entry.action}</span>
                  </div>
                </div>
                <div className="history-card-meta">{new Date(entry.timestamp).toLocaleString()}</div>
                <p className="history-card-snippet">{entry.rationale.slice(0, 100)}…</p>
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function StagesGuide({ onOpenAgents }: { onOpenAgents: (agentKey?: string) => void }) {
  const [activeStage, setActiveStage] = useState<StageKey>("B+");

  const FLOW_STEPS = [
    {
      num: "01",
      title: "Parallel Domain Analysis",
      body: "Fundamental, Technical, and News Harvester agents each examine the stock independently using different data sources — no shared context between them.",
      chips: ["FA", "TA", "NH"],
      tone: "core",
    },
    {
      num: "02",
      title: "Evidence Extraction",
      body: "Two specialist agents read all three reports and surface the strongest upside catalysts and downside risks the manager should focus on.",
      chips: ["UP", "DN"],
      tone: "stage",
    },
    {
      num: "03",
      title: "Manager Synthesis",
      body: "The Research Manager weighs all reports and evidence, then produces a single thesis: BUY, SELL, or HOLD with clear reasoning.",
      chips: ["RM"],
      tone: "decision",
    },
    {
      num: "04",
      title: "Risk Validation",
      body: "A risk agent (or full committee in Stage C) reviews the thesis for fragility. It can approve, reduce position size, or block the trade.",
      chips: ["RG"],
      tone: "risk",
    },
  ];

  return (
    <main>
      {/* ── Hero ── */}
      <section className="card hiw-hero">
        <div className="hiw-hero-content">
          <div className="hiw-badge">
            <span className="hiw-badge-dot" />
            <span>NexusTrader · FYP 2025/26</span>
          </div>
          <h2 className="hiw-title">
            Multi-agent AI that debates,{" "}
            <span className="hiw-gradient-word">then decides.</span>
          </h2>
          <p className="hiw-subtitle">
            NexusTrader is a Final Year Project research system that produces transparent{" "}
            <strong>BUY, SELL, or HOLD</strong> verdicts on any stock. Instead of a single AI,
            a team of specialized agents each contribute a distinct analysis layer — and can
            challenge each other before a decision is reached.
          </p>
          <div className="hiw-stats-bar">
            <div className="hiw-stat">
              <span className="hiw-stat-num">9</span>
              <span className="hiw-stat-label">Agents</span>
            </div>
            <div className="hiw-stat-div" />
            <div className="hiw-stat">
              <span className="hiw-stat-num">4–11</span>
              <span className="hiw-stat-label">LLM Calls</span>
            </div>
            <div className="hiw-stat-div" />
            <div className="hiw-stat">
              <span className="hiw-stat-num">3</span>
              <span className="hiw-stat-label">Verdicts</span>
            </div>
            <div className="hiw-stat-div" />
            <div className="hiw-stat">
              <span className="hiw-stat-num">5</span>
              <span className="hiw-stat-label">Configs</span>
            </div>
          </div>
        </div>
        <div className="hiw-hero-deco" aria-hidden="true">
          <svg className="hiw-deco-lines" viewBox="0 0 210 190" fill="none">
            <line x1="27" y1="32" x2="105" y2="110" stroke="rgba(0,82,255,0.14)" strokeWidth="1.2" />
            <line x1="105" y1="22" x2="105" y2="110" stroke="rgba(0,82,255,0.14)" strokeWidth="1.2" />
            <line x1="183" y1="32" x2="105" y2="110" stroke="rgba(0,82,255,0.14)" strokeWidth="1.2" />
            <line x1="105" y1="110" x2="52" y2="168" stroke="rgba(245,158,11,0.22)" strokeWidth="1.2" />
            <line x1="105" y1="110" x2="158" y2="168" stroke="rgba(16,185,129,0.22)" strokeWidth="1.2" />
          </svg>
          <span className="hiw-deco-n hiw-dn-1">FA</span>
          <span className="hiw-deco-n hiw-dn-2">TA</span>
          <span className="hiw-deco-n hiw-dn-3">NH</span>
          <span className="hiw-deco-n hiw-dn-4">RM</span>
          <span className="hiw-deco-n hiw-dn-5">RG</span>
          <span className="hiw-deco-n hiw-dn-6">OUT</span>
        </div>
      </section>

      {/* ── Decision Pipeline ── */}
      <section className="card hiw-flow-card">
        <div className="hiw-section-label">
          <span className="hiw-badge-dot hiw-dot-sm" />
          <span>Decision Pipeline</span>
        </div>
        <h3 className="hiw-section-title">How a verdict is reached</h3>
        <p className="hiw-section-body">
          Every analysis runs the same agent pipeline. The three core analysts work in parallel,
          then specialists surface overlooked evidence, and the research manager synthesizes
          everything. Optional risk layers then validate the final call.
        </p>
        <div className="hiw-flow-steps">
          {FLOW_STEPS.map((step, i) => (
            <div className="hiw-step-outer" key={step.num}>
              <div
                className={`hiw-step hiw-step-${step.tone}`}
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                <div className="hiw-step-top">
                  <span className="hiw-step-num">{step.num}</span>
                  <div className="hiw-step-chips">
                    {step.chips.map((c) => (
                      <span className={`hiw-chip hiw-chip-${step.tone}`} key={c}>{c}</span>
                    ))}
                  </div>
                </div>
                <h4 className="hiw-step-title">{step.title}</h4>
                <p className="hiw-step-body">{step.body}</p>
              </div>
              {i < FLOW_STEPS.length - 1 && (
                <div className="hiw-step-connector">
                  <div className="hiw-connector-line" />
                  <span className="hiw-connector-arrow">→</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Agent Pipeline ── */}
      <section className="card hiw-pipeline-card">
        <div className="hiw-pipeline-top">
          <div>
            <div className="hiw-section-label">
              <span className="hiw-badge-dot hiw-dot-sm hiw-dot-stage" />
              <span>Who Runs</span>
            </div>
            <h3 className="hiw-section-title">Agent pipeline by configuration</h3>
            <p className="hiw-section-body">
              Select a stage to see which agents are active and how data flows.
              Each stage adds exactly one new mechanism on top of the previous.
            </p>
          </div>
          <button className="hiw-agents-btn" onClick={() => onOpenAgents()} type="button">
            View all agent profiles →
          </button>
        </div>
        <div className="pipeline-section" style={{ marginTop: "1.25rem", marginBottom: 0 }}>
          <div className="pipeline-stage-switcher">
            <span className="pipeline-stage-label">Stage</span>
            {STAGE_ORDER.map((sk) => (
              <button
                className={`pipeline-stage-btn${activeStage === sk ? " active" : ""}`}
                key={sk}
                onClick={() => setActiveStage(sk)}
                type="button"
              >
                {sk}
              </button>
            ))}
          </div>
          <div className="pipeline-scroll">
            <PipelineViz stage={activeStage} onAgentsClick={onOpenAgents} />
          </div>
          <p className="pipeline-caption">
            <strong>{STAGE_EXPLAINERS[activeStage].title}:</strong>{" "}
            {STAGE_EXPLAINERS[activeStage].body}
          </p>
        </div>
      </section>

      {/* ── Stage Configurations ── */}
      <section className="card hiw-stages-card">
        <div className="hiw-section-label">
          <span className="hiw-badge-dot hiw-dot-sm hiw-dot-risk" />
          <span>Ablation Study</span>
        </div>
        <h3 className="hiw-section-title">Stage configurations</h3>
        <p className="hiw-section-body">
          The five stages are <strong>research configurations</strong> for an ablation study.
          Each adds exactly one mechanism — debate, risk checking, or memory — so the
          contribution of each layer can be measured in isolation.
        </p>
        <div className="hiw-stage-grid">
          {STAGE_ORDER.map((sk, i) => {
            const info = STAGE_EXPLAINERS[sk];
            const tone = sk.replace("+", "plus").toLowerCase();
            const prevMechs = i > 0 ? STAGE_MECHANISMS[STAGE_ORDER[i - 1]] : [];
            return (
              <button
                className={`hiw-stage-card hiw-stage-card-${tone}${activeStage === sk ? " active" : ""}`}
                key={sk}
                onClick={() => setActiveStage(sk)}
                style={{ animationDelay: `${i * 0.07}s` }}
                type="button"
              >
                <div className="hiw-sc-top">
                  <span className="hiw-sc-key">{sk}</span>
                  <span className="hiw-sc-calls">{info.llmCalls.replace(" LLM calls", "").replace(" LLM call", "")} calls</span>
                </div>
                <div className="hiw-sc-delta">{STAGE_DELTAS[sk]}</div>
                <p className="hiw-sc-why">{info.whyItExists}</p>
                <div className="hiw-sc-mechs">
                  {STAGE_MECHANISMS[sk].map((m) => (
                    <span
                      className={`hiw-mchip${!prevMechs.includes(m) ? " hiw-mchip-new" : ""}`}
                      key={m}
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
}

export function App() {
  const [view, setView] = useState<ViewKey>("stages");
  const [stage, setStage] = useState<StageKey>("B+");
  const [targetAgentKey, setTargetAgentKey] = useState<string | null>(null);

  function openAgentsPage(agentKey?: string) {
    setTargetAgentKey(agentKey ?? null);
    setView("agents");
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>NexusTrader</h1>
          <p>Transparent multi-agent equity forecasting research prototype</p>
        </div>
        <div className="nav-links">
          <button
            className={`nav-btn${view === "stages" ? " active" : ""}`}
            onClick={() => {
              setTargetAgentKey(null);
              setView("stages");
            }}
            type="button"
          >
            How It Works
          </button>
          <button
            className={`nav-btn${view === "live" ? " active" : ""}`}
            onClick={() => {
              setTargetAgentKey(null);
              setView("live");
            }}
            type="button"
          >
            Live Analysis
          </button>
          <button
            className={`nav-btn${view === "history" ? " active" : ""}`}
            onClick={() => {
              setTargetAgentKey(null);
              setView("history");
            }}
            type="button"
          >
            History
          </button>
          <button
            className={`nav-btn${view === "agents" ? " active" : ""}`}
            onClick={() => openAgentsPage()}
            type="button"
          >
            Agents
          </button>
        </div>
      </header>

      {view === "live" ? (
        <LiveAnalysisShell stage={stage} onOpenGuide={() => setView("stages")} onStageChange={setStage} />
      ) : null}
      {view === "history" ? <HistoryShell /> : null}
      {view === "stages" ? <StagesGuide onOpenAgents={(agentKey?: string) => openAgentsPage(agentKey)} /> : null}
      {view === "agents" ? <AgentGuide targetAgentKey={targetAgentKey} /> : null}

      <footer className="footer">NexusTrader · Multi-Agent LLM Trading · FYP 2025/26</footer>
    </div>
  );
}