"""
NEXUS NOW — Free AI Provider Manager
======================================
The system NEVER collapses when one AI subscription ends.

Provider priority order (all FREE tiers):
  1. Google Gemini Flash     — 15 req/min, 1M tokens/day (primary)
  2. Google Gemini 1.5 Flash — fallback Gemini model
  3. Groq (Llama 3.3 70B)   — 14,400 req/day FREE, extremely fast
  4. Together AI             — Free $25 credit, then cheap
  5. Cohere                  — Free tier 1000 req/month
  6. Hugging Face Inference  — Free serverless endpoints
  7. Mistral AI              — Free tier (le chat API)
  8. OpenRouter              — Routes to cheapest free model available

For IMAGE generation (all FREE):
  1. Gemini Imagen           — free with API key
  2. Hugging Face FLUX       — free serverless
  3. Pollinations.ai         — completely free, no key needed
  4. Stable Diffusion (HF)   — free serverless

For TEXT-TO-SPEECH (all FREE):
  1. Google Cloud TTS        — 1M chars/month free
  2. Hugging Face TTS        — free serverless (VITS, SpeechT5)
  3. gTTS (Google Translate) — completely free, no key
  4. Edge TTS (Microsoft)    — completely free via edge-tts package
"""

import os
import json
import time
import base64
import requests
from pathlib import Path
from datetime import datetime, date


# ── PROVIDER QUOTA TRACKER (stored in Google Sheets via free API) ──────────
QUOTA_FILE = Path("agent_memory/provider_quotas.json")

def load_quotas() -> dict:
    if QUOTA_FILE.exists():
        try:
            return json.loads(QUOTA_FILE.read_text())
        except:
            pass
    return {}

def save_quotas(quotas: dict):
    QUOTA_FILE.parent.mkdir(exist_ok=True)
    QUOTA_FILE.write_text(json.dumps(quotas, indent=2))

def mark_provider_used(provider: str, tokens: int = 100):
    quotas = load_quotas()
    today  = str(date.today())
    if provider not in quotas:
        quotas[provider] = {}
    if today not in quotas[provider]:
        quotas[provider][today] = {"calls": 0, "tokens": 0}
    quotas[provider][today]["calls"]  += 1
    quotas[provider][today]["tokens"] += tokens
    save_quotas(quotas)

def is_provider_available(provider: str) -> bool:
    """Check if a provider is within its daily free limits."""
    quotas  = load_quotas()
    today   = str(date.today())
    usage   = quotas.get(provider, {}).get(today, {"calls": 0, "tokens": 0})
    calls   = usage["calls"]
    LIMITS  = {
        "gemini_flash":    {"calls": 1400},   # 15/min = ~1400/day safe limit
        "gemini_15_flash": {"calls": 1400},
        "groq":            {"calls": 14000},  # 14,400/day
        "together":        {"calls": 500},
        "cohere":          {"calls": 950},    # 1000/month → ~30/day
        "huggingface":     {"calls": 300},
        "mistral":         {"calls": 500},
        "openrouter":      {"calls": 200},
    }
    limit = LIMITS.get(provider, {}).get("calls", 100)
    return calls < limit


