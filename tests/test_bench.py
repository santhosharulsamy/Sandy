"""Correctness of the benchmark pairs.

A speed comparison is only fair if both versions compute the same thing. For
each benchmark we check, at the small (quick) size, that the Sandy program and
the Python program produce the same result, and that it matches the benchmark's
own expected value.

Run with:  python -m unittest tests.test_bench
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.interpreter import Interpreter
from sandy.runtime import run_source

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "bench"))
import compare  # noqa: E402


class TestBenchmarkPairsAgree(unittest.TestCase):
    def test_sandy_python_and_expected_match(self):
        for name, (sy_t, py_t, _full, quick, expected_fn) in \
                compare.BENCHMARKS.items():
            with self.subTest(benchmark=name):
                want = str(expected_fn(quick))

                out = io.StringIO()
                run_source(sy_t.format(n=quick), Interpreter(out=out))
                self.assertEqual(out.getvalue().strip(), want,
                                 f"Sandy result for {name}")

                ns = {}
                buf = io.StringIO()
                _stdout = sys.stdout
                sys.stdout = buf
                try:
                    exec(py_t.format(n=quick), ns)  # noqa: S102 - trusted bench
                finally:
                    sys.stdout = _stdout
                self.assertEqual(buf.getvalue().strip(), want,
                                 f"Python result for {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
