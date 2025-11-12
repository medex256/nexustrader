# In nexustrader/backend/app/agents/research_team.py

from ..llm import invoke_llm as call_llm


def bull_researcher_agent(state: dict):
    """
    The Bull Researcher Agent.
    """
    reports = state['reports']
    
    # 1. Construct the prompt for the LLM
    prompt = f"""
Your mission is to build a compelling bullish argument for the stock, based on the provided analysis reports.

Analysis Reports:
{reports}

Please perform the following tasks:
1.  Review the reports from the Analyst Team.
2.  Identify all the positive factors and potential catalysts.
3.  Synthesize these factors into a coherent and persuasive bullish thesis.
4.  Address any potential weaknesses or counterarguments in a way that reinforces the bullish case.
5.  Summarize your argument in a clear and concise report.
"""
    
    # 2. Call the LLM to generate the argument
    bullish_argument = call_llm(prompt)
    
    # 3. Update the state
    if 'arguments' not in state:
        state['arguments'] = {}
    state['arguments']['bullish'] = bullish_argument
    
    return state

def bear_researcher_agent(state: dict):
    """
    The Bear Researcher Agent.
    """
    reports = state['reports']
    
    # 1. Construct the prompt for the LLM
    prompt = f"""
Your mission is to build a compelling bearish argument for the stock, based on the provided analysis reports.

Analysis Reports:
{reports}

Please perform the following tasks:
1.  Review the reports from the Analyst Team.
2.  Identify all the negative factors and potential risks.
3.  Synthesize these factors into a coherent and persuasive bearish thesis.
4.  Challenge the bullish arguments and highlight any potential weaknesses.
5.  Summarize your argument in a clear and concise report.
"""
    
    # 2. Call the LLM to generate the argument
    bearish_argument = call_llm(prompt)
    
    # 3. Update the state
    state['arguments']['bearish'] = bearish_argument
    
    return state
