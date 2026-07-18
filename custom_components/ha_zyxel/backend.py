"""Shared Zyxel backend helpers."""
from __future__ import annotations

import ast
import json
import logging
import re
from collections.abc import Mapping

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER = logging.getLogger(__name__)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


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
        self._session.verify = False

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
        self._session.verify = False
        page = self._session.get(f"{self.host}/", timeout=self.timeout)
        _LOGGER.debug("NWA50AX login page status=%s url=%s", page.status_code, page.url)
        if page.status_code >= 500:
            _LOGGER.debug("NWA50AX login page returned %s; continuing to POST login", page.status_code)
        csrf_token = (
            self._session.cookies.get("CSRFToken")
            or self._session.cookies.get("csrftok")
            or self._session.cookies.get("csrf")
        )
        payloads = [
            {"username": self.username, "pwd": self.password},
            {"username": self.username, "password": self.password},
        ]
        if csrf_token:
            for payload in payloads:
                payload["CSRFToken"] = csrf_token

        last_response = None
        for payload in payloads:
            resp = self._session.post(
                f"{self.host}/",
                data=payload,
                timeout=self.timeout,
                allow_redirects=True,
            )
            last_response = resp
            if resp.status_code >= 500:
                _LOGGER.debug(
                    "NWA50AX login POST returned %s; checking body/cookies instead of failing hard",
                    resp.status_code,
                )
            _LOGGER.debug("NWA50AX login response status=%s url=%s", resp.status_code, resp.url)
            if "login" in resp.text.lower() and "fail" in resp.text.lower():
                continue
            if "invalid" in resp.text.lower() and "password" in resp.text.lower():
                continue
            if self._session.cookies.get("authtok") or self._session.cookies.get("authtoken") or self._session.cookies.get("auth"):
                return

        _LOGGER.debug("NWA50AX login cookies after POST attempts: %s", self._session.cookies.get_dict())
        if last_response is not None and (
            "login" in last_response.text.lower() and "fail" in last_response.text.lower()
        ):
            raise UpdateFailed("Login failed")
        if last_response is not None and (
            "invalid" in last_response.text.lower() and "password" in last_response.text.lower()
        ):
            raise UpdateFailed("Login failed")
        raise UpdateFailed("Login session not established")

    def _post_cmds(self, cmds: list[str]) -> dict:
        from urllib.parse import quote_plus

        payload = "&".join(["filter=js2"] + [f"cmd={quote_plus(cmd)}" for cmd in cmds] + ["write=0"])
        resp = self._session.post(
            f"{self.host}/cgi-bin/zysh-cgi",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            _LOGGER.debug("NWA50AX zysh-cgi returned %s for %s", resp.status_code, cmds[0])
        return self._parse_zysh_response(resp.text)

    @staticmethod
    def _parse_zysh_response(text: str) -> dict:
        stripped = text.strip()
        lowered = stripped.lower()
        if "login" in lowered and ("password" in lowered or "invalid" in lowered):
            raise UpdateFailed("Login failed")
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                parsed_json = json.loads(stripped)
            except json.JSONDecodeError:
                parsed_json = None
            else:
                if isinstance(parsed_json, dict):
                    return parsed_json

        result: dict = {}
        pattern = re.compile(
            r"var\s+([A-Za-z0-9_]+)\s*=\s*\[(.*?)\];\s*var\s+errno\1\s*=\s*(\d+);\s*var\s+errmsg\1\s*=\s*(['\"])(.*?)\4;?",
            re.S,
        )
        for match in pattern.finditer(text):
            data_name = match.group(1)
            raw = match.group(2)
            parsed = ast.literal_eval("[" + raw + "]")
            errno = int(match.group(3))
            errmsg = match.group(5)
            if errno != 0:
                raise UpdateFailed(errmsg or f"zysh-cgi command {data_name} failed with errno {errno}")
            result[data_name] = parsed
        if not result:
            var_pattern = re.compile(r"var\s+([A-Za-z0-9_]+)\s*=\s*(\[[^\n;]*\]|'[^']*'|\"[^\"]*\"|\d+)\s*;")
            for match in var_pattern.finditer(text):
                name = match.group(1)
                value = match.group(2)
                if not name.startswith("zyshdata"):
                    continue
                try:
                    result[name] = ast.literal_eval(value)
                except (SyntaxError, ValueError):
                    continue
        if not result:
            raise UpdateFailed(f"zysh-cgi returned no usable data: {text[:120]}")
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

    @staticmethod
    def get_device_name(status: Mapping) -> str | None:
        """Return the best device name we can find in zysh status data."""
        candidates = (
            "fqdn",
            "_fqdn",
            "hostname",
            "_hostname",
            "system_name",
            "_system_name",
            "device_name",
            "_device_name",
        )
        for key in candidates:
            value = status.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        for value in status.values():
            if isinstance(value, Mapping):
                nested = NWA50AXClient.get_device_name(value)
                if nested:
                    return nested
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, Mapping):
                        nested = NWA50AXClient.get_device_name(item)
                        if nested:
                            return nested
        return None

    def reboot(self) -> None:
        self._post_cmds(["reboot"])


def normalize_zysh_status(data: Mapping) -> dict:
    """Flatten the zysh response into a status dict."""
    normalized: dict = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, list) and value:
            item = value[0]
            if isinstance(item, dict):
                normalized[key] = item
                for subkey, subvalue in item.items():
                    if subkey.startswith("_"):
                        normalized[subkey.lstrip("_")] = subvalue
            else:
                normalized[key] = value
    return normalized
