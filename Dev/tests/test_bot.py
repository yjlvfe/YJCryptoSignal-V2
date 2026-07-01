"""
Unit tests for bot/ modules.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os
import json


class TestBotConfig:
    """Test bot configuration."""

    def test_config_loads_from_env(self):
        """Config should load from environment variables."""
        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "test_token_123",
            "OWNER_ID": "123456789",
            "POSITION_SIZE_PCT": "15.0",
        }):
            # Reload to capture env changes
            import importlib
            import bot.bot_config
            importlib.reload(bot.bot_config)

            assert bot.bot_config.BOT_TOKEN == "test_token_123"
            assert bot.bot_config.OWNER_ID == 123456789
            assert bot.bot_config.POSITION_SIZE_PCT == 15.0


class TestBotUserLists:
    """Test bot watchlist and subscriber management."""

    @pytest.fixture(autouse=True)
    def setup_files(self, tmp_path):
        """Mock paths in bot_userlists to use temp directory."""
        with patch("trade.trade_userlists.DATA_DIR", tmp_path), \
             patch("trade.trade_userlists.LISTS_FILE", tmp_path / "user_lists.json"), \
             patch("trade.trade_userlists.SUBS_FILE", tmp_path / "trade_subscribers.json"), \
             patch("trade.trade_userlists.ENTRY_PRICES_FILE", tmp_path / "user_entry_prices.json"), \
             patch("trade.trade_userlists.TRACKING_FILE", tmp_path / "user_tracking.json"), \
             patch("trade.trade_userlists.SALES_FILE", tmp_path / "user_sales.json"):
            yield

    def test_add_remove_user_list(self):
        """Should manage symbol watchlists per user."""
        from trade.trade_userlists import add_to_user_list, remove_from_user_list, get_user_list, is_in_user_list

        user_id = 555555
        symbol = "BTCUSDT"

        assert add_to_user_list(user_id, symbol) is True
        assert is_in_user_list(user_id, symbol) is True
        assert symbol in get_user_list(user_id)

        assert remove_from_user_list(user_id, symbol) is True
        assert is_in_user_list(user_id, symbol) is False


class TestBotHandlers:
    """Test webhook-based handlers."""

    @patch("bot.bot_handlers.safe_send")
    def test_handle_update_start(self, mock_safe_send):
        """handle_update should process '/start' command."""
        from bot.bot_handlers import handle_update

        update = {
            "update_id": 10001,
            "message": {
                "message_id": 999,
                "chat": {"id": 123456, "type": "private"},
                "from": {"id": 123456, "first_name": "Test User"},
                "text": "/start"
            }
        }

        handle_update(update)

        mock_safe_send.assert_called_once()
        args = mock_safe_send.call_args[0]
        assert args[0] == 123456
        assert "مرحباً" in args[1] or "Welcome" in args[1]