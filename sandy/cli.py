"""Command-line entry point for Sandy.

Usage:
  sandy               start the interactive REPL
  sandy <file.sy>     run a Sandy program
  sandy run <file.sy> run a Sandy program (explicit)
  sandy --version     print version
  sandy --help        show this help
"""

import sys

from .runtime import run_file
from .repl import repl

VERSION = "0.1.0"

HELP = """Sandy — a small, friendly scripting language (.sy)

usage:
  sandy                 start the interactive REPL
  sandy FILE.sy         run a Sandy program
  sandy run FILE.sy     run a Sandy program (explicit)
  sandy --version       print the version
  sandy --help          show this help
"""


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

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
    if first == "run":
        if len(argv) < 2:
            print("sandy: 'run' needs a file argument", file=sys.stderr)
            return 2
        return run_file(argv[1])

    # Otherwise treat the first argument as a filename.
    return run_file(first)


if __name__ == "__main__":
    raise SystemExit(main())
