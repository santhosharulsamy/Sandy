"""A small interactive REPL for Sandy."""

import sys

from .errors import SandyError
from .lexer import tokenize
from .parser import parse
from . import nodes as N
from .interpreter import Interpreter
from .values import to_str

BANNER = "Sandy 0.1.0 — type expressions or statements, 'exit' to quit."


def repl():
    interp = Interpreter()
    print(BANNER)
    while True:
        try:
            line = input("sandy> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip() in ("exit", "quit"):
            break
        if not line.strip():
            continue
        try:
            program = parse(tokenize(line))
            # If the last statement is a bare expression, echo its value.
            _run_and_echo(interp, program)
        except SandyError as e:
            print(e.format("Error"), file=sys.stderr)
            # Point at the offending column when we know it (single line here).
            if getattr(e, "col", None):
                print("  " + line, file=sys.stderr)
                print("  " + " " * (e.col - 1) + "^", file=sys.stderr)


def _run_and_echo(interp, program):
    stmts = program.statements
    if stmts and isinstance(stmts[-1], N.ExprStmt):
        last = stmts[-1]
        for s in stmts[:-1]:
            interp._exec(s, interp.globals)
        value = interp._eval(last.expr, interp.globals)
        if value is not None:
            print(to_str(value))
    else:
        interp.run(program)
