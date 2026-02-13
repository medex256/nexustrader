import os
import re
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()

# ── Two-tier thinking levels ─────────────────────────────────────────────
# Gemini 3 Flash supports: minimal | low | medium | high
#   "low"  → fast analysts / signal extraction  (~quick_think)
#   "high" → judges / complex reasoning          (~deep_think)
DEFAULT_THINKING_LEVEL = "low"

# Model name
MODEL_NAME = "gemini-3-flash-preview"

# Singleton client (created on first call)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazily create and return a singleton genai Client."""
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY not found in environment variables.")
        _client = genai.Client(api_key=api_key)
    return _client


def invoke_llm(
    prompt: str,
    *,
    thinking_level: str = DEFAULT_THINKING_LEVEL,
    temperature: float = 1.0,
    max_retries: int = 3,
) -> str:
    """
    Invokes Gemini 3 Flash with two-tier thinking.

    Args:
        prompt: The prompt to send to the language model.
        thinking_level: "minimal" | "low" | "medium" | "high"
                        Use "high" for judges (Research Manager, Risk Manager).
                        Use "low" for analysts, researchers, signal extraction.
        temperature: Sampling temperature (default 1.0).
        max_retries: Maximum number of retry attempts for rate limits.

    Returns:
        The model's response text.
    """
    client = _get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
        thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

            # Extract text (skip thought-summary parts)
            if response.text:
                return response.text

            # Fallback: iterate parts for non-thought text
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'thought') and part.thought:
                        continue  # skip thought summaries
                    if part.text:
                        return part.text

            print(f"Warning: Response has no valid text. Candidates: {response.candidates}")
            return "Error: The model returned an empty response. Please try again."

        except Exception as e:
            error_msg = str(e)

            # Rate-limit handling
            if "429" in error_msg or "Quota exceeded" in error_msg or "rate" in error_msg.lower():
                if attempt < max_retries:
                    wait_time = 10
                    match = re.search(r'retry in (\d+\.?\d*)s', error_msg)
                    if match:
                        wait_time = float(match.group(1)) + 1
                    print(f"[RATE LIMIT] Attempt {attempt + 1}/{max_retries + 1} failed. Waiting {wait_time:.0f}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[RATE LIMIT] Max retries reached. Error: {e}")
                    return f"Error: Rate limit exceeded after {max_retries} retries."
            else:
                print(f"An error occurred while calling the LLM: {e}")
                return f"Error: Could not get a response from the LLM. Details: {e}"

    return "Error: Max retries exceeded."


# ── Convenience aliases ──────────────────────────────────────────────────

def invoke_llm_deep(prompt: str, **kwargs) -> str:
    """Invoke LLM with high thinking — for judges / complex reasoning."""
    return invoke_llm(prompt, thinking_level="high", **kwargs)


def invoke_llm_quick(prompt: str, **kwargs) -> str:
    """Invoke LLM with low thinking — for analysts / signal extraction."""
    return invoke_llm(prompt, thinking_level="low", **kwargs)
