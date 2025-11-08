from datetime import datetime
import logging

from zeroconf import ServiceBrowser, ServiceStateChange

from homeassistant.components import zeroconf
from homeassistant.components.zeroconf import async_get_instance
from homeassistant.core import HomeAssistant

from . import state
from .const import DOMAIN
from .coordinator import TimerlyCoordinator
from .entity import TimerlyTimerEntity
from .TimerlyDevice import TimerlyDevice

_LOGGER = logging.getLogger(__name__)


def get_discovered_devices():
    """Return the currently known Timerly devices, or empty if not available."""
    if state.hass_ref:
        return state.hass_ref.data.get(DOMAIN, {}).get("discovered", {})
    return {}


def add_discovered_device(device) -> None:
    """Store or update a discovered Timerly device in the global cache."""
    if not state.hass_ref:
        return

    hass = state.hass_ref
    hass.data.setdefault(DOMAIN, {})
    discovered = hass.data[DOMAIN].setdefault("discovered", {})

    now = datetime.utcnow()

    if device.name in discovered:
        entry = discovered[device.name]
        entry["last_seen"] = now
        _LOGGER.debug("🔄 Updated last_seen for %s", device.name)
    else:
        discovered[device.name] = {"device": device, "last_seen": now}
        _LOGGER.debug("📦 Added new Timerly device: %s", device.name)

    _LOGGER.debug("📦 Discovery cache now has %d devices", len(discovered))


async def mock_mdns(hass: HomeAssistant):
    """MNock mDNS discovery of Timerly devices and register callback."""
    _LOGGER.debug("🔁 Mock mDNS event: %s (%s)", "Office TV", "added")
    device = TimerlyDevice("Office TV", "192.168.10.37", "8181")
    add_discovered_device(device)
    _LOGGER.info(
        "📡 Discovered Timerly device: %s (%s:%s)",
        device.name,
        device.address,
        device.port,
    )

    # # ✅ Trigger entity registration
    if "component" in hass.data[DOMAIN]:
        _LOGGER.debug("📡 Passing off to try_add_new_entities")
        hass.loop.call_soon_threadsafe(
            lambda: hass.async_create_task(try_add_new_entities(hass))
        )


async def async_setup_mdns(hass: HomeAssistant):
    """Start mDNS discovery of Timerly devices and register callback."""
    zc = await async_get_instance(hass)

    # Ensure our integration dict is present
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("discovered", {})

    def service_handler(
        zeroconf: zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ) -> None:
        _LOGGER.debug("🔁 mDNS event: %s (%s)", name, state_change)

        if state_change is ServiceStateChange.Added:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                address = info.parsed_addresses()[0]
                port = info.port

                device = TimerlyDevice(name, address, port)

                add_discovered_device(device)
                _LOGGER.info(
                    "📡 Discovered Timerly device: %s (%s:%d)",
                    device.name,
                    address,
                    port,
                )

                # # ✅ Trigger entity registration
                if "async_add_entities" in hass.data[DOMAIN]:
                    _LOGGER.info("📡 Passing off to try_add_new_entities")
                    hass.loop.call_soon_threadsafe(
                        lambda: hass.async_create_task(try_add_new_entities(hass))
                    )
                else:
                    _LOGGER.debug("⚠️ async_add_entities not yet initialized")

        elif state_change is ServiceStateChange.Removed:
            device = TimerlyDevice(
                name, "", ""
            )  # JUST USING THE OBJECT TO GET THE PROPER NAME
            state.hass_ref.data[DOMAIN]["discovered"].pop(device.name, None)
            _LOGGER.info("❌ Timerly device removed: %s", device.name)

    return ServiceBrowser(zc, ["_tvtimer._tcp.local."], handlers=[service_handler])


async def try_add_new_entities(hass: HomeAssistant):
    discovered = get_discovered_devices()
    async_add_entities = hass.data[DOMAIN].get("async_add_entities")
    entry = hass.data[DOMAIN]["entry"]
    existing_entity_ids = hass.data[DOMAIN].setdefault("entities", [])
    coordinators = hass.data[DOMAIN].setdefault("coordinators", {})

    new_entities = []

    for name, device_info in list(discovered.items()):
        _LOGGER.info("🆕 Checking %s", name)

        device = device_info["device"] if isinstance(device_info, dict) else device_info

        # Reuse or create new coordinator
        if name not in coordinators:
            _LOGGER.info("🧠 Creating new coordinator for %s", name)
            coordinator = TimerlyCoordinator(hass, device, entry)
            try:
                await coordinator.async_config_entry_first_refresh()
                coordinators[name] = coordinator
            except Exception as err:
                _LOGGER.error("Failed to initialize coordinator for %s: %s", name, err)
                continue  # Skip this device and try the next one
        else:
            coordinator = coordinators[name]
            _LOGGER.debug("♻️ Reusing existing coordinator for %s", name)

        # Create entity
        entity = TimerlyTimerEntity(coordinator, entry)
        unique_id = entity.unique_id

        if unique_id not in existing_entity_ids:
            _LOGGER.info("🆕 Registering entity %s", unique_id)
            new_entities.append(entity)
            existing_entity_ids.append(unique_id)
        else:
            _LOGGER.debug("🧩 Entity already known: %s", unique_id)

    _LOGGER.debug("📦 Entity cache now has %d entities", len(existing_entity_ids))

    if new_entities:
        _LOGGER.info("🧱 Adding %d new Timerly entities", len(new_entities))
        async_add_entities(new_entities)
