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


class TestInterpolation(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(run('name = "Sandy"\nprint("hi {name}")'), "hi Sandy\n")

    def test_expression(self):
        self.assertEqual(run('print("{2 + 3 * 4}")'), "14\n")

    def test_multiple_and_text(self):
        code = 'a = 1\nb = 2\nprint("{a} and {b} make {a + b}")'
        self.assertEqual(run(code), "1 and 2 make 3\n")

    def test_method_call_inside(self):
        self.assertEqual(run('n = "hi"\nprint("{n.upper()}!")'), "HI!\n")

    def test_nested_quotes_and_index(self):
        code = 'm = { "k": 9 }\nprint("val={m["k"]}")'
        self.assertEqual(run(code), "val=9\n")

    def test_literal_braces(self):
        self.assertEqual(run('print("{{literal}}")'), "{literal}\n")

    def test_non_string_values(self):
        code = 'print("list={[1, 2]} nil={nil} bool={true}")'
        self.assertEqual(run(code), "list=[1, 2] nil=nil bool=true\n")

    def test_empty_interpolation_errors(self):
        with self.assertRaises((ParseError, LexError)):
            run('print("bad {}")')


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

    def test_module_import(self):
        import tempfile
        from sandy.runtime import run_source_vm
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "lib.sy"), "w", encoding="utf-8") as f:
            f.write("gain = 10\nfn boost(n) { return n + gain }\n"
                    "struct Pair { a, b }\n")
        main = ('import "lib.sy" as lib\nprint(lib.boost(5))\n'
                'p = lib.Pair(1, 2)\nprint(p.a + p.b)\nprint(lib.gain)')
        o1 = io.StringIO()
        run_source(main, Interpreter(out=o1), base_dir=d)
        self.assertEqual(o1.getvalue(), "15\n3\n10\n")
        # The VM must produce identical output.
        o2 = io.StringIO()
        run_source_vm(main, out=o2, base_dir=d)
        self.assertEqual(o2.getvalue(), o1.getvalue())

    def test_stdlib_math(self):
        out = run('import "math" as m\nprint(m.gcd(48, 36))\n'
                  'print(m.factorial(5))\nprint(m.is_prime(13))\n'
                  'print(m.clamp(99, 0, 10))')
        self.assertEqual(out, "12\n120\ntrue\n10\n")

    def test_stdlib_lists_higher_order(self):
        # Callbacks defined in the caller, passed into stdlib functions.
        out = run('import "lists" as ls\nfn dbl(x) { return x * 2 }\n'
                  'fn odd(x) { return x % 2 == 1 }\n'
                  'print(ls.map(dbl, [1, 2, 3]))\n'
                  'print(ls.filter(odd, [1, 2, 3, 4, 5]))\n'
                  'print(ls.unique([1, 1, 2, 3, 3]))')
        self.assertEqual(out, "[2, 4, 6]\n[1, 3, 5]\n[1, 2, 3]\n")

    def test_stdlib_higher_order_on_vm(self):
        # The VM must match the interpreter, including callbacks into stdlib.
        from sandy.runtime import run_source_vm
        src = ('import "lists" as ls\nimport "strings" as s\n'
               'fn inc(x) { return x + 1 }\n'
               'print(ls.map(inc, [10, 20]))\nprint(s.reverse("abc"))')
        o1 = io.StringIO(); run_source(src, Interpreter(out=o1))
        o2 = io.StringIO(); run_source_vm(src, out=o2)
        self.assertEqual(o1.getvalue(), "[11, 21]\ncba\n")
        self.assertEqual(o2.getvalue(), o1.getvalue())

    def test_import_missing_module(self):
        try:
            run_source('import "does_not_exist.sy" as m', Interpreter(),
                       base_dir="/tmp")
        except RuntimeErrorSandy as e:
            self.assertIn("cannot import", e.message)
        else:
            self.fail("expected RuntimeErrorSandy")

    def test_struct_basics(self):
        out = run('struct Point { x, y }\np = Point(3, 4)\n'
                  'print(p)\nprint(p.x)\np.y = 9\nprint(p.y)')
        self.assertEqual(out, "Point(x=3, y=4)\n3\n9\n")

    def test_struct_equality_by_value(self):
        out = run('struct P { a, b }\nprint(P(1, 2) == P(1, 2))\n'
                  'print(P(1, 2) == P(2, 1))')
        self.assertEqual(out, "true\nfalse\n")

    def test_struct_wrong_field(self):
        try:
            run('struct P { x }\np = P(1)\nprint(p.z)')
        except RuntimeErrorSandy as e:
            self.assertIn("no field 'z'", e.message)
        else:
            self.fail("expected RuntimeErrorSandy")

    def test_struct_arity(self):
        try:
            run('struct P { x, y }\np = P(1)')
        except RuntimeErrorSandy as e:
            self.assertIn("expects 2 field", e.message)
        else:
            self.fail("expected RuntimeErrorSandy")

    def test_try_catch_runtime_error(self):
        out = run('try { x = 1 / 0\n print("no") } catch e { print("got: " + e) }')
        self.assertEqual(out, "got: division by zero\n")

    def test_throw_and_catch(self):
        out = run('try { throw "custom" } catch e { print(e) }')
        self.assertEqual(out, "custom\n")

    def test_throw_propagates_through_calls(self):
        out = run('fn g() { throw "deep" }\nfn f() { g() }\n'
                  'try { f() } catch e { print("caught " + e) }')
        self.assertEqual(out, "caught deep\n")

    def test_uncaught_throw_aborts(self):
        try:
            run('throw "unhandled"')
        except RuntimeErrorSandy as e:
            self.assertEqual(e.message, "unhandled")
        else:
            self.fail("expected RuntimeErrorSandy")

    def test_file_io_roundtrip(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "data.txt").replace("\\", "/")
        out = run(
            f'write_file("{p}", "a\\nb\\n")\n'
            f'append_file("{p}", "c\\n")\n'
            f'print(read_file("{p}"))\n'
            f'print(len(read_lines("{p}")))')
        self.assertEqual(out, "a\nb\nc\n\n3\n")

    def test_read_file_error(self):
        try:
            run('read_file("/no/such/sandy_file.txt")')
        except RuntimeErrorSandy as e:
            self.assertIn("cannot read", e.message)
        else:
            self.fail("expected RuntimeErrorSandy")

    def test_syntax_error_has_column(self):
        # Column info lets the reporter draw a caret at the exact spot.
        try:
            run("x = 1 +* 2")
        except ParseError as e:
            self.assertEqual(e.line, 1)
            self.assertEqual(e.col, 8)  # the stray '*'
        else:
            self.fail("expected ParseError")

    def test_column_tracks_across_lines(self):
        try:
            run("a = 1\nb = )")
        except ParseError as e:
            self.assertEqual(e.line, 2)
            self.assertEqual(e.col, 5)  # the ')' is column 5 on line 2
        else:
            self.fail("expected ParseError")

    def test_did_you_mean_suggestion(self):
        try:
            run("message = 1\nprint(mesage)")
        except RuntimeErrorSandy as e:
            self.assertIn("did you mean 'message'", e.message)
        else:
            self.fail("expected RuntimeErrorSandy")

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
