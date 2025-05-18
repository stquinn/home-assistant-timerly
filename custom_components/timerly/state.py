from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

# Stores shared global Home Assistant instance
hass_ref: HomeAssistant | None = None  # ✅ global shared hass


async def try_add_new_entities(hass: HomeAssistant):
    from .entity import TimerlyTimerEntity
    from .discovery import get_discovered_devices

    discovered = get_discovered_devices()
    async_add_entities = hass.data[DOMAIN].get("async_add_entities")
    entry = hass.data[DOMAIN]["entry"]
    _LOGGER.info("🆕 About to get Registry")
    registry = async_get_entity_registry(hass)
    _LOGGER.info("🆕 Got Registry")
    existing_entity_ids = {
        e.entity_id for e in registry.entities.values() if e.platform == DOMAIN
    }

    new_entities = []

    for name, device_info in discovered.items():
        _LOGGER.info("🆕 Checking %s", name)
        device = device_info["device"] if isinstance(device_info, dict) else device_info
        entity_id = f"binary_sensor.{name.lower().replace(' ', '_')}_timer"
        entity = TimerlyTimerEntity(name, device, entry)
        hass.data[DOMAIN].setdefault("entities", []).append(entity)
        # I know this is wrong and gives an error but seems to be the only way to get it all wired up
        # I am not doing this registration properly - needs huge simplification
        new_entities.append(entity) 
        if entity_id not in existing_entity_ids:
            _LOGGER.info("🆕 New Device %s", name)
        else:
            _LOGGER.info("🆕 Old Device %s", name)
    _LOGGER.debug(
        "📦 Entity cache now has %d entities",
        len(hass.data[DOMAIN].setdefault("entities", [])),
    )
    if new_entities:
        _LOGGER.info("🆕 Adding %d new Timerly entities", len(new_entities))
        async_add_entities(new_entities)
