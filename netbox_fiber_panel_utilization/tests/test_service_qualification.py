"""Unit tests for FiberPanelUtilizationService.__init__ and is_supported_device.

Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.7, 2.1, 2.2, 2.3, 2.4, 2.5
"""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService


# ---------------------------------------------------------------------------
# Helpers – lightweight fakes for NetBox ORM objects
# ---------------------------------------------------------------------------

def _make_device(type_slug="fiber-panel", role_slug="patch-panel", model="FP-4U"):
    """Return a minimal fake device with device_type and device_role."""
    device_type = SimpleNamespace(slug=type_slug, model=model)
    device_role = SimpleNamespace(slug=role_slug)
    return SimpleNamespace(device_type=device_type, device_role=device_role, pk=1)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_stores_config(self):
        cfg = {"device_type_slugs": ["a"], "warning_threshold": 60}
        svc = FiberPanelUtilizationService(cfg)
        assert svc.config is cfg

    def test_empty_config(self):
        svc = FiberPanelUtilizationService({})
        assert svc.config == {}


# ---------------------------------------------------------------------------
# Qualification chain – device_type_slugs filter (Req 1.2)
# ---------------------------------------------------------------------------

class TestDeviceTypeSlugsFilter:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_passes_when_slug_in_list(self, _mock):
        svc = FiberPanelUtilizationService({"device_type_slugs": ["fiber-panel"]})
        device = _make_device(type_slug="fiber-panel")
        assert svc.is_supported_device(device) is True

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_rejects_when_slug_not_in_list(self, _mock):
        svc = FiberPanelUtilizationService({"device_type_slugs": ["other-type"]})
        device = _make_device(type_slug="fiber-panel")
        assert svc.is_supported_device(device) is False

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_skipped_when_list_empty(self, _mock):
        svc = FiberPanelUtilizationService({"device_type_slugs": []})
        device = _make_device(type_slug="anything")
        assert svc.is_supported_device(device) is True


# ---------------------------------------------------------------------------
# Qualification chain – device_role_slugs filter (Req 1.3)
# ---------------------------------------------------------------------------

class TestDeviceRoleSlugsFilter:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_passes_when_role_in_list(self, _mock):
        svc = FiberPanelUtilizationService({"device_role_slugs": ["patch-panel"]})
        device = _make_device(role_slug="patch-panel")
        assert svc.is_supported_device(device) is True

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_rejects_when_role_not_in_list(self, _mock):
        svc = FiberPanelUtilizationService({"device_role_slugs": ["router"]})
        device = _make_device(role_slug="patch-panel")
        assert svc.is_supported_device(device) is False

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_skipped_when_list_empty(self, _mock):
        svc = FiberPanelUtilizationService({"device_role_slugs": []})
        device = _make_device(role_slug="anything")
        assert svc.is_supported_device(device) is True


# ---------------------------------------------------------------------------
# Qualification chain – model_regex filter (Req 1.4)
# ---------------------------------------------------------------------------

class TestModelRegexFilter:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_passes_when_model_matches(self, _mock):
        svc = FiberPanelUtilizationService({"model_regex": r"FP-\d+"})
        device = _make_device(model="FP-4U")
        assert svc.is_supported_device(device) is True

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_passes_when_slug_matches(self, _mock):
        svc = FiberPanelUtilizationService({"model_regex": r"fiber"})
        device = _make_device(type_slug="fiber-panel", model="SomeOtherModel")
        assert svc.is_supported_device(device) is True

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_rejects_when_no_match(self, _mock):
        svc = FiberPanelUtilizationService({"model_regex": r"^SWITCH"})
        device = _make_device(type_slug="fiber-panel", model="FP-4U")
        assert svc.is_supported_device(device) is False

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_skipped_when_empty(self, _mock):
        svc = FiberPanelUtilizationService({"model_regex": ""})
        device = _make_device()
        assert svc.is_supported_device(device) is True


# ---------------------------------------------------------------------------
# Invalid regex fallback (Req 1.7)
# ---------------------------------------------------------------------------

class TestInvalidRegexFallback:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_invalid_regex_logs_warning_and_falls_through(self, _mock, caplog):
        svc = FiberPanelUtilizationService({"model_regex": r"[invalid"})
        device = _make_device()
        with caplog.at_level(logging.WARNING):
            result = svc.is_supported_device(device)
        assert result is True
        assert "Invalid model_regex pattern" in caplog.text

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=False)
    def test_invalid_regex_still_requires_structural_check(self, _mock, caplog):
        svc = FiberPanelUtilizationService({"model_regex": r"[invalid"})
        device = _make_device()
        with caplog.at_level(logging.WARNING):
            result = svc.is_supported_device(device)
        assert result is False


# ---------------------------------------------------------------------------
# Empty config → structural fallback only (Req 1.5)
# ---------------------------------------------------------------------------

