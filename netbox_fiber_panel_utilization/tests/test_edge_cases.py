"""Unit tests for qualification edge cases and empty states.

Validates: Requirements 1.5, 1.7, 2.1, 3.5, 8.4

Note: Requirements 1.5, 1.7, 2.1 are covered in test_service_qualification.py.
      Requirement 3.5 is covered in test_service_calculation.py.
      This file adds coverage for Req 8.4 (unexpected exception handling).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from netbox_fiber_panel_utilization.services import (
    FiberPanelUtilizationService,
    ModuleUtilization,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_device(pk=1, name="Panel-1", site="Site A", location="Room 1", rack="Rack 1"):
    return SimpleNamespace(
        pk=pk,
        name=name,
        site=site,
        location=location,
        rack=rack,
        device_type=SimpleNamespace(slug="fiber-panel", model="FP-4U"),
        device_role=SimpleNamespace(slug="patch-panel"),
    )


# ---------------------------------------------------------------------------
# Req 8.4 – Unexpected exception during calculation
# ---------------------------------------------------------------------------

class TestUnexpectedExceptionHandling:
    """Verify that unexpected exceptions in the service layer are propagated
    so that callers (template extension, views) can catch and handle them.

    Per the design, the service layer does NOT swallow exceptions.
    The template extension (task 4.1) catches Exception, logs it, and
    displays 'Unable to calculate utilization'.

    These tests verify:
    1. The exception propagates from calculate() when get_module_breakdown fails.
    2. The exception propagates from calculate() when an internal error occurs.
    """

    def test_calculate_propagates_exception_from_get_module_breakdown(self):
        """When get_module_breakdown raises, calculate() should propagate it."""
        svc = FiberPanelUtilizationService({})
        device = _make_device()

        with patch.object(
            svc, 'get_module_breakdown', side_effect=RuntimeError("DB connection lost")
        ):
            with pytest.raises(RuntimeError, match="DB connection lost"):
                svc.calculate(device)

    def test_calculate_propagates_exception_from_get_installed_modules(self):
        """When get_installed_modules raises, get_module_breakdown propagates it."""
        svc = FiberPanelUtilizationService({})
        device = _make_device()

        with patch.object(
            svc, 'get_installed_modules', side_effect=ConnectionError("timeout")
        ):
            with pytest.raises(ConnectionError, match="timeout"):
                svc.get_module_breakdown(device)

    def test_exception_can_be_caught_and_logged_by_caller(self, caplog):
        """Demonstrate the pattern callers should use (Req 8.4):
        catch Exception, log it, return a friendly message."""
        svc = FiberPanelUtilizationService({})
        device = _make_device()

        with patch.object(
            svc, 'get_module_breakdown', side_effect=RuntimeError("unexpected failure")
        ):
            # Simulate what template_content.py should do (Req 8.4)
            with caplog.at_level(logging.ERROR):
                try:
                    svc.calculate(device)
                    friendly_message = None  # Should not reach here
                except Exception:
                    logger = logging.getLogger("netbox_fiber_panel_utilization")
                    logger.exception("Error calculating utilization for device %s", device.pk)
                    friendly_message = "Unable to calculate utilization"

            assert friendly_message == "Unable to calculate utilization"
            assert "Error calculating utilization for device 1" in caplog.text
            assert "unexpected failure" in caplog.text


# ---------------------------------------------------------------------------
# Req 3.5 – Zero-port module in breakdown returns 0.0%
# ---------------------------------------------------------------------------

class TestZeroPortModuleUtilization:
    """Verify ModuleUtilization.utilization_percent handles zero total_ports."""

    def test_zero_total_ports_returns_zero_percent(self):
        mod = ModuleUtilization(bay_name="Bay 1", module_model="LC-0", used_ports=0, total_ports=0)
        assert mod.utilization_percent == 0.0

    def test_nonzero_ports_calculates_correctly(self):
        mod = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=3, total_ports=12)
        assert mod.utilization_percent == 25.0
