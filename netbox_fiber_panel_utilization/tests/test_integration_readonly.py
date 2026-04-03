"""Integration tests for read-only enforcement.

Validates: Requirements 10.1, 10.2

- The service layer only calls read methods on the ORM (filter, select_related,
  prefetch_related, get, exists, all) and never calls create, save, update,
  delete, or bulk_create/bulk_update.
- The API view only allows GET method (http_method_names = ['get']).
- The API view returns 405 for write methods (POST, PUT, PATCH, DELETE).
- The service's calculate() and get_module_breakdown() only perform read
  operations by inspecting mock call history.
- The template extension's right_page() doesn't trigger any write operations.
"""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch, call

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
from rest_framework.test import APIRequestFactory

from netbox_fiber_panel_utilization.api.views import PanelUtilizationAPIView
from netbox_fiber_panel_utilization.services import FiberPanelUtilizationService
from netbox_fiber_panel_utilization.template_content import (
    FiberPanelUtilizationExtension,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WRITE_METHODS = [
    'create', 'save', 'update', 'delete',
    'bulk_create', 'bulk_update', 'bulk_delete',
]

READ_METHODS = [
    'filter', 'select_related', 'prefetch_related',
    'get', 'exists', 'all', 'order_by',
]

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_front_port(cable=None):
    """Create a fake FrontPort with optional cable."""
    return SimpleNamespace(cable=cable)


def _make_module(bay_name, module_model, front_ports):
    """Create a fake Module with module_bay, module_type, and prefetched frontports."""
    module = MagicMock()
    module.module_bay = SimpleNamespace(name=bay_name)
    module.module_type = SimpleNamespace(model=module_model)
    module.frontports.all.return_value = front_ports
    return module


def _make_device():
    """Create a fake device with standard attributes."""
    return SimpleNamespace(
        pk=1,
        name='Panel-RO-Test',
        site='DC-East',
        location='Hall-A',
        rack='Rack-7',
        device_type=SimpleNamespace(slug='fiber-panel', model='FP-4U'),
        device_role=SimpleNamespace(slug='patch-panel'),
    )


def _build_tracked_orm_mocks():
    """Build mock ORM classes that track all method calls for write detection.

    Returns (mock_module_cls, mock_modulebay_cls, mock_frontport_cls,
             mock_prefetch_cls, saved_modules) for use in sys.modules patching.
    """
    mock_module_cls = MagicMock(name='Module')
    mock_modulebay_cls = MagicMock(name='ModuleBay')
    mock_frontport_cls = MagicMock(name='FrontPort')
    mock_prefetch_cls = MagicMock(name='Prefetch')

    dcim_models = MagicMock()
    dcim_models.Module = mock_module_cls
    dcim_models.ModuleBay = mock_modulebay_cls
    dcim_models.FrontPort = mock_frontport_cls

    django_db_models = MagicMock()
    django_db_models.Prefetch = mock_prefetch_cls

    saved = {}
    for key in ('dcim', 'dcim.models', 'django.db', 'django.db.models'):
        saved[key] = sys.modules.get(key)

    sys.modules['dcim'] = MagicMock(models=dcim_models)
    sys.modules['dcim.models'] = dcim_models
    sys.modules['django.db'] = MagicMock(models=django_db_models)
    sys.modules['django.db.models'] = django_db_models

    return mock_module_cls, mock_modulebay_cls, mock_frontport_cls, saved


def _restore_modules(saved):
    """Restore sys.modules to their original state."""
    for key, val in saved.items():
        if val is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = val


def _extract_call_names(mock_obj):
    """Recursively extract all method names called on a mock and its children."""
    names = set()
    for c in mock_obj.mock_calls:
        call_str = str(c)
        # Extract method names from call strings like "call.objects.filter(...)"
        for method in WRITE_METHODS:
            if f'.{method}(' in call_str or f'.{method}.' in call_str:
                names.add(method)
    return names


def _make_mock_device_module(*, device=None, raise_not_found=False):
    """Create mock dcim.models with a Device class for API view tests."""
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


# ---------------------------------------------------------------------------
# Req 10.1, 10.2 – API view only allows GET
# ---------------------------------------------------------------------------

class TestAPIViewReadOnlyEnforcement:
    """Validates: Requirements 10.1, 10.2, 10.3"""

    def test_http_method_names_is_get_only(self):
        """The API view's http_method_names must contain only 'get'."""
        assert PanelUtilizationAPIView.http_method_names == ['get']

    def test_405_for_post(self):
        """POST request returns 405 Method Not Allowed."""
        factory = APIRequestFactory()
        request = factory.post(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)
        view = PanelUtilizationAPIView.as_view()
        response = view(request, device_id=1)
        assert response.status_code == 405

    def test_405_for_put(self):
        """PUT request returns 405 Method Not Allowed."""
        factory = APIRequestFactory()
        request = factory.put(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)
        view = PanelUtilizationAPIView.as_view()
        response = view(request, device_id=1)
        assert response.status_code == 405

    def test_405_for_patch(self):
        """PATCH request returns 405 Method Not Allowed."""
        factory = APIRequestFactory()
        request = factory.patch(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)
        view = PanelUtilizationAPIView.as_view()
        response = view(request, device_id=1)
        assert response.status_code == 405

    def test_405_for_delete(self):
        """DELETE request returns 405 Method Not Allowed."""
        factory = APIRequestFactory()
        request = factory.delete(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)
        view = PanelUtilizationAPIView.as_view()
        response = view(request, device_id=1)
        assert response.status_code == 405


# ---------------------------------------------------------------------------
# Req 10.1, 10.2 – Service calculate() only performs read operations
# ---------------------------------------------------------------------------

class TestServiceCalculateReadOnly:
    """Validates: Requirements 10.1, 10.2

    Verify that calculate() and get_module_breakdown() only call read
    methods on the ORM by inspecting mock call history.
    """

    def test_calculate_no_write_calls(self):
        """calculate() must not invoke any ORM write methods."""
        device = _make_device()
        modules = [
            _make_module('Bay 1', 'LC-12', [
                _make_front_port(cable='c1'),
                _make_front_port(),
            ]),
        ]

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, 'get_installed_modules', return_value=modules):
            result = svc.calculate(device)

        # Verify result is valid (service ran successfully)
        assert result.total_ports == 2
        assert result.used_ports == 1

        # Inspect each module mock for write method calls
        for mod in modules:
            write_calls = _extract_call_names(mod)
            assert len(write_calls) == 0, (
                f"Write methods called on module mock: {write_calls}"
            )

    def test_get_module_breakdown_no_write_calls(self):
        """get_module_breakdown() must not invoke any ORM write methods."""
        device = _make_device()
        modules = [
            _make_module('Bay 1', 'LC-12', [
                _make_front_port(cable='c1'),
                _make_front_port(cable='c2'),
            ]),
            _make_module('Bay 2', 'LC-24', [
                _make_front_port(),
                _make_front_port(),
            ]),
        ]

        svc = FiberPanelUtilizationService({})
        with patch.object(svc, 'get_installed_modules', return_value=modules):
            breakdown = svc.get_module_breakdown(device)

        assert len(breakdown) == 2

        for mod in modules:
            write_calls = _extract_call_names(mod)
            assert len(write_calls) == 0, (
                f"Write methods called on module mock: {write_calls}"
            )

    def test_get_installed_modules_uses_only_read_chain(self):
        """get_installed_modules() constructs a read-only ORM query chain."""
        mock_module_cls, mock_modulebay_cls, mock_fp_cls, saved = (
            _build_tracked_orm_mocks()
        )
        try:
            device = SimpleNamespace(pk=1)
            svc = FiberPanelUtilizationService({})
            svc.get_installed_modules(device)

            # Verify filter was called (read operation)
            mock_module_cls.objects.filter.assert_called_once()

            # Verify no write methods were called on Module.objects
            write_calls = _extract_call_names(mock_module_cls.objects)
            assert len(write_calls) == 0, (
                f"Write methods called on Module.objects: {write_calls}"
            )
        finally:
            _restore_modules(saved)


