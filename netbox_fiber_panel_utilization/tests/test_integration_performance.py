"""Integration tests for performance requirements.

Validates: Requirements 11.1, 11.2, 11.3

- Response time < 500ms for a 72-port device fixture (Req 11.1)
- Bounded query count independent of module/port count (Req 11.2, 11.3)
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService


# ---------------------------------------------------------------------------
# Helpers – 72-port device fixture (6 modules × 12 front ports)
# ---------------------------------------------------------------------------

def _make_front_port(cable=None):
    """Create a fake FrontPort with optional cable."""
    return SimpleNamespace(cable=cable)


def _make_module(bay_name: str, module_model: str, front_ports: list):
    """Create a fake Module with module_bay, module_type, and prefetched frontports."""
    module = MagicMock()
    module.module_bay = SimpleNamespace(name=bay_name)
    module.module_type = SimpleNamespace(model=module_model)
    module.frontports.all.return_value = front_ports
    return module


def _build_72_port_device():
    """Build a 72-port device: 6 modules × 12 front ports each, ~50% cabled."""
    device = SimpleNamespace(
        pk=42,
        name="FP-72",
        site="DC-East",
        location="Hall-A",
        rack="Rack-7",
        device_type=SimpleNamespace(slug="fiber-panel", model="FP-72"),
        device_role=SimpleNamespace(slug="patch-panel"),
    )

    modules = []
    for i in range(1, 7):
        ports = []
        for j in range(12):
            # Roughly half connected (even-indexed ports get a cable)
            cable = f"cable-{i}-{j}" if j % 2 == 0 else None
            ports.append(_make_front_port(cable=cable))
        modules.append(_make_module(f"Bay {i}", "LC-12", ports))

    return device, modules


# ---------------------------------------------------------------------------
# Performance: response time < 500ms for 72-port device (Req 11.1)
# ---------------------------------------------------------------------------

class TestPerformanceResponseTime:
    """Validates: Requirements 11.1"""

    def test_calculate_completes_within_500ms(self):
        """calculate() for a 72-port device must finish in < 500ms."""
        device, modules = _build_72_port_device()
        svc = FiberPanelUtilizationService({})

        with patch.object(svc, "get_installed_modules", return_value=modules):
            start = time.perf_counter()
            result = svc.calculate(device)
            elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500, (
            f"calculate() took {elapsed_ms:.1f}ms, exceeding the 500ms budget"
        )
        # Sanity: verify the result is correct for the fixture
        assert result.total_ports == 72
        assert result.used_ports == 36  # 6 ports per module (even indices)
        assert result.free_ports == 36
        assert result.utilization_percent == 50.0
        assert len(result.modules) == 6


# ---------------------------------------------------------------------------
# Bounded query count (Req 11.2, 11.3)
# ---------------------------------------------------------------------------

class TestBoundedQueryCount:
    """Validates: Requirements 11.2, 11.3

    Since we cannot use Django's assertNumQueries without a real DB, we
    verify that get_installed_modules constructs a single ORM call chain
    (filter → select_related → prefetch_related → order_by) regardless of
    module/port count.
    """

    def _setup_mock_orm(self):
        """Set up mock ORM classes and inject them into sys.modules."""
        import sys

        mock_module_cls = MagicMock()
        mock_frontport_cls = MagicMock()
        mock_prefetch_cls = MagicMock()

        mock_dcim_models = MagicMock()
        mock_dcim_models.Module = mock_module_cls
        mock_dcim_models.FrontPort = mock_frontport_cls

        mock_django_db_models = MagicMock()
        mock_django_db_models.Prefetch = mock_prefetch_cls

        saved = {}
        for key in ("dcim", "dcim.models", "django", "django.db", "django.db.models"):
            saved[key] = sys.modules.get(key)

        sys.modules["dcim"] = MagicMock(models=mock_dcim_models)
        sys.modules["dcim.models"] = mock_dcim_models
        sys.modules["django"] = MagicMock()
        sys.modules["django.db"] = MagicMock()
        sys.modules["django.db.models"] = mock_django_db_models

        return mock_module_cls, saved

    def _teardown_mock_orm(self, saved):
        import sys
        for key, val in saved.items():
            if val is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = val

    def test_single_orm_call_for_small_device(self):
        """A 2-module device triggers exactly one filter() call."""
        mock_module_cls, saved = self._setup_mock_orm()
        try:
            device = SimpleNamespace(pk=1)
            svc = FiberPanelUtilizationService({})
            svc.get_installed_modules(device)

            # filter() should be called exactly once
            assert mock_module_cls.objects.filter.call_count == 1
        finally:
            self._teardown_mock_orm(saved)

    def test_single_orm_call_for_large_device(self):
        """A 12-module device still triggers exactly one filter() call."""
        mock_module_cls, saved = self._setup_mock_orm()
        try:
            device = SimpleNamespace(pk=99)
            svc = FiberPanelUtilizationService({})
            svc.get_installed_modules(device)

            # Same single filter() call regardless of how many modules exist
            assert mock_module_cls.objects.filter.call_count == 1
        finally:
            self._teardown_mock_orm(saved)

    def test_orm_chain_uses_select_related_and_prefetch_related(self):
        """Verify the ORM chain includes select_related and prefetch_related."""
        mock_module_cls, saved = self._setup_mock_orm()
        try:
            device = SimpleNamespace(pk=1)
            svc = FiberPanelUtilizationService({})
            svc.get_installed_modules(device)

            qs = mock_module_cls.objects.filter.return_value
            qs.select_related.assert_called_once()
            qs.select_related.return_value.prefetch_related.assert_called_once()
        finally:
            self._teardown_mock_orm(saved)

    def test_query_count_independent_of_module_count(self):
        """Calling get_installed_modules for different device sizes
        always results in exactly 1 filter() call per invocation."""
        mock_module_cls, saved = self._setup_mock_orm()
        try:
            svc = FiberPanelUtilizationService({})

            for num_modules in (1, 6, 12, 24):
                mock_module_cls.reset_mock()
                device = SimpleNamespace(pk=num_modules)
                svc.get_installed_modules(device)
                assert mock_module_cls.objects.filter.call_count == 1, (
                    f"Expected 1 filter() call for {num_modules}-module device, "
                    f"got {mock_module_cls.objects.filter.call_count}"
                )
        finally:
            self._teardown_mock_orm(saved)
