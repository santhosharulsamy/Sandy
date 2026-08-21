#!/usr/bin/env python3
"""Convenience launcher so you can run Sandy without installing:

    ./sandy.py examples/hello.sy
    ./sandy.py            # REPL
"""

import sys

from sandy.cli import main

if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    raise SystemExit(main())
