from datetime import UTC, datetime, timedelta
import logging

import aiohttp

from custom_components.timerly.const import (
    SCHEDULER_JOB_END_TIME_REFRESH,
    UPDATE_TIMEOUT_SEC,
)
from custom_components.timerly.TimerlyDevice import TimerlyDevice
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class TimerlyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, device: TimerlyDevice):
        super().__init__(
            hass,
            _LOGGER,
            name=f"Timerly ({device.name})",
            update_interval=timedelta(seconds=15),
        )
        self.device = device
        self._session = async_get_clientsession(hass)
        self._scheduler = NamedRefreshScheduler(hass, label=device.name)
        self._scheduled_end_time: datetime | None = None
        self._consecutive_failures = 0
        self._failure_threshold = 2  # or 3 for h

    async def _fetch_timer_data(self):
        try:
            url = f"http://{self.device.address}:{self.device.port}/timer"
            async with (
                self._session.get(url, timeout=UPDATE_TIMEOUT_SEC) as resp,
            ):
                if resp.status == 200:
                    newData = await resp.json()
                    _LOGGER.debug("✅ %s: %s", self.device.name, newData)
                    _LOGGER.debug("Headers: %s", resp.headers)
                    return {
                        "available": True,
                        "properties": newData.get("properties", {}),
                        "end_ms": newData.get("endTime"),
                    }
                if resp.status == 404:
                    return {
                        "available": True,
                        "properties": {},
                        "end_ms": None,
                    }
                raise UpdateFailed(f"Unexpected HTTP {resp.status}")
        except (TimeoutError, aiohttp.ClientError, OSError) as e:
            _LOGGER.warning("❌ %s unreachable: %s", self.device.name, e)
            raise UpdateFailed(e) from e

    async def _async_update_data(self):
        try:
            newData = await self._fetch_timer_data()
            # Reset failure count on success
            self._consecutive_failures = 0
            end_ms = newData.get("end_ms")
            self._maybe_schedule_refresh(end_ms)
        except (TimeoutError, aiohttp.ClientError, OSError) as e:
            self._consecutive_failures += 1

            if self._consecutive_failures < self._failure_threshold:
                _LOGGER.warning(
                    "[%s] ⚠️ Fetch failed (%s), but tolerating (%d/%d)",
                    self.device.name,
                    e,
                    self._consecutive_failures,
                    self._failure_threshold,
                )
                # Return the last known good data
                return self.data or {
                    "available": True,
                    "properties": {},
                    "end_ms": None,
                }

            _LOGGER.error(
                "[%s] ❌ Failed %d times in a row. Marking unavailable: %s",
                self.device.name,
                self._consecutive_failures,
                e,
            )
            raise UpdateFailed(e) from e
        else:
            return newData

    def _maybe_schedule_refresh(self, end_ms: int | None):
        """Schedule a one-time refresh at the timer's end time, only if not already scheduled."""
        if not end_ms:
            # No timer running, cancel any scheduled refresh
            self._scheduler.cancel(SCHEDULER_JOB_END_TIME_REFRESH)
            self._scheduled_end_time = None
            return

        new_end_time = datetime.fromtimestamp(end_ms / 1000, tz=UTC)
        refreshedMS = end_ms + 1000
        scheduledRefreshTime = datetime.fromtimestamp(refreshedMS / 1000, tz=UTC)
        if (
            self._scheduled_end_time is not None
            and abs((self._scheduled_end_time - new_end_time).total_seconds()) == 0
        ):
            # Already scheduled for this time (within 2s tolerance)
            _LOGGER.debug(
                "[%s] ⏭️ Skipping reschedule (end_time unchanged)", self.device.name
            )
            return

        # Cancel old job if it exists (we're rescheduling)
        self._scheduler.cancel(SCHEDULER_JOB_END_TIME_REFRESH)

        async def trigger_refresh():
            _LOGGER.info(
                "[%s] 🔁 Running %s", self.device.name, SCHEDULER_JOB_END_TIME_REFRESH
            )
            await self.async_request_refresh()

        self._scheduled_end_time = new_end_time
        self._scheduler.schedule(
            SCHEDULER_JOB_END_TIME_REFRESH, scheduledRefreshTime, trigger_refresh
        )
        _LOGGER.debug(
            "[%s] ✅ Scheduled refresh for %s",
            self.device.name,
            new_end_time.isoformat(),
        )


class NamedRefreshScheduler:
    def __init__(self, hass, label="Scheduler"):
        self._hass = hass
        self._jobs = {}
        self._label = label

    def schedule(self, name: str, utc_time: datetime, callback):
        """Schedule a one-time callback at a specific UTC datetime."""
        self.cancel(name)

        _LOGGER.debug(
            "[%s] 🕒 Scheduling job '%s' at %s", self._label, name, utc_time.isoformat()
        )

        def _wrapped_callback(now):
            _LOGGER.info("[%s] 🔁 Running job '%s'", self._label, name)
            self._jobs.pop(name, None)
            self._hass.loop.call_soon_threadsafe(
                lambda: self._hass.async_create_task(callback())
            )

        self._jobs[name] = async_track_point_in_utc_time(
            self._hass, _wrapped_callback, utc_time
        )

    def cancel(self, name: str):
        """Cancel a specific named job."""
        if name in self._jobs:
            _LOGGER.debug("[%s] ❌ Cancelling job '%s'", self._label, name)
            self._jobs[name]()
            del self._jobs[name]

    def cancel_all(self):
        """Cancel all scheduled jobs."""
        for name in list(self._jobs.keys()):
            self.cancel(name)

    def is_scheduled(self, name: str) -> bool:
        return name in self._jobs

    def scheduled_jobs(self):
        """Return a list of currently scheduled job names."""
        return list(self._jobs.keys())
