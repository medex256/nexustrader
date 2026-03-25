import os
import random
import re
import time
import logging
from typing import TypeVar
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
import requests
import threading

# Load environment variables
BACKEND_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(BACKEND_ENV_PATH, override=True)

# Flash model — default model for all agents
MODEL_NAME = "gemini-3-flash-preview"
PRO_MODEL_NAME = "gemini-3.1-pro-preview"

# Singleton client (created on first call)
_client: genai.Client | None = None
T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)

# Global token tracking (for debugging)
_token_log: list[dict] = []

# Global LLM call stats (total calls, retries, 429s)
_call_stats: dict = {"total_calls": 0, "retries": 0, "rate_limits_429": 0}

# Concurrency limiter — caps simultaneous in-flight API calls across all workers.
# Semaphore is acquired per-attempt and released before backoff sleep,
# so stalled retries don't block other workers.
# Control via LLM_MAX_CONCURRENT env var (default 8).
_llm_semaphore = threading.Semaphore(int("16"))

def reset_token_log():
    """Clear the token log for a new run."""
    global _token_log
    _token_log = []

def get_token_log() -> list[dict]:
    """Return accumulated token usage log."""
    return _token_log.copy()

def reset_call_stats():
    """Clear call stats for a new run."""
    global _call_stats
    _call_stats = {"total_calls": 0, "retries": 0, "rate_limits_429": 0}

def get_call_stats() -> dict:
    """Return accumulated LLM call stats (total_calls, retries, rate_limits_429)."""
    return _call_stats.copy()

def log_tokens(call_name: str, input_tokens: int, output_tokens: int, model: str):
    """Log a single LLM call's token usage."""
    global _token_log
    _token_log.append({
        "call": call_name,
        "model": model,
        "input": input_tokens,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
    })


def _safe_int(value) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _extract_usage_counts(usage_metadata) -> tuple[int, int]:
    """Extract usage token counts across SDK/API variants without raising."""
    if usage_metadata is None:
        return 0, 0

    # Dict-like metadata (REST responses)
    if isinstance(usage_metadata, dict):
        input_tokens = usage_metadata.get("input_token_count", usage_metadata.get("promptTokenCount", usage_metadata.get("prompt_token_count", 0)))
        output_tokens = usage_metadata.get("output_token_count", usage_metadata.get("candidatesTokenCount", usage_metadata.get("candidates_token_count", 0)))
        return _safe_int(input_tokens), _safe_int(output_tokens)

    # Object-like metadata (SDK responses)
    input_tokens = (
        getattr(usage_metadata, "input_token_count", None)
        or getattr(usage_metadata, "prompt_token_count", None)
        or getattr(usage_metadata, "promptTokenCount", None)
        or 0
    )
    output_tokens = (
        getattr(usage_metadata, "output_token_count", None)
        or getattr(usage_metadata, "candidates_token_count", None)
        or getattr(usage_metadata, "candidatesTokenCount", None)
        or 0
    )
    return _safe_int(input_tokens), _safe_int(output_tokens)


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


