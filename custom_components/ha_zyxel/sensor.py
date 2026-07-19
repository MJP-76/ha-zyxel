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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.ha_zyxel.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

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
    # EX3301-T0 DSL router keys (from CardInfo / DAL?oid=cardpage_status)
    "WAN_IP": {
        "name": "WAN IP Address",
        "unit": None,
        "icon": "mdi:ip-network",
        "device_class": None,
        "state_class": None,
    },
    "WAN_Status": {
        "name": "WAN Status",
        "unit": None,
        "icon": "mdi:wan",
        "device_class": None,
        "state_class": None,
    },
    "DSL_Speed_Down": {
        "name": "DSL Downstream Sync Rate",
        "unit": "kbit/s",
        "icon": "mdi:download-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "DSL_Speed_Up": {
        "name": "DSL Upstream Sync Rate",
        "unit": "kbit/s",
        "icon": "mdi:upload-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "DSL_DS_Actual_Rate": {
        "name": "DSL Downstream Actual Rate",
        "unit": "kbit/s",
        "icon": "mdi:download-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "DSL_US_Actual_Rate": {
        "name": "DSL Upstream Actual Rate",
        "unit": "kbit/s",
        "icon": "mdi:upload-network",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "FW_Version": {
        "name": "Firmware Version",
        "unit": None,
        "icon": "mdi:information-outline",
        "device_class": None,
        "state_class": None,
    },
    "ConnectedDevices": {
        "name": "Connected Devices",
        "unit": None,
        "icon": "mdi:devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "loginAccount": {
        "name": "Logged In Account",
        "unit": None,
        "icon": "mdi:account",
        "device_class": None,
        "state_class": None,
    },
    "loginLevel": {
        "name": "Account Level",
        "unit": None,
        "icon": "mdi:account-key",
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

    if not coordinator.data:
        _LOGGER.warning("Zyxel coordinator has no data at sensor setup — no sensors created")
        return

    flat = _flatten_dict(coordinator.data)
    _LOGGER.debug("Zyxel sensor setup: coordinator data keys = %s", list(flat.keys()))
    sensors = []

    for key, value in flat.items():
        if not _is_value_scalar(value):
            continue

        sensor_config = KNOWN_SENSORS.get(key.split(".")[-1], None)

        if sensor_config:
            sensors.append(ConfiguredZyxelSensor(coordinator, entry, key, sensor_config))
        else:
            sensors.append(GenericZyxelSensor(coordinator, entry, key))

    _LOGGER.debug("Zyxel sensor setup: creating %d sensors", len(sensors))
    if sensors:
        async_add_entities(sensors)


class AbstractZyxelSensor(CoordinatorEntity, SensorEntity):
    """Base class for Zyxel device sensors."""

    def __init__(self, coordinator, entry: ConfigEntry, key: str):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._flat_state: dict[str, Any] = {}
        safe_key = key.replace("?", "_").replace("=", "_").replace("&", "_").replace(" ", "_")
        self._attr_unique_id = f"{entry.entry_id}_{safe_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
            model="",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        return self._key in self._flat_state

    def _get_value_from_path(self) -> Any:
        """Get a value from the cached flattened coordinator data."""
        self._flat_state = _flatten_dict(self.coordinator.data)
        return self._flat_state[self._key]


class ConfiguredZyxelSensor(AbstractZyxelSensor):
    """Representation of a configured Zyxel sensor."""

    def __init__(self, coordinator, entry: ConfigEntry, key: str, config: dict):
        """Initialize the sensor."""
        super().__init__(coordinator, entry, key)
        self._config = config
        self._attr_name = f"Zyxel {config['name']}"
        self._attr_native_unit_of_measurement = config["unit"]
        self._attr_icon = config["icon"]
        self._attr_device_class = config["device_class"]
        self._attr_state_class = config["state_class"]

    @property
    def state(self):
        """Return the state of the sensor."""
        try:
            return self._get_value_from_path()
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
        """Return the state of the sensor."""
        try:
            return self._get_value_from_path()
        except (KeyError, AttributeError, TypeError, IndexError, ValueError):
            return None

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:router-wireless"
