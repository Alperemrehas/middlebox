#!/usr/bin/env python3
import subprocess
import time
import csv
import math
import statistics
import matplotlib.pyplot as plt
import os


# Standardized output directory name.
output_dir = "TPPhase2_results"
os.makedirs(output_dir, exist_ok=True)

# List of inter-packet interval values (in seconds) to test.
intervals = [0.5, 1.0, 1.5, 2.0]
num_trials = 5

# The covert message to send.
covert_message = "Secret: Operation Mincemeat"
message_length_bits = len(covert_message) * 8
receiver_count = len(covert_message)

def run_covert_sender(interval):
    
    cmd = [
        "docker", "exec", "sec", "python3",
        "/code/sec/covert_sender.py",
        "--dest", "10.0.0.21",
        "--message", covert_message,
        "--interval", str(interval)
    ]
    print(f"Running covert sender with interval {interval} sec...")
    start = time.time()
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    end = time.time()
    elapsed = end - start
    sender_output = result.stdout
    if result.stderr:
        sender_output += "\nError: " + result.stderr
        print("Sender Error:", result.stderr)
    return elapsed, sender_output

results = []
trial_results = {}

for interval in intervals:
    capacities = []
    print(f"\nTesting covert channel with interval: {interval} sec")
    for trial in range(1, num_trials + 1):
        print(f"Trial {trial}/{num_trials} for interval {interval} sec:")

        # Launch receiver in background first
        receiver_cmd = [
            "docker", "exec", "insec", "python3",
            "/code/insec/covert_receiver.py",
            "--iface", "eth0",
            "--count", str(receiver_count)
        ]
        print(f"Starting covert receiver to capture {receiver_count} packets...")
        receiver_proc = subprocess.Popen(receiver_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        time.sleep(2)
        elapsed, sender_log = run_covert_sender(interval)

        # Ensure the receiver is still running before sending the message
        sender_log_filename = f"sent_interval_{interval}_trial_{trial}.txt"
        sender_log_path = os.path.join(output_dir, sender_log_filename)
        with open(sender_log_path, "w") as f:
            f.write(sender_log)
        print(f"Sender log saved to {sender_log_path}")

        try:
            # Increased timeout to prevent premature process killing
            receiver_stdout, receiver_stderr = receiver_proc.communicate(timeout=60)
            receiver_log = receiver_stdout + ("\nError: " + receiver_stderr if receiver_stderr else "")
        except subprocess.TimeoutExpired:
            receiver_proc.kill()
            receiver_log = "Error: Receiver command timed out."
            print(receiver_log)

        receiver_log_filename = f"received_interval_{interval}_trial_{trial}.txt"
        receiver_log_path = os.path.join(output_dir, receiver_log_filename)
        with open(receiver_log_path, "w") as f:
            f.write(receiver_log)
        print(f"Receiver log saved to {receiver_log_path}")

        capacity = message_length_bits / elapsed if elapsed > 0 else 0
        print(f"Elapsed time: {elapsed:.3f} sec, Capacity: {capacity:.2f} bps")
        capacities.append(capacity)
        time.sleep(5)

    trial_results[interval] = capacities
    avg = statistics.mean(capacities)
    stdev = statistics.stdev(capacities) if len(capacities) > 1 else 0
    error_margin = 1.96 * stdev / math.sqrt(num_trials) if num_trials > 1 else 0
    lower_ci = avg - error_margin
    upper_ci = avg + error_margin
    results.append((interval, avg, lower_ci, upper_ci))

csv_path = os.path.join(output_dir, "covert_channel_results.csv")
with open(csv_path, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Interval (sec)", "Avg Capacity (bps)", "Lower CI (bps)", "Upper CI (bps)"])
    writer.writerows(results)
print(f"CSV results saved to {csv_path}")

if results:
    intervals_plot, avg_capacities, lower_cis, upper_cis = zip(*results)
    error_bars = [
        [avg - low for avg, low in zip(avg_capacities, lower_cis)],
        [up - avg for avg, up in zip(avg_capacities, upper_cis)]
    ]
    plt.errorbar(intervals_plot, avg_capacities, yerr=error_bars, fmt='o-', capsize=5)
    plt.xlabel("Inter-Packet Interval (sec)")
    plt.ylabel("Covert Channel Capacity (bps)")
    plt.title("Covert Channel Capacity vs Inter-Packet Interval")
    plt.grid(True)
    plot_path = os.path.join(output_dir, "covert_channel_capacity.png")
    plt.savefig(plot_path)
    plt.show(block=False)
    print(f"Plot saved to {plot_path}")
else:
    print("No results to plot.")