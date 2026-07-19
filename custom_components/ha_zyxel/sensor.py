"""Support for Zyxel device sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.ha_zyxel.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_UPTIME_LEAF_KEYS = {"UpTime", "DSLUpTime", "ipoeConnectionUpTime", "pppoeConnectionUpTime"}
_WLAN_HINT_TOKENS = ("wlan", "wifi", "wireless", "ssid", "channel", "radio", "band")
_SENSITIVE_HINT_TOKENS = ("password", "passphrase", "psk", "wep", "key")
_EX3301_WIFI_ALLOWED_LEAFS = {
    "GuestSSIDEnable",
    "oneSsidEnable",
    "WiFiDriverVersion",
    "AutoChannelEnable",
    "Channel",
    "Enable",
    "IntfPath",
    "MACAddress",
    "ModeEnabled",
    "OperatingChannelBandwidth",
    "OperatingFrequencyBand",
    "OperatingStandards",
    "SSID",
    "WPSEnable",
    "X_ZYXEL_MainSSID",
    "X_ZYXEL_Rate",
    "band",
    "bandwidth",
    "BSSID",
    "channel",
    "downRate",
    "encryp",
    "extcha",
    "Index",
    "IsolationEnable",
    "MainSSID",
    "MaxAssociatedDevices",
    "ModesSupported",
}


def _format_uptime_dms(value: Any) -> str | None:
    """Format uptime seconds as <days>d <hours>h <minutes>m <seconds>s."""
    try:
        total_seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    if total_seconds < 0:
        return None
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


def _looks_like_wlan_path(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _WLAN_HINT_TOKENS)


def _is_sensitive_path(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_HINT_TOKENS)


def _is_ex3301_wifi_sensor_key(key: str) -> bool:
    """Return True for EX3301 WiFi telemetry keys we intentionally expose."""
    leaf = key.split(".")[-1]
    if leaf not in _EX3301_WIFI_ALLOWED_LEAFS:
        return False
    return (
        ".WiFiInfo." in key
        or key.startswith("DAL?oid=wlan.")
        or key.endswith(".GuestSSIDEnable")
        or key.endswith(".oneSsidEnable")
        or key.endswith(".WiFiDriverVersion")
    )


# Define some known sensor types for proper configuration
KNOWN_SENSORS = {
    "INTF_RSSI": {
        "name": "Cellular RSSI",
        "unit": "dBm",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_PhyCell_ID": {
        "name": "Physical Cell ID",
        "unit": None,
        "icon": "mdi:antenna",
        "device_class": None,
        "state_class": None,
    },
    "INTF_RSRP": {
        "name": "Cellular Reference Signal Received Power",
        "unit": "dBm",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_RSRQ": {
        "name": "Cellular Reference Signal Received Quality",
        "unit": "dB",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_SINR": {
        "name": "Cellular Signal-to-Noise Ratio",
        "unit": "dB",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_MCS": {
        "name": "Cellular Modulation and Coding Scheme",
        "unit": "",
        "icon": "mdi:signal",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_CQI": {
        "name": "Cellular Channel Quality Indicator",
        "unit": "",
        "icon": "mdi:signal",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_RI": {
        "name": "Cellular Rank Indicator",
        "unit": "",
        "icon": "mdi:signal",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "INTF_PMI": {
        "name": "Cellular Precoding Matrix Indicator",
        "unit": "",
        "icon": "mdi:signal",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "NSA_PhyCellID": {
        "name": "NSA Physical Cell ID",
        "unit": None,
        "icon": "mdi:antenna",
        "device_class": None,
        "state_class": None,
    },
    "NSA_RSRP": {
        "name": "NSA Reference Signal Received Power",
        "unit": "dBm",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "NSA_RSRQ": {
        "name": "NSA Reference Signal Received Quality",
        "unit": "dB",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "NSA_RSSI": {
        "name": "NSA Reference Signal Strength Indicator",
        "unit": "dBm",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "NSA_SINR": {
        "name": "NSA Signal-to-Noise Ratio",
        "unit": "dB",
        "icon": "mdi:signal",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "X_ZYXEL_TEMPERATURE_AMBIENT": {
        "name": "Ambient Temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "X_ZYXEL_TEMPERATURE_SDX": {
        "name": "SDX Temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "X_ZYXEL_TEMPERATURE_CPU0": {
        "name": "CPU Temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT
    },
    "BytesSent": {
        "name": "Bytes Sent",
        "unit": "B",
        "icon": "mdi:numeric-10-box",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "BytesReceived": {
        "name": "Bytes Received",
        "unit": "B",
        "icon": "mdi:numeric-10-box",
        "device_class": SensorDeviceClass.DATA_SIZE,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    # ── EX3301-T0: Device info (DAL?oid=cardpage_status.Object.0.DeviceInfo) ──
    "SoftwareVersion": {
        "name": "Firmware Version",
        "unit": None,
        "icon": "mdi:information-outline",
        "device_class": None,
        "state_class": None,
    },
    "HardwareVersion": {
        "name": "Hardware Version",
        "unit": None,
        "icon": "mdi:chip",
        "device_class": None,
        "state_class": None,
    },
    "ModelName": {
        "name": "Model",
        "unit": None,
        "icon": "mdi:router",
        "device_class": None,
        "state_class": None,
    },
    "SerialNumber": {
        "name": "Serial Number",
        "unit": None,
        "icon": "mdi:barcode",
        "device_class": None,
        "state_class": None,
    },
    "UpTime": {
        "name": "System Uptime",
        "unit": "s",
        "icon": "mdi:timer-outline",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    # ── EX3301-T0: DSL channel (DslChannelInfo.0) ──
    "DownstreamCurrRate": {
        "name": "DSL Downstream Rate",
        "unit": "kbit/s",
        "icon": "mdi:download-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "UpstreamCurrRate": {
        "name": "DSL Upstream Rate",
        "unit": "kbit/s",
        "icon": "mdi:upload-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "DSLUpTime": {
        "name": "DSL Uptime",
        "unit": "s",
        "icon": "mdi:timer-outline",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    # ── EX3301-T0: WAN summary (Object.0 level) ──
    "WanRate_RX": {
        "name": "WAN Receive Rate",
        "unit": "kbit/s",
        "icon": "mdi:download",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "WanRate_TX": {
        "name": "WAN Transmit Rate",
        "unit": "kbit/s",
        "icon": "mdi:upload",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "WanType": {
        "name": "WAN Type",
        "unit": None,
        "icon": "mdi:wan",
        "device_class": None,
        "state_class": None,
    },
    # ── EX3301-T0: WAN interface (WanLanInfo) ──
    "IPAddress": {
        "name": "IP Address",
        "unit": None,
        "icon": "mdi:ip-network",
        "device_class": None,
        "state_class": None,
    },
    "DefaultGateway": {
        # This field is a boolean: True = this interface is the active default route.
        "name": "Is Default Route",
        "unit": None,
        "icon": "mdi:routes",
        "device_class": None,
        "state_class": None,
    },
    "v4Gateway": {
        "name": "WAN Gateway IP",
        "unit": None,
        "icon": "mdi:router-network",
        "device_class": None,
        "state_class": None,
    },
    "v4dns": {
        "name": "DNS Server",
        "unit": None,
        "icon": "mdi:dns",
        "device_class": None,
        "state_class": None,
    },
    "pppConnectionStatus": {
        "name": "PPP Connection Status",
        "unit": None,
        "icon": "mdi:connection",
        "device_class": None,
        "state_class": None,
    },
    "EthConnectionStatus": {
        "name": "WAN Ethernet Status",
        "unit": None,
        "icon": "mdi:ethernet",
        "device_class": None,
        "state_class": None,
    },
    "ipoeConnectionUpTime": {
        "name": "IPoE Connection Uptime",
        "unit": "s",
        "icon": "mdi:timer-outline",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "pppoeConnectionUpTime": {
        "name": "PPPoE Connection Uptime",
        "unit": "s",
        "icon": "mdi:timer-outline",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "DHCPStatus": {
        "name": "DHCP Status",
        "unit": None,
        "icon": "mdi:ip",
        "device_class": None,
        "state_class": None,
    },
    # ── EX3301-T0: Temperature (GponStatsInfo) ──
    "Temperature": {
        "name": "Device Temperature",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # ── EX3301-T0: WLAN settings (DAL?oid=wlan) ──
    "WiFiSettings_wifikeepsame": {
        "name": "Private WiFi Keep Same",
        "unit": None,
        "icon": "mdi:wifi-sync",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_onessid_24g_switch": {
        "name": "Private WiFi 2.4G Enabled",
        "unit": None,
        "icon": "mdi:wifi",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_onessid_5g_switch": {
        "name": "Private WiFi 5G Enabled",
        "unit": None,
        "icon": "mdi:wifi",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_both_wifiname": {
        "name": "Private WiFi SSID",
        "unit": None,
        "icon": "mdi:wifi-settings",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_24g_randompw": {
        "name": "Private WiFi 2.4G Random Password",
        "unit": None,
        "icon": "mdi:key-variant",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_both_randompw": {
        "name": "Private WiFi Random Password",
        "unit": None,
        "icon": "mdi:key-variant",
        "device_class": None,
        "state_class": None,
    },
    "WiFiSettings_both_hidewifiname": {
        "name": "Private WiFi Hide SSID",
        "unit": None,
        "icon": "mdi:wifi-hidden",
        "device_class": None,
        "state_class": None,
    },
    "Guest_WiFiSettings_both_wifiname": {
        "name": "Guest WiFi SSID",
        "unit": None,
        "icon": "mdi:wifi-settings",
        "device_class": None,
        "state_class": None,
    },
    "Guest_WiFiSettings_both_hidewifiname": {
        "name": "Guest WiFi Hide SSID",
        "unit": None,
        "icon": "mdi:wifi-hidden",
        "device_class": None,
        "state_class": None,
    },
}


def _flatten_dict(d: dict, parent_key: str = "") -> dict:
    """Flatten a nested dictionary with dot notation for keys."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                list_key = f"{new_key}.{i}"
                if isinstance(item, dict):
                    items.extend(_flatten_dict(item, list_key).items())
                else:
                    items.append((list_key, item))
        else:
            items.append((new_key, v))
    return dict(items)


