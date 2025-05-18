import logging
import aiohttp
import time
from datetime import datetime
from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

# from homeassistant.config_entries import async_unload_platforms
from homeassistant.helpers.event import async_track_time_interval

from .discovery import async_setup_mdns, mock_mdns
from .discovery import get_discovered_devices, add_discovered_device

from . import state  # ✅ import the whole
from .state import try_add_new_entities


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# PLATFORMS = ["binary_sensor", "button"]
PLATFORMS = ["binary_sensor"]

# at the module level
discovery_browser = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    global discovery_browser
    _LOGGER.info("✅ async_setup_entry called for Timerly")

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
                async with aiohttp.ClientSession() as session:
                    async with session.post(uri, json=payload, timeout=5) as response:
                        if response.status != 200:
                            _LOGGER.error(
                                "Timerly %s failed for %s: %s",
                                uri,
                                host.name,
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

    async def handle_start_timer(call: ServiceCall):
        seconds = call.data["seconds"]
        name = call.data.get("name", "custom-timer")
        position = call.data.get("position", "BottomRight")
        duration = call.data.get("duration", seconds)
        voice = call.data.get("voice", True)
        roar = call.data.get("roar", False)
        tick = call.data.get("tick", False)
        type_ = call.data.get("type", "DEFAULT")
        entity_ids = call.data.get("entity_id", [])

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
        except Exception as e:
            _LOGGER.exception("Error starting timer: %s", e)

    async def handle_cancel_all(call: ServiceCall):
        await post_to_hosts(
            get_matching_devices(call.data.get("entity_id", [])), "cancel", {}
        )

    async def handle_doorbell(call: ServiceCall):
        await post_to_hosts(
            get_matching_devices(call.data.get("entity_id", [])), "doorbell", {}
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

    return True
