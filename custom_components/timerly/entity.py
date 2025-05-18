import logging
from datetime import datetime, timezone
from homeassistant.helpers.entity import Entity
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


class TimerlyTimerEntity(Entity):
    def __init__(self, name: str, device: TimerlyDevice, config_entry):
        self._device = device
        # self._name = device.name
        self._end_utc = None
        self._is_running = False
        self._selected = True
        self._last_props = {}
        self._available = False  # pessimistic default

        # ✅ Set Home Assistant Entity attributes
        self._attr_has_entity_name = True
        self._attr_name = device.name
        self._attr_icon = "mdi:bell-badge"
        self._attr_should_poll = True
        self._attr_unique_id = device.unique_id
        self._attr_config_entry_id = config_entry.entry_id  # ✅ Correct modern usage
        _LOGGER.info("Config Entry is  %s", id(config_entry))
        _LOGGER.info(
            "Entity Unique IDS is %s / %s",
            self._attr_unique_id,
            self._attr_config_entry_id,
        )

    @property
    def state(self):
        if not self._is_running or not self._end_utc:
            return "idle"
        remaining = (self._end_utc - datetime.now(timezone.utc)).total_seconds()
        return int(max(0, remaining))

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "Timerly")},
            manufacturer="Timerly",
            name=self._attr_name,
            sw_version="1.0.0",
            model="Timerly Visual Timer",
            suggested_area="self._name",
        )

    # @property
    # def extra_state_attributes(self):
    #     attrs = {
    #         "device": self._device.name,
    #         "selected": self._selected,
    #         "running": self._is_running,
    #         "end_time_utc": self._end_utc.isoformat() if self._end_utc else None,
    #         **self._last_props
    #     }

    #     if self._is_running and self._end_utc:
    #         now = datetime.now(timezone.utc)
    #         remaining_sec = int((self._end_utc - now).total_seconds())
    #         if remaining_sec > 0:
    #             mins, secs = divmod(remaining_sec, 60)
    #             hrs, mins = divmod(mins, 60)
    #             attrs["remaining_time"] = f"{hrs}h {mins}m {secs}s" if hrs > 0 else f"{mins}m {secs}s"
    #         else:
    #             attrs["remaining_time"] = "0s"
    #     else:
    #         attrs["remaining_time"] = "idle"

    #     return attrs

    def set_available(self, is_available: bool):
        if is_available != self._available:
            self._available = is_available
            state = "ONLINE" if is_available else "UNAVAILABLE"
            _LOGGER.info("🔄 %s is now %s", self._attr_name, state)
            self.schedule_update_ha_state()

    # @property
    # def available(self):
    #     return self._available

    # @property
    # def should_poll(self):
    #     return True

    async def async_added_to_hass(self):
        # Schedule a fast health check 2 seconds after startup
        async def quick_check():
            await asyncio.sleep(2)
            is_online, _ = await self.ping(timeout=1)  # fast, short timeout
            self.set_available(is_online)

        asyncio.create_task(quick_check())

    async def async_update(self):
        if not self.available:
            _LOGGER.debug("⏳ Skipping update — %s is unavailable", self.name)
            return
        import aiohttp

        try:
            url = f"http://{self._device.address}:{self._device.port}/timer"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=UPDATE_TIMEOUT_SEC) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._last_props = data.get("properties", {})
                        end_ms = data.get("endTime")
                        if end_ms:
                            self._end_utc = datetime.fromtimestamp(
                                end_ms / 1000, tz=timezone.utc
                            )
                            self._is_running = True
                        else:
                            self._is_running = False
                    if resp.status == 404:
                        self._is_running = False
                        self._last_props = {}
        except Exception as e:
            _LOGGER.warning("Failed to update Timerly %s: %s", self._device.name, e)
            self._is_running = False

    async def ping(self, timeout=PING_TIMEOUT_SEC) -> Tuple[bool, Optional[dict]]:
        """
        Try to reach the Timerly device and fetch its /timer data.

        Returns:
            (is_reachable: bool, timer_data: dict or None)
        """

        url = f"http://{self._device.address}:{self._device.port}/timer"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        _LOGGER.debug(
                            "👍 PING worked %s from Timerly %s",
                            resp.status,
                            self._device.name,
                        )
                        return True, data
                    elif resp.status == 404:
                        # Device reachable, but timer not running
                        _LOGGER.debug(
                            "👍 PING worked %s from Timerly %s",
                            resp.status,
                            self._device.name,
                        )
                        return True, {}
                    else:
                        _LOGGER.debug(
                            "❌ Unexpected HTTP status %s from Timerly %s",
                            resp.status,
                            self._device.name,
                        )
                        return False, None

        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            _LOGGER.debug(
                "❌ Failed to reach Timerly %s (%s:%d): %s",
                self._device.name,
                self._device.address,
                self._device.port,
                e,
            )
            return False, None


# async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
#     _LOGGER.info("✅ async_setup_entry called for Timerly sensor platform")
#     _LOGGER.info("🔍 hass is hass_ref? %s", hass is state.hass_ref)
#     # Store the add_entities callback so discovery can call us later
#     hass.data[DOMAIN]["add_entities"] = async_add_entities


#     async def delayed_try():
#         await asyncio.sleep(5)
#         _LOGGER.info("🔁 Retrying device scan after delay")
#         await try_add_new_entities(hass, async_add_entities)

#     hass.async_create_task(delayed_try())


# async def try_add_new_entities(hass: HomeAssistant, async_add_entities):
#     """Register new entities for newly discovered devices."""
#     devices = get_discovered_devices()
#     _LOGGER.info("📦 Found %d devices in discovered list", len(devices))
#     new_entities = []

#     for name, device in devices.items():
#         if device.unique_id in already_added:
#             continue
#         entity = TimerlyTimerEntity(device)
#         new_entities.append(entity)
#         already_added.add(device.unique_id)

#     if new_entities:
#         async_add_entities(new_entities)
#         _LOGGER.info("✅ Added %d new Timerly sensors", len(new_entities))