def _parse_retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After header seconds when present."""
    if not value:
        return None
    try:
        parsed = float(value.strip())
        if parsed > 0:
            return parsed
    except Exception:
        return None
    return None


def _extract_retry_after_from_error_text(error_text: str) -> float | None:
    """Best-effort extraction of retry hints from provider error text."""
    if not error_text:
        return None

    # Common patterns: "Retry-After: 12", "retry after 12s", "retry after 12.5"
    patterns = [
        r"retry[-\s]?after[:\s]+([0-9]+(?:\.[0-9]+)?)",
        r"retry\s+after\s+([0-9]+(?:\.[0-9]+)?)s?",
    ]
    text = error_text.lower()
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = float(match.group(1))
                if value > 0:
                    return value
            except Exception:
                continue
    return None


def _compute_backoff_delay(attempt: int, retry_after_seconds: float | None = None) -> float:
    """Truncated exponential backoff with jitter."""
    cap_seconds = 30.0
    base_seconds = 1.0
    # attempt starts at 0 for first try; first retry should be ~1s
    exp_delay = min(cap_seconds, base_seconds * (2 ** max(0, attempt)))
    jitter = random.uniform(0.0, max(0.25, exp_delay * 0.25))
    delay = exp_delay + jitter

    if retry_after_seconds is not None and retry_after_seconds > 0:
        # Respect server retry guidance when provided.
        delay = max(delay, min(cap_seconds, retry_after_seconds + random.uniform(0.0, 0.5)))

    return delay


def _apply_burst_smoothing() -> None:
    """Small jitter before requests to reduce synchronized bursts across workers."""
    time.sleep(random.uniform(0.0, 0.15))


def _redact_vertex_url(url: str) -> str:
    """Remove secret query parameters from a Vertex REST URL before logging."""
    return url.split("?", 1)[0]


def _redact_api_key(api_key: str | None) -> str:
    """Return a short fingerprint of an API key without exposing the secret."""
    if not api_key:
        return "<missing>"
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _invoke_vertex_api_key(
    prompt: str,
    *,
    model: str,
    temperature: float,
    max_retries: int,
    call_name: str = "unnamed",
    response_mime_type: str | None = None,
    response_schema: dict | None = None,
    return_usage: bool = False,
) -> str | dict:
    """
    Invoke Vertex API via REST endpoint. Returns text by default, or dict with usage if return_usage=True.
    """
    api_key = os.getenv("GOOGLE_VERTEX_API_KEY") or os.getenv("VERTEX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Vertex API key mode requires GOOGLE_VERTEX_API_KEY (or VERTEX_API_KEY)."
        )

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project:
        # Hardcoded global endpoint path for smoother pay-as-you-go behavior where supported.
        url = f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/models/{model}:generateContent?key={api_key}"
    else:
        # Fallback keeps compatibility if project id is not yet configured.
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
    _call_stats["total_calls"] += 1
    for attempt in range(max_retries + 1):
        try:
            _apply_burst_smoothing()
            logger.warning(
                "[LLM] %s | attempt %s/%s | model=%s",
                call_name,
                attempt + 1,
                max_retries + 1,
                model,
            )
            with _llm_semaphore:
                response = requests.post(url, json=payload, timeout=90)
            if response.status_code == 429:
                _call_stats["rate_limits_429"] += 1
                if attempt < max_retries:
                    _call_stats["retries"] += 1
                    retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
                    time.sleep(_compute_backoff_delay(attempt, retry_after))
                    continue

            if not response.ok:
                last_error = f"HTTP {response.status_code}: {response.text}"
                if attempt < max_retries:
                    _call_stats["retries"] += 1
                    retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
                    time.sleep(_compute_backoff_delay(attempt, retry_after))
                    continue
                break

            data = response.json()
            candidates = data.get("candidates") or []
            if candidates:
                parts = ((candidates[0].get("content") or {}).get("parts") or [])
                text = "".join(p.get("text", "") for p in parts if p.get("text"))
                if text:
                    text = text.strip()
                    
                    # Extract usage metadata if requested
                    if return_usage:
                        usage_metadata = data.get("usageMetadata", {})
                        return {
                            "text": text,
                            "usage": {
                                "input": usage_metadata.get("promptTokenCount", 0),
                                "output": usage_metadata.get("candidatesTokenCount", 0),
                            }
                        }
                    return text

            raise ValueError("Empty response text from Vertex API")
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                _call_stats["retries"] += 1
                retry_after = _extract_retry_after_from_error_text(last_error)
                time.sleep(_compute_backoff_delay(attempt, retry_after))
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
    call_name: str = "unnamed",
) -> str:
    """
    Invokes Gemini 3 Flash Preview.
    Optionally logs token usage if call_name is provided (for debugging).
    """
    model = model_name or MODEL_NAME
    mode = _provider_mode()

    if mode == "vertex_api_key":
        try:
            result = _invoke_vertex_api_key(
                prompt,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
                call_name=call_name,
                return_usage=True,
            )
            # Handle both dict (with usage) and string (fallback) returns
            if isinstance(result, dict):
                log_tokens(call_name, result["usage"]["input"], result["usage"]["output"], model)
                return result["text"]
            return result
        except Exception as e:
            return f"Error: {e}"

    client = _get_client()

    # Single clean config for all agents
    config = types.GenerateContentConfig(
        temperature=temperature,
    )

    last_error: Exception | None = None
    _call_stats["total_calls"] += 1
    for attempt in range(max_retries + 1):
        try:
            _apply_burst_smoothing()
            with _llm_semaphore:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

            # Log token usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens, output_tokens = _extract_usage_counts(response.usage_metadata)
                log_tokens(
                    call_name,
                    input_tokens,
                    output_tokens,
                    model,
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
            last_error = e
            if "429" in str(e):
                _call_stats["rate_limits_429"] += 1
            if attempt < max_retries:
                _call_stats["retries"] += 1
                retry_after = _extract_retry_after_from_error_text(str(e))
                time.sleep(_compute_backoff_delay(attempt, retry_after))
                continue
            break

    if last_error is not None:
        return f"Error: {last_error}"
    return "Error: Max retries exceeded."


def invoke_llm_structured(
    prompt: str,
    schema: type[T],
    *,
    model_name: str | None = None,
    temperature: float = 0.3,
    max_retries: int = 3,
    call_name: str = "unnamed_structured",
) -> T:
    """
    Invokes Gemini with native schema-constrained JSON output.
    Optionally logs token usage if call_name is provided (for debugging).

    Args:
        prompt: Prompt text
        schema: Pydantic model class for strict output validation
        temperature: Sampling temperature
        max_retries: Maximum retries for API/rate-limit issues
        call_name: Name of this call for logging/debugging
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
            result = _invoke_vertex_api_key(
                prompt,
                model=model,
                temperature=temperature,
                max_retries=max_retries,
                call_name=call_name,
                response_mime_type="application/json",
                response_schema=schema_json,
                return_usage=True,
            )
            # Handle both dict (with usage) and string (fallback) returns
            if isinstance(result, dict):
                log_tokens(call_name, result["usage"]["input"], result["usage"]["output"], model)
                text = result["text"]
            else:
                text = result
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
    _call_stats["total_calls"] += 1
    for attempt in range(max_retries + 1):
        try:
            _apply_burst_smoothing()
            with _llm_semaphore:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

            # Log token usage if available
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens, output_tokens = _extract_usage_counts(response.usage_metadata)
                log_tokens(
                    call_name,
                    input_tokens,
                    output_tokens,
                    model,
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
            if "429" in str(e):
                _call_stats["rate_limits_429"] += 1
            if attempt < max_retries:
                _call_stats["retries"] += 1
                retry_after = _extract_retry_after_from_error_text(str(e))
                time.sleep(_compute_backoff_delay(attempt, retry_after))
                continue
            break

    raise RuntimeError(f"Structured LLM call failed after retries: {last_error}")



