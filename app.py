"""HTTP API for an LCUS-1 compatible USB relay."""

import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
from dotenv import dotenv_values


class Relay:
    def __init__(self, port):
        self.port = port
        self.last_command = None
        self.lock = threading.Lock()

    def switch(self, enabled):
        command = bytes((0xA0, 0x01, int(enabled), 0xA1 + int(enabled)))
        with self.lock:
            # Open per request so a USB reconnect does not leave a stale handle.
            with serial.Serial(self.port, 9600, timeout=1, write_timeout=2) as connection:
                if connection.write(command) != len(command):
                    raise serial.SerialException("Incomplete serial write")
                connection.flush()
            self.last_command = "on" if enabled else "off"
            return self.status_unlocked()

    def status_unlocked(self):
        return {"port": self.port, "last_command": self.last_command,
                "physical_state": "unknown"}

    def status(self):
        with self.lock:
            return self.status_unlocked()


def make_handler(relay):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self.respond(200, {"status": "ok"})
            elif self.path == "/status":
                self.respond(200, relay.status())
            else:
                self.respond(404, {"error": "Not found"})

        def do_POST(self):
            if self.path not in ("/on", "/off"):
                self.respond(404, {"error": "Not found"})
                return
            try:
                result = relay.switch(self.path == "/on")
            except (serial.SerialException, OSError) as exc:
                self.respond(503, {"error": "USB relay communication failed",
                                   "detail": str(exc)})
                return
            self.respond(200, result)

    return Handler


def parse_settings(argv=None, env_file=None):
    env_file = Path(env_file) if env_file is not None else Path(__file__).resolve().with_name(".env")
    config = {**dotenv_values(env_file, encoding="utf-8-sig"), **os.environ}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=config.get("HOST") or "127.0.0.1")
    parser.add_argument("--port", type=int, default=config.get("PORT") or "8000")
    parser.add_argument("--serial-port", default=config.get("SERIAL_PORT"))
    args = parser.parse_args(argv)
    if not args.serial_port or not args.serial_port.strip():
        parser.error("Set SERIAL_PORT in .env (e.g. COM3 or /dev/ttyUSB0), or use --serial-port")
    args.serial_port = args.serial_port.strip()
    if not 1 <= args.port <= 65535:
        parser.error("--port / PORT must be between 1 and 65535")
    return args


def main():
    args = parse_settings()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(Relay(args.serial_port)))
    print(f"Listening on http://{args.host}:{server.server_port}, relay: {args.serial_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
