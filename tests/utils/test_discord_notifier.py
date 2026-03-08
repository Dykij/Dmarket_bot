"""Tests for Discord webhook notifier."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.utils.discord_notifier import (
    DiscordEmbed,
    DiscordNotifier,
    EmbedField,
    NotificationLevel,
    create_discord_notifier_from_env,
)


class TestEmbedField:
    """Tests for EmbedField dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        field = EmbedField(name="Test", value="Value", inline=True)
        data = field.to_dict()

        assert data["name"] == "Test"
        assert data["value"] == "Value"
        assert data["inline"] is True

    def test_default_inline(self):
        """Test default inline value."""
        field = EmbedField(name="Test", value="Value")
        assert field.inline is True


class TestDiscordEmbed:
    """Tests for DiscordEmbed dataclass."""

    def test_basic_embed(self):
        """Test basic embed creation."""
        embed = DiscordEmbed(
            title="Test Title",
            description="Test Description",
            color=0xFF0000,
        )

        data = embed.to_dict()

        assert data["title"] == "Test Title"
        assert data["description"] == "Test Description"
        assert data["color"] == 0xFF0000

    def test_embed_with_fields(self):
        """Test embed with fields."""
        embed = DiscordEmbed(
            title="Test",
            description="Desc",
            fields=[
                EmbedField("Field1", "Value1"),
                EmbedField("Field2", "Value2"),
            ],
        )

        data = embed.to_dict()

        assert "fields" in data
        assert len(data["fields"]) == 2

    def test_embed_with_footer(self):
        """Test embed with footer."""
        embed = DiscordEmbed(
            title="Test",
            description="Desc",
            footer="Footer text",
        )

        data = embed.to_dict()

        assert data["footer"]["text"] == "Footer text"

    def test_embed_without_optional_fields(self):
        """Test embed without optional fields."""
        embed = DiscordEmbed(title="Test", description="Desc")
        data = embed.to_dict()

        assert "footer" not in data
        assert "timestamp" not in data
        assert "thumbnAlgol" not in data


class TestDiscordNotifier:
    """Tests for DiscordNotifier class."""

    @pytest.fixture()
    def notifier(self):
        """Create notifier with test webhook URL."""
        return DiscordNotifier(
            webhook_url="https://discord.com/api/webhooks/test/token",
            username="Test Bot",
        )

    @pytest.fixture()
    def disabled_notifier(self):
        """Create disabled notifier."""
        return DiscordNotifier(
            webhook_url=None,
            enabled=False,
        )

    def test_init_with_webhook(self, notifier):
        """Test initialization with webhook URL."""
        assert notifier.enabled is True
        assert notifier.username == "Test Bot"

    def test_init_disabled_without_url(self):
        """Test that notifier is disabled without URL."""
        notifier = DiscordNotifier(webhook_url=None)
        assert notifier.enabled is False

    @pytest.mark.asyncio()
    async def test_send_notification_disabled(self, disabled_notifier):
        """Test that disabled notifier returns False."""
        result = await disabled_notifier.send_notification(
            title="Test",
            description="Test",
        )
        assert result is False

    @pytest.mark.asyncio()
    async def test_send_notification_success(self, notifier):
        """Test successful notification sending."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_notification(
                title="Test",
                description="Test description",
                level=NotificationLevel.SUCCESS,
            )

            assert result is True
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio()
    async def test_send_notification_with_fields(self, notifier):
        """Test notification with fields."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_notification(
                title="Test",
                description="Desc",
                fields=[EmbedField("Field", "Value")],
            )

            assert result is True

    @pytest.mark.asyncio()
    async def test_send_notification_webhook_error(self, notifier):
        """Test handling of webhook error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_notification(
                title="Test",
                description="Test",
            )

            assert result is False

    @pytest.mark.asyncio()
    async def test_send_notification_request_error(self, notifier):
        """Test handling of request error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.RequestError("Connection error")
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_notification(
                title="Test",
                description="Test",
            )

            assert result is False

    @pytest.mark.asyncio()
    async def test_send_trade_notification(self, notifier):
        """Test trade notification."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_trade_notification(
                action="bought",
                item_name="AK-47 | Redline",
                price=25.50,
                profit=5.00,
                game="csgo",
            )

            assert result is True

    @pytest.mark.asyncio()
    async def test_send_alert(self, notifier):
        """Test alert notification."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_alert(
                alert_type="price_drop",
                message="Price dropped below threshold",
                details={"item": "AWP | Asiimov", "price": 45.00},
            )

            assert result is True

    @pytest.mark.asyncio()
    async def test_send_error(self, notifier):
        """Test error notification."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_error(
                error_type="APIError",
                error_message="Failed to connect to DMarket API",
                traceback="Traceback...",
            )

            assert result is True

    @pytest.mark.asyncio()
    async def test_send_health_check(self, notifier):
        """Test health check notification."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_instance

            result = await notifier.send_health_check(
                status="healthy",
                components={
                    "API": "✅ OK",
                    "Database": "✅ OK",
                    "Cache": "✅ OK",
                },
            )

            assert result is True

    def test_get_level_emoji(self, notifier):
        """Test level emoji mapping."""
        assert notifier._get_level_emoji(NotificationLevel.INFO) == "ℹ️"
        assert notifier._get_level_emoji(NotificationLevel.SUCCESS) == "✅"
        assert notifier._get_level_emoji(NotificationLevel.WARNING) == "⚠️"
        assert notifier._get_level_emoji(NotificationLevel.ERROR) == "❌"
        assert notifier._get_level_emoji(NotificationLevel.CRITICAL) == "🚨"


class TestCreateNotifierFromEnv:
    """Tests for create_discord_notifier_from_env function."""

    def test_create_with_env_vars(self):
        """Test creation with environment variables."""
        with patch.dict(
            "os.environ",
            {
                "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
                "DISCORD_NOTIFICATIONS_ENABLED": "true",
            },
        ):
            notifier = create_discord_notifier_from_env()

            assert notifier.webhook_url == "https://discord.com/api/webhooks/test"
            assert notifier.enabled is True

    def test_create_disabled(self):
        """Test creation with disabled flag."""
        with patch.dict(
            "os.environ",
            {
                "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/test",
                "DISCORD_NOTIFICATIONS_ENABLED": "false",
            },
        ):
            notifier = create_discord_notifier_from_env()

            assert notifier.enabled is False

    def test_create_without_url(self):
        """Test creation without URL."""
        with patch.dict("os.environ", {}, clear=True):
            notifier = create_discord_notifier_from_env()

            assert notifier.webhook_url is None
            assert notifier.enabled is False
