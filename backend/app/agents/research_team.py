# In nexustrader/backend/app/agents/research_team.py

from ..llm import invoke_llm as call_llm


def bull_researcher_agent(state: dict):
    """
    The Bull Researcher Agent - Builds bullish arguments in a debate format.
    """
    reports = state.get('reports', {})
    
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
    
    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 0:
        # First round - opening argument
        prompt = f"""You are the Bull Researcher. Your role is to build a compelling bullish case for this stock.

Analysis Reports from the Analyst Team:
{reports}

Please perform the following tasks:
1. Review the reports from the Analyst Team.
2. Identify all the positive factors, growth catalysts, and upside potential.
3. Synthesize these factors into a coherent and persuasive bullish thesis.
4. Present your opening argument clearly and convincingly.

Start your response with "Bull Researcher:" and provide your bullish argument."""
    else:
        # Subsequent rounds - respond to bear's counterarguments
        prompt = f"""You are the Bull Researcher in a debate about this stock's investment potential.

Analysis Reports:
{reports}

Bear Researcher's Previous Arguments:
{bear_history}

Your Previous Arguments:
{debate_state.get('bull_history', '')}

Please respond to the Bear Researcher's points:
1. Address their concerns with factual counterarguments.
2. Reinforce your bullish thesis with additional evidence.
3. Highlight why the positive factors outweigh the risks.
4. Be persuasive but professional.

Start your response with "Bull Researcher:" and provide your rebuttal."""
    
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
    """
    reports = state.get('reports', {})
    debate_state = state.get('investment_debate_state', {})
    
    # Get the bull's previous argument to respond to
    bull_history = debate_state.get('bull_history', '')
    
    # 1. Construct the prompt for the LLM
    if debate_state['count'] == 1:
        # First response to bull's opening argument
        prompt = f"""You are the Bear Researcher. Your role is to present the bearish case and challenge overly optimistic views.

Analysis Reports from the Analyst Team:
{reports}

Bull Researcher's Opening Argument:
{bull_history}

Please perform the following tasks:
1. Review the reports from the Analyst Team.
2. Identify all the negative factors, risks, and red flags.
3. Challenge the Bull Researcher's arguments with facts and analysis.
4. Present your bearish thesis clearly and convincingly.

Start your response with "Bear Researcher:" and provide your bearish counterargument."""
    else:
        # Subsequent rounds - continue the debate
        prompt = f"""You are the Bear Researcher in an ongoing debate about this stock's investment potential.

Analysis Reports:
{reports}

Bull Researcher's Arguments:
{bull_history}

Your Previous Arguments:
{debate_state.get('bear_history', '')}

Please respond to the Bull Researcher's latest points:
1. Counter their optimistic claims with factual analysis.
2. Reinforce your bearish thesis with additional evidence.
3. Highlight risks they may be overlooking.
4. Be critical but professional.

Start your response with "Bear Researcher:" and provide your rebuttal."""
    
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
    prompt = f"""You are the Research Manager and Portfolio Strategist. Your role is to evaluate the debate between the Bull and Bear researchers and make a definitive investment recommendation.

Original Analysis Reports:
{reports}

Complete Debate Transcript:
{debate_history}

Please perform the following tasks:
1. Summarize the key points from both the bullish and bearish sides.
2. Weigh the strength of evidence on each side.
3. Make a clear recommendation: BUY, SELL, or HOLD.
4. If recommending BUY or SELL, provide specific reasoning.
5. Develop a detailed investment plan including:
   - Your recommendation (BUY/SELL/HOLD)
   - Key rationale (most compelling arguments)
   - Risk factors to monitor
   - Suggested entry/exit strategy
6. Be decisive - avoid defaulting to HOLD without strong justification.

Provide your analysis and investment plan in a clear, actionable format."""
    
    # 2. Call the LLM to generate the decision
    manager_decision = call_llm(prompt)
    
    # 3. Update the state
    debate_state['judge_decision'] = manager_decision
    state['investment_debate_state'] = debate_state
    state['investment_plan'] = manager_decision
    
    return state
