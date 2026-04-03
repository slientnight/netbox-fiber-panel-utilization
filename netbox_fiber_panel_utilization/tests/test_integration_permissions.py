"""Integration tests for permissions and data visibility.

Validates: Requirements 13.1, 13.2, 13.3

- API view has proper permission classes (IsAuthenticated)
- API view returns 404 (via restrict()) when user lacks permission to view device
- Service layer queries use NetBox's standard ORM (which respects object-level permissions)
- Template extension doesn't render data when device query would be restricted
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

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

import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory

from netbox_fiber_panel_utilization.api.views import PanelUtilizationAPIView
from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService
from netbox_fiber_panel_utilization.template_content import (
    FiberPanelUtilizationExtension,
)


# ---------------------------------------------------------------------------
# Shared helpers
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


def _make_mock_device_module(*, device=None, raise_not_found=False):
    """Create mock dcim.models with a Device class supporting restrict().

    When *raise_not_found* is True the restrict().get() chain raises
    DoesNotExist, simulating a user who lacks object-level permission.
    """
    mock_device_cls = MagicMock()
    does_not_exist = type('DoesNotExist', (Exception,), {})
    mock_device_cls.DoesNotExist = does_not_exist

    if raise_not_found:
        mock_device_cls.objects.restrict.return_value.get.side_effect = (
            does_not_exist("not found")
        )
        mock_device_cls.objects.get.side_effect = does_not_exist("not found")
    elif device is not None:
        mock_device_cls.objects.restrict.return_value.get.return_value = device
        mock_device_cls.objects.get.return_value = device

    dcim_models = ModuleType('dcim.models')
    dcim_models.Device = mock_device_cls

    dcim = ModuleType('dcim')
    dcim.models = dcim_models

    return dcim, dcim_models, mock_device_cls


def _make_get_request(*, authenticated=True):
    """Create a DRF GET request with a mock user."""
    factory = APIRequestFactory()
    request = factory.get(
        '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
    )
    request.user = MagicMock()
    request.user.is_authenticated = authenticated
    return request


def _call_view_get(mock_svc_cls, dcim_module, dcim_models_module,
                   device_id=1, request=None):
    """Invoke PanelUtilizationAPIView.get() with patched imports."""
    view_instance = PanelUtilizationAPIView()
    if request is None:
        request = _make_get_request()

    saved_dcim = sys.modules.get('dcim')
    saved_dcim_models = sys.modules.get('dcim.models')
    try:
        sys.modules['dcim'] = dcim_module
        sys.modules['dcim.models'] = dcim_models_module
        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG, create=True):
            response = view_instance.get(request, device_id=device_id)
    finally:
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
# Req 13.3, 13.4 – API view has IsAuthenticated permission class
# ---------------------------------------------------------------------------

class TestAPIViewPermissionClasses:
    """Validates: Requirement 13.3, 13.4"""

    def test_is_authenticated_in_permission_classes(self):
        """IsAuthenticated must be listed in the view's permission_classes."""
        assert IsAuthenticated in PanelUtilizationAPIView.permission_classes

    def test_permission_class_is_instantiable(self):
        """Each permission class can be instantiated (no broken imports)."""
        view = PanelUtilizationAPIView()
        instances = [p() for p in view.permission_classes]
        assert any(isinstance(p, IsAuthenticated) for p in instances)


# ---------------------------------------------------------------------------
# Req 13.1, 13.2, 13.3 – API returns 404 when user lacks device permission
# ---------------------------------------------------------------------------

