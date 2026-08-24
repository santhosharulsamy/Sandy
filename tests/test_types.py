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
from sandy.typecheck import check, TypeChecker


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

    def test_struct_unknown_field(self):
        msgs = messages('struct Point { x: int, y: int }\n'
                        'p: Point = Point(1, 2)\nprint(p.z)')
        self.assertTrue(any("has no field 'z'" in m for m in msgs))

    def test_struct_field_type_mismatch(self):
        msgs = messages('struct Point { x: int, y: int }\np = Point("a", 2)')
        self.assertTrue(any("field 'x' of Point expects int" in m for m in msgs))

    def test_struct_arity(self):
        msgs = messages('struct Point { x, y }\np = Point(1)')
        self.assertTrue(any("expects 2 field" in m for m in msgs))

    def test_struct_field_via_typed_param(self):
        msgs = messages('struct P { x: int }\n'
                        'fn f(p: P) -> int { return p.nope }')
        self.assertTrue(any("has no field 'nope'" in m for m in msgs))

    def test_struct_field_assignment_mismatch(self):
        msgs = messages('struct P { x: int }\np: P = P(1)\np.x = "no"')
        self.assertTrue(any("field 'x'" in m for m in msgs))

    def test_unknown_type_name(self):
        msgs = messages('fn f(w: Widget) -> int { return 1 }')
        self.assertTrue(any("unknown type 'Widget'" in m for m in msgs))


class TestTypedModules(unittest.TestCase):
    """The checker reads imported modules' exported signatures."""

    def test_stdlib_function_arity(self):
        # math.gcd takes two arguments; catch a one-arg call across the import.
        msgs = messages('import "math" as m\nprint(m.gcd(48))')
        self.assertTrue(any("gcd() expects 2 argument" in m for m in msgs))

    def test_unknown_module_member(self):
        msgs = messages('import "math" as m\nprint(m.nope(1))')
        self.assertTrue(any("has no member 'nope'" in m for m in msgs))

    def test_stdlib_calls_are_clean(self):
        code = ('import "math" as m\nimport "lists" as ls\n'
                'fn sq(x) { return x * x }\n'
                'print(m.gcd(48, 36))\nprint(ls.map(sq, [1, 2, 3]))')
        self.assertEqual(errors(code), [])

    def test_imported_struct_field_types(self):
        import tempfile
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "geo.sy"), "w", encoding="utf-8") as f:
            f.write("struct Circle { radius: int }\n"
                    "fn area(c: Circle) -> int { return c.radius * c.radius }\n")
        # Wrong field type when constructing an imported struct.
        errs = TypeChecker(base_dir=d).check(
            parse(tokenize('import "geo.sy" as geo\nc = geo.Circle("x")')))
        self.assertTrue(any("field 'radius' of Circle expects int"
                            in m for m, _ in errs))
        # Valid usage across the boundary is clean.
        ok = TypeChecker(base_dir=d).check(parse(tokenize(
            'import "geo.sy" as geo\nc: Circle = geo.Circle(5)\n'
            'print(geo.area(c))\nprint(c.radius)')))
        self.assertEqual(ok, [])


class TestStructsNoFalsePositives(unittest.TestCase):
    def test_valid_struct_program_is_clean(self):
        code = ('struct Point { x: int, y: int }\n'
                'fn sumxy(a: Point, b: Point) -> int {\n'
                '  return a.x + b.x + a.y + b.y\n}\n'
                'p: Point = Point(2, 3)\nq: Point = Point(4, 5)\n'
                'print(sumxy(p, q))\nprint(p.x)')
        self.assertEqual(errors(code), [])

    def test_unannotated_struct_use_is_clean(self):
        # Without annotations, struct code stays fully dynamic (no errors).
        code = ('struct Point { x, y }\np = Point(1, 2)\n'
                'p.x = 9\nprint(p.x + p.y)')
        self.assertEqual(errors(code), [])


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


class TestFunctionTypes(unittest.TestCase):
    HOF = ('fn apply(f: fn(int) -> int, x: int) -> int { return f(x) }\n'
           'fn twice(n: int) -> int { return n * 2 }\n')

    def test_first_class_function_clean(self):
        code = self.HOF + ('print(apply(twice, 5))\n'
                           'g: fn(int) -> int = twice\nprint(g(3))')
        self.assertEqual(errors(code), [])

    def test_call_through_value_checks_arg_type(self):
        code = self.HOF + 'print(apply(twice, "no"))'
        self.assertTrue(any("argument" in m for m in messages(code)), messages(code))

    def test_call_through_value_checks_arity(self):
        code = ('fn f(g: fn(int, int) -> int) -> int { return g(1) }')
        self.assertTrue(any("argument" in m for m in messages(code)), messages(code))

    def test_wrong_function_return_used(self):
        # twice returns int, so its result flows into a string slot -> error
        code = self.HOF + 'fn need(s: string) -> string { return s }\n' \
                          'print(need(apply(twice, 1)))'
        self.assertTrue(any("expects" in m or "argument" in m
                            for m in messages(code)), messages(code))

    def test_bare_fn_is_gradual(self):
        # A bare `fn` annotation stays fully gradual: no arity/type errors.
        code = ('fn run(f: fn, x) { return f(x) }\n'
                'fn twice(n) { return n * 2 }\nprint(run(twice, 4))')
        self.assertEqual(errors(code), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
