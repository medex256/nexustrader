# In nexustrader/backend/app/main.py
import os
import json
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .graph.agent_graph import create_agent_graph
from .utils.memory import initialize_memory, get_memory
from .utils.run_archive import initialize_run_archive, get_run_archive
from .utils.stage_a_cache import (
    build_stage_a_cache_key,
    extract_cached_reports,
    extract_cached_signals,
    extract_cached_stage_a_prior,
    get_cached_stage_a_trace,
)
from .tools.technical_analysis_tools import get_chart_data_json
from .baselines.strategies import get_baseline
from .llm import get_call_stats, get_token_log, reset_call_stats, reset_token_log

DEFAULT_MEMORY_DIR = "./chroma_db"
DEFAULT_ARCHIVE_DB = "./run_archive.sqlite3"
MEMORY_DIR = os.getenv("NEXUSTRADER_MEMORY_DIR", DEFAULT_MEMORY_DIR)
ARCHIVE_DB_PATH = os.getenv("NEXUSTRADER_ARCHIVE_DB", DEFAULT_ARCHIVE_DB)


def ensure_storage_paths(memory_dir: str, archive_db_path: str) -> None:
    os.makedirs(memory_dir, exist_ok=True)

    archive_parent = os.path.dirname(os.path.abspath(archive_db_path))
    if archive_parent:
        os.makedirs(archive_parent, exist_ok=True)

# Create the FastAPI app
app = FastAPI(
    title="NexusTrader API",
    description="An API for running the NexusTrader multi-agent trading analysis.",
    version="0.1.0",
)

# --- CORS Middleware ---
# This allows the frontend to make requests to the backend.
# In a production environment, you would restrict this to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Initialize Memory System on Startup ---
@app.on_event("startup")
async def startup_event():
    """Initialize the memory system when the server starts."""
    ensure_storage_paths(MEMORY_DIR, ARCHIVE_DB_PATH)

    print("[STARTUP] Initializing memory system...")
    initialize_memory(persist_directory=MEMORY_DIR)
    print("[STARTUP] Memory system ready!")
    print("[STARTUP] Initializing run archive...")
    initialize_run_archive(db_path=ARCHIVE_DB_PATH)
    print("[STARTUP] Run archive ready!")

# --- Static File Serving ---
# Get the absolute path to the directory of the current file (main.py)
current_file_dir = os.path.dirname(os.path.abspath(__file__))
# Construct the path to the 'charts' directory (located at ../charts relative to this file)
charts_directory = os.path.join(current_file_dir, "..", "charts")
# Construct the path to the 'frontend' directory
frontend_directory = os.path.join(current_file_dir, "..", "..", "frontend")

# Mount the charts directory to serve static files under the /static/charts URL
app.mount("/static/charts", StaticFiles(directory=charts_directory), name="charts")
# Mount the frontend directory to serve the demo HTML
app.mount("/demo", StaticFiles(directory=frontend_directory, html=True), name="frontend")


# Horizon mapping: convert human-readable to trading days
HORIZON_MAP = {
    "short": 10,
    "medium": 21,
    "long": 126,
}

STAGE_PRESETS = {
    "A": {"debate_mode": "off", "debate_rounds": 0, "risk_debate_rounds": 0, "risk_mode": "off", "memory_on": False},
    "B": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 0, "risk_mode": "off", "memory_on": False},
    "B+": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 0, "risk_mode": "single", "memory_on": False},
    "C": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 1, "risk_mode": "debate", "memory_on": False},
    "D": {"debate_mode": "on", "debate_rounds": 1, "risk_debate_rounds": 0, "risk_mode": "single", "memory_on": True},
}


def _normalize_stage(stage: Optional[str]) -> Optional[str]:
    if not stage:
        return None
    normalized = stage.strip().upper()
    if normalized == "BPLUS":
        return "B+"
    return normalized if normalized in STAGE_PRESETS else None


