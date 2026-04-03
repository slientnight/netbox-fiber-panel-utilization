"""Unit tests for FiberPanelUtilizationService calculation methods.

Tests: get_installed_modules, get_front_ports, get_module_breakdown, calculate.
Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 11.2, 11.3
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from netbox_fiber_panel_utilization.services import (
    FiberPanelUtilizationService,
    ModuleUtilization,
    PanelUtilization,
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


def _make_front_port(cable=None):
    """Create a fake FrontPort with optional cable."""
    return SimpleNamespace(cable=cable)


def _make_module(bay_name, module_model, front_ports):
    """Create a fake Module with module_bay, module_type, and prefetched frontports."""
    module = MagicMock()
    module.module_bay = SimpleNamespace(name=bay_name)
    module.module_type = SimpleNamespace(model=module_model)
    # Simulate prefetched frontports.all() returning the list
    module.frontports.all.return_value = front_ports
    return module


def _patch_get_installed_modules(svc, modules):
    """Patch get_installed_modules to return a list of fake modules."""
    return patch.object(svc, 'get_installed_modules', return_value=modules)


# ---------------------------------------------------------------------------
# get_installed_modules
# ---------------------------------------------------------------------------

class TestGetInstalledModules:
    def test_calls_orm_with_correct_filters(self):
        """Verify the ORM query chain is constructed correctly."""
        device = _make_device()
        svc = FiberPanelUtilizationService({})

        mock_module_cls = MagicMock()
        mock_frontport_cls = MagicMock()
        mock_prefetch_cls = MagicMock()

        mock_dcim_models = MagicMock()
        mock_dcim_models.Module = mock_module_cls
        mock_dcim_models.FrontPort = mock_frontport_cls

        mock_django_prefetch = MagicMock()
        mock_django_prefetch.Prefetch = mock_prefetch_cls

        saved = {}
        for key in ('dcim', 'dcim.models', 'django', 'django.db', 'django.db.models'):
            saved[key] = sys.modules.get(key)

        sys.modules['dcim'] = MagicMock(models=mock_dcim_models)
        sys.modules['dcim.models'] = mock_dcim_models
        mock_django_db_models = MagicMock()
        mock_django_db_models.Prefetch = mock_prefetch_cls
        sys.modules['django'] = MagicMock()
        sys.modules['django.db'] = MagicMock()
        sys.modules['django.db.models'] = mock_django_db_models

        try:
            svc.get_installed_modules(device)
            mock_module_cls.objects.filter.assert_called_once_with(
                module_bay__device=device,
            )
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val


# ---------------------------------------------------------------------------
# get_front_ports
# ---------------------------------------------------------------------------

class TestGetFrontPorts:
    def test_returns_frontports_all(self):
        """get_front_ports delegates to module.frontports.all()."""
        ports = [_make_front_port(), _make_front_port(cable="cable-1")]
        module = MagicMock()
        module.frontports.all.return_value = ports

        svc = FiberPanelUtilizationService({})
        result = svc.get_front_ports(module)
        assert result == ports
        module.frontports.all.assert_called_once()


# ---------------------------------------------------------------------------
# get_module_breakdown
# ---------------------------------------------------------------------------

class TestGetModuleBreakdown:
    def test_single_module_all_connected(self):
        ports = [_make_front_port(cable="c1"), _make_front_port(cable="c2")]
        mod = _make_module("Bay 1", "LC-12", ports)

        svc = FiberPanelUtilizationService({})
        with _patch_get_installed_modules(svc, [mod]):
            result = svc.get_module_breakdown(_make_device())

        assert len(result) == 1
        assert result[0].bay_name == "Bay 1"
        assert result[0].module_model == "LC-12"
        assert result[0].used_ports == 2
        assert result[0].total_ports == 2

    def test_single_module_none_connected(self):
        ports = [_make_front_port(), _make_front_port()]
        mod = _make_module("Bay 1", "LC-12", ports)

        svc = FiberPanelUtilizationService({})
        with _patch_get_installed_modules(svc, [mod]):
            result = svc.get_module_breakdown(_make_device())

        assert result[0].used_ports == 0
        assert result[0].total_ports == 2

    def test_multiple_modules(self):
        mod1 = _make_module("Bay 1", "LC-12", [
            _make_front_port(cable="c1"), _make_front_port(),
        ])
        mod2 = _make_module("Bay 2", "LC-24", [
            _make_front_port(cable="c1"), _make_front_port(cable="c2"),
            _make_front_port(),
        ])

        svc = FiberPanelUtilizationService({})
        with _patch_get_installed_modules(svc, [mod1, mod2]):
            result = svc.get_module_breakdown(_make_device())

        assert len(result) == 2
        assert result[0].bay_name == "Bay 1"
        assert result[0].used_ports == 1
        assert result[0].total_ports == 2
        assert result[1].bay_name == "Bay 2"
        assert result[1].used_ports == 2
        assert result[1].total_ports == 3

    def test_empty_modules(self):
        """No installed modules → empty breakdown."""
        svc = FiberPanelUtilizationService({})
        with _patch_get_installed_modules(svc, []):
            result = svc.get_module_breakdown(_make_device())

        assert result == []

    def test_module_with_zero_ports(self):
        mod = _make_module("Bay 1", "LC-0", [])

        svc = FiberPanelUtilizationService({})
        with _patch_get_installed_modules(svc, [mod]):
            result = svc.get_module_breakdown(_make_device())

        assert result[0].used_ports == 0
        assert result[0].total_ports == 0


# ---------------------------------------------------------------------------
# calculate
# ---------------------------------------------------------------------------

class TestCalculate:
    def test_basic_calculation(self):
        """Standard case with mixed connected/free ports."""
        svc = FiberPanelUtilizationService({})
        breakdown = [
            ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=6, total_ports=12),
            ModuleUtilization(bay_name="Bay 2", module_model="LC-12", used_ports=4, total_ports=12),
        ]
        with patch.object(svc, 'get_module_breakdown', return_value=breakdown):
            result = svc.calculate(_make_device())

        assert isinstance(result, PanelUtilization)
        assert result.device_id == 1
        assert result.device_name == "Panel-1"
        assert result.site == "Site A"
        assert result.location == "Room 1"
        assert result.rack == "Rack 1"
        assert result.total_ports == 24
        assert result.used_ports == 10
        assert result.free_ports == 14
        assert result.utilization_percent == 41.7
        assert result.modules == breakdown

    def test_zero_ports_edge_case(self):
        """Zero total ports → 0.0% utilization (Req 3.5)."""
        svc = FiberPanelUtilizationService({})
        with patch.object(svc, 'get_module_breakdown', return_value=[]):
            result = svc.calculate(_make_device())

        assert result.total_ports == 0
        assert result.used_ports == 0
        assert result.free_ports == 0
        assert result.utilization_percent == 0.0

    def test_all_ports_used(self):
        svc = FiberPanelUtilizationService({})
        breakdown = [
            ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=12, total_ports=12),
        ]
        with patch.object(svc, 'get_module_breakdown', return_value=breakdown):
            result = svc.calculate(_make_device())

        assert result.utilization_percent == 100.0
        assert result.free_ports == 0

    def test_no_ports_used(self):
        svc = FiberPanelUtilizationService({})
        breakdown = [
            ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=0, total_ports=12),
        ]
        with patch.object(svc, 'get_module_breakdown', return_value=breakdown):
            result = svc.calculate(_make_device())

        assert result.utilization_percent == 0.0
        assert result.free_ports == 12

    def test_nullable_site_location_rack(self):
        """None values for site/location/rack are handled (Req 5.8)."""
        device = _make_device(site=None, location=None, rack=None)
        svc = FiberPanelUtilizationService({})
        with patch.object(svc, 'get_module_breakdown', return_value=[]):
            result = svc.calculate(device)

        assert result.site is None
        assert result.location is None
        assert result.rack is None

    def test_percent_rounds_to_one_decimal(self):
        """Utilization percent is rounded to 1 decimal (Req 3.4)."""
        svc = FiberPanelUtilizationService({})
        breakdown = [
            ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=1, total_ports=3),
        ]
        with patch.object(svc, 'get_module_breakdown', return_value=breakdown):
            result = svc.calculate(_make_device())

        assert result.utilization_percent == 33.3
