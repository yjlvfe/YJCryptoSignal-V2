"""
🚨 Alerting & Webhooks — Real-time notifications for CryptoSignal
Supports: Telegram, Discord, Slack, Generic Webhooks
"""
import json
import time
import logging
import threading
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from core.core_logging import get_context_logger

logger = get_context_logger("cryptosignal.alerting", {"component": "alerting"})

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    """Alert data structure"""
    title: str
    message: str
    level: AlertLevel = AlertLevel.INFO
    source: str = "cryptosignal"
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    fingerprint: str = ""  # For deduplication
    
    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = f"{self.source}:{self.title}:{hash(self.message)%10000}"

@dataclass
class WebhookConfig:
    """Webhook configuration"""
    name: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 10
    retry_count: int = 3
    retry_delay: float = 2.0
    enabled: bool = True
    # Filter: only send alerts matching these criteria
    min_level: AlertLevel = AlertLevel.INFO
    sources: List[str] = field(default_factory=list)  # empty = all
    tags: Dict[str, str] = field(default_factory=dict)  # must match all

class AlertManager:
    """Central alert manager with deduplication and webhook delivery"""
    
    def __init__(self, dedup_window: int = 300):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.dedup_window = dedup_window  # seconds
        self._sent_alerts: Dict[str, float] = {}  # fingerprint -> timestamp
        self._lock = threading.Lock()
        self._stats = {
            "sent": 0,
            "failed": 0,
            "deduplicated": 0
        }
    
    def add_webhook(self, config: WebhookConfig):
        """Register a webhook"""
        with self._lock:
            self.webhooks[config.name] = config
            logger.info(f"Added webhook: {config.name} -> {config.url}")
    
    def remove_webhook(self, name: str):
        """Remove a webhook"""
        with self._lock:
            if name in self.webhooks:
                del self.webhooks[name]
                logger.info(f"Removed webhook: {name}")
    
    def _should_send(self, alert: Alert, config: WebhookConfig) -> bool:
        """Check if alert should be sent to this webhook"""
        # Check min level
        level_order = {AlertLevel.INFO: 0, AlertLevel.WARNING: 1, AlertLevel.CRITICAL: 2}
        if level_order[alert.level] < level_order[config.min_level]:
            return False
        
        # Check source filter
        if config.sources and alert.source not in config.sources:
            return False
        
        # Check tag filters
        for key, value in config.tags.items():
            if alert.tags.get(key) != value:
                return False
        
        return True
    
    def _is_deduplicated(self, alert: Alert) -> bool:
        """Check if alert was recently sent"""
        with self._lock:
            now = time.time()
            # Clean old entries
            self._sent_alerts = {
                fp: ts for fp, ts in self._sent_alerts.items()
                if now - ts < self.dedup_window
            }
            
            if alert.fingerprint in self._sent_alerts:
                self._stats["deduplicated"] += 1
                return True
            
            self._sent_alerts[alert.fingerprint] = now
            return False
    
    def send_alert(self, alert: Alert) -> Dict[str, bool]:
        """Send alert to all matching webhooks"""
        results = {}
        
        # Deduplication check
        if self._is_deduplicated(alert):
            logger.debug(f"Alert deduplicated: {alert.fingerprint}")
            return results
        
        with self._lock:
            webhooks = list(self.webhooks.values())
        
        for config in webhooks:
            if not config.enabled:
                continue
            
            if not self._should_send(alert, config):
                continue
            
            success = self._deliver_with_retry(alert, config)
            results[config.name] = success
            
            with self._lock:
                if success:
                    self._stats["sent"] += 1
                else:
                    self._stats["failed"] += 1
        
        return results
    
    def _deliver_with_retry(self, alert: Alert, config: WebhookConfig) -> bool:
        """Deliver alert with retry logic"""
        payload = {
            "title": alert.title,
            "message": alert.message,
            "level": alert.level.value,
            "source": alert.source,
            "tags": alert.tags,
            "timestamp": alert.timestamp,
            "fingerprint": alert.fingerprint
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "YJCryptoSignal/3.0",
            **config.headers
        }
        
        for attempt in range(config.retry_count):
            try:
                response = requests.post(
                    config.url,
                    json=payload,
                    headers=headers,
                    timeout=config.timeout
                )
                
                if 200 <= response.status_code < 300:
                    logger.debug(f"Alert sent to {config.name} (attempt {attempt+1})")
                    return True
                else:
                    logger.warning(f"Webhook {config.name} returned {response.status_code}: {response.text[:200]}")
            
            except Exception as e:
                logger.warning(f"Webhook {config.name} attempt {attempt+1} failed: {e}")
            
            if attempt < config.retry_count - 1:
                time.sleep(config.retry_delay * (attempt + 1))  # Exponential backoff
        
        logger.error(f"Alert delivery failed to {config.name} after {config.retry_count} attempts")
        return False
    
    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return self._stats.copy()
    
    def get_registered_webhooks(self) -> List[str]:
        with self._lock:
            return list(self.webhooks.keys())


