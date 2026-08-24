"""Tests for HTTP support (http_get/http_post builtins and the `http` module).

A small HTTP server runs in a background thread, so these tests need no
external network. Each program is run on both engines.

Run with:  python -m unittest tests.test_http
"""

import io
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.interpreter import Interpreter
from sandy.runtime import run_source, run_source_vm


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/miss":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "nope"}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"name": "Sandy", "n": 42}).encode())

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"echo": ' + data + b'}')


class HttpCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Localhost must bypass any configured proxy.
        os.environ["no_proxy"] = "127.0.0.1,localhost"
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        cls.srv = HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def check(self, body, expected):
        src = body.replace("BASE", self.base)
        out = io.StringIO()
        run_source(src, Interpreter(out=out))
        self.assertEqual(out.getvalue(), expected, "interpreter")
        vout = io.StringIO()
        run_source_vm(src, out=vout)
        self.assertEqual(vout.getvalue(), expected, "vm")

    def test_get_returns_status_ok_body(self):
        self.check('r = http_get("BASE/")\nprint(r["status"])\n'
                   'print(r["ok"])\nprint(len(r["body"]) > 0)\n',
                   "200\ntrue\ntrue\n")

    def test_error_status_is_returned_not_thrown(self):
        self.check('r = http_get("BASE/miss")\nprint(r["status"])\n'
                   'print(r["ok"])\n', "404\nfalse\n")

    def test_get_json(self):
        self.check('import "http" as http\n'
                   'd = http.get_json("BASE/")\nprint(d["name"])\n'
                   'print(d["n"])\n', "Sandy\n42\n")

    def test_post_json_roundtrip(self):
        self.check('import "http" as http\n'
                   'r = http.post_json("BASE/echo", {"x": 7})\n'
                   'print(r["echo"]["x"])\n', "7\n")

    def test_get_json_throws_on_error_status(self):
        self.check('import "http" as http\nmsg = "none"\n'
                   'try { http.get_json("BASE/miss") } catch e { msg = e }\n'
                   'print(msg)\n',
                   "http GET BASE/miss returned status 404\n"
                   .replace("BASE", self.base))

    def test_transport_error_raises(self):
        # Nothing is listening on this port -> a transport error is raised.
        self.check('msg = "none"\n'
                   'try { http_get("http://127.0.0.1:1") } '
                   'catch e { msg = "caught" }\nprint(msg)\n',
                   "caught\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
