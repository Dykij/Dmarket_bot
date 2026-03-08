import sys
import argparse
import os

# MANDATORY: Unicode Fix
sys.stdout.reconfigure(encoding='utf-8')

# CRITICAL FIX: Inject Token for Session
os.environ["TELEGRAM_BOT_TOKEN"] = "8461845004:AAE3eAnAyohsRh9XMrkv3pNx56iACKmOuws"

def broadcast(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"BROADCASTING {file_path}:\n")
            print(content)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
    except Exception as e:
        print(f"Error broadcasting: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="File to broadcast")
    args = parser.parse_args()
    
    broadcast(args.file)