# ═══════════════════════════════════════════
# Pre-built webhook configurations
# ═══════════════════════════════════════════

def create_telegram_webhook(bot_token: str, chat_id: str, name: str = "telegram") -> WebhookConfig:
    """Create Telegram webhook config"""
    return WebhookConfig(
        name=name,
        url=f"https://api.telegram.org/bot{bot_token}/sendMessage",
        headers={},
        timeout=10,
        retry_count=3
    )


def create_telegram_webhook_from_env(name: str = "telegram") -> Optional[WebhookConfig]:
    """Create Telegram webhook from env vars TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID.
    
    Falls back to BOT_TOKEN / OWNER_ID for legacy compatibility.
    Returns None if neither TELEGRAM_BOT_TOKEN nor BOT_TOKEN is set.
    """
    import os
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or ""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("OWNER_ID") or ""
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — telegram webhook unavailable")
        return None
    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not set — telegram webhook chat target unknown")
        return None
    return create_telegram_webhook(bot_token=bot_token, chat_id=chat_id, name=name)

def create_discord_webhook(webhook_url: str, name: str = "discord") -> WebhookConfig:
    """Create Discord webhook config"""
    return WebhookConfig(
        name=name,
        url=webhook_url,
        headers={},
        timeout=10
    )

def create_slack_webhook(webhook_url: str, name: str = "slack") -> WebhookConfig:
    """Create Slack webhook config"""
    return WebhookConfig(
        name=name,
        url=webhook_url,
        headers={},
        timeout=10
    )

def create_generic_webhook(url: str, name: str, headers: Dict = None, **kwargs) -> WebhookConfig:
    """Create generic webhook config"""
    return WebhookConfig(
        name=name,
        url=url,
        headers=headers or {},
        **kwargs
    )


# ═══════════════════════════════════════════
# Global instance & convenience functions
# ═══════════════════════════════════════════

_alert_manager: Optional[AlertManager] = None
_alert_lock = threading.Lock()

def get_alert_manager() -> AlertManager:
    global _alert_manager
    with _alert_lock:
        if _alert_manager is None:
            _alert_manager = AlertManager()
        return _alert_manager

def send_alert(title: str, message: str, level: AlertLevel = AlertLevel.INFO, 
               source: str = "cryptosignal", tags: Dict = None, **kwargs) -> Dict[str, bool]:
    """Convenience function to send an alert"""
    alert = Alert(
        title=title,
        message=message,
        level=level,
        source=source,
        tags=tags or {},
        **kwargs
    )
    return get_alert_manager().send_alert(alert)

def alert_critical(message: str, **kwargs):
    """Send critical alert"""
    return send_alert("🔴 CRITICAL", message, AlertLevel.CRITICAL, **kwargs)

def alert_warning(message: str, **kwargs):
    """Send warning alert"""
    return send_alert("🟡 WARNING", message, AlertLevel.WARNING, **kwargs)

def alert_info(message: str, **kwargs):
    """Send info alert"""
    return send_alert("🔵 INFO", message, AlertLevel.INFO, **kwargs)


# ═══════════════════════════════════════════
# Domain-specific alert helpers
# ═══════════════════════════════════════════

def alert_ai_failure(provider: str, error: str, consecutive_failures: int = 1):
    """Alert on AI provider failure"""
    if consecutive_failures >= 3:
        return alert_critical(f"AI Provider {provider} failed {consecutive_failures}x", 
                             source="ai", tags={"provider": provider, "error": error})
    else:
        return alert_warning(f"AI Provider {provider} failed", 
                            source="ai", tags={"provider": provider, "error": error})

def alert_exchange_failure(exchange: str, error: str):
    """Alert on exchange API failure"""
    return alert_critical(f"Exchange {exchange} unavailable",
                         source="exchange", tags={"exchange": exchange, "error": error})

def alert_trade_sl_hit(symbol: str, pnl: float, entry: float, sl: float):
    """Alert on stop loss hit"""
    return alert_warning(f"SL Hit: {symbol} at {sl}",
                        source="trade", tags={
                            "symbol": symbol, "pnl": f"{pnl:.2f}%",
                            "entry": str(entry), "sl": str(sl)
                        })

def alert_signal_generated(symbol: str, direction: str, confidence: float):
    """Alert on new signal"""
    return alert_info(f"Signal: {direction} {symbol} ({confidence:.0f}%)",
                     source="scanner", tags={
                         "symbol": symbol, "direction": direction, "confidence": str(confidence)
                     })

def alert_system_health(check: str, status: str, details: str = ""):
    """Alert on health check"""
    if status != "healthy":
        return alert_critical(f"Health check failed: {check}",
                             source="health", tags={"check": check, "status": status, "details": details})
    return {}