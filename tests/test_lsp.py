"""Tests for the Sandy language server.

Run with:  python -m unittest tests.test_lsp
"""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.lsp import compute_diagnostics, completions, document_symbols


class TestDiagnostics(unittest.TestCase):
    def test_syntax_error(self):
        d = compute_diagnostics("x = 1 +* 2")
        self.assertEqual(len(d), 1)
        self.assertIn("unexpected", d[0]["message"])
        self.assertEqual(d[0]["range"]["start"]["line"], 0)

    def test_type_error(self):
        d = compute_diagnostics('fn f() -> int { return "no" }')
        self.assertTrue(any("return type mismatch" in x["message"] for x in d))

    def test_clean_program(self):
        self.assertEqual(compute_diagnostics("x = 1\nprint(x)"), [])

    def test_error_line_reported(self):
        d = compute_diagnostics("x = 1\ny = 2\nz = )")
        self.assertEqual(d[0]["range"]["start"]["line"], 2)  # 0-based line 3


class TestCompletion(unittest.TestCase):
    def test_includes_keywords_builtins_and_locals(self):
        labels = {i["label"] for i in completions("fn myfunc() { return 1 }\n"
                                                   "struct Widget { a }")}
        self.assertIn("fn", labels)        # keyword
        self.assertIn("print", labels)     # builtin
        self.assertIn("myfunc", labels)    # local function
        self.assertIn("Widget", labels)    # local struct

    def test_survives_syntax_error(self):
        labels = {i["label"] for i in completions("x = )")}
        self.assertIn("print", labels)     # still offers keywords/builtins


class TestSymbols(unittest.TestCase):
    def test_outline(self):
        syms = document_symbols("fn foo() { return 1 }\n"
                                "struct P { x, y }\ntop = 5")
        names = {s["name"]: s["kind"] for s in syms}
        self.assertEqual(names["foo"], 12)   # Function
        self.assertEqual(names["P"], 23)     # Struct
        self.assertEqual(names["top"], 13)   # Variable


class TestServerRoundTrip(unittest.TestCase):
    def _frame(self, obj):
        data = json.dumps(obj).encode()
        return f"Content-Length: {len(data)}\r\n\r\n".encode() + data

    def test_initialize_and_diagnostics(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        msgs = b"".join(self._frame(m) for m in [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
                "textDocument": {"uri": "file:///t.sy",
                                 "text": 'fn f() -> int { return "x" }'}}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
            {"jsonrpc": "2.0", "method": "exit", "params": {}},
        ])
        p = subprocess.run([sys.executable, "-m", "sandy", "lsp"],
                           input=msgs, capture_output=True, timeout=30, cwd=root)
        out = p.stdout
        # The diagnostics notification must be somewhere in the framed output.
        self.assertIn(b"publishDiagnostics", out)
        self.assertIn(b"return type mismatch", out)
        self.assertIn(b"capabilities", out)


if __name__ == "__main__":
    unittest.main()
