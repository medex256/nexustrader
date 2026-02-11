# In nexustrader/backend/app/agents/research_team.py

from ..llm import invoke_llm as call_llm
from ..utils.memory import get_memory


def bull_researcher_agent(state: dict):
    """
    The Bull Researcher Agent - Builds bullish arguments in a debate format.
    Now enhanced with memory to learn from past analyses.
    """
    reports = state.get('reports', {})
    ticker = state.get('ticker', '')
    
    # Initialize debate state if this is the first round
    if 'investment_debate_state' not in state or state['investment_debate_state'] is None:
        state['investment_debate_state'] = {
            'history': '',
            'bull_history': '',
            'bear_history': '',
            'current_response': '',
            'current_speaker': '',
            'count': 0,
            'judge_decision': ''
        }
    
    debate_state = state['investment_debate_state']
    
    # Get the bear's previous argument (if any) to respond to
    bear_history = debate_state.get('bear_history', '')
    
    # Query memory for similar past situations (only on first round)
    memory_context = ""
    run_config = state.get("run_config", {})
    if debate_state['count'] == 0 and run_config.get("memory_on", True):
        try:
            memory = get_memory()
            
            # Build comprehensive situation description matching storage format
            # Use same structure as stored documents for better semantic matching
            situation_desc = f"""
[TICKER] {ticker}

[FUNDAMENTAL ANALYSIS]
{reports.get('fundamental_analyst', 'N/A')[:800]}

[TECHNICAL ANALYSIS]
{reports.get('technical_analyst', 'N/A')[:800]}

[SENTIMENT & NEWS]
Sentiment: {reports.get('sentiment_analyst', 'N/A')[:500]}
News: {reports.get('news_harvester', 'N/A')[:500]}
"""
            
            # Get similar past analyses
            similar = memory.get_similar_past_analyses(
                current_situation=situation_desc,
                ticker=ticker,  # Filter by same ticker for more relevant matches
                n_results=3,  # Increased to get more context
                min_similarity=0.15  # Lowered to account for ChromaDB's conservative similarity scores
            )
            
            if similar:
                memory_context = "\n\n--- LESSONS FROM PAST ANALYSES ---\n"
                for i, mem in enumerate(similar, 1):
                    outcome = mem['metadata'].get('outcome', 'PENDING')
                    pnl = mem['metadata'].get('profit_loss_pct', 'N/A')
                    lesson = mem['metadata'].get('lessons_learned', 'N/A')
                    
                    memory_context += f"""
Past Analysis {i} (Similarity: {mem['similarity']:.0%}):
- Ticker: {mem['metadata']['ticker']}
- Action: {mem['metadata']['action']}
- Outcome: {outcome} (P/L: {pnl}%)
- Lesson Learned: {lesson}
"""
                print(f"[MEMORY] Bull Researcher found {len(similar)} similar past analyses")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not query memory: {str(e)}")
            memory_context = ""
    
    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument with cross-examination prep
        prompt = f"""You are a Bull Analyst advocating for investing in {ticker}. Build a strong, evidence-based case that anticipates and pre-empts bearish counterarguments.

**CROSS-EXAMINATION RULES:**
1. Support EVERY claim with specific data (numbers, dates, sources)
2. Anticipate the Bear's likely objections (valuation concerns, risks) and address them proactively
3. Use comparative analysis (vs peers, vs historical averages) to strengthen your case
4. Prepare to defend your key claims with evidence in next round

Focus on:
- Growth catalysts and revenue opportunities (with specific metrics)
- Competitive advantages and market positioning (backed by numbers)
- Financial health and positive trends (actual data)
{f"- Learn from past analyses - what worked and what didn't" if memory_context else ""}

Analysis Reports:
{reports}
{memory_context}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Core Thesis**: The primary reason to buy (with 2-3 data points).
- **Key Catalysts**: 2-3 specific growth drivers (quantified when possible).
- **Financial Strength**: Strongest metrics supporting the case (actual numbers).
- **Pre-emptive Defense**: Acknowledge 1-2 risks but explain why they're manageable.
- **Conclusion**: Strong closing statement.

Keep response under 400 words. Start with "Bull Researcher:"."""
    else:
        # Subsequent rounds - cross-examination with direct rebuttal
        prompt = f"""You are the Bull Analyst in a debate about {ticker}. Cross-examine the Bear's arguments by directly challenging their evidence and logic.

**CROSS-EXAMINATION REQUIREMENTS:**
1. **Quote Specific Claims**: Cite 2-3 exact statements from the Bear that you're rebutting
2. **Expose Contradictions**: Point out logical flaws or inconsistencies in their argument
3. **Counter with Evidence**: Provide contradicting data (numbers, facts, sources) for each claim
4. **Attack Weak Points**: Identify and exploit the Bear's least-supported assertions
5. **No Generic Rebuttals**: Every counterpoint must reference a specific Bear claim

Analysis Reports:
{reports}

Bear's Arguments:
{bear_history}

Your Previous Points:
{debate_state.get('bull_history', '')}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Direct Rebuttals** (Label each: "Bear claimed X, but..."):
  - Quote Bear's claim → Explain the flaw → Provide counter-evidence
  - Repeat for 2-3 key claims
- **Logical Inconsistencies**: Expose contradictions in Bear's reasoning
- **Supporting Evidence**: New data that undermines Bear's thesis
- **Restate Thesis**: Why the upside still dominates despite Bear's concerns

Keep response under 400 words. Start with "Bull Researcher:"."""
    
    # 2. Call the LLM to generate the argument
    bullish_response = call_llm(prompt)
    
    # 3. Update the debate state
    debate_state['bull_history'] += f"\n\n{bullish_response}"
    debate_state['history'] += f"\n\n{bullish_response}"
    debate_state['current_response'] = bullish_response
    debate_state['current_speaker'] = "Bull Researcher"
    debate_state['count'] += 1
    
    state['investment_debate_state'] = debate_state
    
    # Also update the arguments dict for backward compatibility
    if 'arguments' not in state:
        state['arguments'] = {}
    state['arguments']['bullish'] = debate_state['bull_history']
    
    return state


