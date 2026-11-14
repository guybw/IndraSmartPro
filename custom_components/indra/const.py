"""Constants for the Indra EV Charger integration."""

from datetime import timedelta

DOMAIN = "indra"

CONF_EMAIL = "email"
CONF_MOBILE_KEY = "mobile_key"
CONF_JWT_TOKEN = "jwt_token"
CONF_SCAN_INTERVAL = "scan_interval"

API_URL = "https://api.indra.co.uk"

# Seconds to wait for the API before giving up on a request
REQUEST_TIMEOUT = 30

# Refresh the login token this long before it expires (Indra tokens last
# 30 days), and wait this long before trying again if a refresh fails.
TOKEN_REFRESH_BEFORE = timedelta(days=7)
TOKEN_REFRESH_RETRY = timedelta(hours=6)

# Update interval in seconds
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

# Charger states
CHARGER_MODE_IDLE = "IDLE"
CHARGER_MODE_BOOST = "BOOST"
CHARGER_MODE_CHARGING = "CHARGING"
CHARGER_MODE_SOLAR = "SOLAR"

# cableState values that mean no cable is plugged in. Any other value
# (including "disabled" - plugged in but charging not currently permitted,
# and any future values Indra adds) is treated as connected, so this is a
# denylist rather than an allowlist.
CABLE_STATES_UNPLUGGED = frozenset({"", "unplugged", "disconnected", "unknown"})
