"""Security Module with 2FA and Audit Logging.

Provides security features:
- Two-Factor Authentication (2FA) for critical operations
- Audit logging for all user actions
- IP whitelist management
- Encrypted API key storage

Usage:
    ```python
    from src.security.security import SecurityManager

    security = SecurityManager()

    # Setup 2FA
    secret = security.setup_2fa(user_id)

    # Verify 2FA
    is_valid = security.verify_2fa(user_id, code)

    # Log action
    security.audit_log(user_id, "buy_item", details={...})
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = structlog.get_logger(__name__)


class SecurityLevel(StrEnum):
    """Security level for operations."""

    LOW = "low"  # No additional verification needed
    MEDIUM = "medium"  # EmAlgol verification or cooldown
    HIGH = "high"  # 2FA required
    CRITICAL = "critical"  # 2FA + additional confirmation


class ActionCategory(StrEnum):
    """Action categories for audit logging."""

    AUTH = "auth"  # Login, logout, session management
    TRADE = "trade"  # Buy, sell, list operations
    CONFIG = "config"  # Settings changes
    SECURITY = "security"  # 2FA setup, password changes
    ADMIN = "admin"  # Admin operations
    API = "api"  # API key operations


@dataclass
class AuditLogEntry:
    """Single audit log entry."""

    log_id: str
    user_id: int
    action: str
    category: ActionCategory
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Context
    ip_address: str | None = None
    user_agent: str | None = None

    # Details
    success: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    # Security
    security_level: SecurityLevel = SecurityLevel.LOW
    required_2fa: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "log_id": self.log_id,
            "user_id": self.user_id,
            "action": self.action,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "success": self.success,
            "details": self.details,
            "error_message": self.error_message,
            "security_level": self.security_level.value,
            "required_2fa": self.required_2fa,
        }


@dataclass
class TwoFactorAuth:
    """2FA configuration for a user."""

    user_id: int
    secret: str
    is_enabled: bool = False
    backup_codes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime | None = None

    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup codes."""
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes = codes
        return codes


@dataclass
class IPWhitelistEntry:
    """IP whitelist entry."""

    user_id: int
    ip_address: str
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    is_active: bool = True

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class TOTP:
    """Time-based One-Time Password implementation (RFC 6238)."""

    def __init__(
        self,
        secret: str,
        digits: int = 6,
        interval: int = 30,
        algorithm: str = "SHA1",
    ) -> None:
        """Initialize TOTP.

        Args:
            secret: Base32 encoded secret
            digits: Number of digits in OTP
            interval: Time interval in seconds
            algorithm: Hash algorithm
        """
        self.secret = secret
        self.digits = digits
        self.interval = interval
        self.algorithm = algorithm

    def _get_counter(self, time_value: float | None = None) -> int:
        """Get counter from time."""
        if time_value is None:
            time_value = time.time()
        return int(time_value) // self.interval

    def generate(self, time_value: float | None = None) -> str:
        """Generate TOTP code.

        Args:
            time_value: Optional time value (default: current time)

        Returns:
            TOTP code string
        """
        counter = self._get_counter(time_value)

        # Decode secret
        try:
            key = base64.b32decode(
                self.secret.upper() + "=" * ((8 - len(self.secret) % 8) % 8)
            )
        except Exception:
            key = self.secret.encode()

        # Generate HMAC
        counter_bytes = struct.pack(">Q", counter)
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0F
        code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0]
        code = (code & 0x7FFFFFFF) % (10**self.digits)

        return str(code).zfill(self.digits)

    def verify(
        self,
        code: str,
        time_value: float | None = None,
        window: int = 1,
    ) -> bool:
        """Verify TOTP code.

        Args:
            code: Code to verify
            time_value: Optional time value
            window: Number of intervals to check before/after

        Returns:
            True if code is valid
        """
        if time_value is None:
            time_value = time.time()

        # Check current and adjacent intervals
        for offset in range(-window, window + 1):
            check_time = time_value + (offset * self.interval)
            if self.generate(check_time) == code:
                return True

        return False

    @classmethod
    def generate_secret(cls, length: int = 32) -> str:
        """Generate random secret.

        Args:
            length: Secret length

        Returns:
            Base32 encoded secret
        """
        random_bytes = secrets.token_bytes(length)
        return base64.b32encode(random_bytes).decode("utf-8").rstrip("=")

    def get_uri(
        self,
        account_name: str,
        issuer: str = "DMarket Bot",
    ) -> str:
        """Get otpauth URI for QR code.

        Args:
            account_name: User's account name
            issuer: Service name

        Returns:
            otpauth URI
        """
        return (
            f"otpauth://totp/{issuer}:{account_name}"
            f"?secret={self.secret}"
            f"&issuer={issuer}"
            f"&algorithm={self.algorithm}"
            f"&digits={self.digits}"
            f"&period={self.interval}"
        )


