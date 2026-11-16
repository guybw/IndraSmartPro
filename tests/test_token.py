"""Tests for refreshing the login token before it expires and keeping it."""

import base64
import json
import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.indra.api import IndraApi, IndraApiError, IndraAuthError
from custom_components.indra.const import CONF_JWT_TOKEN, DOMAIN

from .conftest import mock_api


def make_jwt(expires_in: timedelta) -> str:
    """An unsigned token with the claims Indra's tokens have."""
    def part(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    exp = int((dt_util.utcnow() + expires_in).timestamp())
    claims = {"email": "user@example.com", "key": "k", "nbf": exp - 30 * 86400, "exp": exp}
    return f"{part({'alg': 'HS256', 'typ': 'JWT'})}.{part(claims)}.signature"


def refresh_to(new_token: str):
    """A refresh_token side effect that swaps in ``new_token``, like the real one."""
    def refresh(api: IndraApi) -> bool:
        api.jwt_token = new_token
        return True
    return {"autospec": True, "side_effect": refresh}


async def _setup(hass: HomeAssistant, entry, token: str) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_JWT_TOKEN: token})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def test_token_expiry_reads_exp_claim() -> None:
    token = make_jwt(timedelta(days=21))
    expiry = IndraApi("user@example.com", jwt_token=token).token_expiry()
    assert abs((expiry - dt_util.utcnow()) - timedelta(days=21)) < timedelta(seconds=5)


def test_token_expiry_unreadable() -> None:
    for token in (None, "x" * 64, "a.b.c", "a.e30.c"):  # e30 = "{}"
        assert IndraApi("user@example.com", jwt_token=token).token_expiry() is None


async def test_token_far_from_expiry_is_left_alone(hass: HomeAssistant, config_entry) -> None:
    token = make_jwt(timedelta(days=20))
    with mock_api() as mocks:
        await _setup(hass, config_entry, token)
        mocks["refresh_token"].assert_not_called()
    assert config_entry.data[CONF_JWT_TOKEN] == token


async def test_token_near_expiry_is_refreshed_and_saved(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="custom_components.indra")
    new = make_jwt(timedelta(days=30))
    with mock_api(refresh_token=refresh_to(new)) as mocks:
        await _setup(hass, config_entry, make_jwt(timedelta(days=3)))
        mocks["refresh_token"].assert_called_once()
        assert config_entry.data[CONF_JWT_TOKEN] == new
        # The next poll sees a fresh token and doesn't refresh again
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        await coordinator.async_refresh()
        mocks["refresh_token"].assert_called_once()
        assert coordinator.last_update_success
    assert "Token refreshed; it expired" in caplog.text


async def test_refresh_that_does_not_extend_is_flagged(
    hass: HomeAssistant, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    """If Indra hands back a token that expires no later, say so in the log."""
    old = make_jwt(timedelta(days=3))
    with mock_api(refresh_token=refresh_to(old)):
        await _setup(hass, config_entry, old)
    assert "doesn't expire later" in caplog.text


def test_refused_refresh_logs_status(caplog: pytest.LogCaptureFixture) -> None:
    api = IndraApi("user@example.com", "k", make_jwt(timedelta(days=3)))
    response = MagicMock(status_code=401, text="Unauthorized")
    with patch.object(api, "_request", return_value=response):
        assert api.refresh_token() is False
    assert "HTTP 401: Unauthorized" in caplog.text


async def test_failed_refresh_keeps_polling_and_retries_later(
    hass: HomeAssistant, config_entry, freezer: FrozenDateTimeFactory
) -> None:
    old = make_jwt(timedelta(days=3))
    with mock_api(refresh_token={"side_effect": IndraApiError("timed out")}) as mocks:
        await _setup(hass, config_entry, old)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        assert coordinator.last_update_success
        assert mocks["refresh_token"].call_count == 1

        # Not retried on every poll...
        freezer.tick(timedelta(hours=1))
        await coordinator.async_refresh()
        assert mocks["refresh_token"].call_count == 1

        # ...but again after the retry interval
        mocks["refresh_token"].side_effect = None
        mocks["refresh_token"].return_value = False
        freezer.tick(timedelta(hours=6))
        await coordinator.async_refresh()
        assert mocks["refresh_token"].call_count == 2
        assert coordinator.last_update_success
    assert config_entry.data[CONF_JWT_TOKEN] == old


async def test_refresh_after_auth_error_is_saved(hass: HomeAssistant, config_entry) -> None:
    """A token refreshed after a 401 is kept for the next restart."""
    new = make_jwt(timedelta(days=30))
    with mock_api(refresh_token=refresh_to(new)) as mocks:
        await _setup(hass, config_entry, make_jwt(timedelta(days=20)))
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        devices = mocks["get_devices"].return_value
        mocks["get_devices"].side_effect = [IndraAuthError("expired"), devices]
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert config_entry.data[CONF_JWT_TOKEN] == new
