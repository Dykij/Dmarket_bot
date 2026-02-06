import sys
import os
import subprocess

def run_checks():
    print("[*] Running Arkady Pre-Commit Checks...")
    
    # 1. Secret Scan
    print("[*] Checking for secrets...")
    # Add project root to path to find tool
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools"))
    try:
        from secret_scanner import scan_secrets
        # We need to capture its warning or modify it to return a boolean
        # For this hook, we'll re-implement basic logic for speed or call as subprocess
        result = subprocess.run(["python", os.path.join(os.path.dirname(__file__), "..", "tools", "secret_scanner.py")], capture_output=True, text=True)
        if "CRITICAL SECURITY WARNING" in result.stdout:
            print("[FAIL] Hardcoded secrets detected!")
            return False
    except Exception as e:
        print(f"[ERROR] Secret scanner failed: {e}")
        return False

    # 2. Syntax Check
    print("[*] Checking Python syntax...")
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    result = subprocess.run(["python", "-m", "py_compile", src_dir], capture_output=True)
    if result.returncode != 0:
        print("[FAIL] Syntax errors detected in src/")
        return False

    print("[SUCCESS] All checks passed.")
    return True

if __name__ == "__main__":
    if not run_checks():
        sys.exit(1)
