"""Shared pytest configuration for the plugin cell tests."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``pybuggy_services`` marker for the local SandboxPlugin tests.

    Consumers get the same registration from the sandbox plugin's configure step; without
    it, exercising the marker inside this suite would emit ``PytestUnknownMarkWarning``.
    """
    config.addinivalue_line("markers", "pybuggy_services: per-test sandbox data presets")
