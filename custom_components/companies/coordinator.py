"""Data update coordinator for Companies."""

import logging
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

    def _find_or_create_company(self, name: str, registration_number: str, company_type: str) -> str:
        """Find existing company by reg number or name, or create a new one."""
        # Match by registration number first
        if registration_number:
            for comp_id, comp in self.store.companies.items():
                if comp["registration_number"] and comp["registration_number"] == registration_number:
                    return comp_id

        # Match by exact name
        for comp_id, comp in self.store.companies.items():
            if comp["name"].lower() == name.lower():
                return comp_id

        # Create new company
        comp_id = self.store.add_company(name, registration_number, company_type)
        _LOGGER.info("Auto-created company: %s (%s)", name, registration_number)
        return comp_id

    async def _async_update_data(self) -> dict:
        """Discover companies from sources and aggregate balances."""
        changed = False

        # Phase 1: Discover companies from Wise profiles
        wise_data = self.hass.data.get("wise", {})
        for entry_id, coordinator in wise_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            # Collect unique profiles
            seen_profiles = set()
            for key, account in coordinator.data.items():
                profile_id = account.get("profile_id")
                if profile_id in seen_profiles:
                    continue
                seen_profiles.add(profile_id)

                name = account["profile_name"]
                reg = account.get("registration_number", "")
                ptype = "personal" if account["profile_type"] == "personal" else "company"
                comp_id = self._find_or_create_company(name, reg, ptype)

                # Auto-assign all accounts for this profile
                for k, a in coordinator.data.items():
                    if a.get("profile_id") == profile_id:
                        account_key = f"wise::{k}"
                        if account_key not in self.store.assignments:
                            self.store.assign_account(account_key, comp_id)
                            changed = True

        # Phase 2: Discover companies from Blockonomics wallets
        blockonomics_data = self.hass.data.get("blockonomics", {})
        for entry_id, coordinator in blockonomics_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            for key, wallet in coordinator.data.items():
                account_key = f"blockonomics::{key}"
                if account_key in self.store.assignments:
                    continue

                company_number = wallet.get("company_number", "")
                wallet_name = wallet.get("wallet_name", "")

                if company_number:
                    # Try to match by company number
                    comp_id = self._find_or_create_company(
                        wallet_name, company_number, "company"
                    )
                    self.store.assign_account(account_key, comp_id)
                    changed = True

        if changed:
            await self.store.async_save()

        # Phase 3: Aggregate balances per company
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

        # Aggregate Wise accounts
        for entry_id, coordinator in wise_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            shares = entry.options.get("shares", {}) if entry else {}

            for key, account in coordinator.data.items():
                account_key = f"wise::{key}"
                comp_id = self.store.assignments.get(account_key)
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
                    "native_balance": account["balance"],
                    "native_currency": account["currency"],
                    "balance_gbp": gbp,
                    "share": share,
                })

        # Aggregate Blockonomics accounts
        for entry_id, coordinator in blockonomics_data.items():
            if not hasattr(coordinator, "data") or not coordinator.data:
                continue
            entry = self.hass.config_entries.async_get_entry(entry_id)
            shares = entry.options.get("shares", {}) if entry else {}

            for key, wallet in coordinator.data.items():
                account_key = f"blockonomics::{key}"
                comp_id = self.store.assignments.get(account_key)
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
                    "native_balance": wallet["balance_btc"],
                    "native_currency": "BTC",
                    "balance_gbp": gbp,
                    "share": share,
                })

        for comp_id in company_data:
            company_data[comp_id]["total_gbp"] = round(company_data[comp_id]["total_gbp"], 2)
            company_data[comp_id]["wise_total"] = round(company_data[comp_id]["wise_total"], 2)
            company_data[comp_id]["btc_total"] = round(company_data[comp_id]["btc_total"], 2)

        _LOGGER.debug("Companies: %d companies, %d total accounts",
                      len(company_data),
                      sum(c["account_count"] for c in company_data.values()))
        return company_data
