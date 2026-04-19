"""Sensor platform for Wise integration."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WiseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wise sensors from a config entry."""
    coordinator: WiseCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for key, account_data in coordinator.data.items():
        entities.append(WiseBalanceSensor(coordinator, entry, key))

    async_add_entities(entities)


class WiseBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a Wise account balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WiseCoordinator,
        entry: ConfigEntry,
        account_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_key = account_key
        data = coordinator.data[account_key]

        self._attr_unique_id = f"{entry.entry_id}_{account_key}"
        self._attr_name = f"Wise {data['profile_type'].title()} {data['currency']}"
        self._attr_native_unit_of_measurement = data["currency"]

    @property
    def native_value(self) -> float | None:
        """Return the balance."""
        data = self.coordinator.data.get(self._account_key)
        if data is None:
            return None
        return data["balance"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        data = self.coordinator.data.get(self._account_key)
        if data is None:
            return {}
        return {
            "currency": data["currency"],
            "balance_gbp": data["balance_gbp"],
            "profile_name": data["profile_name"],
            "profile_type": data["profile_type"],
            "account_type": "Current",
            "reserved_amount": data["reserved_amount"],
        }
