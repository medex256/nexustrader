import type { AgentDef, StageExplainer, StageKey } from "./types";

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
    { key: "bull_researcher", name: "Upside Catalyst Analyst", icon: "UP" },
    { key: "bear_researcher", name: "Downside Risk Analyst", icon: "DN" },
    { key: "research_manager", name: "Research Manager", icon: "RM" },
    { key: "risk_manager", name: "Risk Manager + Memory", icon: "MM" },
  ],
};

export const STAGE_DESCRIPTIONS: Record<StageKey, string> = {
  A: "Stage A - Analyst core only · 4 LLM calls · No debate · No risk",
  B: "Stage B - + Specialist evidence extraction · 6 LLM calls",
  "B+": "Stage B+ - + Single risk judge · 7 LLM calls",
  C: "Stage C - + Full risk committee debate · 11 LLM calls",
  D: "Stage D - + Episodic memory · 11+ LLM calls",
};

export const STAGE_TOOLTIPS: Record<StageKey, string> = {
  A: "Analyst core only",
  B: "Adds upside and downside specialist extractors",
  "B+": "Adds a single risk judge",
  C: "Adds full risk committee debate",
  D: "Adds episodic memory retrieval",
};

export const STAGE_EXPLAINERS: Record<StageKey, StageExplainer> = {
  A: {
    title: "Stage A - Baseline Analyst Core",
    body: "Three domain analysts feed one Research Manager. This is the clean baseline used to test whether extra delegation helps at all.",
    agents: "Fundamental · Technical · News · Research Manager",
  },
  B: {
    title: "Stage B - Specialist Evidence Extraction",
    body: "Adds one upside specialist and one downside specialist. They do not decide the trade; they surface overlooked catalysts and risks for the Research Manager.",
    agents: "Stage A + Bull Specialist + Bear Specialist",
  },
  "B+": {
    title: "Stage B+ - Single Risk Judge",
    body: "Keeps Stage B's evidence extraction, then applies one lightweight risk layer to approve, reduce, or block the thesis.",
    agents: "Stage B + Risk Manager",
  },
  C: {
    title: "Stage C - Full Risk Committee",
    body: "Replaces the single risk pass with a small risk debate. This tests whether more adversarial challenge improves reliability or just adds noise.",
    agents: "Stage B + Aggressive / Conservative / Neutral Risk Analysts + Judge",
  },
  D: {
    title: "Stage D - Memory-Augmented Reasoning",
    body: "Adds retrieval of past lessons under strict no-leak rules. This tests whether episodic memory improves current decisions without contaminating evaluation.",
    agents: "Stage B+ + Memory Retrieval",
  },
};

export const STAGE_MECHANISMS: Record<StageKey, string[]> = {
  A: ["Analyst Core", "Research Manager"],
  B: ["Analyst Core", "Specialist Extractors", "Research Manager"],
  "B+": ["Analyst Core", "Specialist Extractors", "Research Manager", "Single Risk Judge"],
  C: ["Analyst Core", "Specialist Extractors", "Research Manager", "Risk Committee"],
  D: ["Analyst Core", "Specialist Extractors", "Research Manager", "Single Risk Judge", "Memory"],
};

export const AGENT_NAME_TO_KEY: Record<string, string> = {
  "Fundamental Analyst": "fundamental_analyst",
  "Technical Analyst": "technical_analyst",
  "News Harvester": "news_harvester",
  "Bull Researcher": "bull_researcher",
  "Bear Researcher": "bear_researcher",
  "Research Manager": "research_manager",
  "Risk Manager": "risk_manager",
  "Aggressive Risk Analyst": "aggressive_analyst",
  "Conservative Risk Analyst": "conservative_analyst",
  "Neutral Risk Analyst": "neutral_analyst",
  "Strategy Synthesizer": "research_manager",
  "Sentiment Analyst": "fundamental_analyst",
};

export const STAGE_ORDER: StageKey[] = ["A", "B", "B+", "C", "D"];
