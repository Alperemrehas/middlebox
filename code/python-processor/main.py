#!/usr/bin/env python3
import asyncio
import os, time, csv, random
from nats.aio.client import Client as NATS
from scapy.all import Ether, IP

# --- Phase 3 Heuristic Detector Parameters ---
WINDOW_SIZE      = 20
THRESHOLD_RATIO  = 0.8
PRINTABLE_RANGE  = range(32, 127)  # ASCII printable

# --- Detection Metrics ---
TP = FP = TN = FN = 0
packet_window = []  # list of tuples: (timestamp, ip_id, is_covert_label)

# --- Output Setup ---
results_dir = "TPPhase3_results"
os.makedirs(results_dir, exist_ok=True)
csv_path = os.path.join(results_dir, "detection_metrics.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "window_end", "TP", "FP", "TN", "FN",
        "Precision", "Recall", "F1"
    ])

# --- Phase 1 Delay Parameter (unchanged) ---
MEAN_DELAY_MS = 200  # or your chosen default

def is_printable(ip_id):
    return ip_id in PRINTABLE_RANGE

def analyze_window():
    """Return True if current window is classified as covert."""
    printable = sum(1 for (_, ip_id, _) in packet_window if is_printable(ip_id))
    return (printable / len(packet_window)) >= THRESHOLD_RATIO

async def run():
    global TP, FP, TN, FN, packet_window

    # NATS connection
    nc = NATS()
    nats_url = os.getenv("NATS_SURVEYOR_SERVERS", "nats://nats:4222")
    await nc.connect(nats_url)

    async def message_handler(msg):
        nonlocal nc
        global TP, FP, TN, FN, packet_window

        pkt = Ether(msg.data)
        # Determine whether covert should be considered active
        covert_active = (os.getenv("COVERT_ACTIVE", "0") == "1")

        # Heuristic: only apply on IP packets
        if IP in pkt:
            ip_id = pkt[IP].id
            # Append (timestamp, id, label) to window
            packet_window.append((time.time(), ip_id, covert_active))
            if len(packet_window) > WINDOW_SIZE:
                packet_window.pop(0)

            # Once full window collected, analyze
            if len(packet_window) == WINDOW_SIZE:
                decision   = analyze_window()
                # true label: majority of window’s labels
                true_label = sum(1 for (_, _, lab) in packet_window) >= (WINDOW_SIZE/2)

                # update confusion counts
                if decision and true_label:    TP += 1
                elif decision and not true_label: FP += 1
                elif not decision and not true_label: TN += 1
                else:                           FN += 1

                # compute metrics
                precision = TP / (TP + FP) if (TP + FP) else 0
                recall    = TP / (TP + FN) if (TP + FN) else 0
                f1        = (2 * precision * recall / (precision + recall)
                             if (precision + recall) else 0)

                # log to CSV
                with open(csv_path, "a", newline="") as f:
                    csv.writer(f).writerow([
                        time.time(), TP, FP, TN, FN,
                        round(precision, 3),
                        round(recall,    3),
                        round(f1,        3)
                    ])
                print(f"[Detector] TP={TP} FP={FP} TN={TN} FN={FN} F1={f1:.3f}")

        # Phase 1 delay logic (unchanged)
        delay = random.uniform(0, MEAN_DELAY_MS / 1000.0)
        await asyncio.sleep(delay)

        # Forward packet to opposite topic
        out_topic = "outpktinsec" if msg.subject == "inpktsec" else "outpktsec"
        await nc.publish(out_topic, msg.data)

    # Subscribe to both streams
    await nc.subscribe("inpktsec",   cb=message_handler)
    await nc.subscribe("inpktinsec", cb=message_handler)
    print("Processor + Detector subscribed; running...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        await nc.close()

if __name__ == "__main__":
    asyncio.run(run())
