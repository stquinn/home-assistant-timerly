from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN

TRANSLATION_KEY = "timer_type"

OPTIONS = [
    "DEFAULT",
    "BEDTIME",
    "SCHOOL",
    "CODING",
    "RUGBY",
    "SCREEN_BREAK",
    "SWITCH_TIME",
    "CAR",
]


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TimerlyTimerTypeSelect(hass, entry.entry_id)])


class TimerlyTimerTypeSelect(SelectEntity):
    """Global integration-level select for the default timer type."""

    def __init__(self, hass, entry_id: str) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._store = Store(hass, 1, f"{DOMAIN}_{entry_id}_timer_type")

        self._attr_name = "Timerly Timer Type"
        self._attr_unique_id = f"{entry_id}_timer_type"
        self._attr_options = OPTIONS
        self._attr_current_option = "DEFAULT"
        self._attr_translation_key = TRANSLATION_KEY
        self._attr_entity_category = (
            EntityCategory.CONFIG
        )  # Optional: groups it under "Settings" in UI

    async def async_added_to_hass(self) -> None:
        """Restore the previous selection from storage."""
        data = await self._store.async_load()
        if data:
            value = data.get("option")
            if value in OPTIONS:
                self._attr_current_option = value
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Handle user selection."""
        if option in OPTIONS:
            self._attr_current_option = option
            self.async_write_ha_state()
            await self._store.async_save({"option": option})
