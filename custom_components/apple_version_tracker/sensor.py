"""Apple Version Tracker sensor platform."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apple_version_tracker"
SCAN_INTERVAL = timedelta(seconds=600)  # 10 minutes
API_URL = "https://gdmf.apple.com/v2/pmv"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Apple Version Tracker sensor from a config entry."""
    device_model = config_entry.data["device_model"]
    device_name = config_entry.data["device_name"]

    coordinator = AppleVersionCoordinator(hass, device_model)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([AppleVersionSensor(coordinator, device_name, device_model)])


class AppleVersionCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Apple version data."""

    def __init__(self, hass: HomeAssistant, device_model: str) -> None:
        """Initialize."""
        self.device_model = device_model
        super().__init__(
            hass,
            _LOGGER,
            name=f"Apple Version {device_model}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Apple API."""
        session = async_get_clientsession(self.hass, verify_ssl=False)
        
        try:
            async with async_timeout.timeout(10):
                async with session.get(API_URL) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    
                    data = await response.json()
                    
                    # Parse versions for the specific device model
                    versions = data.get("PublicAssetSets", {}).get("iOS", [])
                    
                    # Filter versions that support this device
                    matches = [
                        v for v in versions
                        if "SupportedDevices" in v
                        and self.device_model in v.get("SupportedDevices", [])
                    ]
                    
                    if not matches:
                        _LOGGER.warning(
                            "No versions found for device model: %s", self.device_model
                        )
                        return {
                            "version": "unknown",
                            "build": None,
                            "posting_date": None,
                        }
                    
                    # Sort by posting date and get the latest
                    matches.sort(key=lambda x: x.get("PostingDate", ""), reverse=True)
                    latest = matches[0]
                    
                    return {
                        "version": latest.get("ProductVersion", "unknown"),
                        "build": latest.get("Build"),
                        "posting_date": latest.get("PostingDate"),
                        "supported_devices": latest.get("SupportedDevices", []),
                    }
                    
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err


class AppleVersionSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Apple Version sensor."""

    def __init__(
        self,
        coordinator: AppleVersionCoordinator,
        device_name: str,
        device_model: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_name = device_name
        self._device_model = device_model
        self._attr_name = f"Latest Version {device_name}"
        self._attr_unique_id = f"apple_version_{device_model}"
        self._attr_icon = "mdi:apple"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data.get("version", "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "product_version": self.coordinator.data.get("version"),
            "build": self.coordinator.data.get("build"),
            "posting_date": self.coordinator.data.get("posting_date"),
            "device_model": self._device_model,
            "supported_devices": self.coordinator.data.get("supported_devices", []),
        }
