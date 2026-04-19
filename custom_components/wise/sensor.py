"""Sensor platform for Wise integration."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SHARES, DEFAULT_SHARE, DOMAIN
from .coordinator import WiseCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wise sensors from a config entry."""
    coordinator: WiseCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Setting up Wise sensors, coordinator has %d accounts", len(coordinator.data))

    entities = []
    for key in coordinator.data:
        entities.append(WiseBalanceSensor(coordinator, entry, key))

    _LOGGER.debug("Adding %d Wise sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class WiseBalanceSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a Wise account balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "GBP"

    def __init__(
        self,
        coordinator: WiseCoordinator,
        entry: ConfigEntry,
        account_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_key = account_key
        self._entry = entry
        data = coordinator.data[account_key]

        profile_name = data["profile_name"]
        currency = data["currency"]
        profile_type = data["profile_type"]

        self._attr_unique_id = f"{entry.entry_id}_{account_key}"
        self._attr_name = f"{profile_name} {currency}"
        self._attr_icon = "mdi:account-cash" if profile_type == "personal" else "mdi:domain"

    @property
    def _share(self) -> float:
        """Get the share percentage for this account."""
        shares = self._entry.options.get(CONF_SHARES, {})
        return shares.get(self._account_key, DEFAULT_SHARE)

    @property
    def native_value(self) -> float | None:
        """Return the balance in GBP adjusted by share."""
        data = self.coordinator.data.get(self._account_key)
        if data is None:
            return None
        share = self._share
        return round(data["balance_gbp"] * share / 100, 2)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        data = self.coordinator.data.get(self._account_key)
        if data is None:
            return {}
        share = self._share
        return {
            "native_balance": data["balance"],
            "native_currency": data["currency"],
            "balance_gbp_full": data["balance_gbp"],
            "share": share,
            "profile_name": data["profile_name"],
            "profile_type": data["profile_type"],
            "account_type": "Personal" if data["profile_type"] == "personal" else "Company",
            "reserved_amount": data["reserved_amount"],
        }
