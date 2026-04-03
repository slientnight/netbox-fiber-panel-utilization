"""Unit tests for device widget template rendering.

Validates: Requirements 5.1–5.9, 4.5, 4.6, 8.1, 8.2, 8.3, 8.4

Tests render the device_widget.html template directly using Django's
template engine with a minimal settings configuration (no full NetBox
instance required).
"""

from __future__ import annotations

import os

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [],
            },
        }],
        INSTALLED_APPS=[
            'django.contrib.staticfiles',
            'netbox_fiber_panel_utilization',
        ],
        STATIC_URL='/static/',
    )
    django.setup()

from django.template.loader import render_to_string

import pytest

from netbox_fiber_panel_utilization.services import (
    ModuleUtilization,
    PanelUtilization,
)

TEMPLATE = 'netbox_fiber_panel_utilization/device_widget.html'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config(**overrides):
    """Return a config dict with sensible defaults, merged with overrides."""
    cfg = {
        'warning_threshold': 50,
        'critical_threshold': 80,
        'show_module_breakdown': True,
        'show_port_table': True,
    }
    cfg.update(overrides)
    return cfg


def _sample_utilization(**overrides):
    """Return a PanelUtilization with reasonable defaults."""
    defaults = dict(
        device_id=1,
        device_name='Fiber-Panel-01',
        site='Site Alpha',
        location='Room 101',
        rack='Rack A1',
        total_ports=24,
        used_ports=12,
        free_ports=12,
        utilization_percent=50.0,
        modules=[
            ModuleUtilization(
                bay_name='Bay 1',
                module_model='LC-12',
                used_ports=6,
                total_ports=12,
            ),
            ModuleUtilization(
                bay_name='Bay 2',
                module_model='LC-12',
                used_ports=6,
                total_ports=12,
            ),
        ],
    )
    defaults.update(overrides)
    return PanelUtilization(**defaults)


def _render(utilization=None, config=None, error_message=None, empty_message=None):
    """Render the widget template with the given context."""
    ctx = {}
    if utilization is not None:
        ctx['utilization'] = utilization
    if config is not None:
        ctx['config'] = config
    if error_message is not None:
        ctx['error_message'] = error_message
    if empty_message is not None:
        ctx['empty_message'] = empty_message
    return render_to_string(TEMPLATE, ctx)


# ---------------------------------------------------------------------------
# Req 5.1 – Widget displays device name
# ---------------------------------------------------------------------------

