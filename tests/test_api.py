"""Tests for the Indra API client against real local sockets.

These use real HTTP over 127.0.0.1 (no mocked `requests`), so they show
how the client behaves when the API is slow, down, or returns errors.
"""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from custom_components.indra import api as api_module
from custom_components.indra.api import IndraApi, IndraApiError, IndraAuthError

TOKEN = "t" * 64
NEW_TOKEN = "n" * 64


class _StubHandler(BaseHTTPRequestHandler):
    """Answers from the server's `routes` table and records each request."""

    def _handle(self):
        self.server.calls.append(
            (self.command, self.path, self.headers.get("Authorization"))
        )
        status, body = self.server.routes.get(
            (self.command, self.path), (404, {"error": "not found"})
        )
        payload = body if isinstance(body, str) else json.dumps(body)
        data = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = _handle

    def log_message(self, *args):  # keep test output quiet
        pass


@pytest.fixture
def stub(socket_enabled, monkeypatch):
    """A local HTTP server standing in for api.indra.co.uk."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    server.routes = {}
    server.calls = []
    thread = threading.Thread(target=server.serve_forever, name="indra-stub")
    thread.start()
    monkeypatch.setattr(api_module, "API_URL", f"http://127.0.0.1:{server.server_port}")
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def black_hole(socket_enabled, monkeypatch):
    """A server that accepts TCP connections but never answers.

    The kernel completes the handshake from the listen backlog, so a client
    connects fine and then waits for a response that never comes - the
    failure mode that froze the integration on 2026-11-06.
    """
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    monkeypatch.setattr(api_module, "API_URL", f"http://127.0.0.1:{sock.getsockname()[1]}")
    monkeypatch.setattr(api_module, "REQUEST_TIMEOUT", 0.5, raising=False)
    yield sock
    sock.close()


@pytest.fixture
def refused(socket_enabled, monkeypatch):
    """A port with nothing listening (connection refused)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    monkeypatch.setattr(api_module, "API_URL", f"http://127.0.0.1:{port}")


def _api() -> IndraApi:
    return IndraApi("user@example.com", mobile_key="mk", jwt_token=TOKEN)


# -- behaviour that must not change ------------------------------------------


def test_get_devices_statuses(stub):
    api = _api()
    stub.routes[("GET", "/api/devices")] = (200, [{"deviceUID": "d1"}])
    assert api.get_devices() == [{"deviceUID": "d1"}]
    assert stub.calls[-1] == ("GET", "/api/devices", f"Bearer {TOKEN}")

    stub.routes[("GET", "/api/devices")] = (401, {})
    with pytest.raises(IndraAuthError):
        api.get_devices()

    stub.routes[("GET", "/api/devices")] = (500, {})
    with pytest.raises(IndraApiError) as err:
        api.get_devices()
    assert not isinstance(err.value, IndraAuthError)


def test_properties_statuses(stub):
    api = _api()
    path = "/api/command/properties/d1"
    stub.routes[("GET", path)] = (200, {"boost": {"settingValue": "False"}})
    assert api.get_device_properties("d1") == {"boost": {"settingValue": "False"}}
    stub.routes[("GET", path)] = (401, {})
    with pytest.raises(IndraAuthError):
        api.get_device_properties("d1")
    stub.routes[("GET", path)] = (500, {})
    assert api.get_device_properties("d1") == {}


def test_soft_getters_return_defaults_on_http_errors(stub):
    api = _api()
    stub.routes[("GET", "/api/telemetry/devices/d1/latest")] = (200, {"state": "idle"})
    assert api.get_device_telemetry("d1") == {"state": "idle"}
    # Everything else is unrouted, so the stub answers 404.
    assert api.get_telemetry("loc1") == {}
    assert api.get_solar_status("d1") == {}
    assert api.get_schedules() == []
    assert api.get_current_transaction("d1") is None
    paths = [path for _, path, _ in stub.calls]
    assert paths == [
        "/api/telemetry/devices/d1/latest",
        "/api/v1/installations/loc1/telemetry/latest",
        "/api/devices/d1/solar",
        "/api/schedules",
        "/api/reports/transactions/latest",
    ]


def test_current_transaction_picks_this_device(stub):
    api = _api()
    stub.routes[("GET", "/api/reports/transactions/latest")] = (
        200,
        [{"deviceUId": "other", "n": 1}, {"deviceUId": "d1", "n": 2}],
    )
    assert api.get_current_transaction("d1") == {"deviceUId": "d1", "n": 2}
    assert api.get_current_transaction("nope") is None