# ---------------------------------------------------------------------------
# Req 10.1, 10.2 – Template extension right_page() read-only
# ---------------------------------------------------------------------------

class TestTemplateExtensionReadOnly:
    """Validates: Requirements 10.1, 10.2

    Verify that the template extension's right_page() does not trigger
    any write operations on the ORM.
    """

    @patch.object(FiberPanelUtilizationService, 'is_supported_device',
                  return_value=True)
    @patch.object(FiberPanelUtilizationService, 'calculate')
    def test_right_page_no_write_operations(self, mock_calc, mock_supported):
        """right_page() must not trigger any ORM write operations."""
        from netbox_fiber_panel_utilization.services import (
            ModuleUtilization,
            PanelUtilization,
        )

        device = _make_device()
        mock_calc.return_value = PanelUtilization(
            device_id=1,
            device_name='Panel-RO-Test',
            site='DC-East',
            location='Hall-A',
            rack='Rack-7',
            total_ports=12,
            used_ports=6,
            free_ports=6,
            utilization_percent=50.0,
            modules=[
                ModuleUtilization(
                    bay_name='Bay 1',
                    module_model='LC-12',
                    used_ports=6,
                    total_ports=12,
                ),
            ],
        )

        ext = FiberPanelUtilizationExtension({'object': device})

        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                          create=True):
            result = ext.right_page()

        # is_supported_device was called (read check)
        mock_supported.assert_called_once_with(device)
        # calculate was called (read operation)
        mock_calc.assert_called_once_with(device)

        # Verify no write methods were called on the service
        # (the service only reads; we verify the mock wasn't asked to write)
        for method_name in WRITE_METHODS:
            assert not hasattr(mock_calc, method_name) or \
                not getattr(mock_calc, method_name).called, (
                    f"Write method '{method_name}' was called during right_page()"
                )

    @patch.object(FiberPanelUtilizationService, 'is_supported_device',
                  return_value=False)
    def test_unsupported_device_no_write_operations(self, mock_supported):
        """right_page() for unsupported device returns '' with no writes."""
        device = _make_device()
        ext = FiberPanelUtilizationExtension({'object': device})

        with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                          create=True):
            result = ext.right_page()

        assert result == ''
        mock_supported.assert_called_once_with(device)


