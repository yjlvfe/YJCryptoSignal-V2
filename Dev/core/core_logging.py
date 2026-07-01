"""
📋 Core Logging — Structured JSON logging for CryptoSignal
Compatible with ELK Stack, Datadog, Loki, etc.
"""
import json
import logging
import logging.handlers
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
import threading

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def __init__(self, service_name: str = "cryptosignal", include_traceback: bool = True):
        super().__init__()
        self.service_name = service_name
        self.include_traceback = include_traceback
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                          'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                          'message', 'pathname', 'process', 'processName', 
                          'relativeCreated', 'thread', 'threadName', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
        
        # Add exception info
        if record.exc_info and self.include_traceback:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)


class ContextLogger:
    """Logger with context propagation"""
    
    def __init__(self, name: str, base_context: Dict[str, Any] = None):
        self.logger = logging.getLogger(name)
        self.base_context = base_context or {}
        self._context = threading.local()
    
    def set_context(self, **kwargs):
        """Set context for current thread"""
        if not hasattr(self._context, 'data'):
            self._context.data = {}
        self._context.data.update(kwargs)
    
    def clear_context(self):
        """Clear context for current thread"""
        if hasattr(self._context, 'data'):
            self._context.data.clear()
    
    def get_context(self) -> Dict[str, Any]:
        """Get combined context"""
        ctx = self.base_context.copy()
        if hasattr(self._context, 'data'):
            ctx.update(self._context.data)
        return ctx
    
    def _log(self, level: int, message: str, **kwargs):
        ctx = self.get_context()
        extra = {**ctx, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        self._log(logging.ERROR, message, exc_info=True, **kwargs)


# ═══════════════════════════════════════════
# Setup functions
# ═══════════════════════════════════════════

def setup_json_logging(
    service_name: str = "cryptosignal",
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """Setup structured JSON logging"""
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    formatter = JSONFormatter(service_name=service_name)
    
    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation (10 MB max, 10 backup files)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10_485_760, backupCount=10
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_context_logger(name: str, base_context: Dict[str, Any] = None) -> ContextLogger:
    """Get a context-aware logger"""
    return ContextLogger(name, base_context)


# ═══════════════════════════════════════════
# Pre-configured loggers for components
# ═══════════════════════════════════════════

SCAN_LOGGER = get_context_logger("cryptosignal.scanner", {"component": "scanner"})
AI_LOGGER = get_context_logger("cryptosignal.ai", {"component": "ai"})
TRADE_LOGGER = get_context_logger("cryptosignal.trade", {"component": "trade"})
BOT_LOGGER = get_context_logger("cryptosignal.bot", {"component": "bot"})
EXCHANGE_LOGGER = get_context_logger("cryptosignal.exchange", {"component": "exchange"})
LEARNING_LOGGER = get_context_logger("cryptosignal.learning", {"component": "learning"})


# ═══════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════

def log_scan_start(cycle: int, symbols_count: int):
    SCAN_LOGGER.info("Scan cycle started", cycle=cycle, symbols_count=symbols_count)


def log_scan_complete(cycle: int, duration: float, signals: int, coins_scanned: int):
    SCAN_LOGGER.info("Scan cycle completed", 
                     cycle=cycle, duration_seconds=duration, 
                     signals_generated=signals, coins_scanned=coins_scanned)


def log_ai_request(provider: str, model: str, duration: float, success: bool, tokens: int = 0):
    AI_LOGGER.info("AI request completed",
                   provider=provider, model=model,
                   duration_seconds=duration, success=success,
                   tokens_used=tokens)


def log_trade_event(event: str, symbol: str, **details):
    TRADE_LOGGER.info(f"Trade {event}", event=event, symbol=symbol, **details)


def log_bot_command(command: str, user_id: int, success: bool = True):
    BOT_LOGGER.info("Bot command", command=command, user_id=user_id, success=success)


def log_exchange_call(exchange: str, endpoint: str, duration: float, success: bool, error: str = None):
    EXCHANGE_LOGGER.info("Exchange API call",
                         exchange=exchange, endpoint=endpoint,
                         duration_seconds=duration, success=success,
                         error=error)


def log_learning_event(event: str, strategy: str = None, **details):
    LEARNING_LOGGER.info(f"Learning {event}", event=event, strategy=strategy, **details)