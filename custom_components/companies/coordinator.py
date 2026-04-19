"""Data update coordinator for Companies."""

import logging
from collections import defaultdict
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .store import CompanyStore

_LOGGER = logging.getLogger(__name__)


class CompaniesCoordinator(DataUpdateCoordinator):
    """Coordinator that aggregates data from Wise and Blockonomics into companies."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: CompanyStore) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.store = store

    async def _async_update_data(self) -> dict:
        """Aggregate account data into companies."""
        company_data = {}

        for comp_id, comp in self.store.companies.items():
            company_data[comp_id] = {
                "name": comp["name"],
                "registration_number": comp["registration_number"],
                "type": comp["type"],
                "total_gbp": 0,
                "wise_total": 0,
                "btc_total": 0,
                "account_count": 0,
                "accounts": [],
            }

        wise_data = self.hass.data.get("wise", {})
        for entry_id, coordinator in wise_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            shares = entry.options.get("shares", {}) if entry else {}

            for key, account in coordinator.data.items():
                reg_num = account.get("registration_number", "")
                account_key = f"wise::{key}"
                comp_id = self.store.get_company_for_account(account_key, reg_num)
                if not comp_id or comp_id not in company_data:
                    continue

                share = shares.get(key, 100.0)
                gbp = round(account["balance_gbp"] * share / 100, 2)

                company_data[comp_id]["total_gbp"] += gbp
                company_data[comp_id]["wise_total"] += gbp
                company_data[comp_id]["account_count"] += 1
                company_data[comp_id]["accounts"].append({
                    "source": "wise",
                    "key": key,
                    "name": f"{account.get('balance_name', '')} {account['currency']}".strip(),
                    "balance_gbp": gbp,
                    "share": share,
                })

        blockonomics_data = self.hass.data.get("blockonomics", {})
        for entry_id, coordinator in blockonomics_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            shares = entry.options.get("shares", {}) if entry else {}

            for key, wallet in coordinator.data.items():
                company_number = wallet.get("company_number", "")
                account_key = f"blockonomics::{key}"
                comp_id = self.store.get_company_for_account(account_key, company_number)
                if not comp_id or comp_id not in company_data:
                    continue

                share = shares.get(key, 100.0)
                gbp = round(wallet["balance_gbp"] * share / 100, 2)

                company_data[comp_id]["total_gbp"] += gbp
                company_data[comp_id]["btc_total"] += gbp
                company_data[comp_id]["account_count"] += 1
                company_data[comp_id]["accounts"].append({
                    "source": "blockonomics",
                    "key": key,
                    "name": wallet.get("wallet_name", ""),
                    "balance_gbp": gbp,
                    "share": share,
                })

        for comp_id in company_data:
            company_data[comp_id]["total_gbp"] = round(company_data[comp_id]["total_gbp"], 2)
            company_data[comp_id]["wise_total"] = round(company_data[comp_id]["wise_total"], 2)
            company_data[comp_id]["btc_total"] = round(company_data[comp_id]["btc_total"], 2)

        _LOGGER.debug("Companies: %d companies aggregated", len(company_data))
        return company_data
