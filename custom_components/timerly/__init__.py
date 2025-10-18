from datetime import datetime
import logging
import time

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

# from homeassistant.config_entries import async_unload_platforms
from homeassistant.util import dt as dt_util

from . import state  # ✅ import the whole
from .const import DOMAIN
from .discovery import get_discovered_devices
from .TimerlyDevice import TimerlyDevice

_LOGGER = logging.getLogger(__name__)

# PLATFORMS = ["binary_sensor", "button"]
PLATFORMS = ["binary_sensor", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug("✅ async_setup_entry called for Timerly")

    # Init first
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["entry"] = entry
    state.hass_ref = hass

    # Then forward to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup(hass: HomeAssistant, config: dict):
    async def post_to_hosts(hosts, endpoint: str, payload: dict):
        for host in hosts:
            try:
                uri = (
                    f"http://{host['device'].address}:{host['device'].port}/{endpoint}"
                )
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(uri, json=payload, timeout=5) as response,
                ):
                    if response.status != 200:
                        _LOGGER.error(
                            "Timerly %s failed for %s: %s",
                            uri,
                            host["device"].name,
                            response.status,
                        )
            except Exception as e:
                _LOGGER.exception(
                    "Error sending %s to %s - %s", endpoint, host["device"].name, e
                )

    def get_matching_devices(entity_ids):
        devices = get_discovered_devices().values()
        # Determine which hosts match the selected entity_ids
        if entity_ids:
            entity_id_values = (
                entity_ids.values() if isinstance(entity_ids, dict) else entity_ids
            )
            hosts = [
                h
                for h in devices
                if f"binary_sensor.{h['device'].name.lower().replace(' ', '_')}_timer"
                in (entity_id_values)
            ]
        else:
            hosts = devices

        return hosts

    async def handle_refresh_all(call):
        entity_registry = async_get_entity_registry(hass)

        # Get only binary_sensors from the 'timerly' integration
        binary_sensor_ids = [
            entry.entity_id
            for entry in entity_registry.entities.values()
            if entry.platform == DOMAIN and entry.entity_id.startswith("binary_sensor.")
        ]

        platforms = async_get_platforms(hass, DOMAIN)
        if not platforms:
            _LOGGER.error("No platforms found for domain '%s'", DOMAIN)
            return

        for entity_id in binary_sensor_ids:
            entity = None
            for platform in platforms:
                entity = platform.entities.get(entity_id)
                if entity:
                    break  # found it!

            if entity:
                await entity.async_update()
                entity.async_write_ha_state()
                _LOGGER.debug("✅ Refreshed %s", entity_id)
            else:
                _LOGGER.warning(
                    "⚠️ Entity %s not found in any timerly platform", entity_id
                )

    async def handle_start_timer(call: ServiceCall):
        seconds = call.data.get("seconds", -1)
        minutes = call.data.get("minutes", -1)
        endTimeString = call.data.get("endTime")
        if endTimeString:
            now = dt_util.now()
            today = now.date()
            parsedTime = datetime.strptime(endTimeString, "%H:%M:%S").time()
            endTime = dt_util.as_local(datetime.combine(today, parsedTime))

            delta = endTime - now
            seconds = int(delta.total_seconds())
            if seconds < 0:
                _LOGGER.error(
                    "Time specified is in the past - Specified %s, and its now %s",
                    endTimeString,
                    now.time(),
                )
                raise Exception("Must specify an endtime in the future")

            _LOGGER.debug(
                "Endtime  parameter specified (%s) and is overriding seconds. Seconds is now %s",
                endTime,
                seconds,
            )

        if minutes > 0:
            seconds = minutes * 60
            _LOGGER.debug(
                "Minutes parameter specified (%s) and is overriding seconds. Seconds is now %s",
                minutes,
                seconds,
            )
        if seconds <= 0:
            _LOGGER.error(
                "Neither a time in the future, minutes or seconds were specified"
            )
            raise Exception("Must specify one of endTime, minutes or seconds")

        duration = call.data.get("duration", seconds)
        position = call.data.get("position", "BottomRight")
        duration = call.data.get("duration", seconds)
        voice = call.data.get("voice", True)
        type_ = call.data.get("type", "DEFAULT")
        payload = {
            "seconds": seconds,
            "position": position,
            "duration": duration,
            "voice": voice,
            "type": type_,
            "startTime": int(time.time() * 1000),
        }

        try:
            await post_to_hosts(
                get_matching_devices(call.data.get("entity_id", [])), "timer", payload
            )
            await handle_refresh_all(None)
        except Exception as e:
            _LOGGER.exception("Error starting timer: %s", e)

    async def handle_cancel_all(call: ServiceCall):
        await post_to_hosts(
            get_matching_devices(call.data.get("entity_id", [])), "cancel", {}
        )
        await handle_refresh_all(None)

    async def handle_doorbell(call: ServiceCall):
        seconds = call.data.get("duration", 30)
        video = call.data.get("video", "")
        payload = {"duration": seconds, "videoUri": video}
        await post_to_hosts(
            get_matching_devices(call.data.get("entity_id", [])), "doorbell", payload
        )

    async def handle_dismiss(call: ServiceCall):
        name = call.data.get("name", "")
        await post_to_hosts(
            get_matching_devices(call.data.get("entity_id", [])),
            "cancel",
            {"name": name},
        )

    hass.services.async_register(DOMAIN, "start_timer", handle_start_timer)
    hass.services.async_register(DOMAIN, "cancel_all", handle_cancel_all)
    hass.services.async_register(DOMAIN, "doorbell", handle_doorbell)
    hass.services.async_register(DOMAIN, "dismiss", handle_dismiss)
    hass.services.async_register(DOMAIN, "refresh_all", handle_refresh_all)

    return True
