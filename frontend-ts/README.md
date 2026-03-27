# NexusTrader TypeScript Frontend (Vite)

This is the TypeScript migration of the live demo frontend, built with Vite and Lightweight Charts.

## Features
- SSE-driven agent progress updates
- Interactive candlestick chart (TradingView Lightweight Charts)
- Structured results panel for strategy + reports

## Requirements
- Node.js 18+ recommended
- Backend running on http://127.0.0.1:8000, or set `VITE_API_BASE_URL` for a hosted backend

## Run
```powershell
cd nexustrader\frontend-ts
npm install
npm run dev
```

To target a hosted backend during local dev or deployment, set:

```powershell
$env:VITE_API_BASE_URL="https://your-backend.onrender.com"
```

Then open:
```
http://localhost:5173
```

## API Endpoints Used
- `GET /analyze/stream?ticker=TSLA` (SSE)
- `GET /analyze/stream?ticker=TSLA&simulated_date=2024-01-03&horizon=medium` (historical + horizon)
- `GET /api/chart/TSLA?period=6mo&as_of=2024-01-03` (OHLCV JSON as-of a date)

## Notes
- The React app reads the backend URL from `VITE_API_BASE_URL` and falls back to `http://127.0.0.1:8000`.
- The UI expects the backend to stream agent status events before final results.
