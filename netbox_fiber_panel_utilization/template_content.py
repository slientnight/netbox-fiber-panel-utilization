"""Template extension for injecting the fiber panel utilization widget."""

import logging

try:
    from netbox.plugins import PluginTemplateExtension
except ImportError:
    try:
        from extras.plugins import PluginTemplateExtension
    except ImportError:
        # Allow import outside of a NetBox environment (e.g. for testing)
        class PluginTemplateExtension:
            """Stub for environments without NetBox installed."""

            model = None

            def __init__(self, context):
                self.context = context

            def render(self, template_name, extra_context=None):
                return ''

            def right_page(self):
                return ''


from .services import FiberPanelUtilizationService

logger = logging.getLogger(__name__)


class FiberPanelUtilizationExtension(PluginTemplateExtension):
    """Inject utilization widget into the device detail page."""

    model = 'dcim.device'

    def right_page(self):
        """Render widget HTML or empty string if device not supported."""
        device = self.context.get('object')
        if device is None:
            return ''

        # Guard: only proceed for Device instances
        try:
            from dcim.models import Device
            if not isinstance(device, Device):
                return ''
        except ImportError:
            pass

        # Retrieve plugin config from Django settings
        try:
            from django.conf import settings
            config = settings.PLUGINS_CONFIG.get(
                'netbox_fiber_panel_utilization', {}
            )
        except Exception:
            config = {}

        svc = FiberPanelUtilizationService(config)

        # Req 8.3: No widget for non-matching device
        if not svc.is_supported_device(device):
            return ''

        try:
            utilization = svc.calculate(device)
        except Exception:
            # Req 8.4: Log and display friendly error
            logger.exception(
                "Error calculating utilization for device %s", device.pk
            )
            return self.render(
                'netbox_fiber_panel_utilization/device_widget.html',
                extra_context={'error_message': 'Unable to calculate utilization'},
            )

        # Req 8.1: No installed fiber modules
        if not utilization.modules:
            return self.render(
                'netbox_fiber_panel_utilization/device_widget.html',
                extra_context={'empty_message': 'No installed fiber modules found'},
            )

        # Req 8.2: No front ports available
        if utilization.total_ports == 0:
            return self.render(
                'netbox_fiber_panel_utilization/device_widget.html',
                extra_context={'empty_message': 'No front ports available'},
            )

        return self.render(
            'netbox_fiber_panel_utilization/device_widget.html',
            extra_context={
                'utilization': utilization,
                'config': config,
            },
        )


template_extensions = [FiberPanelUtilizationExtension]
