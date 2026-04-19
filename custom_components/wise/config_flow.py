"""Config flow for Wise integration."""

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN, WISE_PROFILES_URL


class WiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wise."""

    VERSION = 1

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
                                name = profiles[0].get("details", {}).get(
                                    "firstName", "Wise"
                                )
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
