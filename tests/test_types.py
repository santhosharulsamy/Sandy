"""Tests for Sandy's gradual type checker.

Run with:  python -m unittest tests.test_types
"""

import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.lexer import tokenize
from sandy.parser import parse
from sandy.typecheck import check


def errors(code):
    return check(parse(tokenize(code)))


def messages(code):
    return [m for m, _ in errors(code)]


class TestNoFalsePositives(unittest.TestCase):
    """Unannotated (dynamic) code must never produce type errors."""

    def test_dynamic_code_is_clean(self):
        snippets = [
            'x = 5\nx = "now a string"\nprint(x)',
            'fn f(a, b) { return a + b }\nprint(f(1, 2))\nprint(f("a", "b"))',
            'a = [1, 2]\nprint(a[0] + a[1])',
            'total = 0\nfor n in range(10) { total += n }',
            'm = { "k": 1 }\nprint(m["k"] + 1)',
        ]
        for code in snippets:
            self.assertEqual(errors(code), [], f"false positive in: {code!r}")

    def test_all_examples_clean(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for path in sorted(glob.glob(os.path.join(root, "examples", "*.sy"))):
            src = open(path, encoding="utf-8").read()
            self.assertEqual(errors(src), [], f"false positive in {path}")


class TestCatchesRealBugs(unittest.TestCase):
    def test_add_mismatch(self):
        msgs = messages('fn f(a: int) -> int { return a + "x" }')
        self.assertTrue(any("cannot add" in m for m in msgs))

    def test_return_type_mismatch(self):
        msgs = messages('fn f() -> int { return "hello" }')
        self.assertTrue(any("return type mismatch" in m for m in msgs))

    def test_variable_annotation_mismatch(self):
        msgs = messages('x: int = "nope"')
        self.assertTrue(any("cannot assign string to 'x'" in m for m in msgs))

    def test_reassignment_mismatch(self):
        msgs = messages('x: int = 5\nx = "no"')
        self.assertTrue(any("cannot assign" in m for m in msgs))

    def test_argument_type_mismatch(self):
        msgs = messages('fn f(a: int) -> int { return a }\nf("bad")')
        self.assertTrue(any("argument 1" in m for m in msgs))

    def test_arity_mismatch(self):
        msgs = messages('fn f(a: int, b: int) -> int { return a + b }\nf(1)')
        self.assertTrue(any("expects 2 argument" in m for m in msgs))

    def test_compare_mismatch(self):
        msgs = messages('fn f(a: int, b: string) -> bool { return a < b }')
        self.assertTrue(any("cannot compare" in m for m in msgs))


class TestGradualInterop(unittest.TestCase):
    def test_any_is_compatible(self):
        # An unannotated arg (any) may flow into a typed parameter.
        code = 'fn f(a: int) -> int { return a }\nfn g(x) { return f(x) }'
        self.assertEqual(errors(code), [])

    def test_int_widens_to_float(self):
        code = 'x: float = 3'
        self.assertEqual(errors(code), [])

    def test_recursion_typechecks(self):
        code = 'fn fib(n: int) -> int { if n < 2 { return n }\n return fib(n-1) + fib(n-2) }'
        self.assertEqual(errors(code), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
