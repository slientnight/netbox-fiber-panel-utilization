"""NetBox plugin for fiber patch panel utilization tracking."""

try:
    from netbox.plugins import PluginConfig
except ImportError:
    # Allow import outside of a NetBox environment (e.g. for testing)
    from types import SimpleNamespace as _NS

    class _PluginConfigMeta(type):
        pass

    class PluginConfig(metaclass=_PluginConfigMeta):
        pass


class FiberPanelUtilizationConfig(PluginConfig):
    """Plugin configuration for netbox_fiber_panel_utilization."""

    name = 'netbox_fiber_panel_utilization'
    verbose_name = 'Fiber Patch Panel Utilization'
    app_label = 'netbox_fiber_panel_utilization'
    description = (
        'A read-only NetBox plugin that calculates and displays '
        'fiber patch panel utilization based on connected front ports.'
    )
    version = '1.0.0'
    author = 'Marshall Hollis'
    author_email = 'hollisma@cec.sc.edu'
    base_url = 'fiber-patch-panel-utilization'
    min_version = '3.5.0'
    max_version = '4.99'

    default_config = {
        'device_type_slugs': [],
        'device_role_slugs': [],
        'model_regex': '',
        'warning_threshold': 50,
        'critical_threshold': 80,
        'show_module_breakdown': True,
        'show_port_table': True,
    }


config = FiberPanelUtilizationConfig
