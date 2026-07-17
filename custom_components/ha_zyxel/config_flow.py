"""Config flow for Zyxel integration."""
import logging

import voluptuous as vol
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DEFAULT_DEVICE_TYPE, DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN, CONF_DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)

# Block excessive nr7101 debug logging
nr7101_logger = logging.getLogger("nr7101.nr7101")
nr7101_logger.setLevel(logging.WARNING)

from nr7101 import nr7101

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_DEVICE_TYPE, default=DEFAULT_DEVICE_TYPE
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    {"value": "nwa50ax", "label": "NWA50AX AP"},
                    {"value": "legacy", "label": "Legacy Zyxel device"},
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


def _normalize_host(host: str) -> str:
    """Return the host without a URL scheme."""
    if host.startswith("http://"):
        return host.removeprefix("http://")
    if host.startswith("https://"):
        return host.removeprefix("https://")
    return host


def _candidate_hosts(host: str, device_type: str) -> list[str]:
    """Return connection candidates for the selected device type."""
    if device_type == "nwa50ax":
        return [f"http://{host}", f"https://{host}"]
    if host.startswith("http://") or host.startswith("https://"):
        return [host]
    return [f"https://{host}", f"http://{host}"]


async def validate_input(hass: core.HomeAssistant, data):
    """Validate that the user input allows us to connect."""

    try:
        host = _normalize_host(data[CONF_HOST])
        device_type = data[CONF_DEVICE_TYPE]
        _LOGGER.debug(
            "Validating Zyxel connection to %s as %s (%s)",
            host,
            data[CONF_USERNAME],
            device_type,
        )
        last_error = None
        for candidate in _candidate_hosts(host, device_type):
            _LOGGER.debug("Trying Zyxel connection candidate %s", candidate)
            router = await hass.async_add_executor_job(
                nr7101.NR7101,
                candidate,
                data[CONF_USERNAME],
                data[CONF_PASSWORD],
                {"timeout": 15},
            )

            try:
                if device_type == "nwa50ax":
                    await hass.async_add_executor_job(router.login)
                    await hass.async_add_executor_job(router.get_status)
                else:
                    await hass.async_add_executor_job(router.connect)
                data[CONF_HOST] = host
                _LOGGER.debug("Zyxel connection validation succeeded for %s", candidate)
                break
            except Exception as ex:  # pylint: disable=broad-except
                last_error = ex
                _LOGGER.debug("Candidate %s failed", candidate, exc_info=True)
        else:
            raise last_error if last_error else Exception("Connection failed")
    except Exception as ex:
        _LOGGER.exception("Unable to connect to Zyxel device at %s", data[CONF_HOST])
        raise ConnectionError from ex

    return {"title": f"Zyxel device: ({data[CONF_HOST]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zyxel devices."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        success = False

        if user_input is not None:
            host = _normalize_host(user_input[CONF_HOST])
            user_input[CONF_HOST] = host

            # sanitize entry
            try:
                info = await validate_input(self.hass, user_input)
                success = True
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "First attempt failed for %s", user_input[CONF_HOST], exc_info=True
                )
                errors["base"] = "cannot_connect"

            if not success:
                errors["base"] = "cannot_connect"

        if success:
            return self.async_create_entry(title=info["title"], data=user_input)
        else:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )


class ConnectionError(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
