from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .device_names import DEVICE_NAMES

_LOGGER = logging.getLogger(__name__)

DOMAIN = "apple_device_latest_version"
API_URL = "https://gdmf.apple.com/v2/pmv"

# Apple device identifiers are a family prefix followed by a major,minor
# revision: "iPhone14,4", "Watch7,1", "MacBookPro18,1".
_IDENTIFIER = re.compile(r"^([A-Za-z]+)(\d+),(\d+)$")

# Bucket for identifiers that do not follow the pattern above.
OTHER_TYPE = "other"

# Friendly names for the device families Apple currently ships. A family that
# is missing here still shows up in the picker under its raw prefix, so new
# Apple hardware needs no code change to be selectable.
DEVICE_TYPE_NAMES = {
    "AppleTV": "Apple TV",
    "AudioAccessory": "HomePod",
    "iMac": "iMac",
    "iMacPro": "iMac Pro",
    "iPad": "iPad",
    "iPhone": "iPhone",
    "iPod": "iPod touch",
    "Mac": "Mac",
    "MacBook": "MacBook",
    "MacBookAir": "MacBook Air",
    "MacBookPro": "MacBook Pro",
    "Macmini": "Mac mini",
    "MacPro": "Mac Pro",
    "RealityDevice": "Apple Vision Pro",
    "VirtualMac": "Virtual Mac",
    "Watch": "Apple Watch",
    OTHER_TYPE: "Other",
}

# The families most people are here for, shown at the top of the picker.
# Everything else follows alphabetically.
PREFERRED_TYPE_ORDER = (
    "iPhone",
    "iPad",
    "Watch",
    "AppleTV",
    "AudioAccessory",
    "RealityDevice",
)


def _device_type_name(device_type: str) -> str:
    return DEVICE_TYPE_NAMES.get(device_type, device_type)


def _model_label(model: str) -> str:
    """Label a model as "iPhone 13 mini (iPhone14,4)".

    The identifier stays visible because it is what gets stored, and because
    several models share a marketing name (the Wi-Fi and cellular iPad Pro,
    for instance). A model Apple has published but the name table does not
    know yet is shown as the bare identifier.
    """
    name = DEVICE_NAMES.get(model)
    return f"{name} ({model})" if name else model


def _model_sort_key(model: str) -> tuple[int, str, int, int]:
    """Sort model identifiers so iPhone9,1 comes before iPhone14,4."""
    if match := _IDENTIFIER.match(model):
        return (0, match.group(1), int(match.group(2)), int(match.group(3)))
    return (1, model, 0, 0)


def _device_type_sort_key(device_type: str) -> tuple[int, str]:
    try:
        return (PREFERRED_TYPE_ORDER.index(device_type), "")
    except ValueError:
        return (len(PREFERRED_TYPE_ORDER), _device_type_name(device_type).lower())


def _group_by_device_type(models: Iterable[str]) -> dict[str, list[str]]:
    """Group model identifiers by their family prefix."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for model in models:
        match = _IDENTIFIER.match(model)
        grouped[match.group(1) if match else OTHER_TYPE].append(model)

    return {
        device_type: sorted(type_models, key=_model_sort_key)
        for device_type, type_models in grouped.items()
    }


async def _async_fetch_device_types(hass: HomeAssistant) -> dict[str, list[str]]:
    """Fetch every device Apple currently publishes versions for, by family."""
    # gdmf.apple.com serves a certificate that does not validate against the
    # standard trust store, so verification has to be off for this host.
    session = async_get_clientsession(hass, verify_ssl=False)

    async with asyncio.timeout(10):
        async with session.get(API_URL) as response:
            response.raise_for_status()
            data = await response.json(content_type=None)

    models: set[str] = set()
    for asset_list in (data.get("PublicAssetSets") or {}).values():
        if isinstance(asset_list, list):
            for asset in asset_list:
                models.update(asset.get("SupportedDevices", []))

    return _group_by_device_type(models)


def _validated_input(data: dict[str, Any]) -> dict[str, str]:
    device_model = data["device_model"].strip()
    device_name = data["device_name"].strip()

    if not device_model:
        raise InvalidDeviceModel

    if not device_name:
        raise InvalidDeviceName

    return {"device_model": device_model, "device_name": device_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._models_by_type: dict[str, list[str]] = {}
        self._device_type: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which kind of Apple device to track."""
        if not self._models_by_type:
            try:
                self._models_by_type = await _async_fetch_device_types(self.hass)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                _LOGGER.warning(
                    "Could not fetch Apple's device list from %s (%s: %s); "
                    "falling back to entering a model identifier by hand",
                    API_URL,
                    type(err).__name__,
                    err,
                )
                return await self.async_step_manual()

        if not self._models_by_type:
            return await self.async_step_manual()

        if user_input is not None:
            self._device_type = user_input["device_type"]
            return await self.async_step_model()

        options = [
            selector.SelectOptionDict(
                value=device_type, label=_device_type_name(device_type)
            )
            for device_type in sorted(self._models_by_type, key=_device_type_sort_key)
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("device_type"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the exact model within the chosen device type."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if (entry := await self._async_create_entry(user_input, errors)) is not None:
                return entry

        device_type_name = _device_type_name(self._device_type)

        return self.async_show_form(
            step_id="model",
            data_schema=vol.Schema(
                {
                    vol.Required("device_model"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=model, label=_model_label(model)
                                )
                                for model in self._models_by_type.get(
                                    self._device_type, []
                                )
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    vol.Required("device_name", default=device_type_name): str,
                }
            ),
            errors=errors,
            description_placeholders={"device_type": device_type_name},
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter a model identifier by hand when Apple's list is unreachable."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if (entry := await self._async_create_entry(user_input, errors)) is not None:
                return entry

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("device_model"): str,
                    vol.Required("device_name"): str,
                }
            ),
            errors=errors,
        )

    async def _async_create_entry(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Create the entry, or fill in errors and return None."""
        try:
            info = _validated_input(user_input)
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
            return self.async_create_entry(title=info["device_name"], data=info)

        return None


class InvalidDeviceModel(HomeAssistantError):
    """Error to indicate invalid device model."""


class InvalidDeviceName(HomeAssistantError):
    """Error to indicate invalid device name."""
