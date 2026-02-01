"""Switch platform for Indra EV Charger."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IndraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Indra switches from a config entry."""
    coordinator: IndraDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device_uid, device_data in coordinator.data.get("devices", {}).items():
        device_info = device_data.get("device_info", {})

        # Boost switch
        entities.append(
            IndraBoostSwitch(
                coordinator=coordinator,
                device_uid=device_uid,
                device_info=device_info,
            )
        )

        # Lock switch
        entities.append(
            IndraLockSwitch(
                coordinator=coordinator,
                device_uid=device_uid,
                device_info=device_info,
            )
        )

        # Solar switch
        entities.append(
            IndraSolarSwitch(
                coordinator=coordinator,
                device_uid=device_uid,
                device_info=device_info,
            )
        )

    async_add_entities(entities)


class IndraBoostSwitch(CoordinatorEntity[IndraDataUpdateCoordinator], SwitchEntity):
    """Indra boost charging switch."""

    _attr_has_entity_name = True
    _attr_name = "Boost Charging"
    _attr_icon = "mdi:lightning-bolt"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_boost"
        self._optimistic_state: bool | None = None

        model = device_info.get("deviceModel", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
            name=f"Indra {model.get('deviceModel', 'Charger')}",
            manufacturer="Indra",
            model=f"{model.get('deviceModel', 'Smart PRO')} {model.get('deviceCapacity', 7)}kW",
            sw_version=device_info.get("firmwareVersion"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if boost is on."""
        # Use optimistic state if set (right after toggle)
        if self._optimistic_state is not None:
            return self._optimistic_state

        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        props = device_data.get("properties", {})
        boost_val = props.get("boost", {}).get("settingValue", "False")
        return boost_val == "True"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on boost charging."""
        self._optimistic_state = True
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.start_boost, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to start boost")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off boost charging."""
        self._optimistic_state = False
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.stop_boost, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to stop boost")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear optimistic state when we get real data
        self._optimistic_state = None
        super()._handle_coordinator_update()


class IndraLockSwitch(CoordinatorEntity[IndraDataUpdateCoordinator], SwitchEntity):
    """Indra charger lock switch."""

    _attr_has_entity_name = True
    _attr_name = "Lock Charger"
    _attr_icon = "mdi:lock"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_lock"
        self._optimistic_state: bool | None = None

        model = device_info.get("deviceModel", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
            name=f"Indra {model.get('deviceModel', 'Charger')}",
            manufacturer="Indra",
            model=f"{model.get('deviceModel', 'Smart PRO')} {model.get('deviceCapacity', 7)}kW",
            sw_version=device_info.get("firmwareVersion"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if charger is locked."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        props = device_data.get("properties", {})
        locked_val = props.get("deviceLocked", {}).get("settingValue", "False")
        return locked_val == "True"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the charger."""
        self._optimistic_state = True
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.lock_charger, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to lock charger")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the charger."""
        self._optimistic_state = False
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.unlock_charger, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to unlock charger")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()


class IndraSolarSwitch(CoordinatorEntity[IndraDataUpdateCoordinator], SwitchEntity):
    """Indra solar matching switch."""

    _attr_has_entity_name = True
    _attr_name = "Solar Matching"
    _attr_icon = "mdi:solar-power"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: IndraDataUpdateCoordinator,
        device_uid: str,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_uid = device_uid
        self._attr_unique_id = f"{device_uid}_solar"
        self._optimistic_state: bool | None = None

        model = device_info.get("deviceModel", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_uid)},
            name=f"Indra {model.get('deviceModel', 'Charger')}",
            manufacturer="Indra",
            model=f"{model.get('deviceModel', 'Smart PRO')} {model.get('deviceCapacity', 7)}kW",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if solar matching is enabled."""
        if self._optimistic_state is not None:
            return self._optimistic_state

        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        solar = device_data.get("solar", {})
        if solar:
            return solar.get("enabled", False)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device_data = self.coordinator.data.get("devices", {}).get(self._device_uid, {})
        solar = device_data.get("solar")
        return solar is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable solar matching."""
        self._optimistic_state = True
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.enable_solar, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to enable solar")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable solar matching."""
        self._optimistic_state = False
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.coordinator.api.disable_solar, self._device_uid
        )
        if not success:
            self._optimistic_state = None
            self.async_write_ha_state()
            _LOGGER.error("Failed to disable solar")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_state = None
        super()._handle_coordinator_update()
