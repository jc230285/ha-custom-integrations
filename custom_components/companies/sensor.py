"""Sensor platform for Companies integration."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CompaniesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Companies sensors from a config entry."""
    coordinator: CompaniesCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    known_keys: set[str] = set()

    @callback
    def _async_add_new_entities():
        """Add sensors for any new companies."""
        new_entities = []
        for key in coordinator.data:
            if key not in known_keys:
                known_keys.add(key)
                new_entities.append(CompanyBalanceSensor(coordinator, entry, key))
        if new_entities:
            _LOGGER.debug("Adding %d new Company sensors", len(new_entities))
            async_add_entities(new_entities)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


class CompanyBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a company's aggregated balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "GBP"

    def __init__(
        self,
        coordinator: CompaniesCoordinator,
        entry: ConfigEntry,
        company_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._company_id = company_id
        data = coordinator.data[company_id]

        self._attr_unique_id = f"{entry.entry_id}_{company_id}"
        self._attr_name = data["name"]
        self._attr_icon = "mdi:account-cash" if data["type"] == "personal" else "mdi:domain"

    @property
    def native_value(self) -> float | None:
        """Return the total company balance in GBP."""
        data = self.coordinator.data.get(self._company_id)
        if data is None:
            return None
        return data["total_gbp"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        data = self.coordinator.data.get(self._company_id)
        if data is None:
            return {}
        return {
            "registration_number": data["registration_number"],
            "company_type": data["type"],
            "account_count": data["account_count"],
            "wise_total_gbp": data["wise_total"],
            "btc_total_gbp": data["btc_total"],
            "accounts": data["accounts"],
        }
