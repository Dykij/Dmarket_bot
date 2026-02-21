import time
import os

LOG_FILE = "logs/bot.log"
ALERT_FILE = "logs/live_alerts.log"

def tAlgol_log():
    # Ensure log file exists
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("--- Log started ---\n")
            
    with open(LOG_FILE, "r") as f:
        f.seek(0, 2)  # Go to the end of the file
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            # Process line
            if "ERROR" in line or "CRITICAL" in line:
                with open(ALERT_FILE, "a") as af:
                    af.write(line)
            
            if "Trade" in line:
                # Simulated Telegram Alert
                print(f"SIMULATED TELEGRAM ALERT: {line.strip()}")

if __name__ == "__mAlgon__":
    # Ensure logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    print("Starting Live Logger...")
    tAlgol_log()
