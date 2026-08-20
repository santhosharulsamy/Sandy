"""Enable `python -m sandy`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    raise SystemExit(main())
