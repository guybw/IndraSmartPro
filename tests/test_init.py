"""Tests for setup, polling failures and recovery."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.indra.api import IndraApiError, IndraAuthError
from custom_components.indra.const import DOMAIN

from .conftest import mock_api

VOLTAGE = "sensor.indra_smart_pro_voltage"
BOOST = "switch.indra_smart_pro_boost_charging"


async def _setup(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()


async def test_setup_and_unload(hass: HomeAssistant, config_entry) -> None:
    with mock_api():
        await _setup(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED
        assert hass.states.get(VOLTAGE).state == "239"
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unreachable_api_at_startup_retries(hass: HomeAssistant, config_entry) -> None:
    """A timeout while validating the token means 'try again', not 'failed'."""
    with mock_api(validate_token={"side_effect": IndraApiError("timed out")}):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_first_poll_failure_retries(hass: HomeAssistant, config_entry) -> None:
    with mock_api(get_devices={"side_effect": IndraApiError("timed out")}):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_poll_failure_marks_unavailable_then_recovers(
    hass: HomeAssistant, config_entry
) -> None:
    with mock_api() as mocks:
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]

        mocks["get_device_telemetry"].side_effect = IndraApiError("timed out")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.last_update_success is False
        assert hass.states.get(VOLTAGE).state == STATE_UNAVAILABLE

        mocks["get_device_telemetry"].side_effect = None
        mocks["get_device_telemetry"].return_value = {"data": {"voltage": 241}}
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.last_update_success is True
        assert hass.states.get(VOLTAGE).state == "241"


async def test_token_refresh_timeout_is_update_failed(hass: HomeAssistant, config_entry) -> None:
    with mock_api() as mocks:
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]

        mocks["get_devices"].side_effect = IndraAuthError("expired")
        mocks["refresh_token"].side_effect = IndraApiError("timed out")
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.last_update_success is False
        assert hass.states.get(VOLTAGE).state == STATE_UNAVAILABLE


async def test_failed_command_reverts_switch(hass: HomeAssistant, config_entry) -> None:
    """A boost command that times out (False) must not leave the switch 'on'."""
    with mock_api(start_boost={"return_value": False}) as mocks:
        await _setup(hass, config_entry)
        assert hass.states.get(BOOST).state == "off"
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": BOOST}, blocking=True
        )
        await hass.async_block_till_done()
        mocks["start_boost"].assert_called_once()
        assert hass.states.get(BOOST).state == "off"
