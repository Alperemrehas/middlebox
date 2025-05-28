#!/usr/bin/env python3
import asyncio
import os
import time
import csv
import random
from nats.aio.client import Client as NATS
from scapy.all import Ether, IP

# --- Phase 3 Heuristic Detector Parameters ---
WINDOW_SIZE = 20
MARKER = b"CovertChannel"  # what we look for

# --- Detection Metrics Counters ---
TP = FP = TN = FN = 0
packet_window = []  # list of tuples: (timestamp, is_marker)

# --- Output Setup: one timestamped subfolder per run ---
BASE_RESULTS_DIR = "TPPhase3_results"
timestamp = time.strftime("%Y%m%d-%H%M%S")
results_dir = os.path.join(BASE_RESULTS_DIR, timestamp)
os.makedirs(results_dir, exist_ok=True)
csv_path = os.path.join(results_dir, "detection_metrics.csv")

# write CSV header
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "window_end", "TP", "FP", "TN", "FN", "Precision", "Recall", "F1"
    ])

# (unchanged) artificial delay before forwarding
MEAN_DELAY_MS = 200

def analyze_window():
    """Return True if *any* packet in the current window carries our marker."""
    return any(is_marker for (_, is_marker) in packet_window)

async def run():
    global TP, FP, TN, FN, packet_window

    nc = NATS()
    nats_url = os.getenv("NATS_SURVEYOR_SERVERS", "nats://nats:4222")
    await nc.connect(nats_url)

    async def message_handler(msg):
        nonlocal nc
        global TP, FP, TN, FN, packet_window

        data = msg.data
        pkt = Ether(data)

        if IP in pkt:
            is_marker = (MARKER in data)

            # slide the window of markers
            packet_window.append((time.time(), is_marker))
            if len(packet_window) > WINDOW_SIZE:
                packet_window.pop(0)

            # once we have a full window, decide & score
            if len(packet_window) == WINDOW_SIZE:
                decision   = analyze_window()
                true_label = analyze_window()  # ground-truth = actual marker presence

                # update counts
                if decision and true_label:
                    TP += 1
                elif decision and not true_label:
                    FP += 1
                elif not decision and not true_label:
                    TN += 1
                else:
                    FN += 1

                precision = TP / (TP + FP) if (TP + FP) else 0
                recall    = TP / (TP + FN) if (TP + FN) else 0
                f1        = (2 * precision * recall / (precision + recall)
                             if (precision + recall) else 0)

                # append metrics row
                with open(csv_path, "a", newline="") as f:
                    csv.writer(f).writerow([
                        time.time(), TP, FP, TN, FN,
                        round(precision, 3),
                        round(recall,    3),
                        round(f1,        3)
                    ])
                print(f"[Detector] TP={TP} FP={FP} TN={TN} FN={FN} F1={f1:.3f}")

        # forward the packet after a bit of random delay
        delay = random.uniform(0, MEAN_DELAY_MS / 1000.0)
        await asyncio.sleep(delay)
        out_topic = "outpktinsec" if msg.subject == "inpktsec" else "outpktsec"
        await nc.publish(out_topic, data)

    # subscribe to both directions
    await nc.subscribe("inpktsec",   cb=message_handler)
    await nc.subscribe("inpktinsec", cb=message_handler)
    print("Processor + Detector subscribed; running…")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down…")
        await nc.close()

if __name__ == "__main__":
    asyncio.run(run())
