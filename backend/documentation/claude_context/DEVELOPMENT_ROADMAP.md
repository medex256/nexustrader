# NexusTrader Development Roadmap - November 12, 2025

## 🎯 Current Status: Week 14 (Debate Mechanism Complete ✅)

**Progress:** ~45% Complete | **Timeline:** On Track

---

## ✅ **What's Done (Weeks 1-14)**

### Core Architecture (Week 8-13)
- [x] 12 agent personas designed
- [x] System architecture documented
- [x] End-to-end scaffolding built
- [x] Google Gemini LLM integration
- [x] Basic tool implementations
- [x] FastAPI backend structure

### Major Breakthrough (Week 14) - TODAY!
- [x] **Debate State System** - Multi-round debate tracking
- [x] **Conditional Routing** - Dynamic graph flow
- [x] **Research Manager Agent** - Judge & final decision maker
- [x] **Multi-Round Debates** - Bull ↔️ Bear arguments
- [x] **Performance Infrastructure** - Caching system ready
- [x] **Caching Applied** - Tools now cached (30min-1hr TTL)

---

## 📋 **Immediate Next Steps (Week 15 - This Week)**

### Step 1: Complete Performance Optimization (2-3 hours) ⚡
**Priority:** HIGH - Reduces execution time 40-50%

**Tasks:**
1. ✅ Apply caching to all tools (DONE)
2. [ ] Implement shared context in agents
   - Update `sentiment_analyst_agent` to store social data
   - Update `bull_trader_agent` to retrieve cached data
   - Update `news_harvester_agent` to share news data
3. [ ] Test and measure improvements
   - Run `test_debate_mechanism.py` twice
   - First run: normal
   - Second run: should show "[CACHE HIT]" messages
   - Verify no duplicate Twitter/Reddit calls

**Expected Results:**
- Execution time: 5 min → 2-3 min
- Duplicate calls: eliminated
- API costs: reduced 60%

---

### Step 2: Memory System with ChromaDB (3-4 days) 🧠
**Priority:** HIGH - Core innovation feature

**Why:** Agents need to learn from past mistakes

**Tasks:**

#### Day 1: Setup ChromaDB
```python
# Install
uv pip install chromadb

# Create memory class
class FinancialSituationMemory:
    def __init__(self, name, config):
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(name)
    
    def store(self, situation, recommendation, outcome, reflection):
        # Store analysis + outcome + lessons learned
        pass
    
    def query(self, current_situation, n_matches=3):
        # Find similar past situations
        pass
```

#### Day 2: Integrate into Agents
- Add memory queries to Bull/Bear researchers
- Add memory to Research Manager
- Add "past mistakes" to prompts

#### Day 3-4: Reflection Mechanism
- Create `reflect_and_remember()` method
- After analysis, compare predicted vs. actual
- Store "what went wrong" reflections
- Test with historical data

**Expected Results:**
- Agents reference past similar analyses
- Prompts include "Last time with NVDA, I was too bullish..."
- Recommendations improve over time

---

### Step 3: Convert Tools to LangChain Format (2-3 days) 🔧
**Priority:** MEDIUM - Better tool management

**Why:** LangGraph needs proper tool integration

**Tasks:**

#### Current Format (Direct Call):
```python
def get_stock_price(ticker):
    return yf.Ticker(ticker).info
```

#### Target Format (LangChain Tool):
```python
from langchain_core.tools import tool

@tool
def get_stock_price(ticker: str) -> dict:
    """Get current stock price and info."""
    return yf.Ticker(ticker).info
```

**What to convert:**
1. All financial data tools
2. All social media tools
3. All news tools
4. All technical analysis tools

**Then update agents:**
- Remove direct tool calls
- Use tool binding with LLM
- Let LangGraph execute tools automatically

---

## 📅 **Phase 2: Data Quality (Week 16-18)**

### Week 16: Replace Placeholder Logic
**Tasks:**
1. **Strategy Synthesizer**
   - Use LLM JSON mode for structured output
   - Parse BUY/SELL/HOLD with prices
   - Add error handling for parse failures

2. **Risk Calculations**
   - Implement real VaR formula
   - Calculate position sizing (Kelly Criterion)
   - Add volatility-based stop losses

3. **Compliance Checks**
   - Pattern day trading rules
   - Margin requirements
   - Position concentration limits

**Estimated:** 4-5 days

---

### Week 17-18: Hong Kong Market Integration 🇭🇰
**Why:** Your FYP emphasizes HK market specialization

**Tasks:**
1. **Ticker Support**
   - Add `.HK` suffix handling
   - Map HK tickers to data sources
   - Handle HKT timezone

2. **Local News Sources**
   - Integrate SCMP API
   - Add HK Economic Times scraper
   - Add Hong Kong Business News

3. **Sentiment Analysis**
   - Add Cantonese text support
   - Use translation API if needed
   - HK-specific social platforms

4. **Market Data**
   - HKEX trading hours
   - HKD currency handling
   - Hang Seng Index correlation

**Estimated:** 3-4 days

