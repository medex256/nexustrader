# In nexustrader/backend/app/main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .graph.agent_graph import create_agent_graph
from .utils.memory import initialize_memory, get_memory

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

# Mount the charts directory to serve static files under the /static/charts URL
app.mount("/static/charts", StaticFiles(directory=charts_directory), name="charts")


# Define the request body for the /analyze endpoint
class AnalysisRequest(BaseModel):
    ticker: str
    market: str = "US"

@app.post("/analyze")
def analyze_ticker(request: AnalysisRequest):
    """
    Runs the agent graph for a given stock ticker and returns the analysis.
    """
    # Create the agent graph
    agent_graph = create_agent_graph()

    # Define the initial state from the request
    initial_state = {
        "ticker": request.ticker,
        "market": request.market,
        "reports": {},
        "stock_chart_image": None,
        "sentiment_score": 0.0,
        "arguments": {},
        "trading_strategy": {},
        "trader_reports": {},
        "risk_reports": {},
        "compliance_check": {},
        "proposed_trade": {},
    }

    # Invoke the graph
    print(f"Invoking the agent graph for {request.ticker}...")
    final_state = agent_graph.invoke(initial_state)

    # Store analysis in memory for future learning
    try:
        memory = get_memory()
        memory_id = memory.store_analysis(
            ticker=request.ticker,
            analysis_summary=f"Analysis completed for {request.ticker}",
            bull_arguments=final_state.get('investment_debate_state', {}).get('bull_history', 'N/A'),
            bear_arguments=final_state.get('investment_debate_state', {}).get('bear_history', 'N/A'),
            final_decision=final_state.get('investment_plan', 'N/A'),
            strategy=final_state.get('trading_strategy', {}),
            metadata={"market": request.market}
        )
        final_state['memory_id'] = memory_id
        print(f"[MEMORY] Stored analysis with ID: {memory_id}")
    except Exception as e:
        print(f"[MEMORY] Warning: Could not store analysis: {str(e)}")

    # Print and return the final state
    print("\n--- Analysis Complete ---")
    print(final_state)
    return final_state

@app.get("/")
def read_root():
    return {"message": "Welcome to the NexusTrader API"}

# --- Memory System Endpoints ---

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
