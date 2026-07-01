"""Input validation and sanitization for Telegram commands."""
import re
from typing import List

SYMBOL_RE = re.compile(r'^[A-Z0-9]{2,20}$')
SYMBOL_USDT_RE = re.compile(r'^[A-Z0-9]{2,10}USDT$')
CALLBACK_DATA_RE = re.compile(r'^[a-z_]+[0-9]*_?[A-Z0-9]*$')
MAX_SYMBOL_LEN = 20
MAX_ARGS_LEN = 500
MAX_CALLBACK_LEN = 64
MAX_PRICE = 10_000_000


def validate_symbol(raw: str) -> bool:
    """Validate a raw symbol input."""
    clean = raw.strip().upper()
    if not clean or len(clean) > MAX_SYMBOL_LEN:
        return False
    return bool(SYMBOL_RE.match(clean))


def validate_callback_data(data: str) -> bool:
    """Prevent callback data injection."""
    if not data or len(data) > MAX_CALLBACK_LEN:
        return False
    return bool(CALLBACK_DATA_RE.match(data))


def validate_price_input(raw: str) -> bool:
    """Validate price entry from user."""
    if not raw or len(raw) > 30:
        return False
    try:
        val = float(raw.replace(",", "").replace("$", ""))
        return 0 < val < MAX_PRICE
    except ValueError:
        return False


def sanitize_symbol(raw: str) -> str:
    """Normalize symbol: uppercase, strip whitespace."""
    return raw.strip().upper()[:MAX_SYMBOL_LEN]


def sanitize_command_args(text: str, max_args: int = 10) -> List[str]:
    """Split and limit command arguments."""
    parts = text.split()
    return [p.strip() for p in parts if p.strip()][:max_args]


def validate_uid(raw: str) -> bool:
    """Validate a Telegram user ID (positive integer)."""
    try:
        uid = int(raw.strip())
        return uid > 0
    except (ValueError, AttributeError):
        return False


def validate_limit(raw: str) -> bool:
    """Validate a limit/range parameter (positive int, reasonable max)."""
    try:
        val = int(raw.strip())
        return 1 <= val <= 1000
    except (ValueError, AttributeError):
        return False