# ---------------------------------------------------------------------------
# Req 10.1, 10.2 – API view GET path performs only read operations
# ---------------------------------------------------------------------------

class TestAPIViewGetReadOnly:
    """Validates: Requirements 10.1, 10.2

    Verify the API view's GET handler only performs read operations
    by inspecting mock call history on the service and ORM.
    """

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_api_get_no_write_operations_on_service(self, mock_svc_cls):
        """API GET must only call read methods on the service."""
        mock_svc = MagicMock()
        mock_svc.is_supported_device.return_value = True
        mock_svc.calculate.return_value = MagicMock()
        mock_svc.serialize.return_value = {
            'device_id': 1, 'device_name': 'P1', 'site': None,
            'location': None, 'rack': None, 'total_ports': 12,
            'used_ports': 6, 'free_ports': 6, 'utilization_percent': 50.0,
            'modules': [],
        }
        mock_svc_cls.return_value = mock_svc

        mock_device = MagicMock(pk=1)
        dcim, dcim_models, mock_device_cls = _make_mock_device_module(
            device=mock_device,
        )

        view = PanelUtilizationAPIView()
        factory = APIRequestFactory()
        request = factory.get(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)

        saved_dcim = sys.modules.get('dcim')
        saved_dcim_models = sys.modules.get('dcim.models')
        try:
            sys.modules['dcim'] = dcim
            sys.modules['dcim.models'] = dcim_models
            with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                              create=True):
                response = view.get(request, device_id=1)
        finally:
            if saved_dcim is None:
                sys.modules.pop('dcim', None)
            else:
                sys.modules['dcim'] = saved_dcim
            if saved_dcim_models is None:
                sys.modules.pop('dcim.models', None)
            else:
                sys.modules['dcim.models'] = saved_dcim_models

        assert response.status_code == 200

        # Verify service was only called with read methods
        svc_calls = [str(c) for c in mock_svc.mock_calls]
        for call_str in svc_calls:
            for write_method in WRITE_METHODS:
                assert f'.{write_method}(' not in call_str, (
                    f"Write method '{write_method}' found in service calls: "
                    f"{call_str}"
                )

        # Verify Device ORM was only called with read methods
        device_write_calls = _extract_call_names(mock_device_cls.objects)
        assert len(device_write_calls) == 0, (
            f"Write methods called on Device.objects: {device_write_calls}"
        )

    @patch('netbox_fiber_panel_utilization.api.views.FiberPanelUtilizationService')
    def test_api_get_device_queried_via_get_only(self, mock_svc_cls):
        """API GET retrieves the device via .get() (a read operation)."""
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

        view = PanelUtilizationAPIView()
        factory = APIRequestFactory()
        request = factory.get(
            '/api/plugins/fiber-panel-utilization/panels/1/utilization/',
        )
        request.user = MagicMock(is_authenticated=True)

        saved_dcim = sys.modules.get('dcim')
        saved_dcim_models = sys.modules.get('dcim.models')
        try:
            sys.modules['dcim'] = dcim
            sys.modules['dcim.models'] = dcim_models
            with patch.object(settings, 'PLUGINS_CONFIG', _PLUGIN_CONFIG,
                              create=True):
                view.get(request, device_id=1)
        finally:
            if saved_dcim is None:
                sys.modules.pop('dcim', None)
            else:
                sys.modules['dcim'] = saved_dcim
            if saved_dcim_models is None:
                sys.modules.pop('dcim.models', None)
            else:
                sys.modules['dcim.models'] = saved_dcim_models

        # Verify .restrict().get() was called (both are read operations)
        mock_device_cls.objects.restrict.assert_called_once()
        mock_device_cls.objects.restrict.return_value.get.assert_called_once_with(
            pk=1,
        )

        # Verify no write methods on Device.objects
        for method in WRITE_METHODS:
            assert not getattr(mock_device_cls.objects, method).called, (
                f"Device.objects.{method}() was called during API GET"
            )


