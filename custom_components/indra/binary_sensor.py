"""Binary sensor platform for Indra EV Charger."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Binary sensor descriptions for device properties
BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="connected",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        icon="mdi:wifi",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="charging",
        name="Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        icon="mdi:battery-charging",
    ),
    BinarySensorEntityDescription(
        key="cable_connected",
        name="Cable Connected",
        device_class=BinarySensorDeviceClass.PLUG,
        icon="mdi:ev-plug-type2",
    ),
    BinarySensorEntityDescription(
        key="supply_issue",
        name="Supply Issue",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="charge_interrupted",
        name="Charge Interrupted",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="device_fault",
        name="Device Fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-octagon",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="low_current",
        name="Low Current Warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:current-ac",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Indra binary sensors from a config entry."""
    coordinator: IndraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_uid, device_data in coordinator.data.get("devices", {}).items():
        device_info = device_data.get("device_info", {})

        for description in BINARY_SENSOR_DESCRIPTIONS:
            entities.append(
                IndraBinarySensor(
                    coordinator=coordinator,
                    device_uid=device_uid,
                    device_info=device_info,
                    description=description,
                )
            )

    async_add_entities(entities)


def _get_device_info(device_uid: str, device_info: dict[str, Any]) -> DeviceInfo:
    """Create device info for an entity."""
    model = device_info.get("deviceModel", {})
    return DeviceInfo(
        identifiers={(DOMAIN, device_uid)},
        name=f"Indra {model.get('deviceModel', 'Charger')}",
        manufacturer="Indra",
        model=f"{model.get('deviceModel', 'Smart PRO')} {model.get('deviceCapacity', 7)}kW",
        sw_version=device_info.get("firmwareVersion"),
    )


class IndraBinarySensor(CoordinatorEntity[IndraDataUpdateCoordinator], BinarySensorEntity):
    """Indra EV Charger binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_{description.key}"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        props = device_data.get("properties", {})
        telemetry = device_data.get("device_telemetry", {})

        key = self.entity_description.key

        if key == "connected":
            # Inverse of disconnected
            disconnected = props.get("disconnected", {}).get("settingValue", "False")
            return disconnected != "True"

        elif key == "charging":
            # Check if actively charging from telemetry
            state = telemetry.get("state", "")
            return state == "charging"

        elif key == "cable_connected":
            # Check cable state
            cable_state = props.get("cableState", {}).get("settingValue", "")
            return cable_state in ["charging", "connected", "notCharging"]

        elif key == "supply_issue":
            return props.get("chargeInterruptedSupplyIssue", {}).get("settingValue") == "True"

        elif key == "charge_interrupted":
            supply = props.get("chargeInterruptedSupplyIssue", {}).get("settingValue") == "True"
            unknown = props.get("chargeInterruptedUnknown", {}).get("settingValue") == "True"
            return supply or unknown

        elif key == "device_fault":
            temp_fault = props.get("deviceInoperableTemporary", {}).get("settingValue") == "True"
            diag_fault = props.get("deviceInoperableDiagnosed", {}).get("settingValue") == "True"
            not_auth = props.get("deviceNotAuthorised", {}).get("settingValue") == "True"
            return temp_fault or diag_fault or not_auth

        elif key == "low_current":
            operable = props.get("lowCurrentOperable", {}).get("settingValue") == "True"
            inoperable = props.get("lowCurrentInoperable", {}).get("settingValue") == "True"
            not_accepting = props.get("notAcceptingCurrent", {}).get("settingValue") == "True"
            return operable or inoperable or not_accepting

        return None
