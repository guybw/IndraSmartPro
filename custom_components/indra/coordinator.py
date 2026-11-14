"""Data coordinator for Indra EV Charger."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import IndraApi, IndraApiError, IndraAuthError
from .const import (
    CONF_JWT_TOKEN,
    TOKEN_REFRESH_BEFORE,
    TOKEN_REFRESH_RETRY,
    CABLE_STATES_UNPLUGGED,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

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
        # Track session energy baselines (activeEnergyToEv at plug-in)
        self._session_baselines: dict[str, float | None] = {}
        self._prev_cable_connected: dict[str, bool] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._storage_loaded = False
        self._last_token_refresh_attempt = None

    async def _load_baselines(self) -> None:
        """Load persisted session baselines from disk."""
        if self._storage_loaded:
            return
        stored = await self._store.async_load()
        if stored and isinstance(stored, dict):
            self._session_baselines = stored.get("baselines", {})
            self._prev_cable_connected = stored.get("cable_connected", {})
            _LOGGER.debug("Restored session baselines: %s", self._session_baselines)
        self._storage_loaded = True

    async def _save_baselines(self) -> None:
        """Persist session baselines to disk."""
        await self._store.async_save({
            "baselines": self._session_baselines,
            "cable_connected": self._prev_cable_connected,
        })

    def _save_token(self) -> None:
        """Store the API's current token in the config entry.

        The token is refreshed in memory; without this, setup would start
        from the old (eventually expired) token after every restart.
        """
        if self.api.jwt_token and self._entry.data.get(CONF_JWT_TOKEN) != self.api.jwt_token:
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_JWT_TOKEN: self.api.jwt_token},
            )

    async def _refresh_token_if_due(self) -> None:
        """Refresh the token before it expires, and keep the new one."""
        expiry = self.api.token_expiry()
        now = dt_util.utcnow()
        if expiry is None or expiry - now > TOKEN_REFRESH_BEFORE:
            return
        last = self._last_token_refresh_attempt
        if last is not None and now - last < TOKEN_REFRESH_RETRY:
            return
        self._last_token_refresh_attempt = now
        try:
            refreshed = await self.hass.async_add_executor_job(self.api.refresh_token)
        except IndraApiError as err:
            _LOGGER.warning("Token refresh failed, will retry: %s", err)
            return
        if not refreshed:
            _LOGGER.warning(
                "Token refresh was refused; the current token expires %s", expiry
            )
            return
        self._save_token()
        new_expiry = self.api.token_expiry()
        if new_expiry is None or new_expiry <= expiry:
            _LOGGER.warning(
                "Token refreshed, but the new one doesn't expire later "
                "(was %s, now %s)",
                expiry,
                new_expiry,
            )
        else:
            _LOGGER.info(
                "Token refreshed; it expired %s, now expires %s", expiry, new_expiry
            )

    def update_interval_from_options(self) -> None:
        """Update the scan interval from config entry options."""
        scan_interval = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.update_interval = timedelta(seconds=scan_interval)

    async def _async_update_data(self, retry: int = 0) -> dict[str, Any]:
        """Fetch data from API."""
        # Restore baselines from disk on first run
        await self._load_baselines()

        if not retry:
            await self._refresh_token_if_due()

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

                # Session energy baseline tracking.
                # This matches the Cable Connected binary sensor logic: any
                # cableState other than a known-unplugged one (see
                # CABLE_STATES_UNPLUGGED) counts as connected. Values like
                # "notCharging" and "disabled" mean the cable is connected
                # but not actively charging (e.g. supplier paused the charge
                # overnight, or charging isn't currently permitted).
                cable_state = props.get("cableState", {}).get("settingValue") or ""
                cable_connected = cable_state not in CABLE_STATES_UNPLUGGED
                was_connected = self._prev_cable_connected.get(device_uid, False)
                telem_data = device_telemetry.get("data", {})
                current_energy_wh = telem_data.get("activeEnergyToEv")

                # Cable just unplugged - clear baseline
                if was_connected and not cable_connected:
                    if device_uid in self._session_baselines:
                        del self._session_baselines[device_uid]
                        _LOGGER.debug("Cable unplugged, cleared baseline")
                    baselines_changed = True

                # Cable just plugged in - set new baseline
                if cable_connected and not was_connected:
                    if current_energy_wh is not None:
                        self._session_baselines[device_uid] = current_energy_wh
                        _LOGGER.debug(
                            "Cable plugged in, baseline: %s Wh",
                            current_energy_wh,
                        )
                    baselines_changed = True

                if cable_connected != was_connected:
                    self._prev_cable_connected[device_uid] = cable_connected

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
            # Try to refresh token, but only once to avoid an unbounded
            # retry loop if the API keeps reporting the refreshed token
            # as invalid (e.g. a persistent server-side auth problem).
            if retry:
                raise UpdateFailed(f"Authentication failed after refresh: {err}") from err
            _LOGGER.warning("Auth error, attempting token refresh")
            try:
                refreshed = await self.hass.async_add_executor_job(
                    self.api.refresh_token
                )
            except IndraApiError as refresh_err:
                raise UpdateFailed(f"Token refresh failed: {refresh_err}") from refresh_err
            if not refreshed:
                raise UpdateFailed(f"Authentication failed: {err}") from err
            self._save_token()
            # Retry once after refresh
            return await self._async_update_data(retry=retry + 1)

        except IndraApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
