"""
Unit tests for bot/bot_security.py — input validation and sanitization.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestValidateSymbol:
    """validate_symbol accepts/rejects symbol inputs."""

    def test_validate_symbol_valid(self):
        from bot.bot_security import validate_symbol
        assert validate_symbol("BTC") is True
        assert validate_symbol("ETH") is True
        assert validate_symbol("BTCUSDT") is True
        assert validate_symbol("DOGEUSDT") is True
        assert validate_symbol("1INCHUSDT") is True

    def test_validate_symbol_invalid(self):
        from bot.bot_security import validate_symbol
        assert validate_symbol("") is False
        assert validate_symbol("A") is False
        assert validate_symbol("X" * 21) is False
        assert validate_symbol("BTC; DROP TABLE") is False
        assert validate_symbol("<script>") is False
        assert validate_symbol("BTC USDT") is False
        assert validate_symbol("BTC@USDT") is False


class TestValidateCallbackData:
    """validate_callback_data prevents injection in button callbacks."""

    def test_validate_callback_data_valid(self):
        from bot.bot_security import validate_callback_data
        assert validate_callback_data("sold_0_BTCUSDT") is True
        assert validate_callback_data("target_3_ETHUSDT") is True
        assert validate_callback_data("signals_active") is True
        assert validate_callback_data("back_list") is True
        assert validate_callback_data("add_BTCUSDT") is True
        assert validate_callback_data("trade_ETHUSDT") is True

    def test_validate_callback_data_invalid(self):
        from bot.bot_security import validate_callback_data
        assert validate_callback_data("<script>") is False
        assert validate_callback_data("'; DROP TABLE") is False
        assert validate_callback_data("") is False
        assert validate_callback_data("A" * 65) is False
        assert validate_callback_data("SIGNALS_ACTIVE") is False


class TestValidatePriceInput:
    """validate_price_input ensures numeric price is within bounds."""

    def test_validate_price_input_valid(self):
        from bot.bot_security import validate_price_input
        assert validate_price_input("45000") is True
        assert validate_price_input("45,000") is True
        assert validate_price_input("$50000") is True
        assert validate_price_input("0.001") is True
        assert validate_price_input("$1,234.56") is True

    def test_validate_price_input_invalid(self):
        from bot.bot_security import validate_price_input
        assert validate_price_input("-1") is False
        assert validate_price_input("abc") is False
        assert validate_price_input("") is False
        assert validate_price_input("0") is False
        assert validate_price_input("99999999") is False


class TestSanitizeSymbol:
    """sanitize_symbol normalizes symbol strings."""

    def test_sanitize_symbol_whitespace_and_case(self):
        from bot.bot_security import sanitize_symbol
        assert sanitize_symbol("  btc  ") == "BTC"
        assert sanitize_symbol(" eth ") == "ETH"
        assert sanitize_symbol("Dogeusdt") == "DOGEUSDT"

    def test_sanitize_symbol_truncation(self):
        from bot.bot_security import sanitize_symbol
        result = sanitize_symbol("A" * 30)
        assert len(result) == 20


class TestValidateUid:
    """validate_uid ensures Telegram user IDs are positive integers."""

    def test_validate_uid_valid(self):
        from bot.bot_security import validate_uid
        assert validate_uid("12345") is True
        assert validate_uid("1") is True
        assert validate_uid("  99999  ") is True

    def test_validate_uid_invalid(self):
        from bot.bot_security import validate_uid
        assert validate_uid("-1") is False
        assert validate_uid("abc") is False
        assert validate_uid("") is False
        assert validate_uid("0") is False


class TestValidateLimit:
    """validate_limit ensures range parameters are within bounds."""

    def test_validate_limit_valid(self):
        from bot.bot_security import validate_limit
        assert validate_limit("1") is True
        assert validate_limit("10") is True
        assert validate_limit("1000") is True

    def test_validate_limit_invalid(self):
        from bot.bot_security import validate_limit
        assert validate_limit("0") is False
        assert validate_limit("99999") is False
        assert validate_limit("-5") is False
        assert validate_limit("abc") is False


class TestSanitizeCommandArgs:
    """sanitize_command_args splits, trims, and limits args."""

    def test_sanitize_command_args_normal(self):
        from bot.bot_security import sanitize_command_args
        result = sanitize_command_args("/analyze BTC")
        assert result == ["/analyze", "BTC"]

    def test_sanitize_command_args_max_limit(self):
        from bot.bot_security import sanitize_command_args
        args = " ".join([f"arg{i}" for i in range(20)])
        result = sanitize_command_args(args, max_args=10)
        assert len(result) == 10

    def test_sanitize_command_args_trims_whitespace(self):
        from bot.bot_security import sanitize_command_args
        result = sanitize_command_args("  /start   BTC  ")
        assert result == ["/start", "BTC"]


class TestCallbackValidationIntegration:
    """Integration: handle_callback rejects invalid callback data."""

    @patch("bot.bot_handlers.requests")
    def test_handle_callback_rejects_invalid_data(self, mock_requests):
        from bot.bot_handlers import handle_callback
        cb = {
            "id": "cb_001",
            "data": "<script>alert(1)</script>",
            "message": {"chat": {"id": 123456}, "message_id": 100},
        }
        handle_callback(cb)
        assert mock_requests.post.call_count == 0

    @patch("bot.bot_handlers.requests")
    def test_handle_callback_accepts_valid_data(self, mock_requests):
        from bot.bot_handlers import handle_callback
        cb = {
            "id": "cb_002",
            "data": "nav_ignore",
            "message": {"chat": {"id": 123456}, "message_id": 100},
        }
        handle_callback(cb)
        assert mock_requests.post.call_count >= 1
