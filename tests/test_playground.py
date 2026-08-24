"""Guard: the generated web playground stays in sync with the package.

If this fails, regenerate with:  python web/build_playground.py

Run with:  python -m unittest tests.test_playground
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "build_playground", os.path.join(ROOT, "web", "build_playground.py"))
build_playground = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_playground)


class TestPlayground(unittest.TestCase):
    def test_generated_file_is_current(self):
        path = os.path.join(ROOT, "web", "playground.html")
        with open(path, encoding="utf-8") as f:
            committed = f.read()
        self.assertEqual(
            committed, build_playground.render(),
            "web/playground.html is stale — run: python web/build_playground.py")

    def test_embeds_the_package(self):
        sources = build_playground.collect_sources()
        # Core modules and the standard library must be embedded.
        for expected in ("/sandy/interpreter.py", "/sandy/runtime.py",
                         "/sandy/stdlib/math.sy"):
            self.assertIn(expected, sources)


if __name__ == "__main__":
    unittest.main()
