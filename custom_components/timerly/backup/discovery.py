import logging
from homeassistant.core import HomeAssistant
from homeassistant.components.zeroconf import async_get_instance
from zeroconf import ServiceBrowser, ServiceStateChange
from homeassistant.components import zeroconf
from .const import DOMAIN
from . import state
from .state import try_add_new_entities
from datetime import datetime, timedelta
from homeassistant.helpers.device_registry import format_mac


_LOGGER = logging.getLogger(__name__)


class TimerlyDevice:
    def __init__(self, name: str, address: str, port: int):
        raw_name = name.removesuffix("._tvtimer._tcp.local.")
        clean_name = raw_name.removeprefix("Timerly ").strip()
        self.name = clean_name
        self.address = address
        self.port = port
        self.unique_id = f"timerly_{self.name.lower().replace('.', '_')}"


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
        _LOGGER.info("📦 Added new Timerly device: %s", device.name)

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
        _LOGGER.info("📡 Passing off to try_add_new_entities")
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
                if "component" in hass.data[DOMAIN]:
                    _LOGGER.info("📡 Passing off to try_add_new_entities")
                    hass.loop.call_soon_threadsafe(
                        lambda: hass.async_create_task(try_add_new_entities(hass))
                    )
                else:
                    _LOGGER.debug("⚠️ EntityComponent not yet initialized")

        elif state_change is ServiceStateChange.Removed:
            device = TimerlyDevice(
                name, "", ""
            )  # JUST USING THE OBJECT TO GET THE PROPER NAME
            state.hass_ref.data[DOMAIN]["discovered"].pop(device.name, None)
            _LOGGER.info("❌ Timerly device removed: %s", device.name)

    return ServiceBrowser(zc, ["_tvtimer._tcp.local."], handlers=[service_handler])
