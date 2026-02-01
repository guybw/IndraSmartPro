"""Data coordinator for Indra EV Charger."""

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IndraApi, IndraApiError, IndraAuthError
from .const import DOMAIN, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


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

    def update_interval_from_options(self) -> None:
        """Update the scan interval from config entry options."""
        scan_interval = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.update_interval = timedelta(seconds=scan_interval)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Get devices
            devices = await self.hass.async_add_executor_job(self.api.get_devices)
            self.devices = devices

            data = {"devices": {}}

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

                data["devices"][device_uid] = {
                    "device_info": device,
                    "properties": props,
                    "telemetry": telemetry,
                    "device_telemetry": device_telemetry,
                    "current_transaction": current_txn,
                    "solar": solar,
                }

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
