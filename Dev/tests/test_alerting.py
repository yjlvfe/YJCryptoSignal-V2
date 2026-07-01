"""
Unit tests for utils/alerting.py
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import time


class TestWebhookConfig:
    """Test WebhookConfig dataclass."""

    def test_webhook_config_creation(self):
        """WebhookConfig should store all parameters."""
        from utils.alerting import WebhookConfig, AlertLevel

        config = WebhookConfig(
            name="test_webhook",
            url="https://hooks.example.com/webhook",
            headers={"X-Custom": "value"},
            timeout=10,
            retry_count=3,
            retry_delay=2.0,
            min_level=AlertLevel.WARNING,
        )

        assert config.name == "test_webhook"
        assert config.url == "https://hooks.example.com/webhook"
        assert config.headers == {"X-Custom": "value"}
        assert config.timeout == 10
        assert config.retry_count == 3
        assert config.retry_delay == 2.0
        assert config.min_level == AlertLevel.WARNING

    def test_webhook_config_defaults(self):
        """WebhookConfig should have sensible defaults."""
        from utils.alerting import WebhookConfig, AlertLevel

        config = WebhookConfig(name="test_webhook", url="https://example.com/webhook")

        assert config.headers == {}
        assert config.timeout == 10
        assert config.retry_count == 3
        assert config.retry_delay == 2.0
        assert config.min_level == AlertLevel.INFO


class TestAlertManager:
    """Test AlertManager class."""

    @pytest.fixture
    def manager(self):
        """Create a test AlertManager."""
        from utils.alerting import AlertManager
        return AlertManager(dedup_window=60)

    def test_manager_initialization(self, manager):
        """Manager should initialize with empty webhooks."""
        assert manager.webhooks == {}
        assert manager._sent_alerts == {}
        assert manager.dedup_window == 60

    def test_add_webhook(self, manager):
        """Should add webhook."""
        from utils.alerting import WebhookConfig

        config = WebhookConfig(name="test", url="https://example.com/webhook")
        manager.add_webhook(config)

        assert "test" in manager.webhooks
        assert manager.webhooks["test"] is config

    def test_remove_webhook(self, manager):
        """Should remove webhook."""
        from utils.alerting import WebhookConfig

        config = WebhookConfig(name="test", url="https://example.com/webhook")
        manager.add_webhook(config)
        manager.remove_webhook("test")

        assert "test" not in manager.webhooks

    def test_send_alert_basic(self, manager):
        """Should send alert to registered webhooks."""
        from utils.alerting import WebhookConfig, Alert, AlertLevel

        config = WebhookConfig(name="test", url="https://example.com/webhook")
        manager.add_webhook(config)

        with patch("utils.alerting.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            alert = Alert(title="Test Alert", message="This is a test", level=AlertLevel.WARNING, source="test")
            manager.send_alert(alert)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://example.com/webhook"


class TestConvenienceFunctions:
    """Test convenience functions for creating webhooks."""

    def test_create_telegram_webhook(self):
        """create_telegram_webhook should create proper config."""
        from utils.alerting import create_telegram_webhook

        config = create_telegram_webhook(bot_token="123:abc", chat_id="-1001234567890")

        assert "api.telegram.org/bot123:abc/sendMessage" in config.url
        assert config.name == "telegram"

    def test_create_discord_webhook(self):
        """create_discord_webhook should create proper config."""
        from utils.alerting import create_discord_webhook

        config = create_discord_webhook("https://discord.com/api/webhooks/123/abc")

        assert config.url == "https://discord.com/api/webhooks/123/abc"
        assert config.name == "discord"

    def test_create_slack_webhook(self):
        """create_slack_webhook should create proper config."""
        from utils.alerting import create_slack_webhook

        config = create_slack_webhook("https://hooks.slack.com/services/123/abc/def")

        assert config.url == "https://hooks.slack.com/services/123/abc/def"
        assert config.name == "slack"


class TestDomainAlertHelpers:
    """Test domain-specific alert helper functions."""

    def test_alert_ai_failure(self):
        """alert_ai_failure should send formatted alert."""
        from utils.alerting import alert_ai_failure

        with patch("utils.alerting.send_alert") as mock_send:
            alert_ai_failure(
                provider="openai",
                error="Rate limit exceeded",
            )
            mock_send.assert_called_once()

    def test_alert_exchange_failure(self):
        """alert_exchange_failure should send formatted alert."""
        from utils.alerting import alert_exchange_failure

        with patch("utils.alerting.send_alert") as mock_send:
            alert_exchange_failure(
                exchange="bybit",
                error="Connection timeout",
            )
            mock_send.assert_called_once()

    def test_alert_trade_sl_hit(self):
        """alert_trade_sl_hit should send formatted alert."""
        from utils.alerting import alert_trade_sl_hit

        with patch("utils.alerting.send_alert") as mock_send:
            alert_trade_sl_hit(
                symbol="BTCUSDT",
                pnl=-2.0,
                entry=45000.0,
                sl=44100.0,
            )
            mock_send.assert_called_once()