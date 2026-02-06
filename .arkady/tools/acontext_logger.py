import json
import datetime
import os

LOG_PATH = r"D:\DMarket-Telegram-Bot-main\.arkady\logs\activity.jsonl"

def log_activity(role: str, action: str, input_summary: str, output_status: str):
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "agent_role": role,
        "action": action,
        "input_summary": input_summary,
        "output_status": output_status
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    # Test logging
    log_activity("ARCHITECT", "INITIALIZE_LOGGING", "Setting up Acontext-style logging", "SUCCESS")