def bear_researcher_agent(state: dict):
    """
    The Bear Researcher Agent - Builds bearish arguments in a debate format.
    Now enhanced with memory to learn from past mistakes.
    """
    reports = state.get('reports', {})
    ticker = state.get('ticker', '')
    debate_state = state.get('investment_debate_state', {})
    
    # Get the bull's previous argument to respond to
    bull_history = debate_state.get('bull_history', '')
    
    # Query memory for past mistakes (only on first response)
    memory_context = ""
    run_config = state.get("run_config", {})
    if debate_state['count'] == 1 and run_config.get("memory_on", True):
        try:
            memory = get_memory()
            
            # Get past mistakes to learn what risks were underestimated
            mistakes = memory.get_past_mistakes(
                ticker=None,
                min_loss_pct=-10.0,
                n_results=2
            )
            
            if mistakes:
                memory_context = "\n\n--- LESSONS FROM PAST MISTAKES ---\n"
                for i, mem in enumerate(mistakes, 1):
                    pnl = mem['metadata'].get('profit_loss_pct', 'N/A')
                    lesson = mem['metadata'].get('lessons_learned', 'N/A')
                    
                    memory_context += f"""
Past Mistake {i}:
- Ticker: {mem['metadata']['ticker']}
- Action: {mem['metadata']['action']}
- Loss: {pnl}%
- What Went Wrong: {lesson}
"""
                print(f"[MEMORY] Bear Researcher found {len(mistakes)} past mistakes to learn from")
        except Exception as e:
            print(f"[MEMORY] Warning: Could not query memory: {str(e)}")
            memory_context = ""
    
    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # First response - cross-examine bull's opening argument
        prompt = f"""You are a Bear Analyst cross-examining the bullish case for {ticker}. Systematically challenge the Bull's evidence and expose flaws in their logic.

**CROSS-EXAMINATION REQUIREMENTS:**
1. **Quote Specific Bull Claims**: Cite 2-3 exact statements from the Bull that you're challenging
2. **Expose Logical Flaws**: Point out where Bull's reasoning breaks down or contradicts itself
3. **Counter with Contradicting Evidence**: Provide specific data (numbers, dates) that refutes Bull's claims
4. **Highlight Cherry-Picking**: Identify metrics/data the Bull ignored that weaken their case
5. **No Generic Criticism**: Every challenge must reference a specific Bull assertion

Focus on:
- Negative factors, risks, and red flags (with specific evidence)
- Overvaluation or weakness indicators (actual numbers vs Bull's claims)
- Market headwinds and competitive threats (concrete examples)
{f"- Learn from past mistakes - what risks were underestimated" if memory_context else ""}

Analysis Reports:
{reports}

Bull's Argument:
{bull_history}
{memory_context}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Direct Challenges** (Label each: "Bull claimed X, but..."):
  - Quote Bull's claim → Explain the flaw → Provide counter-evidence
  - Repeat for 2-3 key claims
- **What Bull Ignored**: Metrics/risks conveniently omitted from their analysis
- **Core Thesis**: The primary reason to avoid/short (with data)
- **Valuation Reality Check**: Why the price is too high (vs Bull's optimism)
- **Key Risks**: Specific threats the Bull downplayed or missed

Keep response under 400 words. Start with "Bear Researcher:"."""
    else:
        # Subsequent rounds - cross-examination with direct counter-rebuttal
        prompt = f"""You are the Bear Analyst in a debate about {ticker}. Cross-examine the Bull's latest defense by exposing weaknesses in their rebuttals.

**CROSS-EXAMINATION REQUIREMENTS:**
1. **Quote Bull's Rebuttals**: Cite 2-3 specific defenses the Bull just made
2. **Expose Rebuttal Flaws**: Show where Bull's counterarguments fail or contradict evidence
3. **Double Down with New Evidence**: Provide fresh data that reinforces your original concerns
4. **Exploit Defensive Positions**: Identify where Bull is now defending rather than attacking
5. **No Repetition**: Don't just restate old arguments - escalate with new facts

Analysis Reports:
{reports}

Bull's Arguments:
{bull_history}

Your Previous Points:
{debate_state.get('bear_history', '')}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Counter-Rebuttals** (Label each: "Bull defended X by claiming Y, but..."):
  - Quote Bull's defense → Expose the flaw → Provide new counter-evidence
  - Repeat for 2-3 key rebuttals
- **Unanswered Questions**: Points the Bull avoided or couldn't refute
- **Risk Amplification**: Why the risks are more severe than Bull admits (new data)
- **Final Warning**: Closing statement on downside potential (with evidence)

Keep response under 400 words. Start with "Bear Researcher:"."""
    
    # 2. Call the LLM to generate the argument
    bearish_response = call_llm(prompt)
    
    # 3. Update the debate state
    debate_state['bear_history'] += f"\n\n{bearish_response}"
    debate_state['history'] += f"\n\n{bearish_response}"
    debate_state['current_response'] = bearish_response
    debate_state['current_speaker'] = "Bear Researcher"
    debate_state['count'] += 1
    
    state['investment_debate_state'] = debate_state
    
    # Also update the arguments dict for backward compatibility
    state['arguments']['bearish'] = debate_state['bear_history']
    
    return state


