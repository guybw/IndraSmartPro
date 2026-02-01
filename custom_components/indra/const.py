"""Constants for the Indra EV Charger integration."""

DOMAIN = "indra"

CONF_EMAIL = "email"
CONF_MOBILE_KEY = "mobile_key"
CONF_JWT_TOKEN = "jwt_token"
CONF_SCAN_INTERVAL = "scan_interval"

API_URL = "https://api.indra.co.uk"

# Update interval in seconds
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 300

# Charger states
CHARGER_MODE_IDLE = "IDLE"
CHARGER_MODE_BOOST = "BOOST"
CHARGER_MODE_CHARGING = "CHARGING"
CHARGER_MODE_SOLAR = "SOLAR"

CABLE_STATE_NOT_CHARGING = "notCharging"
CABLE_STATE_CHARGING = "charging"
CABLE_STATE_CONNECTED = "connected"
