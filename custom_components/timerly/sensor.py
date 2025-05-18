from datetime import datetime, timedelta
import logging
import time

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import state  # ✅ import the whole
from .const import DOMAIN
from .discovery import (
    add_discovered_device,
    async_setup_mdns,
    get_discovered_devices,
    mock_mdns,
)
from .state import try_add_new_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Store the callback so we can add entities later from discovery

    hass.data[DOMAIN]["discovered"] = {}
    hass.data[DOMAIN]["async_add_entities"] = async_add_entities
    hass.data[DOMAIN]["entry"] = entry

    # Run mDNS discovery
    await mock_mdns(hass)
    # discovery_browser = await async_setup_mdns(hass)

    # Add discovered devices as entities
    await try_add_new_entities(hass)

    async def refresh(_):
        await refresh_entity_availability(hass)

    unsub_interval = async_track_time_interval(hass, refresh, timedelta(seconds=60))

    # Save to hass.data for later cleanup
    hass.data[DOMAIN]["unsub_refresh"] = unsub_interval

    return True


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
        hass.data[DOMAIN].pop("component", None)
        hass.data[DOMAIN].pop("entry", None)
        hass.data[DOMAIN].pop("notify_services", None)
        hass.data[DOMAIN].pop["unsub_refresh", None]

    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict):
    async def post_to_hosts(hosts, endpoint: str, payload: dict):
        for host in hosts:
            try:
                uri = f"http://{host.address}:{host.port}/{endpoint}"
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
                _LOGGER.exception("Error sending %s to %s - %s", endpoint, host.name, e)

    def get_matching_devices(entity_ids):
        devices = get_discovered_devices().values()
        # Determine which hosts match the selected entity_ids
        if entity_ids:
            hosts = [
                h
                for h in devices
                if f"timerly.{h.name.lower().replace(' ', '_')}" in entity_ids
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
