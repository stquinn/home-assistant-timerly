from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
import logging
_LOGGER = logging.getLogger(__name__)
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        TimerlyStartButton(config_entry_id=entry.entry_id),
    ])

class TimerlyStartButton(ButtonEntity):
    def __init__(self, device_id, name, config_entry_id):
        self._attr_name = f"Clear Timers"
        self._attr_unique_id = f"timerly_clear_timer_button"
        self._attr_config_entry_id = config_entry_id

    async def async_press(self):
        # Optional: log or perform some minimal action
        _LOGGER.info("Timerly button pressed — dummy entity")


    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "Timerly")},
            manufacturer="Timerly",
            name="Timerly",
            sw_version="1.0.0",
            model="Timerly Visual Timer"
        )
