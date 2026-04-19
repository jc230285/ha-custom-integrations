"""Constants for the Wise integration."""

DOMAIN = "wise"
PLATFORMS = ["sensor"]

WISE_API_BASE = "https://api.wise.com"
WISE_PROFILES_URL = f"{WISE_API_BASE}/v2/profiles"
WISE_BALANCES_URL = f"{WISE_API_BASE}/v4/profiles"
EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest/GBP"

CONF_SHARES = "shares"
DEFAULT_SHARE = 100.00
