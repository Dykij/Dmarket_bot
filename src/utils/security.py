import re
import logging

logger = logging.getLogger("SecurityAuditor")

class DataSanitizer:
    """
    Sanitizes external data (e.g., from DMarket API) before it enters LLM prompts.
    Defends against prompt injection worms hidden in item names or descriptions.
    """
    
    # Common prompt injection triggers
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+all\s+(previous\s+)?instructions", re.IGNORECASE),
        re.compile(r"disregard\s+all", re.IGNORECASE),
        re.compile(r"print\s+(your\s+)?system\s+prompt", re.IGNORECASE),
        re.compile(r"you\s+are\s+now", re.IGNORECASE),
        re.compile(r"forget\s+user\s+request", re.IGNORECASE),
        re.compile(r"bypass\s+security", re.IGNORECASE),
        re.compile(r"system:\s+", re.IGNORECASE),
        re.compile(r"```(bash|sh|python)", re.IGNORECASE)
    ]

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Scans a single string for malicious injections. 
        Returns immediately if None.
        """
        if not text or not isinstance(text, str):
            return text
            
        for pattern in DataSanitizer.INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning(f"🚨 Prompt Injection attempt detected and blocked: {text[:50]}...")
                return "[BLOCKED_INJECTION_STRING]"
                
        return text

    @staticmethod
    def sanitize_dict(data: dict) -> dict:
        """
        Recursively sanitizes all string values within a dictionary.
        Used for entire DMarket API JSON responses.
        """
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = DataSanitizer.sanitize_text(value)
            elif isinstance(value, dict):
                sanitized[key] = DataSanitizer.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    DataSanitizer.sanitize_dict(item) if isinstance(item, dict) 
                    else DataSanitizer.sanitize_text(item) if isinstance(item, str) 
                    else item 
                    for item in value
                ]
            else:
                sanitized[key] = value  # type: ignore
                
        return sanitized
