# Chapter 19 — Tooling and the CLI

Sandy ships with the tools a language needs to be pleasant to work in: a runner,
a compiler, a type checker, a formatter, a language server, and a browser
playground. All are invoked through `python -m sandy` (shown below as `sandy`).

## The command line

```
sandy                    start the interactive REPL
sandy FILE.sy            run a program (tree-walking interpreter)
sandy run FILE.sy        run a program (explicit)
sandy --vm FILE.sy       run on the bytecode VM
sandy --no-check FILE.sy run without the pre-run type check
sandy check FILE.sy      type-check without running
sandy build FILE.sy      compile the typed subset to a native binary
sandy fmt FILE.sy        format a program in place
sandy add NAME SPEC      add a dependency (version, path, or git URL)
sandy install            resolve dependencies and write sandy.lock
sandy publish            publish the current project to the registry
sandy registry serve     run an HTTP registry server
sandy lsp                start the language server (stdio, for editors)
sandy --version          print the version
sandy --help             show help
```

### Running

`sandy run` uses the tree-walking interpreter — instant, full language, no build
step. `sandy --vm run` uses the bytecode VM, a faster interpreter that is kept
behavior-identical. Both type-check first; pass `--no-check` to skip that for a
quick throwaway run.

Arguments after the filename are passed to the program and read with `args()`:

```bash
sandy run tool.sy input.txt --verbose
```

### Building

`sandy build` compiles the typed subset to a native executable (Chapter 16):

```bash
sandy build app.sy            # -> ./app
sandy build app.sy --run      # build and run
sandy build app.sy -o mytool  # output name
sandy build app.sy --emit-c   # keep the generated C
sandy build app.sy --gc       # link the garbage collector
```

### Checking

`sandy check` runs the type checker and reports, without executing:

```bash
sandy check app.sy
```

```
app.sy: no type errors ✓
```

## The formatter

`sandy fmt` rewrites a file in Sandy's canonical style — consistent indentation,
spacing, and precedence-correct parenthesization — while preserving your comments
and blank lines. It is idempotent (formatting twice changes nothing) and
semantics-preserving.

```bash
sandy fmt app.sy            # reformat in place
sandy fmt --check app.sy    # exit non-zero if not already formatted (for CI)
```

## The language server

`sandy lsp` speaks the Language Server Protocol over stdio, so editors get live
Sandy support: syntax and type-error diagnostics as you type, formatting,
completion (keywords, builtins, and your file's own definitions), a symbol
outline, hover signatures, and go-to-definition. It reuses the same lexer,
parser, checker, and formatter as the CLI, so the editor and the command line
always agree.

A ready-to-use VS Code extension, with a TextMate grammar for syntax
highlighting, lives in `editors/vscode/`.

## The REPL

Running `sandy` with no file starts a read-eval-print loop. Type an expression to
see its value, or statements to run them, with errors reported inline — handy for
exploring the language and the standard library.

## The browser playground

`web/playground.html` runs the **real** Sandy implementation in the browser via
WebAssembly (Pyodide) — no server, no install. Open it locally or host it on any
static site to let people try Sandy from a link. It is generated from the package
sources and kept in sync by a test, so it never drifts from the language.

## Testing your own code

Because the `assert` module (Chapter 17) throws a descriptive message on failure,
you can write tests as ordinary Sandy programs:

```sandy
import "assert" as assert

fn add(a, b) { return a + b }

assert.eq(add(2, 3), 5, "adds")
assert.is_true(add(2, 3) > 0, "positive")
print("all tests passed")
```

Run them with `sandy run tests.sy` (or compile them). The language's own test
suite additionally checks the interpreter and VM against each other and the
native output against the interpreter.

The final chapter is the formal grammar.
