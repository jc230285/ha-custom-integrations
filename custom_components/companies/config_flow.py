"""Config flow for Companies integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CompaniesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Companies."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return CompaniesOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Company Management", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={"info": "This integration manages companies and links accounts from Wise and Blockonomics."},
        )


class CompaniesOptionsFlow(OptionsFlow):
    """Handle Companies options — CRUD for companies and account assignments."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self._selected_company: str | None = None

    def _get_store(self):
        """Get the company store."""
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        return data.get("store")

    def _get_coordinator(self):
        """Get the companies coordinator."""
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
        return data.get("coordinator")

    async def async_step_init(self, user_input=None):
        """Show menu."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_company()
            elif action == "edit":
                return await self.async_step_select_edit()
            elif action == "delete":
                return await self.async_step_select_delete()
            elif action == "assign":
                return await self.async_step_select_assign()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(
                        {
                            "add": "Add Company",
                            "edit": "Edit Company",
                            "delete": "Delete Company",
                            "assign": "Assign Accounts to Company",
                        }
                    ),
                }
            ),
        )

    async def async_step_add_company(self, user_input=None):
        """Add a new company."""
        if user_input is not None:
            store = self._get_store()
            if store:
                store.add_company(
                    user_input["name"],
                    user_input.get("registration_number", ""),
                    user_input["company_type"],
                )
                await store.async_save()
                coordinator = self._get_coordinator()
                if coordinator:
                    await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="add_company",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("registration_number", default=""): str,
                    vol.Required("company_type", default="company"): vol.In(
                        {"company": "Company", "personal": "Personal"}
                    ),
                }
            ),
        )

    async def async_step_select_edit(self, user_input=None):
        """Select a company to edit."""
        store = self._get_store()
        if not store or not store.companies:
            return self.async_abort(reason="no_companies")

        if user_input is not None:
            self._selected_company = user_input["company"]
            return await self.async_step_edit_company()

        companies = {cid: c["name"] for cid, c in store.companies.items()}
        return self.async_show_form(
            step_id="select_edit",
            data_schema=vol.Schema(
                {vol.Required("company"): vol.In(companies)}
            ),
        )

    async def async_step_edit_company(self, user_input=None):
        """Edit a company."""
        store = self._get_store()
        comp = store.companies.get(self._selected_company, {})

        if user_input is not None:
            store.edit_company(
                self._selected_company,
                user_input["name"],
                user_input.get("registration_number", ""),
                user_input["company_type"],
            )
            await store.async_save()
            coordinator = self._get_coordinator()
            if coordinator:
                await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data=self.config_entry.options)

        return self.async_show_form(
            step_id="edit_company",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=comp.get("name", "")): str,
                    vol.Optional("registration_number", default=comp.get("registration_number", "")): str,
                    vol.Required("company_type", default=comp.get("type", "company")): vol.In(
                        {"company": "Company", "personal": "Personal"}
                    ),
                }
            ),
        )

    async def async_step_select_delete(self, user_input=None):
        """Select a company to delete."""
        store = self._get_store()
        if not store or not store.companies:
            return self.async_abort(reason="no_companies")

        if user_input is not None:
            store.delete_company(user_input["company"])
            await store.async_save()
            coordinator = self._get_coordinator()
            if coordinator:
                await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data=self.config_entry.options)

        companies = {cid: c["name"] for cid, c in store.companies.items()}
        return self.async_show_form(
            step_id="select_delete",
            data_schema=vol.Schema(
                {vol.Required("company"): vol.In(companies)}
            ),
        )

    async def async_step_select_assign(self, user_input=None):
        """Select a company to assign accounts to."""
        store = self._get_store()
        if not store or not store.companies:
            return self.async_abort(reason="no_companies")

        if user_input is not None:
            self._selected_company = user_input["company"]
            return await self.async_step_assign_accounts()

        companies = {cid: c["name"] for cid, c in store.companies.items()}
        return self.async_show_form(
            step_id="select_assign",
            data_schema=vol.Schema(
                {vol.Required("company"): vol.In(companies)}
            ),
        )

    async def async_step_assign_accounts(self, user_input=None):
        """Assign accounts to the selected company."""
        store = self._get_store()

        if user_input is not None:
            selected = user_input.get("accounts", [])
            # Remove old assignments for this company
            old_keys = [k for k, v in store.assignments.items() if v == self._selected_company]
            for k in old_keys:
                store.unassign_account(k)
            # Add new assignments
            for account_key in selected:
                store.assign_account(account_key, self._selected_company)
            await store.async_save()
            coordinator = self._get_coordinator()
            if coordinator:
                await coordinator.async_request_refresh()
            return self.async_create_entry(title="", data=self.config_entry.options)

        # Build list of all available accounts
        all_accounts = {}
        currently_assigned = [
            k for k, v in store.assignments.items() if v == self._selected_company
        ]

        wise_data = self.hass.data.get("wise", {})
        for coordinator in wise_data.values():
            if hasattr(coordinator, "data") and coordinator.data:
                for key, account in coordinator.data.items():
                    label = f"Wise: {account['profile_name']} {account.get('balance_name', '')} {account['currency']}".strip()
                    all_accounts[f"wise::{key}"] = label

        blockonomics_data = self.hass.data.get("blockonomics", {})
        for coordinator in blockonomics_data.values():
            if hasattr(coordinator, "data") and coordinator.data:
                for key, wallet in coordinator.data.items():
                    label = f"BTC: {wallet['wallet_name']}"
                    all_accounts[f"blockonomics::{key}"] = label

        if not all_accounts:
            return self.async_abort(reason="no_accounts")

        return self.async_show_form(
            step_id="assign_accounts",
            data_schema=vol.Schema(
                {
                    vol.Optional("accounts", default=currently_assigned): vol.All(
                        [vol.In(all_accounts)],
                    ),
                }
            ),
            description_placeholders={"company": store.companies.get(self._selected_company, {}).get("name", "")},
        )
