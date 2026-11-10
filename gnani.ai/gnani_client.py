"""Gnani API helpers + threat analysis for Raksha Voice.

Env vars:
  GNANI_API_KEY   (required)  -> Prisma v3.0 STT + Timbre v3.0 TTS
  LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (optional) -> OpenAI-compatible host serving Gnani Evon.
If not set (or failing), a multilingual keyword engine is used and the UI says so.
"""
import base64
import json
import os
import re

import requests

BASE = "https://api.vachana.ai"
LEVELS = ["Safe", "Concern", "Danger", "Emergency"]


def _key():
    return os.getenv("GNANI_API_KEY", "")


# ------------------------------------------------------------------ STT (Prisma v3.0)
def stt(audio_bytes: bytes, filename: str = "audio.wav", language_code: str = "indic-auto"):
    """Returns (transcript, response_json). Prisma v3.0 with automatic language detection."""
    r = requests.post(
        f"{BASE}/stt/v3",
        headers={"X-API-Key-ID": _key()},
        files={"audio_file": (filename, audio_bytes)},
        data={"model": "prisma-v3.0", "language_code": language_code},
        timeout=90,
    )
    try:
        body = r.json()
    except Exception:
        raise RuntimeError(f"STT failed: HTTP {r.status_code} {r.text[:200]}")
    if not body.get("success"):
        err = body.get("error", body)
        raise RuntimeError(f"STT failed: {err}")
    return body.get("transcript", ""), body


# ------------------------------------------------------------------ TTS (Timbre v3.0)
def tts(text: str, language: str = "hi-IN", voice: str = "Shivani"):
    """Returns audio bytes. Timbre v3.0 first; falls back to v2.5."""
    attempts = [
        {"text": text, "voice": voice, "model": "timbre-v3.0", "language": language},
        {"text": text, "voice": "Nalini", "model": "timbre-v2.5", "language": language},
    ]
    last = None
    for body in attempts:
        r = requests.post(
            f"{BASE}/api/v1/tts/inference",
            headers={"X-API-Key-ID": _key(), "Content-Type": "application/json"},
            json=body,
            timeout=90,
        )
        if r.ok:
            if "json" in r.headers.get("content-type", ""):
                j = r.json()
                b64 = j.get("audio") or j.get("audio_base64") or ""
                return base64.b64decode(b64)
            return r.content
        last = f"{r.status_code} {r.text[:200]}"
    raise RuntimeError(f"TTS failed: {last}")


# ------------------------------------------------------------------ language
def detect_script(text: str) -> str:
    for rng, code in ((r"[஀-௿]", "ta-IN"), (r"[ఀ-౿]", "te-IN"), (r"[ಀ-೿]", "kn-IN"),
                      (r"[ഀ-ൿ]", "ml-IN"), (r"[ঀ-৿]", "bn-IN"), (r"[઀-૿]", "gu-IN"),
                      (r"[਀-੿]", "pa-IN"), (r"[ऀ-ॿ]", "hi-IN")):
        if re.search(rng, text):
            return code
    return "en-IN"


LANG_NAMES = {"hi-IN": "Hindi", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada", "ml-IN": "Malayalam",
              "bn-IN": "Bengali", "gu-IN": "Gujarati", "pa-IN": "Punjabi", "mr-IN": "Marathi", "en-IN": "English"}

REPLIES = {
    "hi-IN": {
        "Safe": "आपका संदेश मिल गया। स्थिति सुरक्षित लग रही है। ज़रूरत हो तो फिर बताइए।",
        "Concern": "आपका संदेश मिल गया। आप सुरक्षित जगह पर रहिए। हम आपके भरोसेमंद व्यक्ति को सूचित कर रहे हैं।",
        "Danger": "घबराइए मत। हम आपके भरोसेमंद व्यक्ति को अभी सूचित कर रहे हैं। किसी भीड़ वाली, रोशनी वाली जगह पर जाइए।",
        "Emergency": "घबराइए मत, मदद भेजी जा रही है। लाइन पर बने रहिए और सुरक्षित जगह पर जाइए।",
    },
    "ta-IN": {
        "Safe": "உங்கள் செய்தி கிடைத்தது. நிலைமை பாதுகாப்பாக உள்ளது.",
        "Concern": "உங்கள் செய்தி கிடைத்தது. பாதுகாப்பான இடத்தில் இருங்கள். உங்கள் நம்பிக்கைக்குரியவருக்கு தெரிவிக்கிறோம்.",
        "Danger": "பயப்பட வேண்டாம். உங்கள் நம்பிக்கைக்குரியவருக்கு இப்போதே தெரிவிக்கிறோம். கூட்டமான, வெளிச்சமான இடத்திற்கு செல்லுங்கள்.",
        "Emergency": "பயப்பட வேண்டாம், உதவி அனுப்பப்படுகிறது. லைனில் இருங்கள், பாதுகாப்பான இடத்திற்கு செல்லுங்கள்.",
    },
    "en-IN": {
        "Safe": "Message received. The situation looks safe. Tell us if anything changes.",
        "Concern": "Message received. Stay in a safe place. We are informing your trusted contact.",
        "Danger": "Stay calm. We are alerting your trusted contact now. Move to a crowded, well-lit place.",
        "Emergency": "Stay calm, help is being alerted. Stay on the line and move to a safe place.",
    },
}


