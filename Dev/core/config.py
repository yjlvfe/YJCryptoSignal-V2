"""
core/config.py — Shared configuration constants for YJCryptoSignal.

This module is the single source of truth for configuration values
that are needed by multiple layers (core/, trade/, bot/, etc.).
Import from here instead of from layer-specific config files.
"""
import os

# ── Position sizing ──────────────────────────────────────────────
# Percentage of portfolio allocated per trade (0–100).
# Configurable via POSITION_SIZE_PCT env var.
POSITION_SIZE_PCT: float = float(os.getenv("POSITION_SIZE_PCT", "10.0"))
