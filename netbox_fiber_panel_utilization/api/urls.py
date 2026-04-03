from django.urls import path

from .views import PanelUtilizationAPIView

urlpatterns = [
    path('panels/<int:device_id>/utilization/', PanelUtilizationAPIView.as_view(), name='panel_utilization'),
]
