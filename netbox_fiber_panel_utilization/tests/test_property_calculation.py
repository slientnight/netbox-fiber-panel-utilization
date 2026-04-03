"""Property-based tests for utilization calculation invariants.

# Feature: fiber-patch-panel-utilization, Property 4: Utilization calculation invariants

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

Property 4: For any supported device with modules and front ports:
1. total_ports = sum of all FrontPort objects across all installed modules
2. used_ports = count of FrontPort objects with non-null cable
3. free_ports = total_ports - used_ports
4. utilization_percent = round((used/total)*100, 1) when total > 0, else 0.0
5. Rear port cable status does not affect any of the above values
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
    """Generate a single module with random front ports (0-24), each randomly connected."""
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
    return {
        "bay_name": bay_name,
        "module_model": module_model,
        "ports": connected,  # list of bools: True = cable attached
    }


modules_strategy = st.lists(module_strategy(), min_size=0, max_size=6)


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
    """Build fake Module objects from strategy-generated descriptors."""
    modules = []
    for desc in module_descs:
        module = MagicMock()
        module.module_bay = SimpleNamespace(name=desc["bay_name"])
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


class TestUtilizationCalculationInvariants:
    """Property 4: Utilization calculation invariants."""

    @given(module_descs=modules_strategy)
    @settings(max_examples=100)
    def test_total_ports_equals_sum_of_front_ports(self, module_descs):
        """total_ports == sum of FrontPorts across all installed modules."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        expected_total = sum(len(desc["ports"]) for desc in module_descs)
        assert result.total_ports == expected_total

    @given(module_descs=modules_strategy)
    @settings(max_examples=100)
    def test_used_ports_equals_count_with_cable(self, module_descs):
        """used_ports == count of ports where cable is not None."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        expected_used = sum(
            sum(1 for c in desc["ports"] if c) for desc in module_descs
        )
        assert result.used_ports == expected_used

    @given(module_descs=modules_strategy)
    @settings(max_examples=100)
    def test_free_ports_equals_total_minus_used(self, module_descs):
        """free_ports == total_ports - used_ports."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        assert result.free_ports == result.total_ports - result.used_ports

    @given(module_descs=modules_strategy)
    @settings(max_examples=100)
    def test_utilization_percent_formula(self, module_descs):
        """utilization_percent == round((used/total)*100, 1) or 0.0 when total=0."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        if result.total_ports > 0:
            expected_pct = round((result.used_ports / result.total_ports) * 100, 1)
        else:
            expected_pct = 0.0
        assert result.utilization_percent == expected_pct

    @given(module_descs=modules_strategy)
    @settings(max_examples=100)
    def test_modules_count_matches_input(self, module_descs):
        """Modules list length matches input modules count."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        assert len(result.modules) == len(module_descs)

    @given(module_descs=st.lists(module_strategy(), min_size=1, max_size=6))
    @settings(max_examples=100)
    def test_rear_ports_ignored(self, module_descs):
        """Rear port cable status does not affect utilization values."""
        device = _make_device()
        fake_modules = _build_fake_modules(module_descs)

        # Add rear ports with cables to each module — should be ignored
        for module in fake_modules:
            rear_ports = [
                SimpleNamespace(cable="rear-cable-1"),
                SimpleNamespace(cable="rear-cable-2"),
            ]
            module.rearports = MagicMock()
            module.rearports.all.return_value = rear_ports

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, "get_installed_modules", return_value=fake_modules):
            result = svc.calculate(device)

        # Totals should only reflect front ports, not rear ports
        expected_total = sum(len(desc["ports"]) for desc in module_descs)
        expected_used = sum(
            sum(1 for c in desc["ports"] if c) for desc in module_descs
        )
        assert result.total_ports == expected_total
        assert result.used_ports == expected_used
        assert result.free_ports == expected_total - expected_used