def _resolve_modes(
    *,
    stage: Optional[str],
    debate_mode: str,
    debate_rounds: int,
    risk_debate_rounds: int,
    memory_on: bool,
    risk_on_legacy: Optional[bool],
    risk_mode: Optional[str],
) -> dict:
    stage_key = _normalize_stage(stage)
    if stage_key:
        preset = STAGE_PRESETS[stage_key]
        resolved_debate_mode = preset["debate_mode"]
        resolved_debate_rounds = preset["debate_rounds"]
        preset_risk_rounds = preset.get("risk_debate_rounds", 0)
        resolved_risk_debate_rounds = max(0, int(risk_debate_rounds if risk_debate_rounds is not None else preset_risk_rounds))
        resolved_risk_mode = preset["risk_mode"]
        resolved_memory_on = preset["memory_on"]

        if resolved_risk_mode != "debate":
            resolved_risk_debate_rounds = 0
        elif resolved_risk_debate_rounds < 1:
            resolved_risk_debate_rounds = max(1, int(preset_risk_rounds) or 1)

        return {
            "stage": stage_key,
            "debate_mode": resolved_debate_mode,
            "debate_rounds": resolved_debate_rounds,
            "risk_debate_rounds": resolved_risk_debate_rounds,
            "risk_mode": resolved_risk_mode,
            "memory_on": resolved_memory_on,
        }

    # Legacy compatibility: if risk_mode is absent, infer from old risk_on flag.
    resolved_risk_mode = (risk_mode or ("single" if bool(risk_on_legacy) else "off")).strip().lower()
    if resolved_risk_mode not in {"off", "single", "debate"}:
        resolved_risk_mode = "single"

    resolved_debate_mode = (debate_mode or "on").strip().lower()
    if resolved_debate_mode not in {"on", "off"}:
        resolved_debate_mode = "on"
    resolved_debate_rounds = debate_rounds if resolved_debate_mode == "on" else 0
    resolved_risk_debate_rounds = max(0, int(risk_debate_rounds or 0))
    if resolved_risk_mode != "debate":
        resolved_risk_debate_rounds = 0
    elif resolved_risk_debate_rounds < 1:
        resolved_risk_debate_rounds = 1

    return {
        "stage": None,
        "debate_mode": resolved_debate_mode,
        "debate_rounds": resolved_debate_rounds,
        "risk_debate_rounds": resolved_risk_debate_rounds,
        "risk_mode": resolved_risk_mode,
        "memory_on": bool(memory_on),
    }


def _build_initial_state(
    *,
    ticker: str,
    market: str,
    simulated_date: Optional[str],
    horizon: str,
    decision_style: str,
    resolved: dict,
    use_cached_stage_a_reports: bool = False,
    use_cached_stage_a_prior: bool = False,
    use_pro_stage_a_manager: bool = False,
    cache_trace_file: Optional[str] = None,
    cached_stage_a_trace: Optional[dict] = None,
) -> dict:
    horizon_days = HORIZON_MAP.get(horizon.lower(), 10)
    cache_lookup_key = build_stage_a_cache_key(ticker, simulated_date, horizon, market)
    reports = {}
    signals = {}
    cached_stage_a_prior = None
    if cached_stage_a_trace is not None:
        if use_cached_stage_a_reports:
            reports = extract_cached_reports(cached_stage_a_trace)
            signals = extract_cached_signals(cached_stage_a_trace)
        if use_cached_stage_a_prior:
            cached_stage_a_prior = extract_cached_stage_a_prior(cached_stage_a_trace)

    return {
        "ticker": ticker,
        "market": market,
        "run_config": {
            "stage": resolved.get("stage"),
            "simulated_date": simulated_date,
            "horizon": horizon,
            "horizon_days": horizon_days,
            "debate_rounds": resolved["debate_rounds"],
            "risk_debate_rounds": resolved["risk_debate_rounds"],
            "debate_mode": resolved["debate_mode"],
            "decision_style": (decision_style or "classification").strip().lower(),
            "memory_on": resolved["memory_on"],
            "risk_mode": resolved["risk_mode"],
            "use_cached_stage_a_reports": bool(use_cached_stage_a_reports),
            "use_cached_stage_a_prior": bool(use_cached_stage_a_prior),
            "use_pro_stage_a_manager": bool(use_pro_stage_a_manager),
            "cache_trace_file": cache_trace_file,
        },
        "simulated_date": simulated_date,
        "horizon": horizon,
        "horizon_days": horizon_days,
        "reports": reports,
        "signals": signals,
        "stock_chart_image": None,
        "sentiment_score": 0.0,
        "arguments": {},
        "trading_strategy": {},
        "trader_reports": {},
        "risk_reports": {},
        "compliance_check": {},
        "proposed_trade": {},
        "investment_plan_structured": None,
        "research_manager_recommendation": None,
        "memory_id": None,
        "memory_summary": None,
        "cache_context": {
            "cache_trace_file": cache_trace_file,
            "cache_lookup_key": cache_lookup_key,
            "cached_stage_a_trace": cached_stage_a_trace,
            "cached_stage_a_reports_used": bool(use_cached_stage_a_reports and reports),
            "cached_stage_a_prior": cached_stage_a_prior,
            "cached_stage_a_prior_used": False,
        },
        "provenance": {
            "cache": {
                "cache_trace_file": cache_trace_file,
                "cache_lookup_key": cache_lookup_key,
                "cached_stage_a_reports_used": bool(use_cached_stage_a_reports and reports),
                "cached_stage_a_prior_requested": bool(use_cached_stage_a_prior),
                "cached_stage_a_prior_used": False,
            }
        },
    }


