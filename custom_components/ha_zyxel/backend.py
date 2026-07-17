"""Shared Zyxel backend helpers."""
from __future__ import annotations

import ast
import logging
import re
from collections.abc import Mapping

import requests
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)


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
        if "invalid" in resp.text.lower() and "password" in resp.text.lower():
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
            r"var zyshdata(\d+)\s*=\s*\[(.*?)\];\s*var errno\1\s*=\s*(\d+);\s*var errmsg\1\s*=\s*'([^']*)';",
            re.S,
        )
        for match in pattern.finditer(text):
            data_idx = int(match.group(1))
            raw = match.group(2)
            parsed = ast.literal_eval("[" + raw + "]")
            errno = int(match.group(3))
            errmsg = match.group(4)
            if errno != 0:
                raise UpdateFailed(errmsg or f"zysh-cgi command {data_idx} failed with errno {errno}")
            result[f"zyshdata{data_idx}"] = parsed
        if not result:
            raise UpdateFailed("zysh-cgi returned no usable data")
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
        normalized = normalize_zysh_status(data)
        if not normalized:
            raise UpdateFailed("zysh-cgi returned an empty status payload")
        return normalized

    def reboot(self) -> None:
        self._post_cmds(["reboot"])


def normalize_zysh_status(data: Mapping) -> dict:
    """Flatten the zysh response into a status dict."""
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
