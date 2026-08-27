from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apple_device_latest_version"
API_URL = "https://gdmf.apple.com/v2/pmv"


async def _async_get_device_models(hass: HomeAssistant) -> list[str]:
    """Fetch the list of device model identifiers Apple currently supports."""
    session = async_get_clientsession(hass)

    async with asyncio.timeout(10):
        async with session.get(API_URL) as response:
            response.raise_for_status()
            data = await response.json()

    models: set[str] = set()
    for asset_list in (data.get("PublicAssetSets") or {}).values():
        if isinstance(asset_list, list):
            for asset in asset_list:
                models.update(asset.get("SupportedDevices", []))

    return sorted(models)


def _build_data_schema(device_models: list[str]) -> vol.Schema:
    if device_models:
        device_model_selector: Any = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=device_models,
                mode=selector.SelectSelectorMode.DROPDOWN,
                custom_value=True,
                sort=True,
            )
        )
    else:
        device_model_selector = str

    return vol.Schema(
        {
            vol.Required("device_model"): device_model_selector,
            vol.Required("device_name"): str,
        }
    )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    device_model = data["device_model"].strip()
    device_name = data["device_name"].strip()

    if not device_model:
        raise InvalidDeviceModel

    if not device_name:
        raise InvalidDeviceName

    return {"title": device_name, "device_model": device_model}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        try:
            device_models = await _async_get_device_models(self.hass)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.warning(
                "Could not fetch the list of supported device models; "
                "falling back to manual entry"
            )
            device_models = []

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidDeviceModel:
                errors["device_model"] = "invalid_device_model"
            except InvalidDeviceName:
                errors["device_name"] = "invalid_device_name"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["device_model"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_data_schema(device_models),
            errors=errors,
        )


class InvalidDeviceModel(HomeAssistantError):
    """Error to indicate invalid device model."""
    pass


class InvalidDeviceName(HomeAssistantError):
    """Error to indicate invalid device name."""
    pass