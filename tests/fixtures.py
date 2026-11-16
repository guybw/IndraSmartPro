"""Anonymised Indra API responses, shaped like the real ones (Smart PRO, 2026-11)."""

EMAIL = "user@example.com"
DEVICE_UID = "11111111-2222-4333-8444-555555555555"


def _prop(value: str, modified: str = "2026-11-06T08:26:47.188Z") -> dict:
    return {"settingValue": value, "lastModified": modified}


DEVICES = [
    {
        "deviceUID": DEVICE_UID,
        "deviceMac": "00:00:5e:00:53:01",
        "deviceName": "Driveway",
        "deviceDescription": "",
        "active": True,
        "deviceStateId": "state-1",
        "state": "ACTIVE_USER",
        "deviceModel": {
            "deviceModel": "Smart PRO",
            "deviceCapacity": 7,
            "deviceCapacityW": 7360,
            "connectionType": "Type 2",
            "tethered": True,
            "motherboardVersion": 4.1,
        },
        "location": {"locationUID": "loc-1", "country": "UK"},
        "chargeOwner": {"id": 2, "name": "Octopus"},
    }
]

_BASE_PROPERTIES = {
    "disconnected": _prop("False"),
    "cableState": _prop("unplugged"),
    "chargerMode": _prop("IDLE"),
    "deviceLocked": _prop("False"),
    "boost": _prop("False"),
    "defaultProfile": _prop(""),
    "notAcceptingCurrent": _prop("False"),
    "deviceNotAuthorised": _prop("False"),
    "lowCurrentOperable": _prop("False"),
    "lowCurrentInoperable": _prop("False"),
    "scheduleTargetImpossible": _prop("False"),
    "deviceInoperableTemporary": _prop("False"),
    "deviceInoperableDiagnosed": _prop("False"),
    "chargeInterruptedSupplyIssue": _prop("False"),
    "chargeInterruptedUnknown": _prop("False"),
    "persistentProfile": _prop("ZeroLimit"),
    "defaultProfileOverride": _prop(""),
    "chargeProfile": _prop("00000000-0000-4000-8000-0000000000aa"),
    "chargeProfileOverride": _prop(""),
}

TRANSACTION = {
    "id": "txn-1",
    "deviceUId": DEVICE_UID,
    "start": "2026-11-02T20:29:59.917Z",
    "end": "2026-11-03T07:34:44.666Z",
    "chargeOwner": {"id": 2, "name": "Octopus"},
    "totals": {
        "costInclTax": 0,
        "energyExportedKwh": 0,
        "energyImportedKwh": 23.12,
        "energyKwh": 23.12,
        "rangeMiles": 75.9,
    },
    "events": [],
}

SCENARIOS = {
    # Unplugged, idle, offline-safe values: the state seen on 2026-11-06 08:37.
    "idle": {
        "devices": DEVICES,
        "properties": _BASE_PROPERTIES,
        "device_telemetry": {
            "time": "2026-11-06T08:36:19.506Z",
            "isBoosting": False,
            "mode": "IDLE",
            "state": "unplugged",
            "data": {
                "activeEnergyFromEv": 159,
                "activeEnergyToEv": 18086270,
                "powerToEv": 0,
                "ctClamp": -56,
                "current": 0,
                "voltage": 239,
                "freq": 50,
                "temp": 14,
            },
        },
        "solar": {"hasSolar": False, "useSolar": False},
        "transaction": TRANSACTION,
        "schedules": [],
    },
    # Plugged in and charging under a boost, with a schedule, solar on,
    # problem flags set and the charger offline - exercises the other branches.
    "charging": {
        "devices": DEVICES,
        "properties": {
            **_BASE_PROPERTIES,
            "disconnected": _prop("True"),
            "cableState": _prop("charging"),
            "chargerMode": _prop("BOOST"),
            "boost": _prop("True"),
            "deviceLocked": _prop("True"),
            "chargeInterruptedUnknown": _prop("True"),
            "deviceInoperableTemporary": _prop("True"),
            "lowCurrentOperable": _prop("True"),
        },
        "device_telemetry": {
            "time": "2026-11-06T00:15:00.000Z",
            "isBoosting": True,
            "mode": "BOOST",
            "state": "charging",
            "data": {
                "activeEnergyFromEv": 159,
                "activeEnergyToEv": 18090123,
                "powerToEv": 7123,
                "ctClamp": 7456,
                "current": 31.27,
                "voltage": 238.44,
                "freq": 49.987,
                "temp": 21.36,
            },
        },
        "solar": {"enabled": True, "hasSolar": True, "useSolar": True},
        "transaction": None,
        "schedules": [
            {
                "deviceUId": DEVICE_UID,
                "name": "Weeknights",
                "timing": {"start": "23:30:00", "end": "05:30:00"},
                "recurrence": "MON,TUE,WED,THU,FRI",
                "target": {"value": 80, "unit": "PERCENT"},
            },
            {"deviceUId": "someone-else", "name": "Not ours"},
        ],
    },
}
