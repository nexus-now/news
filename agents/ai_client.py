"""
NEXUS NOW - AI Client
All AI calls go through here. Auto-failover: Gemini → Groq → HuggingFace.
All imports are inside functions so nothing crashes at import time.
"""
import os, json, base64, requests
from pathlib import Path


def _k(name):
    return os.environ.get(name, "")


def ai_text(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    """Generate text. Tries providers in order. Never returns empty."""
    errors = []

    # 1. Gemini Flash
    key = _k("GEMINI_API_KEY")
    if key:
        for model in ["gemini-2.0-flash-exp", "gemini-1.5-flash"]:
            try:
                url = (f"https://generativelanguage.googleapis.com/v1beta"
                       f"/models/{model}:generateContent?key={key}")
                body = {"contents": [], "generationConfig": {
                    "maxOutputTokens": max_tokens, "temperature": 0.75}}
                if system:
                    body["contents"] += [
                        {"role": "user",  "parts": [{"text": system}]},
                        {"role": "model", "parts": [{"text": "Understood."}]}]
                body["contents"].append({"role": "user", "parts": [{"text": prompt}]})
                r = requests.post(url, json=body, timeout=90)
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                errors.append(f"{model}: {e}")

    # 2. Groq
    key = _k("GROQ_API_KEY")
    if key:
        try:
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile",
                      "messages": msgs,
                      "max_tokens": min(max_tokens, 8000),
                      "temperature": 0.75},
                timeout=60)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            errors.append(f"Groq: {e}")

    # 3. HuggingFace (free, no key)
    try:
        full = f"{system}\n\n{prompt}" if system else prompt
        r = requests.post(
            "https://api-inference.huggingface.co/models"
            "/mistralai/Mistral-7B-Instruct-v0.3",
            json={"inputs": full[:3000],
                  "parameters": {"max_new_tokens": min(max_tokens, 800)}},
            timeout=120)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "")
            return text[len(full):].strip() if text.startswith(full[:50]) else text.strip()
    except Exception as e:
        errors.append(f"HuggingFace: {e}")

    raise RuntimeError("All AI providers failed: " + " | ".join(errors))


def ai_image(prompt: str, slug: str) -> str | None:
    """Generate thumbnail image. Returns file path or None."""
    Path("assets/images").mkdir(parents=True, exist_ok=True)
    out = f"assets/images/{slug}.jpg"

    # 1. Pollinations (free, no key, no limit)
    try:
        enc = requests.utils.quote(prompt[:400])
        r = requests.get(
            f"https://image.pollinations.ai/prompt/{enc}"
            f"?width=1280&height=720&nologo=true&model=flux",
            timeout=120)
        if r.status_code == 200 and "image" in r.headers.get("content-type", ""):
            Path(out).write_bytes(r.content)
            return out
    except Exception:
        pass

    # 2. Gemini Imagen
    key = _k("GEMINI_API_KEY")
    if key:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta"
                f"/models/imagen-3.0-generate-002:predict?key={key}",
                json={"instances": [{"prompt": prompt[:400]}],
                      "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}},
                timeout=90)
            if r.status_code == 200:
                b64 = r.json().get("predictions", [{}])[0].get("bytesBase64Encoded", "")
                if b64:
                    Path(out).write_bytes(base64.b64decode(b64))
                    return out
        except Exception:
            pass

    return None


def ai_tts(text: str, slug: str) -> str | None:
    """Generate voiceover MP3. Returns file path or None."""
    Path("assets/audio").mkdir(parents=True, exist_ok=True)
    out = f"assets/audio/{slug}.mp3"

    # 1. Google Cloud TTS
    key = _k("GEMINI_API_KEY")
    if key:
        try:
            r = requests.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                json={"input": {"text": text[:4500]},
                      "voice": {"languageCode": "en-US",
                                "name": "en-US-Neural2-D",
                                "ssmlGender": "MALE"},
                      "audioConfig": {"audioEncoding": "MP3",
                                      "speakingRate": 1.05, "pitch": -1.0}},
                timeout=30)
            if r.status_code == 200:
                b64 = r.json().get("audioContent", "")
                if b64:
                    Path(out).write_bytes(base64.b64decode(b64))
                    return out
        except Exception:
            pass

    # 2. gTTS (free, always works)
    try:
        from gtts import gTTS
        gTTS(text=text[:3000], lang="en", slow=False).save(out)
        return out
    except Exception:
        pass

    return None


def extract_json(text: str) -> str:
    """Pull first valid JSON object or array from text."""
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            p = part.strip().lstrip("json").strip()
            if p.startswith(("{", "[")):
                text = p
                break
    stack = []
    pairs = {"{": "}", "[": "]"}
    for i, ch in enumerate(text):
        if ch in "{[":
            stack.append(pairs[ch])
        elif ch in "}]" and stack:
            if ch == stack[-1]:
                stack.pop()
            if not stack:
                return text[:i+1]
    return text