# ═══════════════════════════════════════════════════════════════════════════
# UNIVERSAL AI TEXT GENERATOR
# Auto-fails over through every free provider
# ═══════════════════════════════════════════════════════════════════════════
class FreeAIProvider:
    """
    Call this instead of any hardcoded AI API.
    It tries providers in order, skips exhausted ones,
    and always finds a working free model.
    """

    def __init__(self):
        self.gemini_key   = os.environ.get("GEMINI_API_KEY", "")
        self.groq_key     = os.environ.get("GROQ_API_KEY", "")
        self.together_key = os.environ.get("TOGETHER_API_KEY", "")
        self.cohere_key   = os.environ.get("COHERE_API_KEY", "")
        self.hf_key       = os.environ.get("HF_TOKEN", "")
        self.mistral_key  = os.environ.get("MISTRAL_API_KEY", "")
        self.openrouter_k = os.environ.get("OPENROUTER_API_KEY", "")

    def generate(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        """
        Try every free provider in order until one succeeds.
        Returns the text response.
        """
        providers = [
            ("gemini_flash",     self._try_gemini_flash),
            ("gemini_15_flash",  self._try_gemini_15_flash),
            ("groq",             self._try_groq),
            ("together",         self._try_together),
            ("cohere",           self._try_cohere),
            ("huggingface",      self._try_huggingface),
            ("mistral",          self._try_mistral),
            ("openrouter",       self._try_openrouter),
        ]

        last_error = None
        for name, fn in providers:
            if not is_provider_available(name):
                print(f"    [AI] {name} quota exhausted today — trying next")
                continue
            try:
                result = fn(prompt, system, max_tokens)
                if result and len(result.strip()) > 20:
                    mark_provider_used(name, len(result.split()))
                    print(f"    [AI] Used: {name}")
                    return result
            except Exception as e:
                last_error = e
                print(f"    [AI] {name} failed: {str(e)[:80]} — trying next")
                time.sleep(1)

        raise RuntimeError(f"ALL AI PROVIDERS EXHAUSTED. Last error: {last_error}")

    # ── PROVIDER IMPLEMENTATIONS ───────────────────────────────────────────

    def _try_gemini_flash(self, prompt, system, max_tokens):
        if not self.gemini_key:
            raise ValueError("No GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.gemini_key}"
        contents = []
        if system:
            contents += [
                {"role":"user",  "parts":[{"text": system}]},
                {"role":"model", "parts":[{"text":"Understood."}]},
            ]
        contents.append({"role":"user","parts":[{"text": prompt}]})
        r = requests.post(url, json={
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.75}
        }, timeout=90)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _try_gemini_15_flash(self, prompt, system, max_tokens):
        if not self.gemini_key:
            raise ValueError("No GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        r = requests.post(url, json={
            "contents": [{"role":"user","parts":[{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}
        }, timeout=90)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _try_groq(self, prompt, system, max_tokens):
        if not self.groq_key:
            raise ValueError("No GROQ_API_KEY")
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.groq_key}",
                     "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    *([ {"role":"system","content":system} ] if system else []),
                    {"role":"user","content": prompt}
                ],
                "max_tokens": min(max_tokens, 8000),
                "temperature": 0.75
            }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]

    def _try_together(self, prompt, system, max_tokens):
        if not self.together_key:
            raise ValueError("No TOGETHER_API_KEY")
        r = requests.post("https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.together_key}"},
            json={
                "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                "messages": [
                    *([ {"role":"system","content":system} ] if system else []),
                    {"role":"user","content": prompt}
                ],
                "max_tokens": max_tokens
            }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]

    def _try_cohere(self, prompt, system, max_tokens):
        if not self.cohere_key:
            raise ValueError("No COHERE_API_KEY")
        r = requests.post("https://api.cohere.ai/v1/generate",
            headers={"Authorization": f"Bearer {self.cohere_key}"},
            json={
                "model": "command-r-plus",
                "prompt": f"{system}\n\n{prompt}" if system else prompt,
                "max_tokens": max_tokens,
                "temperature": 0.75
            }, timeout=60)
        return r.json()["generations"][0]["text"]

    def _try_huggingface(self, prompt, system, max_tokens):
        """HuggingFace free serverless inference."""
        model = "mistralai/Mistral-7B-Instruct-v0.3"
        headers = {}
        if self.hf_key:
            headers["Authorization"] = f"Bearer {self.hf_key}"
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        r = requests.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers=headers,
            json={"inputs": full_prompt, "parameters": {"max_new_tokens": min(max_tokens, 1000)}},
            timeout=120
        )
        data = r.json()
        if isinstance(data, list):
            return data[0].get("generated_text", "")
        raise ValueError(str(data))

    def _try_mistral(self, prompt, system, max_tokens):
        if not self.mistral_key:
            raise ValueError("No MISTRAL_API_KEY")
        r = requests.post("https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.mistral_key}"},
            json={
                "model": "mistral-small-latest",
                "messages": [
                    *([ {"role":"system","content":system} ] if system else []),
                    {"role":"user","content": prompt}
                ],
                "max_tokens": max_tokens
            }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]

    def _try_openrouter(self, prompt, system, max_tokens):
        if not self.openrouter_k:
            raise ValueError("No OPENROUTER_API_KEY")
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.openrouter_k}",
                     "HTTP-Referer": "https://nexusnow.media"},
            json={
                "model": "google/gemma-3-27b-it:free",   # Free on OpenRouter
                "messages": [
                    *([ {"role":"system","content":system} ] if system else []),
                    {"role":"user","content": prompt}
                ],
                "max_tokens": max_tokens
            }, timeout=60)
        return r.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════════════════
