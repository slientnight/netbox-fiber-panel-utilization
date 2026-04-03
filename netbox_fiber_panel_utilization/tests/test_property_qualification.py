"""Property-based tests for qualification filter membership.

# Feature: fiber-patch-panel-utilization, Property 1: Qualification filter membership

**Validates: Requirements 1.2, 1.3, 2.3**

Property 1: For any device and for any non-empty allowlist configuration
(device_type_slugs or device_role_slugs), the device passes that filter stage
if and only if its corresponding slug is a member of the configured allowlist.
"""

from types import SimpleNamespace
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

slug_st = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=1,
    max_size=10,
)

slug_list_st = st.lists(slug_st, min_size=1, max_size=10)


def _make_device(type_slug="panel", role_slug="patch"):
    """Return a minimal fake device with device_type and device_role."""
    return SimpleNamespace(
        device_type=SimpleNamespace(slug=type_slug, model=""),
        device_role=SimpleNamespace(slug=role_slug),
        pk=1,
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestQualificationFilterMembership:
    """Property 1: Qualification filter membership."""

    @given(allowlist=slug_list_st, device_slug=slug_st)
    @settings(max_examples=100)
    @patch.object(
        FiberPanelUtilizationService, "_has_fiber_structure", return_value=True
    )
    def test_device_type_slug_filter_membership(
        self, _mock_struct, allowlist, device_slug
    ):
        """device_type_slugs filter passes iff the device's type slug is in the allowlist."""
        svc = FiberPanelUtilizationService({"device_type_slugs": allowlist})
        device = _make_device(type_slug=device_slug)
        result = svc.is_supported_device(device)
        expected = device_slug in allowlist
        assert result is expected, (
            f"device_type_slugs filter: slug={device_slug!r}, "
            f"allowlist={allowlist!r}, got={result}, expected={expected}"
        )

    @given(allowlist=slug_list_st, device_slug=slug_st)
    @settings(max_examples=100)
    @patch.object(
        FiberPanelUtilizationService, "_has_fiber_structure", return_value=True
    )
    def test_device_role_slug_filter_membership(
        self, _mock_struct, allowlist, device_slug
    ):
        """device_role_slugs filter passes iff the device's role slug is in the allowlist."""
        svc = FiberPanelUtilizationService({"device_role_slugs": allowlist})
        device = _make_device(role_slug=device_slug)
        result = svc.is_supported_device(device)
        expected = device_slug in allowlist
        assert result is expected, (
            f"device_role_slugs filter: slug={device_slug!r}, "
            f"allowlist={allowlist!r}, got={result}, expected={expected}"
        )
