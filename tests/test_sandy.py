"""Tests for the Sandy interpreter.

Run with:  python -m unittest discover -s tests
       or:  python tests/test_sandy.py
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.interpreter import Interpreter
from sandy.runtime import run_source
from sandy.errors import RuntimeErrorSandy, ParseError, LexError


def run(code):
    """Run Sandy source, returning everything print() produced."""
    out = io.StringIO()
    interp = Interpreter(out=out)
    run_source(code, interp)
    return out.getvalue()


class TestBasics(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(run('print("hi")'), "hi\n")

    def test_arithmetic(self):
        self.assertEqual(run("print(2 + 3 * 4)"), "14\n")
        self.assertEqual(run("print((2 + 3) * 4)"), "20\n")
        self.assertEqual(run("print(2 ** 10)"), "1024\n")
        self.assertEqual(run("print(17 % 5)"), "2\n")

    def test_true_division_is_float(self):
        self.assertEqual(run("print(10 / 2)"), "5.0\n")
        self.assertEqual(run("print(7 / 2)"), "3.5\n")

    def test_unary_and_power_precedence(self):
        self.assertEqual(run("print(-2 ** 2)"), "-4\n")  # -(2**2)
        self.assertEqual(run("print(2 ** -1)"), "0.5\n")

    def test_string_ops(self):
        self.assertEqual(run('print("ab" + "cd")'), "abcd\n")
        self.assertEqual(run('print("ha" * 3)'), "hahaha\n")

    def test_variables_and_compound_assign(self):
        self.assertEqual(run("x = 5\nx += 3\nprint(x)"), "8\n")
        self.assertEqual(run("x = 10\nx /= 4\nprint(x)"), "2.5\n")


class TestControlFlow(unittest.TestCase):
    def test_if_elif_else(self):
        code = "x = 5\nif x > 10 { print(\"big\") } elif x > 3 { print(\"mid\") } else { print(\"small\") }"
        self.assertEqual(run(code), "mid\n")

    def test_while(self):
        code = "i = 0\nwhile i < 3 { print(i)\n i += 1 }"
        self.assertEqual(run(code), "0\n1\n2\n")

    def test_for_range(self):
        self.assertEqual(run("for i in range(3) { print(i) }"), "0\n1\n2\n")

    def test_break_continue(self):
        code = "for i in range(10) { if i == 2 { continue }\n if i == 4 { break }\n print(i) }"
        self.assertEqual(run(code), "0\n1\n3\n")

    def test_logical_short_circuit(self):
        self.assertEqual(run('print(true and "yes")'), "yes\n")
        self.assertEqual(run('print(false or "fallback")'), "fallback\n")
        self.assertEqual(run("print(not false)"), "true\n")


class TestFunctions(unittest.TestCase):
    def test_recursion(self):
        code = "fn fib(n) { if n < 2 { return n }\n return fib(n-1) + fib(n-2) }\nprint(fib(10))"
        self.assertEqual(run(code), "55\n")

    def test_closures(self):
        code = (
            "fn counter() { c = 0\n fn tick() { c += 1\n return c }\n return tick }\n"
            "t = counter()\nprint(t())\nprint(t())"
        )
        self.assertEqual(run(code), "1\n2\n")

    def test_higher_order(self):
        code = (
            "fn twice(f, x) { return f(f(x)) }\n"
            "fn inc(n) { return n + 1 }\n"
            "print(twice(inc, 10))"
        )
        self.assertEqual(run(code), "12\n")


class TestDataStructures(unittest.TestCase):
    def test_list_index_and_negative(self):
        self.assertEqual(run("a = [10, 20, 30]\nprint(a[0])\nprint(a[-1])"), "10\n30\n")

    def test_list_mutate(self):
        self.assertEqual(run("a = [1]\npush(a, 2)\na[0] = 9\nprint(a)"), "[9, 2]\n")

    def test_map(self):
        code = 'm = { "a": 1, "b": 2 }\nprint(m["a"])\nm["c"] = 3\nprint(len(m))'
        self.assertEqual(run(code), "1\n3\n")

    def test_multiline_list_and_map(self):
        code = (
            "a = [\n 1,\n 2,\n 3,\n]\n"
            'm = {\n "x": 1,\n "y": 2,\n}\n'
            "print(len(a))\nprint(len(m))"
        )
        self.assertEqual(run(code), "3\n2\n")

    def test_methods(self):
        self.assertEqual(run('print("hi".upper())'), "HI\n")
        self.assertEqual(run('print("a,b".split(","))'), '["a", "b"]\n')
        self.assertEqual(run("a = [3,1,2]\nprint(a.sort())"), "[1, 2, 3]\n")
        self.assertEqual(run('m = {"k": 1}\nprint(m.has("k"))'), "true\n")


class TestBuiltins(unittest.TestCase):
    def test_conversions(self):
        self.assertEqual(run('print(int("42") + 1)'), "43\n")
        self.assertEqual(run('print(float("1.5") * 2)'), "3.0\n")
        self.assertEqual(run("print(str(123) + \"!\")"), "123!\n")

    def test_len_type(self):
        self.assertEqual(run('print(len("abc"))'), "3\n")
        self.assertEqual(run('print(type([]))'), "list\n")
        self.assertEqual(run('print(type(1.0))'), "float\n")

    def test_math(self):
        self.assertEqual(run("print(sqrt(16))"), "4.0\n")
        self.assertEqual(run("print(abs(-7))"), "7\n")
        self.assertEqual(run("print(max([3, 9, 2]))"), "9\n")
        self.assertEqual(run("print(sum([1, 2, 3]))"), "6\n")


class TestErrors(unittest.TestCase):
    def test_undefined_variable(self):
        with self.assertRaises(RuntimeErrorSandy):
            run("print(nope)")

    def test_division_by_zero(self):
        with self.assertRaises(RuntimeErrorSandy):
            run("print(1 / 0)")

    def test_type_error(self):
        with self.assertRaises(RuntimeErrorSandy):
            run('print(1 + "a")')

    def test_index_out_of_range(self):
        with self.assertRaises(RuntimeErrorSandy):
            run("a = [1]\nprint(a[5])")

    def test_parse_error(self):
        with self.assertRaises(ParseError):
            run("fn (")

    def test_line_number_reported(self):
        try:
            run("x = 1\ny = 2\nprint(undefined_here)")
        except RuntimeErrorSandy as e:
            self.assertEqual(e.line, 3)
        else:
            self.fail("expected RuntimeErrorSandy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
