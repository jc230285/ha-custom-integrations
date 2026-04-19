"""Constants for the Wise integration."""

DOMAIN = "wise"
PLATFORMS = ["sensor"]
DEFAULT_UPDATE_INTERVAL = 30  # minutes

WISE_API_BASE = "https://api.wise.com"
WISE_PROFILES_URL = f"{WISE_API_BASE}/v2/profiles"
WISE_BALANCES_URL = f"{WISE_API_BASE}/v1/borderless-accounts"
EXCHANGE_RATE_URL = "https://open.er-api.com/v6/latest/GBP"
