"""Command-line entry point for Sandy.

Usage:
  sandy               start the interactive REPL
  sandy <file.sy>     run a Sandy program
  sandy run <file.sy> run a Sandy program (explicit)
  sandy --version     print version
  sandy --help        show this help
"""

import sys

from .runtime import run_file, build_file
from .repl import repl

VERSION = "0.1.0"

HELP = """Sandy — a small, friendly scripting language (.sy)

usage:
  sandy                 start the interactive REPL
  sandy FILE.sy         run a Sandy program
  sandy run FILE.sy     run a Sandy program (explicit)
  sandy build FILE.sy   compile to a native executable (typed scalar core)
  sandy check FILE.sy   type-check a program without running it
  sandy --vm FILE.sy    run on the bytecode VM engine (experimental, faster)
  sandy --no-check FILE.sy  skip the static type checker
  sandy --version       print the version
  sandy --help          show this help
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # Optional flags, anywhere in the arguments.
    engine = "walk"
    check_types = True
    if "--vm" in argv:
        argv.remove("--vm")
        engine = "vm"
    if "--walk" in argv:
        argv.remove("--walk")
        engine = "walk"
    if "--no-check" in argv:
        argv.remove("--no-check")
        check_types = False

    if not argv:
        repl()
        return 0

    first = argv[0]
    if first in ("-h", "--help", "help"):
        print(HELP)
        return 0
    if first in ("-v", "--version", "version"):
        print(f"Sandy {VERSION}")
        return 0
    if first == "build":
        files = [a for a in argv[1:] if not a.startswith("-")]
        if not files:
            print("sandy: 'build' needs a file argument", file=sys.stderr)
            return 2
        output = None
        if "-o" in argv:
            i = argv.index("-o")
            if i + 1 < len(argv):
                output = argv[i + 1]
                files = [f for f in files if f != output]
        return build_file(files[0], output=output,
                          run="--run" in argv, emit_c="--emit-c" in argv)
    if first == "check":
        if len(argv) < 2:
            print("sandy: 'check' needs a file argument", file=sys.stderr)
            return 2
        return check_only(argv[1])
    if first == "run":
        if len(argv) < 2:
            print("sandy: 'run' needs a file argument", file=sys.stderr)
            return 2
        return run_file(argv[1], engine=engine, check_types=check_types)

    # Otherwise treat the first argument as a filename.
    return run_file(first, engine=engine, check_types=check_types)


def check_only(path):
    """Type-check a file and report, without running it."""
    from .runtime import type_check_source
    from .errors import SandyError
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"sandy: cannot open {path}: {e.strerror}", file=sys.stderr)
        return 1
    try:
        errors = type_check_source(source)
    except SandyError as e:
        print(f"{path}: {e.format('SyntaxError')}", file=sys.stderr)
        return 1
    if not errors:
        print(f"{path}: no type errors ✓")
        return 0
    from .runtime import _report_type_errors
    _report_type_errors(errors, path, source)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
