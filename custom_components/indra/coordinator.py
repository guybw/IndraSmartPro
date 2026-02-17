"""Data coordinator for Indra EV Charger."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IndraApi, IndraApiError, IndraAuthError
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_session_baselines"
STORAGE_VERSION = 1


class IndraDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates from Indra API."""

    def __init__(
        self, hass: HomeAssistant, api: IndraApi, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self._entry = entry
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.devices: list[dict[str, Any]] = []
        # Track session energy baselines (activeEnergyToEv at session start)
        self._session_baselines: dict[str, float | None] = {}
        self._prev_cable_states: dict[str, str | None] = {}
        self._unplug_count: dict[str, int] = {}  # consecutive notCharging polls
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._storage_loaded = False

    async def _load_baselines(self) -> None:
        """Load persisted session baselines from disk."""
        if self._storage_loaded:
            return
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            self._session_baselines = stored.get("baselines", {})
            self._prev_cable_states = stored.get("cable_states", {})
            self._unplug_count = stored.get("unplug_count", {})
            _LOGGER.debug("Restored session baselines: %s", self._session_baselines)
        self._storage_loaded = True

    async def _save_baselines(self) -> None:
        """Persist session baselines to disk."""
        await self._store.async_save({
            "baselines": self._session_baselines,
            "cable_states": self._prev_cable_states,
            "unplug_count": self._unplug_count,
        })

    def update_interval_from_options(self) -> None:
        """Update the scan interval from config entry options."""
        scan_interval = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.update_interval = timedelta(seconds=scan_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        # Restore baselines from disk on first run
        await self._load_baselines()

        try:
            # Get devices
            devices = await self.hass.async_add_executor_job(self.api.get_devices)
            self.devices = devices

            data = {"devices": {}}
            baselines_changed = False

            for device in devices:
                device_uid = device.get("deviceUID")
                location_uid = device.get("location", {}).get("locationUID")

                # Get device properties
                props = await self.hass.async_add_executor_job(
                    self.api.get_device_properties, device_uid
                )

                # Get telemetry if location available
                telemetry = {}
                if location_uid:
                    telemetry = await self.hass.async_add_executor_job(
                        self.api.get_telemetry, location_uid
                    )

                # Get solar status
                solar = await self.hass.async_add_executor_job(
                    self.api.get_solar_status, device_uid
                )

                # Get device telemetry (power, current, voltage)
                device_telemetry = await self.hass.async_add_executor_job(
                    self.api.get_device_telemetry, device_uid
                )

                # Get current transaction for session energy
                current_txn = await self.hass.async_add_executor_job(
                    self.api.get_current_transaction, device_uid
                )

                # Get schedules for this device
                all_schedules = await self.hass.async_add_executor_job(
                    self.api.get_schedules
                )
                device_schedules = [
                    s for s in all_schedules
                    if s.get("deviceUId") == device_uid
                ]

                # Track session energy baseline
                cable_state = props.get("cableState", {}).get("settingValue", "")
                prev_state = self._prev_cable_states.get(device_uid)
                telem_data = device_telemetry.get("data", {})
                current_energy_wh = telem_data.get("activeEnergyToEv")

                # Track session energy baseline.
                # Only set baseline on a confirmed new plug-in event.
                # Supplier stop/start cycles can briefly set cableState
                # to "notCharging", so we require 2 consecutive polls
                # in "notCharging" before we consider the cable truly
                # unplugged and clear the baseline.
                is_plugged_in = cable_state in ("charging", "connected")

                if cable_state == "notCharging":
                    count = self._unplug_count.get(device_uid, 0) + 1
                    self._unplug_count[device_uid] = count
                    if count >= 2 and device_uid in self._session_baselines:
                        # Confirmed unplug - clear baseline
                        del self._session_baselines[device_uid]
                        baselines_changed = True
                        _LOGGER.debug("Confirmed unplug, cleared baseline")
                else:
                    self._unplug_count[device_uid] = 0

                if is_plugged_in and device_uid not in self._session_baselines:
                    # No baseline exists - new plug-in, set it
                    if current_energy_wh is not None:
                        self._session_baselines[device_uid] = current_energy_wh
                        baselines_changed = True
                        _LOGGER.debug(
                            "Car plugged in, baseline: %s Wh",
                            current_energy_wh,
                        )

                if cable_state != prev_state:
                    self._prev_cable_states[device_uid] = cable_state
                    baselines_changed = True

                data["devices"][device_uid] = {
                    "device_info": device,
                    "properties": props,
                    "telemetry": telemetry,
                    "device_telemetry": device_telemetry,
                    "current_transaction": current_txn,
                    "solar": solar,
                    "session_energy_baseline": self._session_baselines.get(device_uid),
                    "schedules": device_schedules,
                }

            # Only write to disk when baselines or cable states change
            if baselines_changed:
                await self._save_baselines()

            return data

        except IndraAuthError as err:
            # Try to refresh token
            _LOGGER.warning("Auth error, attempting token refresh")
            refreshed = await self.hass.async_add_executor_job(self.api.refresh_token)
            if not refreshed:
                raise UpdateFailed(f"Authentication failed: {err}") from err
            # Retry after refresh
            return await self._async_update_data()

        except IndraApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
