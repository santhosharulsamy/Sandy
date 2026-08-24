# Contributing to Sandy

Thanks for your interest in Sandy! This guide explains how the project is laid
out, how to run it, and how to make a change that lands cleanly.

Sandy is created and maintained by **Santhosh Arulsamy**. Contributions of all
sizes — bug fixes, standard-library modules, examples, documentation — are
welcome.

## Getting set up

You need **Python 3.11+**, and a C compiler (`cc`, `gcc`, or `clang`) if you
want to work on or test the native backend.

```bash
git clone https://github.com/santhosharulsamy/Sandy.git
cd Sandy
python -m sandy --version        # confirm it runs
python -m unittest discover -s tests   # run the whole test suite
```

There are no third-party runtime dependencies; Sandy runs on the standard
library alone.

## Project layout

```
sandy/            the implementation
  lexer.py, parser.py, nodes.py     source -> tokens -> AST
  interpreter.py                    the tree-walking engine
  compiler.py, vm.py, bytecode.py   the bytecode VM
  typecheck.py                      the gradual type checker
  cbackend.py                       the native (C) compiler
  concurrency.py                    tasks and channels
  builtins.py                       global built-in functions
  packages.py, registry_server.py   package manager + registry
  formatter.py, lsp.py              tooling
  stdlib/*.sy                       the standard library, written in Sandy
tests/            the test suite (unittest)
docs/             reference, tour, and the book
examples/         runnable example programs
web/              the browser playground and landing page
bench/            the benchmark suite
editors/vscode/   the VS Code extension and grammar
```

## Running and building

```bash
python -m sandy run program.sy       # interpret
python -m sandy --vm run program.sy  # bytecode VM
python -m sandy check program.sy     # type-check only
python -m sandy build program.sy     # compile to a native binary
python -m sandy fmt program.sy       # format
```

## The rules that keep the build green

A few invariants are enforced by tests — keep them in mind:

1. **The engines must agree.** The interpreter and the VM must produce identical
   output on every program, and the native backend must match the interpreter.
   If you change evaluation, run the full suite; the equivalence tests will
   catch a divergence.

2. **Built-ins stay in sync.** A new built-in must be added in four places:
   `sandy/builtins.py` (the implementation and `BUILTIN_NAMES`), the grammar in
   `editors/vscode/syntaxes/sandy.tmLanguage.json`, and the hover signatures in
   `sandy/lsp.py`. A test checks the grammar against `BUILTIN_NAMES`.

3. **Regenerate the playground last.** `web/playground.html` embeds the package
   sources. If you edit anything under `sandy/`, regenerate it before
   committing, or the drift test fails:
   ```bash
   python web/build_playground.py
   ```

4. **Format your code** to match the surrounding style, and add tests for new
   behavior.

## Adding a standard-library module

Standard-library modules are ordinary Sandy files in `sandy/stdlib/`. Add your
`.sy` file, write it in Sandy, and add tests in `tests/test_stdlib.py` that run
it on **both** engines. A couple of Sandy gotchas worth knowing while you write:

- Statements are newline-separated (no `;`), and `elif`/`else` go on the same
  line as the preceding `}`.
- A literal `{` or `}` inside a string is written doubled (`{{`, `}}`).
- Don't name a module function the same as a builtin it calls (it would recurse).

## Running the benchmarks and building the book

```bash
python bench/compare.py           # cross-runtime benchmarks
python docs/book/build_pdf.py     # rebuild the book (needs `pip install markdown`)
```

## Submitting a change

1. Create a branch, make your change, and add or update tests.
2. Run the full suite: `python -m unittest discover -s tests` — it should be
   all green.
3. Open a pull request describing what you changed and why.

## Reporting bugs

Open an issue with a minimal `.sy` program that reproduces the problem, what you
expected, and what happened. Small, self-contained reproductions get fixed
fastest.

Thank you for helping make Sandy better.
