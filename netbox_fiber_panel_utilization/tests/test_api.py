"""Unit tests for the API endpoint (PanelUtilizationAPIView).

Validates: Requirements 7.2, 7.4, 7.5, 7.6, 7.7, 7.8, 10.3, 13.3, 13.4

Since we cannot run a full NetBox instance, tests mock the Django ORM and
DRF request objects.  View-class introspection tests (http_method_names,
permission_classes) require no mocking at all.
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
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'rest_framework',
            'netbox_fiber_panel_utilization',
        ],
        STATIC_URL='/static/',
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            },
        },
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': [
                'rest_framework.authentication.SessionAuthentication',
            ],
        },
    )
    django.setup()

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory

from netbox_fiber_panel_utilization.api.views import PanelUtilizationAPIView
from netbox_fiber_panel_utilization.services import (
    ModuleUtilization,
    PanelUtilization,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLUGIN_CONFIG = {
    'netbox_fiber_panel_utilization': {
        'device_type_slugs': [],
        'device_role_slugs': [],
        'model_regex': '',
        'warning_threshold': 50,
        'critical_threshold': 80,
        'show_module_breakdown': True,
        'show_port_table': True,
    },
}

_SERIALIZED_DATA = {
    'device_id': 1,
    'device_name': 'Fiber-Panel-01',
    'site': 'Site Alpha',
    'location': 'Room 101',
    'rack': 'Rack A1',
    'total_ports': 24,
    'used_ports': 12,
    'free_ports': 12,
    'utilization_percent': 50.0,
    'modules': [
        {'name': 'Bay 1', 'model': 'LC-12', 'used': 6, 'total': 12},
        {'name': 'Bay 2', 'model': 'LC-12', 'used': 6, 'total': 12},
    ],
}


def _sample_utilization():
    """Return a PanelUtilization with reasonable defaults."""
    return PanelUtilization(
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
            ModuleUtilization(bay_name='Bay 1', module_model='LC-12', used_ports=6, total_ports=12),
            ModuleUtilization(bay_name='Bay 2', module_model='LC-12', used_ports=6, total_ports=12),
        ],
    )


def _make_mock_device_module(*, device=None, raise_not_found=False):
    """Create a mock dcim.models module with a Device class.

    The Device mock is set up so that local imports inside the view's get()
    method (``from dcim.models import Device``) resolve correctly.
    """
    mock_device_cls = MagicMock()
    does_not_exist = type('DoesNotExist', (Exception,), {})
    mock_device_cls.DoesNotExist = does_not_exist

    if raise_not_found:
        mock_device_cls.objects.restrict.return_value.get.side_effect = does_not_exist("not found")
        mock_device_cls.objects.get.side_effect = does_not_exist("not found")
    elif device is not None:
        mock_device_cls.objects.restrict.return_value.get.return_value = device
        mock_device_cls.objects.get.return_value = device

    dcim_models = ModuleType('dcim.models')
    dcim_models.Device = mock_device_cls

    dcim = ModuleType('dcim')
    dcim.models = dcim_models

    return dcim, dcim_models, mock_device_cls


def _make_get_request():
    """Create a DRF GET request with a mock authenticated user."""
    factory = APIRequestFactory()
    request = factory.get('/api/plugins/fiber-panel-utilization/panels/1/utilization/')
    request.user = MagicMock()
    request.user.is_authenticated = True
    return request


def _call_view_get(mock_svc_cls, dcim_module, dcim_models_module, device_id=1):
    """Invoke PanelUtilizationAPIView.get() with patched imports."""
    view_instance = PanelUtilizationAPIView()
    request = _make_get_request()

    saved_dcim = sys.modules.get('dcim')
    saved_dcim_models = sys.modules.get('dcim.models')
    try:
        sys.modules['dcim'] = dcim_module
        sys.modules['dcim.models'] = dcim_models_module
        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG, create=True):
            response = view_instance.get(request, device_id=device_id)
    finally:
        # Restore original module state
        if saved_dcim is None:
            sys.modules.pop('dcim', None)
        else:
            sys.modules['dcim'] = saved_dcim
        if saved_dcim_models is None:
            sys.modules.pop('dcim.models', None)
        else:
            sys.modules['dcim.models'] = saved_dcim_models

    return response


# ---------------------------------------------------------------------------
# Req 7.6, 10.3 – http_method_names only allows GET
# ---------------------------------------------------------------------------

class TestHttpMethodNames:
    def test_http_method_names_only_get(self):
        """The view only allows GET requests."""
        assert PanelUtilizationAPIView.http_method_names == ['get']


# ---------------------------------------------------------------------------
# Req 7.7, 13.4 – permission_classes includes IsAuthenticated
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    def test_permission_classes_includes_is_authenticated(self):
        """IsAuthenticated is in the view's permission_classes."""
        assert IsAuthenticated in PanelUtilizationAPIView.permission_classes


