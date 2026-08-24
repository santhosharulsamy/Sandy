"""A minimal HTTP registry server for Sandy packages.

A reference implementation of the server the registry client
(`sandy/packages.py`) talks to. Packages are stored on disk in the same
`<name>/<version>/` layout the file-based registry uses, and served as JSON:

    GET  /packages/<name>            -> {"name", "versions": [...]}
    GET  /packages/<name>/<version>  -> {"name", "version", "files": {path: text}}
    PUT  /packages/<name>/<version>  -> publish (body {"files": {...}}); 409 if
                                        the version exists (immutable) unless
                                        ?force=1

Run it with `sandy registry serve` (see the CLI). Point a client at it with
`SANDY_REGISTRY=http://host:port`.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import packages


def make_handler(store_dir):
    backend = packages._FileBackend(store_dir)

    class Handler(BaseHTTPRequestHandler):
        server_version = "SandyRegistry/0.1"

        def log_message(self, *args):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _route(self):
            return [p for p in self.path.split("?")[0].split("/") if p]

        def do_GET(self):
            parts = self._route()
            if len(parts) == 2 and parts[0] == "packages":
                name = parts[1]
                versions = backend.list_versions(name)
                if not versions:
                    return self._json(404, {"error": f"no package '{name}'"})
                return self._json(200, {"name": name, "versions": versions})
            if len(parts) == 3 and parts[0] == "packages":
                name, version = parts[1], parts[2]
                if not backend.has(name, version):
                    return self._json(404, {"error": "no such version"})
                return self._json(200, {"name": name, "version": version,
                                        "files": backend.read_files(name, version)})
            self._json(404, {"error": "not found"})

        def do_PUT(self):
            parts = self._route()
            if len(parts) != 3 or parts[0] != "packages":
                return self._json(404, {"error": "not found"})
            name, version = parts[1], parts[2]
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                files = payload["files"]
            except (ValueError, KeyError):
                return self._json(400, {"error": "expected JSON {files: {...}}"})
            force = "force=1" in (self.path.split("?", 1)[1]
                                  if "?" in self.path else "")
            try:
                backend.publish(name, version, files, force)
            except packages.PackageError as e:
                return self._json(409, {"error": str(e)})
            return self._json(201, {"published": f"{name} {version}"})

    return Handler


def serve(store_dir, port, host="127.0.0.1"):
    """Create (but do not start) a threaded registry server. Call
    serve_forever() to run it. Returns the HTTPServer."""
    os.makedirs(store_dir, exist_ok=True)
    return ThreadingHTTPServer((host, port), make_handler(store_dir))
