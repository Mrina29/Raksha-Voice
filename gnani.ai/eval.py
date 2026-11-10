"""Clean vs noisy evaluation.

Folder layout:
  clips/clean/01.wav ...
  noise.mp3                      (any traffic/crowd noise)
  labels.csv   columns: file,reference,true_risk     (file = 01.wav ; true_risk in Safe/Concern/Danger/Emergency)

Steps:
  python eval.py --make-noisy noise.mp3      # creates clips/noisy/* using ffmpeg
  python eval.py                             # runs Prisma on both, writes results.csv + summary.csv
"""
import argparse
import os
import subprocess

import jiwer
import pandas as pd

from gnani_client import analyze, stt


def make_noisy(noise):
    os.makedirs("clips/noisy", exist_ok=True)
    for f in sorted(os.listdir("clips/clean")):
        subprocess.run(
            ["ffmpeg", "-y", "-i", f"clips/clean/{f}", "-stream_loop", "-1", "-i", noise,
             "-filter_complex", "[1:a]volume=0.8[n];[0:a][n]amix=inputs=2:duration=first:dropout_transition=0",
             "-ar", "16000", "-ac", "1", f"clips/noisy/{os.path.splitext(f)[0]}.wav"],
            check=True, capture_output=True)
    print("noisy clips created")


def norm(s):
    return " ".join(str(s).lower().replace("।", " ").replace(".", " ").replace(",", " ").replace("?", " ").split())


def run():
    labels = pd.read_csv("labels.csv")
    rows = []
    for cond in ("clean", "noisy"):
        for _, r in labels.iterrows():
            stem = os.path.splitext(r["file"])[0]
            p = f"clips/{cond}/{stem}.wav" if os.path.exists(f"clips/{cond}/{stem}.wav") else f"clips/{cond}/{r['file']}"
            if not os.path.exists(p):
                continue
            hyp, _ = stt(open(p, "rb").read(), os.path.basename(p))
            pred = analyze(hyp)["risk_level"]
            rows.append({"file": r["file"], "condition": cond, "reference": r["reference"], "hypothesis": hyp,
                         "wer": round(jiwer.wer(norm(r["reference"]), norm(hyp)), 3),
                         "true_risk": r["true_risk"], "pred_risk": pred, "correct": pred == r["true_risk"]})
            print(cond, r["file"], rows[-1]["wer"], pred)
    df = pd.DataFrame(rows)
    df.to_csv("results.csv", index=False)
    s = df.groupby("condition").agg(clips=("file", "count"), avg_WER=("wer", "mean"),
                                   threat_accuracy=("correct", "mean")).reset_index()
    s["transcription_accuracy_%"] = ((1 - s["avg_WER"]).clip(lower=0) * 100).round(1)
    s["threat_accuracy_%"] = (s["threat_accuracy"] * 100).round(1)
    s = s[["condition", "clips", "transcription_accuracy_%", "threat_accuracy_%"]]
    s.to_csv("summary.csv", index=False)
    print(s.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--make-noisy")
    a = ap.parse_args()
    make_noisy(a.make_noisy) if a.make_noisy else run()
