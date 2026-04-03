"""Property-based tests for structural qualification completeness.

# Feature: fiber-patch-panel-utilization, Property 3: Structural qualification completeness

**Validates: Requirements 2.2, 2.4, 2.5**

Property 3: For any device that passes all configured filters,
``is_supported_device`` returns True if and only if the device has at least one
ModuleBay with an installed Module that has at least one FrontPort.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def module_bay_strategy(draw):
    """Generate a single module bay with optional installed module and ports.

    Each bay is a dict describing:
    - has_module: whether a module is installed
    - has_frontports: whether the installed module has ≥1 front port
    """
    has_module = draw(st.booleans())
    has_frontports = draw(st.booleans()) if has_module else False
    return {"has_module": has_module, "has_frontports": has_frontports}


device_structure_st = st.lists(module_bay_strategy(), min_size=0, max_size=8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_device():
    """Return a minimal fake device that passes all config filters."""
    return SimpleNamespace(
        device_type=SimpleNamespace(slug="panel", model=""),
        device_role=SimpleNamespace(slug="patch"),
        pk=1,
    )


def _build_mock_bays(structure: list[dict]) -> list[MagicMock]:
    """Turn a list of bay descriptors into mock ModuleBay objects."""
    bays = []
    for desc in structure:
        bay = MagicMock()
        if desc["has_module"]:
            module = MagicMock()
            module.frontports.exists.return_value = desc["has_frontports"]
            bay.installed_module = module
        else:
            bay.installed_module = None
        bays.append(bay)
    return bays


def _expected_result(structure: list[dict]) -> bool:
    """Compute the expected is_supported_device result from the structure."""
    return any(
        bay["has_module"] and bay["has_frontports"] for bay in structure
    )


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------


class TestStructuralQualificationCompleteness:
    """Property 3: Structural qualification completeness."""

    @given(structure=device_structure_st)
    @settings(max_examples=100)
    def test_structural_check_matches_specification(self, structure):
        """is_supported_device returns True iff ≥1 bay has installed module with ≥1 front port."""
        device = _make_device()
        mock_bays = _build_mock_bays(structure)

        # Mock dcim.models.ModuleBay for the local import inside _has_fiber_structure
        mock_module_bay_cls = MagicMock()
        mock_module_bay_cls.objects.filter.return_value.select_related.return_value = mock_bays

        mock_dcim_models = MagicMock()
        mock_dcim_models.ModuleBay = mock_module_bay_cls

        saved = {
            "dcim": sys.modules.get("dcim"),
            "dcim.models": sys.modules.get("dcim.models"),
        }
        sys.modules["dcim"] = MagicMock(models=mock_dcim_models)
        sys.modules["dcim.models"] = mock_dcim_models

        try:
            # Empty config → all filters skipped, only structural check matters
            svc = FiberPanelUtilizationService({})
            result = svc.is_supported_device(device)
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

        expected = _expected_result(structure)
        assert result is expected, (
            f"structure={structure!r}, expected={expected}, got={result}"
        )
