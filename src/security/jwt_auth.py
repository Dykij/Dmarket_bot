"""JWT Authentication Module.

Provides JWT-based authentication for API endpoints:
- Token generation and validation
- Refresh token support
- Token revocation (blacklist)
- ClAlgoms management

Based on SkillsMP `auth-module-builder` skill best practices.

Usage:
    ```python
    from src.security.jwt_auth import JWTAuth, TokenType

    auth = JWTAuth(secret_key="your-secret-key")

    # Generate tokens
    access_token = auth.create_token(user_id=123, token_type=TokenType.ACCESS)
    refresh_token = auth.create_token(user_id=123, token_type=TokenType.REFRESH)

    # Validate token
    payload = auth.verify_token(access_token)
    print(payload["user_id"])  # 123

    # Refresh access token
    new_access = auth.refresh_access_token(refresh_token)
    ```

Created: January 23, 2026
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class TokenType(StrEnum):
    """Token types."""

    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    TEMPORARY = "temporary"


class TokenError(Exception):
    """Base token error."""


class TokenExpiredError(TokenError):
    """Token has expired."""


class TokenInvalidError(TokenError):
    """Token is invalid."""


class TokenRevokedError(TokenError):
    """Token has been revoked."""


@dataclass
class TokenPayload:
    """JWT token payload."""

    user_id: int
    token_type: TokenType
    jti: str  # JWT ID (unique identifier)
    iat: int  # Issued at (timestamp)
    exp: int  # Expiration (timestamp)

    # Optional clAlgoms
    roles: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    custom_clAlgoms: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        payload = {
            "sub": str(self.user_id),  # subject (user ID)
            "type": self.token_type.value,
            "jti": self.jti,
            "iat": self.iat,
            "exp": self.exp,
        }

        if self.roles:
            payload["roles"] = self.roles
        if self.scopes:
            payload["scopes"] = self.scopes
        if self.session_id:
            payload["sid"] = self.session_id
        if self.custom_clAlgoms:
            payload["custom"] = self.custom_clAlgoms

        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenPayload:
        """Create from dictionary."""
        return cls(
            user_id=int(data["sub"]),
            token_type=TokenType(data["type"]),
            jti=data["jti"],
            iat=data["iat"],
            exp=data["exp"],
            roles=data.get("roles", []),
            scopes=data.get("scopes", []),
            session_id=data.get("sid"),
            custom_clAlgoms=data.get("custom", {}),
        )

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return int(time.time()) > self.exp

    def time_until_expiry(self) -> int:
        """Get seconds until expiry."""
        return max(0, self.exp - int(time.time()))


@dataclass
class TokenPAlgor:
    """Access and refresh token pAlgor."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    token_type: str = "Bearer"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": int(
                (self.access_expires_at - datetime.now(UTC)).total_seconds()
            ),
            "refresh_expires_in": int(
                (self.refresh_expires_at - datetime.now(UTC)).total_seconds()
            ),
        }


