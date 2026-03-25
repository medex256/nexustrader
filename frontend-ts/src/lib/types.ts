export type StageKey = "A" | "B" | "B+" | "C" | "D";

export interface AgentDef {
  key: string;
  name: string;
  icon: string;
}

export interface StageExplainer {
  title: string;
  body: string;
  agents: string;
  added: string;
  whyItExists: string;
  llmCalls: string;
}

export interface AgentExplainer {
  title: string;
  summary: string;
  role: string;
  output: string;
}

export interface StreamProcessingEvent {
  status: "processing";
  step: number;
  total: number;
  agent: string;
}

export interface StreamExecutingEvent {
  status: "executing";
}

export interface StreamCompleteEvent {
  status: "complete";
  result: AnalysisResult;
}

export interface StreamErrorEvent {
  status: "error";
  message?: string;
}

export type AnalyzeStreamEvent =
  | StreamProcessingEvent
  | StreamExecutingEvent
  | StreamCompleteEvent
  | StreamErrorEvent;

export interface TradingStrategy {
  action?: string;
  confidence_score?: number;
  position_size_pct?: number;
  rationale?: string;
  entry_price?: number | null;
  take_profit?: number | null;
  stop_loss?: number | null;
}

export interface RunConfig {
  stage?: StageKey;
  simulated_date?: string;
  horizon_days?: number;
  decision_style?: string;
  risk_mode?: string;
  memory_on?: boolean;
}

export interface MemorySummary {
  bull_hits?: number;
  bear_hits?: number;
}

export interface BackendHistoryItem {
  id: string;
  ticker: string;
  timestamp: string;
  action?: string;
  stage?: string;
  market?: string;
  simulated_date?: string;
  horizon?: string;
  rationale?: string;
  source?: string;
  result_json?: string;
}

export interface AnalysisResult {
  simulated_date?: string;
  horizon_days?: number;
  run_config?: RunConfig;
  trading_strategy?: TradingStrategy;
  reports?: Record<string, string>;
  signals?: Record<string, unknown>;
  llm_stats?: Record<string, unknown>;
  memory_summary?: MemorySummary;
  investment_plan?: string;
  investment_plan_structured?: Record<string, unknown> | null;
  investment_debate_state?: Record<string, unknown>;
  risk_debate_state?: Record<string, unknown>;
  risk_reports?: Record<string, unknown>;
  provenance?: Record<string, unknown>;
  analysis_time_seconds?: number;
  market_snapshot?: {
    current_price?: number;
    sma_20?: number;
    sma_50?: number;
  };
}
