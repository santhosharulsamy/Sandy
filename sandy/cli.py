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
  sandy fmt FILE.sy     format a program in place (--check to just verify)
  sandy add NAME SPEC   add a dependency (a version, path, or git URL)
  sandy install         resolve dependencies and write sandy.lock
  sandy publish         publish the current project to the registry
  sandy registry serve  run an HTTP registry server (--port, --dir, --host)
  sandy lsp             start the language server (stdio, for editors)
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
                          run="--run" in argv, emit_c="--emit-c" in argv,
                          gc="--gc" in argv)
    if first == "install":
        return install_cmd()
    if first == "publish":
        return publish_cmd(force="--force" in argv)
    if first == "registry":
        return registry_cmd(argv[1:])
    if first == "add":
        args = [a for a in argv[1:] if not a.startswith("-")]
        if len(args) < 2:
            print("sandy: 'add' needs a name and a path or git URL "
                  "(e.g. `sandy add geometry ../geometry`)", file=sys.stderr)
            return 2
        return add_cmd(args[0], args[1])
    if first == "lsp":
        from .lsp import main as lsp_main
        return lsp_main()
    if first == "fmt":
        files = [a for a in argv[1:] if not a.startswith("-")]
        if not files:
            print("sandy: 'fmt' needs a file argument", file=sys.stderr)
            return 2
        return fmt_files(files, check="--check" in argv)
    if first == "check":
        if len(argv) < 2:
            print("sandy: 'check' needs a file argument", file=sys.stderr)
            return 2
        return check_only(argv[1])
    if first == "run":
        if len(argv) < 2:
            print("sandy: 'run' needs a file argument", file=sys.stderr)
            return 2
        # Everything after the file is passed to the program via args().
        return run_file(argv[1], engine=engine, check_types=check_types,
                        args=argv[2:])

    # Otherwise treat the first argument as a filename; the rest are its args.
    return run_file(first, engine=engine, check_types=check_types,
                    args=argv[1:])


def fmt_files(paths, check=False):
    """Format each file in place, or with --check verify they are formatted."""
    from .formatter import format_source
    from .errors import SandyError
    rc = 0
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            print(f"sandy: cannot open {path}: {e.strerror}", file=sys.stderr)
            rc = 1
            continue
        try:
            formatted = format_source(source)
        except SandyError as e:
            print(f"{path}: {e.format('SyntaxError')}", file=sys.stderr)
            rc = 1
            continue
        if check:
            if formatted != source:
                print(f"{path}: not formatted")
                rc = 1
        elif formatted != source:
            with open(path, "w", encoding="utf-8") as f:
                f.write(formatted)
            print(f"formatted {path}")
    return rc


def install_cmd():
    """Resolve dependencies declared in sandy.toml and write sandy.lock."""
    import os
    from . import packages
    root = packages.find_project_root(os.getcwd())
    if root is None:
        print(f"sandy: no {packages.MANIFEST} found (run `sandy add` to start "
              f"one)", file=sys.stderr)
        return 1
    try:
        resolved = packages.install(root)
    except packages.PackageError as e:
        print(f"sandy: {e}", file=sys.stderr)
        return 1
    if not resolved:
        print("no dependencies to install")
    else:
        for name, info in sorted(resolved.items()):
            print(f"  {name} {info['version']} ({info['source']})")
        print(f"installed {len(resolved)} "
              f"dependenc{'y' if len(resolved) == 1 else 'ies'} "
              f"→ {packages.LOCKFILE}")
    return 0


def registry_cmd(args):
    """`sandy registry serve [--port N] [--dir PATH] [--host H]`."""
    if not args or args[0] != "serve":
        print("usage: sandy registry serve [--port N] [--dir PATH] [--host H]",
              file=sys.stderr)
        return 2

    def opt(flag, default):
        return args[args.index(flag) + 1] if flag in args \
            and args.index(flag) + 1 < len(args) else default

    import os
    from .registry_server import serve
    port = int(opt("--port", "8377"))
    host = opt("--host", "127.0.0.1")
    store = os.path.abspath(opt("--dir", os.path.join(
        os.path.expanduser("~"), ".sandy", "registry")))
    httpd = serve(store, port, host)
    print(f"Sandy registry serving {store} on http://{host}:{port}")
    print(f"  point clients at it:  export SANDY_REGISTRY=http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()
    return 0


def publish_cmd(force=False):
    """Publish the current project to the registry."""
    import os
    from . import packages
    root = packages.find_project_root(os.getcwd())
    if root is None:
        print(f"sandy: no {packages.MANIFEST} found to publish", file=sys.stderr)
        return 1
    try:
        name, version, dest = packages.publish(root, force=force)
    except packages.PackageError as e:
        print(f"sandy: {e}", file=sys.stderr)
        return 1
    print(f"published {name} {version} → {dest}")
    return 0


def add_cmd(name, spec):
    """Add a dependency to sandy.toml, then resolve and lock."""
    import os
    from . import packages
    root = packages.find_project_root(os.getcwd()) or os.getcwd()
    try:
        packages.add_dependency(root, name, spec)
        resolved = packages.install(root)
    except packages.PackageError as e:
        print(f"sandy: {e}", file=sys.stderr)
        return 1
    info = resolved.get(name, {})
    print(f"added {name} {info.get('version', '')} "
          f"({info.get('source', '?')}) → {packages.MANIFEST}")
    return 0


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
        import os
        errors = type_check_source(
            source, base_dir=os.path.dirname(os.path.abspath(path)))
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
