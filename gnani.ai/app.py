import datetime as dt
import html
import os

import pandas as pd
import streamlit as st

from gnani_client import LANG_NAMES, LEVELS, analyze, detect_script, reply_for, stt, tts

st.set_page_config(page_title="Raksha Voice · Emergency Intelligence", page_icon="🛡️", layout="wide")

COLORS = {"Safe": "#2ecc71", "Concern": "#f4c430", "Danger": "#ff8c1a", "Emergency": "#ff3b4e"}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Playfair+Display:wght@700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: radial-gradient(1200px 600px at 10% -10%, #1b2a4a 0%, #0b1220 55%) fixed; color:#e8ecf5; }
header[data-testid="stHeader"] { background: transparent; }
.hero { padding: 26px 30px; border-radius: 18px; border:1px solid #243558;
  background: linear-gradient(135deg, rgba(27,42,74,.85), rgba(11,18,32,.9)); margin-bottom: 18px; }
.hero h1 { font-family:'Playfair Display',serif; font-size:2.6rem; margin:0; color:#fff; letter-spacing:.5px;}
.hero h1 span { color:#ff3b4e; }
.hero p { margin:.4rem 0 0 0; color:#a9b6d3; font-size:1.02rem; }
.pill { display:inline-block; padding:4px 12px; margin:10px 8px 0 0; border-radius:999px; font-size:.78rem;
  border:1px solid #2f4478; color:#c9d6f5; background:#14213d; }
.card { border:1px solid #243558; border-radius:16px; padding:18px 20px; background:rgba(20,33,61,.7); margin-bottom:14px; }
.card h3 { margin:0 0 8px 0; font-size:.8rem; letter-spacing:1.6px; text-transform:uppercase; color:#7f93c0; }
.meter { display:flex; gap:8px; margin:6px 0 10px 0; }
.seg { flex:1; height:30px; border-radius:8px; background:#1d2b4a; }
.lvl { font-size:2.1rem; font-weight:800; letter-spacing:1px; }
.alert { border-left:5px solid #ff3b4e; background:rgba(255,59,78,.12); padding:14px 16px; border-radius:10px; }
.soft { border-left:5px solid #f4c430; background:rgba(244,196,48,.1); padding:14px 16px; border-radius:10px; }
.step { display:inline-block; padding:6px 12px; margin:4px 6px 0 0; border-radius:8px; background:#14213d;
  border:1px solid #2f4478; font-size:.82rem; color:#c9d6f5;}
.tr { font-size:1.15rem; line-height:1.6; padding:12px 14px; border-radius:10px; background:#0e1730; border:1px solid #243558;}
.helpline b { color:#ff8c9a; font-size:1.05rem; }
div.stButton > button { border-radius:10px; font-weight:700; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🛡️ Raksha <span>Voice</span></h1>
  <p>Voice-first Emergency Intelligence for Low-Resource Languages — speak in your own language, in any noise.</p>
  <span class="pill">🎙️ Gnani Prisma v3.0 · speech-to-text + language detection</span>
  <span class="pill">🧠 Threat triage · 4-level risk meter</span>
  <span class="pill">🔊 Gnani Timbre v3.0 · calm spoken reply</span>
  <span class="pill">📄 Instant incident report</span>
</div>
""", unsafe_allow_html=True)

if not os.getenv("GNANI_API_KEY"):
    st.error("GNANI_API_KEY is not set. Set it and restart:  `export GNANI_API_KEY=your_key`")
    st.stop()

SAMPLES = {
    "— choose a sample —": "",
    "Hinglish · being followed": "Koi mera peecha kar raha hai bahut der se, mujhe darr lag raha hai, main akeli hoon",
    "Hindi · emergency": "बचाओ! उसके पास चाकू है, वो मुझे मार डालेगा, जल्दी मदद भेजो",
    "Tamil · harassment": "ஒருவன் என்னை பின்தொடர்கிறான், எனக்கு பயமா இருக்கு, தயவு செய்து உதவுங்கள்",
    "English · uncomfortable": "I am alone in a cab late at night and the driver is acting weird, I feel unsafe",
}

with st.sidebar:
    st.markdown("### ⚙️ Settings")
    voice = st.selectbox("Reply voice (Timbre v3.0)", ["Shivani", "Chetana", "Kalpana", "Tarika", "Avinash", "Prakash"])
    trusted = st.text_input("Trusted contact (demo)", "Mom · +91 98XXXXXX10")
    st.markdown("### 📞 India helplines")
    st.markdown("""<div class="helpline">Emergency <b>112</b><br>Women helpline <b>1091</b><br>
    Women in distress <b>181</b><br>Police <b>100</b><br>Cyber crime <b>1930</b></div>""", unsafe_allow_html=True)
    st.caption("Raksha Voice is a decision-support prototype. In real danger, call 112.")


def meter(level):
    n = LEVELS.index(level) + 1
    segs = "".join(f'<div class="seg" style="background:{COLORS[LEVELS[i]] if i < n else "#1d2b4a"}"></div>' for i in range(4))
    return (f'<div class="card"><h3>Risk meter</h3><div class="meter">{segs}</div>'
            f'<div class="lvl" style="color:{COLORS[level]}">{level.upper()}</div></div>')


def report_html(res, transcript, lang, now):
    e = html.escape
    rows = [("Risk level", res["risk_level"]), ("Threat type", res.get("threat_type", "")),
            ("Location mentioned", res.get("location", "")), ("Language", LANG_NAMES.get(lang, lang)),
            ("Summary", res.get("summary", "")), ("Flagged phrases", ", ".join(res.get("flagged_phrases", []))),
            ("Transcript (Gnani Prisma v3.0)", transcript), ("Analysis engine", res.get("engine", ""))]
    tr = "".join(f"<tr><td><b>{e(a)}</b></td><td>{e(str(b))}</td></tr>" for a, b in rows)
    return (f'<html><head><meta charset="utf-8"><title>Incident Report</title><style>'
            f"body{{font-family:Arial,'Noto Sans Tamil','Noto Sans Devanagari',sans-serif;max-width:780px;margin:30px auto}}"
            f"td{{padding:8px 12px;border:1px solid #ccc;vertical-align:top}}h1{{color:#c62828}}</style></head><body>"
            f"<h1>Incident Report (Draft)</h1><p>Generated by Raksha Voice · {e(now)}</p><table>{tr}</table>"
            f'<p style="color:#666;font-size:12px">AI-generated draft for assistance. Verify before filing. '
            f"Print this page to save as PDF.</p></body></html>")


def show_result(transcript, lang, source):
    with st.spinner("Triage…"):
        res = analyze(transcript)
    text, reply_lang = reply_for(res["risk_level"], lang)
    now = dt.datetime.now().strftime("%d %b %Y, %I:%M %p IST")
    a, b = st.columns([1, 1])
    with a:
        st.markdown(f'<div class="card"><h3>Transcript · {source}</h3><div class="tr">{html.escape(transcript) or "(empty)"}</div>'
                    f'<div style="margin-top:8px;color:#a9b6d3">Detected language: <b>{LANG_NAMES.get(lang, lang)}</b></div></div>',
                    unsafe_allow_html=True)
    with b:
        st.markdown(meter(res["risk_level"]), unsafe_allow_html=True)
    flagged = ", ".join(f"<code>{html.escape(p)}</code>" for p in res.get("flagged_phrases", [])) or "—"
    st.markdown(f'<div class="card"><h3>Assessment</h3><b>Threat:</b> {html.escape(str(res.get("threat_type")))}'
                f' &nbsp;·&nbsp; <b>Location:</b> {html.escape(str(res.get("location")))}'
                f' &nbsp;·&nbsp; <b>Engine:</b> {html.escape(str(res.get("engine")))}<br><b>Flagged:</b> {flagged}</div>',
                unsafe_allow_html=True)
    c, d = st.columns([1, 1])
    with c:
        st.markdown(f'<div class="card"><h3>Spoken reply · Timbre v3.0 · {voice}</h3>{html.escape(text)}</div>',
                    unsafe_allow_html=True)
        try:
            with st.spinner("Timbre: speaking…"):
                st.audio(tts(text, reply_lang, voice), format="audio/wav", autoplay=True)
        except Exception as ex:
            st.warning(f"Voice reply unavailable: {ex}")
    with d:
        lvl = LEVELS.index(res["risk_level"])
        if lvl >= 2:
            st.markdown(f'<div class="alert">🚨 <b>ALERT DISPATCHED (simulated)</b><br>To: {html.escape(trusted)}<br>'
                        f'Time: {now}<br>{html.escape(str(res.get("summary")))}<br><b>Call 112 / 1091 now.</b></div>',
                        unsafe_allow_html=True)
        elif lvl == 1:
            st.markdown(f'<div class="soft">⚠️ Soft check-in sent (simulated) to {html.escape(trusted)} at {now}</div>',
                        unsafe_allow_html=True)
        else:
            st.success("No alert needed.")
        st.download_button("⬇️ Download incident report", report_html(res, transcript, lang, now),
                           file_name="incident_report.html", mime="text/html")


tab1, tab2, tab3 = st.tabs(["🎙️ Live triage", "📊 Clean vs Noisy results", "ℹ️ How it works"])

with tab1:
    st.markdown("**Step 1 — give a distress voice note** (upload or record). Works in Tamil, Hindi, Hinglish and more.")
    c1, c2 = st.columns([1, 1])
    with c1:
        up = st.file_uploader("Upload audio", type=["wav", "mp3", "m4a", "ogg", "flac", "aac"])
    with c2:
        rec = st.audio_input("…or record now") if hasattr(st, "audio_input") else None
    audio = rec or up
    if st.button("🔍 Analyze voice", type="primary", disabled=audio is None, use_container_width=True):
        try:
            with st.spinner("Prisma v3.0: transcribing + detecting language…"):
                transcript, body = stt(audio.getvalue(), getattr(audio, "name", "audio.wav") or "audio.wav")
        except Exception as ex:
            st.error(str(ex))
            st.stop()
        lang = body.get("detected_language_code") or detect_script(transcript)
        show_result(transcript, lang, "Gnani Prisma v3.0")

    st.markdown("---")
    st.markdown("**No audio handy?** Try a sample scenario (skips speech-to-text, uses the same triage + voice reply):")
    choice = st.selectbox("Sample scenario", list(SAMPLES.keys()), label_visibility="collapsed")
    if SAMPLES[choice] and st.button("▶️ Run sample", use_container_width=True):
        show_result(SAMPLES[choice], detect_script(SAMPLES[choice]), "typed sample")

with tab2:
    st.markdown("Robustness check: the same clips, clean vs. mixed with street noise. **All numbers below were measured by `eval.py`.**")
    if os.path.exists("summary.csv"):
        st.table(pd.read_csv("summary.csv"))
    if os.path.exists("results.csv"):
        st.dataframe(pd.read_csv("results.csv"), use_container_width=True)
    if not os.path.exists("results.csv"):
        st.info("Run `python eval.py` to generate results.")

with tab3:
    st.markdown("""
<div class="card"><h3>Pipeline</h3>
<span class="step">1 · Voice in</span>→<span class="step">2 · Prisma v3.0 STT + auto language</span>→
<span class="step">3 · Threat triage (4 levels)</span>→<span class="step">4 · Timbre v3.0 reply in caller's language</span>→
<span class="step">5 · Alert + incident report</span></div>
<div class="card"><h3>Who it helps</h3>Women facing street harassment · elderly living alone · campus safety cells ·
helpline operators · rural emergency reporting where typing in English is not an option.</div>
<div class="card"><h3>Built with</h3>Gnani Prisma v3.0 (speech-to-text) · Gnani Timbre v3.0 (text-to-speech) ·
Python · Streamlit. Optional: Gnani Evon for LLM triage when a hosted endpoint is configured.</div>
""", unsafe_allow_html=True)
