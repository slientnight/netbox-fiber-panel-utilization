"""API views for the fiber patch panel utilization plugin."""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services import FiberPanelUtilizationService
from .serializers import PanelUtilizationSerializer

logger = logging.getLogger(__name__)


class PanelUtilizationAPIView(APIView):
    """Read-only API endpoint for fiber panel utilization data."""

    http_method_names = ['get']
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        from dcim.models import Device
        from django.conf import settings

        config = settings.PLUGINS_CONFIG.get('netbox_fiber_panel_utilization', {})

        # Req 7.5, 13.1, 13.2, 13.3: 404 for non-existent device or
        # device the user lacks permission to view.
        # NetBox's restrict() enforces object-level permissions; if the user
        # cannot view the device the queryset excludes it → DoesNotExist → 404.
        try:
            try:
                device = Device.objects.restrict(request.user, 'view').get(pk=device_id)
            except AttributeError:
                # Fallback for environments without NetBox's restrict() method
                device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            return Response(
                {'detail': 'Device not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        svc = FiberPanelUtilizationService(config)

        # Req 7.4: 404 for unsupported device
        if not svc.is_supported_device(device):
            return Response(
                {'detail': 'Device is not a supported fiber patch panel.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        utilization = svc.calculate(device)
        serialized = svc.serialize(utilization)
        serializer = PanelUtilizationSerializer(data=serialized)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
