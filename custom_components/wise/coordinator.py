"""Data update coordinator for Wise."""

import logging
from datetime import timedelta

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    EXCHANGE_RATE_URL,
    WISE_BALANCES_URL,
    WISE_PROFILES_URL,
)

_LOGGER = logging.getLogger(__name__)


class WiseCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Wise account data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL),
        )
        self.api_key = entry.data[CONF_API_KEY]
        self._exchange_rates: dict[str, float] = {}
        self._rates_fetched = False

    async def _async_update_data(self) -> dict:
        """Fetch data from Wise API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                profiles = await self._fetch_profiles(session, headers)
                if not self._rates_fetched:
                    await self._fetch_exchange_rates(session)

                accounts = {}
                for profile in profiles:
                    profile_id = profile["id"]
                    profile_type = profile["type"]
                    details = profile.get("details", {})

                    if profile_type == "personal":
                        profile_name = f"{details.get('firstName', '')} {details.get('lastName', '')}".strip()
                    else:
                        profile_name = details.get("name", "Business")

                    balances = await self._fetch_balances(session, headers, profile_id)

                    for balance in balances:
                        currency = balance["currency"]
                        amount = balance["amount"]["value"]
                        reserved = balance.get("reservedAmount", {}).get("value", 0)
                        rate = self._exchange_rates.get(currency, 1.0)
                        balance_gbp = round(amount / rate, 2) if rate else amount

                        key = f"{profile_type}_{currency}"
                        accounts[key] = {
                            "balance": amount,
                            "currency": currency,
                            "balance_gbp": balance_gbp,
                            "reserved_amount": reserved,
                            "profile_name": profile_name,
                            "profile_type": profile_type,
                            "profile_id": profile_id,
                            "balance_id": balance.get("id"),
                        }

                return accounts

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with Wise API: {err}") from err

    async def _fetch_profiles(self, session, headers) -> list:
        """Fetch Wise profiles."""
        async with session.get(WISE_PROFILES_URL, headers=headers) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Wise API returned {resp.status}")
            return await resp.json()

    async def _fetch_balances(self, session, headers, profile_id: int) -> list:
        """Fetch balances for a profile."""
        url = f"{WISE_BALANCES_URL}?profileId={profile_id}"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                _LOGGER.warning("Failed to fetch balances for profile %s: %s", profile_id, resp.status)
                return []
            data = await resp.json()
            if data and isinstance(data, list) and "balances" in data[0]:
                return data[0]["balances"]
            return []

    async def _fetch_exchange_rates(self, session) -> None:
        """Fetch exchange rates with GBP as base."""
        try:
            async with session.get(EXCHANGE_RATE_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._exchange_rates = data.get("rates", {})
                    self._exchange_rates["GBP"] = 1.0
                    self._rates_fetched = True
                    _LOGGER.debug("Fetched exchange rates: %s currencies", len(self._exchange_rates))
        except Exception:
            _LOGGER.warning("Failed to fetch exchange rates, using defaults")
            self._exchange_rates = {"GBP": 1.0, "USD": 1.27, "EUR": 1.17}
