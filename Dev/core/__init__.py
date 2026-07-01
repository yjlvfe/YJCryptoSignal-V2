"""
📦 YJCryptoSignal Core Package
"""
from .core_ai import (
    call_ai,
    analyze_coin,
    analyze_coin_pure,
    compare_opportunities,
    get_provider_status,
    force_provider_recovery,
    health_check,
    enrich_with_modules,
    AI_ANALYST_SYSTEM,
    AI_ANALYST_PURE_SYSTEM,
)

__all__ = [
    "call_ai",
    "analyze_coin",
    "analyze_coin_pure",
    "compare_opportunities",
    "get_provider_status",
    "force_provider_recovery",
    "health_check",
    "enrich_with_modules",
    "AI_ANALYST_SYSTEM",
    "AI_ANALYST_PURE_SYSTEM",
]