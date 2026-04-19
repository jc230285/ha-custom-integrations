"""Data update coordinator for Blockonomics."""

import logging
import re
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BTC_GBP_URL, DOMAIN, WALLETS_URL

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)
SATS_PER_BTC = 100_000_000

TAG_RE = re.compile(r"\[([^\]]+)\]")
COMPANY_NUM_RE = re.compile(r"\(([^)]+)\)")


class BlockonomicsCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch Blockonomics wallet data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api_key = entry.data[CONF_API_KEY]
        self._btc_gbp_rate: float = 0

    async def _async_update_data(self) -> dict:
        """Fetch data from Blockonomics API."""
        session = async_get_clientsession(self.hass)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
        }

        try:
            async with session.get(WALLETS_URL, headers=headers) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Blockonomics API returned {resp.status}")
                data = await resp.json()

            await self._fetch_btc_gbp_rate(session)

            wallets = {}
            for wallet in data.get("data", []):
                balance = wallet.get("balance", {})
                confirmed_sats = balance.get("confirmed_sats", 0)
                unconfirmed_sats = balance.get("unconfirmed_sats", 0)

                if confirmed_sats == 0 and unconfirmed_sats == 0:
                    continue

                wallet_id = str(wallet["id"])
                wallet_name = wallet.get("name", "")
                balance_btc = confirmed_sats / SATS_PER_BTC
                balance_gbp = round(balance_btc * self._btc_gbp_rate, 2)

                tag_match = TAG_RE.search(wallet_name)
                company_match = COMPANY_NUM_RE.search(wallet_name)

                wallets[wallet_id] = {
                    "wallet_name": wallet_name,
                    "tag": tag_match.group(1) if tag_match else "",
                    "company_number": company_match.group(1) if company_match else "",
                    "balance_sats": confirmed_sats,
                    "balance_btc": balance_btc,
                    "balance_gbp": balance_gbp,
                    "address": wallet.get("address", ""),
                    "crypto": wallet.get("crypto", "BTC"),
                }

            _LOGGER.debug("Blockonomics: %d wallets with non-zero balances", len(wallets))
            return wallets

        except Exception as err:
            _LOGGER.error("Error fetching Blockonomics data: %s", err)
            raise UpdateFailed(f"Error communicating with Blockonomics API: {err}") from err

    async def _fetch_btc_gbp_rate(self, session) -> None:
        """Fetch BTC/GBP exchange rate."""
        try:
            async with session.get(BTC_GBP_URL) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._btc_gbp_rate = data.get("bitcoin", {}).get("gbp", 0)
                    _LOGGER.debug("BTC/GBP rate: %s", self._btc_gbp_rate)
        except Exception:
            _LOGGER.warning("Failed to fetch BTC/GBP rate, using previous: %s", self._btc_gbp_rate)
            if self._btc_gbp_rate == 0:
                self._btc_gbp_rate = 65000