def test_commands(stub):
    api = _api()
    stub.routes[("POST", "/api/command/boost/start/d1")] = (202, {})
    stub.routes[("POST", "/api/command/boost/stop/d1")] = (200, {})
    stub.routes[("PUT", "/api/devices/d1/solar/enable")] = (200, {})
    stub.routes[("PUT", "/api/devices/d1/solar/disable")] = (202, {})  # only 200 counts
    stub.routes[("PUT", "/lock/d1")] = (200, {})
    stub.routes[("PUT", "/unlock/d1")] = (500, {})
    assert api.start_boost("d1") is True
    assert api.stop_boost("d1") is True
    assert api.enable_solar("d1") is True
    assert api.disable_solar("d1") is False
    assert api.lock_charger("d1") is True
    assert api.unlock_charger("d1") is False


def test_auth_flow(stub):
    api = IndraApi("user@example.com", mobile_key="mk")
    assert api.validate_token() is False  # no token: no request made
    assert stub.calls == []

    stub.routes[("GET", "/api/user/check/user@example.com/mk/1")] = (200, '"abc123"')
    assert api.request_magic_link() == "abc123"

    stub.routes[("GET", "/api/user/token/user@example.com/mk/abc123/1")] = (200, '"short"')
    assert api.get_token("abc123") is None
    stub.routes[("GET", "/api/user/token/user@example.com/mk/abc123/1")] = (200, f'"{TOKEN}"')
    assert api.get_token("abc123") == TOKEN

    stub.routes[("GET", "/api/authorize/validate")] = (200, {})
    assert api.validate_token() is True
    assert stub.calls[-1][2] == f"Bearer {TOKEN}"

    stub.routes[("GET", "/api/authorize/refresh")] = (200, f'"{NEW_TOKEN}"')
    assert api.refresh_token() is True
    assert api.jwt_token == NEW_TOKEN
    api.validate_token()
    assert stub.calls[-1][2] == f"Bearer {NEW_TOKEN}"

    stub.routes[("GET", "/api/authorize/refresh")] = (401, {})
    assert api.refresh_token() is False

    stub.routes[("GET", "/api/user/check/user@example.com/mk/1")] = (500, {})
    with pytest.raises(IndraApiError):
        api.request_magic_link()


# -- new behaviour: a hung or unreachable API can't block forever -------------


@pytest.mark.timeout(15)
@pytest.mark.parametrize(
    "call",
    [
        lambda api: api.get_devices(),
        lambda api: api.get_device_properties("d1"),
        lambda api: api.get_device_telemetry("d1"),
        lambda api: api.get_schedules(),
        lambda api: api.validate_token(),
        lambda api: api.refresh_token(),
    ],
    ids=["devices", "properties", "telemetry", "schedules", "validate", "refresh"],
)
def test_unanswered_request_times_out(black_hole, call):
    started = time.monotonic()
    with pytest.raises(IndraApiError):
        call(_api())
    assert time.monotonic() - started < 5


@pytest.mark.timeout(15)
def test_unanswered_command_returns_false(black_hole):
    started = time.monotonic()
    assert _api().start_boost("d1") is False
    assert time.monotonic() - started < 5


def test_connection_refused_is_an_api_error(refused):
    with pytest.raises(IndraApiError):
        _api().get_devices()
    assert _api().lock_charger("d1") is False


def test_every_request_passes_a_timeout(stub, monkeypatch):
    """Guard against a future method calling the session without a timeout."""
    api = _api()
    seen = []
    real_request = api._session.request

    def spy(method, url, **kwargs):
        seen.append(kwargs.get("timeout"))
        return real_request(method, url, **kwargs)

    monkeypatch.setattr(api._session, "request", spy)
    for name in ("get", "post", "put", "delete", "patch"):
        monkeypatch.setattr(
            api._session, name, lambda *a, **k: pytest.fail("bypassed _request")
        )

    for call in (
        lambda: api.get_device_properties("d1"),
        lambda: api.get_telemetry("loc1"),
        lambda: api.get_solar_status("d1"),
        lambda: api.get_schedules(),
        lambda: api.get_device_telemetry("d1"),
        lambda: api.get_current_transaction("d1"),
        lambda: api.validate_token(),
        lambda: api.refresh_token(),
        lambda: api.get_token("h"),
        lambda: api.start_boost("d1"),
        lambda: api.stop_boost("d1"),
        lambda: api.enable_solar("d1"),
        lambda: api.disable_solar("d1"),
        lambda: api.lock_charger("d1"),
        lambda: api.unlock_charger("d1"),
    ):
        call()
    with pytest.raises(IndraApiError):
        api.get_devices()  # 404 from the stub
    with pytest.raises(IndraApiError):
        api.request_magic_link()  # 404 from the stub
    assert len(seen) == 17
    assert all(t == api_module.REQUEST_TIMEOUT for t in seen)
