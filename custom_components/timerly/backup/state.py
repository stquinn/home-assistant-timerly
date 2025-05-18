from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

# Stores shared global Home Assistant instance
hass_ref: HomeAssistant | None = None  # ✅ global shared hass


async def try_add_new_entities(hass: HomeAssistant):
    from .sensor import TimerlyTimerEntity
    from .discovery import get_discovered_devices

    discovered = get_discovered_devices()
    async_add_entities: AddEntitiesCallback = hass.data[DOMAIN]["async_add_entities"]
    _LOGGER.info("🆕 About to get Registry")
    registry = async_get_entity_registry(hass)
    _LOGGER.info("🆕 Got Registry")
    existing_entity_ids = {
        e.entity_id for e in registry.entities.values() if e.domain == DOMAIN
    }

    new_entities = []

    for name, device_info in discovered.items():
        _LOGGER.info("🆕 Checking %s", name)
        device = device_info["device"] if isinstance(device_info, dict) else device_info
        entity_id = f"{DOMAIN}.{name.lower().replace(' ', '_')}"
        if entity_id not in existing_entity_ids:
            _LOGGER.info("🆕 New Device %s", name)
            entity = TimerlyTimerEntity(name, device)
            new_entities.append(entity)
            hass.data[DOMAIN].setdefault("entities", []).append(entity)
        else:
            _LOGGER.info("🆕 Old Device %s", name)

    if new_entities:
        _LOGGER.info("🆕 Adding %d new Timerly entities", len(new_entities))
        async_add_entities(new_entities)