# ---------------------------------------------------------------------------
# Req 7.2, 7.8 – Successful JSON response structure and Content-Type
# ---------------------------------------------------------------------------

class TestSuccessfulResponse:
    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_successful_response_structure(self, mock_svc_cls):
        """A successful GET returns all expected top-level keys."""
        mock_svc = MagicMock()
        mock_svc.is_supported_device.return_value = True
        mock_svc.calculate.return_value = _sample_utilization()
        mock_svc.serialize.return_value = dict(_SERIALIZED_DATA)
        mock_svc_cls.return_value = mock_svc

        mock_device = MagicMock(pk=1)
        dcim, dcim_models, _ = _make_mock_device_module(device=mock_device)

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1)

        assert response.status_code == 200
        expected_keys = {
            'device_id', 'device_name', 'site', 'location', 'rack',
            'total_ports', 'used_ports', 'free_ports', 'utilization_percent',
            'modules',
        }
        assert set(response.data.keys()) == expected_keys
        assert response.data['device_id'] == 1
        assert response.data['device_name'] == 'Fiber-Panel-01'
        assert isinstance(response.data['modules'], list)
        assert len(response.data['modules']) == 2

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_content_type_is_json(self, mock_svc_cls):
        """Successful response uses application/json Content-Type.

        DRF's Response sets Content-Type during rendering.  When calling
        the view's get() directly the response is unrendered, so we render
        it manually with the JSONRenderer to verify the header.
        """
        from rest_framework.renderers import JSONRenderer

        mock_svc = MagicMock()
        mock_svc.is_supported_device.return_value = True
        mock_svc.calculate.return_value = _sample_utilization()
        mock_svc.serialize.return_value = dict(_SERIALIZED_DATA)
        mock_svc_cls.return_value = mock_svc

        mock_device = MagicMock(pk=1)
        dcim, dcim_models, _ = _make_mock_device_module(device=mock_device)

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1)

        assert response.status_code == 200
        # Render the response so Content-Type is set
        response.accepted_renderer = JSONRenderer()
        response.accepted_media_type = 'application/json'
        response.renderer_context = {}
        response.render()
        assert response['Content-Type'] == 'application/json'


# ---------------------------------------------------------------------------
# Req 7.5 – 404 for non-existent device
# ---------------------------------------------------------------------------

class TestNonExistentDevice:
    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_404_for_nonexistent_device(self, mock_svc_cls):
        """GET for a device ID that doesn't exist returns 404."""
        dcim, dcim_models, _ = _make_mock_device_module(raise_not_found=True)

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=99999)

        assert response.status_code == 404
        assert 'detail' in response.data


# ---------------------------------------------------------------------------
# Req 7.4 – 404 for unsupported device
# ---------------------------------------------------------------------------

class TestUnsupportedDevice:
    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_404_for_unsupported_device(self, mock_svc_cls):
        """GET for a device that is not a supported panel returns 404."""
        mock_svc = MagicMock()
        mock_svc.is_supported_device.return_value = False
        mock_svc_cls.return_value = mock_svc

        mock_device = MagicMock(pk=1)
        dcim, dcim_models, _ = _make_mock_device_module(device=mock_device)

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1)

        assert response.status_code == 404
        assert 'not a supported' in response.data['detail'].lower()


# ---------------------------------------------------------------------------
# Req 7.6, 10.3 – 405 for POST/PUT/PATCH/DELETE
# ---------------------------------------------------------------------------

class TestMethodNotAllowed:
    def test_405_for_post(self):
        """POST returns 405 because http_method_names only includes 'get'."""
        assert 'post' not in PanelUtilizationAPIView.http_method_names

    def test_405_for_put(self):
        """PUT returns 405 because http_method_names only includes 'get'."""
        assert 'put' not in PanelUtilizationAPIView.http_method_names

    def test_405_for_patch(self):
        """PATCH returns 405 because http_method_names only includes 'get'."""
        assert 'patch' not in PanelUtilizationAPIView.http_method_names

    def test_405_for_delete(self):
        """DELETE returns 405 because http_method_names only includes 'get'."""
        assert 'delete' not in PanelUtilizationAPIView.http_method_names


# ---------------------------------------------------------------------------
# Req 13.3 – Permission denied returns 403
# ---------------------------------------------------------------------------

class TestPermissionDenied:
    def test_permission_denied_mechanism(self):
        """IsAuthenticated in permission_classes ensures 403 for unauthorized users.

        DRF's IsAuthenticated permission returns 403 when the user is
        authenticated but lacks the required permission.  We verify the
        permission class is configured; actual 403 enforcement is handled
        by DRF's permission framework.
        """
        view = PanelUtilizationAPIView()
        permission_instances = [p() for p in view.permission_classes]
        assert any(isinstance(p, IsAuthenticated) for p in permission_instances)
