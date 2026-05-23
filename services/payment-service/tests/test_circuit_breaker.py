"""Tests del Circuit Breaker (requieren Redis disponible)."""
import pytest

from app.core.circuit_breaker import CBState, CircuitBreaker


@pytest.fixture
def cb():
    """Circuit Breaker aislado para pruebas, reseteado antes y despues."""
    c = CircuitBreaker(name="test_cb", failure_threshold=3, open_ttl_seconds=2,
                       window_seconds=60)
    c.reset()
    yield c
    c.reset()


def test_initial_state_is_closed(cb):
    """Un Circuit Breaker nuevo inicia CLOSED y permite la llamada."""
    assert cb.get_state() == CBState.CLOSED
    allowed, state = cb.allow()
    assert allowed is True
    assert state == CBState.CLOSED


def test_opens_after_threshold(cb):
    """Tres fallos consecutivos abren el circuito y bloquean llamadas."""
    for _ in range(cb.failure_threshold):
        cb.record_failure()
    assert cb.get_state() == CBState.OPEN
    allowed, state = cb.allow()
    assert allowed is False
    assert state == CBState.OPEN


def test_success_resets(cb):
    """Un exito posterior reinicia fallos y mantiene el circuito cerrado."""
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.get_state() == CBState.CLOSED


def test_stats_exposes_redis_flag_and_failures(cb):
    """Las estadisticas exponen estado, contador y umbral operativo."""
    cb.record_failure()
    s = cb.stats()
    assert s["state"] == CBState.CLOSED.value
    assert s["failures"] == 1
    assert s["threshold"] == 3
