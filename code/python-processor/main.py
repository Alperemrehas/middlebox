#!/usr/bin/env python3
import os
import time
import csv
import random
import asyncio
from nats.aio.client import Client as NATS
from scapy.all import Ether, IP

# ─── Phase 2: Random‐delay parameters ───────────────────────────────
# in ms; you can still override via ENV if you like
MEAN_DELAY_MS = 200

# ─── Phase 3: Sliding‐window detector parameters ─────────────────────
WINDOW_SIZE = int(os.getenv("DETECTION_WINDOW_SIZE", "20"))
# byte‐string marker to look for
MARKER = os.getenv("DETECTION_MARKER", "CovertChannel").encode()

# ─── Metrics bookkeeping ────────────────────────────────────────────
TP = FP = TN = FN = 0
packet_window = []  # list of (timestamp, is_marker)

# Create one timestamped subfolder under TPPhase3_results
BASE_RESULTS_DIR = "TPPhase3_results"
timestamp = time.strftime("%Y%m%d-%H%M%S")
results_dir = os.path.join(BASE_RESULTS_DIR, timestamp)
os.makedirs(results_dir, exist_ok=True)
csv_path = os.path.join(results_dir, "detection_metrics.csv")

# Write CSV header
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "window_end", "TP", "FP", "TN", "FN",
        "Precision", "Recall", "F1"
    ])


async def run():
    global TP, FP, TN, FN, packet_window

    nc = NATS()
    nats_url = os.getenv("NATS_SURVEYOR_SERVERS", "nats://nats:4222")
    await nc.connect(nats_url)

    async def message_handler(msg):
        global TP, FP, TN, FN, packet_window

        data = msg.data
        pkt = Ether(data)

        # ─── Phase 3: Detection ───────────────────────────────────
        if IP in pkt:
            is_marker = (MARKER in data)

            # slide the window
            packet_window.append((time.time(), is_marker))
            if len(packet_window) > WINDOW_SIZE:
                packet_window.pop(0)

            # once we have a full window, score it
            if len(packet_window) == WINDOW_SIZE:
                decision   = any(flag for (_, flag) in packet_window)
                true_label = decision  # ground truth = actual marker presence

                # update confusion counts
                if decision and true_label:
                    TP += 1
                elif decision and not true_label:
                    FP += 1
                elif not decision and not true_label:
                    TN += 1
                else:
                    FN += 1

                # compute metrics
                precision = TP / (TP + FP) if (TP + FP) else 0.0
                recall    = TP / (TP + FN) if (TP + FN) else 0.0
                f1        = (2 * precision * recall / (precision + recall)
                             if (precision + recall) else 0.0)

                # append to CSV
                with open(csv_path, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        time.time(), TP, FP, TN, FN,
                        round(precision, 3),
                        round(recall,    3),
                        round(f1,        3)
                    ])

                print(f"[Detector] TP={TP} FP={FP} TN={TN} FN={FN} F1={f1:.3f}")

        # ─── Phase 2: Random delay before forwarding ────────────────
        delay = random.uniform(0, MEAN_DELAY_MS / 1000.0)
        await asyncio.sleep(delay)

        # Forward on the correct topic
        out_topic = "outpktinsec" if msg.subject == "inpktsec" else "outpktsec"
        await nc.publish(out_topic, data)


    # subscribe to both directions
    await nc.subscribe("inpktsec",   cb=message_handler)
    await nc.subscribe("inpktinsec", cb=message_handler)

    print(f"Processor running → MEAN_DELAY_MS={MEAN_DELAY_MS} ms  |  WINDOW_SIZE={WINDOW_SIZE}")
    try:
        # just keep it alive
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down…")
        await nc.close()


if __name__ == "__main__":
    asyncio.run(run())