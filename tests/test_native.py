"""Tests for the native (C) backend.

Where a C compiler is available, each supported program is compiled and run,
and its output is compared against the tree-walking interpreter — the native
binary must produce identical results. Unsupported features must raise a clear
NativeUnsupported error rather than emitting broken C.
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.lexer import tokenize
from sandy.parser import parse
from sandy.interpreter import Interpreter
from sandy.runtime import run_source
from sandy.cbackend import to_c, NativeUnsupported

CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)


def interpret(src):
    out = io.StringIO()
    run_source(src, Interpreter(out=out))
    return out.getvalue()


def compile_and_run(src):
    csrc = to_c(parse(tokenize(src)))
    tmp = tempfile.mkdtemp()
    c_file = os.path.join(tmp, "prog.c")
    exe = os.path.join(tmp, "prog")
    with open(c_file, "w") as f:
        f.write(csrc)
    subprocess.run([CC, "-O2", "-o", exe, c_file, "-lm"], check=True,
                   capture_output=True)
    return subprocess.run([exe], capture_output=True, text=True).stdout


# Programs whose output is exactly reproducible (ints, bools, strings,
# and clean half-integer floats). Kept dense — each cc invocation is slow, so
# several semantic checks are bundled per program.
SUPPORTED = [
    # arithmetic, power, Python floor-mod, always-float division
    'print(2 + 3 * 4)\nprint(2 ** 10)\nprint(-7 % 3)\nprint(7 % -3)\n'
    'print(10 / 4)\nprint(9 / 3)',
    # recursion, loops, conditionals
    'fn fib(n: int) -> int { if n < 2 { return n }\n'
    ' return fib(n-1) + fib(n-2) }\nprint(fib(18))\n'
    'total = 0\ni = 0\nwhile i < 100 { total += i\n i += 1 }\nprint(total)\n'
    'c = 0\nfor k in range(1, 50) { if k % 7 == 0 { c += 1 } }\nprint(c)',
    # bools, strings, interpolation, float vars, negative-step loop
    'fn even(n: int) -> bool { return n % 2 == 0 }\n'
    'print(even(10))\nprint(even(7))\n'
    'name: string = "Sandy"\nprint("hello {name}, {3 * 4}")\n'
    'x: float = 5.0\nx /= 2\nprint(x)\n'
    'for i in range(3, 0, -1) { print(i) }',
    # string operations: concat, repeat, methods, len, str, comparison
    'fn tag(s: string) -> string { return "[" + s.upper() + "]" }\n'
    'g: string = "hi" + " " + "there"\n'
    'print(tag(g))\nprint(g)\nprint(len(g))\nprint("ab" * 4)\n'
    'print("  pad  ".trim())\nprint("ZZZ".lower())\n'
    'print("apple" < "banana")\nprint("n = " + str(21 * 2))\n'
    'print("f = " + str(1.5))\nprint("b = " + str(3 > 1))',
    # typed lists: literals, indexing, push, index-set, iteration, params
    'fn total(xs: list<int>) -> int { s: int = 0\n for x in xs { s += x }\n'
    ' return s }\n'
    'a: list<int> = [4, 8, 15]\npush(a, 16)\na[0] = 40\n'
    'print(a)\nprint(len(a))\nprint(a[-1])\nprint(total(a))\n'
    'sq: list<int> = []\nfor i in range(5) { push(sq, i * i) }\nprint(sq)\n'
    'ws: list<string> = ["z", "a"]\nprint(ws)\nprint(ws[1])',
    # typed maps: literals, get, set, has, len, missing-key default
    'fn get(m: map<string, int>, k: string) -> int {\n'
    ' if has(m, k) { return m[k] }\n return -1 }\n'
    'm: map<string, int> = {"a": 1, "b": 2}\nm["c"] = 3\nm["a"] = 10\n'
    'print(m["a"])\nprint(m["c"])\nprint(len(m))\nprint(has(m, "z"))\n'
    'print(get(m, "b"))\nprint(get(m, "zz"))\n'
    'freq: map<int, int> = {}\nfor i in range(7) { k: int = i % 3\n'
    ' if has(freq, k) { freq[k] = freq[k] + 1 } else { freq[k] = 1 } }\n'
    'print(freq[0])\nprint(freq[1])\nprint(freq[2])',
    # map printing, iteration, keys()/values() — insertion order preserved
    'm: map<string, int> = {"a": 1, "b": 2, "c": 3}\nm["d"] = 4\nprint(m)\n'
    't: int = 0\nfor k in m { t += m[k] }\nprint(t)\n'
    'print(keys(m))\nprint(values(m))\n'
    'nums: map<int, string> = {1: "one", 2: "two"}\nprint(nums)\n'
    'for n in keys(nums) { print(nums[n]) }',
]

# Programs the native backend must reject with a clear error.
UNSUPPORTED = [
    'a = [1, "two", 3]',                  # heterogeneous list literal
    'a = [[1, 2], [3]]',                  # nested lists (element not scalar)
    'm = {"a": 1, "b": "x"}',             # heterogeneous map values
    'm: map<bool, int> = {}',             # bool keys not supported natively
    'fn f(x) { return x + 1 }\nprint(f(1))',  # untyped params
    'print(keys({}))',                    # unsupported builtin
    'x = [1]\nprint(x.push(2))',          # unsupported (list) method
    'fn outer() { fn inner() { return 1 }\n return inner }',  # nested funcs
]


@unittest.skipIf(CC is None, "no C compiler available")
class TestNativeMatchesInterpreter(unittest.TestCase):
    def test_supported_programs(self):
        for i, src in enumerate(SUPPORTED):
            with self.subTest(program=i):
                self.assertEqual(compile_and_run(src), interpret(src),
                                 f"native != interpreter for program #{i}")

    def test_example(self):
        # native.sy computes fib(30) — instant compiled, but slow on the
        # interpreter, so compare against the known-good output directly.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "examples", "native.sy")) as f:
            src = f.read()
        expected = ("== RESULTS ==\n"
                    "fib(30) = 832040\n"
                    "primes under 100 = 25\n"
                    "average(7, 10) = 8.5\n"
                    "squares 1..5 = [1, 4, 9, 16, 25]\n"
                    + "-" * 20 + "\n")
        self.assertEqual(compile_and_run(src), expected)


class TestNativeRejects(unittest.TestCase):
    def test_unsupported_features(self):
        for i, src in enumerate(UNSUPPORTED):
            with self.subTest(program=i):
                with self.assertRaises(NativeUnsupported):
                    to_c(parse(tokenize(src)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
