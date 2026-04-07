import type { AgentDef, AgentExplainer, StageExplainer, StageKey } from "./types";

export const STAGE_AGENTS: Record<StageKey, AgentDef[]> = {
  A: [
    { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "FA" },
    { key: "technical_analyst", name: "Technical Analyst", icon: "TA" },
    { key: "news_harvester", name: "News Harvester", icon: "NH" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
  ],
  B: [
    { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "FA" },
    { key: "technical_analyst", name: "Technical Analyst", icon: "TA" },
    { key: "news_harvester", name: "News Harvester", icon: "NH" },
    { key: "bull_researcher", name: "Upside Catalyst Analyst", icon: "UP" },
    { key: "bear_researcher", name: "Downside Risk Analyst", icon: "DN" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
  ],
  "B+": [
    { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "FA" },
    { key: "technical_analyst", name: "Technical Analyst", icon: "TA" },
    { key: "news_harvester", name: "News Harvester", icon: "NH" },
    { key: "bull_researcher", name: "Upside Catalyst Analyst", icon: "UP" },
    { key: "bear_researcher", name: "Downside Risk Analyst", icon: "DN" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
    { key: "risk_manager", name: "Risk Manager", icon: "RG" },
  ],
  C: [
    { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "FA" },
    { key: "technical_analyst", name: "Technical Analyst", icon: "TA" },
    { key: "news_harvester", name: "News Harvester", icon: "NH" },
    { key: "bull_researcher", name: "Upside Catalyst Analyst", icon: "UP" },
    { key: "bear_researcher", name: "Downside Risk Analyst", icon: "DN" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
    { key: "aggressive_analyst", name: "Aggressive Risk Analyst", icon: "AR" },
    { key: "conservative_analyst", name: "Conservative Risk Analyst", icon: "CR" },
    { key: "neutral_analyst", name: "Neutral Risk Analyst", icon: "NR" },
    { key: "risk_manager", name: "Risk Committee Judge", icon: "RG" },
  ],
  D: [
    { key: "fundamental_analyst", name: "Fundamental Analyst", icon: "FA" },
    { key: "technical_analyst", name: "Technical Analyst", icon: "TA" },
    { key: "news_harvester", name: "News Harvester", icon: "NH" },
    { key: "memory_retrieval", name: "Memory Retrieval", icon: "MEM" },
    { key: "bull_researcher", name: "Upside Catalyst Analyst", icon: "UP" },
    { key: "bear_researcher", name: "Downside Risk Analyst", icon: "DN" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
    { key: "risk_manager", name: "Risk Manager", icon: "RG" },
  ],
};

export const STAGE_DESCRIPTIONS: Record<StageKey, string> = {
  A: "Stage A · baseline analyst core · 4 LLM calls · no debate · no risk gate",
  B: "Stage B · adds upside/downside evidence review · 7 LLM calls · sharper catalyst and risk coverage",
  "B+": "Stage B+ · adds one lightweight risk judge · 8 LLM calls · same evidence, safer execution",
  C: "Stage C · replaces single risk check with a risk committee · 11 LLM calls · strongest challenge layer",
  D: "Stage D · Stage B+ with episodic memory retrieval · 8 LLM calls · memory-informed single risk pass",
};

export const STAGE_TOOLTIPS: Record<StageKey, string> = {
  A: "Baseline: three domain analysts plus one manager",
  B: "Adds upside and downside extractors that surface overlooked evidence",
  "B+": "Adds one risk judge that can approve, reduce, or block the thesis",
  C: "Replaces the single judge with an adversarial risk committee",
  D: "Keeps B+ structure and adds episodic memory retrieval for the Bull/Bear reviewers",
};

export const STAGE_EXPLAINERS: Record<StageKey, StageExplainer> = {
  A: {
    title: "Stage A - Baseline Analyst Core",
    body: "Three domain analysts feed one Research Manager. No upside/downside evidence review, no risk gate, and no memory. This is the clean ablation baseline for the rest of the system.",
    agents: "Fundamental · Technical · News · Research Manager",
    added: "Starting point: only the analyst core and final synthesis layer.",
    whyItExists: "Measures what the base pipeline can do before any extra mechanism is introduced.",
    llmCalls: "4 LLM calls",
  },
  B: {
    title: "Stage B - Upside/Downside Evidence Review",
    body: "Adds one upside catalyst specialist (Bull) and one downside risk specialist (Bear). They do not make the trade decision. They sharpen the manager's view by surfacing overlooked evidence from the same analyst reports.",
    agents: "Stage A + Upside Catalyst Analyst + Downside Risk Analyst",
    added: "New mechanism: upside/downside evidence review before manager synthesis.",
    whyItExists: "Tests whether extra evidence organization improves quality without adding risk control yet.",
    llmCalls: "7 LLM calls",
  },
  "B+": {
    title: "Stage B+ - Single Risk Judge",
    body: "Keeps Stage B's evidence review, then adds one lightweight risk judge after the thesis is formed. This judge can approve, reduce, or block a trade when the setup looks fragile even if the evidence looks directional.",
    agents: "Stage B + Risk Manager",
    added: "New mechanism: one post-thesis risk gate with minimal overhead.",
    whyItExists: "Tests whether a single low-cost risk layer improves reliability without the full cost of a committee.",
    llmCalls: "8 LLM calls",
  },
  C: {
    title: "Stage C - Full Risk Committee",
    body: "Replaces the single risk judge with a three-view risk committee: aggressive, conservative, and neutral. The goal is to see whether structured adversarial challenge improves decisions or only adds cost and noise.",
    agents: "Stage B + Aggressive / Conservative / Neutral Risk Analysts + Judge",
    added: "New mechanism: adversarial risk debate instead of a single risk pass.",
    whyItExists: "Tests whether stronger internal challenge produces better final decisions than the lighter B+ gate.",
    llmCalls: "11 LLM calls",
  },
  D: {
    title: "Stage D - Memory-Augmented Reasoning",
    body: "Builds on the B+ structure, then gives the Bull/Bear reviewers access to episodic memory under strict no-leak rules. The current run can use past lessons, but only from information that would have existed at that simulated date.",
    agents: "Stage B+ + Memory Retrieval",
    added: "New mechanism: retrieval of past correct and incorrect lessons before evidence review.",
    whyItExists: "Tests whether memory improves current judgment without contaminating evaluation with future information.",
    llmCalls: "8 LLM calls",
  },
};

export const STAGE_MECHANISMS: Record<StageKey, string[]> = {
  A: ["Analyst Core", "Research Manager"],
  B: ["Analyst Core", "Upside/Downside Evidence Review", "Research Manager"],
  "B+": ["Analyst Core", "Upside/Downside Evidence Review", "Research Manager", "Single Risk Judge"],
  C: ["Analyst Core", "Upside/Downside Evidence Review", "Research Manager", "Risk Committee"],
  D: ["Analyst Core", "Upside/Downside Evidence Review", "Research Manager", "Single Risk Judge", "Episodic Memory"],
};

export const STAGE_DELTAS: Record<StageKey, string> = {
  A: "Baseline only",
  B: "+ Upside/Downside evidence review",
  "B+": "+ Single risk gate",
  C: "+ Adversarial risk committee",
  D: "+ Episodic memory retrieval",
};

export const AGENT_EXPLAINERS: Record<string, AgentExplainer> = {
  fundamental_analyst: {
    title: "Fundamental Analyst",
    summary: "Examines company quality, business performance, valuation context, and financially grounded upside or downside signals.",
    role: "Core analyst",
    output: "A structured fundamental view that feeds the research stack.",
  },
  technical_analyst: {
    title: "Technical Analyst",
    summary: "Reads price action, trend structure, momentum, and chart context to surface timing and directional clues.",
    role: "Core analyst",
    output: "A market-structure view focused on timing, confirmation, and technical risk.",
  },
  news_harvester: {
    title: "News Harvester",
    summary: "Collects recent narrative drivers, catalysts, and sentiment-relevant headlines that may change the current setup.",
    role: "Core analyst",
    output: "A news-driven context layer highlighting fresh events and narrative risk.",
  },
  research_manager: {
    title: "Research Manager",
    summary: "Synthesizes the analyst evidence into a single thesis and decides what the overall evidence actually supports.",
    role: "Synthesis judge",
    output: "The stage thesis and recommendation basis used by later risk layers.",
  },
  bull_researcher: {
    title: "Upside Catalyst Analyst",
    summary: "Searches the full analyst reports for overlooked upside drivers, catalysts, and reasons a bullish case might still be stronger than it first appears.",
    role: "Specialist extractor",
    output: "A concise upside evidence brief for the manager.",
  },
  bear_researcher: {
    title: "Downside Risk Analyst",
    summary: "Searches the full analyst reports for overlooked fragilities, bearish evidence, and reasons the current thesis may fail.",
    role: "Specialist extractor",
    output: "A concise downside evidence brief for the manager.",
  },
  risk_manager: {
    title: "Risk Manager",
    summary: "Acts as the final guardrail after the thesis is formed, deciding whether the trade should pass, be reduced, or be blocked based on fragility and risk.",
    role: "Risk gate",
    output: "A final risk judgment that can approve, constrain, or reject execution.",
  },
  aggressive_analyst: {
    title: "Aggressive Risk Analyst",
    summary: "Argues for taking more risk when the setup appears actionable and the upside looks worth the exposure.",
    role: "Risk committee member",
    output: "A pro-risk perspective inside the committee debate.",
  },
  conservative_analyst: {
    title: "Conservative Risk Analyst",
    summary: "Presses on fragility, loss containment, and whether the setup is too weak or too uncertain to justify action.",
    role: "Risk committee member",
    output: "A defensive, caution-first perspective inside the committee debate.",
  },
  neutral_analyst: {
    title: "Neutral Risk Analyst",
    summary: "Tries to balance both sides and assess whether the position is proportionate to the actual evidence quality.",
    role: "Risk committee member",
    output: "A balancing perspective that mediates between aggressive and conservative views.",
  },
  memory_retrieval: {
    title: "Memory Retrieval",
    summary: "Not a reasoning agent — a retrieval mechanism. Before the evidence review begins, it queries ChromaDB for past correct and incorrect calls on this or similar tickers, injecting lessons into the Bull/Bear agents\u2019 context. Only memory that predates the simulated date is surfaced to prevent look-ahead leakage.",
    role: "Retrieval mechanism (Stage D only)",
    output: "A structured set of past lessons injected into the specialist context before synthesis.",
  },
};

export const AGENT_NAME_TO_KEY: Record<string, string> = {
  "Fundamental Analyst": "fundamental_analyst",
  "Technical Analyst": "technical_analyst",
  "News Harvester": "news_harvester",
  "Bull Researcher": "bull_researcher",
  "Bear Researcher": "bear_researcher",
  "Research Manager": "research_manager",
  Trader: "strategy_synthesizer",
  "Risk Manager": "risk_manager",
  "Aggressive Risk Analyst": "aggressive_analyst",
  "Conservative Risk Analyst": "conservative_analyst",
  "Neutral Risk Analyst": "neutral_analyst",
  "Strategy Synthesizer": "strategy_synthesizer",
  "Sentiment Analyst": "fundamental_analyst",
  // Raw node names (backend may pass these unmapped)
  "aggressive_analyst": "aggressive_analyst",
  "conservative_analyst": "conservative_analyst",
  "neutral_analyst": "neutral_analyst",
  "risk_manager": "risk_manager",
  // LangGraph node keys for Stage C risk committee
  "aggressive_risk": "aggressive_analyst",
  "conservative_risk": "conservative_analyst",
  "neutral_risk": "neutral_analyst",
  "fundamental_analyst": "fundamental_analyst",
  "technical_analyst": "technical_analyst",
  "news_harvester": "news_harvester",
  "bull_researcher": "bull_researcher",
  "bear_researcher": "bear_researcher",
  "research_manager": "research_manager",
  "strategy_synthesizer": "strategy_synthesizer",
};

/** Map agent key → human-readable display name */
export const AGENT_KEY_TO_DISPLAY: Record<string, string> = {
  ...Object.fromEntries(
    Object.values(STAGE_AGENTS)
      .flat()
      .map((a) => [a.key, a.name])
  ),
  strategy_synthesizer: "Trader",
};

export const STAGE_ORDER: StageKey[] = ["A", "B", "B+", "C", "D"];
