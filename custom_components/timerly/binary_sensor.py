from datetime import datetime, timedelta
import logging
import time

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

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
PLATFORMS = ["sensor", "button"]


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

    return True


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

    # # Stop the interval task
    # if "unsub_refresh" in hass.data[DOMAIN]:
    #     hass.data[DOMAIN]["unsub_refresh"]()
    #     _LOGGER.info("🛑 Stopped Timerly refresh interval")

    if unload_ok:
        hass.data[DOMAIN].pop("component", None)
        hass.data[DOMAIN].pop("entry", None)
        hass.data[DOMAIN].pop("notify_services", None)
        hass.data[DOMAIN].pop["unsub_refresh", None]

    return unload_ok
