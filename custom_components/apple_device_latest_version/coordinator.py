from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

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


class AppleVersionCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.device_model: str = entry.data["device_model"]
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Apple Version {self.device_model}",
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
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timed out talking to Apple's version feed") from err
        except ValueError as err:
            raise UpdateFailed(f"Apple's version feed was not valid JSON: {err}") from err

        # Apple groups assets loosely: watchOS and tvOS releases are filed under
        # the "iOS" key rather than keys of their own, so every asset list has
        # to be searched to find a given device.
        versions: list[dict[str, Any]] = []
        for asset_list in (data.get("PublicAssetSets") or {}).values():
            if isinstance(asset_list, list):
                versions.extend(asset_list)

        matches = [
            v for v in versions if self.device_model in v.get("SupportedDevices", [])
        ]

        if not matches:
            _LOGGER.warning("No versions found for device model: %s", self.device_model)
            return {"version": "unknown", "build": None, "posting_date": None}

        # Highest version number wins, not most recently posted.
        latest = max(matches, key=_release_sort_key)

        return {
            "version": latest.get("ProductVersion", "unknown"),
            "build": latest.get("Build"),
            "posting_date": latest.get("PostingDate"),
            "supported_devices": latest.get("SupportedDevices", []),
        }