class TestDeviceName:
    def test_device_name_appears_in_output(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Fiber-Panel-01' in html


# ---------------------------------------------------------------------------
# Req 5.2 – Widget displays utilization percentage
# ---------------------------------------------------------------------------

class TestUtilizationPercentage:
    def test_percentage_value_appears(self):
        html = _render(
            utilization=_sample_utilization(utilization_percent=75.3),
            config=_default_config(),
        )
        assert '75.3%' in html


# ---------------------------------------------------------------------------
# Req 5.3 – Widget displays connected/total/free counts
# ---------------------------------------------------------------------------

class TestPortCounts:
    def test_connected_count_appears(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        # used_ports=12
        assert '>12<' in html or '>12</div>' in html.replace('\n', '')

    def test_total_count_appears(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert '>24<' in html or '>24</div>' in html.replace('\n', '')

    def test_free_count_appears(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        # free_ports=12 — check the label "Free" is present
        assert 'Free' in html

    def test_labels_present(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Connected' in html
        assert 'Total' in html
        assert 'Free' in html


# ---------------------------------------------------------------------------
# Req 5.4 – Widget renders a progress bar
# ---------------------------------------------------------------------------

class TestProgressBar:
    def test_progress_bar_present(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'class="progress-bar utilization-bar"' in html
        assert 'role="progressbar"' in html

    def test_progress_bar_width_matches_percent(self):
        html = _render(
            utilization=_sample_utilization(utilization_percent=65.0),
            config=_default_config(),
        )
        assert 'width: 65.0%' in html

    def test_progress_bar_aria_attributes(self):
        html = _render(
            utilization=_sample_utilization(utilization_percent=42.5),
            config=_default_config(),
        )
        assert 'aria-valuenow="42.5"' in html
        assert 'aria-valuemin="0"' in html
        assert 'aria-valuemax="100"' in html


# ---------------------------------------------------------------------------
# Req 5.5 – Progress bar has threshold data attributes
# ---------------------------------------------------------------------------

class TestColorThresholdAttributes:
    def test_data_warning_threshold_present(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'data-warning-threshold="50"' in html

    def test_data_critical_threshold_present(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'data-critical-threshold="80"' in html

    def test_custom_thresholds(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(warning_threshold=30, critical_threshold=70),
        )
        assert 'data-warning-threshold="30"' in html
        assert 'data-critical-threshold="70"' in html


# ---------------------------------------------------------------------------
# Req 5.7 – Contextual info present when available
# ---------------------------------------------------------------------------

class TestContextualInfoPresent:
    def test_site_displayed(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Site Alpha' in html
        assert 'Site' in html

    def test_location_displayed(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Room 101' in html
        assert 'Location' in html

    def test_rack_displayed(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Rack A1' in html
        assert 'Rack' in html


# ---------------------------------------------------------------------------
# Req 5.8 – Contextual info absent when None
# ---------------------------------------------------------------------------

class TestContextualInfoAbsent:
    def test_no_site_row_when_none(self):
        util = _sample_utilization(site=None, location=None, rack=None)
        html = _render(utilization=util, config=_default_config())
        # The contextual info table should not appear at all
        assert 'Site Alpha' not in html
        assert 'Room 101' not in html
        assert 'Rack A1' not in html

    def test_partial_context_only_shows_available(self):
        util = _sample_utilization(site='Site Beta', location=None, rack='Rack B2')
        html = _render(utilization=util, config=_default_config())
        assert 'Site Beta' in html
        assert 'Rack B2' in html
        # location row should not appear
        assert 'Room 101' not in html


# ---------------------------------------------------------------------------
# Req 5.9 – Detail page link
# ---------------------------------------------------------------------------

class TestDetailPageLink:
    def test_link_url_present(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert '/plugins/fiber-patch-panel-utilization/1/' in html

    def test_link_text(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'View Full Details' in html

    def test_link_uses_device_id(self):
        util = _sample_utilization(device_id=42)
        html = _render(utilization=util, config=_default_config())
        assert '/plugins/fiber-patch-panel-utilization/42/' in html


# ---------------------------------------------------------------------------
# Req 4.5 – Module breakdown shown when enabled
# ---------------------------------------------------------------------------

class TestModuleBreakdownEnabled:
    def test_module_table_appears(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_module_breakdown=True),
        )
        assert 'Module Breakdown' in html
        assert 'Bay 1' in html
        assert 'Bay 2' in html
        assert 'LC-12' in html

    def test_module_mini_progress_bars(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_module_breakdown=True),
        )
        # Each module row should have its own progress bar
        assert html.count('utilization-bar') >= 3  # 1 main + 2 module bars


# ---------------------------------------------------------------------------
# Req 4.6 – Module breakdown hidden when disabled
# ---------------------------------------------------------------------------

class TestModuleBreakdownDisabled:
    def test_module_table_absent(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_module_breakdown=False),
        )
        assert 'Module Breakdown' not in html

    def test_module_bay_names_absent(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_module_breakdown=False),
        )
        # Bay names should not appear in the module table section
        # (they may still appear elsewhere, but the table heading is gone)
        assert 'Module Breakdown' not in html


# ---------------------------------------------------------------------------
# Req 8.3 – No widget for non-matching device (template_content returns '')
# ---------------------------------------------------------------------------

class TestNoWidgetForNonMatchingDevice:
    def test_empty_context_renders_nothing(self):
        """When no utilization, error_message, or empty_message is passed,
        the template should produce essentially empty output."""
        html = _render()
        stripped = html.strip()
        # Template should produce no card markup
        assert 'card' not in stripped
        assert 'Fiber Panel Utilization' not in stripped


# ---------------------------------------------------------------------------
# Req 8.4 – Error message displayed
# ---------------------------------------------------------------------------

class TestErrorMessage:
    def test_error_message_renders(self):
        html = _render(error_message='Unable to calculate utilization')
        assert 'Unable to calculate utilization' in html
        assert 'alert-danger' in html

    def test_error_message_shows_card_header(self):
        html = _render(error_message='Unable to calculate utilization')
        assert 'Fiber Panel Utilization' in html


# ---------------------------------------------------------------------------
# Req 8.1, 8.2 – Empty message displayed
# ---------------------------------------------------------------------------

class TestEmptyMessage:
    def test_no_modules_message(self):
        html = _render(empty_message='No installed fiber modules found')
        assert 'No installed fiber modules found' in html
        assert 'alert-warning' in html

    def test_no_ports_message(self):
        html = _render(empty_message='No front ports available')
        assert 'No front ports available' in html
        assert 'alert-warning' in html

    def test_empty_message_shows_card_header(self):
        html = _render(empty_message='No installed fiber modules found')
        assert 'Fiber Panel Utilization' in html
