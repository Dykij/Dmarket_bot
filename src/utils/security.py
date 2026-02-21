import re
import logging

logger = logging.getLogger(__name__)

class SecurityFirewall:
    """
    The Iron Dome agAlgonst Config Worms and Injection Attacks.
    Designed by Core, Audited by QA.
    """

    # Basic Injection Patterns (The Worms)
    WORM_SIGNATURES = [
        r"Ignore previous instructions",
        r"System Config",
        r"You are now",
        r"os\.system",
        r"subprocess",
        r"rm -rf",
        r"DROP TABLE",
        r"eval\("
    ]

    @staticmethod
    def sanitize_external_input(text: str) -> str:
        """
        Cleans text from external sources (Habr/GitHub/API).
        Strips control characters and blocks known worm signatures.
        """
        if not text:
            return ""

        # 1. Strip Control Characters (Transport Layer for Worms)
        # Removes non-printable chars except newlines/tabs
        clean_text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        # 2. Pattern Matching (Heuristic Firewall)
        for pattern in SecurityFirewall.WORM_SIGNATURES:
            if re.search(pattern, clean_text, re.IGNORECASE):
                logger.warning(f"🚨 SECURITY ALERT: Config Worm detected. Pattern: {pattern}")
                return "[REDACTED: MALICIOUS CONTENT BLOCKED BY QA]"

        return clean_text.strip()

    @staticmethod
    def validate_command(cmd: list) -> bool:
        """
        QA's Final Gate. Checks if a command list is safe for execution.
        """
        cmd_str = " ".join(cmd)
        if "rm " in cmd_str or "del " in cmd_str:
            return False
        return True