def research_manager_agent(state: dict):
    """
    The Research Manager Agent - Judges the debate and makes final investment recommendation.
    """
    debate_state = state.get('investment_debate_state', {})
    reports = state.get('reports', {})
    
    debate_history = debate_state.get('history', '')
    bull_arguments = debate_state.get('bull_history', '')
    bear_arguments = debate_state.get('bear_history', '')
    
    # 1. Construct the prompt for the LLM
    prompt = f"""As the portfolio manager, evaluate this debate and make a definitive decision: Buy, Sell, or Hold.

Decision rule:
- Default to BUY or SELL when there is any directional edge.
- Use HOLD only if you can name at least two specific unresolved blockers that materially prevent a directional call.
- If uncertainty is moderate, recommend a smaller / phased execution approach rather than HOLD.

Analysis Reports:
{reports}

Complete Debate:
{debate_history}

Deliverables:
1. **Executive Summary**: 1-2 sentence core conclusion.
2. **Debate Analysis**: Bullet points contrasting Bull vs Bear arguments.
3. **Recommendation**: BUY, SELL, or HOLD.
4. **Investment Plan**:
   - **Rationale**: The 'why' behind the trade.
   - **Risk Factors**: Specific catalysts to watch.
   - **Execution**: Recommended approach (e.g., "Scale in on weakness").

FORMAT: Use Markdown headers (##) and bullet points. Be structured, professional, and direct. NO conversational filler (e.g., "Alright team", "Here is my thought process")."""
    
    # 2. Call the LLM to generate the decision
    manager_decision = call_llm(prompt)
    
    # 3. Update the state
    debate_state['judge_decision'] = manager_decision
    state['investment_debate_state'] = debate_state
    state['investment_plan'] = manager_decision
    
    return state
