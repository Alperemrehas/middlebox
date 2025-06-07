#!/usr/bin/env python3
import os
import subprocess
import shutil
import time
import datetime
import sys

# Root directory for collecting everything
COMPLETE_ROOT = "complete_test"
os.makedirs(COMPLETE_ROOT, exist_ok=True)

# Timestamp to namespace this run
TS = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def fail(msg):
    print(f"\n✖ {msg}", file=sys.stderr)
    sys.exit(1)

def run_cmd(cmd, **kw):
    print(f"\n▶️  Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, **kw)
    except subprocess.CalledProcessError:
        fail(f"Command failed: {' '.join(cmd)}")

def phase1():
    phase = f"phase1-{TS}"
    outdir = os.path.join(COMPLETE_ROOT, phase)
    os.makedirs(outdir, exist_ok=True)
    print(f"\n=== Phase 1: Warm-up (random delays) ===")

    # 1) Start MITM switch from code/mitm
    print("🔄 Starting MITM switch (make && ./switch in code/mitm)...")
    mitm = subprocess.Popen(
        ["bash","-lc","cd code/mitm && make && ./switch"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(5)  # give it a moment

    # 2) Run your Phase 1 test script from repo root
    run_cmd(["python3", "tests/run_random_delay_tests.py"])

    # 3) Tear down MITM switch
    mitm.terminate()
    try:
        mitm.wait(timeout=5)
    except subprocess.TimeoutExpired:
        mitm.kill()

    # 4) Collect outputs
    for fn in ("rtt_results.csv", "rtt_vs_delay.png"):
        if os.path.isfile(fn):
            shutil.move(fn, os.path.join(outdir, fn))
        else:
            print(f"⚠️  Missing Phase 1 output: {fn}")
    print(f"✅ Phase 1 outputs moved to {outdir}")

def phase2():
    phase = f"phase2-{TS}"
    outdir = os.path.join(COMPLETE_ROOT, phase)
    os.makedirs(outdir, exist_ok=True)
    print(f"\n=== Phase 2: Covert-channel benchmark ===")

    run_cmd(["python3", "tests/run_covert_tests.py"])
    if os.path.isdir("compelete_test_results/TPPhase2_results"):
        shutil.move("compelete_test_results/TPPhase2_results", outdir)
        print(f"✅ Phase 2 outputs moved to {outdir}")
    else:
        print("⚠️  TPPhase2_results/ not found.")

def phase3():
    phase = f"phase3-{TS}"
    base = "TPPhase3_results"
    print(f"\n=== Phase 3: Detector benchmark ===")

    run_cmd(["python3", "tests/run_detector_tests.py"])
    if os.path.isdir(base):
        subs = sorted(os.listdir(base))
        if subs:
            latest = subs[-1]
            src = os.path.join(base, latest)
            dst = os.path.join(COMPLETE_ROOT, phase)
            shutil.move(src, dst)
            print(f"✅ Phase 3 outputs moved to {dst}")
        else:
            print(f"⚠️  No subfolders in {base}/")
    else:
        print(f"⚠️  {base}/ not found.")

def phase4():
    phase = f"phase4-{TS}"
    base = "TPPhase4_results"
    print(f"\n=== Phase 4: Mitigator benchmark ===")

    run_cmd(["python3", "tests/run_mitigator_tests.py"])
    if os.path.isdir(base):
        for sub in os.listdir(base):
            src = os.path.join(base, sub)
            dst = os.path.join(COMPLETE_ROOT, f"{phase}-{sub}")
            shutil.move(src, dst)
            print(f"✅ Phase 4 outputs moved to {dst}")
    else:
        print(f"⚠️  {base}/ not found.")

def main():
    phase1()
    phase2()
    phase3()
    #phase4()
    print(f"\n🎉 All phases complete. Results under {COMPLETE_ROOT}/")

if __name__ == "__main__":
    main()
