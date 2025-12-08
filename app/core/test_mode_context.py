"""
Test Mode Context - Global context for test mode flag.

Uses Python contextvars to pass test_mode through all layers
without having to thread it through every function call.
"""
from contextvars import ContextVar

# Context variable for test mode (0, 1, or 2)
test_mode_var: ContextVar[int] = ContextVar('test_mode', default=0)


def get_test_mode() -> int:
    """Get current test mode from context."""
    return test_mode_var.get()


def set_test_mode(mode: int) -> None:
    """Set test mode in context."""
    test_mode_var.set(mode)
