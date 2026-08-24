"""High-level helpers to run Sandy source code."""

import os
import sys

from .errors import SandyError, LexError, ParseError, RuntimeErrorSandy
from .lexer import tokenize
from .parser import parse
from .interpreter import Interpreter


def load_module_interpreted(source, base_dir, out, cache):
    """Run an imported module on the tree-walker; return its exported names."""
    interp = Interpreter(out=out)
    interp.base_dir = base_dir
    interp.module_cache = cache
    interp.module_loader = load_module_interpreted
    interp.run(parse(tokenize(source)))
    return {n: interp.globals.vars[n] for n in interp.user_names()}


def load_module_vm(source, base_dir, out, cache):
    """Run an imported module on the bytecode VM; return its exported names."""
    from .compiler import compile_program
    from .vm import VM
    vm = VM(out=out)
    vm.rt.base_dir = base_dir
    vm.rt.module_cache = cache
    vm.rt.module_loader = load_module_vm
    vm.run(compile_program(parse(tokenize(source))))
    return {n: vm.rt.globals.vars[n] for n in vm.rt.user_names()}


def run_source(source, interp=None, filename="<stdin>", base_dir=None,
               args=None):
    """Lex, parse and evaluate Sandy source with the tree-walking engine.
    Returns the interpreter used. Raises SandyError on a Sandy error."""
    if interp is None:
        interp = Interpreter()
    if base_dir is not None:
        interp.base_dir = base_dir
    if args is not None:
        interp.program_args = list(args)
    interp.module_loader = load_module_interpreted
    tokens = tokenize(source)
    program = parse(tokens)
    interp.run(program)
    return interp


def run_source_vm(source, out=None, base_dir=None, args=None):
    """Lex, parse, compile and execute Sandy source on the bytecode VM."""
    from .compiler import compile_program
    from .vm import VM
    program = parse(tokenize(source))
    vm = VM(out=out)
    if base_dir is not None:
        vm.rt.base_dir = base_dir
    if args is not None:
        vm.rt.program_args = list(args)
    vm.rt.module_loader = load_module_vm
    vm.run(compile_program(program))


def type_check_source(source, base_dir=None):
    """Return a list of (message, line) type errors for Sandy source."""
    from .typecheck import TypeChecker
    return TypeChecker(base_dir=base_dir).check(parse(tokenize(source)))


def build_file(path, output=None, run=False, emit_c=False, gc=False):
    """Compile a Sandy program to a native executable via C.

    Handles the typed scalar core; unsupported features are reported clearly.
    With gc=True, the generated program manages memory with a conservative
    garbage collector instead of leaking (for long-running programs).
    """
    import os
    import shutil
    import subprocess
    import tempfile
    from .cbackend import to_c, NativeUnsupported

    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"sandy: cannot open {path}: {e.strerror}", file=sys.stderr)
        return 1

    try:
        csrc = to_c(parse(tokenize(source)))
    except NativeUnsupported as e:
        _report(e.format("NativeError"), path, e.line, source)
        print("  the native backend supports Sandy's typed scalar core; run "
              "full programs with `sandy --vm` or `sandy run`.", file=sys.stderr)
        return 1
    except (LexError, ParseError) as e:
        _report(e.format("SyntaxError"), path, e.line, source)
        return 1

    cc = next((c for c in ("cc", "gcc", "clang") if shutil.which(c)), None)
    if cc is None:
        print("sandy: no C compiler found (need cc, gcc, or clang)",
              file=sys.stderr)
        return 1

    if output is None:
        output = os.path.splitext(os.path.basename(path))[0]

    c_path = output + ".c" if emit_c else None
    if c_path is None:
        fd, c_path = tempfile.mkstemp(suffix=".c")
        os.close(fd)
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(csrc)

    cc_cmd = [cc, "-O2", "-o", output, c_path, "-lm"]
    if gc:
        cc_cmd.insert(1, "-DSANDY_GC")
    try:
        result = subprocess.run(cc_cmd, capture_output=True, text=True)
    finally:
        if not emit_c:
            try:
                os.remove(c_path)
            except OSError:
                pass

    if result.returncode != 0:
        print(f"sandy: C compilation failed:\n{result.stderr}", file=sys.stderr)
        return 1

    print(f"built native executable: {output}")
    if emit_c:
        print(f"  (C source kept at {c_path})")
    if run:
        return subprocess.run([os.path.abspath(output)]).returncode
    return 0


def run_file(path, engine="walk", check_types=True, args=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"sandy: cannot open {path}: {e.strerror}", file=sys.stderr)
        return 1

    base_dir = os.path.dirname(os.path.abspath(path))
    try:
        if check_types:
            type_errors = type_check_source(source, base_dir=base_dir)
            if type_errors:
                _report_type_errors(type_errors, path, source)
                return 1
        if engine == "vm":
            run_source_vm(source, base_dir=base_dir, args=args)
        else:
            run_source(source, Interpreter(), filename=path, base_dir=base_dir,
                       args=args)
    except LexError as e:
        _report(e.format("SyntaxError"), path, e.line, source, e.col)
        return 1
    except ParseError as e:
        _report(e.format("SyntaxError"), path, e.line, source, e.col)
        return 1
    except RuntimeErrorSandy as e:
        _report(e.format("RuntimeError"), path, e.line, source, e.col)
        return 1
    except SandyError as e:
        _report(e.format("Error"), path, e.line, source, e.col)
        return 1
    return 0


def _report_type_errors(errors, path, source):
    lines = source.splitlines()
    n = len(errors)
    print(f"\n{path}: found {n} type error{'s' if n != 1 else ''} "
          f"before running:", file=sys.stderr)
    for message, line in sorted(errors, key=lambda e: (e[1] or 0)):
        where = f" (line {line})" if line is not None else ""
        print(f"\n  TypeError{where}: {message}", file=sys.stderr)
        if line is not None and 1 <= line <= len(lines):
            print(f"    {line} | {lines[line - 1].strip()}", file=sys.stderr)


def _report(message, path, line, source, col=None):
    print(f"\n{path}: {message}", file=sys.stderr)
    if line is not None:
        lines = source.splitlines()
        if 1 <= line <= len(lines):
            gutter = f"  {line} | "
            print(f"{gutter}{lines[line - 1]}", file=sys.stderr)
            if col is not None and col >= 1:
                print(" " * (len(gutter) + col - 1) + "^", file=sys.stderr)
