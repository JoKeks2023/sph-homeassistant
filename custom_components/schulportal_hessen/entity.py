"""Base entity for Schulportal Hessen."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SCHOOL_NAME, DOMAIN
from .coordinator import SphCoordinator


class SphEntity(CoordinatorEntity[SphCoordinator]):
    """Entity bound to the coordinator and one device per config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SphCoordinator, key: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_SCHOOL_NAME) or "Schulportal Hessen",
            manufacturer="Schulportal Hessen (inoffiziell)",
            entry_type=DeviceEntryType.SERVICE,
        )
