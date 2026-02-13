"""Sensor platform for Indra EV Charger."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


# Status sensors from device properties
STATUS_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="charger_mode",
        name="Charger Mode",
        icon="mdi:ev-station",
    ),
    SensorEntityDescription(
        key="cable_state",
        name="Charger State",
        icon="mdi:ev-plug-type2",
    ),
    SensorEntityDescription(
        key="boost",
        name="Boost Active",
        icon="mdi:lightning-bolt",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="device_locked",
        name="Locked",
        icon="mdi:lock",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Indra sensors from a config entry."""
    coordinator: IndraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_uid, device_data in coordinator.data.get("devices", {}).items():
        device_info = device_data.get("device_info", {})

        # Add status sensors
        for description in STATUS_SENSOR_DESCRIPTIONS:
            entities.append(
                IndraStatusSensor(
                    coordinator=coordinator,
                    device_uid=device_uid,
                    device_info=device_info,
                    description=description,
                )
            )

        # Add telemetry sensors
        entities.extend([
            IndraPowerSensor(coordinator, device_uid, device_info),
            IndraCurrentSensor(coordinator, device_uid, device_info),
            IndraVoltageSensor(coordinator, device_uid, device_info),
            IndraTemperatureSensor(coordinator, device_uid, device_info),
            IndraSessionEnergySensor(coordinator, device_uid, device_info),
            IndraTotalEnergySensor(coordinator, device_uid, device_info),
            IndraCtClampSensor(coordinator, device_uid, device_info),
            IndraFrequencySensor(coordinator, device_uid, device_info),
        ])

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


class IndraStatusSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra EV Charger status sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_{description.key}"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        props = device_data.get("properties", {})

        key_map = {
            "charger_mode": "chargerMode",
            "cable_state": "cableState",
            "boost": "boost",
            "device_locked": "deviceLocked",
        }

        api_key = key_map.get(self.entity_description.key)
        if api_key and api_key in props:
            return props[api_key].get("settingValue")

        return None


class IndraPowerSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra charging power sensor."""

    _attr_has_entity_name = True
    _attr_name = "Charging Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_power"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the charging power in kW."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        power_w = data.get("powerToEv")
        if power_w is not None:
            return round(power_w / 1000, 2)  # Convert W to kW
        return 0.0


class IndraCurrentSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra charging current sensor."""

    _attr_has_entity_name = True
    _attr_name = "Charging Current"
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:current-ac"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_current"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the charging current in Amps."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        current = data.get("current")
        if current is not None:
            return round(current, 1)
        return 0.0


class IndraVoltageSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra voltage sensor."""

    _attr_has_entity_name = True
    _attr_name = "Voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sine-wave"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_voltage"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the voltage."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        voltage = data.get("voltage")
        if voltage is not None:
            return round(voltage, 1)
        return None


class IndraTemperatureSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra temperature sensor."""

    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_temperature"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the temperature."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        temp = data.get("temp")
        if temp is not None:
            return round(temp, 1)
        return None


class IndraSessionEnergySensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra session energy sensor - energy from the last completed charging session."""

    _attr_has_entity_name = True
    _attr_name = "Last Session Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:battery-charging"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_session_energy"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the session energy in kWh."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        txn = device_data.get("current_transaction")

        if txn:
            totals = txn.get("totals", {})
            energy = totals.get("energyImportedKwh")
            if energy is not None:
                return round(energy, 2)
        return 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        txn = device_data.get("current_transaction")

        if txn:
            totals = txn.get("totals", {})
            return {
                "session_start": txn.get("start"),
                "session_end": txn.get("end"),
                "range_added_miles": totals.get("rangeMiles"),
            }
        return {}


class IndraTotalEnergySensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra total energy sensor - lifetime energy delivered."""

    _attr_has_entity_name = True
    _attr_name = "Total Energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:counter"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_total_energy"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the total energy in kWh."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        # activeEnergyToEv is in Wh
        energy_wh = data.get("activeEnergyToEv")
        if energy_wh is not None:
            return round(energy_wh / 1000, 2)  # Convert Wh to kWh
        return None


class IndraCtClampSensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra CT clamp sensor - grid power measurement."""

    _attr_has_entity_name = True
    _attr_name = "Grid Power (CT Clamp)"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:transmission-tower"

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_ct_clamp"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the CT clamp power in kW."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        ct_power_w = data.get("ctClamp")
        if ct_power_w is not None:
            return round(ct_power_w / 1000, 2)  # Convert W to kW
        return None


class IndraFrequencySensor(CoordinatorEntity[IndraDataUpdateCoordinator], SensorEntity):
    """Indra grid frequency sensor."""

    _attr_has_entity_name = True
    _attr_name = "Grid Frequency"
    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_native_unit_of_measurement = "Hz"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sine-wave"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_frequency"
        self._attr_device_info = _get_device_info(device_uid, device_info)

    @property
    def native_value(self) -> float | None:
        """Return the grid frequency in Hz."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        telemetry = device_data.get("device_telemetry", {})
        data = telemetry.get("data", {})

        freq = data.get("freq")
        if freq is not None:
            return round(freq, 2)
        return None
