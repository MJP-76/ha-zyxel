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


async def validate_input(hass: core.HomeAssistant, data):
    """Validate that the user input allows us to connect."""

    try:
        device_type = data[CONF_DEVICE_TYPE]
        _LOGGER.debug(
            "Validating Zyxel connection to %s as %s (%s)",
            data[CONF_HOST],
            data[CONF_USERNAME],
            device_type,
        )
        # Create router instance and test connection
        router = await hass.async_add_executor_job(
            nr7101.NR7101,
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            {"timeout": 15},
        )

        if device_type == "nwa50ax":
            _LOGGER.debug("Attempting Zyxel login for %s", data[CONF_HOST])
            await hass.async_add_executor_job(router.login)
            _LOGGER.debug("Login succeeded, probing status for %s", data[CONF_HOST])
            await hass.async_add_executor_job(router.get_status)
        else:
            _LOGGER.debug("Attempting legacy Zyxel connectivity check for %s", data[CONF_HOST])
            await hass.async_add_executor_job(router.connect)
        _LOGGER.debug("Zyxel connection validation succeeded for %s", data[CONF_HOST])



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
            host = user_input[CONF_HOST]

            # sanitize entry
            if not host.startswith("http://") and not host.startswith("https://"):
                host = f"https://{host}"
                user_input[CONF_HOST] = host

            try:
                info = await validate_input(self.hass, user_input)
                success = True
            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.debug(
                    "First attempt failed for %s", user_input[CONF_HOST], exc_info=True
                )
                errors["base"] = "cannot_connect"

            if not success and "https" not in user_input["host"]:
                _LOGGER.info("User specified http but it failed, trying https...")
                user_input["host"] = user_input["host"].replace("http://", "https://")
                try:
                    info = await validate_input(self.hass, user_input)
                    success = True
                except ConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception as e:  # pylint: disable=broad-except
                    _LOGGER.debug(
                        "Second attempt failed for %s", user_input[CONF_HOST], exc_info=True
                    )
                    errors["base"] = "unknown"

        if success:
            return self.async_create_entry(title=info["title"], data=user_input)
        else:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )


class ConnectionError(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
