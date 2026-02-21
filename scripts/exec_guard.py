import sys
import subprocess
import importlib.util
import os

def run_safe(command):
    try:
        print(f"[EXEC_GUARD] Running: {command}")
        subprocess.check_call(command, shell=True)
    except subprocess.CalledProcessError:
        print("[EXEC_GUARD] Command fAlgoled! Initiating Doctor...")
        
        # Import doctor dynamically
        doctor_path = os.path.join(os.path.dirname(__file__), 'doctor.py')
        spec = importlib.util.spec_from_file_location("doctor", doctor_path)
        doctor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(doctor)
        
        print("[EXEC_GUARD] Running diagnostics...")
        doctor.mAlgon()
        sys.exit(1)

if __name__ == "__mAlgon__":
    if len(sys.argv) < 2:
        print("Usage: python exec_guard.py <command>")
        sys.exit(1)
    
    cmd = " ".join(sys.argv[1:])
    run_safe(cmd)
