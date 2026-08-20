"""Equivalence tests: the bytecode VM must produce exactly the same output
as the tree-walking interpreter, for every program we throw at both.

Run with:  python -m unittest tests.test_vm
"""

import glob
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.lexer import tokenize
from sandy.parser import parse
from sandy.interpreter import Interpreter
from sandy.runtime import run_source
from sandy.vm import run_program


def walk(code):
    out = io.StringIO()
    run_source(code, Interpreter(out=out))
    return out.getvalue()


def vm(code):
    out = io.StringIO()
    run_program(parse(tokenize(code)), out=out)
    return out.getvalue()


PROGRAMS = [
    'print(2 + 3 * 4 - 1)',
    'print(2 ** 10)\nprint(-2 ** 2)\nprint(7 % 3)\nprint(10 / 4)',
    'x = 5\nx += 3\nx *= 2\nprint(x)',
    'print("ab" + "cd")\nprint("hi" * 3)\nprint([1] + [2, 3])',
    'name = "Sandy"\nprint("hello {name}, {2 + 3}!")',
    'for i in range(5) { if i == 2 { continue }\n if i == 4 { break }\n print(i) }',
    'i = 0\nwhile i < 4 { print(i)\n i += 1 }',
    'if 5 > 3 { print("a") } elif 1 > 0 { print("b") } else { print("c") }',
    'print(true and "yes")\nprint(false or 7)\nprint(not nil)',
    'fn fib(n) { if n < 2 { return n }\n return fib(n-1) + fib(n-2) }\nprint(fib(12))',
    'fn mk() { c = 0\n fn t() { c += 1\n return c }\n return t }\n'
    'f = mk()\nprint(f())\nprint(f())\nprint(f())',
    'a = [3, 1, 2]\na[0] = 9\npush(a, 5)\nprint(a)\nprint(a[-1])',
    'a = [1, 2, 3]\na[0] += 10\nprint(a)',
    'm = { "x": 1, "y": 2 }\nm["z"] = 3\nprint(len(m))\nprint(m["x"])',
    'm = { "n": 5 }\nm["n"] *= 4\nprint(m["n"])',
    'print("HI".lower())\nprint("a,b,c".split(","))\nprint([3,1,2].sort())',
    'total = 0\nfor n in [10, 20, 30] { total += n }\nprint(total)',
    'print(len("hello"))\nprint(type([]))\nprint(sqrt(144))\nprint(max([4, 9, 2]))',
    'nums = []\nfor i in range(6) { push(nums, i * i) }\nprint(nums)',
    'fn apply(f, x) { return f(f(x)) }\nfn inc(n) { return n + 1 }\nprint(apply(inc, 10))',
]


class TestVMMatchesInterpreter(unittest.TestCase):
    def test_programs(self):
        for i, code in enumerate(PROGRAMS):
            with self.subTest(program=i):
                self.assertEqual(vm(code), walk(code), f"mismatch in program #{i}")

    def test_examples(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = sorted(glob.glob(os.path.join(root, "examples", "*.sy")))
        self.assertTrue(files, "no example programs found")
        for path in files:
            with self.subTest(example=os.path.basename(path)):
                src = open(path, encoding="utf-8").read()
                self.assertEqual(vm(src), walk(src), f"mismatch in {path}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
