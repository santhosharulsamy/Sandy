"""Tests for the Sandy formatter (`sandy fmt`).

Run with:  python -m unittest tests.test_format
"""

import glob
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.formatter import format_source
from sandy.runtime import run_source
from sandy.interpreter import Interpreter


def run(code):
    out = io.StringIO()
    run_source(code, Interpreter(out=out))
    return out.getvalue()


# Runnable programs covering many features (no imports / file I/O).
SNIPPETS = [
    'fn add(a,b){return a+b}\nprint(add(2,3))',
    'x=1+2*3-4\nprint(x)\nprint((1+2)*3)',
    'for i in range(5){if i%2==0{print(i)}}',
    'i=0\nwhile i<3{print(i)\ni+=1}',
    'fn mk(){c=0\nfn t(){c+=1\nreturn c}\nreturn t}\nf=mk()\nprint(f())\nprint(f())',
    'a=[3,1,2]\na[0]=9\npush(a,5)\nprint(a)',
    'm={"x":1,"y":2}\nm["z"]=3\nprint(len(m))',
    'struct Point{x,y}\np=Point(3,4)\np.x+=1\nprint(p)\nprint(p.x+p.y)',
    'try{throw "boom"}catch e{print("caught "+e)}',
    'name="Sandy"\nprint("hi {name}, {2+3}!")',
    'print(2**3**2)\nprint(-2**2)\nprint(not true and false)',
    'print(true or false)\nprint("a"<"b")\nprint(10/4)',
]


class TestFormatter(unittest.TestCase):
    def test_idempotent(self):
        for code in SNIPPETS:
            once = format_source(code)
            self.assertEqual(format_source(once), once, f"not idempotent: {code!r}")

    def test_semantics_preserved(self):
        for code in SNIPPETS:
            self.assertEqual(run(format_source(code)), run(code),
                             f"formatting changed behavior of: {code!r}")

    def test_comments_and_blanks_preserved(self):
        code = ("# header\nx = 1  # inline\n\n# section\nfn f() {\n"
                "    # body comment\n    return 1\n}")
        out = format_source(code)
        for expected in ("# header", "# inline", "# section", "# body comment"):
            self.assertIn(expected, out)
        self.assertIn("\n\n", out)  # blank line preserved

    def test_precedence_parentheses(self):
        cases = {
            'x = (a + b) * c': 'x = (a + b) * c',
            'x = a + b * c': 'x = a + b * c',
            'x = (-a) ** 2': 'x = (-a) ** 2',
            'x = -a ** 2': 'x = -a ** 2',
            'x = 2 ** 3 ** 2': 'x = 2 ** 3 ** 2',
            'x = (2 ** 3) ** 2': 'x = (2 ** 3) ** 2',
            'x = (a or b) and c': 'x = (a or b) and c',
        }
        for src, expected in cases.items():
            self.assertEqual(format_source(src).strip(), expected)

    def test_examples_idempotent(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        files = glob.glob(os.path.join(root, "examples", "*.sy"))
        files += glob.glob(os.path.join(root, "examples", "modules", "*.sy"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(example=os.path.basename(path)):
                src = open(path, encoding="utf-8").read()
                once = format_source(src)
                self.assertEqual(format_source(once), once)


if __name__ == "__main__":
    unittest.main()
