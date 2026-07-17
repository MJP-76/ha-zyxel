"""The Zyxel integration."""
import asyncio
import json
import logging
import re
import ast
from collections.abc import Mapping
from datetime import timedelta

import async_timeout
import requests
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

from nr7101 import nr7101

PLATFORMS = ["sensor", "button"]


class NWA50AXClient:
    """Minimal Zyxel NWA50AX client using the zysh CGI endpoint."""

    def __init__(self, host: str, username: str, password: str, timeout: int = 15) -> None:
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.host,
                "Referer": f"{self.host}/",
            }
        )

    def login(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.host,
                "Referer": f"{self.host}/",
            }
        )
        page = self._session.get(f"{self.host}/", timeout=self.timeout)
        page.raise_for_status()
        _LOGGER.debug("NWA50AX login page status=%s url=%s", page.status_code, page.url)
        resp = self._session.post(
            f"{self.host}/",
            data={"username": self.username, "pwd": self.password},
            timeout=self.timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
        _LOGGER.debug(
            "NWA50AX login response status=%s url=%s body=%s",
            resp.status_code,
            resp.url,
            resp.text[:500],
        )
        if "login" in resp.text.lower() and "fail" in resp.text.lower():
            raise UpdateFailed("Login failed")

    def _post_cmds(self, cmds: list[str]) -> dict:
        from urllib.parse import quote_plus

        payload = "&".join(["filter=js2"] + [f"cmd={quote_plus(cmd)}" for cmd in cmds] + ["write=0"])
        resp = self._session.post(
            f"{self.host}/cgi-bin/zysh-cgi",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        _LOGGER.debug("NWA50AX cmd response for %s: %s", cmds[0], resp.text[:500])
        return self._parse_zysh_response(resp.text)

    @staticmethod
    def _parse_zysh_response(text: str) -> dict:
        result: dict = {}
        pattern = re.compile(
            r"var zyshdata(\d+)=\[(.*?)\];\nvar errno\1=(\d+);\nvar errmsg\1='([^']*)';",
            re.S,
        )
        for match in pattern.finditer(text):
            data_idx = int(match.group(1))
            raw = match.group(2)
            parsed = ast.literal_eval("[" + raw + "]")
            result[f"zyshdata{data_idx}"] = parsed
        return result

    def get_status(self) -> dict:
        data = self._post_cmds(
            [
                "show language setting",
                "show users current",
                "show version",
                "show hybrid-mode",
                "show manager vlan",
                "show wlan all",
                "show wireless-hal current channel",
                "show wireless-hal statistic",
                "show nebula ethernet status",
                "show nebula internet status",
                "show nebula cloud status",
                "show nebula claim status",
                "show netconf proxy status",
                "show fqdn",
                "show mac",
                "show serial-number",
                "show netconf status",
                "show nebula ntp status",
                "show nebula cloud-gui status",
            ]
        )
        return self._normalize_status(data)

    @staticmethod
    def _normalize_status(data: Mapping) -> dict:
        normalized: dict = {}
        for key, value in data.items():
            if key.startswith("zyshdata") and isinstance(value, list) and value:
                item = value[0]
                if isinstance(item, dict):
                    normalized[key] = item
                    for subkey, subvalue in item.items():
                        if subkey.startswith("_"):
                            normalized[subkey.lstrip("_")] = subvalue
                else:
                    normalized[key] = value
        return normalized

    def reboot(self) -> None:
        self._post_cmds(["reboot"])


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
    if device_type == "nwa50ax" and not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    try:
        _LOGGER.debug("Creating Zyxel client for %s", host)
        if device_type == "nwa50ax":
            router = NWA50AXClient(host, username, password)
            await hass.async_add_executor_job(router.login)
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

                    if not data:
                        if device_type != "nwa50ax":
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
