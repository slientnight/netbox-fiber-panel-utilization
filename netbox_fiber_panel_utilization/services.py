"""Service layer for fiber patch panel utilization calculations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModuleUtilization:
    """Per-module utilization data for a single cassette module."""

    bay_name: str  # Module_Bay.name
    module_model: str  # ModuleType.model
    used_ports: int  # Connected front ports on this module
    total_ports: int  # Total front ports on this module

    @property
    def utilization_percent(self) -> float:
        """Calculate utilization percentage with zero-division guard."""
        if self.total_ports == 0:
            return 0.0
        return round((self.used_ports / self.total_ports) * 100, 1)


@dataclass
class PanelUtilization:
    """Aggregate utilization data for a fiber patch panel device."""

    device_id: int
    device_name: str
    site: str | None
    location: str | None
    rack: str | None
    total_ports: int
    used_ports: int
    free_ports: int
    utilization_percent: float
    modules: list[ModuleUtilization] = field(default_factory=list)


class FiberPanelUtilizationService:
    """Central service for fiber patch panel utilization logic.

    Stateless service that receives a config dict at construction.
    All qualification and calculation logic lives here.
    """

    def __init__(self, config: dict) -> None:
        """Initialise with plugin configuration dictionary.

        Args:
            config: Settings dict sourced from
                    PLUGINS_CONFIG['netbox_fiber_panel_utilization'].
        """
        self.config = config

    # ------------------------------------------------------------------
    # Qualification
    # ------------------------------------------------------------------

    def is_supported_device(self, device) -> bool:
        """Run the ordered qualification chain and structural check.

        Qualification order:
        1. device_type_slugs (allowlist) – reject if non-empty and slug not in list
        2. device_role_slugs (allowlist) – reject if non-empty and slug not in list
        3. model_regex – reject if non-empty and no match (invalid regex → skip)
        4. Structural fallback – device must have ≥1 ModuleBay with an
           installed Module that has ≥1 FrontPort.

        Returns:
            True if the device qualifies as a supported fiber patch panel.
        """
        # --- Filter 1: device_type_slugs ---
        type_slugs = self.config.get('device_type_slugs', [])
        if type_slugs:
            if device.device_type.slug not in type_slugs:
                return False

        # --- Filter 2: device_role_slugs ---
        role_slugs = self.config.get('device_role_slugs', [])
        if role_slugs:
            if device.device_role.slug not in role_slugs:
                return False

        # --- Filter 3: model_regex ---
        model_regex = self.config.get('model_regex', '')
        if model_regex:
            try:
                pattern = re.compile(model_regex)
                model_str = getattr(device.device_type, 'model', '') or ''
                slug_str = device.device_type.slug or ''
                if not (pattern.search(model_str) or pattern.search(slug_str)):
                    return False
            except re.error:
                logger.warning(
                    "Invalid model_regex pattern %r – falling back to "
                    "structural detection only.",
                    model_regex,
                )
                # Skip regex filter; continue to structural check

        # --- Structural check ---
        return self._has_fiber_structure(device)

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    def get_installed_modules(self, device):
        """Return installed modules in device's module bays, ordered by bay position.

        Uses select_related/prefetch_related to avoid N+1 queries.
        """
        from dcim.models import FrontPort, Module
        from django.db.models import Prefetch

        return Module.objects.filter(
            module_bay__device=device,
        ).select_related(
            'module_bay',
            'module_type',
        ).prefetch_related(
            Prefetch('frontports', queryset=FrontPort.objects.select_related('cable')),
        ).order_by('module_bay__position')

    def get_front_ports(self, module):
        """Return front ports for a module with cable info prefetched."""
        return module.frontports.all()

    def get_module_breakdown(self, device) -> list[ModuleUtilization]:
        """Per-module utilization list."""
        modules = self.get_installed_modules(device)
        breakdown = []
        for module in modules:
            port_list = list(self.get_front_ports(module))
            total = len(port_list)
            used = sum(1 for p in port_list if p.cable is not None)
            breakdown.append(ModuleUtilization(
                bay_name=module.module_bay.name,
                module_model=module.module_type.model,
                used_ports=used,
                total_ports=total,
            ))
        return breakdown

    def calculate(self, device) -> PanelUtilization:
        """Full utilization calculation for a device."""
        breakdown = self.get_module_breakdown(device)
        total = sum(m.total_ports for m in breakdown)
        used = sum(m.used_ports for m in breakdown)
        free = total - used
        percent = round((used / total) * 100, 1) if total > 0 else 0.0

        return PanelUtilization(
            device_id=device.pk,
            device_name=device.name,
            site=str(device.site) if device.site else None,
            location=str(device.location) if device.location else None,
            rack=str(device.rack) if device.rack else None,
            total_ports=total,
            used_ports=used,
            free_ports=free,
            utilization_percent=percent,
            modules=breakdown,
        )

    def serialize(self, utilization: PanelUtilization) -> dict:
        """Convert PanelUtilization to JSON-serializable dict matching the API schema."""
        return {
            "device_id": utilization.device_id,
            "device_name": utilization.device_name,
            "site": utilization.site,
            "location": utilization.location,
            "rack": utilization.rack,
            "total_ports": utilization.total_ports,
            "used_ports": utilization.used_ports,
            "free_ports": utilization.free_ports,
            "utilization_percent": utilization.utilization_percent,
            "modules": [
                {
                    "name": m.bay_name,
                    "model": m.module_model,
                    "used": m.used_ports,
                    "total": m.total_ports,
                }
                for m in utilization.modules
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_fiber_structure(device) -> bool:
        """Return True if *device* has ≥1 ModuleBay → installed Module → ≥1 FrontPort."""
        from dcim.models import ModuleBay

        module_bays = ModuleBay.objects.filter(device=device).select_related(
            'installed_module',
        )
        for bay in module_bays:
            module = getattr(bay, 'installed_module', None)
            if module is None:
                continue
            if module.frontports.exists():
                return True
        return False
