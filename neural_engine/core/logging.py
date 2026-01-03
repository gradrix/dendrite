"""
Structured Logging for Dendrite

Provides JSON-formatted logging for production use with human-readable
console output for development.

Usage:
    from neural_engine.core.logging import get_logger
    
    logger = get_logger(__name__)
    logger.info("Processing goal", goal="fetch data", user_id=123)
    logger.warning("Low confidence", confidence=0.45)
    logger.error("Tool failed", tool="strava", error=str(e))

Environment variables:
    LOG_FORMAT: "json" (default in production) or "console" (development)
    LOG_LEVEL: DEBUG, INFO (default), WARNING, ERROR
    LOG_FILE: Optional file path for logging
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Any, Optional
from functools import lru_cache


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for structured logging.
    
    Output format:
    {"timestamp": "2024-01-01T12:00:00.000Z", "level": "INFO", "logger": "module", "message": "...", ...extra_fields}
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add location info for errors
        if record.levelno >= logging.WARNING:
            log_data["location"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }
        
        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable console formatter with colors and emojis.
    """
    
    COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[35m", # Magenta
    }
    RESET = "\033[0m"
    
    ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️ ",
        "WARNING": "⚠️ ",
        "ERROR": "❌",
        "CRITICAL": "💥",
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        icon = self.ICONS.get(record.levelname, "")
        reset = self.RESET
        
        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Format message
        msg = record.getMessage()
        
        # Add extra fields inline
        extra = ""
        if hasattr(record, "extra_fields") and record.extra_fields:
            extra_parts = [f"{k}={v}" for k, v in record.extra_fields.items()]
            extra = f" ({', '.join(extra_parts)})"
        
        # Format the line
        line = f"{color}{timestamp} {icon} [{record.name}] {msg}{extra}{reset}"
        
        # Add exception if present
        if record.exc_info:
            line += f"\n{self.formatException(record.exc_info)}"
        
        return line


class StructuredLogger(logging.Logger):
    """
    Logger that supports structured fields in log messages.
    
    Example:
        logger.info("User action", user_id=123, action="login")
    """
    
    def _log_with_fields(self, level: int, msg: str, args: tuple, 
                         exc_info=None, extra: dict = None, 
                         stack_info: bool = False, stacklevel: int = 1,
                         **fields):
        """Log with extra fields attached to the record."""
        if extra is None:
            extra = {}
        
        # Store fields for formatters to use
        extra["extra_fields"] = fields
        
        super()._log(level, msg, args, exc_info=exc_info, extra=extra,
                     stack_info=stack_info, stacklevel=stacklevel + 1)
    
    def debug(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.DEBUG):
            self._log_with_fields(logging.DEBUG, msg, args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.INFO):
            self._log_with_fields(logging.INFO, msg, args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log_with_fields(logging.WARNING, msg, args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.ERROR):
            self._log_with_fields(logging.ERROR, msg, args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.CRITICAL):
            self._log_with_fields(logging.CRITICAL, msg, args, **kwargs)


# Register our custom logger class
logging.setLoggerClass(StructuredLogger)


@lru_cache(maxsize=1)
def _setup_root_logger() -> None:
    """Configure the root logger once."""
    log_format = os.environ.get("LOG_FORMAT", "console").lower()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_file = os.environ.get("LOG_FILE")
    
    # Get root logger for our namespace
    root = logging.getLogger("neural_engine")
    root.setLevel(getattr(logging, log_level, logging.INFO))
    
    # Remove any existing handlers
    root.handlers.clear()
    
    # Choose formatter based on environment
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root.addHandler(file_handler)
    
    # Prevent propagation to root logger
    root.propagate = False


def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger for a module.
    
    Args:
        name: Module name, typically __name__
        
    Returns:
        Configured StructuredLogger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("Starting", component="orchestrator")
    """
    _setup_root_logger()
    
    # Ensure it's under our namespace
    if not name.startswith("neural_engine"):
        name = f"neural_engine.{name}"
    
    return logging.getLogger(name)


# Convenience functions for quick logging without getting a logger
def log_info(msg: str, **fields):
    """Quick info log."""
    get_logger("dendrite").info(msg, **fields)


def log_warning(msg: str, **fields):
    """Quick warning log."""
    get_logger("dendrite").warning(msg, **fields)


def log_error(msg: str, **fields):
    """Quick error log."""
    get_logger("dendrite").error(msg, **fields)


# Event logging for the "Public Pipe" concept
class EventType:
    """Standard event types for the public pipe."""
    GOAL_STARTED = "goal.started"
    GOAL_COMPLETED = "goal.completed"
    GOAL_FAILED = "goal.failed"
    NEURON_CALLED = "neuron.called"
    NEURON_COMPLETED = "neuron.completed"
    TOOL_SELECTED = "tool.selected"
    TOOL_EXECUTED = "tool.executed"
    CACHE_HIT = "cache.hit"
    CACHE_MISS = "cache.miss"


def log_event(event_type: str, **fields):
    """
    Log a structured event for the public pipe.
    
    Args:
        event_type: One of EventType constants
        **fields: Event-specific data
        
    Example:
        log_event(EventType.GOAL_STARTED, goal="fetch data", goal_id="abc123")
    """
    logger = get_logger("events")
    logger.info(event_type, event_type=event_type, **fields)
