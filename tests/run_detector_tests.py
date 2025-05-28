#!/usr/bin/env python3
import os
import subprocess
import time
import shutil

# Paths on your host
PHASE2_CSV = "TPPhase2_results/covert_channel_results.csv"
PHASE3_DIR = "TPPhase3_results"
PHASE3_CSV = os.path.join(PHASE3_DIR, "detection_metrics.csv")

# Ensure Phase 2 has run
if not os.path.isfile(PHASE2_CSV):
    print(f"❗ Phase 2 results not found at {PHASE2_CSV}. Please run Phase 2 first.")
    exit(1)

os.makedirs(PHASE3_DIR, exist_ok=True)
# Backup any old CSV
if os.path.isfile(PHASE3_CSV):
    bak = PHASE3_CSV + ".bak"
    shutil.move(PHASE3_CSV, bak)
    print(f"🔄 Backed up old Phase 3 CSV to {bak}")

print("\n=== Phase 3 Detection Tests ===")
for mode in ("0", "1"):
    print(f"\n▶️  Running detector with COVERT_ACTIVE={mode}")
    # 1) restart detector container
    subprocess.run(["docker","restart","-t","2","python-processor"], check=True)

    # 2) launch the detector in background
    subprocess.run([
        "docker","exec","-d","python-processor","bash","-lc",
        f"export COVERT_ACTIVE={mode} && python3 /code/python-processor/main.py"
    ], check=True)

    # 3) start a steady ping (normal ICMP traffic)
    print("⏳  Starting steady ping from sec→insec…")
    ping_proc = subprocess.Popen([
        "docker","exec","sec","bash","-lc",
        "ping -i 0.1 -c 300 10.0.0.21"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4) if covert‐active, also start the covert sender
    if mode == "1":
        print("🚨  Launching covert sender in sec…")
        covert_proc = subprocess.Popen([
            "docker","exec","sec","bash","-lc",
            "python3 /code/sec/covert_sender.py "
            "--dest 10.0.0.21 "
            "--message 'Secret: Operation Mincemeat' "
            "--interval 0.2"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 5) let detector collect WINDOWS
    print("⏱  Sleeping 30 s to let detector build windows…")
    time.sleep(30)

    # 6) tear down ping & covert
    print("🔪  Stopping ping and covert sender…")
    ping_proc.terminate()
    if mode == "1":
        covert_proc.terminate()

    # 7) kill the detector inside the container
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

    # 8) copy out its CSV
    print("📥  Copying detection CSV out of container…")
    subprocess.run([
        "docker","cp",
        "python-processor:/code/python-processor/TPPhase3_results/detection_metrics.csv",
        PHASE3_CSV
    ], check=False)

# final check
if os.path.isfile(PHASE3_CSV):
    print(f"\n✅  Detection metrics written to {PHASE3_CSV}")
else:
    print(f"\n❌  No detection metrics found at {PHASE3_CSV}; please inspect your detector logic.")
