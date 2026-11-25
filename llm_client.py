import os
import time
import requests

API_KEY = os.environ.get("GEMINI_API_KEY")
BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Model ke naam badalte rehte hain. AI Studio mein current naam dekh lein.
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-flash-lite-latest")
EMBED_MODEL = "gemini-embedding-001"
API_TIMEOUT = float(os.environ.get("GEMINI_API_TIMEOUT", "45"))
MAX_RETRIES = int(os.environ.get("GEMINI_API_RETRIES", "3"))
CHAT_MODELS = [
    CHAT_MODEL,
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
]


def _post(url, body, retries=MAX_RETRIES):
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable set nahi hai.")
    for attempt in range(retries):
        try:
            r = requests.post(
                url,
                json=body,
                headers={"x-goog-api-key": API_KEY},
                timeout=(10, API_TIMEOUT),
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(
                    f"Gemini API unavailable after {retries} attempts: {exc}"
                ) from exc
            delay = min(2 ** attempt, 10)
            time.sleep(delay)
            continue

        if r.status_code in (429, 500, 502, 503, 504):
            if attempt == retries - 1:
                details = r.text[:500]
                raise RuntimeError(
                    f"Gemini API temporarily unavailable after {retries} attempts "
                    f"(HTTP {r.status_code}): {details}"
                )
            retry_after = r.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else min(5 * (2 ** attempt), 10)
            except ValueError:
                delay = min(5 * (2 ** attempt), 10)
            time.sleep(delay)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Gemini API error {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("Gemini API request failed after retries.")


def create_embedding(text_list, task="RETRIEVAL_DOCUMENT"):
    """task: chunks ke liye RETRIEVAL_DOCUMENT, user ke sawaal ke liye RETRIEVAL_QUERY"""
    requests_body = {
        "requests": [
            {
                "model": f"models/{EMBED_MODEL}",
                "content": {"parts": [{"text": t}]},
                "taskType": task,
            }
            for t in text_list
        ]
    }
    data = _post(f"{BASE}/{EMBED_MODEL}:batchEmbedContents", requests_body)
    return [e["values"] for e in data["embeddings"]]


def inference(prompt):
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500},
    }
    data = None
    errors = []
    tried_models = []

    for model in dict.fromkeys(CHAT_MODELS):
        tried_models.append(model)
        try:
            data = _post(
                f"{BASE}/{model}:generateContent",
                body,
                retries=1,
            )
            break
        except RuntimeError as exc:
            errors.append(str(exc))

    if data is None:
        raise RuntimeError(
            "Gemini models temporarily unavailable "
            f"(tried: {', '.join(tried_models)}). "
            f"Latest error: {errors[-1]}"
        )

    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        text = ""

    if not text:
        raise RuntimeError(f"Model ne khali jawab diya: {str(data)[:300]}")
    return {"response": text}