import logging
from http import HTTPStatus

from homeassistant.components.notify import BaseNotificationService
from homeassistant.core import HomeAssistant
from .discovery import get_discovered_devices
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

ATTR_POSITION = "position"
ATTR_DURATION = "duration"
ATTR_NAME = "name"
ATTR_TYPE = "type"
ATTR_WIDTH = "width"
ATTR_HEIGHT = "height"
ATTR_TEXT = "text"
ATTR_TITLE = "title"
ATTR_VOICE_MESSAGE_ENABLED = "voiceMessageEnabled"
ATTR_VOICE_MESSAGE = "voiceMessage"
ATTR_VOICE_MESSAGE_DELAY = "voiceMessageDelay"
ATTR_FLASH_ANIMATION_ENABLED = "flashAnimationEnabled"
ATTR_FLASH_ANIMATION_REPEAT_COUNT = "flashAnimationRepeatCount"
ATTR_FLASH_ANIMATION_DELAY = "flashAnimationInitialDelay"
ATTR_NOTIFICATION_SOUND_ENABLED = "notificationSoundEnabled"
ATTR_NOTIFICATION_SOUND = "notificationSound"
ATTR_NOTIFICATION_SOUND_NAME = "notificationSoundName"

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the timerly platform."""
    _LOGGER.info("🆕 In Notify.async_setup_entry")


# ✅ Home Assistant calls this to get your service
async def async_get_service(hass: HomeAssistant, config, discovery_info=None):
    service_name = config.get("name", "timerly")
    service = TimerlyNotificationService()

    # Save service name so we can unregister it later
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("notify_services", []).append(service_name)

    _LOGGER.info("🆕 Registered Timerly Notify service: %s", service_name)
    return service


class TimerlyNotificationService(BaseNotificationService):
    def __init__(self):
        self._session = aiohttp.ClientSession()

    async def async_send_message(self, message="", **kwargs):
        title = kwargs.get("title", "")
        data = kwargs.get("data", {})

        payload = {
            ATTR_NAME: data.get(ATTR_NAME, ""),
            ATTR_TYPE: data.get(ATTR_TYPE, ""),
            ATTR_POSITION: data.get(ATTR_POSITION, "BottomRight"),
            ATTR_TITLE: title,
            ATTR_TEXT: message,
            ATTR_DURATION: data.get(ATTR_DURATION, "15"),
            ATTR_VOICE_MESSAGE_ENABLED: data.get(ATTR_VOICE_MESSAGE_ENABLED, "false"),
            ATTR_VOICE_MESSAGE: data.get(ATTR_VOICE_MESSAGE, ""),
            ATTR_VOICE_MESSAGE_DELAY: data.get(ATTR_VOICE_MESSAGE_DELAY, ""),
            ATTR_FLASH_ANIMATION_ENABLED: data.get(
                ATTR_FLASH_ANIMATION_ENABLED, "false"
            ),
            ATTR_FLASH_ANIMATION_REPEAT_COUNT: data.get(
                ATTR_FLASH_ANIMATION_REPEAT_COUNT, ""
            ),
            ATTR_FLASH_ANIMATION_DELAY: data.get(ATTR_FLASH_ANIMATION_DELAY, ""),
            ATTR_NOTIFICATION_SOUND_ENABLED: data.get(
                ATTR_NOTIFICATION_SOUND_ENABLED, "false"
            ),
            ATTR_NOTIFICATION_SOUND: data.get(ATTR_NOTIFICATION_SOUND, ""),
            ATTR_NOTIFICATION_SOUND_NAME: data.get(ATTR_NOTIFICATION_SOUND_NAME, ""),
        }

        await self.post_to_all_hosts("alert", payload)

    async def post_to_all_hosts(self, path: str, payload: dict):
        devices = get_discovered_devices()
        for host in devices.values():
            try:
                uri = f"http://{host.address}:{host.port}/{path}"
                _LOGGER.info("📨 Sending Timerly message to %s at %s", host.name, uri)
                async with self._session.post(uri, json=payload, timeout=5) as response:
                    if response.status != HTTPStatus.OK:
                        _LOGGER.error("❌ Timerly failed: %s", await response.text())
            except Exception as e:
                _LOGGER.exception("💥 Error sending to Timerly %s: %s", host.name, e)
