"""Indra EV Charger integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant

from .api import IndraApi
from .const import DOMAIN, CONF_MOBILE_KEY, CONF_JWT_TOKEN
from .coordinator import IndraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Indra EV Charger from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client
    api = IndraApi(
        email=entry.data[CONF_EMAIL],
        mobile_key=entry.data[CONF_MOBILE_KEY],
        jwt_token=entry.data[CONF_JWT_TOKEN],
    )

    # Validate token, refresh if needed
    valid = await hass.async_add_executor_job(api.validate_token)
    if not valid:
        _LOGGER.info("Token invalid, attempting refresh")
        refreshed = await hass.async_add_executor_job(api.refresh_token)
        if refreshed:
            # Update stored token
            hass.config_entries.async_update_entry(
                entry,
                data={
                    **entry.data,
                    CONF_JWT_TOKEN: api.jwt_token,
                },
            )
        else:
            _LOGGER.error("Failed to refresh token, re-authentication required")
            # Could trigger reauth flow here

    # Create coordinator
    coordinator = IndraDataUpdateCoordinator(hass, api, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: IndraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_interval_from_options()
    _LOGGER.info("Updated scan interval from options")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
