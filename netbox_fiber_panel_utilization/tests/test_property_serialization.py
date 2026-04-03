"""Property-based tests for serialization round-trip.

# Feature: fiber-patch-panel-utilization, Property 6: Serialization round-trip

**Validates: Requirements 14.1, 14.2, 14.3, 7.2, 7.3**

Property 6: For any valid PanelUtilization object, serializing it to JSON
via serialize() and then parsing the JSON back with json.loads() SHALL
produce a dictionary with equivalent values: same device_id, device_name,
site, location, rack, total_ports, used_ports, free_ports,
utilization_percent, and modules list with matching entries.
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from netbox_fiber_panel_utilization.services import (
    FiberPanelUtilizationService,
    ModuleUtilization,
    PanelUtilization,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd", "Zs")),
    min_size=1,
    max_size=20,
)

optional_text = st.none() | safe_text


@st.composite
def module_utilization_strategy(draw):
    """Generate a random ModuleUtilization instance."""
    bay_name = draw(safe_text)
    module_model = draw(safe_text)
    total_ports = draw(st.integers(min_value=0, max_value=96))
    used_ports = draw(st.integers(min_value=0, max_value=total_ports))
    return ModuleUtilization(
        bay_name=bay_name,
        module_model=module_model,
        used_ports=used_ports,
        total_ports=total_ports,
    )


@st.composite
def panel_utilization_strategy(draw):
    """Generate a random PanelUtilization instance with consistent values."""
    device_id = draw(st.integers(min_value=1, max_value=10_000))
    device_name = draw(safe_text)
    site = draw(optional_text)
    location = draw(optional_text)
    rack = draw(optional_text)

    modules = draw(st.lists(module_utilization_strategy(), min_size=0, max_size=8))

    total_ports = sum(m.total_ports for m in modules)
    used_ports = sum(m.used_ports for m in modules)
    free_ports = total_ports - used_ports
    utilization_percent = (
        round((used_ports / total_ports) * 100, 1) if total_ports > 0 else 0.0
    )

    return PanelUtilization(
        device_id=device_id,
        device_name=device_name,
        site=site,
        location=location,
        rack=rack,
        total_ports=total_ports,
        used_ports=used_ports,
        free_ports=free_ports,
        utilization_percent=utilization_percent,
        modules=modules,
    )


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    """Property 6: Serialization round-trip."""

    @given(utilization=panel_utilization_strategy())
    @settings(max_examples=100)
    def test_round_trip_preserves_all_fields(self, utilization):
        """Serializing to JSON and parsing back produces equivalent values."""
        svc = FiberPanelUtilizationService({})

        serialized = svc.serialize(utilization)
        json_str = json.dumps(serialized)
        parsed = json.loads(json_str)

        # Top-level scalar fields
        assert parsed["device_id"] == utilization.device_id
        assert parsed["device_name"] == utilization.device_name
        assert parsed["site"] == utilization.site
        assert parsed["location"] == utilization.location
        assert parsed["rack"] == utilization.rack
        assert parsed["total_ports"] == utilization.total_ports
        assert parsed["used_ports"] == utilization.used_ports
        assert parsed["free_ports"] == utilization.free_ports
        assert parsed["utilization_percent"] == utilization.utilization_percent

        # Modules list
        assert len(parsed["modules"]) == len(utilization.modules)
        for parsed_mod, orig_mod in zip(parsed["modules"], utilization.modules):
            assert parsed_mod["name"] == orig_mod.bay_name
            assert parsed_mod["model"] == orig_mod.module_model
            assert parsed_mod["used"] == orig_mod.used_ports
            assert parsed_mod["total"] == orig_mod.total_ports

    @given(utilization=panel_utilization_strategy())
    @settings(max_examples=100)
    def test_serialized_output_is_valid_json(self, utilization):
        """serialize() output can be encoded as valid JSON (RFC 8259)."""
        svc = FiberPanelUtilizationService({})

        serialized = svc.serialize(utilization)
        json_str = json.dumps(serialized)

        # json.loads will raise ValueError if not valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

    @given(utilization=panel_utilization_strategy())
    @settings(max_examples=100)
    def test_modules_array_structure(self, utilization):
        """Each module in the serialized output has exactly the expected keys."""
        svc = FiberPanelUtilizationService({})

        serialized = svc.serialize(utilization)
        json_str = json.dumps(serialized)
        parsed = json.loads(json_str)

        expected_keys = {"name", "model", "used", "total"}
        for mod in parsed["modules"]:
            assert set(mod.keys()) == expected_keys
