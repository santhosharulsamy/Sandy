"""Benchmark: tree-walking interpreter vs bytecode VM.

Runs a few representative Sandy programs on both engines and prints a
comparison table. Usage:

    python bench/bench.py
"""

import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandy.lexer import tokenize
from sandy.parser import parse
from sandy.interpreter import Interpreter
from sandy.compiler import compile_program
from sandy.vm import VM


PROGRAMS = {
    "fib(27) recursive": """
fn fib(n) {
    if n < 2 { return n }
    return fib(n - 1) + fib(n - 2)
}
print(fib(27))
""",
    "loop sum 1..1000000": """
total = 0
i = 0
while i < 1000000 {
    total += i
    i += 1
}
print(total)
""",
    "nested loops 1000x1000": """
count = 0
for i in range(1000) {
    for j in range(1000) {
        count += 1
    }
}
print(count)
""",
    "string build 50000": """
parts = []
i = 0
while i < 50000 {
    push(parts, "n{i}")
    i += 1
}
print(len(parts))
""",
}


def time_walk(source, repeats):
    program = parse(tokenize(source))
    best = float("inf")
    for _ in range(repeats):
        interp = Interpreter(out=io.StringIO())
        t = time.perf_counter()
        interp.run(program)
        best = min(best, time.perf_counter() - t)
    return best


def time_vm(source, repeats):
    code = compile_program(parse(tokenize(source)))
    best = float("inf")
    for _ in range(repeats):
        vm = VM(out=io.StringIO())
        t = time.perf_counter()
        vm.run(code)
        best = min(best, time.perf_counter() - t)
    return best


def main():
    repeats = 3
    print(f"Python {sys.version.split()[0]}  |  best of {repeats} runs\n")
    header = f"{'benchmark':<26}{'tree-walk':>12}{'vm':>12}{'speedup':>10}"
    print(header)
    print("-" * len(header))
    total_w = total_v = 0.0
    for name, src in PROGRAMS.items():
        w = time_walk(src, repeats)
        v = time_vm(src, repeats)
        total_w += w
        total_v += v
        print(f"{name:<26}{w*1000:>10.1f}ms{v*1000:>10.1f}ms{w/v:>9.2f}x")
    print("-" * len(header))
    print(f"{'TOTAL':<26}{total_w*1000:>10.1f}ms{total_v*1000:>10.1f}ms"
          f"{total_w/total_v:>9.2f}x")


if __name__ == "__main__":
    main()