def _is_value_scalar(value: Any) -> bool:
    """Check if a value is a scalar (string, number, bool)."""
    return isinstance(value, (str, int, float, bool)) or value is None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Zyxel sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_type = hass.data[DOMAIN][entry.entry_id].get("device_type", "legacy")

    if not coordinator.data:
        _LOGGER.warning("Zyxel coordinator has no data at sensor setup — no sensors created")
        return

    flat = _flatten_dict(coordinator.data)
    # Log available keys at INFO level to help tune sensor mappings.
    _LOGGER.info(
        "Zyxel (%s) available data keys (%d total): %s",
        device_type,
        len(flat),
        sorted(flat.keys()),
    )
    if device_type == "ex3301_t0":
        wlan_keys = sorted(
            key for key in flat if _looks_like_wlan_path(key) and not _is_sensitive_path(key)
        )
        _LOGGER.info(
            "Zyxel (%s) WLAN-related data keys (%d total): %s",
            device_type,
            len(wlan_keys),
            wlan_keys,
        )
    sensors = []

    for key, value in flat.items():
        if not _is_value_scalar(value):
            continue

        # For EX3301, skip API fields that return null — these are firmware stubs
        # (GPON temperature, WAN rate reporting, inactive DSL channels) that will
        # never have useful data and only add clutter to the entity list.
        if device_type == "ex3301_t0" and value is None:
            continue

        leaf = key.split(".")[-1]
        sensor_config = KNOWN_SENSORS.get(leaf)

        if sensor_config:
            sensors.append(ConfiguredZyxelSensor(coordinator, entry, key, sensor_config))
        elif (
            device_type == "ex3301_t0"
            and _is_ex3301_wifi_sensor_key(key)
            and not _is_sensitive_path(key)
        ):
            sensors.append(GenericZyxelSensor(coordinator, entry, key))
        elif device_type != "ex3301_t0":
            # Generic sensors for legacy/NWA50AX — avoid flooding HA for EX3301
            # whose responses contain deeply-nested arrays with hundreds of fields.
            sensors.append(GenericZyxelSensor(coordinator, entry, key))

    # Remove stale entity registry entries that are no longer being created
    # (e.g. sensors suppressed by the null-value filter on this reload).
    current_unique_ids = {s.unique_id for s in sensors}
    ent_reg = er.async_get(hass)
    config_entries = list(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    for reg_entry in config_entries:
        if reg_entry.unique_id not in current_unique_ids:
            _LOGGER.debug("Removing stale entity %s", reg_entry.entity_id)
            ent_reg.async_remove(reg_entry.entity_id)

    # Migration cleanup: purge legacy generic EX3301 entities created by older
    # builds for the same physical device under a different config_entry_id.
    # These have entity IDs like sensor.zyxel_dal_oid_... and are no longer used.
    if device_type == "ex3301_t0":
        current_device_ids = {reg.device_id for reg in config_entries if reg.device_id}
        if current_device_ids:
            for reg_entry in list(ent_reg.entities.values()):
                if reg_entry.platform != DOMAIN:
                    continue
                if reg_entry.config_entry_id == entry.entry_id:
                    continue
                if reg_entry.device_id not in current_device_ids:
                    continue
                if reg_entry.entity_id.startswith("sensor.zyxel_dal_oid_"):
                    _LOGGER.debug(
                        "Removing legacy EX3301 generic entity from old entry: %s",
                        reg_entry.entity_id,
                    )
                    ent_reg.async_remove(reg_entry.entity_id)

    if not sensors:
        _LOGGER.warning(
            "Zyxel (%s): no sensors matched KNOWN_SENSORS — check the data keys log above",
            device_type,
        )
    else:
        _LOGGER.debug("Zyxel sensor setup: creating %d sensors for %s", len(sensors), device_type)
        async_add_entities(sensors)


class AbstractZyxelSensor(CoordinatorEntity, SensorEntity):
    """Base class for Zyxel device sensors."""

    def __init__(self, coordinator, entry: ConfigEntry, key: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        # Pre-populate immediately in case the coordinator already refreshed
        # before this sensor was registered (sensors are created after first_refresh).
        self._flat_state: dict[str, Any] = (
            _flatten_dict(coordinator.data) if coordinator.data else {}
        )
        safe_key = key.replace("?", "_").replace("=", "_").replace("&", "_").replace(" ", "_")
        self._attr_unique_id = f"{entry.entry_id}_{safe_key}"
        flat = self._flat_state
        # flat has full-path keys; search by leaf name (first match wins).
        leaf_vals: dict[str, Any] = {}
        for k, v in flat.items():
            leaf = k.split(".")[-1]
            if leaf not in leaf_vals:
                leaf_vals[leaf] = v
        model = (
            leaf_vals.get("ModelName")
            or leaf_vals.get("ProductClass")
            or leaf_vals.get("HardwareVersion")
            or entry.data.get("device_type", "").upper().replace("_", "-")
            or entry.data.get("host", "")
        )
        sw_version = leaf_vals.get("SoftwareVersion") or leaf_vals.get("FirmwareVersion")
        host = str(entry.data.get("host", "")).replace("http://", "").replace("https://", "")
        host = host.split("/", 1)[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel {host}" if host else f"Zyxel {model}",
            manufacturer="Zyxel",
            model=model,
            sw_version=sw_version,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh flat-state cache then write HA state."""
        if self.coordinator.data:
            self._flat_state = _flatten_dict(self.coordinator.data)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return self._key in self._flat_state

    def _get_value_from_path(self) -> Any:
        """Return the value from the cached flat state."""
        return self._flat_state[self._key]


class ConfiguredZyxelSensor(AbstractZyxelSensor):
    """Representation of a configured Zyxel sensor."""

    # Human-readable labels for known array-parent names.
    _PARENT_LABELS: dict[str, str] = {
        "DslChannelInfo": "DSL Ch",
        "WanLanInfo": "WAN",
        "LanInfo": "LAN",
        "LanPortInfo": "LAN Port",
        "dnsv4Server": "DNS",
        "IPv4Address": "",
        "Object": "",
    }

    @classmethod
    def _path_suffix(cls, key: str) -> str:
        """Return a disambiguating suffix for keys that appear at multiple array indices.

        Scans the path right-to-left for the first numeric component whose
        named parent maps to a non-empty label, skipping 'Object' and parents
        mapped to '' (e.g. IPv4Address) so we bubble up to a more meaningful
        ancestor like WanLanInfo.
        """
        parts = key.split(".")
        for i in range(len(parts) - 2, 0, -1):
            if parts[i].isdigit() and not parts[i - 1].isdigit():
                parent = parts[i - 1]
                if parent == "Object":
                    continue
                if parent == "WanLanInfo":
                    if parts[i] == "0":
                        return " (LAN)"
                    return f" (WAN {parts[i]})"
                prefix = cls._PARENT_LABELS.get(parent, parent)
                if prefix == "":
                    continue  # uninformative parent (e.g. IPv4Address) — keep scanning
                label = f"{prefix} {parts[i]}".strip()
                return f" ({label})" if label else ""
        return ""

    def __init__(self, coordinator, entry: ConfigEntry, key: str, config: dict):
        """Initialize the sensor."""
        super().__init__(coordinator, entry, key)
        self._config = config
        self._is_uptime = key.split(".")[-1] in _UPTIME_LEAF_KEYS
        self._attr_name = f"Zyxel {config['name']}{self._path_suffix(key)}"
        self._attr_native_unit_of_measurement = None if self._is_uptime else config["unit"]
        self._attr_icon = config["icon"]
        self._attr_device_class = None if self._is_uptime else config["device_class"]
        self._attr_state_class = None if self._is_uptime else config["state_class"]

    @property
    def state(self):
        """Return the state of the sensor, or None for empty strings."""
        try:
            value = self._get_value_from_path()
            if value == "":
                return None
            if self._is_uptime:
                return _format_uptime_dms(value)
            return value
        except (KeyError, AttributeError, TypeError, IndexError, ValueError):
            return None


class GenericZyxelSensor(AbstractZyxelSensor):
    """Representation of a generic Zyxel sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        name_parts = self._key.split(".")
        return f"Zyxel {'.'.join(name_parts)}"

    @property
    def state(self):
        """Return the state of the sensor, or None for empty strings."""
        try:
            value = self._get_value_from_path()
            return value if value != "" else None
        except (KeyError, AttributeError, TypeError, IndexError, ValueError):
            return None

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:router-wireless"
