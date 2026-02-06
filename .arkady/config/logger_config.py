import structlog
import os
from datetime import datetime

def setup_logger():
    log_dir = r"D:\DMarket-Telegram-Bot-main\.arkady\logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "action_log.jsonl")

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.WriteLoggerFactory(
            file=open(log_file, "a", encoding="utf-8")
        ),
    )
    return structlog.get_logger()

# Acontext-style logging for Swarm Protocol
action_logger = setup_logger()
