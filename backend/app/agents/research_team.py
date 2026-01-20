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
    if debate_state['count'] == 0:
        try:
            memory = get_memory()
            
            # Build situation description from reports
            situation_desc = f"""
Ticker: {ticker}
Fundamental Analysis: {reports.get('fundamental_analyst', 'N/A')[:500]}
Technical Analysis: {reports.get('technical_analyst', 'N/A')[:500]}
Sentiment: {reports.get('sentiment_analyst', 'N/A')[:300]}
"""
            
            # Get similar past analyses
            similar = memory.get_similar_past_analyses(
                current_situation=situation_desc,
                ticker=None,  # Don't filter by ticker - learn from all stocks
                n_results=2,
                min_similarity=0.3
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
        # First round - opening argument
        prompt = f"""You are a Bull Analyst advocating for investing in {ticker}. Build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive indicators.

Focus on:
- Growth catalysts and revenue opportunities
- Competitive advantages and market positioning
- Financial health and positive trends
{f"- Learn from past analyses - what worked and what didn't" if memory_context else ""}

Analysis Reports:
{reports}
{memory_context}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Core Thesis**: The primary reason to buy.
- **Key Catalysts**: 2-3 specific growth drivers.
- **Financial Strength**: Strongest metrics supporting the case.
- **Conclusion**: Strong closing statement.

Keep response under 400 words. Start with "Bull Researcher:"."""
    else:
        # Subsequent rounds - respond to bear's counterarguments
        prompt = f"""You are the Bull Analyst in a debate about {ticker}.

Analysis Reports:
{reports}

Bear's Arguments:
{bear_history}

Your Previous Points:
{debate_state.get('bull_history', '')}

Counter the bear's concerns with specific data and sound reasoning.

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Rebuttal**: Directly address the Bear's key flaws.
- **Supporting Evidence**: Data backing your defense.
- **Restate Thesis**: Reinforce why the upside outweighs the risk.

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
    if debate_state['count'] == 1:
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
        # First response to bull's opening argument
        prompt = f"""You are a Bear Analyst presenting the bearish case for {ticker}. Challenge overly optimistic views with facts and analysis.

Focus on:
- Negative factors, risks, and red flags
- Overvaluation or weakness indicators
- Market headwinds and competitive threats
{f"- Learn from past mistakes - what risks were underestimated" if memory_context else ""}

Analysis Reports:
{reports}

Bull's Argument:
{bull_history}
{memory_context}

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Core Thesis**: The primary reason to avoid/short.
- **Valuation Concerns**: Why the price is too high.
- **Key Risks**: Specific threats (competition, macro, regulation).
- **Rebuttal**: Direct challenges to the Bull's points.

Keep response under 400 words. Start with "Bear Researcher:"."""
    else:
        # Subsequent rounds - continue the debate
        prompt = f"""You are the Bear Analyst in a debate about {ticker}.

Analysis Reports:
{reports}

Bull's Arguments:
{bull_history}

Your Previous Points:
{debate_state.get('bear_history', '')}

Counter the bull's optimistic claims with factual analysis. Highlight risks they're overlooking.

FORMAT: Use Markdown headers and bullet points.
Structure:
- **Counter-Rebuttal**: Address the Bull's defense.
- **Risk Amplification**: Why the risks are severe.
- **Final Warning**: Closing statement on downside potential.

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
