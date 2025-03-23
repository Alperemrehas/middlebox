import subprocess
import time
import re
import csv
import matplotlib.pyplot as plt

# List of mean delays (in milliseconds) to test.
mean_delays = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 200]

results = []

# Path to the python processor file.
processor_file = "code/python-processor/main.py"

def update_mean_delay(new_delay):
    """Update the MEAN_DELAY_MS value in the processor file."""
    print(f"Updating MEAN_DELAY_MS to {new_delay} ms in {processor_file}")
    with open(processor_file, "r") as f:
        lines = f.readlines()
    with open(processor_file, "w") as f:
        for line in lines:
            if line.strip().startswith("MEAN_DELAY_MS"):
                f.write(f"MEAN_DELAY_MS = {new_delay}\n")
            else:
                f.write(line)

def restart_processor():
    """Restart the python-processor container using docker compose."""
    print("Restarting python-processor container...")
    subprocess.run(["docker", "compose", "restart", "python-processor"], check=True)

def run_ping_test():
    """Run a ping test in the 'sec' container and return the output."""
    print("Running ping test from SEC container...")
    result = subprocess.run(
        ["docker", "exec", "sec", "ping", "-c", "5", "insec"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print("Ping output:")
    print(result.stdout)
    return result.stdout

def parse_avg_rtt(ping_output):
    """Parse the average RTT from the ping command output."""
    match = re.search(r"rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/", ping_output)
    if match:
        return float(match.group(1))
    return None

for delay in mean_delays:
    print(f"\nTesting with MEAN_DELAY_MS = {delay}")
    update_mean_delay(delay)
    restart_processor()
    time.sleep(15)
    
    ping_output = run_ping_test()
    avg_rtt = parse_avg_rtt(ping_output)
    if avg_rtt is not None:
        print(f"Average RTT: {avg_rtt} ms")
        results.append((delay, avg_rtt))
    else:
        print("Ping test failed: Could not parse average RTT. Check connectivity and MITM switch.")
    
    time.sleep(5)

# Save results to CSV.
with open("rtt_results.csv", "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Mean Delay (ms)", "Average RTT (ms)"])
    writer.writerows(results)

# Plot the results if we got some data.
if results:
    delays, rtts = zip(*results)
    plt.plot(delays, rtts, marker="o")
    plt.xlabel("Mean Random Delay (ms)")
    plt.ylabel("Average RTT (ms)")
    plt.title("Impact of Random Delay on Ping RTT")
    plt.grid(True)
    plt.savefig("rtt_vs_delay.png")
    plt.show()
else:
    print("No results to plot.")
