import os
import time
from typing import TypeVar
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
import requests

# Load environment variables
load_dotenv()

# Flash model — default model for all agents
MODEL_NAME = "gemini-3-flash-preview"
PRO_MODEL_NAME = "gemini-3.1-pro-preview"

# Singleton client (created on first call)
_client: genai.Client | None = None
T = TypeVar("T", bound=BaseModel)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _use_vertex_mode() -> bool:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider:
        return provider in {"vertex", "vertex_ai", "vertexai"}
    # Backward-compatible boolean switch.
    return _env_flag("GOOGLE_GENAI_USE_VERTEXAI", default=False)


def _provider_mode() -> str:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider in {"vertex_api_key", "vertex-key", "vertex_key"}:
        return "vertex_api_key"
    if _use_vertex_mode():
        return "vertex"
    return "gemini_api"


def _invoke_vertex_api_key(
    prompt: str,
    *,
    model: str,
    temperature: float,
    max_retries: int,
    response_mime_type: str | None = None,
    response_schema: dict | None = None,
) -> str:
    api_key = os.getenv("GOOGLE_VERTEX_API_KEY") or os.getenv("VERTEX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Vertex API key mode requires GOOGLE_VERTEX_API_KEY (or VERTEX_API_KEY)."
        )

    url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent?key={api_key}"

    generation_config: dict = {
        "temperature": temperature,
    }
    if response_mime_type:
        generation_config["responseMimeType"] = response_mime_type
    if response_schema:
        generation_config["responseSchema"] = response_schema

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": generation_config,
    }

    last_error: str | None = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=90)
            if response.status_code == 429 and attempt < max_retries:
                time.sleep(10)
                continue

            if not response.ok:
                last_error = f"HTTP {response.status_code}: {response.text}"
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                break

            data = response.json()
            candidates = data.get("candidates") or []
            if candidates:
                parts = ((candidates[0].get("content") or {}).get("parts") or [])
                text = "".join(p.get("text", "") for p in parts if p.get("text"))
                if text:
                    return text.strip()

            raise ValueError("Empty response text from Vertex API")
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                time.sleep(2)
                continue
            break

    raise RuntimeError(f"Vertex API key call failed after retries: {last_error}")


def _get_client() -> genai.Client:
    """Lazily create and return a singleton genai Client."""
    global _client
    if _client is None:
        mode = _provider_mode()
        if mode == "vertex":
            project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT")
            location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION") or "us-central1"
            if not project:
                raise RuntimeError(
                    "Vertex mode requires GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT) in environment variables."
                )
            _client = genai.Client(vertexai=True, project=project, location=location)
        elif mode == "gemini_api":
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GOOGLE_API_KEY / GEMINI_API_KEY not found in environment variables.")
            _client = genai.Client(api_key=api_key)
        else:
            # Vertex API key mode uses direct REST calls in invoke_* functions.
            raise RuntimeError("_get_client is not used when LLM_PROVIDER=vertex_api_key.")
    return _client


def invoke_llm(
    prompt: str,
    *,
    model_name: str | None = None,
    temperature: float = 1.0,
    max_retries: int = 3,
) -> str:
    """
    Invokes Gemini 3 Flash Preview.
    """
    model = model_name or MODEL_NAME
    mode = _provider_mode()

    if mode == "vertex_api_key":
        try:
            return _invoke_vertex_api_key(
                prompt,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
            )
        except Exception as e:
            return f"Error: {e}"

    client = _get_client()

    # Single clean config for all agents
    config = types.GenerateContentConfig(
        temperature=temperature,
    )

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
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
    model_name: str | None = None,
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
    model = model_name or MODEL_NAME
    mode = _provider_mode()

    if mode == "vertex_api_key":
        schema_json = schema.model_json_schema()
        try:
            text = _invoke_vertex_api_key(
                prompt,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
                response_mime_type="application/json",
                response_schema=schema_json,
            )
            return schema.model_validate_json(text)
        except Exception as e:
            raise RuntimeError(f"Structured LLM call failed after retries: {e}")

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
                model=model,
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



