#!/usr/bin/env python3
import subprocess
import time
import csv
import math
import statistics
import matplotlib.pyplot as plt
import argparse
import os

# Ensure the output directory exists.
output_dir = "TPPhase2_results"
os.makedirs(output_dir, exist_ok=True)

# List of inter-packet interval values (in seconds) to test.
# (A smaller interval means more packets per second.)
intervals = [0.5, 1.0, 1.5, 2.0]

# Number of trials to run for each interval.
num_trials = 5

# The covert message to send (WWII).
covert_message = "Secret: Operation Mincemeat"
# Calculate message length in bits (each character is 8 bits).
message_length_bits = len(covert_message) * 8

def run_covert_sender(interval):
    """
    Calls the covert sender with the given inter-packet interval.
    Returns a tuple: (elapsed time in seconds, sender output log as a string).
    """
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

def run_covert_receiver(packet_count, timeout=20):
    """
    Calls the covert receiver to capture a specified number of packets.
    A timeout (in seconds) is used to prevent the call from hanging indefinitely.
    Returns the receiver output log as a string.
    """
    cmd = [
        "docker", "exec", "insec", "python3",
        "/code/insec/covert_receiver.py",
        "--iface", "eth0",  
        "--count", str(packet_count)
    ]
    print(f"Running covert receiver to capture {packet_count} packets with timeout {timeout} sec...")
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        receiver_output = result.stdout
        if result.stderr:
            receiver_output += "\nError: " + result.stderr
            print("Receiver Error:", result.stderr)
    except subprocess.TimeoutExpired as e:
        receiver_output = e.stdout or ""
        receiver_output += "\nError: Receiver command timed out."
        print("Receiver command timed out.")
    return receiver_output

# For each inter-packet interval, perform several trials and compute throughput.
results = []  # Each element: (interval, avg_capacity_bps, lower_ci, upper_ci)
trial_results = {}  # Map: interval -> list of measured capacities (bps)

# I assume one covert packet per character.
receiver_count = len(covert_message)

for interval in intervals:
    capacities = []
    print(f"\nTesting covert channel with interval: {interval} sec")
    for trial in range(1, num_trials + 1):
        print(f"Trial {trial}/{num_trials} for interval {interval} sec:")
        
        # Run covert sender and capture its output and elapsed time.
        elapsed, sender_log = run_covert_sender(interval)
        
        # Save sender output log to a file.
        sender_log_filename = f"sent_interval_{interval}_trial_{trial}.txt"
        sender_log_path = os.path.join(output_dir, sender_log_filename)
        with open(sender_log_path, "w") as f:
            f.write(sender_log)
        print(f"Sender log saved to {sender_log_path}")
        
        # Calculate capacity in bits per second.
        capacity = message_length_bits / elapsed if elapsed > 0 else 0
        print(f"Elapsed time: {elapsed:.3f} sec, Capacity: {capacity:.2f} bps")
        capacities.append(capacity)
        
        # Run covert receiver to capture the covert packets.
        receiver_log = run_covert_receiver(receiver_count, timeout=20)
        receiver_log_filename = f"received_interval_{interval}_trial_{trial}.txt"
        receiver_log_path = os.path.join(output_dir, receiver_log_filename)
        with open(receiver_log_path, "w") as f:
            f.write(receiver_log)
        print(f"Receiver log saved to {receiver_log_path}")
        
        # Wait briefly before running the next trial.
        time.sleep(5)
    
    trial_results[interval] = capacities
    # Compute average capacity and 95% confidence interval.
    avg = statistics.mean(capacities)
    stdev = statistics.stdev(capacities) if len(capacities) > 1 else 0
    error_margin = 1.96 * stdev / math.sqrt(num_trials) if num_trials > 1 else 0
    lower_ci = avg - error_margin
    upper_ci = avg + error_margin
    results.append((interval, avg, lower_ci, upper_ci))

# Save summary results to a CSV file.
csv_path = os.path.join(output_dir, "covert_channel_results.csv")
with open(csv_path, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Interval (sec)", "Avg Capacity (bps)", "Lower CI (bps)", "Upper CI (bps)"])
    writer.writerows(results)
print(f"CSV results saved to {csv_path}")

# Plot results and save the plot in the same folder.
if results:
    intervals_plot, avg_capacities, lower_cis, upper_cis = zip(*results)
    
    # Compute symmetric error bars.
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
    plt.show()
    print(f"Plot saved to {plot_path}")
else:
    print("No results to plot.")
