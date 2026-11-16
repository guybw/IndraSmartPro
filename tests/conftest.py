"""Shared fixtures for the Indra tests."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.indra.api import IndraApi
from custom_components.indra.const import CONF_JWT_TOKEN, CONF_MOBILE_KEY, DOMAIN

from . import fixtures

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/indra."""
    yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A config entry as created by a successful magic-link login."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Indra Charger ({fixtures.EMAIL})",
        unique_id=fixtures.EMAIL,
        data={
            "email": fixtures.EMAIL,
            CONF_MOBILE_KEY: "00000000-0000-4000-8000-000000000001",
            CONF_JWT_TOKEN: "x" * 64,
        },
    )


@contextmanager
def mock_api(scenario: dict | None = None, **overrides):
    """Patch IndraApi's network methods to return fixture data.

    ``scenario`` is one of the dicts in fixtures.SCENARIOS. Any keyword
    argument replaces that method's mock (pass a side_effect callable or
    an exception instance via ``side_effect=``).
    """
    data = scenario or fixtures.SCENARIOS["idle"]
    methods = {
        "validate_token": {"return_value": True},
        "refresh_token": {"return_value": True},
        "get_devices": {"return_value": data["devices"]},
        "get_device_properties": {"side_effect": lambda uid: data["properties"]},
        "get_telemetry": {"side_effect": lambda uid: {}},
        "get_solar_status": {"side_effect": lambda uid: data["solar"]},
        "get_device_telemetry": {"side_effect": lambda uid: data["device_telemetry"]},
        "get_current_transaction": {"side_effect": lambda uid: data["transaction"]},
        "get_schedules": {"return_value": data["schedules"]},
        "start_boost": {"return_value": True},
        "stop_boost": {"return_value": True},
        "lock_charger": {"return_value": True},
        "unlock_charger": {"return_value": True},
        "enable_solar": {"return_value": True},
        "disable_solar": {"return_value": True},
    }
    methods.update(overrides)
    started = []
    mocks = {}
    try:
        for name, kwargs in methods.items():
            patcher = patch.object(IndraApi, name, **kwargs)
            mocks[name] = patcher.start()
            started.append(patcher)
        yield mocks
    finally:
        for patcher in reversed(started):
            patcher.stop()
