"""
Tests for structured logging configuration.

Verifies that the logging setup from main.py is correctly applied and 
handles structured context via the 'extra' parameter.
"""

from __future__ import annotations

import logging
import pytest


def test_logging_setup_configures_root_logger():
    """setup_logging should configure the root logger and its handlers."""
    from app.main import setup_logging
    setup_logging()
    root = logging.getLogger()
    
    # Check if we have at least one handler (ConsoleHandler)
    assert len(root.handlers) >= 1
    
    # Verify we have our configured console handler with proper formatter
    console_handler = next((h for h in root.handlers if isinstance(h, logging.StreamHandler)), None)
    assert console_handler is not None
    
    # Check if formatter is set (it should be either "default" or "json")
    assert console_handler.formatter is not None


def test_extra_parameter_logging_call():
    """
    Ensure the logger accepts 'extra' without crashing.
    We don't use caplog here because setup_logging overrides handlers.
    """
    from app.main import setup_logging
    setup_logging()
    
    logger = logging.getLogger("test_structured")
    # This should pass without raising 
    logger.info("Test message", extra={"case_id": "123", "user_id": "456"})
