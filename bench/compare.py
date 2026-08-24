"""Cross-runtime benchmarks: Python vs Sandy (interpreter, VM, native).

Each benchmark is one algorithm expressed twice — once in Sandy (typed, so it
compiles natively) and once in equivalent Python — plus the expected result.
We run each as a subprocess and report wall-clock time, which is what a user
actually waits for (Sandy's startup is part of the experience).

    python bench/compare.py            # full run
    python bench/compare.py --quick    # smaller sizes (fast; for a smoke check)

Honest expectation: Sandy's interpreter and VM are themselves written in
Python, so they are *slower* than CPython — they are for quick runs and
development. The point of the project is the last column: typed Sandy compiled
to a native binary, which runs many times faster than CPython because it *is*
compiled C.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CC = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)


# Each entry: name -> (sandy_template, python_template, full_N, quick_N, expected_fn)
# Templates take a single {n} parameter.
BENCHMARKS = {
    "fib(N) recursive": (
        "fn fib(n: int) -> int {{\n"
        "    if n < 2 {{ return n }}\n"
        "    return fib(n - 1) + fib(n - 2)\n"
        "}}\n"
        "print(fib({n}))\n",
        "def fib(n):\n"
        "    if n < 2: return n\n"
        "    return fib(n - 1) + fib(n - 2)\n"
        "print(fib({n}))\n",
        30, 25,
        lambda n: _fib(n),
    ),
    "count primes < N": (
        "fn count(limit: int) -> int {{\n"
        "    c: int = 0\n"
        "    n: int = 2\n"
        "    while n < limit {{\n"
        "        prime: bool = true\n"
        "        d: int = 2\n"
        "        while d * d <= n {{\n"
        "            if n % d == 0 {{ prime = false\n d = n }}\n"
        "            d += 1\n"
        "        }}\n"
        "        if prime {{ c += 1 }}\n"
        "        n += 1\n"
        "    }}\n"
        "    return c\n"
        "}}\n"
        "print(count({n}))\n",
        "def count(limit):\n"
        "    c = 0\n"
        "    for n in range(2, limit):\n"
        "        prime = True\n"
        "        d = 2\n"
        "        while d * d <= n:\n"
        "            if n % d == 0:\n"
        "                prime = False; break\n"
        "            d += 1\n"
        "        if prime: c += 1\n"
        "    return c\n"
        "print(count({n}))\n",
        40000, 20000,
        lambda n: _count_primes(n),
    ),
    "sum i*i to N": (
        "total: int = 0\n"
        "i: int = 0\n"
        "while i < {n} {{\n"
        "    total += i * i\n"
        "    i += 1\n"
        "}}\n"
        "print(total)\n",
        "total = 0\n"
        "i = 0\n"
        "while i < {n}:\n"
        "    total += i * i\n"
        "    i += 1\n"
        "print(total)\n",
        2000000, 200000,
        lambda n: sum(i * i for i in range(n)),
    ),
}


def _fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _count_primes(limit):
    c = 0
    for n in range(2, limit):
        d, prime = 2, True
        while d * d <= n:
            if n % d == 0:
                prime = False
                break
            d += 1
        if prime:
            c += 1
    return c


def _best(cmd, repeats, cwd=None):
    """Best wall-clock time (seconds) over `repeats` runs, and stdout."""
    best, out = float("inf"), ""
    for _ in range(repeats):
        t = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        best = min(best, time.perf_counter() - t)
        out = r.stdout.strip()
        if r.returncode != 0:
            return None, (r.stderr.strip() or "failed")
    return best, out


def run(quick=False, repeats=3):
    tmp = tempfile.mkdtemp()
    print(f"Python {sys.version.split()[0]}  |  best of {repeats}  |  "
          f"C compiler: {CC or 'none'}\n")
    cols = f"{'benchmark':<20}{'python':>11}{'interp':>11}{'vm':>11}" \
           f"{'native':>11}{'native vs py':>14}"
    print(cols)
    print("-" * len(cols))
    for name, (sy_t, py_t, full_n, quick_n, _) in BENCHMARKS.items():
        n = quick_n if quick else full_n
        sy_path = os.path.join(tmp, "b.sy")
        py_path = os.path.join(tmp, "b.py")
        with open(sy_path, "w") as f:
            f.write(sy_t.format(n=n))
        with open(py_path, "w") as f:
            f.write(py_t.format(n=n))
        py, _o = _best([sys.executable, py_path], repeats)
        interp, _o = _best(
            [sys.executable, "-m", "sandy", "run", sy_path], repeats, cwd=ROOT)
        vm, _o = _best(
            [sys.executable, "-m", "sandy", "--vm", "run", sy_path], repeats,
            cwd=ROOT)
        native = None
        if CC is not None:
            exe = os.path.join(tmp, "b")
            build = subprocess.run(
                [sys.executable, "-m", "sandy", "build", sy_path, "-o", exe],
                capture_output=True, text=True, cwd=ROOT)
            if build.returncode == 0:
                native, _o = _best([exe], repeats)

        def ms(x):
            return f"{x * 1000:>9.1f}ms" if x else f"{'—':>11}"
        speedup = f"{py / native:>12.1f}x" if (py and native) else f"{'—':>14}"
        print(f"{name:<20}{ms(py)}{ms(interp)}{ms(vm)}{ms(native)}{speedup:>14}")
    print("-" * len(cols))
    print("\nnative vs py = how many times faster the native Sandy binary is "
          "than CPython.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="smaller sizes")
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()
    run(quick=args.quick, repeats=args.repeats)
