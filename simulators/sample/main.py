"""
Moxa ioLogik E1212 Simulator

Emulates a Moxa ioLogik hub by running a simple HTTP server that responds
to the Moxa REST API endpoints. Simulates 8 DI + 8 DIO channels.

Digital inputs toggle randomly over time for testing purposes.
Digital and analog outputs accept PUT requests.
"""

import json
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Default simulated I/O state
SIMULATOR_PORT = 9090

NUM_DI = 8
NUM_DO = 8
NUM_AI = 4
NUM_AO = 4

# Shared I/O state (protected by lock)
io_lock = threading.Lock()

di_state = [{"diIndex": i, "diMode": 0, "diStatus": 0} for i in range(NUM_DI)]
do_state = [{"doIndex": i, "doMode": 0, "doStatus": 0} for i in range(NUM_DO)]
ai_state = [{"aiIndex": i, "aiMode": 0, "aiValue": 0.0, "aiValueRaw": 0.0} for i in range(NUM_AI)]
ao_state = [{"aoIndex": i, "aoMode": 0, "aoValue": 0.0, "aoValueRaw": 0.0} for i in range(NUM_AO)]

device_info = {
    "modelName": "ioLogik E1212 (Simulator)",
    "deviceUpTime": 0,
    "firmwareVersion": "3.2",
    "ipAddress": "0.0.0.0",
    "macAddress": "00:00:00:00:00:00",
}


class MoxaAPIHandler(BaseHTTPRequestHandler):
    """HTTP handler emulating Moxa ioLogik REST API."""

    def log_message(self, format, *args):
        # Suppress default request logging
        pass

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/api/slot/0/sysInfo/device":
            self._send_json({"slot": 0, "sysInfo": {"device": device_info}})
            return

        with io_lock:
            if path == "/api/slot/0/io/di":
                self._send_json({"slot": 0, "io": {"di": list(di_state)}})
            elif path.startswith("/api/slot/0/io/di/"):
                idx = int(path.split("/")[-1])
                if 0 <= idx < NUM_DI:
                    self._send_json({"slot": 0, "io": {"di": di_state[idx]}})
                else:
                    self._send_json({"error": "Invalid index"}, 404)
            elif path == "/api/slot/0/io/do":
                self._send_json({"slot": 0, "io": {"do": list(do_state)}})
            elif path.startswith("/api/slot/0/io/do/"):
                idx = int(path.split("/")[-1])
                if 0 <= idx < NUM_DO:
                    self._send_json({"slot": 0, "io": {"do": do_state[idx]}})
                else:
                    self._send_json({"error": "Invalid index"}, 404)
            elif path == "/api/slot/0/io/ai":
                self._send_json({"slot": 0, "io": {"ai": list(ai_state)}})
            elif path.startswith("/api/slot/0/io/ai/"):
                idx = int(path.split("/")[-1])
                if 0 <= idx < NUM_AI:
                    self._send_json({"slot": 0, "io": {"ai": ai_state[idx]}})
                else:
                    self._send_json({"error": "Invalid index"}, 404)
            elif path == "/api/slot/0/io/ao":
                self._send_json({"slot": 0, "io": {"ao": list(ao_state)}})
            elif path.startswith("/api/slot/0/io/ao/"):
                idx = int(path.split("/")[-1])
                if 0 <= idx < NUM_AO:
                    self._send_json({"slot": 0, "io": {"ao": ao_state[idx]}})
                else:
                    self._send_json({"error": "Invalid index"}, 404)
            else:
                self._send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        path = self.path.rstrip("/")

        with io_lock:
            if path.startswith("/api/slot/0/io/do"):
                self._handle_do_put(path, data)
            elif path.startswith("/api/slot/0/io/ao"):
                self._handle_ao_put(path, data)
            else:
                self._send_json({"error": "Not found"}, 404)

    def _handle_do_put(self, path: str, data: dict):
        do_data = data.get("io", {}).get("do", {})
        if isinstance(do_data, dict):
            idx = do_data.get("doIndex")
            if idx is not None and 0 <= idx < NUM_DO:
                do_state[idx]["doStatus"] = do_data.get("doStatus", do_state[idx]["doStatus"])
                self._send_json({"slot": 0, "io": {"do": do_state[idx]}})
                return
        elif isinstance(do_data, list):
            for item in do_data:
                idx = item.get("doIndex")
                if idx is not None and 0 <= idx < NUM_DO:
                    do_state[idx]["doStatus"] = item.get("doStatus", do_state[idx]["doStatus"])
            self._send_json({"slot": 0, "io": {"do": list(do_state)}})
            return
        self._send_json({"error": "Invalid DO data"}, 400)

    def _handle_ao_put(self, path: str, data: dict):
        ao_data = data.get("io", {}).get("ao", {})
        if isinstance(ao_data, dict):
            idx = ao_data.get("aoIndex")
            if idx is not None and 0 <= idx < NUM_AO:
                ao_state[idx]["aoValue"] = ao_data.get("aoValue", ao_state[idx]["aoValue"])
                ao_state[idx]["aoValueRaw"] = ao_state[idx]["aoValue"]
                self._send_json({"slot": 0, "io": {"ao": ao_state[idx]}})
                return
        elif isinstance(ao_data, list):
            for item in ao_data:
                idx = item.get("aoIndex")
                if idx is not None and 0 <= idx < NUM_AO:
                    ao_state[idx]["aoValue"] = item.get("aoValue", ao_state[idx]["aoValue"])
                    ao_state[idx]["aoValueRaw"] = ao_state[idx]["aoValue"]
            self._send_json({"slot": 0, "io": {"ao": list(ao_state)}})
            return
        self._send_json({"error": "Invalid AO data"}, 400)


def simulate_inputs():
    """Background thread that randomly toggles DI and varies AI values."""
    while True:
        time.sleep(3)
        with io_lock:
            # Randomly toggle one DI channel
            idx = random.randint(0, NUM_DI - 1)
            di_state[idx]["diStatus"] = 1 - di_state[idx]["diStatus"]

            # Vary AI values with some noise
            for i in range(NUM_AI):
                base = 2.5 + i * 0.5
                ai_state[i]["aiValue"] = round(base + random.uniform(-0.3, 0.3), 2)
                ai_state[i]["aiValueRaw"] = ai_state[i]["aiValue"]


def main():
    # Start the input simulation thread
    sim_thread = threading.Thread(target=simulate_inputs, daemon=True)
    sim_thread.start()

    port = SIMULATOR_PORT
    server = HTTPServer(("0.0.0.0", port), MoxaAPIHandler)
    print(f"Moxa ioLogik Simulator running on port {port}")
    print(f"  DI channels: {NUM_DI}, DO channels: {NUM_DO}")
    print(f"  AI channels: {NUM_AI}, AO channels: {NUM_AO}")
    server.serve_forever()


if __name__ == "__main__":
    main()
