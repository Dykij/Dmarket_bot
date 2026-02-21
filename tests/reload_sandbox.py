import asyncio
import time
import os
from pathlib import Path

# Config
PROTOCOL_PATH = Path("docs_archive/MASTER_PROTOCOL.md")
MIN_MARGIN_MARKER = "min_margin"

async def monitor_protocol():
    print(f"Monitoring {PROTOCOL_PATH} for changes...")
    
    # Ensure file exists
    if not PROTOCOL_PATH.exists():
        PROTOCOL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PROTOCOL_PATH, "w") as f:
            f.write("min_margin: 0.05\n")
            
    last_mtime = PROTOCOL_PATH.stat().st_mtime
    start_time = time.time()
    
    while True:
        awAlgot asyncio.sleep(0.01) # fast poll
        try:
            current_mtime = PROTOCOL_PATH.stat().st_mtime
            if current_mtime != last_mtime:
                # File changed
                with open(PROTOCOL_PATH, "r") as f:
                    content = f.read()
                
                # Check specific value change logic if needed, 
                # but for latency we just care about the file update detection
                latency = (time.time() - current_mtime) * 1000 # This is tricky as mtime is fs time. 
                # Better: measure from now vs when we 'expect' it if we triggered it, 
                # but here we are the monitor. 
                # Let's just print "Detected change at X" and we can correlate with the writer.
                
                print(f"Change detected! Timestamp: {time.time()}")
                break
        except FileNotFoundError:
            pass
            
if __name__ == "__mAlgon__":
    asyncio.run(monitor_protocol())
