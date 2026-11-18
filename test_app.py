import json
import threading
import os
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stderr
from io import StringIO
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import serial
from app import Relay, make_handler, parse_settings


class SettingsTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_platform_ports_and_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            for port in ("/dev/cu.usbserial-10", "COM12", "/dev/ttyUSB0",
                         "/dev/serial/by-id/usb-relay"):
                env_file.write_text(f'SERIAL_PORT="{port}"\nPORT=8123\n', encoding="utf-8-sig")
                args = parse_settings([], env_file)
                self.assertEqual(args.serial_port, port)
                self.assertEqual(args.port, 8123)

    @patch.dict(os.environ, {"SERIAL_PORT": "COM4"}, clear=True)
    def test_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("SERIAL_PORT=COM3\n", encoding="utf-8")
            self.assertEqual(parse_settings([], env_file).serial_port, "COM4")
            self.assertEqual(parse_settings(["--serial-port", "COM5"], env_file).serial_port, "COM5")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_port_and_invalid_http_port(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            for content in ("", "SERIAL_PORT=\n", "SERIAL_PORT=COM3\nPORT=abc\n",
                            "SERIAL_PORT=COM3\nPORT=65536\n"):
                env_file.write_text(content, encoding="utf-8")
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                    parse_settings([], env_file)
                self.assertEqual(caught.exception.code, 2)


class APITest(unittest.TestCase):
    def setUp(self):
        self.relay = Relay("/dev/test-relay")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.relay))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    @patch("app.serial.Serial")
    def test_commands_and_read_only_routes(self, constructor):
        device = constructor.return_value.__enter__.return_value
        device.write.return_value = 4
        self.assertIsNone(self.request("GET", "/status")[1]["last_command"])
        self.assertEqual(self.request("GET", "/health")[0], 200)
        self.assertEqual(self.request("GET", "/on")[0], 404)
        self.assertEqual(self.request("POST", "/invalid")[0], 404)
        constructor.assert_not_called()
        for path, expected in (("/on", b"\xa0\x01\x01\xa2"),
                               ("/off", b"\xa0\x01\x00\xa1")):
            code, result = self.request("POST", path)
            self.assertEqual(code, 200)
            device.write.assert_called_with(expected)
            self.assertEqual(result["last_command"], path[1:])
            self.assertEqual(result["physical_state"], "unknown")
        constructor.assert_called_with("/dev/test-relay", 9600, timeout=1, write_timeout=2)

    @patch("app.serial.Serial")
    def test_usb_failure_preserves_last_command(self, constructor):
        self.relay.last_command = "off"
        constructor.side_effect = serial.SerialException("Disconnected")
        self.assertEqual(self.request("POST", "/on")[0], 503)
        self.assertEqual(self.request("GET", "/status")[1]["last_command"], "off")

    @patch("app.serial.Serial")
    def test_short_write_is_failure(self, constructor):
        constructor.return_value.__enter__.return_value.write.return_value = 2
        self.assertEqual(self.request("POST", "/on")[0], 503)
        self.assertIsNone(self.relay.last_command)


if __name__ == "__main__":
    unittest.main()
