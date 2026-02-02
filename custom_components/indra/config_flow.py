"""Config flow for Indra EV Charger integration."""

import logging
import asyncio
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL
from homeassistant.core import callback

from .api import IndraApi, IndraApiError
from .const import (
    DOMAIN,
    CONF_MOBILE_KEY,
    CONF_JWT_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
})


class IndraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Indra EV Charger."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str = ""
        self._mobile_key: str = ""
        self._hash: str = ""
        self._api: IndraApi | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step - email entry."""
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]

            # Check if already configured
            await self.async_set_unique_id(self._email)
            self._abort_if_unique_id_configured()

            # Create API and request magic link
            self._api = IndraApi(self._email)
            self._mobile_key = self._api.mobile_key

            try:
                self._hash = await self.hass.async_add_executor_job(
                    self._api.request_magic_link
                )
                return await self.async_step_verify()
            except IndraApiError as err:
                _LOGGER.error("Failed to request magic link: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_verify(self, user_input=None):
        """Handle magic link verification step."""
        errors = {}

        if user_input is not None:
            # Poll for token
            token = None
            for _ in range(30):  # Try for 60 seconds
                try:
                    token = await self.hass.async_add_executor_job(
                        self._api.get_token, self._hash
                    )
                    if token:
                        break
                except Exception:
                    pass
                await asyncio.sleep(2)

            if token:
                # Verify token works by getting devices
                try:
                    devices = await self.hass.async_add_executor_job(
                        self._api.get_devices
                    )
                    if devices:
                        return self.async_create_entry(
                            title=f"Indra Charger ({self._email})",
                            data={
                                CONF_EMAIL: self._email,
                                CONF_MOBILE_KEY: self._mobile_key,
                                CONF_JWT_TOKEN: token,
                            },
                        )
                    else:
                        errors["base"] = "no_devices"
                except IndraApiError:
                    errors["base"] = "cannot_connect"
            else:
                errors["base"] = "auth_timeout"

        # Show form with empty schema (just a submit button)
        return self.async_show_form(
            step_id="verify",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"email": self._email},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return IndraOptionsFlowHandler()


class IndraOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Indra EV Charger."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }),
        )
