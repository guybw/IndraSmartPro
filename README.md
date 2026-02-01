# Indra EV Charger Integration for Home Assistant

A custom Home Assistant integration for the **Indra Smart PRO** EV charger (formerly Kaluza/ChargedEV).

## Features

### Controls
- **Boost Charging** - Start/stop boost charging on demand
- **Lock Charger** - Lock/unlock the charger
- **Solar Matching** - Enable/disable solar matching mode

### Sensors
- **Charger Mode** - Current mode (IDLE, BOOST, CHARGING, SOLAR)
- **Charger State** - Cable state (charging, notCharging, connected)
- **Charging Power** - Real-time charging power (kW)
- **Charging Current** - Current draw (A)
- **Voltage** - Mains voltage (V)
- **Temperature** - Charger temperature (°C)
- **Session Energy** - Energy added this charging session (kWh)
- **Total Energy** - Lifetime energy delivered (kWh)
- **Grid Power (CT Clamp)** - Total grid import power (kWh)

### Binary Sensors
- **Charging** - Whether the charger is actively charging
- **Cable Connected** - Whether a cable is plugged in

### Diagnostic Sensors
- **Connected** - Charger online status
- **Supply Issue** / **Charge Interrupted** / **Device Fault** / **Low Current Warning** - Fault condition indicators
- **Boost Active** / **Locked** / **Grid Frequency** - Additional status info

## Installation

### HACS (Recommended)
1. Add this repository as a custom repository in HACS
2. Search for "Indra EV Charger" and install
3. Restart Home Assistant

### Manual Installation
1. Copy the `custom_components/indra` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "**Indra**"
3. Enter your Indra account email address
4. Check your email and click the magic link
5. Return to Home Assistant and click **Submit**

The integration uses Indra's magic link authentication (passwordless). Your JWT token is stored locally and will be automatically refreshed when needed.

### Options
After setup, you can configure:
- **Update interval** - How often to poll for updates (30-300 seconds, default 60)

## Standalone CLI Client

A standalone Python client (`indra_client.py`) is included for testing and automation outside Home Assistant:

```bash
# Request authentication magic link
python indra_client.py auth

# After clicking magic link, complete auth
python indra_client.py auth <magic_link_url>

# List devices
python indra_client.py devices

# Get device status
python indra_client.py status

# Get telemetry data
python indra_client.py telemetry

# Start/stop boost charging
python indra_client.py boost start
python indra_client.py boost stop

# Get solar status
python indra_client.py solar

# Get charging schedules
python indra_client.py schedules

# Get recent transactions
python indra_client.py transactions
```

## API Endpoints Discovered

The integration uses the following Indra API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/user/check/{email}/{mobileKey}/{os}` | GET | Request magic link |
| `/api/user/token/{email}/{mobileKey}/{hash}/{os}` | GET | Get JWT token |
| `/api/devices` | GET | List devices |
| `/api/command/properties/{deviceUid}` | GET | Get device properties |
| `/api/telemetry/devices/{deviceUid}/latest` | GET | Get real-time telemetry |
| `/api/command/boost/start/{deviceUid}` | POST | Start boost |
| `/api/command/boost/stop/{deviceUid}` | POST | Stop boost |
| `/lock/{deviceUid}` | PUT | Lock charger |
| `/unlock/{deviceUid}` | PUT | Unlock charger |
| `/api/devices/{deviceUid}/solar/enable` | PUT | Enable solar |
| `/api/devices/{deviceUid}/solar/disable` | PUT | Disable solar |
| `/api/reports/transactions/latest` | GET | Get charging sessions |

Full API documentation: `swagger.json` (from https://api.indra.co.uk/swagger)

## Known Limitations / Future Work

### Not Yet Implemented
- **Charging Schedules** - The API supports schedules but they're not yet exposed in the integration
- **Charge Profiles** - Switch between different charging profiles
- **Tariff Integration** - The API has tariff-related endpoints
- **Historical Data** - Transaction history and historical telemetry

### Known Issues
- Magic link authentication requires manual email click (no way around this)
- Token refresh may require re-authentication if the charger is offline for extended periods

## Compatibility

- **Tested with:** Indra Smart PRO 7kW (tethered, Type 2)
- **Home Assistant:** 2024.1+
- **Python:** 3.11+

## Credits

- API reverse-engineered from the Indra mobile app
- Original Kaluza integration attempt from 2023 (deprecated - old API no longer works)

## License

MIT License - see [LICENSE](LICENSE)

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Indra Renewable Technologies Ltd. Use at your own risk.
