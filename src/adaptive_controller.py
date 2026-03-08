import os
import re
import time

CONFIG_PATH = r"D:\DMarket-Telegram-Bot-main\config\config.yaml"
DEBUG_LOG_PATH = r"D:\DMarket-Telegram-Bot-main\debug.log"
SCAN_INTERVAL_MIN = 2.5
SCAN_INTERVAL_MAX = 10.0
INACTIVITY_THRESHOLD = 300  # 5 minutes in seconds

def get_last_new_item_time():
    """Returns the timestamp of the last 'New item detected' entry in debug.log"""
    if not os.path.exists(DEBUG_LOG_PATH):
        return 0
    
    last_time = 0
    try:
        # Read last 100 lines for efficiency
        with open(DEBUG_LOG_PATH, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-100:]
            for line in reversed(lines):
                if "New item detected" in line:
                    # Try to extract timestamp (assuming standard format)
                    match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                    if match:
                        last_time = time.mktime(time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S"))
                        break
                    else:
                        # If no timestamp found, assume it's current (not ideal, but works for immediate detection)
                        return time.time()
    except Exception as e:
        print(f"Error reading log: {e}")
    return last_time

def update_config_interval(interval):
    """Updates scan_interval_seconds in config.yaml"""
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            content = f.read()
        
        # Simple regex replace to keep comments and structure
        new_content = re.sub(r'(scan_interval_seconds:\s*\$\{SCAN_INTERVAL:)([\d\.]+)(\})', 
                            rf'\g<1>{interval}\g<3>', content)
        
        if new_content != content:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated SCAN_INTERVAL to {interval}")
            return True
    except Exception as e:
        print(f"Error updating config: {e}")
    return False

def main():
    print(f"Pulse Controller started. Target: {CONFIG_PATH}")
    # Force flush output
    import sys
    sys.stdout.flush()
    last_interval = None
    
    start_time = time.time()
    # Run for 2 minutes as requested for testing
    run_duration = 120 
    
    while time.time() - start_time < run_duration:
        last_item_time = get_last_new_item_time()
        time_since_last_item = time.time() - last_item_time
        
        if time_since_last_item > INACTIVITY_THRESHOLD:
            current_interval = SCAN_INTERVAL_MAX
        else:
            current_interval = SCAN_INTERVAL_MIN
            
        if current_interval != last_interval:
            update_config_interval(current_interval)
            last_interval = current_interval
            
        time.sleep(10) # Check every 10 seconds

if __name__ == "__main__":
    main()
