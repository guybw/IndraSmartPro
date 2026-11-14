"""Indra EV Charger API client for Home Assistant."""

import logging
import uuid
import requests
from typing import Any

from .const import API_URL, REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class IndraApiError(Exception):
    """Exception for Indra API errors."""


class IndraAuthError(IndraApiError):
    """Exception for authentication errors."""


class IndraApi:
    """Indra EV Charger API client."""

    def __init__(self, email: str, mobile_key: str = None, jwt_token: str = None):
        """Initialize the API client."""
        self.email = email
        self.mobile_key = mobile_key or str(uuid.uuid4())
        self.jwt_token = jwt_token
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "HomeAssistant/IndraIntegration",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        if jwt_token:
            self._session.headers["Authorization"] = f"Bearer {jwt_token}"

    def _request(self, method: str, url: str) -> requests.Response:
        """Send a request with a timeout.

        Without a timeout a request that never gets an answer blocks its
        executor thread, and with it the coordinator update, for good.
        Network errors and timeouts are raised as IndraApiError.
        """
        try:
            return self._session.request(method, url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as err:
            raise IndraApiError(f"{method} {url} failed: {err}") from err

    def _command(self, method: str, url: str, ok_statuses: tuple[int, ...]) -> bool:
        """Send a command. Returns False if it fails or can't be sent."""
        try:
            response = self._request(method, url)
        except IndraApiError as err:
            _LOGGER.warning("%s", err)
            return False
        return response.status_code in ok_statuses

    def request_magic_link(self) -> str:
        """Request a magic link email. Returns hash for token polling."""
        url = f"{API_URL}/api/user/check/{self.email}/{self.mobile_key}/1"
        response = self._request("GET", url)

        if response.status_code == 200:
            return response.text.strip().strip('"')
        raise IndraApiError(f"Failed to request magic link: {response.status_code}")

    def get_token(self, hash_val: str) -> str | None:
        """Poll for JWT token after magic link verification."""
        url = f"{API_URL}/api/user/token/{self.email}/{self.mobile_key}/{hash_val}/1"
        response = self._request("GET", url)

        if response.status_code == 200:
            token = response.text.strip().strip('"')
            if len(token) > 50:
                self.jwt_token = token
                self._session.headers["Authorization"] = f"Bearer {token}"
                return token
        return None

    def validate_token(self) -> bool:
        """Check if the current token is valid."""
        if not self.jwt_token:
            return False

        response = self._request("GET", f"{API_URL}/api/authorize/validate")
        return response.status_code == 200

    def refresh_token(self) -> bool:
        """Refresh the JWT token."""
        response = self._request("GET", f"{API_URL}/api/authorize/refresh")
        if response.status_code == 200:
            token = response.text.strip().strip('"')
            if len(token) > 50:
                self.jwt_token = token
                self._session.headers["Authorization"] = f"Bearer {token}"
                return True
        return False

    def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices."""
        response = self._request("GET", f"{API_URL}/api/devices")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise IndraAuthError("Authentication failed")
        raise IndraApiError(f"Failed to get devices: {response.status_code}")

    def get_device_properties(self, device_uid: str) -> dict[str, Any]:
        """Get device properties/status."""
        response = self._request("GET", f"{API_URL}/api/command/properties/{device_uid}")
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise IndraAuthError("Authentication failed")
        return {}

    def get_telemetry(self, location_uid: str) -> dict[str, Any]:
        """Get latest telemetry data."""
        response = self._request(
            "GET", f"{API_URL}/api/v1/installations/{location_uid}/telemetry/latest"
        )
        if response.status_code == 200:
            return response.json()
        return {}

    def start_boost(self, device_uid: str) -> bool:
        """Start boost charging."""
        return self._command("POST", f"{API_URL}/api/command/boost/start/{device_uid}", (200, 202))

    def stop_boost(self, device_uid: str) -> bool:
        """Stop boost charging."""
        return self._command("POST", f"{API_URL}/api/command/boost/stop/{device_uid}", (200, 202))

    def enable_solar(self, device_uid: str) -> bool:
        """Enable solar matching."""
        return self._command("PUT", f"{API_URL}/api/devices/{device_uid}/solar/enable", (200,))

    def disable_solar(self, device_uid: str) -> bool:
        """Disable solar matching."""
        return self._command("PUT", f"{API_URL}/api/devices/{device_uid}/solar/disable", (200,))

    def get_solar_status(self, device_uid: str) -> dict[str, Any]:
        """Get solar status."""
        response = self._request("GET", f"{API_URL}/api/devices/{device_uid}/solar")
        if response.status_code == 200:
            return response.json()
        return {}

    def lock_charger(self, device_uid: str) -> bool:
        """Lock the charger."""
        # Note: Lock endpoint doesn't have /api/ prefix
        return self._command("PUT", f"{API_URL}/lock/{device_uid}", (200,))

    def unlock_charger(self, device_uid: str) -> bool:
        """Unlock the charger."""
        # Note: Unlock endpoint doesn't have /api/ prefix
        return self._command("PUT", f"{API_URL}/unlock/{device_uid}", (200,))

    def get_schedules(self) -> list[dict[str, Any]]:
        """Get charging schedules."""
        response = self._request("GET", f"{API_URL}/api/schedules")
        if response.status_code == 200:
            return response.json()
        return []

    def get_device_telemetry(self, device_uid: str) -> dict[str, Any]:
        """Get device telemetry data (power, current, voltage, etc.)."""
        response = self._request(
            "GET", f"{API_URL}/api/telemetry/devices/{device_uid}/latest"
        )
        if response.status_code == 200:
            return response.json()
        return {}

    def get_current_transaction(self, device_uid: str) -> dict[str, Any] | None:
        """Get the current/most recent charging transaction."""
        response = self._request("GET", f"{API_URL}/api/reports/transactions/latest")
        if response.status_code == 200:
            transactions = response.json()
            # Find transaction for this device that's still active (no end time or recent)
            for txn in transactions:
                if txn.get("deviceUId") == device_uid:
                    return txn
        return None
