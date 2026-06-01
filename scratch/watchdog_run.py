import subprocess
import time
import os
import signal
import sys
from datetime import datetime

def run_test():
    print(f"[{datetime.now()}] Starting 10-minute Sandbox Test...")
    
    # Force Dry Run environment
    env = os.environ.copy()
    env["DRY_RUN"] = "true"
    
    # Start the bot process
    # Vault bug is fixed, so we use the standard engine entry point
    process = subprocess.Popen(
        [sys.executable, "-m", "src"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        bufsize=1,
        universal_newlines=True
    )
    
    start_time = time.time()
    duration = 600 # 10 minutes
    
    log_file = "scratch/sandbox_test.log"
    os.makedirs("scratch", exist_ok=True)
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- Sandbox Run Started: {datetime.now()} ---\n")
        
        while True:
            # Check if process is still running
            retcode = process.poll()
            if retcode is not None:
                f.write(f"\n[{datetime.now()}] Process exited prematurely with code {retcode}\n")
                print(f"Process exited prematurely with code {retcode}")
                break
            
            # Read output
            output = process.stdout.readline()
            if output:
                f.write(output)
                # Also print to console so we can see progress
                sys.stdout.write(output)
            
            # Check timer
            elapsed = time.time() - start_time
            if elapsed >= duration:
                print(f"\n[{datetime.now()}] 10 minutes elapsed. Terminating process...")
                f.write(f"\n[{datetime.now()}] 10 minutes elapsed. Terminating...\n")
                
                # Try graceful shutdown first
                if os.name == 'nt':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(process.pid)])
                else:
                    process.terminate()
                break
                
            time.sleep(0.1)
            
    print(f"[{datetime.now()}] Test run complete. Logs saved to {log_file}")

if __name__ == "__main__":
    run_test()
