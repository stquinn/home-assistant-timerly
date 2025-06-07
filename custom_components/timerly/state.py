import logging

from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)

# Stores shared global Home Assistant instance
hass_ref: HomeAssistant | None = None  # ✅ global shared hass
