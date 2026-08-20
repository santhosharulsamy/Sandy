"""High-level helpers to run Sandy source code."""

import sys

from .errors import SandyError, LexError, ParseError, RuntimeErrorSandy
from .lexer import tokenize
from .parser import parse
from .interpreter import Interpreter


def run_source(source, interp=None, filename="<stdin>"):
    """Lex, parse and evaluate Sandy source. Returns the interpreter used.

    On a Sandy error, prints a friendly diagnostic and raises SandyError.
    """
    if interp is None:
        interp = Interpreter()
    tokens = tokenize(source)
    program = parse(tokens)
    interp.run(program)
    return interp


def run_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"sandy: cannot open {path}: {e.strerror}", file=sys.stderr)
        return 1

    interp = Interpreter()
    try:
        run_source(source, interp, filename=path)
    except LexError as e:
        _report(e.format("SyntaxError"), path, e.line, source)
        return 1
    except ParseError as e:
        _report(e.format("SyntaxError"), path, e.line, source)
        return 1
    except RuntimeErrorSandy as e:
        _report(e.format("RuntimeError"), path, e.line, source)
        return 1
    except SandyError as e:
        _report(e.format("Error"), path, e.line, source)
        return 1
    return 0


def _report(message, path, line, source):
    print(f"\n{path}: {message}", file=sys.stderr)
    if line is not None:
        lines = source.splitlines()
        if 1 <= line <= len(lines):
            print(f"  {line} | {lines[line - 1]}", file=sys.stderr)
