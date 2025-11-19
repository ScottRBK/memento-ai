"""Centralised logging configuration

This module provides:
- JSONFormatter: Structured JSON logs
- ConsoleFormatter: Human-readble for development (with pretty colours)
- SensitiveDataFilter: Masks passwords, tokens, connection strings
- configure_logging(): this just sets up the Queue handler for asyncio-safe logging
"""

import json
import logging
import logging.config
import logging.handlers
import re
import sys
from queue import Queue
from datetime import datetime, timezone, date
from uuid import UUID

class ConsoleFormatter(logging.Formatter):
    """
    Console formatter with Pretty ANSI colour codes for development.

    Colours log levels for easy visual scanning:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Magenta
    """

    COLOURS = {
        "DEBUG": "\033[36m",   # Cyan
        "INFO": "\033[32m",    # Green
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",   # Red
        "CRITICAL": "\033[35m" # Magenta
     }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with coloured level name."""

        colour = self.COLOURS.get(record.levelname, self.RESET)

        levelname_coloured = f"{colour}{record.levelname}{self.RESET}"

        original_levelname = record.levelname
        record.levelname = levelname_coloured

        formatted = super().format(record)

        record.levelname = original_levelname

        return formatted 
    
class SensitiveDataFilter(logging.Filter):
    """
    Filter to mask sensitive data in log messages.

    Patterns masked:
    - Passwords (password=xxx, "password": "xxx")
    - Tokens (token=xxx, bearer xxx)
    - PostgreSQL connection strings (hides user:password)
    """

    SENSITIVE_PATTERNS = [
        # password=something or password="something" or "password":"something"
        (re.compile(r'password["\s:=]+["\']?([^"\s,}]+)["\']?', re.I), 'password=***'),
        # token=something or "token":"something"
        (re.compile(r'token["\s:=]+["\']?([^"\s,}]+)["\']?', re.I), 'token=***'),
        # bearer xxx
        (re.compile(r'bearer\s+([^\s,}]+)', re.I), 'bearer ***'),
        # Generic database connection string: scheme://user:password@host
        (re.compile(r'://[^:/@]+:[^@]+@', re.I), '://***:***@'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Mask sensitive data in log message.

        Returns True to allow the log through (after modification).
        """

        if isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # Also mask args if it's present in there as well innit
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._mask_value(v) for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_value(arg) for arg in record.args)
        
        return True
    
    def _mask_value(self, value):
        """Mask a value if it's a string that matches patterns"""
        if isinstance(value, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                value = pattern.sub(replacement, value)
        return value


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs each log record as a single line of JSON with fields:
    - timestamp: ISO 8601 UTC timestamp
    - level: Log Level
    - logger: Logger name (module path)
    - message: Log message
    - module, function, line: source code location
    - exception: Stack trace (if present)
    - All extra={} fields from logger calls
    - request_id, user_id: from contextvars (if set)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from logger.info(..., extra={...})
        # Standard LogRecord attributes to skip
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'getMessage'
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_data[key] = value

        # Add contextvars (request_id, user_id) if available
        # Import here to avoid circular dependency
        try:
            from app.middleware.logging_middleware import get_request_id, get_user_id
            if request_id := get_request_id():
                log_data["request_id"] = request_id
            if user_id := get_user_id():
                log_data["user_id"] = user_id
        except ImportError:
            # Middleware not yet created, skip contextvar injection
            pass
        
        return json.dumps(log_data, default=_serialise_log_value)
    
def _serialise_log_value(obj):
    """Handle non-JSON-serialisable types"""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


# Global listener instance (stored for cleanup)
_queue_listener: logging.handlers.QueueListener | None = None


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "console"
) -> logging.handlers.QueueListener:
    """
    Configure centralized logging with QueueHandler for asyncio.

    This function sets up:
    1. QueueHandler (non-blocking, asyncio-safe)
    2. QueueListener in separate thread
    3. Formatter (JSON or Console based on log_format)
    4. SensitiveDataFilter
    5. Root logger configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: "json" for production, "console" for development

    Returns:
        QueueListener instance (must be stopped during shutdown)

    Learning: QueueHandler is CRITICAL for asyncio. Without it, logging
    I/O operations (file writes, network) block the event loop, causing
    slowdowns. The QueueListener runs in a separate thread, so I/O happens
    off the event loop.
    """
    global _queue_listener

    # Create queue for log records
    log_queue: Queue = Queue(-1)  # Unlimited size

    # Create the appropriate formatter
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Create console handler (writes to stderr to avoid interfering with stdio transport)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())

    # Create QueueListener with the real handler
    # respect_handler_level=True means handler's level is checked
    _queue_listener = logging.handlers.QueueListener(
        log_queue,
        console_handler,
        respect_handler_level=True
    )

    # Start the listener thread
    _queue_listener.start()

    # Configure root logger with QueueHandler
    queue_handler = logging.handlers.QueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(queue_handler)

    # Configure library loggers
    # Reduce noise from uvicorn access logs (keep only warnings+)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Reduce sqlalchemy engine logs (only show warnings+)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Keep FastAPI at INFO
    logging.getLogger("fastapi").setLevel(logging.INFO)

    return _queue_listener


def shutdown_logging():
    """
    Shutdown the QueueListener gracefully.

    Call this during application shutdown to ensure all queued
    log records are flushed before exit.

    """
    global _queue_listener
    if _queue_listener:
        _queue_listener.stop()
        _queue_listener = None


