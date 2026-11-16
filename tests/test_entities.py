"""Golden-snapshot test of every entity the integration creates.

The snapshot (tests/snapshots/entities.json) records unique IDs, entity IDs,
states, attributes and device info for each fixture scenario. It guards
refactors: the same API data must produce exactly the same entities.

Regenerate with:  UPDATE_SNAPSHOT=1 python -m pytest tests/test_entities.py
"""

import json
import os
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import fixtures
from .conftest import mock_api

SNAPSHOT = Path(__file__).parent / "snapshots" / "entities.json"


def _jsonable(value):
    return json.loads(json.dumps(value, default=str, sort_keys=True))


async def _capture(hass: HomeAssistant, entry) -> dict:
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    out = {}
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        state = hass.states.get(entity.entity_id)
        device = dev_reg.async_get(entity.device_id)
        # Unique IDs are only unique per domain (the boost sensor and the
        # boost switch share one), so key by domain + unique ID.
        out[f"{entity.domain}:{entity.unique_id}"] = {
            "entity_id": entity.entity_id,
            "entity_category": entity.entity_category,
            "state": state.state if state else None,
            "attributes": _jsonable(dict(state.attributes)) if state else None,
            "device": {
                "identifiers": sorted(map(list, device.identifiers)),
                "name": device.name,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "sw_version": device.sw_version,
            },
        }
    return _jsonable(out)


@pytest.mark.parametrize("scenario", sorted(fixtures.SCENARIOS))
async def test_entities_match_snapshot(hass: HomeAssistant, config_entry, scenario) -> None:
    with mock_api(fixtures.SCENARIOS[scenario]):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        captured = await _capture(hass, config_entry)
        assert await hass.config_entries.async_unload(config_entry.entry_id)

    snapshot = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    if os.environ.get("UPDATE_SNAPSHOT"):
        snapshot[scenario] = captured
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(json.dumps(snapshot, indent=1, sort_keys=True) + "\n")
        return
    assert scenario in snapshot, "no snapshot yet - run with UPDATE_SNAPSHOT=1"
    assert captured == snapshot[scenario]
