import os
from functools import lru_cache
import google.generativeai as genai


@lru_cache(maxsize=1)
def get_gemini_model():
    genai.configure(api_key=os.environ["GOOGLE_AI_STUDIO_API_KEY"])
    return genai.GenerativeModel("gemini-1.5-pro")


async def call_gemini(prompt: str, system: str = "") -> str:
    model = get_gemini_model()
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    response = await model.generate_content_async(full_prompt)
    return response.text
