"""Data update coordinator for Wise."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    EXCHANGE_RATE_URL,
    WISE_BALANCES_URL,
    WISE_PROFILES_URL,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)


class WiseCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Wise account data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api_key = entry.data[CONF_API_KEY]
        self._exchange_rates: dict[str, float] = {}

    async def _async_update_data(self) -> dict:
        """Fetch data from Wise API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        session = async_get_clientsession(self.hass)

        try:
            profiles = await self._fetch_profiles(session, headers)
            _LOGGER.debug("Fetched %d Wise profiles", len(profiles))
            await self._fetch_exchange_rates(session)

            accounts = {}
            for profile in profiles:
                profile_id = profile["id"]
                profile_type = profile["type"].lower()

                if profile_type == "personal":
                    profile_name = profile.get("fullName", "").strip() or "Personal"
                else:
                    profile_name = (
                        profile.get("businessName")
                        or profile.get("fullName", "").strip()
                        or f"Business {profile_id}"
                    )

                registration_number = profile.get("registrationNumber", "")

                balances = await self._fetch_balances(session, headers, profile_id)

                for balance in balances:
                    bal_amount = balance.get("amount", balance.get("cashAmount", {}))
                    currency = bal_amount.get("currency", balance.get("currency", ""))
                    amount = bal_amount.get("value", 0)
                    reserved = balance.get("reservedAmount", {}).get("value", 0)
                    bal_type = balance.get("type", "STANDARD")
                    bal_name = balance.get("name") or ""
                    bal_id = balance.get("id", "")

                    if amount == 0 and reserved == 0:
                        continue

                    rate = self._exchange_rates.get(currency, 1.0)
                    balance_gbp = round(amount / rate, 2) if rate else amount

                    if bal_name:
                        key = f"{profile_id}_{bal_name}_{currency}"
                    else:
                        key = f"{profile_id}_{currency}"

                    accounts[key] = {
                        "balance": amount,
                        "currency": currency,
                        "balance_gbp": balance_gbp,
                        "reserved_amount": reserved,
                        "profile_name": profile_name,
                        "profile_type": profile_type,
                        "profile_id": profile_id,
                        "balance_id": bal_id,
                        "balance_type": bal_type,
                        "balance_name": bal_name,
                        "registration_number": registration_number,
                    }

            _LOGGER.debug("Wise: %d accounts with non-zero balances", len(accounts))
            return accounts

        except Exception as err:
            _LOGGER.error("Error fetching Wise data: %s", err)
            raise UpdateFailed(f"Error communicating with Wise API: {err}") from err

    async def _fetch_profiles(self, session, headers) -> list:
        """Fetch Wise profiles."""
        async with session.get(WISE_PROFILES_URL, headers=headers) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"Wise API returned {resp.status}")
            return await resp.json()

    async def _fetch_balances(self, session, headers, profile_id: int) -> list:
        """Fetch balances for a profile using v4 API (includes savings/jars)."""
        url = f"{WISE_BALANCES_URL}/{profile_id}/balances?types=STANDARD,SAVINGS"
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                _LOGGER.warning("Failed to fetch balances for profile %s: %s", profile_id, resp.status)
                return []
            return await resp.json()

    async def _fetch_exchange_rates(self, session) -> None:
        """Fetch exchange rates with GBP as base."""
        try:
            async with session.get(EXCHANGE_RATE_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._exchange_rates = data.get("rates", {})
                    self._exchange_rates["GBP"] = 1.0
        except Exception:
            _LOGGER.warning("Failed to fetch exchange rates, using defaults")
            self._exchange_rates = {"GBP": 1.0, "USD": 1.27, "EUR": 1.17}
