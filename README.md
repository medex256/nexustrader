# NexusTrader

NexusTrader is a Final Year Project multi-agent LLM trading research system. It produces transparent BUY, SELL, and HOLD recommendations through a staged pipeline designed for controlled ablation, not just demo output.

The project compares whether specialist evidence extraction, risk control, and retrieval memory improve decision quality over a minimal baseline. The main application consists of a FastAPI backend, a React and TypeScript frontend, and an experiment harness that calls the live backend for repeatable evaluation.

## What This Repository Contains

- A FastAPI backend in `backend/` that runs the stage-specific LangGraph pipeline
- A Vite React frontend in `frontend-ts/` for live interactive analysis
- An experiments package in `experiments/` for single-run debugging and batch evaluation
- Architecture, stage-design, and report documentation in `../documentation/`

The active frontend is `frontend-ts/`. The older `frontend/` folder is a legacy static or demo artifact and is not the main app.

## Stage System

NexusTrader is organized as five evaluation stages.

| Stage | Purpose | Debate | Risk Layer | Memory | Current LLM Calls |
|---|---|---|---|---|---|
| A | Baseline analyst core | Off | Off | Off | 4 |
| B | Specialist evidence extraction | On | Off | Off | 7 |
| B+ | B plus single risk judge | On | Single risk manager | Off | 8 |
| C | B plus risk committee | On | Aggressive, Conservative, Neutral, Judge | Off | 11 |
| D | B+ plus retrieval memory | On | Single risk manager | On | 8 |

Important implementation notes:

- Stage D branches from the B+ topology, not from Stage C.
- The Trader remains a policy-core execution bridge in the normal live path and is not treated as a separate reasoning layer in the frontend stage flow.
- Stage D memory is injected into the Upside Catalyst Analyst and Downside Risk Analyst prompts only.

## Current Pipeline

Shared analyst backbone:

`Fundamental Analyst -> Technical Analyst -> News Harvester`

Stage-specific routing:

- Stage A: analysts -> Research Manager -> final recommendation
- Stage B: analysts -> Upside Catalyst Analyst -> Downside Risk Analyst -> Research Manager -> final recommendation
- Stage B+: Stage B -> Risk Manager
- Stage C: Stage B -> Aggressive Risk Analyst -> Conservative Risk Analyst -> Neutral Risk Analyst -> Risk Committee Judge
- Stage D: Stage B+ plus episodic memory retrieval injected into the specialist layer

## Repository Layout

```text
nexustrader/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   ├── graph/
│   │   ├── tools/
│   │   └── utils/
│   └── pyproject.toml
├── experiments/
│   ├── inputs/
│   ├── results/
│   └── scripts/
├── frontend-ts/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── frontend/
└── README.md
```

## Backend Quick Start

Prerequisites:

- Python 3.11 or newer
- A valid `GOOGLE_API_KEY`

Install the backend:

```bash
cd nexustrader/backend
pip install -e .
```

Create a `.env` file in `backend/` if needed:

```env
GOOGLE_API_KEY=your_key_here
```

Run the API locally:

```bash
uvicorn app.main:app --reload
```

Default local backend URL:

```text
http://127.0.0.1:8000
```

## Frontend Quick Start

The current frontend is the Vite app in `frontend-ts/`.

```bash
cd nexustrader/frontend-ts
npm install
npm run dev
```

If you want the frontend to point to a hosted backend:

```bash
VITE_API_BASE_URL=https://your-backend-host npm run dev
```

The frontend expects the backend to provide:

- `GET /analyze/stream` for SSE progress updates and final results
- `GET /api/chart/{ticker}` for chart data
- `GET /runs` for archived run history

## Running Analyses

Single debug run:

```bash
cd nexustrader/experiments
python scripts/run_single.py --stage B --ticker NVDA --date 2021-12-27 --tag debug_v1
```

Batch evaluation:

```bash
cd nexustrader/experiments
python scripts/run_batch.py --stage C --tag eval_stage_c \
  --tickers-file inputs/tickers.txt \
  --dates-file inputs/dates_eval50.txt \
  --workers 20
```

Batch scripts call the live backend over HTTP. This means the experiment path and the app path use the same analysis endpoint.

## Output and Storage

Generated outputs include:

- Raw batch JSONL files under `experiments/results/raw/`
- Scored CSV summaries under `experiments/results/scored/`
- Interactive run history from the backend archive

Storage roles are intentionally split:

- SQLite archive stores completed runs for replay, review, and app history
- ChromaDB stores retrieval memory used only by Stage D

## Deployment Notes

Typical current deployment pattern:

- Backend runs as a systemd service on a Linux VM
- FastAPI is served privately on `127.0.0.1:8000`
- `nginx` serves the built frontend on port 80 and proxies API routes to the backend

Frontend production deployment is a build-and-copy workflow, not a long-running Vite process:

```bash
cd /path/to/nexustrader/frontend-ts
git pull
npm install
npm run build
```

Then copy `dist/` to the nginx web root.

Do not commit generated frontend build artifacts such as `frontend-ts/dist/`.

## Key Design Rules

- No rule-based override should replace the LLM's recommendation field in the evaluation stages.
- The stage system exists to isolate mechanism changes, not to stack arbitrary features.
- Stage D memory must obey simulated-date no-leak rules.
- The frontend should reflect the actual live topology, not outdated conceptual diagrams.

## Status Summary

The current project state is centered on:

- a deployable FastAPI backend
- an interactive TypeScript frontend
- stage-controlled ablation experiments
- transparent reasoning traces rather than black-box outputs

