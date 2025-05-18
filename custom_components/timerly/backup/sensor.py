import asyncio
from datetime import UTC, datetime, timedelta
import logging

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity

# from homeassistant.config_entries import async_unload_platforms
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, PING_TIMEOUT_SEC, UPDATE_TIMEOUT_SEC
from .discovery import TimerlyDevice, add_discovered_device, async_setup_mdns, mock_mdns
from .state import try_add_new_entities
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

already_added = set()

entity_registry = {}
# at the module level
discovery_browser = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the timerly platform."""

    # add_entities([ExampleSensor()])
    hass.data[DOMAIN]["async_add_entities"] = AddEntitiesCallback

    global discovery_browser
    # Run mDNS discovery
    discovery_browser = await async_setup_mdns(hass)
    await mock_mdns(hass)

    # Add discovered devices as entities
    await try_add_new_entities(hass)

    async def refresh(_):
        await refresh_entity_availability(hass)

    unsub_interval = async_track_time_interval(hass, refresh, timedelta(seconds=60))

    # Save to hass.data for later cleanup
    hass.data[DOMAIN]["unsub_refresh"] = unsub_interval


async def refresh_entity_availability(hass: HomeAssistant):
    _LOGGER.debug("🔄 Refreshing Timerly entity availability")
    for entity in hass.data[DOMAIN].get("entities", []):
        _LOGGER.debug("🔄 Refreshing %s", entity.name)
        is_online, data = await entity.ping()
        entity.set_available(is_online)
        if is_online:
            add_discovered_device(entity._device)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("♻️ Unloading Timerly config entry")

    global discovery_browser

    if discovery_browser:
        _LOGGER.info("🛑 Cancelling mDNS discovery for Timerly")
        discovery_browser.cancel()
        discovery_browser = None

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # ✅ Also remove notify services if any
    for service_name in hass.data.get(DOMAIN, {}).get("notify_services", []):
        hass.services.async_remove("notify", service_name)
        _LOGGER.info("🗑️ Unregistered notify.%s", service_name)

    # Stop the interval task
    if "unsub_refresh" in hass.data[DOMAIN]:
        hass.data[DOMAIN]["unsub_refresh"]()
        _LOGGER.info("🛑 Stopped Timerly refresh interval")

    if unload_ok:
        hass.data[DOMAIN].pop("AddEntitiesCallback", None)
        hass.data[DOMAIN].pop("notify_services", None)
        hass.data[DOMAIN].pop["unsub_refresh", None]

    return True


class TimerlyTimerEntity(Entity):
    def __init__(self, name: str, device: TimerlyDevice):
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
        _LOGGER.info("Entity Unique IDS is %s", self._attr_unique_id)

    @property
    def state(self):
        if not self._is_running or not self._end_utc:
            return "idle"
        remaining = (self._end_utc - datetime.now(UTC)).total_seconds()
        return int(max(0, remaining))

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Timerly",
            name=self._name,
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
            _LOGGER.info("🔄 %s is now %s", self._name, state)
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
                                end_ms / 1000, tz=UTC
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

    async def ping(self, timeout=PING_TIMEOUT_SEC) -> tuple[bool, dict | None]:
        """Try to reach the Timerly device and fetch its /timer data.

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
                    if resp.status == 404:
                        # Device reachable, but timer not running
                        _LOGGER.debug(
                            "👍 PING worked %s from Timerly %s",
                            resp.status,
                            self._device.name,
                        )
                        return True, {}
                    _LOGGER.debug(
                        "❌ Unexpected HTTP status %s from Timerly %s",
                        resp.status,
                        self._device.name,
                    )
                    return False, None

        except (TimeoutError, aiohttp.ClientError, OSError) as e:
            _LOGGER.debug(
                "❌ Failed to reach Timerly %s (%s:%d): %s",
                self._device.name,
                self._device.address,
                self._device.port,
                e,
            )
            return False, None
