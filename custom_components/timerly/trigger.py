async def async_get_triggers(hass, config_entry):
    return [
        {
            "platform": "event",
            "event_type": "timerly_timer_state_changed",
            "event_data": {},  # empty means any timer
            "integration": "timerly",
        }
    ]
