"""Tests for the Sandy standard library (written in Sandy itself).

Each snippet imports a stdlib module by bare name and is run on both engines;
their output must match, and match the expected result.

Run with:  python -m unittest tests.test_stdlib
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.interpreter import Interpreter
from sandy.runtime import run_source, run_source_vm, type_check_source


def interp(src):
    out = io.StringIO()
    run_source(src, Interpreter(out=out))
    return out.getvalue()


def vm(src):
    out = io.StringIO()
    run_source_vm(src, out=out)
    return out.getvalue()


class StdlibCase(unittest.TestCase):
    def check(self, src, expected):
        """Both engines produce `expected`, and the program type-checks clean."""
        self.assertEqual(interp(src), expected, "interpreter")
        self.assertEqual(vm(src), expected, "vm")
        self.assertEqual(type_check_source(src), [], "type checker")


class TestSort(StdlibCase):
    P = 'import "sort" as sort\n'

    def test_sort_numbers_and_strings(self):
        self.check(self.P + "print(sort.sort([3, 1, 2]))\n"
                   'print(sort.sort(["b", "a", "c"]))\n',
                   "[1, 2, 3]\n[\"a\", \"b\", \"c\"]\n")

    def test_sort_is_stable_and_nondestructive(self):
        self.check(self.P + "xs = [3, 1, 2]\nprint(sort.sort(xs))\nprint(xs)\n",
                   "[1, 2, 3]\n[3, 1, 2]\n")

    def test_sort_by_and_desc_and_is_sorted(self):
        src = (self.P + "fn neg(n) { return 0 - n }\n"
               "print(sort.sort_by([1, 3, 2], neg))\n"
               "print(sort.sort_desc([1, 3, 2]))\n"
               "print(sort.is_sorted([1, 2, 2, 3]))\n"
               "print(sort.is_sorted([2, 1]))\n")
        self.check(src, "[3, 2, 1]\n[3, 2, 1]\ntrue\nfalse\n")


class TestSets(StdlibCase):
    P = 'import "sets" as sets\n'

    def test_operations(self):
        src = (self.P +
               "print(sets.union([1, 2], [2, 3]))\n"
               "print(sets.intersection([1, 2, 3], [2, 3, 4]))\n"
               "print(sets.difference([1, 2, 3], [2]))\n"
               "print(sets.symmetric_difference([1, 2], [2, 3]))\n"
               "print(sets.is_subset([1, 2], [1, 2, 3]))\n"
               "print(sets.is_disjoint([1], [2, 3]))\n"
               "print(sets.unique([1, 1, 2, 2, 3]))\n")
        self.check(src, "[1, 2, 3]\n[2, 3]\n[1, 3]\n[1, 3]\ntrue\ntrue\n"
                        "[1, 2, 3]\n")


class TestMath(StdlibCase):
    P = 'import "math" as math\n'

    def test_lcm_and_stats(self):
        src = (self.P +
               "print(math.lcm(4, 6))\n"
               "print(math.median([3, 1, 2]))\n"
               "print(math.median([4, 1, 2, 3]))\n"
               "print(math.gcd(48, 36))\n")
        self.check(src, "12\n2\n2.5\n12\n")

    def test_variance_and_stddev(self):
        # variance([2,4,6]) == 8/3; stddev is its square root.
        src = self.P + "print(math.variance([2, 4, 6]) * 3)\n"
        self.check(src, "8.0\n")


class TestJson(StdlibCase):
    P = 'import "json" as json\n'

    def test_encode(self):
        src = (self.P +
               'print(json.to_json({"a": 1, "b": [2, 3]}))\n'
               'print(json.to_json([true, false, nil]))\n'
               'print(json.to_json("he said \\"hi\\""))\n')
        self.check(src,
                   '{"a":1,"b":[2,3]}\n[true,false,null]\n'
                   '"he said \\"hi\\""\n')

    def test_roundtrip(self):
        src = (self.P +
               'v = json.parse(json.to_json({"n": 42, "xs": [1, 2], '
               '"s": "hi", "ok": true}))\n'
               'print(v["n"])\nprint(v["xs"][1])\nprint(v["s"])\nprint(v["ok"])\n')
        self.check(src, "42\n2\nhi\ntrue\n")

    def test_parse_numbers(self):
        # A flat array exercises int/negative/float parsing without needing a
        # literal brace in the Sandy source (which would start interpolation).
        src = (self.P +
               'd = json.parse("[1, -2, 3.5, true, null]")\n'
               'print(d[0])\nprint(d[1])\nprint(d[2])\nprint(d[3])\n'
               'print(d[4])\n')
        self.check(src, "1\n-2\n3.5\ntrue\nnil\n")

    def test_parse_nested_via_roundtrip(self):
        src = (self.P +
               'orig = {"k": [1, 2], "deep": {"x": 9}}\n'
               'd = json.parse(json.to_json(orig))\n'
               'print(d["k"][1])\nprint(d["deep"]["x"])\n')
        self.check(src, "2\n9\n")

    def test_parse_error_is_reported(self):
        src = (self.P + 'r = "ok"\ntry { r = json.parse("[1, 2") } '
               'catch e { r = "caught" }\nprint(r)\n')
        self.check(src, "caught\n")


class TestRandom(StdlibCase):
    P = 'import "random" as random\n'

    def test_deterministic_given_seed(self):
        # The same seed reproduces the same sequence on both engines.
        src = (self.P + "random.seed(42)\na = []\n"
               "for i in range(5) { push(a, random.randint(1, 6)) }\n"
               "random.seed(42)\nb = []\n"
               "for i in range(5) { push(b, random.randint(1, 6)) }\n"
               "print(a)\nprint(a == b)\n")
        self.check(src, "[6, 3, 6, 5, 6]\ntrue\n")

    def test_randint_in_range_and_next_unit_interval(self):
        src = (self.P + "random.seed(3)\nok = true\n"
               "for i in range(50) { r = random.randint(10, 12)\n"
               "  if r < 10 or r > 12 { ok = false } }\n"
               "print(ok)\n"
               "random.seed(3)\nu = random.next()\n"
               "print(u >= 0.0 and u < 1.0)\n")
        self.check(src, "true\ntrue\n")

    def test_shuffle_is_a_permutation(self):
        src = (self.P + 'import "sort" as sort\nrandom.seed(1)\n'
               "s = random.shuffle([1, 2, 3, 4, 5])\n"
               "print(sort.sort(s))\nprint(len(s))\n")
        self.check(src, "[1, 2, 3, 4, 5]\n5\n")

    def test_sample_size_and_bounds(self):
        src = (self.P + "random.seed(9)\n"
               "print(len(random.sample([1, 2, 3, 4], 2)))\n"
               'ok = "no"\n'
               "try { random.sample([1], 5) } catch e { ok = \"caught\" }\n"
               "print(ok)\n")
        self.check(src, "2\ncaught\n")


class TestOSBuiltins(StdlibCase):
    def test_now_and_clock_are_numbers(self):
        src = ("print(now() > 1000000000.0)\n"      # a real epoch timestamp
               "print(type(clock()))\n")
        self.check(src, "true\nfloat\n")

    def test_env_default_and_present(self):
        os.environ["SANDY_STDLIB_TEST"] = "yes"
        try:
            self.check('print(env("SANDY_STDLIB_TEST"))\n'
                       'print(env("SANDY_DEFINITELY_UNSET_XYZ", "fallback"))\n',
                       "yes\nfallback\n")
        finally:
            del os.environ["SANDY_STDLIB_TEST"]

    def test_sleep_advances_clock(self):
        src = ("start = clock()\nsleep(0.005)\nprint(clock() - start >= 0.0)\n")
        self.check(src, "true\n")


class TestTime(StdlibCase):
    P = 'import "time" as time\n'

    def test_format_durations(self):
        src = (self.P +
               "print(time.format(0))\nprint(time.format(45))\n"
               "print(time.format(125))\nprint(time.format(3723))\n")
        self.check(src, "0s\n45s\n2m 05s\n1h 02m 03s\n")

    def test_since_is_nonnegative(self):
        src = (self.P + "s = time.monotonic()\nprint(time.since(s) >= 0.0)\n")
        self.check(src, "true\n")


class TestArgsAndFilesystem(unittest.TestCase):
    def test_args_are_exposed_on_both_engines(self):
        src = 'print(args())\n'
        out = io.StringIO()
        run_source(src, Interpreter(out=out), args=["a", "b"])
        self.assertEqual(out.getvalue(), '["a", "b"]\n')
        vout = io.StringIO()
        run_source_vm(src, out=vout, args=["a", "b"])
        self.assertEqual(vout.getvalue(), '["a", "b"]\n')

    def test_filesystem_roundtrip(self):
        import tempfile
        d = tempfile.mkdtemp()
        src = (f'p = "{d}/sub"\n'
               'make_dir(p)\n'
               'print(is_dir(p))\n'
               'write_file(p + "/a.txt", "hi")\n'
               'print(exists(p + "/a.txt"))\n'
               'print(is_file(p + "/a.txt"))\n'
               'print(list_dir(p))\n'
               'remove_file(p + "/a.txt")\n'
               'print(exists(p + "/a.txt"))\n')
        out = io.StringIO()
        run_source(src, Interpreter(out=out))
        self.assertEqual(out.getvalue(),
                         'true\ntrue\ntrue\n["a.txt"]\nfalse\n')


class TestOsModule(StdlibCase):
    P = 'import "os" as os\n'

    def test_path_helpers(self):
        src = (self.P +
               'print(os.basename("a/b/c.sy"))\n'
               'print(os.dirname("a/b/c.sy"))\n'
               'print(os.dirname("solo"))\n'
               'print(os.extension("photo.png"))\n'
               'print(os.extension("README"))\n'
               'print(os.stem("a/b/notes.txt"))\n'
               'print(os.join("dir", "file.sy"))\n'
               'print(os.join("dir/", "file.sy"))\n')
        self.check(src,
                   "c.sy\na/b\n\npng\n\nnotes\ndir/file.sy\ndir/file.sy\n")


class TestCharBuiltins(StdlibCase):
    def test_ord_chr_roundtrip(self):
        self.check('print(ord("A"))\nprint(chr(97))\n'
                   'print(chr(ord("a") - 32))\n', "65\na\nA\n")


class TestText(StdlibCase):
    P = 'import "text" as text\n'

    def test_char_predicates(self):
        self.check(self.P +
                   'print(text.is_digit("7"))\nprint(text.is_alpha("z"))\n'
                   'print(text.is_alnum("_"))\nprint(text.is_space("\\t"))\n',
                   "true\ntrue\nfalse\ntrue\n")

    def test_words_lines_chars(self):
        self.check(self.P +
                   'print(text.words("  a   b c "))\n'
                   'print(text.lines("x\\ny"))\nprint(text.chars("hi"))\n',
                   '["a", "b", "c"]\n["x", "y"]\n["h", "i"]\n')

    def test_title_and_count(self):
        self.check(self.P +
                   'print(text.title("hello WORLD"))\n'
                   'print(text.count("abababa", "aba"))\n',
                   "Hello World\n2\n")


class TestCsv(StdlibCase):
    P = 'import "csv" as csv\n'

    def test_parse_basic_and_quoted(self):
        # A quoted field with an embedded comma.
        src = (self.P + 'r = csv.parse("a,b\\nAda,36\\n\\"x, y\\",9")\n'
               "print(r[0])\nprint(r[1])\nprint(r[2][0])\nprint(len(r))\n")
        self.check(src, '["a", "b"]\n["Ada", "36"]\nx, y\n3\n')

    def test_embedded_quote_and_newline(self):
        src = (self.P + 'q = csv.parse("\\"a\\"\\"b\\",\\"l1\\nl2\\"")\n'
               "print(q[0][0])\nprint(q[0][1])\n")
        self.check(src, 'a"b\nl1\nl2\n')

    def test_format_quotes_when_needed(self):
        src = (self.P + 'print(csv.format([["a", "b"], ["c,d", "e"]]))\n')
        self.check(src, 'a,b\n"c,d",e\n')

    def test_roundtrip(self):
        src = (self.P + 'rows = [["x", "y,z"], ["1", "2"]]\n'
               "print(csv.parse(csv.format(rows)) == rows)\n")
        self.check(src, "true\n")


class TestRegex(StdlibCase):
    P = 'import "regex" as regex\n'

    def test_test_find_findall(self):
        self.check(self.P +
                   'print(regex.test("^\\\\d+$", "12345"))\n'
                   'print(regex.test("^\\\\d+$", "12a"))\n'
                   'print(regex.find("\\\\d+", "abc 42 x"))\n'
                   'print(regex.find("z", "abc"))\n'
                   'print(regex.find_all("\\\\w+", "a, bb, ccc"))\n',
                   "true\nfalse\n42\nnil\n[\"a\", \"bb\", \"ccc\"]\n")

    def test_replace_split_groups(self):
        self.check(self.P +
                   'print(regex.replace("\\\\s+", "a   b  c", "_"))\n'
                   'print(regex.split(",\\\\s*", "a, b,c"))\n'
                   'print(regex.groups("(\\\\w+)@(\\\\w+)", "user@host"))\n'
                   'print(regex.replace("(\\\\w+)=(\\\\w+)", "k=v", "\\\\2:\\\\1"))\n',
                   'a_b_c\n["a", "b", "c"]\n["user", "host"]\nv:k\n')

    def test_invalid_pattern_throws(self):
        self.check(self.P + 'msg = "ok"\n'
                   'try { regex.test("(", "x") } catch e { msg = "caught" }\n'
                   'print(msg)\n', "caught\n")


class TestMathBuiltins(StdlibCase):
    def test_trig_log_exp(self):
        self.check("print(floor(sin(0.0) * 1000))\n"
                   "print(floor(cos(0.0) * 1000))\n"
                   "print(floor(exp(0.0)))\n"
                   "print(floor(log(exp(1.0)) * 1000))\n"
                   "print(log10(1000.0))\n", "0\n1000\n1\n1000\n3.0\n")

    def test_math_module_extras(self):
        self.check('import "math" as math\n'
                   "print(math.hypot(3.0, 4.0))\n"
                   "print(math.log_base(8.0, 2.0))\n"
                   "print(floor(math.deg2rad(180.0) * 1000))\n",
                   "5.0\n3.0\n3141\n")


class TestHashAndEncoding(StdlibCase):
    def test_sha256_md5_known_digests(self):
        self.check('print(sha256("hello"))\nprint(md5("hello"))\n',
                   "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e7304336"
                   "2938b9824\n5d41402abc4b2a76b9719d911017c592\n")

    def test_base64_roundtrip_and_error(self):
        self.check('import "base64" as base64\n'
                   'print(base64.encode("hello"))\n'
                   'print(base64.decode("aGVsbG8="))\n'
                   'print(base64.decode(base64.encode("round trip!")))\n'
                   'bad = "ok"\n'
                   'try { base64.decode("!!!") } catch e { bad = "caught" }\n'
                   'print(bad)\n',
                   "aGVsbG8=\nhello\nround trip!\ncaught\n")

    def test_djb2_is_deterministic(self):
        self.check('import "hash" as hash\n'
                   'print(hash.djb2("hello") == hash.djb2("hello"))\n'
                   'print(hash.djb2("hello") != hash.djb2("world"))\n',
                   "true\ntrue\n")


class TestMaps(StdlibCase):
    P = 'import "maps" as maps\n'

    def test_get_items_frompairs(self):
        self.check(self.P + 'm = {"a": 1, "b": 2}\n'
                   'print(maps.get(m, "a", 0))\nprint(maps.get(m, "z", -1))\n'
                   "print(maps.items(m))\n"
                   'print(maps.from_pairs([["k", 1], ["j", 2]]))\n',
                   '1\n-1\n[["a", 1], ["b", 2]]\n{"k": 1, "j": 2}\n')

    def test_merge_invert_pick_mapvalues(self):
        self.check(self.P +
                   'print(maps.merge({"a": 1}, {"a": 9, "c": 3}))\n'
                   'print(maps.invert({"x": "y"}))\n'
                   'print(maps.pick({"a": 1, "b": 2}, ["a", "z"]))\n'
                   'fn dbl(v) { return v * 2 }\n'
                   'print(maps.map_values({"a": 1, "b": 2}, dbl))\n',
                   '{"a": 9, "c": 3}\n{"y": "x"}\n{"a": 1}\n{"a": 2, "b": 4}\n')


class TestAssert(StdlibCase):
    P = 'import "assert" as assert\n'

    def test_pass_and_fail(self):
        src = (self.P +
               'assert.eq(1 + 1, 2, "math")\n'
               'assert.is_true(true, "t")\n'
               'msg = "none"\n'
               'try { assert.eq(1, 2, "nope") } catch e { msg = e }\n'
               'print(msg)\n')
        expected = ("assertion failed: nope (expected 2, got 1)\n")
        self.check(src, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
