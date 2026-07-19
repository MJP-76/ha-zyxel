"""Support for Zyxel device buttons."""
from __future__ import annotations

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _button_device_model(entry: ConfigEntry, coordinator) -> tuple[str, str | None]:
    """Return (model_name, sw_version) from coordinator data or entry config."""
    data = coordinator.data if coordinator else None
    if data:
        # coordinator data is a nested dict; find leaf values by key suffix.
        def _find(d, key):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == key and not isinstance(v, (dict, list)):
                        return v
                    found = _find(v, key)
                    if found is not None:
                        return found
            elif isinstance(d, list):
                for item in d:
                    found = _find(item, key)
                    if found is not None:
                        return found
            return None

        model = (
            _find(data, "ModelName")
            or _find(data, "ProductClass")
            or _find(data, "HardwareVersion")
        )
        sw_version = _find(data, "SoftwareVersion") or _find(data, "FirmwareVersion")
    else:
        model = None
        sw_version = None

    if not model:
        model = entry.data.get("device_type", "").upper().replace("_", "-") or entry.data.get("host", "")

    return model, sw_version


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Zyxel buttons."""
    router = hass.data[DOMAIN][entry.entry_id]["router"]
    coordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
    async_add_entities([ZyxelRebootButton(entry, router, coordinator)])


class ZyxelRebootButton(ButtonEntity):
    """Representation of a Zyxel reboot button."""

    def __init__(self, entry: ConfigEntry, router, coordinator) -> None:
        """Initialize the button."""
        self._router = router
        self._attr_unique_id = f"{entry.entry_id}_reboot"
        model, sw_version = _button_device_model(entry, coordinator)
        host = str(entry.data.get("host", "")).replace("http://", "").replace("https://", "")
        host = host.split("/", 1)[0]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel {host}" if host else f"Zyxel {model}",
            manufacturer="Zyxel",
            model=model,
            sw_version=sw_version,
        )
        self._attr_icon = "mdi:restart"
        self._attr_name = "Reboot Device"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Attempting to reboot Zyxel device")
        try:
            await self.hass.async_add_executor_job(self._router.reboot)
            _LOGGER.info("Zyxel device reboot command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to send reboot command: %s", err)
