"""Config flow for Zyxel integration."""
import logging

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.ha_zyxel.backend import NWA50AXClient
from .const import (
    CONF_DEVICE_TYPE,
    DEFAULT_DEVICE_TYPE,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_USERNAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
nr7101_logger = logging.getLogger("nr7101.nr7101")
nr7101_logger.setLevel(logging.WARNING)

DEVICE_CHOICES = [
    {"value": "generic", "label": "Generic Zyxel Device"},
    {"value": "ax7501-b0", "label": "AX7501-B0"},
    {"value": "fwa505", "label": "FWA505"},
    {"value": "fwa510", "label": "FWA510"},
    {"value": "fwa710-5g-v2", "label": "FWA710 5G V2"},
    {"value": "lte3202-m437", "label": "LTE3202-M437"},
    {"value": "lte7490-m904", "label": "LTE7490-M904"},
    {"value": "lte5398-m904", "label": "LTE5398-M904"},
    {"value": "nr5103e", "label": "NR5103E"},
    {"value": "nr5103v2", "label": "NR5103v2"},
    {"value": "nr5307", "label": "NR5307"},
    {"value": "nr7101", "label": "NR7101"},
    {"value": "nr7102", "label": "NR7102"},
    {"value": "nr7302", "label": "NR7302"},
    {"value": "nwa50ax", "label": "NWA50AX AP"},
    {"value": "vmg3625-t50b", "label": "VMG3625-T50B"},
    {"value": "vmg4005-b50a", "label": "VMG4005-B50A"},
    {"value": "vmg8825-t50", "label": "VMG8825-T50"},
]

SELECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_TYPE, default=DEFAULT_DEVICE_TYPE): SelectSelector(
            SelectSelectorConfig(options=DEVICE_CHOICES, mode=SelectSelectorMode.DROPDOWN)
        )
    }
)

NWA50AX_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

LEGACY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _normalize_host(host: str) -> str:
    if host.startswith("http://"):
        return host.removeprefix("http://")
    if host.startswith("https://"):
        return host.removeprefix("https://")
    return host


def _safe_error_message(err: Exception) -> str:
    message = str(err).strip()
    return message or err.__class__.__name__


def _try_candidates(host: str, device_type: str) -> list[str]:
    if device_type == "nwa50ax":
        return [f"http://{host}", f"https://{host}"]
    if host.startswith("http://") or host.startswith("https://"):
        return [host]
    return [f"https://{host}", f"http://{host}"]


async def _validate_connection(hass: core.HomeAssistant, data):
    device_type = data[CONF_DEVICE_TYPE]
    host = _normalize_host(data[CONF_HOST])

    _LOGGER.debug("Validating Zyxel connection to %s as %s (%s)", host, data[CONF_USERNAME], device_type)

    last_error = None
    for candidate in _try_candidates(host, device_type):
        _LOGGER.debug("Trying Zyxel connection candidate %s", candidate)
        try:
            if device_type == "nwa50ax":
                router = NWA50AXClient(candidate, data[CONF_USERNAME], data[CONF_PASSWORD])
                await hass.async_add_executor_job(router.login)
                status = await hass.async_add_executor_job(router.get_status)
                if not status:
                    raise UpdateFailed("zysh-cgi returned an empty status payload")
                device_name = await hass.async_add_executor_job(router.get_device_name, status)
            else:
                from nr7101 import nr7101

                router = await hass.async_add_executor_job(
                    nr7101.NR7101,
                    candidate,
                    data[CONF_USERNAME],
                    data[CONF_PASSWORD],
                    {"timeout": 15},
                )
                await hass.async_add_executor_job(router.connect)
                device_name = None

            data[CONF_HOST] = host if device_type == "nwa50ax" else candidate
            title = device_name or DEFAULT_NAME
            return {"title": title}
        except UpdateFailed as ex:
            last_error = ex
            _LOGGER.debug("Candidate %s returned empty data: %s", candidate, _safe_error_message(ex))
        except Exception as ex:  # pylint: disable=broad-except
            last_error = ex
            error_message = _safe_error_message(ex).lower()
            if "auth" in error_message or "login failed" in error_message:
                raise ConfigEntryAuthFailed from ex
            _LOGGER.debug("Candidate %s failed: %s", candidate, _safe_error_message(ex))

    raise last_error if last_error else Exception("Connection failed")


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._device_type = user_input[CONF_DEVICE_TYPE]
            if self._device_type == "nwa50ax":
                return await self.async_step_nwa50ax()
            return await self.async_step_legacy()
        return self.async_show_form(step_id="user", data_schema=SELECT_SCHEMA)

    async def async_step_nwa50ax(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {
                CONF_DEVICE_TYPE: "nwa50ax",
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                info = await _validate_connection(self.hass, data)
                self._validated_data = data
                self._validated_info = info
                return self.async_create_entry(title=info["title"], data=data)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("NWA50AX validation failed for %s", user_input[CONF_HOST])
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="nwa50ax", data_schema=NWA50AX_SCHEMA, errors=errors)

    async def async_step_legacy(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {
                CONF_DEVICE_TYPE: getattr(self, "_device_type", "legacy"),
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            try:
                info = await _validate_connection(self.hass, data)
                return self.async_create_entry(title=info["title"], data=data)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Legacy validation failed for %s", user_input[CONF_HOST])
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="legacy", data_schema=LEGACY_SCHEMA, errors=errors)


class ConnectionError(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
