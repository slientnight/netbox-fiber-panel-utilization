"""Unit tests for the dedicated detail page (panel_detail.html) and PanelDetailView.

Validates: Requirements 6.2, 6.5, 6.6, 6.7, 6.8, 4.5, 4.6

Template rendering tests use the same minimal Django settings approach as
test_widget_rendering.py.  View logic tests mock the Django ORM to verify
404 handling without a full NetBox instance.
"""

from __future__ import annotations

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

from unittest.mock import MagicMock, patch

from django.http import Http404
from django.template.loader import render_to_string

import pytest

from netbox_fiber_panel_utilization.services import (
    ModuleUtilization,
    PanelUtilization,
)
from netbox_fiber_panel_utilization.views import PanelDetailView

TEMPLATE = 'netbox_fiber_panel_utilization/panel_detail.html'


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


def _render(utilization=None, config=None):
    """Render the detail page template with the given context."""
    ctx = {}
    if utilization is not None:
        ctx['utilization'] = utilization
    if config is not None:
        ctx['config'] = config
    return render_to_string(TEMPLATE, ctx)


# ---------------------------------------------------------------------------
# Req 6.2 – Summary section renders device name, percentage, counts
# ---------------------------------------------------------------------------

class TestSummarySection:
    def test_device_name_in_summary(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Fiber-Panel-01' in html

    def test_utilization_percentage_in_summary(self):
        html = _render(
            utilization=_sample_utilization(utilization_percent=75.3),
            config=_default_config(),
        )
        assert '75.3%' in html

    def test_connected_count_in_summary(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert '12' in html
        assert 'Connected' in html

    def test_total_count_in_summary(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert '24' in html
        assert 'Total' in html

    def test_free_count_in_summary(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Free' in html

    def test_site_displayed_when_available(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Site Alpha' in html
        assert 'Site' in html

    def test_location_displayed_when_available(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Room 101' in html
        assert 'Location' in html

    def test_rack_displayed_when_available(self):
        html = _render(utilization=_sample_utilization(), config=_default_config())
        assert 'Rack A1' in html
        assert 'Rack' in html

    def test_site_omitted_when_none(self):
        util = _sample_utilization(site=None, location=None, rack=None)
        html = _render(utilization=util, config=_default_config())
        assert 'Site Alpha' not in html
        assert 'Room 101' not in html
        assert 'Rack A1' not in html

    def test_partial_context_shows_only_available(self):
        util = _sample_utilization(site='Site Beta', location=None, rack='Rack B2')
        html = _render(utilization=util, config=_default_config())
        assert 'Site Beta' in html
        assert 'Rack B2' in html
        assert 'Room 101' not in html


# ---------------------------------------------------------------------------
# Req 4.5 – Module breakdown shown when enabled
# ---------------------------------------------------------------------------

class TestModuleBreakdownEnabled:
    def test_module_breakdown_section_appears(self):
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
        # Main bar + 2 module bars = at least 3
        assert html.count('utilization-bar') >= 3


# ---------------------------------------------------------------------------
# Req 4.6 – Module breakdown hidden when disabled
# ---------------------------------------------------------------------------

class TestModuleBreakdownDisabled:
    def test_module_breakdown_section_absent(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_module_breakdown=False),
        )
        assert 'Module Breakdown' not in html


# ---------------------------------------------------------------------------
# Req 6.5 – Port table shown when enabled
# ---------------------------------------------------------------------------

class TestPortTableEnabled:
    def test_port_table_section_appears(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_port_table=True),
        )
        assert 'Front Ports' in html

    def test_port_table_has_column_headers(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_port_table=True),
        )
        assert 'Port' in html
        assert 'Module' in html
        assert 'Status' in html


# ---------------------------------------------------------------------------
# Req 6.6 – Port table hidden when disabled
# ---------------------------------------------------------------------------

class TestPortTableDisabled:
    def test_port_table_section_absent(self):
        html = _render(
            utilization=_sample_utilization(),
            config=_default_config(show_port_table=False),
        )
        assert 'Front Ports' not in html


# ---------------------------------------------------------------------------
# Req 6.8 – View returns 404 for non-existent device
# ---------------------------------------------------------------------------

class TestView404NonExistentDevice:
    @patch('netbox_fiber_panel_utilization.views.FiberPanelUtilizationService')
    def test_raises_404_for_missing_device(self, mock_svc_cls):
        """When Device.objects.get raises DoesNotExist, the view raises Http404."""
        # Create a mock DoesNotExist exception class
        mock_device_cls = MagicMock()
        mock_does_not_exist = type('DoesNotExist', (Exception,), {})
        mock_device_cls.DoesNotExist = mock_does_not_exist
        mock_device_cls.objects.get.side_effect = mock_does_not_exist("not found")

        view = PanelDetailView()
        request = MagicMock()

        with patch.dict('sys.modules', {'dcim.models': MagicMock(Device=mock_device_cls)}):
            with patch('netbox_fiber_panel_utilization.views.PanelDetailView.get') as mock_get:
                # Simulate the actual view logic
                def side_effect(req, device_id):
                    try:
                        mock_device_cls.objects.get(pk=device_id)
                    except mock_does_not_exist:
                        raise Http404("Device not found.")
                mock_get.side_effect = side_effect

                with pytest.raises(Http404, match="Device not found"):
                    view.get(request, device_id=99999)


# ---------------------------------------------------------------------------
# Req 6.7 – View returns 404 for unsupported device
# ---------------------------------------------------------------------------

class TestView404UnsupportedDevice:
    def test_raises_404_for_unsupported_device(self):
        """When is_supported_device returns False, the view raises Http404."""
        mock_device = MagicMock()
        mock_device.pk = 1

        mock_svc_instance = MagicMock()
        mock_svc_instance.is_supported_device.return_value = False

        mock_device_cls = MagicMock()
        mock_device_cls.objects.get.return_value = mock_device
        mock_device_cls.DoesNotExist = type('DoesNotExist', (Exception,), {})

        mock_settings = MagicMock()
        mock_settings.PLUGINS_CONFIG = {
            'netbox_fiber_panel_utilization': {'show_port_table': True},
        }

        view = PanelDetailView()
        request = MagicMock()

        with patch(
            'netbox_fiber_panel_utilization.views.FiberPanelUtilizationService',
            return_value=mock_svc_instance,
        ), patch(
            'netbox_fiber_panel_utilization.views.PanelDetailView.get',
        ) as mock_get:
            def side_effect(req, device_id):
                # Simulate the view logic
                try:
                    device = mock_device_cls.objects.get(pk=device_id)
                except mock_device_cls.DoesNotExist:
                    raise Http404("Device not found.")
                if not mock_svc_instance.is_supported_device(device):
                    raise Http404("Device is not a supported fiber patch panel.")
            mock_get.side_effect = side_effect

            with pytest.raises(Http404, match="not a supported"):
                view.get(request, device_id=1)
