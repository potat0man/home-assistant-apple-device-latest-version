"""Config flow for Apple Version Tracker."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apple_version_tracker"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("device_model"): str,
        vol.Required("device_name"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input."""
    device_model = data["device_model"].strip()
    device_name = data["device_name"].strip()

    if not device_model:
        raise InvalidDeviceModel

    if not device_name:
        raise InvalidDeviceName

    return {"title": device_name, "device_model": device_model}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Apple Version Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
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
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidDeviceModel(HomeAssistantError):
    """Error to indicate invalid device model."""


class InvalidDeviceName(HomeAssistantError):
    """Error to indicate invalid device name."""
