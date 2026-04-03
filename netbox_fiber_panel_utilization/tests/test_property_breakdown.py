"""Property-based tests for module breakdown correctness.

# Feature: fiber-patch-panel-utilization, Property 5: Module breakdown correctness

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

Property 5: For any supported device, the module breakdown list SHALL:
1. Contain one entry per installed module (modules in bays with no installed module are excluded)
2. Each entry contains the bay name, module type model, per-module used count, and per-module total count
3. The sum of per-module used_ports equals the device-level used_ports
4. The sum of per-module total_ports equals the device-level total_ports
5. The list is ordered by module bay position
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

@st.composite
def module_strategy(draw):
    """Generate a single module with random front ports, bay name, model, and position."""
    num_ports = draw(st.integers(min_value=0, max_value=24))
    connected = draw(st.lists(st.booleans(), min_size=num_ports, max_size=num_ports))
    bay_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=10,
    ))
    module_model = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
        min_size=1,
        max_size=10,
    ))
    position = draw(st.integers(min_value=0, max_value=1000))
    return {
        "bay_name": bay_name,
        "module_model": module_model,
        "ports": connected,
        "position": position,
    }


multi_module_strategy = st.lists(module_strategy(), min_size=1, max_size=8)


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
    )


def _build_fake_modules(module_descs: list[dict]) -> list[MagicMock]:
    """Build fake Module objects from strategy-generated descriptors, sorted by position."""
    # Sort by position to simulate the ORM order_by('module_bay__position')
    sorted_descs = sorted(module_descs, key=lambda d: d["position"])
    modules = []
    for desc in sorted_descs:
        module = MagicMock()
        module.module_bay = SimpleNamespace(name=desc["bay_name"], position=desc["position"])
        module.module_type = SimpleNamespace(model=desc["module_model"])

        front_ports = []
        for is_connected in desc["ports"]:
            port = SimpleNamespace(cable="some-cable" if is_connected else None)
            front_ports.append(port)

        module.frontports.all.return_value = front_ports
        modules.append(module)
    return modules


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestModuleBreakdownCorrectness:
    """Property 5: Module breakdown correctness."""

    @given(module_descs=multi_module_strategy)
    @settings(max_examples=100)
    def test_one_entry_per_installed_module(self, module_descs):
        """Breakdown contains exactly one entry per installed module."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        assert len(result.modules) == len(module_descs)

    @given(module_descs=multi_module_strategy)
    @settings(max_examples=100)
    def test_each_entry_contains_required_fields(self, module_descs):
        """Each breakdown entry has bay_name, module_model, used_ports, total_ports."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        for entry in result.modules:
            assert isinstance(entry.bay_name, str) and len(entry.bay_name) > 0
            assert isinstance(entry.module_model, str) and len(entry.module_model) > 0
            assert isinstance(entry.used_ports, int) and entry.used_ports >= 0
            assert isinstance(entry.total_ports, int) and entry.total_ports >= 0

    @given(module_descs=multi_module_strategy)
    @settings(max_examples=100)
    def test_sum_used_ports_matches_device_level(self, module_descs):
        """Sum of per-module used_ports equals device-level used_ports."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        module_used_sum = sum(m.used_ports for m in result.modules)
        assert module_used_sum == result.used_ports

    @given(module_descs=multi_module_strategy)
    @settings(max_examples=100)
    def test_sum_total_ports_matches_device_level(self, module_descs):
        """Sum of per-module total_ports equals device-level total_ports."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        module_total_sum = sum(m.total_ports for m in result.modules)
        assert module_total_sum == result.total_ports

    @given(module_descs=st.lists(module_strategy(), min_size=2, max_size=8))
    @settings(max_examples=100)
    def test_breakdown_ordered_by_bay_position(self, module_descs):
        """Breakdown list is ordered by module bay position."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        # The fake modules were sorted by position in _build_fake_modules,
        # so the bay_names in the result should match the sorted order.
        sorted_descs = sorted(module_descs, key=lambda d: d["position"])
        expected_bay_names = [d["bay_name"] for d in sorted_descs]
        actual_bay_names = [m.bay_name for m in result.modules]
        assert actual_bay_names == expected_bay_names
