from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AppleVersionCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    # The coordinator has already been refreshed in __init__.py, so a failed
    # first fetch is raised there and Home Assistant retries the setup.
    coordinator: AppleVersionCoordinator = config_entry.runtime_data
    async_add_entities(
        [
            AppleVersionSensor(
                coordinator,
                config_entry.data["device_name"],
                config_entry.data["device_model"],
            )
        ]
    )


class AppleVersionSensor(CoordinatorEntity[AppleVersionCoordinator], SensorEntity):
    def __init__(
        self,
        coordinator: AppleVersionCoordinator,
        device_name: str,
        device_model: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_name = device_name
        self._device_model = device_model
        self._attr_name = f"Latest Version {device_name}"
        self._attr_unique_id = f"apple_version_{device_model}"
        self._attr_icon = "mdi:apple"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("version", "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "product_version": self.coordinator.data.get("version"),
            "build": self.coordinator.data.get("build"),
            "posting_date": self.coordinator.data.get("posting_date"),
            "device_model": self._device_model,
            "supported_devices": self.coordinator.data.get("supported_devices", []),
        }