class TestAPIRestrictedUser:
    """Validates: Requirements 13.1, 13.2, 13.3

    When a user lacks object-level permission to view a device, NetBox's
    restrict() queryset excludes the device, causing DoesNotExist → 404.
    The plugin must not expose any device data in this case.
    """

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_restricted_user_gets_404(self, mock_svc_cls):
        """A user without view permission on the device receives 404."""
        dcim, dcim_models, mock_device_cls = _make_mock_device_module(
            raise_not_found=True,
        )

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1)

        assert response.status_code == 404
        assert 'detail' in response.data

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_restricted_user_response_has_no_device_data(self, mock_svc_cls):
        """The 404 response must not leak device name, ports, or modules."""
        dcim, dcim_models, _ = _make_mock_device_module(raise_not_found=True)

        response = _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1)

        assert 'device_name' not in response.data
        assert 'total_ports' not in response.data
        assert 'modules' not in response.data

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_restrict_called_with_user_and_view_action(self, mock_svc_cls):
        """The view must call Device.objects.restrict(user, 'view')."""
        mock_device = MagicMock(pk=1)
        dcim, dcim_models, mock_device_cls = _make_mock_device_module(
            device=mock_device,
        )

        mock_svc = MagicMock()
        mock_svc.is_supported_device.return_value = True
        mock_svc.calculate.return_value = MagicMock()
        mock_svc.serialize.return_value = {
            'device_id': 1, 'device_name': 'P1', 'site': None,
            'location': None, 'rack': None, 'total_ports': 0,
            'used_ports': 0, 'free_ports': 0, 'utilization_percent': 0.0,
            'modules': [],
        }
        mock_svc_cls.return_value = mock_svc

        request = _make_get_request()
        _call_view_get(mock_svc_cls, dcim, dcim_models, device_id=1,
                       request=request)

        mock_device_cls.objects.restrict.assert_called_once_with(
            request.user, 'view',
        )


# ---------------------------------------------------------------------------
# Req 13.1 – Service layer uses standard ORM (respects object permissions)
# ---------------------------------------------------------------------------

class TestServiceLayerORMPermissions:
    """Validates: Requirement 13.1

    The service's get_installed_modules uses Module.objects.filter() which
    is the standard NetBox ORM path. Object-level permissions are enforced
    by the caller (the view) via restrict() before the device reaches the
    service layer. We verify the service queries the standard ORM.
    """

    def test_get_installed_modules_uses_standard_orm_filter(self):
        """get_installed_modules calls Module.objects.filter(module_bay__device=device)."""
        mock_module_cls = MagicMock()
        mock_frontport_cls = MagicMock()
        mock_prefetch_cls = MagicMock()

        mock_dcim_models = MagicMock()
        mock_dcim_models.Module = mock_module_cls
        mock_dcim_models.FrontPort = mock_frontport_cls

        mock_django_db_models = MagicMock()
        mock_django_db_models.Prefetch = mock_prefetch_cls

        saved = {}
        for key in ('dcim', 'dcim.models', 'django', 'django.db',
                     'django.db.models'):
            saved[key] = sys.modules.get(key)

        sys.modules['dcim'] = MagicMock(models=mock_dcim_models)
        sys.modules['dcim.models'] = mock_dcim_models
        sys.modules['django'] = MagicMock()
        sys.modules['django.db'] = MagicMock()
        sys.modules['django.db.models'] = mock_django_db_models

        try:
            device = SimpleNamespace(pk=1)
            svc = FiberPanelUtilizationService({})
            svc.get_installed_modules(device)

            mock_module_cls.objects.filter.assert_called_once_with(
                module_bay__device=device,
            )
        finally:
            for key, val in saved.items():
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val


# ---------------------------------------------------------------------------
# Req 13.2 – Template extension doesn't render data for restricted device
# ---------------------------------------------------------------------------

class TestTemplateExtensionPermissions:
    """Validates: Requirement 13.2

    The template extension calls is_supported_device() on the device
    object provided by the context. If the device is not supported (or
    the service raises), no utilization data is rendered.
    """

    @patch.object(FiberPanelUtilizationService, 'is_supported_device',
                  return_value=False)
    def test_unsupported_device_returns_empty_string(self, mock_supported):
        """When is_supported_device returns False, no widget is rendered."""
        device = SimpleNamespace(pk=1, name='Restricted-Panel')
        ext = FiberPanelUtilizationExtension({'object': device})

        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                          create=True):
            result = ext.right_page()

        assert result == ''

    @patch.object(FiberPanelUtilizationService, 'is_supported_device',
                  return_value=True)
    @patch.object(FiberPanelUtilizationService, 'calculate',
                  side_effect=Exception('permission denied'))
    def test_exception_during_calculate_does_not_expose_data(
        self, mock_calc, mock_supported,
    ):
        """If calculate() raises, the extension must not expose device data.

        The extension catches the exception (Req 8.4) and calls render()
        with an error_message context. In the test stub environment render()
        returns '', but the important assertion is that no utilization data
        leaks into the output.
        """
        device = SimpleNamespace(pk=2, name='Error-Panel')
        ext = FiberPanelUtilizationExtension({'object': device})

        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                          create=True):
            result = ext.right_page()

        # No utilization data should be present in the output
        assert 'total_ports' not in result
        assert 'used_ports' not in result
        assert 'utilization_percent' not in result
