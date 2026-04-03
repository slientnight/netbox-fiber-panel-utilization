from django.urls import path

from .views import PanelDetailView

urlpatterns = [
    path('<int:device_id>/', PanelDetailView.as_view(), name='panel_detail'),
]