class APIKeyEncryption:
    """API key encryption using Fernet."""

    def __init__(self, master_key: str | None = None) -> None:
        """Initialize encryption.

        Args:
            master_key: Master encryption key (generated if not provided)
        """
        if master_key:
            # Derive key from master key
            salt = (
                b"dmarket_bot_salt"  # In production, use unique salt per installation
            )
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
            self._fernet = Fernet(key)
        else:
            # Generate new key
            key = Fernet.generate_key()
            self._fernet = Fernet(key)
            self._key = key.decode()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext.

        Args:
            plaintext: Text to encrypt

        Returns:
            Encrypted text (base64)
        """
        encrypted = self._fernet.encrypt(plaintext.encode())
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext.

        Args:
            ciphertext: Encrypted text

        Returns:
            Decrypted text
        """
        decrypted = self._fernet.decrypt(ciphertext.encode())
        return decrypted.decode()


class SecurityManager:
    """Security manager for 2FA, audit logging, and encryption.

    Provides comprehensive security features:
    - Two-Factor Authentication setup and verification
    - Audit logging for all user actions
    - IP whitelist management
    - API key encryption
    """

    # Actions requiring 2FA
    HIGH_SECURITY_ACTIONS = {
        "withdraw",
        "change_api_key",
        "disable_2fa",
        "bulk_sell",
        "delete_account",
    }

    # Amount thresholds for 2FA requirement
    AMOUNT_THRESHOLD_2FA = 50.0  # USD

    def __init__(
        self,
        encryption_key: str | None = None,
        enable_audit_logging: bool = True,
    ) -> None:
        """Initialize security manager.

        Args:
            encryption_key: Master encryption key
            enable_audit_logging: Enable audit logging
        """
        self._2fa_configs: dict[int, TwoFactorAuth] = {}
        self._ip_whitelist: dict[int, list[IPWhitelistEntry]] = {}
        self._audit_logs: list[AuditLogEntry] = []
        self._log_counter = 0

        self._enable_audit_logging = enable_audit_logging

        # Initialize encryption
        self._encryption = APIKeyEncryption(encryption_key)

        # Session tracking for 2FA
        self._2fa_sessions: dict[str, tuple[int, datetime]] = (
            {}
        )  # session_id -> (user_id, expires)

    # ==================== 2FA ====================

    def setup_2fa(self, user_id: int) -> dict[str, Any]:
        """Setup 2FA for a user.

        Args:
            user_id: User ID

        Returns:
            Setup info with secret and QR URI
        """
        secret = TOTP.generate_secret()
        totp = TOTP(secret)

        backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]

        config = TwoFactorAuth(
            user_id=user_id,
            secret=secret,
            is_enabled=False,
            backup_codes=backup_codes,
        )

        self._2fa_configs[user_id] = config

        self.audit_log(
            user_id=user_id,
            action="setup_2fa_initiated",
            category=ActionCategory.SECURITY,
            security_level=SecurityLevel.HIGH,
        )

        return {
            "secret": secret,
            "uri": totp.get_uri(f"user_{user_id}"),
            "backup_codes": backup_codes,
            "message": "Scan QR code with authenticator app, then verify with a code",
        }

    def enable_2fa(self, user_id: int, verification_code: str) -> bool:
        """Enable 2FA after verification.

        Args:
            user_id: User ID
            verification_code: Code from authenticator app

        Returns:
            True if enabled successfully
        """
        config = self._2fa_configs.get(user_id)
        if not config:
            return False

        totp = TOTP(config.secret)

        if totp.verify(verification_code):
            config.is_enabled = True

            self.audit_log(
                user_id=user_id,
                action="2fa_enabled",
                category=ActionCategory.SECURITY,
                security_level=SecurityLevel.HIGH,
            )

            logger.info("2fa_enabled", user_id=user_id)
            return True

        self.audit_log(
            user_id=user_id,
            action="2fa_enable_failed",
            category=ActionCategory.SECURITY,
            success=False,
            error_message="Invalid verification code",
        )

        return False

    def disable_2fa(
        self,
        user_id: int,
        verification_code: str | None = None,
        backup_code: str | None = None,
    ) -> bool:
        """Disable 2FA.

        Args:
            user_id: User ID
            verification_code: Code from authenticator
            backup_code: Backup code (alternative)

        Returns:
            True if disabled successfully
        """
        config = self._2fa_configs.get(user_id)
        if not config or not config.is_enabled:
            return False

        # Verify with TOTP or backup code
        verified = False

        if verification_code:
            totp = TOTP(config.secret)
            verified = totp.verify(verification_code)

        if not verified and backup_code:
            if backup_code.upper() in config.backup_codes:
                config.backup_codes.remove(backup_code.upper())
                verified = True

        if verified:
            config.is_enabled = False

            self.audit_log(
                user_id=user_id,
                action="2fa_disabled",
                category=ActionCategory.SECURITY,
                security_level=SecurityLevel.CRITICAL,
            )

            logger.info("2fa_disabled", user_id=user_id)
            return True

        self.audit_log(
            user_id=user_id,
            action="2fa_disable_failed",
            category=ActionCategory.SECURITY,
            success=False,
            error_message="Invalid code",
        )

        return False

    def verify_2fa(
        self,
        user_id: int,
        code: str,
    ) -> bool:
        """Verify 2FA code.

        Args:
            user_id: User ID
            code: TOTP code or backup code

        Returns:
            True if code is valid
        """
        config = self._2fa_configs.get(user_id)
        if not config or not config.is_enabled:
            return True  # 2FA not enabled, allow

        # Try TOTP
        totp = TOTP(config.secret)
        if totp.verify(code):
            config.last_used = datetime.now(UTC)

            self.audit_log(
                user_id=user_id,
                action="2fa_verified",
                category=ActionCategory.AUTH,
                required_2fa=True,
            )

            return True

        # Try backup code
        if code.upper() in config.backup_codes:
            config.backup_codes.remove(code.upper())
            config.last_used = datetime.now(UTC)

            self.audit_log(
                user_id=user_id,
                action="2fa_verified_backup",
                category=ActionCategory.AUTH,
                required_2fa=True,
                details={"backup_codes_remaining": len(config.backup_codes)},
            )

            logger.warning(
                "2fa_backup_code_used",
                user_id=user_id,
                remaining=len(config.backup_codes),
            )

            return True

        self.audit_log(
            user_id=user_id,
            action="2fa_verification_failed",
            category=ActionCategory.AUTH,
            success=False,
            required_2fa=True,
        )

        return False

    def is_2fa_enabled(self, user_id: int) -> bool:
        """Check if 2FA is enabled for user.

        Args:
            user_id: User ID

        Returns:
            True if 2FA is enabled
        """
        config = self._2fa_configs.get(user_id)
        return config is not None and config.is_enabled

    def requires_2fa(
        self,
        user_id: int,
        action: str,
        amount: float | None = None,
    ) -> bool:
        """Check if action requires 2FA.

        Args:
            user_id: User ID
            action: Action being performed
            amount: Optional amount involved

        Returns:
            True if 2FA is required
        """
        if not self.is_2fa_enabled(user_id):
            return False

        # High security actions always require 2FA
        if action in self.HIGH_SECURITY_ACTIONS:
            return True

        # Amount threshold
        return bool(amount and amount >= self.AMOUNT_THRESHOLD_2FA)

    def create_2fa_session(self, user_id: int, expires_minutes: int = 15) -> str:
        """Create temporary 2FA session after verification.

        Args:
            user_id: User ID
            expires_minutes: Session expiry in minutes

        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + timedelta(minutes=expires_minutes)

        self._2fa_sessions[session_id] = (user_id, expires)

        return session_id

    def verify_2fa_session(self, session_id: str, user_id: int) -> bool:
        """Verify 2FA session.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            True if session is valid
        """
        session = self._2fa_sessions.get(session_id)
        if not session:
            return False

        stored_user_id, expires = session

        if stored_user_id != user_id:
            return False

        if datetime.now(UTC) > expires:
            del self._2fa_sessions[session_id]
            return False

        return True

    # ==================== IP Whitelist ====================

    def add_ip_whitelist(
        self,
        user_id: int,
        ip_address: str,
        description: str = "",
        expires_days: int | None = None,
    ) -> IPWhitelistEntry:
        """Add IP to whitelist.

        Args:
            user_id: User ID
            ip_address: IP address to whitelist
            description: Optional description
            expires_days: Days until expiry (None = permanent)

        Returns:
            Whitelist entry
        """
        entry = IPWhitelistEntry(
            user_id=user_id,
            ip_address=ip_address,
            description=description,
            expires_at=(
                datetime.now(UTC) + timedelta(days=expires_days)
                if expires_days
                else None
            ),
        )

        if user_id not in self._ip_whitelist:
            self._ip_whitelist[user_id] = []

        self._ip_whitelist[user_id].append(entry)

        self.audit_log(
            user_id=user_id,
            action="ip_whitelist_add",
            category=ActionCategory.SECURITY,
            details={"ip_address": ip_address, "description": description},
        )

        return entry

    def remove_ip_whitelist(self, user_id: int, ip_address: str) -> bool:
        """Remove IP from whitelist.

        Args:
            user_id: User ID
            ip_address: IP address to remove

        Returns:
            True if removed
        """
        if user_id not in self._ip_whitelist:
            return False

        original_count = len(self._ip_whitelist[user_id])
        self._ip_whitelist[user_id] = [
            e for e in self._ip_whitelist[user_id] if e.ip_address != ip_address
        ]

        removed = len(self._ip_whitelist[user_id]) < original_count

        if removed:
            self.audit_log(
                user_id=user_id,
                action="ip_whitelist_remove",
                category=ActionCategory.SECURITY,
                details={"ip_address": ip_address},
            )

        return removed

    def is_ip_whitelisted(self, user_id: int, ip_address: str) -> bool:
        """Check if IP is whitelisted.

        Args:
            user_id: User ID
            ip_address: IP address to check

        Returns:
            True if whitelisted (or no whitelist configured)
        """
        if user_id not in self._ip_whitelist:
            return True  # No whitelist = allow all

        whitelist = self._ip_whitelist[user_id]
        if not whitelist:
            return True

        for entry in whitelist:
            if (
                entry.ip_address == ip_address
                and entry.is_active
                and not entry.is_expired()
            ):
                return True

        return False

    def get_ip_whitelist(self, user_id: int) -> list[IPWhitelistEntry]:
        """Get user's IP whitelist.

        Args:
            user_id: User ID

        Returns:
            List of whitelist entries
        """
        return self._ip_whitelist.get(user_id, [])

    # ==================== API Key Encryption ====================

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key for storage.

        Args:
            api_key: PlAlgon API key

        Returns:
            Encrypted API key
        """
        return self._encryption.encrypt(api_key)

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt stored API key.

        Args:
            encrypted_key: Encrypted API key

        Returns:
            PlAlgon API key
        """
        return self._encryption.decrypt(encrypted_key)

    # ==================== Audit Logging ====================

    def audit_log(
        self,
        user_id: int,
        action: str,
        category: ActionCategory = ActionCategory.TRADE,
        ip_address: str | None = None,
        user_agent: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
        security_level: SecurityLevel = SecurityLevel.LOW,
        required_2fa: bool = False,
    ) -> AuditLogEntry | None:
        """Log an action to audit log.

        Args:
            user_id: User ID
            action: Action name
            category: Action category
            ip_address: Client IP
            user_agent: Client user agent
            success: Whether action succeeded
            details: Additional details
            error_message: Error message if failed
            security_level: Security level
            required_2fa: Whether 2FA was required

        Returns:
            Audit log entry or None if logging disabled
        """
        if not self._enable_audit_logging:
            return None

        self._log_counter += 1
        log_id = f"audit_{self._log_counter}_{int(time.time())}"

        entry = AuditLogEntry(
            log_id=log_id,
            user_id=user_id,
            action=action,
            category=category,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=details or {},
            error_message=error_message,
            security_level=security_level,
            required_2fa=required_2fa,
        )

        self._audit_logs.append(entry)

        # Trim old logs (keep last 10000)
        if len(self._audit_logs) > 10000:
            self._audit_logs = self._audit_logs[-10000:]

        logger.info(
            "audit_log",
            user_id=user_id,
            action=action,
            category=category.value,
            success=success,
        )

        return entry

    def get_audit_logs(
        self,
        user_id: int | None = None,
        category: ActionCategory | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLogEntry]:
        """Get audit logs with filters.

        Args:
            user_id: Filter by user
            category: Filter by category
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum entries to return

        Returns:
            List of audit log entries
        """
        logs = self._audit_logs

        if user_id is not None:
            logs = [log for log in logs if log.user_id == user_id]

        if category is not None:
            logs = [log for log in logs if log.category == category]

        if start_date is not None:
            logs = [log for log in logs if log.timestamp >= start_date]

        if end_date is not None:
            logs = [log for log in logs if log.timestamp <= end_date]

        # Sort by timestamp descending
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)

        return logs[:limit]

    def get_security_summary(self, user_id: int) -> dict[str, Any]:
        """Get security summary for user.

        Args:
            user_id: User ID

        Returns:
            Security summary
        """
        two_fa_config = self._2fa_configs.get(user_id)
        ip_whitelist = self._ip_whitelist.get(user_id, [])

        # Recent security events
        recent_logs = self.get_audit_logs(
            user_id=user_id,
            category=ActionCategory.SECURITY,
            limit=10,
        )

        # Failed login attempts
        auth_logs = self.get_audit_logs(
            user_id=user_id,
            category=ActionCategory.AUTH,
            limit=50,
        )
        failed_attempts = sum(1 for log in auth_logs if not log.success)

        return {
            "2fa_enabled": two_fa_config.is_enabled if two_fa_config else False,
            "2fa_last_used": (
                two_fa_config.last_used.isoformat()
                if two_fa_config and two_fa_config.last_used
                else None
            ),
            "backup_codes_remaining": (
                len(two_fa_config.backup_codes) if two_fa_config else 0
            ),
            "ip_whitelist_count": len([e for e in ip_whitelist if e.is_active]),
            "recent_security_events": len(recent_logs),
            "failed_auth_attempts_recent": failed_attempts,
            "security_score": self._calculate_security_score(user_id),
        }

    def _calculate_security_score(self, user_id: int) -> int:
        """Calculate security score (0-100).

        Args:
            user_id: User ID

        Returns:
            Security score
        """
        score = 50  # Base score

        # 2FA enabled: +30
        if self.is_2fa_enabled(user_id):
            score += 30

        # IP whitelist configured: +10
        if user_id in self._ip_whitelist and len(self._ip_whitelist[user_id]) > 0:
            score += 10

        # No recent failed attempts: +10
        auth_logs = self.get_audit_logs(
            user_id=user_id,
            category=ActionCategory.AUTH,
            limit=20,
        )
        failed = sum(1 for log in auth_logs if not log.success)
        if failed == 0:
            score += 10
        elif failed > 5:
            score -= 20

        return max(0, min(100, score))


# Factory function
def create_security_manager(
    encryption_key: str | None = None,
    enable_audit_logging: bool = True,
) -> SecurityManager:
    """Create security manager instance.

    Args:
        encryption_key: Master encryption key
        enable_audit_logging: Enable audit logging

    Returns:
        SecurityManager instance
    """
    return SecurityManager(
        encryption_key=encryption_key,
        enable_audit_logging=enable_audit_logging,
    )
