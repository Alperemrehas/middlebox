#!/usr/bin/env python3
import os
import subprocess
import time
import csv
from datetime import datetime
import matplotlib.pyplot as plt

# --- Configuration ---
PHASE2_CSV = "TPPhase2_results/covert_channel_results.csv"
PHASE3_ROOT = "TPPhase3_results"
WINDOW_SLEEP = 30  # seconds
PING_CMD = ["docker","exec","sec","bash","-lc","ping -i 0.1 -c 300 10.0.0.21"]
SENDER_CMD = [
    "docker","exec","sec","bash","-lc",
    "python3 /code/sec/covert_sender.py "
    "--dest 10.0.0.21 "
    "--message 'Secret: Operation Mincemeat' "
    "--interval 0.2"
]

# Verify Phase 2 ran
if not os.path.isfile(PHASE2_CSV):
    print(f"❗ Phase 2 results not found at {PHASE2_CSV}. Please run Phase 2 first.")
    exit(1)

# create a single timestamped folder, then subfolders "0/" and "1/"
base_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
base_dir = os.path.join(PHASE3_ROOT, base_ts)
os.makedirs(base_dir, exist_ok=True)

print("\n=== Phase 3 Detection Tests ===")
for mode in ("0", "1"):
    print(f"\n▶️  Running detector with COVERT_ACTIVE={mode}")

    mode_dir = os.path.join(base_dir, mode)
    os.makedirs(mode_dir, exist_ok=True)

    # restart and launch detector
    subprocess.run(["docker","restart","-t","2","python-processor"], check=True)
    subprocess.run([
        "docker","exec","-d","python-processor","bash","-lc",
        f"export COVERT_ACTIVE={mode} && python3 /code/python-processor/main.py"
    ], check=True)

    # steady ping + (maybe) covert sender
    print("⏳  Starting ping from sec→insec…")
    ping_proc = subprocess.Popen(PING_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if mode == "1":
        print("🚨  Launching covert sender…")
        covert_proc = subprocess.Popen(SENDER_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"⏱  Sleeping {WINDOW_SLEEP}s to collect detection windows…")
    time.sleep(WINDOW_SLEEP)

    # tear down
    print("🔪  Stopping ping (and covert sender)…")
    ping_proc.terminate()
    if mode == "1":
        covert_proc.terminate()

    print("🔪  Stopping detector inside container…")
    subprocess.run([
        "docker","exec","python-processor",
        "bash","-lc",
        "pkill -f 'python3 /code/python-processor/main.py'"
    ], check=False)

    # figure out which timestamp folder the container just wrote into
    result = subprocess.run([
        "docker","exec","python-processor",
        "bash","-lc",
        "ls -t /code/python-processor/TPPhase3_results | head -n1"
    ], stdout=subprocess.PIPE, text=True, check=True)
    container_ts = result.stdout.strip()
    container_csv = (
        f"/code/python-processor/TPPhase3_results/"
        f"{container_ts}/detection_metrics.csv"
    )

    host_csv = os.path.join(mode_dir, "detection_metrics.csv")
    print("📥  Copying detection metrics…")
    subprocess.run([
        "docker","cp",
        f"python-processor:{container_csv}",
        host_csv
    ], check=False)

    if not os.path.isfile(host_csv):
        print(f"❌  No detection metrics at {host_csv}; skipping.")
        continue
    print(f"✅  Metrics saved to {host_csv}")

    # load it
    with open(host_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        print("⚠️  Empty CSV; skipping plots.")
        continue

    # extract and convert
    window_ends = [float(r["window_end"]) for r in rows]
    TP_ = [int(r["TP"])   for r in rows]
    FP_ = [int(r["FP"])   for r in rows]
    TN_ = [int(r["TN"])   for r in rows]
    FN_ = [int(r["FN"])   for r in rows]
    P_  = [float(r["Precision"]) for r in rows]
    R_  = [float(r["Recall"])    for r in rows]
    F1_ = [float(r["F1"])        for r in rows]

    # turn timestamps into "seconds since start"
    t0 = window_ends[0]
    rel = [t - t0 for t in window_ends]

    # subsample ~500 points max to thin the lines
    step = max(1, len(rel)//500)
    idxs = list(range(0, len(rel), step))
    x    = [rel[i] for i in idxs]
    th_TP = [TP_[i] for i in idxs]
    th_FP = [FP_[i] for i in idxs]
    th_TN = [TN_[i] for i in idxs]
    th_FN = [FN_[i] for i in idxs]
    th_P  = [P_[i]  for i in idxs]
    th_R  = [R_[i]  for i in idxs]
    th_F1 = [F1_[i] for i in idxs]

    # 1) Counts
    plt.figure()
    plt.plot(x, th_TP, label="TP", lw=0.8, alpha=0.7)
    plt.plot(x, th_FP, label="FP", lw=0.8, alpha=0.7)
    plt.plot(x, th_TN, label="TN", lw=0.8, alpha=0.7)
    plt.plot(x, th_FN, label="FN", lw=0.8, alpha=0.7)
    plt.xlabel("Seconds since start")
    plt.ylabel("Count")
    plt.title(f"Detection Counts (COVERT_ACTIVE={mode})")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(mode_dir, "detection_counts.png"), dpi=150)
    plt.close()

    # 2) Precision / Recall
    plt.figure()
    plt.plot(x, th_P, label="Precision", lw=0.8, alpha=0.7)
    plt.plot(x, th_R, label="Recall",    lw=0.8, alpha=0.7)
    plt.xlabel("Seconds since start")
    plt.ylabel("Rate")
    plt.title(f"Precision & Recall (COVERT_ACTIVE={mode})")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(mode_dir, "precision_recall.png"), dpi=150)
    plt.close()

    # 3) F1 score
    plt.figure()
    plt.plot(x, th_F1, label="F1 Score", lw=0.8, alpha=0.7)
    plt.xlabel("Seconds since start")
    plt.ylabel("F1 Score")
    plt.title(f"F1 Score (COVERT_ACTIVE={mode})")
    plt.grid(True)
    plt.savefig(os.path.join(mode_dir, "f1_score.png"), dpi=150)
    plt.close()

    print(f"📊  Plots saved under {mode_dir}")

print("\n=== Phase 3 Detection Testing Complete ===")
