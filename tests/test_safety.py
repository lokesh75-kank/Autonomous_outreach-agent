"""Tests for safety mechanisms."""

import pytest
from datetime import datetime

from src.agents.linkedin_executor.safety import (
    CircuitBreaker,
    SafetyManager,
    is_safe_to_proceed,
)


def test_circuit_breaker_initial_state():
    """Test circuit breaker starts closed."""
    cb = CircuitBreaker()

    assert cb.state == "closed"
    assert cb.can_proceed() is True


def test_circuit_breaker_opens_on_failures():
    """Test circuit breaker opens after threshold failures."""
    cb = CircuitBreaker(failure_threshold=3)

    cb.record_failure()
    cb.record_failure()
    assert cb.can_proceed() is True

    cb.record_failure()
    assert cb.state == "open"
    assert cb.can_proceed() is False


def test_circuit_breaker_reset():
    """Test circuit breaker can be reset."""
    cb = CircuitBreaker()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()

    assert cb.state == "open"

    cb.reset()
    assert cb.state == "closed"
    assert cb.can_proceed() is True


def test_circuit_breaker_success_closes():
    """Test successful operation in half-open closes breaker."""
    cb = CircuitBreaker()
    cb.state = "half-open"

    cb.record_success()

    assert cb.state == "closed"
    assert cb.failures == 0


def test_safety_manager_initialization():
    """Test safety manager initializes correctly."""
    sm = SafetyManager()

    assert sm._security_warnings == 0
    assert sm.circuit_breaker.state == "closed"


def test_safety_manager_security_warning():
    """Test security warning handling."""
    sm = SafetyManager()

    sm.record_security_warning()
    assert sm._security_warnings == 1

    sm.record_security_warning()
    assert sm._security_warnings == 2
    assert sm.circuit_breaker.state == "open"


def test_safety_manager_status():
    """Test safety manager status reporting."""
    sm = SafetyManager()

    status = sm.get_status()

    assert "circuit_breaker_state" in status
    assert "security_warnings" in status
    assert "is_working_hours" in status
    assert "can_proceed" in status


def test_is_safe_to_proceed():
    """Test is_safe_to_proceed function."""
    result = is_safe_to_proceed()
    assert isinstance(result, bool)
