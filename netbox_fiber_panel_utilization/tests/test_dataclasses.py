"""Tests for ModuleUtilization and PanelUtilization dataclasses."""

from netbox_fiber_panel_utilization.services import ModuleUtilization, PanelUtilization


class TestModuleUtilization:
    """Tests for ModuleUtilization dataclass."""

    def test_utilization_percent_normal(self):
        m = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=6, total_ports=12)
        assert m.utilization_percent == 50.0

    def test_utilization_percent_zero_total(self):
        m = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=0, total_ports=0)
        assert m.utilization_percent == 0.0

    def test_utilization_percent_all_used(self):
        m = ModuleUtilization(bay_name="Bay 1", module_model="LC-24", used_ports=24, total_ports=24)
        assert m.utilization_percent == 100.0

    def test_utilization_percent_none_used(self):
        m = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=0, total_ports=12)
        assert m.utilization_percent == 0.0

    def test_utilization_percent_rounds_to_one_decimal(self):
        m = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=1, total_ports=3)
        assert m.utilization_percent == 33.3


class TestPanelUtilization:
    """Tests for PanelUtilization dataclass."""

    def test_default_modules_empty_list(self):
        p = PanelUtilization(
            device_id=1, device_name="Panel-1", site="Site A",
            location="Room 1", rack="Rack 1",
            total_ports=24, used_ports=12, free_ports=12,
            utilization_percent=50.0,
        )
        assert p.modules == []

    def test_with_modules(self):
        mod = ModuleUtilization(bay_name="Bay 1", module_model="LC-12", used_ports=6, total_ports=12)
        p = PanelUtilization(
            device_id=1, device_name="Panel-1", site=None,
            location=None, rack=None,
            total_ports=12, used_ports=6, free_ports=6,
            utilization_percent=50.0, modules=[mod],
        )
        assert len(p.modules) == 1
        assert p.modules[0].bay_name == "Bay 1"

    def test_nullable_fields(self):
        p = PanelUtilization(
            device_id=1, device_name="Panel-1", site=None,
            location=None, rack=None,
            total_ports=0, used_ports=0, free_ports=0,
            utilization_percent=0.0,
        )
        assert p.site is None
        assert p.location is None
        assert p.rack is None
