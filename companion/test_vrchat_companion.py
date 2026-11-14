import sys
import importlib.util
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import contextlib
import io
import json
import socket
import struct
import threading
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("vrchat_companion.py")
SPEC = importlib.util.spec_from_file_location("vrchat_companion", MODULE_PATH)
companion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(companion)


def read_osc_string(packet, offset):
    end = packet.index(b"\0", offset)
    value = packet[offset:end].decode("utf-8")
    next_offset = (end + 4) & ~3
    return value, next_offset


class CompanionTests(unittest.TestCase):
    def test_encodes_vrchat_eyeheight_as_osc_float(self):
        packet = companion.encode_eyeheight_packet(20)
        address, offset = read_osc_string(packet, 0)
        tags, offset = read_osc_string(packet, offset)
        self.assertEqual(address, "/avatar/eyeheight")
        self.assertEqual(tags, ",f")
        self.assertAlmostEqual(struct.unpack(">f", packet[offset:offset + 4])[0], 20)
        self.assertEqual(offset + 4, len(packet))

    def test_accepts_extended_osc_range_and_rejects_outside_limits(self):
        with self.assertRaises(ValueError):
            companion.encode_eyeheight_packet(0.009)
        with self.assertRaises(ValueError):
            companion.encode_eyeheight_packet(10001)

    def test_encodes_heights_above_100_without_clamping(self):
        for height in (101, 1000, 10000, 0.01):
            packet = companion.encode_eyeheight_packet(height)
            self.assertAlmostEqual(struct.unpack(">f", packet[-4:])[0], height, places=6)

    def test_public_server_url_requires_https(self):
        self.assertEqual(companion.validate_server_url("https://mid.shardware.net/"), "https://mid.shardware.net")
        with self.assertRaises(ValueError):
            companion.validate_server_url("http://mid.shardware.net")
        self.assertEqual(companion.validate_server_url("http://127.0.0.1:4777"), "http://127.0.0.1:4777")

    def test_osc_target_must_be_a_private_ipv4_address(self):
        self.assertEqual(companion.validate_osc_host("192.168.1.42"), "192.168.1.42")
        self.assertEqual(companion.validate_osc_host("127.0.0.1"), "127.0.0.1")
        with self.assertRaises(ValueError):
            companion.validate_osc_host("8.8.8.8")

    def test_waits_for_local_vrchat_oscquery(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/avatar/eyeheight":
                    self.send_error(404)
                    return
                body = b'{"FULL_PATH":"/avatar/eyeheight","ACCESS":3}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertTrue(companion.vrchat_osc_ready("127.0.0.1", server.server_port))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(companion.vrchat_osc_ready("127.0.0.1", server.server_port))

    def test_reads_only_current_height_without_auth_or_ack(self):
        state = {"authorization": None, "writes": 0}

        class ApiHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/api/vrchat/height":
                    self.send_error(404)
                    return
                state["authorization"] = self.headers.get("Authorization")
                body = json.dumps({"heightMeters": 2.25}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                state["writes"] += 1
                self.send_response(405)
                self.end_headers()

            def log_message(self, *_args):
                pass

        class QueryHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/avatar/eyeheight":
                    self.send_error(404)
                    return
                body = b'{"FULL_PATH":"/avatar/eyeheight","ACCESS":3}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        api = HTTPServer(("127.0.0.1", 0), ApiHandler)
        query = HTTPServer(("127.0.0.1", 0), QueryHandler)
        api_thread = threading.Thread(target=api.serve_forever, daemon=True)
        query_thread = threading.Thread(target=query.serve_forever, daemon=True)
        api_thread.start()
        query_thread.start()
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        try:
            config = {
                "serverUrl": f"http://127.0.0.1:{api.server_port}",
                "oscPort": receiver.getsockname()[1],
                "oscQueryPort": 0,  # No OSCQuery service: direct UDP must still work.
                "oscHost": "127.0.0.1",
            }
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(companion.run(config, once=True), 0)
            packet, origin = receiver.recvfrom(1024)
            self.assertEqual(origin[0], "127.0.0.1")
            address, offset = read_osc_string(packet, 0)
            tags, offset = read_osc_string(packet, offset)
            self.assertEqual((address, tags), ("/avatar/eyeheight", ",f"))
            self.assertAlmostEqual(struct.unpack(">f", packet[offset:offset + 4])[0], 2.25)
            self.assertIsNone(state["authorization"])
            self.assertEqual(state["writes"], 0)
        finally:
            receiver.close()
            api.shutdown()
            query.shutdown()
            api.server_close()
            query.server_close()
            api_thread.join(timeout=2)
            query_thread.join(timeout=2)

    def test_config_file_is_private_and_legacy_token_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "companion" / "config.json"
            token = "A" * 43
            companion.save_config({
                "serverUrl": "https://mid.shardware.net",
                "token": token,
                "oscPort": 9000,
                "oscQueryPort": 9001,
                "oscHost": "127.0.0.1",
            }, target)
            if sys.platform != 'win32':
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("token", companion.load_config(target))
            self.assertNotIn("token", json.loads(target.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