def _load_cached_stage_a_trace_for_request(request: "AnalysisRequest") -> Optional[dict]:
    if not (request.use_cached_stage_a_reports or request.use_cached_stage_a_prior):
        return None
    if not request.cache_trace_file:
        raise HTTPException(status_code=400, detail="cache_trace_file is required when cached Stage A inputs are enabled")

    cached_row = get_cached_stage_a_trace(
        request.cache_trace_file,
        ticker=request.ticker,
        simulated_date=request.simulated_date,
        horizon=request.horizon,
        market=request.market,
    )
    if cached_row is None:
        cache_key = build_stage_a_cache_key(request.ticker, request.simulated_date, request.horizon, request.market)
        raise HTTPException(
            status_code=404,
            detail=f"No cached Stage A trace found for {cache_key} in {request.cache_trace_file}",
        )
    return cached_row

# Define the request body for the /analyze endpoint
class AnalysisRequest(BaseModel):
    ticker: str
    market: str = "US"
    simulated_date: Optional[str] = None
    horizon: str = "short"  # "short"|"medium"|"long"
    stage: Optional[str] = None  # "A"|"B"|"B+"|"C"|"D"
    debate_rounds: int = 1  # 0 | 1 | 2
    risk_debate_rounds: int = 1  # 1 | 2 (used when risk_mode=debate)
    debate_mode: str = "on"  # "on"|"off"
    decision_style: str = "classification"  # "classification"|"full"
    memory_on: bool = True
    memory_store: bool = True  # False = read-only (retrieve but don't store new memories)
    archive_run: bool = True
    risk_on: Optional[bool] = None  # legacy (deprecated): use risk_mode instead
    risk_mode: Optional[str] = None  # "off"|"single"|"debate"
    use_cached_stage_a_reports: bool = False
    use_cached_stage_a_prior: bool = False
    use_pro_stage_a_manager: bool = False
    cache_trace_file: Optional[str] = None