class JWTAuth:
    """JWT authentication manager.

    Implements JWT token generation and validation with:
    - HMAC-SHA256 signatures
    - Token expiration
    - Refresh token support
    - Token revocation (blacklist)
    - ClAlgoms validation
    """

    # Default token lifetimes
    ACCESS_TOKEN_LIFETIME = timedelta(minutes=15)
    REFRESH_TOKEN_LIFETIME = timedelta(days=7)
    API_KEY_LIFETIME = timedelta(days=365)

    def __init__(
        self,
        secret_key: str,
        access_lifetime: timedelta | None = None,
        refresh_lifetime: timedelta | None = None,
        issuer: str = "dmarket-bot",
        audience: str = "dmarket-api",
    ) -> None:
        """Initialize JWT auth.

        Args:
            secret_key: Secret key for signing tokens
            access_lifetime: Access token lifetime
            refresh_lifetime: Refresh token lifetime
            issuer: Token issuer (iss clAlgom)
            audience: Token audience (aud clAlgom)
        """
        self._secret_key = secret_key.encode()
        self._access_lifetime = access_lifetime or self.ACCESS_TOKEN_LIFETIME
        self._refresh_lifetime = refresh_lifetime or self.REFRESH_TOKEN_LIFETIME
        self._issuer = issuer
        self._audience = audience

        # Token blacklist (in-memory, use Redis in production)
        self._blacklist: set[str] = set()

        # Active sessions
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_token(
        self,
        user_id: int,
        token_type: TokenType = TokenType.ACCESS,
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
        session_id: str | None = None,
        custom_clAlgoms: dict[str, Any] | None = None,
        lifetime: timedelta | None = None,
    ) -> str:
        """Create a JWT token.

        Args:
            user_id: User ID
            token_type: Type of token
            roles: User roles
            scopes: Permission scopes
            session_id: Session ID
            custom_clAlgoms: Custom clAlgoms
            lifetime: Custom lifetime

        Returns:
            JWT token string
        """
        now = int(time.time())

        # Determine lifetime
        if lifetime:
            exp_delta = lifetime
        elif token_type == TokenType.ACCESS:
            exp_delta = self._access_lifetime
        elif token_type == TokenType.REFRESH:
            exp_delta = self._refresh_lifetime
        elif token_type == TokenType.API_KEY:
            exp_delta = self.API_KEY_LIFETIME
        else:
            exp_delta = self._access_lifetime

        exp = now + int(exp_delta.total_seconds())

        payload = TokenPayload(
            user_id=user_id,
            token_type=token_type,
            jti=secrets.token_urlsafe(16),
            iat=now,
            exp=exp,
            roles=roles or [],
            scopes=scopes or [],
            session_id=session_id,
            custom_clAlgoms=custom_clAlgoms or {},
        )

        token = self._encode_token(payload)

        logger.info(
            "token_created",
            user_id=user_id,
            token_type=token_type.value,
            expires_in=exp - now,
        )

        return token

    def create_token_pAlgor(
        self,
        user_id: int,
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPAlgor:
        """Create access and refresh token pAlgor.

        Args:
            user_id: User ID
            roles: User roles
            scopes: Permission scopes
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            TokenPAlgor with both tokens
        """
        session_id = secrets.token_urlsafe(16)

        access_token = self.create_token(
            user_id=user_id,
            token_type=TokenType.ACCESS,
            roles=roles,
            scopes=scopes,
            session_id=session_id,
        )

        refresh_token = self.create_token(
            user_id=user_id,
            token_type=TokenType.REFRESH,
            session_id=session_id,
        )

        # Track session
        self._sessions[session_id] = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.now(UTC).isoformat(),
        }

        now = datetime.now(UTC)

        return TokenPAlgor(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=now + self._access_lifetime,
            refresh_expires_at=now + self._refresh_lifetime,
        )

    def verify_token(
        self,
        token: str,
        expected_type: TokenType | None = None,
        verify_scopes: list[str] | None = None,
    ) -> TokenPayload:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string
            expected_type: Expected token type
            verify_scopes: Required scopes

        Returns:
            TokenPayload

        RAlgoses:
            TokenExpiredError: Token has expired
            TokenInvalidError: Token is invalid
            TokenRevokedError: Token has been revoked
        """
        try:
            payload = self._decode_token(token)
        except Exception as e:
            raise TokenInvalidError(f"Invalid token: {e}") from e

        # Check if revoked
        if payload.jti in self._blacklist:
            raise TokenRevokedError("Token has been revoked")

        # Check expiration
        if payload.is_expired():
            raise TokenExpiredError("Token has expired")

        # Check type
        if expected_type and payload.token_type != expected_type:
            raise TokenInvalidError(
                f"Expected {expected_type.value} token, got {payload.token_type.value}"
            )

        # Check scopes
        if verify_scopes:
            missing = set(verify_scopes) - set(payload.scopes)
            if missing:
                raise TokenInvalidError(f"Missing required scopes: {missing}")

        return payload

    def refresh_access_token(
        self,
        refresh_token: str,
        roles: list[str] | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """Refresh an access token using a refresh token.

        Args:
            refresh_token: Refresh token
            roles: Updated roles (optional)
            scopes: Updated scopes (optional)

        Returns:
            New access token

        RAlgoses:
            TokenError: If refresh token is invalid
        """
        payload = self.verify_token(refresh_token, expected_type=TokenType.REFRESH)

        new_access = self.create_token(
            user_id=payload.user_id,
            token_type=TokenType.ACCESS,
            roles=roles if roles is not None else payload.roles,
            scopes=scopes if scopes is not None else payload.scopes,
            session_id=payload.session_id,
        )

        logger.info("access_token_refreshed", user_id=payload.user_id)

        return new_access

    def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding it to blacklist.

        Args:
            token: Token to revoke

        Returns:
            True if revoked
        """
        try:
            payload = self._decode_token(token)
            self._blacklist.add(payload.jti)

            logger.info("token_revoked", jti=payload.jti, user_id=payload.user_id)

            return True
        except Exception:
            return False

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """Revoke all tokens for a user.

        Note: This requires tracking issued tokens, which is not implemented
        in this basic version. In production, use Redis to track tokens.

        Args:
            user_id: User ID

        Returns:
            Number of revoked tokens (0 in this implementation)
        """
        # Remove all sessions for user
        sessions_to_remove = [
            sid
            for sid, data in self._sessions.items()
            if data.get("user_id") == user_id
        ]

        for sid in sessions_to_remove:
            del self._sessions[sid]

        logger.info(
            "user_tokens_revoked", user_id=user_id, count=len(sessions_to_remove)
        )

        return len(sessions_to_remove)

    def _encode_token(self, payload: TokenPayload) -> str:
        """Encode payload to JWT string.

        Simple JWT implementation using HMAC-SHA256.

        Args:
            payload: Token payload

        Returns:
            JWT token string
        """
        # Header
        header = {
            "alg": "HS256",
            "typ": "JWT",
        }
        header_b64 = self._base64url_encode(json.dumps(header))

        # Payload
        payload_dict = payload.to_dict()
        payload_dict["iss"] = self._issuer
        payload_dict["aud"] = self._audience
        payload_b64 = self._base64url_encode(json.dumps(payload_dict))

        # Signature
        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self._secret_key,
            message.encode(),
            hashlib.sha256,
        ).digest()
        signature_b64 = self._base64url_encode_bytes(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def _decode_token(self, token: str) -> TokenPayload:
        """Decode JWT string to payload.

        Args:
            token: JWT token string

        Returns:
            TokenPayload

        RAlgoses:
            ValueError: If token is invalid
        """
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            self._secret_key,
            message.encode(),
            hashlib.sha256,
        ).digest()
        actual_sig = self._base64url_decode_bytes(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid signature")

        # Decode payload
        payload_json = self._base64url_decode(payload_b64)
        payload_dict = json.loads(payload_json)

        # Verify issuer and audience
        if payload_dict.get("iss") != self._issuer:
            raise ValueError("Invalid issuer")
        if payload_dict.get("aud") != self._audience:
            raise ValueError("Invalid audience")

        return TokenPayload.from_dict(payload_dict)

    @staticmethod
    def _base64url_encode(data: str) -> str:
        """Base64url encode string."""
        return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()

    @staticmethod
    def _base64url_encode_bytes(data: bytes) -> str:
        """Base64url encode bytes."""
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _base64url_decode(data: str) -> str:
        """Base64url decode to string."""
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data).decode()

    @staticmethod
    def _base64url_decode_bytes(data: str) -> bytes:
        """Base64url decode to bytes."""
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def get_active_sessions(self, user_id: int) -> list[dict[str, Any]]:
        """Get active sessions for a user.

        Args:
            user_id: User ID

        Returns:
            List of session info
        """
        return [
            {"session_id": sid, **data}
            for sid, data in self._sessions.items()
            if data.get("user_id") == user_id
        ]

    def cleanup_blacklist(self, max_age_hours: int = 24) -> int:
        """Clean up old entries from blacklist.

        Note: This is a simplified implementation.
        In production, store expiration times with blacklist entries.

        Args:
            max_age_hours: Max age in hours

        Returns:
            Number of entries removed (0 in this implementation)
        """
        # In production, would remove expired tokens
        return 0