class TestEmptyConfigFallback:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_all_empty_falls_to_structural(self, _mock):
        svc = FiberPanelUtilizationService({
            "device_type_slugs": [],
            "device_role_slugs": [],
            "model_regex": "",
        })
        device = _make_device()
        assert svc.is_supported_device(device) is True

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=False)
    def test_all_empty_structural_fails(self, _mock):
        svc = FiberPanelUtilizationService({
            "device_type_slugs": [],
            "device_role_slugs": [],
            "model_regex": "",
        })
        device = _make_device()
        assert svc.is_supported_device(device) is False


# ---------------------------------------------------------------------------
# Filter ordering (Req 2.1) – type checked before role before regex
# ---------------------------------------------------------------------------

class TestFilterOrdering:
    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_type_rejects_before_role_checked(self, _mock):
        """If type filter rejects, role filter should never matter."""
        svc = FiberPanelUtilizationService({
            "device_type_slugs": ["wrong-type"],
            "device_role_slugs": ["patch-panel"],
        })
        device = _make_device(type_slug="fiber-panel", role_slug="patch-panel")
        assert svc.is_supported_device(device) is False

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_role_rejects_before_regex_checked(self, _mock):
        """If role filter rejects, regex should never matter."""
        svc = FiberPanelUtilizationService({
            "device_type_slugs": ["fiber-panel"],
            "device_role_slugs": ["wrong-role"],
            "model_regex": r"FP",
        })
        device = _make_device(type_slug="fiber-panel", role_slug="patch-panel", model="FP-4U")
        assert svc.is_supported_device(device) is False

    @patch.object(FiberPanelUtilizationService, '_has_fiber_structure', return_value=True)
    def test_all_filters_pass(self, _mock):
        svc = FiberPanelUtilizationService({
            "device_type_slugs": ["fiber-panel"],
            "device_role_slugs": ["patch-panel"],
            "model_regex": r"FP",
        })
        device = _make_device(type_slug="fiber-panel", role_slug="patch-panel", model="FP-4U")
        assert svc.is_supported_device(device) is True


# ---------------------------------------------------------------------------
# Structural check via _has_fiber_structure (Req 2.2, 2.4, 2.5)
# ---------------------------------------------------------------------------

def _patch_dcim_modulebay():
    """Context manager that injects a mock dcim.models.ModuleBay for the local import."""
    import sys
    mock_module_bay = MagicMock()
    mock_dcim_models = MagicMock()
    mock_dcim_models.ModuleBay = mock_module_bay
    mock_dcim = MagicMock()
    mock_dcim.models = mock_dcim_models

    saved = {}
    for key in ('dcim', 'dcim.models'):
        saved[key] = sys.modules.get(key)

    sys.modules['dcim'] = mock_dcim
    sys.modules['dcim.models'] = mock_dcim_models

    class _Ctx:
        def __enter__(self_ctx):
            return mock_module_bay
        def __exit__(self_ctx, *args):
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

    return _Ctx()


class TestStructuralCheck:
    def test_has_fiber_structure_with_module_and_frontports(self):
        """Device with ModuleBay → installed Module → FrontPort → True."""
        mock_frontports = MagicMock()
        mock_frontports.exists.return_value = True
        mock_module = MagicMock()
        mock_module.frontports = mock_frontports

        mock_bay = MagicMock()
        mock_bay.installed_module = mock_module

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_bay]))

        device = _make_device()
        with _patch_dcim_modulebay() as MockModuleBay:
            MockModuleBay.objects.filter.return_value.select_related.return_value = mock_qs
            result = FiberPanelUtilizationService._has_fiber_structure(device)
        assert result is True

    def test_has_fiber_structure_no_module_bays(self):
        """Device with no ModuleBays → False."""
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))

        device = _make_device()
        with _patch_dcim_modulebay() as MockModuleBay:
            MockModuleBay.objects.filter.return_value.select_related.return_value = mock_qs
            result = FiberPanelUtilizationService._has_fiber_structure(device)
        assert result is False

    def test_has_fiber_structure_bay_without_module(self):
        """ModuleBay exists but no installed module → False (Req 2.4)."""
        mock_bay = MagicMock()
        mock_bay.installed_module = None

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_bay]))

        device = _make_device()
        with _patch_dcim_modulebay() as MockModuleBay:
            MockModuleBay.objects.filter.return_value.select_related.return_value = mock_qs
            result = FiberPanelUtilizationService._has_fiber_structure(device)
        assert result is False

    def test_has_fiber_structure_module_with_no_frontports(self):
        """Module installed but zero FrontPorts → False (Req 2.5)."""
        mock_frontports = MagicMock()
        mock_frontports.exists.return_value = False
        mock_module = MagicMock()
        mock_module.frontports = mock_frontports

        mock_bay = MagicMock()
        mock_bay.installed_module = mock_module

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([mock_bay]))

        device = _make_device()
        with _patch_dcim_modulebay() as MockModuleBay:
            MockModuleBay.objects.filter.return_value.select_related.return_value = mock_qs
            result = FiberPanelUtilizationService._has_fiber_structure(device)
        assert result is False