@app.post("/analyze")
def analyze_ticker(request: AnalysisRequest):
    """
    Runs the agent graph for a given stock ticker and returns the analysis.
    """
    import time
    start_time = time.time()

    # Reset LLM stats for this request
    reset_call_stats()
    reset_token_log()
    
    resolved = _resolve_modes(
        stage=request.stage,
        debate_mode=request.debate_mode,
        debate_rounds=request.debate_rounds,
        risk_debate_rounds=request.risk_debate_rounds,
        memory_on=request.memory_on,
        risk_on_legacy=request.risk_on,
        risk_mode=request.risk_mode,
    )
    cached_stage_a_trace = _load_cached_stage_a_trace_for_request(request)

    # Create the agent graph with configurable risk mode
    agent_graph = create_agent_graph(
        max_debate_rounds=resolved["debate_rounds"],
        max_risk_debate_rounds=resolved["risk_debate_rounds"],
        risk_mode=resolved["risk_mode"],
        debate_mode=resolved["debate_mode"],
    )

    initial_state = _build_initial_state(
        ticker=request.ticker,
        market=request.market,
        simulated_date=request.simulated_date,
        horizon=request.horizon,
        decision_style=request.decision_style,
        resolved=resolved,
        use_cached_stage_a_reports=request.use_cached_stage_a_reports,
        use_cached_stage_a_prior=request.use_cached_stage_a_prior,
        use_pro_stage_a_manager=request.use_pro_stage_a_manager,
        cache_trace_file=request.cache_trace_file,
        cached_stage_a_trace=cached_stage_a_trace,
    )

    # Invoke the graph
    print(f"Invoking the agent graph for {request.ticker}...")
    final_state = agent_graph.invoke(initial_state)

    # Record timing
    elapsed_time = time.time() - start_time
    final_state['analysis_time_seconds'] = round(elapsed_time, 2)

    # Attach LLM call stats and token log
    call_stats = get_call_stats()
    token_log = get_token_log()
    total_input = sum(e["input"] for e in token_log)
    total_output = sum(e["output"] for e in token_log)
    final_state['llm_stats'] = {
        **call_stats,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "token_log": token_log,
    }

    # Store analysis in Stage D learning memory only when enabled and store is not disabled.
    if resolved["memory_on"] and request.memory_store:
        try:
            final_state_json = json.dumps(final_state, default=str)
            memory = get_memory()
            memory_id = memory.store_analysis(
                ticker=request.ticker,
                analysis_summary=f"Analysis completed for {request.ticker}",
                bull_arguments=final_state.get('investment_debate_state', {}).get('bull_history', 'N/A'),
                bear_arguments=final_state.get('investment_debate_state', {}).get('bear_history', 'N/A'),
                final_decision=final_state.get('investment_plan', 'N/A'),
                strategy=final_state.get('trading_strategy', {}),
                metadata={
                    "market": request.market,
                    "simulated_date": request.simulated_date,
                    "horizon": request.horizon,
                    "debate_rounds": resolved["debate_rounds"],
                    "risk_debate_rounds": resolved["risk_debate_rounds"],
                    "debate_mode": resolved["debate_mode"],
                    "memory_on": resolved["memory_on"],
                    "risk_mode": resolved["risk_mode"],
                    "stage": resolved.get("stage"),
                    "analysis_time_seconds": final_state.get('analysis_time_seconds'),
                },
                final_state_json=final_state_json,
                reports=final_state.get('reports', {})
            )
            final_state['memory_id'] = memory_id
            print(f"[MEMORY] Stored analysis with ID: {memory_id}")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not store analysis: {str(e)}")

    if request.archive_run:
        try:
            archive = get_run_archive()
            archive_id = archive.store_run(
                ticker=request.ticker,
                stage=resolved.get("stage"),
                market=request.market,
                simulated_date=request.simulated_date,
                horizon=request.horizon,
                action=str((final_state.get("trading_strategy") or {}).get("action") or "HOLD"),
                rationale=str((final_state.get("trading_strategy") or {}).get("rationale") or "")[:500],
                result_json=json.dumps(final_state, default=str),
                source="analyze",
            )
            final_state["archive_id"] = archive_id
            print(f"[ARCHIVE] Stored run with ID: {archive_id}")
        except Exception as e:
            print(f"[ARCHIVE] Warning: Could not archive run: {str(e)}")
    print(f"\n--- Analysis Complete ({elapsed_time:.2f}s) | LLM calls={call_stats['total_calls']} retries={call_stats['retries']} 429s={call_stats['rate_limits_429']} tokens={total_input+total_output} ---")
    
    # Print and return the final state
    print(final_state)
    return final_state

