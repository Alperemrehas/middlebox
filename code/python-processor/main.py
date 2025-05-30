#!/usr/bin/env python3
import os
import random
import asyncio
import csv
from scapy.all import Ether, IP, Raw
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

# Environment flags
MITIGATE_ACTIVE = os.getenv("MITIGATE_ACTIVE", "0") == "1"
COVERT_ACTIVE   = os.getenv("COVERT_ACTIVE",   "0") == "1"

# Metrics output
METRICS_FILE = "/code/python-processor/TPPhase3_results/detection_metrics.csv"
WINDOW_SIZE  = float(os.getenv("DETECTION_WINDOW", "1.0"))  # seconds
STEP_SIZE    = float(os.getenv("DETECTION_STEP",   "0.2"))  # seconds

class PacketProcessor:
    def __init__(self):
        self.nc = NATS()
        # sliding‐window counters
        self.window_start = asyncio.get_event_loop().time()
        self.TP = self.FP = self.TN = self.FN = 0
        # write header
        os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
        with open(METRICS_FILE, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["window_end","TP","FP","TN","FN","Precision","Recall","F1"])

    def _apply_mitigation(self, pkt):
        """
        Erase any covert‐channel data by reseeding the IP ID.
        """
        if MITIGATE_ACTIVE and IP in pkt:
            pkt[IP].id = random.randint(0, 0xFFFF)
        return pkt

    def _score_packet(self, saw_covert):
        """
        Simple heuristic: if COVERT_ACTIVE we expect a covert‐tagged packet.
        Here we assume 'saw_covert' is True if we detected the marker.
        """
        if COVERT_ACTIVE:
            if saw_covert:
                self.TP += 1
            else:
                self.FN += 1
        else:
            if saw_covert:
                self.FP += 1
            else:
                self.TN += 1

    def _maybe_write_metrics(self):
        """
        On each STEP_SIZE, dump a new line of metrics.
        """
        now = asyncio.get_event_loop().time()
        if now - self.window_start >= STEP_SIZE:
            precision = self.TP / (self.TP + self.FP) if (self.TP + self.FP) else 1.0
            recall    = self.TP / (self.TP + self.FN) if (self.TP + self.FN) else 1.0
            f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            with open(METRICS_FILE, "a") as f:
                writer = csv.writer(f)
                writer.writerow([
                    self.window_start + WINDOW_SIZE,
                    self.TP, self.FP, self.TN, self.FN,
                    round(precision, 3),
                    round(recall,    3),
                    round(f1,        3)
                ])
            # slide window
            self.window_start += STEP_SIZE
            # reset counts for next window
            self.TP = self.FP = self.TN = self.FN = 0

    async def _handle_upstream(self, msg: Msg):
        pkt = Ether(msg.data)
        # 1) Mitigate if requested
        pkt = self._apply_mitigation(pkt)
        # 2) Detection: look for your covert marker
        saw_covert = Raw in pkt and b"CovertChannel" in bytes(pkt[Raw].load)
        self._score_packet(saw_covert)
        self._maybe_write_metrics()
        # 3) Forward packet on
        await self.nc.publish("to-insec", bytes(pkt))

    async def _handle_downstream(self, msg: Msg):
        pkt = Ether(msg.data)
        pkt = self._apply_mitigation(pkt)
        saw_covert = Raw in pkt and b"CovertChannel" in bytes(pkt[Raw].load)
        self._score_packet(saw_covert)
        self._maybe_write_metrics()
        await self.nc.publish("to-sec", bytes(pkt))

async def main():
    proc = PacketProcessor()
    nc = proc.nc
    await nc.connect(os.getenv("NATS_URL", "nats://127.0.0.1:4222"))

    # subscribe to directions
    await nc.subscribe("sec-to-processor", cb=proc._handle_upstream)
    await nc.subscribe("insec-to-processor", cb=proc._handle_downstream)

    # run forever
    await asyncio.get_event_loop().create_future()

if __name__ == "__main__":
    asyncio.run(main())
