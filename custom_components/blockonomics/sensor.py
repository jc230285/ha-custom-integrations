"""Sensor platform for Blockonomics integration."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SHARES, DEFAULT_SHARE, DOMAIN
from .coordinator import BlockonomicsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blockonomics sensors from a config entry."""
    coordinator: BlockonomicsCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.debug("Setting up Blockonomics sensors, coordinator has %d wallets", len(coordinator.data))

    entities = []
    for key in coordinator.data:
        entities.append(BlockonomicsSensor(coordinator, entry, key))

    _LOGGER.debug("Adding %d Blockonomics sensor entities", len(entities))
    async_add_entities(entities, update_before_add=True)


class BlockonomicsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a Blockonomics BTC wallet."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "GBP"
    _attr_icon = "mdi:bitcoin"

    def __init__(
        self,
        coordinator: BlockonomicsCoordinator,
        entry: ConfigEntry,
        wallet_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._wallet_key = wallet_key
        self._entry = entry
        data = coordinator.data[wallet_key]

        self._attr_unique_id = f"{entry.entry_id}_{wallet_key}"
        self._attr_name = f"BTC {data['wallet_name']}"

    @property
    def _share(self) -> float:
        """Get the share percentage for this wallet."""
        shares = self._entry.options.get(CONF_SHARES, {})
        return shares.get(self._wallet_key, DEFAULT_SHARE)

    @property
    def native_value(self) -> float | None:
        """Return the balance in GBP adjusted by share."""
        data = self.coordinator.data.get(self._wallet_key)
        if data is None:
            return None
        return round(data["balance_gbp"] * self._share / 100, 2)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        data = self.coordinator.data.get(self._wallet_key)
        if data is None:
            return {}
        return {
            "wallet_name": data["wallet_name"],
            "tag": data["tag"],
            "company_number": data["company_number"],
            "balance_btc": data["balance_btc"],
            "balance_sats": data["balance_sats"],
            "balance_gbp_full": data["balance_gbp"],
            "native_currency": "BTC",
            "share": self._share,
            "address": data["address"],
        }