@app.get("/analyze/stream")
async def analyze_ticker_stream(
    ticker: str,
    market: str = "US",
    simulated_date: Optional[str] = None,
    horizon: str = "short",
    stage: Optional[str] = None,
    debate_rounds: int = 1,
    risk_debate_rounds: int = 1,
    debate_mode: str = "on",
    decision_style: str = "classification",
    memory_on: bool = True,
    memory_store: bool = True,
    archive_run: bool = True,
    risk_on: Optional[bool] = None,
    risk_mode: Optional[str] = None,
    use_cached_stage_a_reports: bool = False,
    use_cached_stage_a_prior: bool = False,
    use_pro_stage_a_manager: bool = False,
    cache_trace_file: Optional[str] = None,
):
    """
    Runs the agent graph with real-time streaming updates via Server-Sent Events.
    """
    async def event_generator():
        try:
            import time
            start_time = time.time()
            reset_call_stats()
            reset_token_log()
            
            # Send initial status
            event_data = json.dumps({'status': 'started', 'message': f'Starting analysis for {ticker}...'})
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(0.1)
            
            resolved = _resolve_modes(
                stage=stage,
                debate_mode=debate_mode,
                debate_rounds=debate_rounds,
                risk_debate_rounds=risk_debate_rounds,
                memory_on=memory_on,
                risk_on_legacy=risk_on,
                risk_mode=risk_mode,
            )
            cached_stage_a_trace = None
            if use_cached_stage_a_reports or use_cached_stage_a_prior:
                cached_stage_a_trace = get_cached_stage_a_trace(
                    cache_trace_file or "",
                    ticker=ticker,
                    simulated_date=simulated_date,
                    horizon=horizon,
                    market=market,
                )
                if cached_stage_a_trace is None:
                    raise HTTPException(status_code=404, detail="Cached Stage A trace row not found")

            # Create the agent graph with configurable risk mode
            agent_graph = create_agent_graph(
                max_debate_rounds=resolved["debate_rounds"],
                max_risk_debate_rounds=resolved["risk_debate_rounds"],
                risk_mode=resolved["risk_mode"],
                debate_mode=resolved["debate_mode"],
            )

            initial_state = _build_initial_state(
                ticker=ticker,
                market=market,
                simulated_date=simulated_date,
                horizon=horizon,
                decision_style=decision_style,
                resolved=resolved,
                use_cached_stage_a_reports=use_cached_stage_a_reports,
                use_cached_stage_a_prior=use_cached_stage_a_prior,
                use_pro_stage_a_manager=use_pro_stage_a_manager,
                cache_trace_file=cache_trace_file,
                cached_stage_a_trace=cached_stage_a_trace,
            )
            
            # Stream updates for each agent
            # We use astream to get real-time updates from the graph execution
            step_count = 0
            # Define a mapping from node names to display names
            node_mapping = {
                "fundamental_analyst": "Fundamental Analyst",
                "technical_analyst": "Technical Analyst",
                "sentiment_analyst": "Sentiment Analyst",
                "news_harvester": "News Harvester",
                "bull_researcher": "Bull Researcher",
                "bear_researcher": "Bear Researcher",
                "research_manager": "Research Manager",
                "strategy_synthesizer": "Strategy Synthesizer",
                "risk_manager": "Risk Manager",
            }
            current_state = initial_state.copy()
            
            # Start stream
            async for event in agent_graph.astream(initial_state):
                for node_name, state_update in event.items():
                    # Update current_state with new keys
                    current_state.update(state_update)

                    # Hide the policy-core Trader echo step from the live UI stream.
                    if node_name == "strategy_synthesizer":
                        continue
                    
                    step_count += 1
                    display_name = node_mapping.get(node_name, node_name)
                    event_data = json.dumps({
                        'status': 'processing', 
                        'agent': display_name, 
                        'step': step_count, 
                        'total': 15 
                    })
                    yield f"data: {event_data}\n\n"
            
            final_state = current_state

            # Add analysis time and llm stats first so archived/replayed results are complete.
            elapsed_time = time.time() - start_time
            final_state['analysis_time_seconds'] = round(elapsed_time, 2)
            call_stats = get_call_stats()
            token_log = get_token_log()
            total_input = sum(e["input"] for e in token_log)
            total_output = sum(e["output"] for e in token_log)
            final_state['llm_stats'] = {
                **call_stats,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "token_log": token_log,
            }

            # Store in Stage D learning memory only when enabled and not read-only.
            if resolved["memory_on"] and memory_store:
                try:
                    final_state_json = json.dumps(final_state, default=str)

                    memory = get_memory()
                    memory_id = memory.store_analysis(
                        ticker=ticker,
                        analysis_summary=f"Analysis completed for {ticker}",
                        bull_arguments=final_state.get('investment_debate_state', {}).get('bull_history', 'N/A'),
                        bear_arguments=final_state.get('investment_debate_state', {}).get('bear_history', 'N/A'),
                        final_decision=final_state.get('investment_plan', 'N/A'),
                        strategy=final_state.get('trading_strategy', {}),
                        metadata={
                            "market": market,
                            "simulated_date": simulated_date,
                            "horizon": horizon,
                            "debate_rounds": resolved["debate_rounds"],
                            "debate_mode": resolved["debate_mode"],
                            "memory_on": resolved["memory_on"],
                            "risk_mode": resolved["risk_mode"],
                            "stage": resolved.get("stage"),
                        },
                        final_state_json=final_state_json,
                        reports=final_state.get('reports', {})
                    )
                    final_state['memory_id'] = memory_id
                except Exception as e:
                    print(f"[MEMORY] Warning: {str(e)}")

            if archive_run:
                try:
                    archive = get_run_archive()
                    archive_id = archive.store_run(
                        ticker=ticker,
                        stage=resolved.get("stage"),
                        market=market,
                        simulated_date=simulated_date,
                        horizon=horizon,
                        action=str((final_state.get("trading_strategy") or {}).get("action") or "HOLD"),
                        rationale=str((final_state.get("trading_strategy") or {}).get("rationale") or "")[:500],
                        result_json=json.dumps(final_state, default=str),
                        source="stream",
                    )
                    final_state["archive_id"] = archive_id
                except Exception as e:
                    print(f"[ARCHIVE] Warning: {str(e)}")
            
            # Send final results
            event_data = json.dumps({'status': 'complete', 'result': final_state})
            yield f"data: {event_data}\n\n"
            
        except Exception as e:
            print(f"Error in stream: {e}")
            event_data = json.dumps({'status': 'error', 'message': str(e)})
            yield f"data: {event_data}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/")
