"""Config flow for Wise integration."""

import logging

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

from .const import CONF_SHARES, DEFAULT_SHARE, DOMAIN, WISE_PROFILES_URL

_LOGGER = logging.getLogger(__name__)


class WiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wise."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return WiseOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        WISE_PROFILES_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                    ) as resp:
                        if resp.status == 200:
                            profiles = await resp.json()
                            if profiles:
                                name = profiles[0].get("fullName", "Wise")
                                return self.async_create_entry(
                                    title=f"Wise ({name})", data=user_input
                                )
                            errors["base"] = "no_profiles"
                        elif resp.status == 401:
                            errors["base"] = "invalid_auth"
                        else:
                            errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class WiseOptionsFlow(OptionsFlow):
    """Handle Wise options (share percentages)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage share options."""
        if user_input is not None:
            shares = {}
            for k, v in user_input.items():
                if k.startswith("share_"):
                    account_key = k[6:]
                    shares[account_key] = round(float(v), 2)
            return self.async_create_entry(title="", data={CONF_SHARES: shares})

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if not coordinator or not coordinator.data:
            return self.async_abort(reason="no_data")

        current_shares = self.config_entry.options.get(CONF_SHARES, {})

        schema = {}
        for key, account in sorted(
            coordinator.data.items(),
            key=lambda x: x[1]["profile_name"],
        ):
            current = current_shares.get(key, DEFAULT_SHARE)
            label = f"{account['profile_name']} {account['currency']}"
            schema[
                vol.Optional(f"share_{key}", default=current, description={"suggested_value": current})
            ] = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