---

## 📅 **Phase 3: Async & Scalability (Week 19-20)**

### Week 19: Celery Task Queue
**Why:** Long analyses shouldn't block FastAPI

**Tasks:**
1. **Setup Redis**
   ```bash
   # Install Redis
   # Windows: Use WSL or Docker
   docker run -d -p 6379:6379 redis
   ```

2. **Create Celery App**
   ```python
   from celery import Celery
   
   celery_app = Celery(
       'nexustrader',
       broker='redis://localhost:6379/0',
       backend='redis://localhost:6379/0'
   )
   
   @celery_app.task
   def run_analysis(ticker, market):
       # Run graph asynchronously
       pass
   ```

3. **Update API Endpoints**
   - `POST /analyze` → returns `task_id`
   - `GET /status/{task_id}` → returns progress
   - `GET /result/{task_id}` → returns final analysis

**Estimated:** 2-3 days

---

### Week 20: Caching & Performance Part 2
**Tasks:**
1. Redis-backed cache (persistent across runs)
2. Request deduplication (if same ticker analyzed twice)
3. Partial result streaming (via WebSockets)

**Estimated:** 2 days

---

## 📅 **Phase 4: Frontend (Week 21-23)**

### Week 21: React Foundation
**Tasks:**
1. Initialize Vite + React + TypeScript
2. Set up routing (/, /analyze/:ticker, /history)
3. Create API client with axios
4. Add TailwindCSS styling
5. Create basic layout (header, sidebar, main)

**Estimated:** 3-4 days

---

### Week 22: Visualization Components
**Tasks:**
1. **Analysis Results Page**
   - Display agent reports in cards
   - Show debate transcript in chat UI
   - Render stock chart inline
   - Strategy summary panel

2. **Progress Tracking**
   - Show "Agent X is analyzing..." status
   - Progress bar (X/12 agents complete)
   - Real-time updates via polling or WebSocket

3. **History View**
   - List past analyses
   - Compare predictions vs. outcomes
   - Show P&L if trades executed

**Estimated:** 4-5 days

---

### Week 23: Real-Time Updates (Optional)
**Tasks:**
1. WebSocket or Server-Sent Events
2. Stream agent outputs as they complete
3. Live debate transcript display

**Estimated:** 2 days

---

## 📅 **Phase 5: Testing & Validation (Week 24-25)**

### Week 24: Backtesting Framework
**Tasks:**
1. Historical simulation loop
2. Virtual portfolio tracking
3. Calculate metrics (Sharpe, max drawdown, win rate)
4. Compare vs. buy-and-hold baseline

**Estimated:** 3-4 days

---

### Week 25: Unit & Integration Tests
**Tasks:**
1. pytest tests for all tools
2. Graph execution tests with mock data
3. API endpoint tests
4. Debate termination edge cases

**Target:** 80%+ code coverage

**Estimated:** 3 days

---

## 📅 **Phase 6: Final Report & Demo (Week 26)**

### Tasks:
1. Write methodology section
2. Document architecture with diagrams
3. Include backtest results
4. Add UI screenshots
5. Discuss limitations & future work
6. Create demo video
7. Prepare presentation slides

---

## 🎯 **Quick Wins to Do Next**

### Option A: Test Performance (5 minutes)
```bash
# Run twice and compare
python test_debate_mechanism.py  # First run
python test_debate_mechanism.py  # Second run - should be faster
```

### Option B: Apply Shared Context (30 minutes)
See `PERFORMANCE_OPTIMIZATION.md` for detailed instructions.

### Option C: Start Memory System (Today)
```bash
uv pip install chromadb
# Create app/utils/memory.py
# Start implementing FinancialSituationMemory
```

---

## 📊 **Project Metrics**

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Core agents | 12 | 12 | ✅ 100% |
| Debate mechanism | Working | Working | ✅ 100% |
| Tools implemented | 20+ | 15 | 🟡 75% |
| Caching | Applied | Applied | ✅ 100% |
| Memory system | Ready | Not started | 🔴 0% |
| Frontend | Complete | Not started | 🔴 0% |
| Backtesting | Working | Not started | 🔴 0% |
| **Overall Progress** | **100%** | **~45%** | **🟢 On Track** |

---

## 🚀 **Recommended Focus This Week (Week 15)**

1. ✅ Test caching improvements (5 min)
2. [ ] Apply shared context (30 min)
3. [ ] Start memory system (3 days)
4. [ ] Begin tool conversion (1 day)

**By end of week:** Memory system working, performance optimized, ready for Phase 2.

---

## 📝 **For Your Supervisor Meeting**

**Show:**
1. Debate mechanism working (4 rounds)
2. Conditional routing implemented
3. Research Manager making decisions
4. Performance optimizations applied
5. Clear roadmap for next 12 weeks

**Ask:**
1. Priority: HK market vs. US market first?
2. Feedback on debate depth (3 rounds sufficient?)
3. Frontend requirements (features needed?)

---

**Next Update:** After Week 15 (Memory System Complete)