def reply_for(level: str, lang: str):
    """Returns (text, language_used). Languages without a written reply fall back to Hindi/English."""
    if lang in REPLIES:
        return REPLIES[lang][level], lang
    fallback = "hi-IN" if lang in ("mr-IN", "pa-IN", "gu-IN", "bn-IN") else "en-IN"
    return REPLIES[fallback][level], fallback


# ------------------------------------------------------------------ analysis
EMERGENCY = [
    "bachao", "bachaao", "bacha lo", "help me", "save me", "knife", "gun", "kill", "maar dega", "maar dalega",
    "kidnap", "rape", "dying", "attack", "acid", "pakad liya", "he is hitting", "hitting me",
    "बचाओ", "बचा लो", "मार डालेगा", "चाकू", "बंदूक", "किडनैप", "जान से", "मार रहा",
    "காப்பாற்று", "காப்பாத்து", "கத்தி", "கொன்று", "கொல்ல", "கடத்த", "அடிக்கிறான்",
]
DANGER = [
    "follow", "peeche", "peecha", "chasing", "threat", "dhamki", "drunk", "grabbed", "touch", "pushed", "stalk",
    "won't leave", "blocking", "behind me", "harass", "chhed", "zabardasti", "force", "scared", "darr",
    "पीछा", "धमकी", "डर", "छेड़", "ज़बरदस्ती", "जबरदस्ती", "शराब",
    "பின்தொடர", "மிரட்ட", "பயம்", "தொந்தரவு", "குடித்து", "வற்புறுத்த",
]
CONCERN = [
    "uncomfortable", "weird", "staring", "comment", "unsafe", "late", "alone", "suspicious", "dark",
    "अकेली", "अजीब", "घूर", "असुरक्षित", "अंधेरा",
    "தனியாக", "வித்தியாசம்", "பாதுகாப்பற்ற", "இருட்டு", "பார்க்கிறா",
]
THREAT_TYPES = {"Emergency": "Immediate physical threat", "Danger": "Harassment / stalking / intimidation",
                "Concern": "Potentially unsafe situation", "Safe": "No threat detected"}


def rules_analyze(text: str) -> dict:
    t = text.lower()
    hits = {"Emergency": [k for k in EMERGENCY if k in t], "Danger": [k for k in DANGER if k in t],
            "Concern": [k for k in CONCERN if k in t]}
    level = "Emergency" if hits["Emergency"] else "Danger" if hits["Danger"] else "Concern" if hits["Concern"] else "Safe"
    return {"risk_level": level, "threat_type": THREAT_TYPES[level], "location": "Not mentioned",
            "summary": text[:200], "flagged_phrases": hits.get(level, []) if level != "Safe" else [],
            "engine": "Multilingual keyword engine"}


LLM_PROMPT = (
    "You are an emergency triage system for distress calls in Indian languages (Hindi, Tamil, English, Hinglish, Tanglish). "
    "Read the transcript and reply with ONLY a JSON object with keys: "
    'risk_level (one of "Safe","Concern","Danger","Emergency"), threat_type (short), location (string or "Not mentioned"), '
    'summary (one English sentence), flagged_phrases (list of exact phrases from the transcript that justify the level).\n'
    "Transcript:\n"
)


def llm_analyze(text: str):
    base, key, model = os.getenv("LLM_BASE_URL"), os.getenv("LLM_API_KEY", ""), os.getenv("LLM_MODEL")
    if not (base and model):
        return None
    try:
        r = requests.post(base.rstrip("/") + "/chat/completions",
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                          json={"model": model, "temperature": 0,
                                "messages": [{"role": "user", "content": LLM_PROMPT + text}]}, timeout=60)
        r.raise_for_status()
        out = re.sub(r"<think>.*?</think>", "", r.json()["choices"][0]["message"]["content"], flags=re.S)
        j = json.loads(re.search(r"\{.*\}", out, re.S).group(0))
        if j.get("risk_level") not in LEVELS:
            return None
        j.setdefault("flagged_phrases", [])
        j["engine"] = "Gnani Evon"
        return j
    except Exception:
        return None


def analyze(text: str) -> dict:
    rules = rules_analyze(text)
    llm = llm_analyze(text)
    if not llm:
        return rules
    if rules["risk_level"] == "Emergency" and llm["risk_level"] != "Emergency":
        llm["risk_level"], llm["engine"] = "Emergency", "Gnani Evon + safety rules"
    return llm
