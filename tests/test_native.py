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


def compile_and_run(src, gc=False):
    csrc = to_c(parse(tokenize(src)))
    tmp = tempfile.mkdtemp()
    c_file = os.path.join(tmp, "prog.c")
    exe = os.path.join(tmp, "prog")
    with open(c_file, "w") as f:
        f.write(csrc)
    cmd = [CC, "-O2", "-o", exe, c_file, "-lm"]
    if gc:
        cmd.insert(1, "-DSANDY_GC")
    subprocess.run(cmd, check=True, capture_output=True)
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
    # structs: construction, field access/mutation, functions, equality,
    # printing, nesting, and reference semantics
    'struct Point { x: int, y: int }\n'
    'fn move(p: Point, dx: int) -> Point { return Point(p.x + dx, p.y) }\n'
    'p: Point = Point(1, 2)\np.x = 10\np.y += 5\nprint(p)\n'
    'q: Point = move(p, 3)\nprint(q)\n'
    'print(Point(1, 1) == Point(1, 1))\nprint(Point(1, 1) == Point(1, 2))\n'
    'struct Line { a: Point, b: Point }\n'
    'seg: Line = Line(Point(0, 0), Point(3, 4))\nprint(seg)\nprint(seg.b.x)',
    # reference semantics: aliasing and mutation through a call
    'struct Box { n: int }\nfn bump(b: Box) { b.n += 100 }\n'
    'a: Box = Box(1)\nb: Box = a\nb.n = 42\nprint(a.n)\nbump(a)\nprint(a.n)',
    # struct fields of list<T> and map<K,V> type: construction, printing,
    # access/index/len/has, iteration, push/index-set/map-set mutation,
    # whole-field reassignment (incl. an empty literal), value equality
    # (list and map fields), and a nested struct holding collection fields
    'struct Bag { name: string, items: list<int>, tags: map<string, int> }\n'
    'fn total(b: Bag) -> int { s: int = 0\n for x in b.items { s += x }\n'
    ' return s }\n'
    'b: Bag = Bag("f", [1, 2, 3], {"a": 1, "b": 2})\nprint(b)\n'
    'print(b.items[1])\nprint(len(b.items))\nprint(b.tags["a"])\n'
    'print(has(b.tags, "z"))\nprint(total(b))\n'
    'push(b.items, 99)\nb.items[0] = 40\nprint(b.items)\nprint(total(b))\n'
    'b.tags["c"] = 3\nb.tags["a"] = 10\nprint(b.tags)\n'
    'b.items = []\npush(b.items, 7)\nprint(b.items)\n'
    'p: Bag = Bag("x", [1, 2], {"k": 5})\nq: Bag = Bag("x", [1, 2], {"k": 5})\n'
    'r: Bag = Bag("x", [1, 9], {"k": 5})\nprint(p == q)\nprint(p == r)\n'
    'struct Wrap { inner: Bag, note: string }\n'
    'w: Wrap = Wrap(Bag("in", [5, 6], {}), "hi")\nprint(w)\n'
    'print(w.inner.items[0])\n'
    'print([1, 2, 3] == [1, 2, 3])\nprint([1, 2] == [1, 2, 3])',
    # try/catch/throw: explicit throw, caught built-in errors (div-by-zero,
    # list index, map key), return-from-try, nesting/rethrow, break-from-try,
    # cross-frame unwinding, and a local mutated in a try then read after
    'fn sdiv(a: float, b: float) -> float {\n'
    ' try { return a / b } catch e { return -1.0 } }\n'
    'fn at(xs: list<int>, i: int) -> int {\n'
    ' try { return xs[i] } catch e { return -999 } }\n'
    'fn deep(n: int) -> int { if n == 0 { throw "bottom" }\n'
    ' return deep(n - 1) }\n'
    'print(sdiv(10.0, 0.0))\nprint(sdiv(9.0, 2.0))\n'
    'a: list<int> = [7, 8, 9]\nprint(at(a, 1))\nprint(at(a, 50))\n'
    'try { throw "boom" } catch m { print("c1: " + m) }\n'
    'try { x: int = 42\n throw x } catch m { print("c2: " + m) }\n'
    'try { try { throw "in" } catch e { throw "re-" + e } }\n'
    ' catch e { print("c3: " + e) }\n'
    'try { deep(4) } catch e { print("c4: " + e) }\n'
    'mp: map<string, int> = {"a": 1}\n'
    'try { print(mp["z"]) } catch e { print("c5: " + e) }\n'
    'acc: int = 100\ntry { acc = 205\n throw "y" } catch e { acc += 1 }\n'
    'print(acc)\n'
    't: int = 0\nfor i in range(8) {\n'
    ' try { if i == 5 { throw "s" }\n t += i } catch e { break } }\nprint(t)',
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
    'struct S { x }\np: S = S(1)',                      # untyped struct field
]


@unittest.skipIf(CC is None, "no C compiler available")
class TestNativeMatchesInterpreter(unittest.TestCase):
    def test_supported_programs(self):
        for i, src in enumerate(SUPPORTED):
            with self.subTest(program=i):
                self.assertEqual(compile_and_run(src), interpret(src),
                                 f"native != interpreter for program #{i}")

    def test_gc_matches_and_bounds_memory(self):
        # An allocation-heavy program: with the GC on, output must be identical
        # to the interpreter, and peak memory must be far below the leaking
        # build (proving collection actually happens).
        src = ('struct P { x: int }\n'
               'total: int = 0\n'
               'for i in range(120000) {\n'
               '    s: string = "n-" + str(i)\n'
               '    xs: list<int> = [i, i * 2]\n'
               '    p: P = P(i)\n'
               '    total += len(s) + xs[1] + p.x\n'
               '}\nprint(total)')
        self.assertEqual(compile_and_run(src, gc=True), interpret(src))

        import resource
        exe_leak = self._build(src, gc=False)
        exe_gc = self._build(src, gc=True)
        leak = self._peak_rss(exe_leak)
        gc = self._peak_rss(exe_gc)
        self.assertLess(gc * 2, leak,
                        f"GC did not bound memory (leak={leak}, gc={gc})")

    def _build(self, src, gc):
        csrc = to_c(parse(tokenize(src)))
        tmp = tempfile.mkdtemp()
        c_file, exe = os.path.join(tmp, "p.c"), os.path.join(tmp, "p")
        with open(c_file, "w") as f:
            f.write(csrc)
        cmd = [CC, "-O2", "-o", exe, c_file, "-lm"]
        if gc:
            cmd.insert(1, "-DSANDY_GC")
        subprocess.run(cmd, check=True, capture_output=True)
        return exe

    def _peak_rss(self, exe):
        # Peak RSS of a fresh child process (KB), isolated in a subprocess.
        r = subprocess.run(
            [sys.executable, "-c",
             "import subprocess,resource,sys;"
             "subprocess.run([sys.argv[1]],stdout=subprocess.DEVNULL);"
             "print(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)",
             exe], capture_output=True, text=True)
        return int(r.stdout.strip())

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
