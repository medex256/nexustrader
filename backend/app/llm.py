import os
import time
from typing import TypeVar
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Flash model — unified model for all agents
MODEL_NAME = "gemini-3-flash-preview"

# Singleton client (created on first call)
_client: genai.Client | None = None
T = TypeVar("T", bound=BaseModel)


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
    temperature: float = 1.0,
    max_retries: int = 3,
) -> str:
    """
    Invokes Gemini 3 Flash Preview.
    """
    client = _get_client()

    # Single clean config for all agents
    config = types.GenerateContentConfig(
        temperature=temperature,
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

            # Filter for response text only, ignoring the internal reasoning (thought) parts
            if response.candidates:
                text_parts = [
                    part.text for part in response.candidates[0].content.parts 
                    if part.text and not getattr(part, 'thought', False)
                ]
                if text_parts:
                    return "".join(text_parts).strip()

            if response.text:
                return response.text.strip()

            return "Error: Empty response."

        except Exception as e:
            # Basic retry logic for rate limits
            if "429" in str(e) and attempt < max_retries:
                time.sleep(10)
                continue
            return f"Error: {e}"

    return "Error: Max retries exceeded."


def invoke_llm_structured(
    prompt: str,
    schema: type[T],
    *,
    temperature: float = 0.3,
    max_retries: int = 3,
) -> T:
    """
    Invokes Gemini with native schema-constrained JSON output.

    Args:
        prompt: Prompt text
        schema: Pydantic model class for strict output validation
        temperature: Sampling temperature
        max_retries: Maximum retries for API/rate-limit issues
    Returns:
        Validated Pydantic model instance.

    Raises:
        RuntimeError when generation/validation fails after retries.
    """
    client = _get_client()

    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=schema,
    )

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=config,
            )

            text = ""
            if response.candidates:
                text_parts = [
                    part.text for part in response.candidates[0].content.parts
                    if part.text and not getattr(part, "thought", False)
                ]
                text = "".join(text_parts).strip()

            if not text and response.text:
                text = response.text.strip()

            if not text:
                raise ValueError("Empty structured response")

            return schema.model_validate_json(text)
        except Exception as e:
            last_error = e
            if "429" in str(e) and attempt < max_retries:
                time.sleep(10)
                continue
            if attempt < max_retries:
                time.sleep(2)
                continue
            break

    raise RuntimeError(f"Structured LLM call failed after retries: {last_error}")



