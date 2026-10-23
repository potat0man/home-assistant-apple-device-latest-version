from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import AppleVersionCoordinator

DOMAIN = "apple_device_latest_version"
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = AppleVersionCoordinator(hass, entry)

    # Fetch before forwarding to the sensor platform. If Apple's feed is
    # unreachable (common right after Home Assistant starts, before the network
    # is up), this raises ConfigEntryNotReady here, where Home Assistant
    # handles it by retrying the setup with backoff. Raised from inside the
    # forwarded platform instead, it is rejected and the entry never recovers.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
