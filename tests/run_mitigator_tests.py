#!/usr/bin/env python3
import os
import subprocess
import time
import csv
import math
import statistics
import matplotlib.pyplot as plt
from datetime import datetime

# --- CONFIG ---
PHASE4_ROOT = "TPPhase4_results"
INTERVALS   = [0.5, 1.0, 1.5, 2.0]     # seconds
NUM_TRIALS  = 5
MESSAGE     = "Secret: Operation Mincemeat"
BITS        = len(MESSAGE) * 8        # total bits
SLEEP_HEAD  = 2                       # head start for receiver
SLEEP_BETWEEN_TRIALS = 5              # seconds
# ---------------------------------------

def run_capacity_test(mitigate_mode, run_dir):
    """
    Runs NUM_TRIALS for each INTERVAL, toggling MITIGATE_ACTIVE inside
    the python-processor container, and collects capacity bps.
    """
    results = []

    for interval in INTERVALS:
        capacities = []
        for t in range(1, NUM_TRIALS+1):
            print(f"  Trial {t}/{NUM_TRIALS}, interval {interval}s, MITIGATE={mitigate_mode}")

            # 1) Restart & launch processor with mitigation toggle
            subprocess.run(["docker", "restart", "-t", "2", "python-processor"], check=True)
            # kill any old processor
            subprocess.run([
                "docker","exec","python-processor",
                "bash","-lc",
                "pkill -f '/code/python-processor/main.py' || true"
            ], check=False)
            # start it fresh
            subprocess.run([
                "docker","exec","-d","python-processor","bash","-lc",
                f"export MITIGATE_ACTIVE={mitigate_mode} && python3 /code/python-processor/main.py"
            ], check=True)

            # 2) Launch receiver
            recv_cmd = [
                "docker", "exec", "-d", "insec",
                "python3", "/code/insec/covert_receiver.py",
                "--iface", "eth0",
                "--count", str(len(MESSAGE))
            ]
            recv_proc = subprocess.Popen(recv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(SLEEP_HEAD)

            # 3) Run sender & measure elapsed
            start = time.time()
            send_cmd = [
                "docker", "exec", "sec",
                "python3", "/code/sec/covert_sender.py",
                "--dest", "10.0.0.21",
                "--message", MESSAGE,
                "--interval", str(interval)
            ]
            subprocess.run(send_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            elapsed = time.time() - start

            # 4) Stop receiver
            try:
                recv_stdout, recv_stderr = recv_proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                recv_proc.kill()
    

            # 5) Compute capacity
            cap = BITS/elapsed if elapsed > 0 else 0.0
            capacities.append(cap)
            print(f"    => elapsed {elapsed:.2f}s, capacity {cap:.2f}bps")

            time.sleep(SLEEP_BETWEEN_TRIALS)

        # summarize
        avg   = statistics.mean(capacities)
        stdev = statistics.stdev(capacities) if NUM_TRIALS>1 else 0.0
        margin = 1.96*stdev/math.sqrt(NUM_TRIALS)
        results.append((interval, avg, avg-margin, avg+margin))

    # save CSV
    csv_path = os.path.join(run_dir, "mitigation_capacity.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Interval (sec)", "Avg Capacity (bps)", "Lower CI", "Upper CI"])
        writer.writerows(results)
    print(f"  → CSV written to {csv_path}")

    # plot with error bars
    ints, avgs, lows, highs = zip(*results)
    err = [[avg-low for avg,low in zip(avgs,lows)],
           [high-avg for avg,high in zip(avgs,highs)]]

    plt.figure()
    plt.errorbar(ints, avgs, yerr=err, fmt='o-', capsize=5)
    plt.xlabel("Inter-Packet Interval (s)")
    plt.ylabel("Capacity (bps)")
    plt.title(f"Covert Capacity (MITIGATE={mitigate_mode})")
    plt.grid(True)
    plot_path = os.path.join(run_dir, f"capacity_mitigate_{mitigate_mode}.png")
    plt.savefig(plot_path)
    plt.close()
    print(f"  → Plot saved to {plot_path}")

def main():
    os.makedirs(PHASE4_ROOT, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    for mode in (0,1):
        print(f"\n=== Running Phase 4: MITIGATE_ACTIVE={mode} ===")
        run_dir = os.path.join(PHASE4_ROOT, f"{ts}-MITIGATE_{mode}")
        os.makedirs(run_dir, exist_ok=True)
        run_capacity_test(mode, run_dir)
    print("\n=== Phase 4 Mitigation Benchmark Complete ===")

if __name__ == "__main__":
    main()