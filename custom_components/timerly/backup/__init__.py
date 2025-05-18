from __future__ import annotations

import logging
import time

import aiohttp

from custom_components.timerly import state  # ✅ import the whole
from custom_components.timerly.discovery import get_discovered_devices
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import Platform


# from homeassistant.config_entries import async_unload_platforms


_LOGGER = logging.getLogger(__name__)
from custom_components.timerly.const import DOMAIN

PLATFORMS = [Platform.SENSOR, Platform.NOTIFY]


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    _LOGGER.info("✅ async_setup_entry called for Timerly")

    state.hass_ref = hass
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["discovered"] = {}

    await hass.config_entries.async_forward_entry_setups(config, PLATFORMS)
    return True


# def setup(hass: HomeAssistant, config: ConfigType) -> bool:
#     """Your controller/hub specific code."""
#     _LOGGER.info("✅ setup called for Timerly")
#     # Data that you want to share with your platforms
#     hass.data[DOMAIN] = {"temperature": 23}

#     hass.helpers.discovery.load_platform(DOMAIN, DOMAIN, {}, config)

#     return True


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

    async def handle_set_selected(call: ServiceCall):
        target = call.data.get("target")
        selected = call.data.get("selected", True)
        entity_id = f"timerly_timer_{target.lower()}"
        entity = entity_registry.get(entity_id)
        if entity:
            entity.set_selected(selected)
        else:
            _LOGGER.warning("Timerly entity not found: %s", entity_id)

    hass.services.async_register(DOMAIN, "start_timer", handle_start_timer)
    hass.services.async_register(DOMAIN, "cancel_all", handle_cancel_all)
    hass.services.async_register(DOMAIN, "doorbell", handle_doorbell)
    hass.services.async_register(DOMAIN, "dismiss", handle_dismiss)
    hass.services.async_register(DOMAIN, "set_selected", handle_set_selected)

    return True
