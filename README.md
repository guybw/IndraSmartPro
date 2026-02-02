# Indra Smart PRO - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A custom Home Assistant integration for the **Indra Smart PRO** EV charger (7.4kW home charger).

Also works with chargers previously branded as **Kaluza**, **ChargedEV**, or **Indra Smart**.

## About the Indra Smart PRO

The [Indra Smart PRO](https://www.indra.co.uk/product/smart-pro/) is a 7.4kW single-phase smart EV charger made by Indra Renewable Technologies Ltd, a British manufacturer. Key features include:

- **7.4kW / 32A** single-phase charging (charge 60kWh in under 9 hours)
- **Solar integration** - charge using excess solar power without additional hardware
- **Smart tariff support** - integrates with thousands of electricity tariffs
- **Type 2 connector** - compatible with all current UK EVs
- **IP65 rated** - suitable for outdoor installation
- **Wi-Fi connected** with optional Ethernet/4G

This integration brings your Indra charger into Home Assistant for local monitoring and control.

## Features

### Controls
- **Boost Charging** - Start/stop boost charging on demand
- **Lock Charger** - Lock/unlock the charger remotely
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
- **Grid Power (CT Clamp)** - Total grid import power (kW)

### Binary Sensors
- **Charging** - Whether the charger is actively charging
- **Cable Connected** - Whether a cable is plugged in

### Diagnostic Sensors
- **Connected** - Charger online status
- **Supply Issue** / **Charge Interrupted** / **Device Fault** / **Low Current Warning** - Fault indicators
- **Boost Active** / **Locked** / **Grid Frequency** - Additional status info

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/guybw/IndraSmartPro` as an **Integration**
4. Search for "Indra EV Charger" and click **Download**
5. **Restart Home Assistant** (required!)

### Manual Installation
1. Copy the `custom_components/indra` folder to your Home Assistant `config/custom_components/` directory
2. **Restart Home Assistant** (required!)

> **Important:** You must restart Home Assistant after installation for the integration to appear.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "**Indra**"
3. Enter your Indra account email address
4. Check your email and click the magic link from Indra
5. Return to Home Assistant and click **Submit**

The integration uses Indra's magic link authentication (passwordless). Your JWT token is stored locally and will be automatically refreshed when needed.

### Options
After setup, you can configure:
- **Update interval** - How often to poll for updates (30-300 seconds, default 60)

## API Reference

The integration uses the following Indra API endpoints (reverse-engineered from the mobile app):

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

## Known Limitations

### Not Yet Implemented
- **Charging Schedules** - The API supports schedules but they're not yet exposed
- **Charge Profiles** - Switch between different charging profiles
- **Tariff Integration** - The API has tariff-related endpoints
- **Historical Data** - Transaction history and historical telemetry

### Known Issues
- Magic link authentication requires manual email click (this is how Indra's auth works)
- Token refresh may require re-authentication if the charger is offline for extended periods

## Compatibility

- **Charger:** Indra Smart PRO 7.4kW (Type 2)
- **Home Assistant:** 2024.1+
- **Python:** 3.11+

Also reported to work with older Kaluza/ChargedEV branded chargers that have been migrated to Indra's platform.


## License

MIT License - see [LICENSE](LICENSE)

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by Indra Renewable Technologies Ltd. Use at your own risk.

---

**Keywords:** Indra Smart PRO, Indra EV charger, Kaluza charger, ChargedEV, Home Assistant EV integration, smart home charging, solar EV charging, 7kW home charger, Type 2 charger, British EV charger
