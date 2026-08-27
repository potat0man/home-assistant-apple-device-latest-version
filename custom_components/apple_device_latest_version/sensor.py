from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
from typing import Any

import aiohttp

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

DOMAIN = "apple_device_latest_version"
SCAN_INTERVAL = timedelta(seconds=600)  # 10 minutes
API_URL = "https://gdmf.apple.com/v2/pmv"


def _release_sort_key(asset: dict[str, Any]) -> tuple[tuple[int, ...], str]:
    """Order a device's available releases, newest first.

    Apple offers several release trains for one device at once and posts them
    all on the same day: an Apple Watch Series 7 is offered watchOS 26.6
    alongside 11.6.2 and 9.6.4, every one of them dated identically. Sorting
    by PostingDate therefore ties, and whichever train Apple happened to list
    first wins, which is how a watch running 26.6 was reported as 9.6.4.

    Compare the version numerically instead, so 26.6 beats 9.6.4 (as strings
    it would not), and keep PostingDate as the tie-breaker.
    """
    version = asset.get("ProductVersion") or ""
    return (
        tuple(int(part) for part in re.findall(r"\d+", version)),
        asset.get("PostingDate") or "",
    )

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device_model = config_entry.data["device_model"]
    device_name = config_entry.data["device_name"]
    coordinator = AppleVersionCoordinator(hass, device_model)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([AppleVersionSensor(coordinator, device_name, device_model)])

class AppleVersionCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, device_model: str) -> None:
        self.device_model = device_model
        super().__init__(
            hass,
            _LOGGER,
            name=f"Apple Version {device_model}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        # gdmf.apple.com serves a certificate that does not validate against
        # the standard trust store, so verification has to be off for this host.
        session = async_get_clientsession(self.hass, verify_ssl=False)

        try:
            async with asyncio.timeout(10):
                async with session.get(API_URL) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
                    
                    data = await response.json(content_type=None)
                    
                    # Parse versions for the specific device model.
                    # Apple groups assets loosely: watchOS and tvOS releases are
                    # filed under the "iOS" key rather than keys of their own, so
                    # every asset list has to be searched to find a given device.
                    public_sets = data.get("PublicAssetSets", {}) or {}
                    versions: list[dict[str, Any]] = []
                    for asset_list in public_sets.values():
                        if isinstance(asset_list, list):
                            versions.extend(asset_list)

                    # Filter versions that support this device
                    matches = [
                        v
                        for v in versions
                        if "SupportedDevices" in v and self.device_model in v.get("SupportedDevices", [])
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
                    
                    # Highest version number wins, not most recently posted.
                    matches.sort(key=_release_sort_key, reverse=True)
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
