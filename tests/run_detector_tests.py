#!/usr/bin/env python3
import os
import subprocess
import time
import shutil
import csv
from datetime import datetime
import matplotlib.pyplot as plt

# --- Configuration ---
PHASE2_CSV = "TPPhase2_results/covert_channel_results.csv"
PHASE3_ROOT = "TPPhase3_results"
DETECTOR_CSV_IN_CONTAINER = "/code/python-processor/TPPhase3_results/detection_metrics.csv"
WINDOW_SLEEP = 30  # seconds to collect windows

# Ensure Phase 2 has already run
if not os.path.isfile(PHASE2_CSV):
    print(f"❗ Phase 2 results not found at {PHASE2_CSV}. Please run Phase 2 first.")
    exit(1)

os.makedirs(PHASE3_ROOT, exist_ok=True)

print("\n=== Phase 3 Detection Tests ===")
for mode in ("0", "1"):
    print(f"\n▶️  Running detector with COVERT_ACTIVE={mode}")

    # Prepare a fresh sub-directory for this run
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(PHASE3_ROOT, f"{timestamp}-COVERT_ACTIVE_{mode}")
    os.makedirs(run_dir, exist_ok=True)

    # Restart the processor container
    subprocess.run(["docker","restart","-t","2","python-processor"], check=True)

    # Launch the detector inside the container
    subprocess.run([
        "docker","exec","-d","python-processor","bash","-lc",
        f"export COVERT_ACTIVE={mode} && python3 /code/python-processor/main.py"
    ], check=True)

    # Start a steady ping from sec→insec
    print("⏳  Starting steady ping from sec→insec…")
    ping_proc = subprocess.Popen([
        "docker","exec","sec","bash","-lc",
        "ping -i 0.1 -c 300 10.0.0.21"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # If covert‐active, also launch the covert sender
    if mode == "1":
        print("🚨  Launching covert sender in sec…")
        covert_proc = subprocess.Popen([
            "docker","exec","sec","bash","-lc",
            "python3 /code/sec/covert_sender.py "
            "--dest 10.0.0.21 "
            "--message 'Secret: Operation Mincemeat' "
            "--interval 0.2"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Let the detector collect windows
    print(f"⏱  Sleeping {WINDOW_SLEEP}s to let detector build windows…")
    time.sleep(WINDOW_SLEEP)

    # Tear down ping & covert sender
    print("🔪  Stopping ping and covert sender…")
    ping_proc.terminate()
    if mode == "1":
        covert_proc.terminate()

    # Kill the detector inside the container
    print("🔪  Stopping detector process inside container…")
    try:
        subprocess.run([
            "docker","exec","python-processor",
            "bash","-lc",
            "pkill -f 'python3 /code/python-processor/main.py'"
        ], check=True)
    except subprocess.CalledProcessError:
        # pkill sometimes returns 1 if process already gone – ignore
        pass

    # Copy out detection_metrics.csv into our run directory
    host_csv = os.path.join(run_dir, "detection_metrics.csv")
    print("📥  Copying detection CSV out of container…")
    subprocess.run([
        "docker","cp",
        f"python-processor:{DETECTOR_CSV_IN_CONTAINER}",
        host_csv
    ], check=False)

    if not os.path.isfile(host_csv):
        print(f"❌  No detection metrics found in {host_csv}; please inspect your detector logic.")
        continue
    print(f"✅  Detection metrics written to {host_csv}")

    # Parse CSV and generate plots
    with open(host_csv, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"⚠️  Empty detection metrics in {host_csv}, skipping plots.")
        continue

    # Extract columns
    window_ends = [float(r["window_end"]) for r in rows]
    TP = [int(r["TP"]) for r in rows]
    FP = [int(r["FP"]) for r in rows]
    TN = [int(r["TN"]) for r in rows]
    FN = [int(r["FN"]) for r in rows]
    Precision = [float(r["Precision"]) for r in rows]
    Recall = [float(r["Recall"]) for r in rows]
    F1 = [float(r["F1"]) for r in rows]

    # 1) Counts plot
    plt.figure()
    plt.plot(window_ends, TP, label="TP")
    plt.plot(window_ends, FP, label="FP")
    plt.plot(window_ends, TN, label="TN")
    plt.plot(window_ends, FN, label="FN")
    plt.xlabel("Window End (s)")
    plt.ylabel("Count")
    plt.title(f"Detection Counts (COVERT_ACTIVE={mode})")
    plt.legend()
    plt.grid(True)
    counts_path = os.path.join(run_dir, "detection_counts.png")
    plt.savefig(counts_path)
    plt.close()

    # 2) Precision & Recall plot
    plt.figure()
    plt.plot(window_ends, Precision, label="Precision")
    plt.plot(window_ends, Recall, label="Recall")
    plt.xlabel("Window End (s)")
    plt.ylabel("Rate")
    plt.title(f"Precision & Recall (COVERT_ACTIVE={mode})")
    plt.legend()
    plt.grid(True)
    pr_path = os.path.join(run_dir, "precision_recall.png")
    plt.savefig(pr_path)
    plt.close()

    # 3) F1-score plot
    plt.figure()
    plt.plot(window_ends, F1, label="F1")
    plt.xlabel("Window End (s)")
    plt.ylabel("F1 Score")
    plt.title(f"F1 Score (COVERT_ACTIVE={mode})")
    plt.grid(True)
    f1_path = os.path.join(run_dir, "f1_score.png")
    plt.savefig(f1_path)
    plt.close()

    print(f"📊  Plots saved to {run_dir}")

print("\n=== Phase 3 Detection Testing Complete ===")
