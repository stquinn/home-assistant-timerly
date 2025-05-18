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

PLATFORMS = ["sensor"]

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
