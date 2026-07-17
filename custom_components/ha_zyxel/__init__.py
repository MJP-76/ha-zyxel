"""The Zyxel integration."""
import asyncio
import logging
from datetime import timedelta

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.ha_zyxel.const import (
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Block excessive nr7101 debug logging
nr7101_logger = logging.getLogger("nr7101.nr7101")
nr7101_logger.setLevel(logging.WARNING)

from nr7101 import nr7101

PLATFORMS = ["sensor", "button"]


def _merge_status_data(router) -> dict:
    """Collect the most useful data objects exposed by a Zyxel device."""
    data = {}

    # Try the generic dashboard OID first; APs expose this while cellular
    # routers still use the legacy cellular/traffic objects below.
    status = router.get_json_object("status")
    if status:
        data.update(status)

    # Preserve the richer legacy data when the device supports it.
    try:
        cellular = router.get_json_object("cellwan_status")
    except Exception:  # pylint: disable=broad-except
        cellular = None
    if cellular:
        data["cellular"] = cellular

    try:
        traffic_obj = router.get_json_object("Traffic_Status")
    except Exception:  # pylint: disable=broad-except
        traffic_obj = None
    if traffic_obj and "ipIface" in traffic_obj and "ipIfaceSt" in traffic_obj:
        traffic = {}
        for iface, iface_st in zip(traffic_obj["ipIface"], traffic_obj["ipIfaceSt"]):
            if isinstance(iface, dict) and "X_ZYXEL_IfName" in iface:
                traffic[iface["X_ZYXEL_IfName"]] = iface_st
        if traffic:
            data["traffic"] = traffic

    try:
        wifi = router.get_json_object("wlan")
    except Exception:  # pylint: disable=broad-except
        wifi = None
    if wifi:
        data["wifi"] = wifi

    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zyxel integration from a config entry."""


    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    device_type = entry.data.get(CONF_DEVICE_TYPE, "legacy")
    if device_type == "nwa50ax" and not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    try:
        _LOGGER.debug("Creating Zyxel client for %s", host)
        router = await hass.async_add_executor_job(
            nr7101.NR7101, host, username, password, {"timeout": 15}
        )
        if device_type == "nwa50ax":
            _LOGGER.debug("Logging into Zyxel NWA50AX at %s", host)
            await hass.async_add_executor_job(router.login)
    except Exception as ex:
        _LOGGER.exception("Could not create Zyxel client for %s", host)
        raise ConfigEntryNotReady from ex

    async def async_update_data():
        """Fetch data from the router."""
        try:
            async with async_timeout.timeout(15):
                def get_all_data():
                    data = _merge_status_data(router)

                    if not data:
                        legacy_data = router.get_status()
                        if legacy_data:
                            data = legacy_data

                    if not data:
                        raise UpdateFailed("No data received from router")

                    return data

                return await hass.async_add_executor_job(get_all_data)
        except asyncio.TimeoutError:
            router._session_valid = False
            raise UpdateFailed("Router data fetch timed out")
        except Exception as err:
            router._session_valid = False
            _LOGGER.exception("Error communicating with Zyxel device at %s", host)
            raise UpdateFailed(f"Error communicating with router: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "router": router,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