def read_root():
    return {"message": "Welcome to the NexusTrader API"}

@app.get("/api/chart/{ticker}")
def get_chart_data(ticker: str, period: str = "6mo", as_of: Optional[str] = None):
    """Return OHLCV data for frontend chart rendering."""
    try:
        data = get_chart_data_json(ticker, period=period, as_of=as_of)
        return {"status": "success", "ticker": ticker, "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Memory System Endpoints ---

@app.get("/memory/all")
def get_all_memory(limit: int = 20):
    """Get recent analyses."""
    try:
        memory = get_memory()
        history = memory.get_all_analyses(limit=limit)
        return {"status": "success", "data": history}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/runs")
def get_archived_runs(limit: int = 100):
    try:
        archive = get_run_archive()
        return {"status": "success", "data": archive.get_runs(limit=limit)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/runs")
def clear_archived_runs():
    try:
        archive = get_run_archive()
        archive.clear_all()
        return {"status": "success", "message": "Cleared archived runs"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/memory/stats")
def get_memory_stats():
    """Get memory system statistics."""
    try:
        memory = get_memory()
        stats = memory.get_statistics()
        return {"status": "success", "data": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/memory/mistakes")
def get_past_mistakes(min_loss_pct: float = -5.0, n_results: int = 5):
    """Get past analyses that resulted in losses."""
    try:
        memory = get_memory()
        mistakes = memory.get_past_mistakes(
            ticker=None,
            min_loss_pct=min_loss_pct,
            n_results=n_results
        )
        return {"status": "success", "data": mistakes}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/memory/successes")
def get_successes(min_profit_pct: float = 5.0, n_results: int = 5):
    """Get past analyses that resulted in profits."""
    try:
        memory = get_memory()
        successes = memory.get_success_patterns(
            min_profit_pct=min_profit_pct,
            n_results=n_results
        )
        return {"status": "success", "data": successes}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class OutcomeUpdate(BaseModel):
    memory_id: str
    actual_outcome: str
    profit_loss_pct: float
    lessons_learned: str

@app.post("/memory/update_outcome")
def update_analysis_outcome(update: OutcomeUpdate):
    """Update an analysis with actual trading outcome."""
    try:
        memory = get_memory()
        memory.update_outcome(
            memory_id=update.memory_id,
            actual_outcome=update.actual_outcome,
            profit_loss_pct=update.profit_loss_pct,
            lessons_learned=update.lessons_learned
        )
        return {"status": "success", "message": f"Updated outcome for {update.memory_id}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Baseline Strategy Endpoint ---
class BaselineRequest(BaseModel):
    ticker: str
    baseline: str  # 'buy_hold', 'sma', 'rsi', 'random'
    simulated_date: Optional[str] = None

@app.post("/baseline")
def run_baseline(request: BaselineRequest):
    """
    Run a non-agentic baseline strategy.
    
    Args:
        ticker: Stock ticker
        baseline: One of 'buy_hold', 'sma', 'rsi', 'random'
        simulated_date: Optional date for backtesting (YYYY-MM-DD)
    
    Returns:
        Result matching NexusTrader output schema
    """
    try:
        strategy = get_baseline(request.baseline)
        result = strategy.generate_signal(request.ticker, request.simulated_date)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

