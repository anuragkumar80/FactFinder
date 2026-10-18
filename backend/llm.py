"""LLM wrapper: Gemini first, Groq fallback, retries, strict JSON validation."""
import json
import re
import time
import requests
from . import config


class LLMError(RuntimeError):
    pass


def _gemini(system: str, prompt: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{config.GEMINI_MODEL}:generateContent")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": 0},
    }
    r = requests.post(url, json=body, timeout=45,
                      headers={"x-goog-api-key": config.GEMINI_API_KEY})
    if r.status_code != 200:
        raise LLMError(f"Gemini {r.status_code}: {r.text[:200]}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(system: str, prompt: str) -> str:
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions", timeout=45,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={"model": config.GROQ_MODEL, "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": prompt}]})
    if r.status_code != 200:
        raise LLMError(f"Groq {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


def _openai(system: str, prompt: str) -> str:
    r = requests.post(
        "https://api.openai.com/v1/chat/completions", timeout=45,
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={"model": config.OPENAI_MODEL, "temperature": 0,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": system},
                           {"role": "user", "content": prompt}]})
    if r.status_code != 200:
        raise LLMError(f"OpenAI {r.status_code}: {r.text[:200]}")
    return r.json()["choices"][0]["message"]["content"]


def parse_json(text: str) -> dict:
    """Parse model output as JSON, tolerating ```json fences."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(text)


def generate_json(system: str, prompt: str, validate=None, retries: int = 2) -> dict:
    """Call the LLM and return validated JSON.

    `validate(obj)` should raise ValueError on bad structure; the call is then
    retried, and finally falls through to the next provider.
    """
    providers = []
    if config.GEMINI_API_KEY:
        providers.append(("gemini", _gemini))
    if config.GROQ_API_KEY:
        providers.append(("groq", _groq))
    if config.OPENAI_API_KEY:
        providers.append(("openai", _openai))
    if not providers:
        raise LLMError("No LLM key set (OPENAI_API_KEY, GEMINI_API_KEY, or GROQ_API_KEY)")

    last = None
    for name, fn in providers:
        for attempt in range(retries + 1):
            try:
                obj = parse_json(fn(system, prompt))
                if validate:
                    validate(obj)
                return obj
            except (LLMError, ValueError, KeyError, requests.RequestException) as e:
                last = f"{name}: {e}"
                time.sleep(1.5 * (attempt + 1))  # simple backoff
    raise LLMError(f"All providers failed. Last error: {last}")
