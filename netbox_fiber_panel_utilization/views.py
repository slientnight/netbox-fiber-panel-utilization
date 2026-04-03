"""Views for the fiber patch panel utilization plugin."""

import logging

from django.http import Http404
from django.shortcuts import render
from django.views import View

from .services import FiberPanelUtilizationService

logger = logging.getLogger(__name__)


class PanelDetailView(View):
    """Dedicated detail page for fiber panel utilization."""

    def get(self, request, device_id):
        from dcim.models import Device
        from django.conf import settings

        config = settings.PLUGINS_CONFIG.get('netbox_fiber_panel_utilization', {})

        # Req 6.8: 404 for non-existent device
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            raise Http404("Device not found.")

        svc = FiberPanelUtilizationService(config)

        # Req 6.7: 404 for unsupported device
        if not svc.is_supported_device(device):
            raise Http404("Device is not a supported fiber patch panel.")

        utilization = svc.calculate(device)

        return render(request, 'netbox_fiber_panel_utilization/panel_detail.html', {
            'utilization': utilization,
            'config': config,
            'device': device,
        })
