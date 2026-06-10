"""
Google AI Studio (Gemini) client wrapper.

The model name is configurable via the GEMINI_MODEL env var so it can be
updated without code changes (Google periodically retires model versions).
Defaults to gemini-1.5-pro per the project spec.
"""

import os
import logging
from functools import lru_cache

import google.generativeai as genai

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")


class GeminiError(RuntimeError):
    """Raised when a Gemini call fails or returns no usable text."""


@lru_cache(maxsize=4)
def get_gemini_model(model_name: str = DEFAULT_MODEL):
    api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        raise GeminiError("GOOGLE_AI_STUDIO_API_KEY is not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


async def call_gemini(prompt: str, system: str = "", model_name: str = DEFAULT_MODEL) -> str:
    """
    Call Gemini and return the response text (stripped).
    Raises GeminiError on any failure or empty/blocked response.
    """
    try:
        model = get_gemini_model(model_name)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = await model.generate_content_async(full_prompt)
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise GeminiError("Gemini returned an empty response")
        return text
    except GeminiError:
        raise
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        raise GeminiError(str(exc)) from exc