# FREE IMAGE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════
class FreeImageProvider:

    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.hf_key     = os.environ.get("HF_TOKEN", "")

    def generate(self, prompt: str, filename: str, aspect: str = "16:9") -> str | None:
        """Try image providers in order. Returns saved file path or None."""
        providers = [
            self._try_gemini_imagen,
            self._try_pollinations,     # ZERO keys needed
            self._try_huggingface_flux,
        ]
        for fn in providers:
            try:
                path = fn(prompt, filename, aspect)
                if path:
                    return path
            except Exception as e:
                print(f"    [IMG] Provider failed: {str(e)[:60]}")
        return None

    def _save(self, data: bytes, filename: str) -> str:
        path = Path(f"assets/images/{filename}.jpg")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def _try_gemini_imagen(self, prompt, filename, aspect):
        if not self.gemini_key:
            raise ValueError("No key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={self.gemini_key}"
        r = requests.post(url, json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": aspect}
        }, timeout=90)
        b64 = r.json()["predictions"][0]["bytesBase64Encoded"]
        return self._save(base64.b64decode(b64), filename)

    def _try_pollinations(self, prompt, filename, aspect):
        """Pollinations.ai — 100% free, no API key, no rate limit listed."""
        w, h = (1280, 720) if aspect == "16:9" else (1080, 1080)
        encoded = requests.utils.quote(prompt[:500])
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&nologo=true&model=flux"
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and r.headers.get("content-type","").startswith("image"):
            return self._save(r.content, filename)
        raise ValueError(f"Status {r.status_code}")

    def _try_huggingface_flux(self, prompt, filename, aspect):
        headers = {}
        if self.hf_key:
            headers["Authorization"] = f"Bearer {self.hf_key}"
        r = requests.post(
            "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
            headers=headers,
            json={"inputs": prompt[:500]},
            timeout=180
        )
        if r.headers.get("content-type","").startswith("image"):
            return self._save(r.content, filename)
        raise ValueError("Not an image response")


# ═══════════════════════════════════════════════════════════════════════════
# FREE TEXT-TO-SPEECH
# ═══════════════════════════════════════════════════════════════════════════
class FreeTTSProvider:

    def __init__(self):
        self.google_key = os.environ.get("GEMINI_API_KEY", "")  # Same key works for TTS

    def generate(self, text: str, filename: str) -> str | None:
        providers = [
            self._try_google_tts,
            self._try_edge_tts,
            self._try_gtts,
        ]
        for fn in providers:
            try:
                path = fn(text, filename)
                if path:
                    return path
            except Exception as e:
                print(f"    [TTS] Provider failed: {str(e)[:60]}")
        return None

    def _save(self, data: bytes, filename: str) -> str:
        path = Path(f"assets/audio/{filename}.mp3")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def _try_google_tts(self, text, filename):
        if not self.google_key:
            raise ValueError("No key")
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.google_key}"
        r = requests.post(url, json={
            "input": {"text": text[:4500]},
            "voice": {"languageCode":"en-US","name":"en-US-Neural2-D","ssmlGender":"MALE"},
            "audioConfig": {"audioEncoding":"MP3","speakingRate":1.08,"pitch":-1.5}
        }, timeout=30)
        b64 = r.json().get("audioContent")
        if not b64:
            raise ValueError(str(r.json())[:100])
        return self._save(base64.b64decode(b64), filename)

    def _try_edge_tts(self, text, filename):
        """Microsoft Edge TTS — completely free via edge-tts package."""
        import subprocess, tempfile
        out = Path(f"assets/audio/{filename}.mp3")
        out.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            "edge-tts",
            "--voice", "en-US-GuyNeural",
            "--rate", "+8%",
            "--text", text[:5000],
            "--write-media", str(out)
        ], capture_output=True, timeout=60)
        if result.returncode == 0 and out.exists():
            return str(out)
        raise ValueError(result.stderr.decode())

    def _try_gtts(self, text, filename):
        """gTTS — uses Google Translate, completely free."""
        from gtts import gTTS
        tts  = gTTS(text=text[:5000], lang="en", slow=False)
        path = f"assets/audio/{filename}.mp3"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tts.save(path)
        return path


# ── GLOBAL SINGLETONS ──────────────────────────────────────────────────────
ai_provider  = FreeAIProvider()
img_provider = FreeImageProvider()
tts_provider = FreeTTSProvider()

def ai_generate(prompt: str, system: str = "", max_tokens: int = 2000) -> str:
    return ai_provider.generate(prompt, system, max_tokens)

def img_generate(prompt: str, filename: str) -> str | None:
    return img_provider.generate(prompt, filename)

def tts_generate(text: str, filename: str) -> str | None:
    return tts_provider.generate(text, filename)
