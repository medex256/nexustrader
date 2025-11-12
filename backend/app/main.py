# In nexustrader/backend/app/main.py
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .graph.agent_graph import create_agent_graph

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

    # Print and return the final state
    print("\n--- Analysis Complete ---")
    print(final_state)
    return final_state

@app.get("/")
def read_root():
    return {"message": "Welcome to the NexusTrader API"}
