"""Persistent storage for company data."""

import logging
import uuid

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


class CompanyStore:
    """Manage persistent company storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict = {"companies": {}, "assignments": {}}

    @property
    def companies(self) -> dict:
        """Return all companies."""
        return self._data.get("companies", {})

    @property
    def assignments(self) -> dict:
        """Return all account-to-company assignments."""
        return self._data.get("assignments", {})

    async def async_load(self) -> None:
        """Load data from storage."""
        data = await self._store.async_load()
        if data:
            self._data = data
            _LOGGER.debug("Loaded %d companies, %d assignments", len(self.companies), len(self.assignments))

    async def async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self._data)

    def add_company(self, name: str, registration_number: str, company_type: str) -> str:
        """Add a company and return its ID."""
        company_id = uuid.uuid4().hex[:12]
        self._data["companies"][company_id] = {
            "name": name,
            "registration_number": registration_number,
            "type": company_type,
        }
        return company_id

    def edit_company(self, company_id: str, name: str, registration_number: str, company_type: str) -> None:
        """Edit an existing company."""
        if company_id in self._data["companies"]:
            self._data["companies"][company_id] = {
                "name": name,
                "registration_number": registration_number,
                "type": company_type,
            }

    def delete_company(self, company_id: str) -> None:
        """Delete a company and its assignments."""
        self._data["companies"].pop(company_id, None)
        self._data["assignments"] = {
            k: v for k, v in self._data["assignments"].items() if v != company_id
        }

    def assign_account(self, account_key: str, company_id: str) -> None:
        """Assign an account to a company."""
        self._data["assignments"][account_key] = company_id

    def unassign_account(self, account_key: str) -> None:
        """Remove an account assignment."""
        self._data["assignments"].pop(account_key, None)

    def get_company_for_account(self, account_key: str, registration_number: str = "") -> str | None:
        """Get company ID for an account. Check explicit assignment first, then auto-match by reg number."""
        if account_key in self._data["assignments"]:
            return self._data["assignments"][account_key]

        if registration_number:
            for comp_id, comp in self._data["companies"].items():
                if comp["registration_number"] and comp["registration_number"] == registration_number:
                    return comp_id

        return None
