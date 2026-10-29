# api_client.py — CityMind 2D: Backend API Client
# Wraps the FastAPI backend endpoints with timeouts, validation,
# and clean error handling. All calls return (data_or_None, error_str_or_None).

import requests
import threading
import time
from typing import Optional, Tuple, Callable


BASE_URL_DEFAULT = "http://127.0.0.1:8000"
TIMEOUT = 8.0          # seconds per request
RETRY_DELAY = 1.5      # seconds between reconnect attempts


class APIError(Exception):
    pass


class CityMindClient:
    """
    Thread-safe HTTP client for the CityMind FastAPI backend.

    Design decisions:
    - Returns (result, error) tuples — never raises in normal use.
    - All network calls have explicit timeouts.
    - Background poller keeps state fresh without blocking the UI thread.
    - Mutation methods validate responses before signalling success.
    """

    def __init__(self, base_url: str = BASE_URL_DEFAULT):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._lock = threading.Lock()
        self._read_session = requests.Session()
        self._read_lock = threading.Lock()
        self._route_session = requests.Session()
        self._route_lock = threading.Lock()

    def close(self):
        for session in (self._session, self._read_session, self._route_session):
            session.close()

    # ── Low-level helpers ─────────────────────────────────────────────────────

    def _get(self, path: str) -> Tuple[Optional[dict], Optional[str]]:
        try:
            with self._read_lock:
                r = self._read_session.get(f"{self.base_url}{path}", timeout=TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, dict):
                return None, "Unexpected response: expected a JSON object"
            return payload, None
        except requests.exceptions.ConnectionError:
            return None, "Cannot connect to backend. Is uvicorn running?"
        except requests.exceptions.Timeout:
            return None, f"Request timed out ({TIMEOUT}s): GET {path}"
        except requests.exceptions.HTTPError as e:
            return None, f"HTTP {e.response.status_code}: GET {path}"
        except Exception as e:
            return None, f"Unexpected error (GET {path}): {e}"

    def _post(self, path: str, json_body: dict = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            session, lock = (self._route_session, self._route_lock) if path == "/simulation/route" else (self._session, self._lock)
            with lock:
                r = session.post(
                    f"{self.base_url}{path}",
                    json=json_body,
                    timeout=TIMEOUT
                )
            r.raise_for_status()
            payload = r.json()
            if not isinstance(payload, dict):
                return None, "Unexpected response: expected a JSON object"
            return payload, None
        except requests.exceptions.ConnectionError:
            return None, "Cannot connect to backend."
        except requests.exceptions.Timeout:
            return None, f"Request timed out ({TIMEOUT}s): POST {path}"
        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = e.response.json().get("detail", e.response.text[:200])
            except Exception:
                pass
            return None, f"HTTP {e.response.status_code}: POST {path} — {body}"
        except Exception as e:
            return None, f"Unexpected error (POST {path}): {e}"

    # ── Health ────────────────────────────────────────────────────────────────

    def ping(self) -> Tuple[bool, Optional[str]]:
        """Quick health check. Returns (ok, error)."""
        data, err = self._get("/")
        if err:
            return False, err
        return True, None

    # ── Read endpoints ────────────────────────────────────────────────────────

    def get_state(self) -> Tuple[Optional[dict], Optional[str]]:
        """GET /state — full simulation state including embedded graph."""
        return self._get("/state")

    def get_graph(self) -> Tuple[Optional[dict], Optional[str]]:
        """GET /graph — graph-only payload."""
        return self._get("/graph")

    # ── Mutation endpoints ────────────────────────────────────────────────────

    def restart(self) -> Tuple[Optional[dict], Optional[str]]:
        """POST /start — restart/reinitialize the simulation."""
        data, err = self._post("/start")
        if err:
            return None, err
        if not isinstance(data, dict):
            return None, "Unexpected response format from /start"
        return data, None

    def step(self) -> Tuple[Optional[dict], Optional[str]]:
        """POST /simulation/step — advance one simulation step."""
        data, err = self._post("/simulation/step")
        if err:
            return None, err
        if not isinstance(data, dict):
            return None, "Unexpected response format from /simulation/step"
        return data, None

    def flood_node(self, node_id: int) -> Tuple[Optional[dict], Optional[str]]:
        """POST /simulation/flood_node/{node_id} — God Mode flood."""
        if type(node_id) is not int or node_id < 0:
            return None, f"Invalid node_id: {node_id!r}"
        data, err = self._post(f"/simulation/flood_node/{node_id}")
        if err:
            return None, err
        if not isinstance(data, dict):
            return None, f"Unexpected response from flood_node/{node_id}"
        return data, None

    def block_road(self, node_a: int, node_b: int) -> Tuple[Optional[dict], Optional[str]]:
        """POST /simulation/block_road/{node_a}/{node_b} — block a road segment."""
        if type(node_a) is not int or type(node_b) is not int:
            return None, f"Invalid node IDs: {node_a!r}, {node_b!r}"
        data, err = self._post(f"/simulation/block_road/{node_a}/{node_b}")
        if err:
            return None, err
        return data, None

    def unblock_road(self, node_a: int, node_b: int) -> Tuple[Optional[dict], Optional[str]]:
        """POST /simulation/unblock_road/{node_a}/{node_b} — reopen a blocked road."""
        if type(node_a) is not int or type(node_b) is not int:
            return None, f"Invalid node IDs: {node_a!r}, {node_b!r}"
        data, err = self._post(f"/simulation/unblock_road/{node_a}/{node_b}")
        if err:
            return None, err
        return data, None

    def calculate_route(self, src: int, dst: int, travel_mode='normal') -> Tuple[Optional[dict], Optional[str]]:
        """
        F16/F41: POST /simulation/route — ask backend A* router for route between src and dst.
        """
        if type(src) is not int or type(dst) is not int:
            return None, f"Invalid route endpoints: src={src!r}, dst={dst!r}"
        data, err = self._post("/simulation/route", {"src": src, "dst": dst, 'travel_mode':travel_mode})
        if err:
            return None, err
        return data, None

    def dispatch_emergency(self, label):
        return self._post('/simulation/emergencies', {'node': label})


    def dispatch_helicopter(self, label):
        return self._post('/simulation/helicopter/dispatch', {'node': label})

    def police_action(self, action, payload=None):
        paths={'report':'reports','settings':'settings','plan':'stations/plan','station':'stations','compare':'compare'}
        if action=='medical':
            return self._post(f"/simulation/police/reports/{payload['report_id']}/medical_rescue")
        if action not in paths:
            return None,'Unknown police action'
        return self._post('/simulation/police/'+paths[action],payload)

    def unleash_gate(self, node_id, intensity):
        return self._post('/simulation/disasters/gate', {'node_id':node_id,'intensity':intensity})

    def preview_gate(self, node_id, intensity):
        return self._post('/simulation/disasters/gate/preview', {'node_id':node_id,'intensity':intensity})

    def clear_gates(self):
        return self._post('/simulation/disasters/gates/clear')

    def set_landings(self, labels):
        return self._post('/simulation/helicopter/landings', {'nodes': labels})

    def relocate_helicopter(self):
        return self._post('/simulation/helicopter/relocate')

    def city_event_settings(self, settings):
        return self._post('/simulation/events/settings', settings)

    def refuel_helicopter(self):
        return self._post('/simulation/helicopter/refuel')

    def add_medical_center(self, label):
        return self._post('/simulation/medical_centers', {'node': label})

    def optimization(self, action):
        if action not in ("start", "pause", "reset"):
            return None, "Unknown optimization action"
        return self._post(f"/simulation/optimization/{action}", {"runs": 1} if action == "start" else None)

    def export_metrics(self):
        try:
            with self._read_lock:
                response = self._read_session.get(f"{self.base_url}/metrics/export", timeout=TIMEOUT)
            response.raise_for_status()
            return response.text, None
        except requests.RequestException as exc:
            return None, f"Metrics export failed: {exc}"


class BackgroundPoller:
    """One wakeable poll loop with automatic reconnect and bounded backoff."""
    def __init__(self, client, on_update, on_error, interval=1.0):
        self._client, self._on_update, self._on_error = client, on_update, on_error
        self._interval = interval
        self._stop_evt = threading.Event()
        self._wake_evt = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="citymind-poller", daemon=True)
        self._thread.start()

    def request_refresh(self):
        self._wake_evt.set()

    def stop(self, timeout=0.25):
        self._stop_evt.set()
        self._wake_evt.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)

    def _loop(self):
        failures = 0
        last_error = None
        while not self._stop_evt.is_set():
            self._wake_evt.clear()
            try:
                data, err = self._client.get_state()
            except Exception as exc:
                data, err = None, str(exc)
            if self._stop_evt.is_set():
                return
            if err or not isinstance(data, dict):
                failures += 1
                message = err or "Backend returned no state"
                if message != last_error:
                    self._on_error(message)
                last_error = message
            else:
                failures, last_error = 0, None
                self._on_update(data)
            delay = min(15.0, self._interval * 2 ** min(failures, 4))
            self._wake_evt.wait(delay)


class AsyncOpRunner:
    """
    Run a single backend mutation asynchronously without blocking the UI loop.
    Only one operation runs at a time.
    """

    def __init__(self):
        self._lock   = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self.is_running = False
        self._closed = False

    def run(self, fn: Callable, on_done: Callable, on_error: Callable):
        """
        fn()           — zero-arg callable that performs the operation, returns (data, err).
        on_done(data)  — called from the background thread on success.
        on_error(err)  — called from the background thread on failure.
        """
        with self._lock:
            if self._closed or self.is_running:
                on_error("Another operation is already in progress.")
                return False
            self.is_running = True

        def _run():
            try:
                data, err = fn()
                if not self._closed:
                    if err:
                        on_error(err)
                    else:
                        on_done(data)
            except Exception as exc:
                if not self._closed:
                    on_error(str(exc))
            finally:
                with self._lock:
                    self.is_running = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return True

    def close(self, timeout=0.25):
        self._closed = True
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)

