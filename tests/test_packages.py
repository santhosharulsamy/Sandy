"""Tests for Sandy's package system (manifest, resolution, lockfile, imports).

Run with:  python -m unittest tests.test_packages
"""

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy import packages
from sandy.interpreter import Interpreter
from sandy.runtime import run_source, run_source_vm, type_check_source


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class PackageProject(unittest.TestCase):
    """A temp workspace with a `geometry` dependency and an app that uses it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        write(os.path.join(self.tmp, "geometry", "sandy.toml"),
              '[package]\nname = "geometry"\nversion = "1.2.0"\n')
        write(os.path.join(self.tmp, "geometry", "geometry.sy"),
              "fn area(w: int, h: int) -> int { return w * h }\n")
        write(os.path.join(self.tmp, "geometry", "circle.sy"),
              "fn twice(r: int) -> int { return r * 2 }\n")
        self.proj = os.path.join(self.tmp, "app")
        write(os.path.join(self.proj, "sandy.toml"),
              '[package]\nname = "app"\nversion = "0.1.0"\n\n'
              '[dependencies]\ngeometry = { path = "../geometry" }\n')

    def app(self, name, src):
        path = os.path.join(self.proj, name)
        write(path, src)
        return path

    def run_interp(self, path):
        out = io.StringIO()
        with open(path, encoding="utf-8") as f:
            src = f.read()
        run_source(src, Interpreter(out=out), base_dir=os.path.dirname(path))
        return out.getvalue()


class TestManifestAndInstall(PackageProject):
    def test_install_writes_lock(self):
        resolved = packages.install(self.proj)
        self.assertIn("geometry", resolved)
        self.assertEqual(resolved["geometry"]["version"], "1.2.0")
        self.assertEqual(resolved["geometry"]["source"], "path")
        with open(os.path.join(self.proj, packages.LOCKFILE)) as f:
            lock = json.load(f)
        self.assertEqual(lock["packages"]["geometry"]["version"], "1.2.0")

    def test_install_missing_path_errors(self):
        write(os.path.join(self.proj, "sandy.toml"),
              '[package]\nname = "app"\nversion = "0.1.0"\n\n'
              '[dependencies]\nnope = { path = "../nope" }\n')
        with self.assertRaises(packages.PackageError):
            packages.install(self.proj)

    def test_manifest_requires_package_name(self):
        write(os.path.join(self.proj, "sandy.toml"), "[dependencies]\n")
        with self.assertRaises(packages.PackageError):
            packages.load_manifest(self.proj)

    def test_find_project_root_walks_up(self):
        nested = os.path.join(self.proj, "a", "b")
        os.makedirs(nested)
        self.assertEqual(packages.find_project_root(nested), self.proj)


class TestImportResolution(PackageProject):
    def test_import_after_install(self):
        packages.install(self.proj)
        p = self.app("main.sy",
                     'import "geometry" as geo\nprint(geo.area(3, 4))\n')
        self.assertEqual(self.run_interp(p), "12\n")

    def test_import_before_install_uses_manifest(self):
        # No lockfile yet: path deps still resolve straight from the manifest.
        p = self.app("main.sy",
                     'import "geometry" as geo\nprint(geo.area(2, 5))\n')
        self.assertEqual(self.run_interp(p), "10\n")

    def test_submodule_import(self):
        packages.install(self.proj)
        p = self.app("m.sy",
                     'import "geometry/circle" as c\nprint(c.twice(21))\n')
        self.assertEqual(self.run_interp(p), "42\n")

    def test_vm_matches_interpreter(self):
        packages.install(self.proj)
        p = self.app("main.sy",
                     'import "geometry" as geo\nprint(geo.area(6, 7))\n')
        vm_out = io.StringIO()
        with open(p, encoding="utf-8") as f:
            src = f.read()
        run_source_vm(src, out=vm_out, base_dir=os.path.dirname(p))
        self.assertEqual(vm_out.getvalue(), self.run_interp(p))

    def test_cross_package_type_error(self):
        packages.install(self.proj)
        src = 'import "geometry" as geo\nprint(geo.area("wide", 4))\n'
        errors = type_check_source(src, base_dir=self.proj)
        self.assertTrue(any("area" in m for m, _ in errors), errors)

    def test_local_file_shadows_package(self):
        # A local module of the same name takes priority over a dependency.
        self.app("geometry.sy",
                 "fn area(w: int, h: int) -> int { return 999 }\n")
        packages.install(self.proj)
        p = self.app("main.sy",
                     'import "geometry" as geo\nprint(geo.area(1, 1))\n')
        self.assertEqual(self.run_interp(p), "999\n")


class TestAddDependency(PackageProject):
    def test_add_appends_to_dependencies(self):
        write(os.path.join(self.tmp, "util", "sandy.toml"),
              '[package]\nname = "util"\nversion = "0.1.0"\n')
        write(os.path.join(self.tmp, "util", "util.sy"),
              "fn ok() -> bool { return true }\n")
        packages.add_dependency(self.proj, "util", "../util")
        manifest = packages.load_manifest(self.proj)
        self.assertIn("util", manifest["dependencies"])
        self.assertIn("geometry", manifest["dependencies"])  # kept existing

    def test_add_creates_manifest_when_absent(self):
        fresh = os.path.join(self.tmp, "fresh")
        os.makedirs(fresh)
        packages.add_dependency(fresh, "geometry", "../geometry")
        manifest = packages.load_manifest(fresh)
        self.assertIn("geometry", manifest["dependencies"])

    def test_git_dep_line_format(self):
        packages.add_dependency(self.proj, "web", "https://example.com/web.git")
        with open(os.path.join(self.proj, "sandy.toml")) as f:
            text = f.read()
        self.assertIn('web = { git = "https://example.com/web.git" }', text)


class TestSemver(unittest.TestCase):
    def test_satisfies(self):
        s = packages.satisfies
        self.assertTrue(s("1.2.0", "^1.0.0"))
        self.assertFalse(s("2.0.0", "^1.0.0"))
        self.assertTrue(s("0.2.9", "^0.2.0"))
        self.assertFalse(s("0.3.0", "^0.2.0"))
        self.assertTrue(s("1.0.5", "~1.0.0"))
        self.assertFalse(s("1.1.0", "~1.0.0"))
        self.assertTrue(s("1.5.0", ">=1.2.0,<2.0.0"))
        self.assertFalse(s("2.1.0", ">=1.2.0,<2.0.0"))
        self.assertTrue(s("3.1.4", "*"))
        self.assertTrue(s("1.2.3", "1.2.3"))
        self.assertFalse(s("1.2.4", "1.2.3"))

    def test_resolve_picks_highest_match(self):
        reg = tempfile.mkdtemp()
        for v in ("1.0.0", "1.2.0", "2.0.0"):
            os.makedirs(os.path.join(reg, "lib", v))
        self.assertEqual(packages.resolve_version(reg, "lib", "^1.0.0"), "1.2.0")
        self.assertEqual(packages.resolve_version(reg, "lib", "*"), "2.0.0")
        with self.assertRaises(packages.PackageError):
            packages.resolve_version(reg, "lib", "^3.0.0")


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.reg = os.path.join(self.tmp, "registry")
        os.environ[packages.REGISTRY_ENV] = self.reg
        # A publishable library, versions 1.0.0 and 1.2.0.
        self.lib = os.path.join(self.tmp, "geolib")
        write(os.path.join(self.lib, "sandy.toml"),
              '[package]\nname = "geolib"\nversion = "1.0.0"\n')
        write(os.path.join(self.lib, "geolib.sy"),
              "fn area(w, h) { return w * h }\n")
        packages.publish(self.lib)
        write(os.path.join(self.lib, "sandy.toml"),
              '[package]\nname = "geolib"\nversion = "1.2.0"\n')
        write(os.path.join(self.lib, "geolib.sy"),
              "fn area(w, h) { return w * h }\n"
              "fn perimeter(w, h) { return 2 * (w + h) }\n")
        packages.publish(self.lib)

    def tearDown(self):
        os.environ.pop(packages.REGISTRY_ENV, None)

    def _app(self, constraint):
        proj = os.path.join(self.tmp, "app_" + constraint.replace(".", "_")
                            .replace("^", "c").replace("~", "t"))
        write(os.path.join(proj, "sandy.toml"),
              '[package]\nname = "app"\nversion = "0.1.0"\n\n'
              f'[dependencies]\ngeolib = "{constraint}"\n')
        return proj

    def test_publish_creates_versioned_layout(self):
        self.assertEqual(packages.available_versions(self.reg, "geolib"),
                         ["1.0.0", "1.2.0"])

    def test_publish_is_immutable(self):
        write(os.path.join(self.lib, "sandy.toml"),
              '[package]\nname = "geolib"\nversion = "1.2.0"\n')
        with self.assertRaises(packages.PackageError):
            packages.publish(self.lib)

    def test_install_resolves_and_vendors_highest(self):
        proj = self._app("^1.0.0")
        resolved = packages.install(proj)
        self.assertEqual(resolved["geolib"]["version"], "1.2.0")
        self.assertEqual(resolved["geolib"]["source"], "registry")
        self.assertTrue(os.path.isfile(
            os.path.join(proj, packages.MODULES_DIR, "geolib", "geolib.sy")))

    def test_import_uses_registry_version(self):
        proj = self._app("^1.0.0")
        packages.install(proj)
        main = os.path.join(proj, "main.sy")
        write(main, 'import "geolib" as geo\nprint(geo.perimeter(3, 4))\n')
        out = io.StringIO()
        run_source(open(main).read(), Interpreter(out=out),
                   base_dir=os.path.dirname(main))
        self.assertEqual(out.getvalue(), "14\n")

    def test_pin_selects_exact_version(self):
        proj = self._app("~1.0.0")
        resolved = packages.install(proj)
        self.assertEqual(resolved["geolib"]["version"], "1.0.0")


class TestHttpRegistry(unittest.TestCase):
    """The registry client talking to the reference HTTP server, in-process."""

    @classmethod
    def setUpClass(cls):
        import threading
        from sandy.registry_server import serve
        os.environ["no_proxy"] = "127.0.0.1,localhost"
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        cls.store = tempfile.mkdtemp()
        cls.httpd = serve(cls.store, 0)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ[packages.REGISTRY_ENV] = self.url
        # Fresh registry contents per test (the server/store are shared).
        for entry in os.listdir(self.store):
            import shutil
            shutil.rmtree(os.path.join(self.store, entry))

    def tearDown(self):
        os.environ.pop(packages.REGISTRY_ENV, None)

    def _publish(self, name, version, body):
        lib = os.path.join(self.tmp, name + version)
        write(os.path.join(lib, "sandy.toml"),
              f'[package]\nname = "{name}"\nversion = "{version}"\n')
        write(os.path.join(lib, name + ".sy"), body)
        return packages.publish(lib)

    def test_publish_list_and_resolve_over_http(self):
        self._publish("mathx", "1.0.0", "fn add(a, b) { return a + b }\n")
        self._publish("mathx", "1.1.0",
                      "fn add(a, b) { return a + b }\nfn mul(a, b) { return a * b }\n")
        self.assertEqual(packages.available_versions(self.url, "mathx"),
                         ["1.0.0", "1.1.0"])
        self.assertEqual(packages.resolve_version(self.url, "mathx", "^1.0.0"),
                         "1.1.0")

    def test_publish_is_immutable_over_http(self):
        self._publish("libz", "2.0.0", "fn f() { return 1 }\n")
        with self.assertRaises(packages.PackageError):
            self._publish("libz", "2.0.0", "fn f() { return 2 }\n")

    def test_install_and_import_over_http(self):
        self._publish("mathx", "1.0.0", "fn add(a, b) { return a + b }\n")
        self._publish("mathx", "1.1.0",
                      "fn add(a, b) { return a + b }\nfn mul(a, b) { return a * b }\n")
        app = os.path.join(self.tmp, "app")
        write(os.path.join(app, "sandy.toml"),
              '[package]\nname = "app"\nversion = "0.1.0"\n\n'
              '[dependencies]\nmathx = "^1.0.0"\n')
        resolved = packages.install(app)
        self.assertEqual(resolved["mathx"]["version"], "1.1.0")
        main = os.path.join(app, "main.sy")
        write(main, 'import "mathx" as m\nprint(m.mul(4, 5))\n')
        out = io.StringIO()
        run_source(open(main).read(), Interpreter(out=out),
                   base_dir=os.path.dirname(main))
        self.assertEqual(out.getvalue(), "20\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
