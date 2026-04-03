"""Unit tests for default plugin configuration loading and URL wiring.

Validates: Requirements 1.1, 9.3, 9.4
"""
import pytest
from netbox_fiber_panel_utilization import FiberPanelUtilizationConfig


class TestDefaultConfig:
    """Verify all 7 default config keys and values load correctly."""

    def test_default_config_has_all_keys(self):
        expected_keys = {
            'device_type_slugs',
            'device_role_slugs',
            'model_regex',
            'warning_threshold',
            'critical_threshold',
            'show_module_breakdown',
            'show_port_table',
        }
        assert set(FiberPanelUtilizationConfig.default_config.keys()) == expected_keys

    def test_device_type_slugs_default(self):
        assert FiberPanelUtilizationConfig.default_config['device_type_slugs'] == []

    def test_device_role_slugs_default(self):
        assert FiberPanelUtilizationConfig.default_config['device_role_slugs'] == []

    def test_model_regex_default(self):
        assert FiberPanelUtilizationConfig.default_config['model_regex'] == ''

    def test_warning_threshold_default(self):
        assert FiberPanelUtilizationConfig.default_config['warning_threshold'] == 50

    def test_critical_threshold_default(self):
        assert FiberPanelUtilizationConfig.default_config['critical_threshold'] == 80

    def test_show_module_breakdown_default(self):
        assert FiberPanelUtilizationConfig.default_config['show_module_breakdown'] is True

    def test_show_port_table_default(self):
        assert FiberPanelUtilizationConfig.default_config['show_port_table'] is True

    def test_default_config_count(self):
        assert len(FiberPanelUtilizationConfig.default_config) == 7


class TestURLWiring:
    """Verify plugin URL modules are discoverable by NetBox's plugin framework.

    NetBox discovers plugin URLs by convention: it imports ``urlpatterns``
    from ``<plugin>.urls`` (mounted at ``/plugins/<base_url>/``) and
    ``<plugin>.api.urls`` (mounted at ``/api/plugins/<base_url>/``).

    Validates: Requirements 9.3, 9.4
    """

    def test_base_url_is_set(self):
        assert FiberPanelUtilizationConfig.base_url == 'fiber-patch-panel-utilization'

    def test_plugin_urls_module_has_urlpatterns(self):
        from netbox_fiber_panel_utilization import urls
        assert hasattr(urls, 'urlpatterns'), (
            "urls.py must define 'urlpatterns' for NetBox to discover plugin views"
        )
        assert isinstance(urls.urlpatterns, list)
        assert len(urls.urlpatterns) > 0

    def test_api_urls_module_has_urlpatterns(self):
        import importlib
        import os
        # Ensure minimal Django settings so DRF can be imported
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            import django.conf
            if not django.conf.settings.configured:
                django.conf.settings.configure(
                    INSTALLED_APPS=['django.contrib.contenttypes', 'rest_framework'],
                    REST_FRAMEWORK={},
                )
        from netbox_fiber_panel_utilization.api import urls as api_urls
        assert hasattr(api_urls, 'urlpatterns'), (
            "api/urls.py must define 'urlpatterns' for NetBox to discover API endpoints"
        )
        assert isinstance(api_urls.urlpatterns, list)
        assert len(api_urls.urlpatterns) > 0

    def test_plugin_url_includes_detail_view(self):
        from netbox_fiber_panel_utilization import urls
        route_names = [p.name for p in urls.urlpatterns if hasattr(p, 'name')]
        assert 'panel_detail' in route_names

    def test_api_url_includes_utilization_endpoint(self):
        import os
        if not os.environ.get('DJANGO_SETTINGS_MODULE'):
            import django.conf
            if not django.conf.settings.configured:
                django.conf.settings.configure(
                    INSTALLED_APPS=['django.contrib.contenttypes', 'rest_framework'],
                    REST_FRAMEWORK={},
                )
        from netbox_fiber_panel_utilization.api import urls as api_urls
        route_names = [p.name for p in api_urls.urlpatterns if hasattr(p, 'name')]
        assert 'panel_utilization' in route_names

    def test_template_extensions_discoverable(self):
        from netbox_fiber_panel_utilization import template_content
        assert hasattr(template_content, 'template_extensions'), (
            "template_content.py must define 'template_extensions' for NetBox discovery"
        )
        assert isinstance(template_content.template_extensions, list)
        assert len(template_content.template_extensions) > 0
