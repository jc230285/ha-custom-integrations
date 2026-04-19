"""Config flow for Blockonomics integration."""

import logging

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

from .const import CONF_SHARES, DEFAULT_SHARE, DOMAIN, WALLETS_URL

_LOGGER = logging.getLogger(__name__)


class BlockonomicsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Blockonomics."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow."""
        return BlockonomicsOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        WALLETS_URL,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "accept": "application/json",
                        },
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            wallets = data.get("data", [])
                            if wallets:
                                return self.async_create_entry(
                                    title=f"Blockonomics ({len(wallets)} wallets)",
                                    data=user_input,
                                )
                            errors["base"] = "no_wallets"
                        elif resp.status in (401, 403):
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


class BlockonomicsOptionsFlow(OptionsFlow):
    """Handle Blockonomics options (share percentages)."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage share options."""
        if user_input is not None:
            shares = {}
            for k, v in user_input.items():
                if k.startswith("share_"):
                    wallet_key = k[6:]
                    shares[wallet_key] = round(float(v), 2)
            return self.async_create_entry(title="", data={CONF_SHARES: shares})

        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if not coordinator or not coordinator.data:
            return self.async_abort(reason="no_data")

        current_shares = self.config_entry.options.get(CONF_SHARES, {})

        schema = {}
        for key, wallet in sorted(
            coordinator.data.items(),
            key=lambda x: x[1]["wallet_name"],
        ):
            current = current_shares.get(key, DEFAULT_SHARE)
            schema[
                vol.Optional(f"share_{key}", default=current, description={"suggested_value": current})
            ] = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
