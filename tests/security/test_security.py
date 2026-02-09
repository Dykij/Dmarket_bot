"""Tests for Security Module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.security.security import (
    TOTP,
    ActionCategory,
    APIKeyEncryption,
    AuditLogEntry,
    IPWhitelistEntry,
    SecurityManager,
    create_security_manager,
)


class TestTOTP:
    """Tests for TOTP implementation."""
    
    def test_generate_secret(self):
        """Test secret generation."""
        secret = TOTP.generate_secret()
        
        assert len(secret) == 52  # Base32 encoded 32 bytes
        assert secret.isalnum()
    
    def test_generate_code(self):
        """Test code generation."""
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        
        code = totp.generate()
        
        assert len(code) == 6
        assert code.isdigit()
    
    def test_verify_valid_code(self):
        """Test valid code verification."""
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        
        code = totp.generate()
        
        assert totp.verify(code) is True
    
    def test_verify_invalid_code(self):
        """Test invalid code verification."""
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        
        assert totp.verify("000000") is False
    
    def test_verify_with_window(self):
        """Test verification with time window."""
        secret = TOTP.generate_secret()
        totp = TOTP(secret)
        
        # Generate code for 30 seconds ago
        past_code = totp.generate(time_value=datetime.now(UTC).timestamp() - 30)
        
        # Should still verify with window=1
        assert totp.verify(past_code, window=1) is True
    
    def test_get_uri(self):
        """Test URI generation for QR code."""
        totp = TOTP("JBSWY3DPEHPK3PXP")
        
        uri = totp.get_uri("test_user", "TestApp")
        
        assert "otpauth://totp/" in uri
        assert "TestApp" in uri
        assert "test_user" in uri
        assert "JBSWY3DPEHPK3PXP" in uri


class TestAPIKeyEncryption:
    """Tests for API key encryption."""
    
    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        encryption = APIKeyEncryption()
        
        original = "my_secret_api_key_12345"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == original
        assert encrypted != original
    
    def test_encrypt_with_master_key(self):
        """Test encryption with master key."""
        master_key = "my_master_password"
        encryption = APIKeyEncryption(master_key)
        
        original = "api_key_to_encrypt"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)
        
        assert decrypted == original


class TestSecurityManager:
    """Tests for SecurityManager class."""
    
    def test_init(self):
        """Test initialization."""
        manager = SecurityManager()
        
        assert manager._enable_audit_logging is True
    
    def test_setup_2fa(self):
        """Test 2FA setup."""
        manager = SecurityManager()
        
        result = manager.setup_2fa(user_id=123)
        
        assert "secret" in result
        assert "uri" in result
        assert "backup_codes" in result
        assert len(result["backup_codes"]) == 10
    
    def test_enable_2fa_valid_code(self):
        """Test enabling 2FA with valid code."""
        manager = SecurityManager()
        
        setup = manager.setup_2fa(user_id=123)
        secret = setup["secret"]
        
        # Generate valid code
        totp = TOTP(secret)
        code = totp.generate()
        
        result = manager.enable_2fa(123, code)
        
        assert result is True
        assert manager.is_2fa_enabled(123) is True
    
    def test_enable_2fa_invalid_code(self):
        """Test enabling 2FA with invalid code."""
        manager = SecurityManager()
        
        manager.setup_2fa(user_id=123)
        
        result = manager.enable_2fa(123, "000000")
        
        assert result is False
        assert manager.is_2fa_enabled(123) is False
    
    def test_verify_2fa_when_disabled(self):
        """Test 2FA verification when disabled."""
        manager = SecurityManager()
        
        # 2FA not set up - should return True
        result = manager.verify_2fa(123, "any_code")
        
        assert result is True
    
    def test_verify_2fa_valid_code(self):
        """Test 2FA verification with valid code."""
        manager = SecurityManager()
        
        setup = manager.setup_2fa(user_id=123)
        secret = setup["secret"]
        
        totp = TOTP(secret)
        manager.enable_2fa(123, totp.generate())
        
        # Verify with new code
        result = manager.verify_2fa(123, totp.generate())
        
        assert result is True
    
    def test_verify_2fa_backup_code(self):
        """Test 2FA verification with backup code."""
        manager = SecurityManager()
        
        setup = manager.setup_2fa(user_id=123)
        secret = setup["secret"]
        
        totp = TOTP(secret)
        manager.enable_2fa(123, totp.generate())
        
        # Get the actual backup codes from the config
        config = manager._2fa_configs[123]
        backup_code = config.backup_codes[0]
        initial_count = len(config.backup_codes)
        
        # Use backup code
        result = manager.verify_2fa(123, backup_code)
        
        assert result is True
        
        # Backup code should be consumed
        assert len(config.backup_codes) == initial_count - 1
        assert backup_code not in config.backup_codes
    
    def test_disable_2fa(self):
        """Test disabling 2FA."""
        manager = SecurityManager()
        
        setup = manager.setup_2fa(user_id=123)
        secret = setup["secret"]
        totp = TOTP(secret)
        
        manager.enable_2fa(123, totp.generate())
        
        result = manager.disable_2fa(123, verification_code=totp.generate())
        
        assert result is True
        assert manager.is_2fa_enabled(123) is False
    
    def test_requires_2fa(self):
        """Test 2FA requirement check."""
        manager = SecurityManager()
        
        setup = manager.setup_2fa(user_id=123)
        totp = TOTP(setup["secret"])
        manager.enable_2fa(123, totp.generate())
        
        # High security action
        assert manager.requires_2fa(123, "withdraw") is True
        
        # Normal action
        assert manager.requires_2fa(123, "view_balance") is False
        
        # High amount
        assert manager.requires_2fa(123, "buy", amount=100.0) is True
    
    def test_create_2fa_session(self):
        """Test 2FA session creation."""
        manager = SecurityManager()
        
        session_id = manager.create_2fa_session(123)
        
        assert session_id is not None
        assert len(session_id) > 20
    
    def test_verify_2fa_session_valid(self):
        """Test valid 2FA session verification."""
        manager = SecurityManager()
        
        session_id = manager.create_2fa_session(123)
        
        assert manager.verify_2fa_session(session_id, 123) is True
    
    def test_verify_2fa_session_wrong_user(self):
        """Test 2FA session with wrong user."""
        manager = SecurityManager()
        
        session_id = manager.create_2fa_session(123)
        
        assert manager.verify_2fa_session(session_id, 456) is False


class TestIPWhitelist:
    """Tests for IP whitelist functionality."""
    
    def test_add_ip_whitelist(self):
        """Test adding IP to whitelist."""
        manager = SecurityManager()
        
        entry = manager.add_ip_whitelist(
            user_id=123,
            ip_address="192.168.1.1",
            description="Home",
        )
        
        assert entry.ip_address == "192.168.1.1"
        assert entry.is_active is True
    
    def test_is_ip_whitelisted_no_list(self):
        """Test IP check with no whitelist configured."""
        manager = SecurityManager()
        
        # No whitelist = allow all
        assert manager.is_ip_whitelisted(123, "1.2.3.4") is True
    
    def test_is_ip_whitelisted_in_list(self):
        """Test IP check when in whitelist."""
        manager = SecurityManager()
        
        manager.add_ip_whitelist(123, "192.168.1.1")
        
        assert manager.is_ip_whitelisted(123, "192.168.1.1") is True
    
    def test_is_ip_whitelisted_not_in_list(self):
        """Test IP check when not in whitelist."""
        manager = SecurityManager()
        
        manager.add_ip_whitelist(123, "192.168.1.1")
        
        assert manager.is_ip_whitelisted(123, "10.0.0.1") is False
    
    def test_remove_ip_whitelist(self):
        """Test removing IP from whitelist."""
        manager = SecurityManager()
        
        manager.add_ip_whitelist(123, "192.168.1.1")
        
        result = manager.remove_ip_whitelist(123, "192.168.1.1")
        
        assert result is True
    
    def test_get_ip_whitelist(self):
        """Test getting IP whitelist."""
        manager = SecurityManager()
        
        manager.add_ip_whitelist(123, "192.168.1.1")
        manager.add_ip_whitelist(123, "192.168.1.2")
        
        whitelist = manager.get_ip_whitelist(123)
        
        assert len(whitelist) == 2


class TestAPIKeyEncryptionInManager:
    """Tests for API key encryption in manager."""
    
    def test_encrypt_decrypt_api_key(self):
        """Test API key encryption through manager."""
        manager = SecurityManager()
        
        original = "my_dmarket_api_key"
        encrypted = manager.encrypt_api_key(original)
        decrypted = manager.decrypt_api_key(encrypted)
        
        assert decrypted == original
        assert encrypted != original


class TestAuditLogging:
    """Tests for audit logging."""
    
    def test_audit_log_basic(self):
        """Test basic audit logging."""
        manager = SecurityManager()
        
        entry = manager.audit_log(
            user_id=123,
            action="buy_item",
            category=ActionCategory.TRADE,
        )
        
        assert entry is not None
        assert entry.user_id == 123
        assert entry.action == "buy_item"
    
    def test_audit_log_disabled(self):
        """Test disabled audit logging."""
        manager = SecurityManager(enable_audit_logging=False)
        
        entry = manager.audit_log(
            user_id=123,
            action="test",
        )
        
        assert entry is None
    
    def test_get_audit_logs_by_user(self):
        """Test filtering audit logs by user."""
        manager = SecurityManager()
        
        manager.audit_log(123, "action1", ActionCategory.TRADE)
        manager.audit_log(456, "action2", ActionCategory.TRADE)
        manager.audit_log(123, "action3", ActionCategory.TRADE)
        
        logs = manager.get_audit_logs(user_id=123)
        
        assert len(logs) == 2
        assert all(l.user_id == 123 for l in logs)
    
    def test_get_audit_logs_by_category(self):
        """Test filtering audit logs by category."""
        manager = SecurityManager()
        
        manager.audit_log(123, "login", ActionCategory.AUTH)
        manager.audit_log(123, "buy", ActionCategory.TRADE)
        manager.audit_log(123, "logout", ActionCategory.AUTH)
        
        logs = manager.get_audit_logs(category=ActionCategory.AUTH)
        
        assert len(logs) == 2
        assert all(l.category == ActionCategory.AUTH for l in logs)
    
    def test_get_audit_logs_limit(self):
        """Test audit logs limit."""
        manager = SecurityManager()
        
        for i in range(10):
            manager.audit_log(123, f"action_{i}", ActionCategory.TRADE)
        
        logs = manager.get_audit_logs(limit=5)
        
        assert len(logs) == 5


class TestSecuritySummary:
    """Tests for security summary."""
    
    def test_get_security_summary(self):
        """Test security summary."""
        manager = SecurityManager()
        
        summary = manager.get_security_summary(123)
        
        assert "2fa_enabled" in summary
        assert "security_score" in summary
    
    def test_security_score_basic(self):
        """Test security score calculation."""
        manager = SecurityManager()
        
        # No security measures - base score
        score_before = manager._calculate_security_score(123)
        
        # Enable 2FA
        setup = manager.setup_2fa(123)
        manager.enable_2fa(123, TOTP(setup["secret"]).generate())
        
        score_after = manager._calculate_security_score(123)
        
        assert score_after > score_before


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""
    
    def test_to_dict(self):
        """Test serialization."""
        entry = AuditLogEntry(
            log_id="log_1",
            user_id=123,
            action="buy_item",
            category=ActionCategory.TRADE,
            success=True,
            details={"item": "AK-47"},
        )
        
        data = entry.to_dict()
        
        assert data["log_id"] == "log_1"
        assert data["action"] == "buy_item"
        assert data["category"] == "trade"


class TestIPWhitelistEntry:
    """Tests for IPWhitelistEntry dataclass."""
    
    def test_is_expired_no_expiry(self):
        """Test entry without expiry."""
        entry = IPWhitelistEntry(
            user_id=123,
            ip_address="192.168.1.1",
        )
        
        assert entry.is_expired() is False
    
    def test_is_expired_future(self):
        """Test entry with future expiry."""
        entry = IPWhitelistEntry(
            user_id=123,
            ip_address="192.168.1.1",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        
        assert entry.is_expired() is False
    
    def test_is_expired_past(self):
        """Test expired entry."""
        entry = IPWhitelistEntry(
            user_id=123,
            ip_address="192.168.1.1",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        
        assert entry.is_expired() is True


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_security_manager(self):
        """Test factory function."""
        manager = create_security_manager(
            encryption_key="test_key",
            enable_audit_logging=True,
        )
        
        assert manager._enable_audit_logging is True
