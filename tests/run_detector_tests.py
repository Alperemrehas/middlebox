#!/usr/bin/env python3
import subprocess
import time
import os
import csv
from pathlib import Path
import matplotlib.pyplot as plt

# --- Determine paths ---
# This script and run_covert_tests.py live in the same directory
HERE = Path(__file__).resolve().parent
PHASE2_RUNNER = HERE / "run_covert_tests.py"

# Detection results directory
DET_RESULTS_DIR = HERE / "TPPhase3_results"
DET_RESULTS_DIR.mkdir(exist_ok=True)

# CSV file written by the processor
detector_csv = DET_RESULTS_DIR / "detection_metrics.csv"

# Helper: restart the python-processor with COVERT_ACTIVE flag
def restart_processor(covert_on: bool):
    flag = "1" if covert_on else "0"
    print(f"\nRestarting python-processor (COVERT_ACTIVE={flag})...")
    # Export the flag and restart in one shell invocation
    subprocess.run(
        ["bash", "-lc", f"export COVERT_ACTIVE={flag}; docker compose restart python-processor"],
        check=True
    )
    time.sleep(5)  # allow time to subscribe

# 1) Positive (covert-on) run
restart_processor(covert_on=True)
print("Generating covert traffic for detection…")
if not PHASE2_RUNNER.exists():
    raise FileNotFoundError(f"{PHASE2_RUNNER} does not exist")
subprocess.run(
    ["python3", str(PHASE2_RUNNER)],
    cwd=str(HERE),  # ensure we run in the correct folder
    check=True
)

# Wait for the detector windows to fill
time.sleep(10)

# 2) Negative (covert-off) run
restart_processor(covert_on=False)
print("Generating benign traffic for detection…")
subprocess.run(
    ["docker", "exec", "sec", "ping", "-c", "200", "insec"],
    check=True
)
time.sleep(10)

# 3) Load and summarize detection metrics
print("\nLoading detection metrics…")
records = []
if detector_csv.exists():
    with open(detector_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
else:
    print(f"No detector CSV found at {detector_csv}")

if records:
    last = records[-1]
    TP = int(last.get("TP", 0))
    FP = int(last.get("FP", 0))
    TN = int(last.get("TN", 0))
    FN = int(last.get("FN", 0))
    precision = float(last.get("Precision", 0))
    recall = float(last.get("Recall", 0))
    f1 = float(last.get("F1", 0))
    print(f"Final confusion counts: TP={TP}, FP={FP}, TN={TN}, FN={FN}")
    print(f"Precision={precision:.3f}, Recall={recall:.3f}, F1-score={f1:.3f}")
else:
    print("No detection records found.")

# 4) Plot Precision & Recall over time
if records:
    print("Plotting Precision and Recall over time…")
    times = [float(r["window_end"]) for r in records]
    precisions = [float(r["Precision"]) for r in records]
    recalls = [float(r["Recall"]) for r in records]

    plt.figure()
    plt.plot(times, precisions, label="Precision")
    plt.plot(times, recalls, label="Recall")
    plt.xlabel("Timestamp")
    plt.ylabel("Metric Value")
    plt.title("Detector Precision & Recall over Time")
    plt.legend()
    plt.grid(True)

    plot_path = DET_RESULTS_DIR / "precision_recall_over_time.png"
    plt.savefig(plot_path)
    print(f"Plot saved to {plot_path}")
    plt.show()
else:
    print("Skipping plot: no records to display.")
