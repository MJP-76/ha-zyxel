"""The Zyxel integration."""
import asyncio
import logging
from collections.abc import Mapping
from datetime import timedelta

import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.ha_zyxel.backend import NWA50AXClient, normalize_zysh_status
from custom_components.ha_zyxel.const import (
    CONF_CREATE_DASHBOARD,
    CONF_DEVICE_TYPE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

from nr7101 import nr7101

PLATFORMS = ["sensor", "button"]
ZyXEL_DASHBOARD_ID = "zyxel-nebula"
ZyXEL_DASHBOARD_STORAGE_KEY = f"lovelace.{ZyXEL_DASHBOARD_ID}"
ZyXEL_DASHBOARDS_STORAGE_KEY = "lovelace_dashboards"
ZyXEL_DASHBOARD_URL_PATH = "zyxel-nebula"
ZYXEL_ENTITY_PREFIXES = ("sensor.", "button.")


def _zyxel_dashboard_config(title: str, entity_rows: list[str]) -> dict:
    return {
        "config": {
            "title": title,
            "views": [
                {
                    "title": "Overview",
                    "path": ZyXEL_DASHBOARD_URL_PATH,
                    "icon": "mdi:cloud",
                    "theme": "Backend-selected",
                    "type": "sections",
                    "sections": [
                        {
                            "type": "grid",
                            "cards": [
                                {
                                    "type": "heading",
                                    "heading": title,
                                    "heading_style": "title",
                                    "icon": "mdi:cloud-outline",
                                },
                            ],
                        },
                        {
                            "type": "grid",
                            "cards": [
                                {
                                    "type": "entities",
                                    "title": "All Zyxel devices",
                                    "entities": entity_rows,
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    }


def _dashboard_entity_entries(hass: HomeAssistant) -> list[str]:
    registry = er.async_get(hass)
    entries: list[str] = []
    for entity in registry.entities.values():
        if entity.platform != DOMAIN:
            continue
        if not entity.entity_id.startswith(ZYXEL_ENTITY_PREFIXES):
            continue
        entries.append(entity.entity_id)
    return sorted(entries)


async def _ensure_zyxel_dashboard(hass: HomeAssistant, title: str) -> None:
    """Create a storage-backed dashboard if it does not already exist."""
    dashboards_store = Store[dict[str, object]](hass, 1, ZyXEL_DASHBOARDS_STORAGE_KEY)
    dashboards_data = await dashboards_store.async_load() or {"items": []}
    items = dashboards_data.setdefault("items", [])
    if not any(item.get("id") == ZyXEL_DASHBOARD_ID for item in items):
        items.append(
            {
                "id": ZyXEL_DASHBOARD_ID,
                "title": title,
                "url_path": ZyXEL_DASHBOARD_URL_PATH,
                "icon": "mdi:cloud",
                "show_in_sidebar": True,
                "require_admin": False,
                "mode": "storage",
            }
        )
        await dashboards_store.async_save(dashboards_data)

    dashboard_store = Store[dict[str, object]](hass, 1, ZyXEL_DASHBOARD_STORAGE_KEY)
    await dashboard_store.async_save(
        _zyxel_dashboard_config(title, _dashboard_entity_entries(hass))
    )


def _flatten_value(value, parent_key: str = "") -> dict:
    items = {}
    if isinstance(value, Mapping):
        for k, v in value.items():
            key = f"{parent_key}.{k}" if parent_key else str(k)
            items.update(_flatten_value(v, key))
    elif isinstance(value, list):
        for idx, v in enumerate(value):
            key = f"{parent_key}.{idx}" if parent_key else str(idx)
            items.update(_flatten_value(v, key))
    else:
        items[parent_key] = value
    return items


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
    create_dashboard = entry.data.get(CONF_CREATE_DASHBOARD, False)
    if device_type == "nwa50ax" and not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    try:
        _LOGGER.debug("Creating Zyxel client for %s", host)
        if device_type == "nwa50ax":
            router = NWA50AXClient(host, username, password)
            await hass.async_add_executor_job(router.login)
            await hass.async_add_executor_job(router.get_status)
        else:
            router = await hass.async_add_executor_job(
                nr7101.NR7101, host, username, password, {"timeout": 15}
            )
    except Exception as ex:
        _LOGGER.exception("Could not create Zyxel client for %s", host)
        raise ConfigEntryNotReady from ex

    async def async_update_data():
        """Fetch data from the router."""
        try:
            async with async_timeout.timeout(15):
                def get_all_data():
                    data = router.get_status() if device_type == "nwa50ax" else _merge_status_data(router)
                    if not data and device_type != "nwa50ax":
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

    if device_type == "nwa50ax" and create_dashboard:
        await _ensure_zyxel_dashboard(hass, entry.title)

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