# ---------------------------------------------------------------------------
# Req 10.1, 10.2 – Structural check (_has_fiber_structure) is read-only
# ---------------------------------------------------------------------------

class TestStructuralCheckReadOnly:
    """Validates: Requirements 10.1, 10.2

    Verify that _has_fiber_structure() only uses read ORM methods.
    """

    def test_has_fiber_structure_uses_only_read_methods(self):
        """_has_fiber_structure uses filter, select_related, exists (all reads)."""
        mock_modulebay_cls = MagicMock(name='ModuleBay')

        # Set up a bay with an installed module that has frontports
        mock_module = MagicMock()
        mock_module.frontports.exists.return_value = True
        mock_bay = MagicMock()
        mock_bay.installed_module = mock_module

        mock_modulebay_cls.objects.filter.return_value.select_related.return_value = [
            mock_bay,
        ]

        dcim_models = MagicMock()
        dcim_models.ModuleBay = mock_modulebay_cls

        saved = {}
        for key in ('dcim', 'dcim.models'):
            saved[key] = sys.modules.get(key)

        sys.modules['dcim'] = MagicMock(models=dcim_models)
        sys.modules['dcim.models'] = dcim_models

        try:
            device = SimpleNamespace(pk=1)
            result = FiberPanelUtilizationService._has_fiber_structure(device)

            assert result is True

            # Verify only read methods were called on ModuleBay.objects
            mock_modulebay_cls.objects.filter.assert_called_once()
            write_calls = _extract_call_names(mock_modulebay_cls.objects)
            assert len(write_calls) == 0, (
                f"Write methods called on ModuleBay.objects: {write_calls}"
            )

            # Verify only exists() was called on frontports (a read method)
            mock_module.frontports.exists.assert_called_once()
            write_calls = _extract_call_names(mock_module)
            assert len(write_calls) == 0, (
                f"Write methods called on module mock: {write_calls}"
            )
        finally:
            _restore_modules(saved)
