import logging
from datetime import datetime, timezone
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN, PING_TIMEOUT_SEC, UPDATE_TIMEOUT_SEC
from .discovery import get_discovered_devices
import aiohttp
import asyncio
from . import state
from .discovery import TimerlyDevice
from typing import Optional, Tuple

_LOGGER = logging.getLogger(__name__)

already_added = set()

entity_registry = {}


class TimerlyTimerEntity(BinarySensorEntity):
    def __init__(self, name: str, device: TimerlyDevice, config_entry):
        self._device = device
        # self._name = device.name
        self._end_utc = None
        self._start_utc = None
        self._is_running = False
        self._selected = True
        self._last_props = {}
        self._available = False  # pessimistic default

        # ✅ Set Home Assistant Entity attributes
        self._attr_has_entity_name = True
        self._attr_name = "Timer"
        self._attr_icon = "mdi:bell-badge"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_should_poll = True
        self._attr_unique_id = f"timerly_{config_entry.entry_id}_{device.name}_timer"
        self._attr_config_entry_id = config_entry.entry_id  # ✅ Correct modern usage
        _LOGGER.debug("Config Entry is  %s", id(config_entry))
        _LOGGER.debug(
            "Entity Unique IDS is %s / %s",
            self._attr_unique_id,
            self._attr_config_entry_id,
        )

    @property
    def state(self):
        if not self._is_running or not self._end_utc:
            return "off"
        return "on"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._attr_config_entry_id}_{self._device.name}")},
            manufacturer="Timerly",
            name=f"{self._device.name}",
            sw_version="1.0.0",
            model="Timerly Visual Timer",
        )

    @property
    def extra_state_attributes(self):
        attrs = {
            "device": self._device.name,
            "selected": self._selected,
            "running": self._is_running,
            "start_time_utc": self._start_utc.isoformat() if self._start_utc else None,
            "end_time_utc": self._end_utc.isoformat() if self._end_utc else None,
            **self._last_props,
        }

        if self._is_running and self._end_utc:
            now = datetime.now(timezone.utc)
            remaining_sec = int((self._end_utc - now).total_seconds())
            if remaining_sec > 0:
                mins, secs = divmod(remaining_sec, 60)
                hrs, mins = divmod(mins, 60)
                attrs["remaining_time"] = (
                    f"{hrs}h {mins}m {secs}s" if hrs > 0 else f"{mins}m {secs}s"
                )
            else:
                attrs["remaining_time"] = "0s"
        else:
            attrs["remaining_time"] = "idle"

        return attrs

    def set_available(self, is_available: bool):
        if is_available != self._available:
            self._available = is_available
            msg = "ONLINE" if is_available else "UNAVAILABLE"
            _LOGGER.info("🔄 %s %s is now %s", self._device.name, self._attr_name, msg)
            self.schedule_update_ha_state(True)

    @property
    def available(self):
        return self._available

    @property
    def should_poll(self):
        return True

    # async def async_added_to_hass(self):
    # Schedule a fast health check 2 seconds after startup
    # async def quick_check():
    #     await asyncio.sleep(30)
    #     is_online, _ = await self.async_update()  # fast, short timeout
    #     self.set_available(is_online)

    # asyncio.create_task(quick_check())

    async def async_update(self):
        # if not self._available:
        #     _LOGGER.debug("⏳ Skipping update — %s is unavailable", self.name)
        #     return
        import aiohttp

        try:
            url = f"http://{self._device.address}:{self._device.port}/timer"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=UPDATE_TIMEOUT_SEC) as resp:
                    if resp.status == 200:
                        _LOGGER.debug(
                            "👍 PING worked %s from Timerly %s",
                            resp.status,
                            self._device.name,
                        )
                        data = await resp.json()
                        self._last_props = data.get("properties", {})
                        end_ms = data.get("endTime")
                        start_ms = self._last_props.get("startTime")
                        if start_ms:
                            self._start_utc = datetime.fromtimestamp(
                                start_ms / 1000, tz=timezone.utc
                            )
                        if end_ms:
                            self._end_utc = datetime.fromtimestamp(
                                end_ms / 1000, tz=timezone.utc
                            )
                            self._is_running = True
                        else:
                            self._is_running = False
                        self.set_available(True)
                    if resp.status == 404:
                        self._is_running = False
                        self._last_props = {}
                        self.set_available(True)
                    _LOGGER.debug(
                        "👍 PING worked %s from Timerly %s",
                        resp.status,
                        self._device.name,
                    )
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            if self._available:  # only log the first time
                _LOGGER.warning(
                    "❌ Failed to reach Timerly %s (%s:%s): %s",
                    self._device.name,
                    self._device.address,
                    self._device.port,
                    e,
                )
            self.set_available(False)
        except Exception as e:
            _LOGGER.warning("Failed to update Timerly %s: %s", self._device.name, e)
            self._is_running = False
