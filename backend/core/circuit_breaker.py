"""Circuit breaker for LLM API calls."""

from __future__ import annotations

import time

from core.logging import get_logger

logger = get_logger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern for external API calls.

    States:
        CLOSED: Normal operation, requests pass through
        OPEN: Too many failures, requests blocked
        HALF_OPEN: After cooldown, allow one test request
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_failure_time: float | None = None
        self._state = "closed"

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is blocking requests."""
        if self._state == "closed":
            return False

        if self._state == "open":
            # Check if cooldown has passed
            if self._last_failure_time and (time.time() - self._last_failure_time > self._cooldown_seconds):
                self._state = "half_open"
                logger.info("circuit_breaker_half_open", cooldown=self._cooldown_seconds)
                return False  # Allow one test request
            return True

        return False  # half_open allows requests

    def record_failure(self) -> None:
        """Record a failure and potentially trip the circuit."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self._failure_threshold:
            self._state = "open"
            logger.error(
                "circuit_breaker_opened",
                failures=self._failure_count,
                threshold=self._failure_threshold,
            )

    def record_success(self) -> None:
        """Record a success and reset the breaker."""
        if self._state == "half_open":
            logger.info("circuit_breaker_closed", reason="successful_test_request")

        self._failure_count = 0
        self._state = "closed"
        self._last_failure_time = None

    @property
    def state(self) -> str:
        return self._state

    def reset(self) -> None:
        """Force reset the circuit breaker."""
        self._failure_count = 0
        self._state = "closed"
        self._last_failure_time = None


# Global circuit breaker instance
circuit_breaker = CircuitBreaker()
