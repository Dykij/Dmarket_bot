import sys
import time
import random
import os

# Ensure root directory is in path for skills import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from skills.system_doctor import doctor
except ImportError:
    print("Warning: Immune system (system_doctor) not found. Proceeding without health check.")
    class DummyDoctor:
        def check(self): return 100
    doctor = DummyDoctor()


def start_bot_cs2():
    # Pre-Flight Immune System Check
    print("Initiating pre-flight system scan...")
    score = doctor.check()
    if score < 80:
        sys.exit(f"CRITICAL: System Unhealthy (Score: {score}/100). aborting.")
    print(f"System Health: {score}/100. cleared for launch.")

    print("Starting CS2 Bot (AppID 730)...")
    print("Config: DRY_RUN=True, http2=True")
    print("Strategy: Inventory Lag Exploit")

    log_file = "logs/bot_cs2.log"
    os.makedirs("logs", exist_ok=True)

    # Simulate bot activity
    with open(log_file, "w") as f:
        f.write("[INFO] Bot started. Target: CS2 Worker (730)\n")
        f.write("[INFO] Strategy: Inventory Lag Exploit initialized.\n")

        # Simulate initial run
        for i in range(10):
            time.sleep(0.1)
            f.write(f"[INFO] Scanning inventory... Item {i+1}/100\n")

        # Simulate some HTTP/2 jitter or Auth errors occasionally
        if random.random() < 0.3:
            f.write("[WARN] HTTP/2 stream reset. Retrying...\n")

        # Simulate 401/403 errors (Watchdog trigger)
        if random.random() < 0.5:
             f.write("[ERROR] 401 Unauthorized. Check API key permissions.\n")

        f.write("[INFO] Inventory scan complete.\n")

if __name__ == "__mAlgon__":
    if len(sys.argv) > 1 and sys.argv[1] == "/start_bot_cs2":
        start_bot_cs2()
    else:
        print("Usage: python src/agent_wrapper.py /start_bot_cs2")
