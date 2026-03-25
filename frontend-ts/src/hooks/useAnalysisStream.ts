import { useEffect, useRef, useState } from "react";
import { buildAnalyzeStreamUrl } from "../lib/api";
import { AGENT_KEY_TO_DISPLAY, AGENT_NAME_TO_KEY, STAGE_AGENTS } from "../lib/stages";
import type { AnalysisResult, AnalyzeStreamEvent, StageKey } from "../lib/types";

interface StartAnalysisInput {
  ticker: string;
  horizon: string;
  simulatedDate: string;
  stage: StageKey;
}

interface LogEntry {
  id: number;
  kind: "info" | "success" | "error";
  message: string;
  timestamp: string;
}

function createLogEntry(id: number, kind: LogEntry["kind"], message: string): LogEntry {
  return {
    id,
    kind,
    message,
    timestamp: new Date().toLocaleTimeString(),
  };
}

export function useAnalysisStream(stage: StageKey) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const nextLogIdRef = useRef(1);

  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState(0);
  const [activeAgentKey, setActiveAgentKey] = useState<string | null>(null);
  const [visitedAgentKeys, setVisitedAgentKeys] = useState<string[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<AnalysisResult | null>(null);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  function appendLog(kind: LogEntry["kind"], message: string) {
    const id = nextLogIdRef.current;
    nextLogIdRef.current += 1;

    setLogs((current) => [createLogEntry(id, kind, message), ...current]);
  }

  function reset() {
    eventSourceRef.current?.close();
    setIsRunning(false);
    setError(null);
    setProgressPercent(0);
    setActiveAgentKey(null);
    setVisitedAgentKeys([]);
    setLogs([]);
    setResult(null);
    nextLogIdRef.current = 1;
  }

  function startAnalysis(input: StartAnalysisInput) {
    reset();

    const params = new URLSearchParams({
      ticker: input.ticker.toUpperCase(),
      stage: input.stage,
      horizon: input.horizon,
    });

    if (input.simulatedDate) {
      params.set("simulated_date", input.simulatedDate);
    }

    setIsRunning(true);
    appendLog("info", `Starting ${input.stage} analysis for ${input.ticker.toUpperCase()}`);

    const eventSource = new EventSource(buildAnalyzeStreamUrl(params));
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data) as AnalyzeStreamEvent;

      if (data.status === "processing") {
        const mappedKey = AGENT_NAME_TO_KEY[data.agent] ?? data.agent;
        const displayName = AGENT_KEY_TO_DISPLAY[mappedKey] ?? data.agent;
        const progress = Math.max(5, Math.round((data.step / Math.max(data.total, 1)) * 100));

        setProgressPercent(progress);
        setActiveAgentKey(mappedKey);
        setVisitedAgentKeys((current) => (current.includes(mappedKey) ? current : [...current, mappedKey]));
        appendLog("info", `Running ${displayName}`);
        return;
      }

      if (data.status === "executing") {
        setProgressPercent(90);
        appendLog("info", "Synthesizing final decision");
        return;
      }

      if (data.status === "complete") {
        setProgressPercent(100);
        setActiveAgentKey(null);
        setResult(data.result);
        setIsRunning(false);
        appendLog("success", "Analysis complete");
        eventSource.close();
        eventSourceRef.current = null;
        return;
      }

      if (data.status === "error") {
        const message = data.message || "Stream error";

        setError(message);
        setIsRunning(false);
        setActiveAgentKey(null);
        appendLog("error", message);
        eventSource.close();
        eventSourceRef.current = null;
      }
    };

    eventSource.onerror = () => {
      const message = "SSE connection error. Is the backend running on localhost:8000?";

      setError(message);
      setIsRunning(false);
      setActiveAgentKey(null);
      appendLog("error", message);
      eventSource.close();
      eventSourceRef.current = null;
    };
  }

  return {
    agents: STAGE_AGENTS[stage],
    activeAgentKey,
    error,
    isRunning,
    logs,
    progressPercent,
    reset,
    result,
    startAnalysis,
    visitedAgentKeys,
  };
}
