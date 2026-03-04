# In nexustrader/backend/app/main.py
import os
import json
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .graph.agent_graph import create_agent_graph
from .utils.memory import initialize_memory, get_memory
from .tools.technical_analysis_tools import get_chart_data_json
from .baselines.strategies import get_baseline

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
    print("[STARTUP] Initializing memory system...")
    initialize_memory(persist_directory="./chroma_db")
    print("[STARTUP] Memory system ready!")

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
    "A": {"debate_mode": "off", "debate_rounds": 0, "risk_mode": "off", "memory_on": False},
    "B": {"debate_mode": "on", "debate_rounds": 1, "risk_mode": "off", "memory_on": False},
    "B+": {"debate_mode": "on", "debate_rounds": 1, "risk_mode": "single", "memory_on": False},
    "C": {"debate_mode": "on", "debate_rounds": 1, "risk_mode": "debate", "memory_on": False},
    "D": {"debate_mode": "on", "debate_rounds": 1, "risk_mode": "debate", "memory_on": True},
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
    memory_on: bool,
    risk_on_legacy: Optional[bool],
    risk_mode: Optional[str],
) -> dict:
    stage_key = _normalize_stage(stage)
    if stage_key:
        preset = STAGE_PRESETS[stage_key]
        resolved_debate_mode = preset["debate_mode"]
        resolved_debate_rounds = preset["debate_rounds"]
        resolved_risk_mode = preset["risk_mode"]
        resolved_memory_on = preset["memory_on"]
        return {
            "stage": stage_key,
            "debate_mode": resolved_debate_mode,
            "debate_rounds": resolved_debate_rounds,
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

    return {
        "stage": None,
        "debate_mode": resolved_debate_mode,
        "debate_rounds": resolved_debate_rounds,
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
) -> dict:
    horizon_days = HORIZON_MAP.get(horizon.lower(), 10)
    return {
        "ticker": ticker,
        "market": market,
        "run_config": {
            "stage": resolved.get("stage"),
            "simulated_date": simulated_date,
            "horizon": horizon,
            "horizon_days": horizon_days,
            "debate_rounds": resolved["debate_rounds"],
            "debate_mode": resolved["debate_mode"],
            "decision_style": (decision_style or "classification").strip().lower(),
            "memory_on": resolved["memory_on"],
            "risk_mode": resolved["risk_mode"],
        },
        "simulated_date": simulated_date,
        "horizon": horizon,
        "horizon_days": horizon_days,
        "reports": {},
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
    }

# Define the request body for the /analyze endpoint
class AnalysisRequest(BaseModel):
    ticker: str
    market: str = "US"
    simulated_date: Optional[str] = None
    horizon: str = "short"  # "short"|"medium"|"long"
    stage: Optional[str] = None  # "A"|"B"|"B+"|"C"|"D"
    debate_rounds: int = 1  # 0 | 1 | 2
    debate_mode: str = "on"  # "on"|"off"
    decision_style: str = "classification"  # "classification"|"full"
    memory_on: bool = True
    risk_on: Optional[bool] = None  # legacy (deprecated): use risk_mode instead
    risk_mode: Optional[str] = None  # "off"|"single"|"debate"

@app.post("/analyze")
def analyze_ticker(request: AnalysisRequest):
    """
    Runs the agent graph for a given stock ticker and returns the analysis.
    """
    import time
    start_time = time.time()
    
    resolved = _resolve_modes(
        stage=request.stage,
        debate_mode=request.debate_mode,
        debate_rounds=request.debate_rounds,
        memory_on=request.memory_on,
        risk_on_legacy=request.risk_on,
        risk_mode=request.risk_mode,
    )

    # Create the agent graph with configurable risk mode
    agent_graph = create_agent_graph(
        max_debate_rounds=resolved["debate_rounds"],
        max_risk_debate_rounds=1,  # 1 round = 3 exchanges (aggressive/conservative/neutral)
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
    )

    # Invoke the graph
    print(f"Invoking the agent graph for {request.ticker}...")
    final_state = agent_graph.invoke(initial_state)

    # Store analysis in memory for future learning (only when memory is enabled)
    if resolved["memory_on"]:
        try:
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
                    "debate_mode": resolved["debate_mode"],
                    "memory_on": resolved["memory_on"],
                    "risk_mode": resolved["risk_mode"],
                    "analysis_time_seconds": final_state.get('analysis_time_seconds'),
                },
                reports=final_state.get('reports', {})
            )
            final_state['memory_id'] = memory_id
            print(f"[MEMORY] Stored analysis with ID: {memory_id}")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not store analysis: {str(e)}")

    # Record timing
    elapsed_time = time.time() - start_time
    final_state['analysis_time_seconds'] = round(elapsed_time, 2)
    print(f"\n--- Analysis Complete ({elapsed_time:.2f}s) ---")
    
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
    debate_mode: str = "on",
    decision_style: str = "classification",
    memory_on: bool = True,
    risk_on: Optional[bool] = None,
    risk_mode: Optional[str] = None,
):
    """
    Runs the agent graph with real-time streaming updates via Server-Sent Events.
    """
    async def event_generator():
        try:
            import time
            start_time = time.time()
            
            # Send initial status
            event_data = json.dumps({'status': 'started', 'message': f'Starting analysis for {ticker}...'})
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(0.1)
            
            resolved = _resolve_modes(
                stage=stage,
                debate_mode=debate_mode,
                debate_rounds=debate_rounds,
                memory_on=memory_on,
                risk_on_legacy=risk_on,
                risk_mode=risk_mode,
            )

            # Create the agent graph with configurable risk mode
            agent_graph = create_agent_graph(
                max_debate_rounds=resolved["debate_rounds"],
                max_risk_debate_rounds=1,  # 1 round = 3 exchanges (aggressive/conservative/neutral)
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
            
            # Use accumulated state to track the full context as agents update it
            current_state = initial_state.copy()
            
            # Start stream
            async for event in agent_graph.astream(initial_state):
                for node_name, state_update in event.items():
                    # Update current_state with new keys
                    current_state.update(state_update)
                    
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

            # Store in memory (only when memory is enabled)
            if resolved["memory_on"]:
                try:
                    # Create a clean version of state for storage (remove non-serializable objects if any)
                    # But here everything is dict/str, so json.dumps works.
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
                        },
                        final_state_json=final_state_json,
                        reports=final_state.get('reports', {})
                    )
                    final_state['memory_id'] = memory_id
                except Exception as e:
                    print(f"[MEMORY] Warning: {str(e)}")
            
            # Add analysis time
            elapsed_time = time.time() - start_time
            final_state['analysis_time_seconds'] = round(elapsed_time, 2)
            
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

