from datetime import UTC, datetime

from custom_components.timerly.const import DOMAIN
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TimerlyCoordinator


class TimerlyTimerEntity(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator: TimerlyCoordinator, config_entry):
        super().__init__(coordinator)
        self._attr_name = "Timer"
        self._attr_icon = "mdi:bell-badge"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_unique_id = coordinator.device.unique_id
        self._attr_config_entry_id = config_entry.entry_id
        self._attr_has_entity_name = True

    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data.get(
            "available"
        )

    @property
    def is_on(self):
        return self.coordinator.is_running(self.coordinator.data.get("end_ms"))

    @property
    def extra_state_attributes(self):
        props = self.coordinator.data.get("properties", {})
        end_ms = self.coordinator.data.get("end_ms")
        start_ms = props.get("startTime")

        attrs = {
            "end_ms": self.coordinator.data.get("end_ms"),
            "device": self.coordinator.device.name,
            "start_time_utc": None,
            "end_time_utc": None,
            "remaining_time": "idle",
            **props,
        }

        if start_ms:
            start_utc = datetime.fromtimestamp(start_ms / 1000, tz=UTC)
            attrs["start_time_utc"] = start_utc.isoformat()
        if end_ms:
            end_utc = datetime.fromtimestamp(end_ms / 1000, tz=UTC)
            attrs["end_time_utc"] = end_utc.isoformat()

            remaining = int((end_utc - datetime.now(UTC)).total_seconds())
            if remaining > 0:
                mins, secs = divmod(remaining, 60)
                hrs, mins = divmod(mins, 60)
                attrs["remaining_time"] = (
                    f"{hrs}h {mins}m {secs}s" if hrs > 0 else f"{mins}m {secs}s"
                )
            else:
                attrs["remaining_time"] = "0s"

        return attrs

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.device.name}")},
            manufacturer="Timerly",
            name=self.coordinator.device.name,
            sw_version="1.0.0",
            model="Timerly Visual Timer",
        )