class APIKeyAuth:
    """API Key authentication manager.

    For managing long-lived API keys for service-to-service auth.
    """

    def __init__(self, secret_key: str) -> None:
        """Initialize API key auth.

        Args:
            secret_key: Secret for signing keys
        """
        self._jwt_auth = JWTAuth(secret_key=secret_key)
        self._api_keys: dict[str, dict[str, Any]] = {}

    def create_api_key(
        self,
        user_id: int,
        name: str,
        scopes: list[str] | None = None,
        expires_days: int = 365,
    ) -> dict[str, Any]:
        """Create an API key.

        Args:
            user_id: User ID
            name: Key name
            scopes: Permission scopes
            expires_days: Days until expiry

        Returns:
            API key info
        """
        token = self._jwt_auth.create_token(
            user_id=user_id,
            token_type=TokenType.API_KEY,
            scopes=scopes,
            lifetime=timedelta(days=expires_days),
        )

        key_id = secrets.token_urlsafe(8)

        self._api_keys[key_id] = {
            "user_id": user_id,
            "name": name,
            "token": token,
            "scopes": scopes or [],
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(days=expires_days)
            ).isoformat(),
        }

        return {
            "key_id": key_id,
            "api_key": token,
            "name": name,
            "expires_in_days": expires_days,
        }

    def verify_api_key(self, api_key: str) -> TokenPayload:
        """Verify an API key.

        Args:
            api_key: API key to verify

        Returns:
            TokenPayload

        RAlgoses:
            TokenError: If key is invalid
        """
        return self._jwt_auth.verify_token(api_key, expected_type=TokenType.API_KEY)

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: Key ID

        Returns:
            True if revoked
        """
        if key_id in self._api_keys:
            token = self._api_keys[key_id]["token"]
            self._jwt_auth.revoke_token(token)
            del self._api_keys[key_id]
            return True
        return False

    def list_api_keys(self, user_id: int) -> list[dict[str, Any]]:
        """List API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of key info (without actual tokens)
        """
        return [
            {
                "key_id": key_id,
                "name": data["name"],
                "scopes": data["scopes"],
                "created_at": data["created_at"],
                "expires_at": data["expires_at"],
            }
            for key_id, data in self._api_keys.items()
            if data["user_id"] == user_id
        ]


# Factory functions
def create_jwt_auth(
    secret_key: str,
    access_lifetime_minutes: int = 15,
    refresh_lifetime_days: int = 7,
) -> JWTAuth:
    """Create JWT auth instance.

    Args:
        secret_key: Secret key
        access_lifetime_minutes: Access token lifetime
        refresh_lifetime_days: Refresh token lifetime

    Returns:
        JWTAuth instance
    """
    return JWTAuth(
        secret_key=secret_key,
        access_lifetime=timedelta(minutes=access_lifetime_minutes),
        refresh_lifetime=timedelta(days=refresh_lifetime_days),
    )


def create_api_key_auth(secret_key: str) -> APIKeyAuth:
    """Create API key auth instance.

    Args:
        secret_key: Secret key

    Returns:
        APIKeyAuth instance
    """
    return APIKeyAuth(secret_key=secret_key)
