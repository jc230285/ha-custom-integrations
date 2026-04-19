"""The Companies integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import CompaniesCoordinator
from .store import CompanyStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Companies from a config entry."""
    store = CompanyStore(hass)
    await store.async_load()

    coordinator = CompaniesCoordinator(hass, entry, store)
    await coordinator.async_config_entry_first_refresh()

    _LOGGER.debug("Companies coordinator: %d companies", len(coordinator.data))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "store": store,
    }

    # Listen to wise and blockonomics coordinator updates
    for source_domain in ("wise", "blockonomics"):
        for eid, source_coordinator in hass.data.get(source_domain, {}).items():
            if hasattr(source_coordinator, "async_add_listener"):
                entry.async_on_unload(
                    source_coordinator.async_add_listener(coordinator.async_request_refresh)
                )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
