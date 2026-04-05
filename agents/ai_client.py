"""
NEXUS NOW — Unified AI Client
==============================
Single file. All AI calls go through here.
Auto-failover across 5 free providers.
NO top-level imports that can crash.
Every import is inside its function with try/except.
"""
import os
import json
import time
import base64
import requests
from pathlib import Path

# ── PROVIDER KEYS (read from environment) ─────────────────────────────────
def _key(name): return os.environ.get(name, "")


# ════════════════════════════════════════════════════════════════════════════
# TEXT GENERATION — tries each provider in order
# ════════════════════════════════════════════════════════════════════════════
def ai_text(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """
    Generate text. Tries free providers in order until one works.
    Raises RuntimeError only if ALL providers fail.
    """
    errors = []

    # 1. Gemini Flash (primary — 1500 free req/day)
    key = _key("GEMINI_API_KEY")
    if key:
        try:
            return _gemini(prompt, system, max_tokens, key,
                           "gemini-2.0-flash-exp")
        except Exception as e:
            errors.append(f"Gemini Flash: {e}")
            try:
                return _gemini(prompt, system, max_tokens, key,
                               "gemini-1.5-flash")
            except Exception as e2:
                errors.append(f"Gemini 1.5: {e2}")

    # 2. Groq — Llama 3.3 70B (14400 free req/day)
    key = _key("GROQ_API_KEY")
    if key:
        try:
            return _groq(prompt, system, max_tokens, key)
        except Exception as e:
            errors.append(f"Groq: {e}")

    # 3. HuggingFace serverless (free, no key needed)
    try:
        return _huggingface(prompt, system, max_tokens)
    except Exception as e:
        errors.append(f"HuggingFace: {e}")

    raise RuntimeError(
        f"All AI providers failed:\n" + "\n".join(errors)
    )


def _gemini(prompt, system, max_tokens, key, model):
    url = (f"https://generativelanguage.googleapis.com/v1beta/"
           f"models/{model}:generateContent?key={key}")
    contents = []
    if system:
        contents.append({"role": "user",  "parts": [{"text": system}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    r = requests.post(url, json={
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.75
        }
    }, timeout=90)
    r.raise_for_status()
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Gemini bad response: {data}") from e


def _groq(prompt, system, max_tokens, key):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"},
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": min(max_tokens, 8000),
            "temperature": 0.75
        },
        timeout=60
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _huggingface(prompt, system, max_tokens):
    full = f"{system}\n\n{prompt}" if system else prompt
    r = requests.post(
        "https://api-inference.huggingface.co/models/"
        "mistralai/Mistral-7B-Instruct-v0.3",
        json={"inputs": full[:3000],
              "parameters": {"max_new_tokens": min(max_tokens, 1000)}},
        timeout=120
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data:
        text = data[0].get("generated_text", "")
        # Remove the input prompt from the output
        if text.startswith(full[:100]):
            text = text[len(full):]
        return text.strip()
    raise RuntimeError(f"HuggingFace bad response: {data}")


# ════════════════════════════════════════════════════════════════════════════
# IMAGE GENERATION — Pollinations (no key, always free) + Gemini
# ════════════════════════════════════════════════════════════════════════════
def ai_image(prompt: str, filename: str) -> str | None:
    """Generate image. Returns saved path or None."""
    Path("assets/images").mkdir(parents=True, exist_ok=True)
    out = f"assets/images/{filename}.jpg"

    # 1. Pollinations.ai — completely free, no key, no rate limit
    try:
        encoded = requests.utils.quote(prompt[:400])
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1280&height=720&nologo=true&model=flux")
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            Path(out).write_bytes(r.content)
            return out
    except Exception as e:
        print(f"  [IMG] Pollinations failed: {e}")

    # 2. Gemini Imagen
    key = _key("GEMINI_API_KEY")
    if key:
        try:
            url = (f"https://generativelanguage.googleapis.com/v1beta/"
                   f"models/imagen-3.0-generate-002:predict?key={key}")
            r = requests.post(url, json={
                "instances": [{"prompt": prompt[:400]}],
                "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}
            }, timeout=90)
            if r.status_code == 200:
                pred = r.json().get("predictions", [{}])[0]
                b64  = pred.get("bytesBase64Encoded", "")
                if b64:
                    Path(out).write_bytes(base64.b64decode(b64))
                    return out
        except Exception as e:
            print(f"  [IMG] Gemini Imagen failed: {e}")

    return None


# ════════════════════════════════════════════════════════════════════════════
# TEXT TO SPEECH
# ════════════════════════════════════════════════════════════════════════════
def ai_tts(text: str, filename: str) -> str | None:
    """Generate voiceover. Returns saved path or None."""
    Path("assets/audio").mkdir(parents=True, exist_ok=True)
    out = f"assets/audio/{filename}.mp3"

    # 1. Google Cloud TTS (free 1M chars/month — uses Gemini API key)
    key = _key("GEMINI_API_KEY")
    if key:
        try:
            r = requests.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                json={
                    "input": {"text": text[:4500]},
                    "voice": {"languageCode": "en-US",
                              "name": "en-US-Neural2-D",
                              "ssmlGender": "MALE"},
                    "audioConfig": {"audioEncoding": "MP3",
                                    "speakingRate": 1.05,
                                    "pitch": -1.0}
                },
                timeout=30
            )
            if r.status_code == 200:
                b64 = r.json().get("audioContent", "")
                if b64:
                    Path(out).write_bytes(base64.b64decode(b64))
                    return out
        except Exception as e:
            print(f"  [TTS] Google TTS failed: {e}")

    # 2. gTTS (uses Google Translate, completely free)
    try:
        from gtts import gTTS
        tts = gTTS(text=text[:3000], lang="en", slow=False)
        tts.save(out)
        return out
    except Exception as e:
        print(f"  [TTS] gTTS failed: {e}")

    return None


# ════════════════════════════════════════════════════════════════════════════
# JSON HELPER
# ════════════════════════════════════════════════════════════════════════════
def extract_json(text: str) -> str:
    """Strip markdown fences and find the first JSON object or array."""
    text = text.strip()
    # Remove markdown code fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{") or part.startswith("["):
                text = part
                break
    # Find first { or [
    for i, ch in enumerate(text):
        if ch in "{[":
            # Find matching close
            stack = []
            pairs = {"{": "}", "[": "]"}
            close = pairs[ch]
            for j, c in enumerate(text[i:], i):
                if c in "{[":
                    stack.append(c)
                elif c in "}]":
                    if stack:
                        stack.pop()
                    if not stack:
                        return text[i:j+1]
    return text
