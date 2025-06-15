#!/usr/bin/env python3
import os
import subprocess
import shutil
import time
import datetime
import sys

# Root directory for collecting everything for this run
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
COMPLETE_ROOT = "complete_results"
os.makedirs(COMPLETE_ROOT, exist_ok=True)

# Define predictable output directory names for each phase
PHASE1_OUT = "TPPhase1_results"
PHASE2_OUT = "TPPhase2_results"
PHASE3_OUT = "TPPhase3_results"
PHASE4_OUT = "TPPhase4_results"

def fail(msg):
    print(f"\n✖ {msg}", file=sys.stderr)
    sys.exit(1)

def run_cmd(cmd, **kw):
    print(f"\n▶️  Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError:
        fail(f"Command failed: {' '.join(cmd)}")

def cleanup_and_move(src_dir, phase_name):
    """Moves a generated results directory into the main run folder."""
    if os.path.isdir(src_dir):
        dst = os.path.join(COMPLETE_ROOT, phase_name)
        shutil.move(src_dir, dst)
        print(f"✅ {phase_name} outputs moved to {dst}")
    else:
        print(f"⚠️  Missing output directory: {src_dir}")

def phase1():
    print(f"\n=== Phase 1: Warm-up (random delays) ===")

    # 1) Clean up any old results
    if os.path.isdir(PHASE1_OUT):
        shutil.rmtree(PHASE1_OUT)

    # 2) Start MITM switch
    print("🔄 Starting MITM switch (make && ./switch in code/mitm)...")
    mitm = subprocess.Popen(
        ["bash","-lc","cd code/mitm && make && ./switch"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(5)  # give it a moment

    # 3) Run the test script
    run_cmd(["python3", "tests/run_random_delay_tests.py"])

    # 4) Tear down MITM switch
    mitm.terminate()
    try:
        mitm.wait(timeout=5)
    except subprocess.TimeoutExpired:
        mitm.kill()

    # 5) Collect outputs
    cleanup_and_move(PHASE1_OUT, "Phase1_RTT_Results")

def phase2():
    print(f"\n=== Phase 2: Covert-channel benchmark ===")
    if os.path.isdir(PHASE2_OUT):
        shutil.rmtree(PHASE2_OUT)
    run_cmd(["python3", "tests/run_covert_tests.py"])
    cleanup_and_move(PHASE2_OUT, "Phase2_Covert_Channel_Capacity")

def phase3():
    print(f"\n=== Phase 3: Detector benchmark ===")
    if os.path.isdir(PHASE3_OUT):
        shutil.rmtree(PHASE3_OUT)
    run_cmd(["python3", "tests/run_detector_tests.py"])
    cleanup_and_move(PHASE3_OUT, "Phase3_Detector_Performance")

def phase4():
    print(f"\n=== Phase 4: Mitigator benchmark ===")
    if os.path.isdir(PHASE4_OUT):
        shutil.rmtree(PHASE4_OUT)
    run_cmd(["python3", "tests/run_mitigator_tests.py"])
    cleanup_and_move(PHASE4_OUT, "Phase4_Mitigation_Effectiveness")

def main():
    phase1()
    phase2()
    phase3()
    phase4()
    print(f"\n🎉 All phases complete. Results collected in {COMPLETE_ROOT}/")

if __name__ == "__main__":
    main()