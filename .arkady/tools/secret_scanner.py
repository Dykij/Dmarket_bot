import os
import re
from acontext_logger import log_activity

# Регулярные выражения для поиска типичных ключей
PATTERNS = {
    "DMarket Public Key": r"[a-fA-F0-9]{32,}",
    "Gemini/Google API Key": r"AIza[0-9A-Za-z-_]{35}",
    "Telegram Bot Token": r"[0-9]{9,10}:[a-zA-Z0-9_-]{35}"
}

IGNORE_DIRS = [".venv", ".git", "__pycache__", "logs", ".arkady"]

def scan_secrets():
    log_activity("WATCHER", "SECRET_SCAN", "Scanning project for hardcoded secrets", "STARTED")
    found_secrets = []
    
    root_dir = "D:\\DMarket-Telegram-Bot-main"
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if file.endswith((".py", ".json", ".md", ".sh", ".ps1")) and file != ".env":
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        for name, pattern in PATTERNS.items():
                            if re.search(pattern, content):
                                # Проверяем, не является ли это примером в .env.example
                                if "example" not in file.lower():
                                    found_secrets.append(f"{name} found in {path}")
                except:
                    continue

    if found_secrets:
        print("\n" + "!"*50)
        print("CRITICAL SECURITY WARNING: Hardcoded secrets detected!")
        for s in found_secrets:
            print(f" - {s}")
        print("ACTION: Move these secrets to .env immediately.")
        print("!"*50 + "\n")
        log_activity("WATCHER", "SECRET_SCAN", f"Found {len(found_secrets)} secrets", "WARNING")
    else:
        print("[+] No hardcoded secrets found in source files.")
        log_activity("WATCHER", "SECRET_SCAN", "No secrets detected", "SUCCESS")

if __name__ == "__main__":
    scan_secrets()
