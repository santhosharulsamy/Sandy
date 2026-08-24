# The Sandy Programming Language

*A complete guide to the language, its standard library, and its tools.*

*by Santhosh Arulsamy*

Sandy is a small, friendly programming language with a specific ambition: to be
**as easy to write as Python, while compiling to a fast native binary and
catching type errors before your program runs.** You write ordinary, readable,
dynamic code; you add type annotations where they earn their keep; and when you
need speed, you compile the typed parts to a standalone executable that runs at
C speed.

This book covers the language completely — every construct, every rule, the
whole standard library, the tooling, and a formal grammar. It is meant to be
read start to finish by a newcomer, and kept nearby as a reference afterward.

Every example is written in real Sandy and behaves as shown.

---

## Editions

Read it as chapters below, or as a single document:

- **[Single-file HTML edition](the-sandy-programming-language.html)** — the whole
  book on one page.
- **[PDF edition](the-sandy-programming-language.pdf)** — print/download.

Both are generated from the chapters with `python docs/book/build_pdf.py`
(needs `pip install markdown`; the PDF step uses a bundled Chromium).

## How to read this book

If you are new, read Part I, then Part II in order. If you already program,
Chapter 2 will get you productive in ten minutes, and you can dip into the rest
as needed. The standard-library and grammar chapters at the end are references.

You need only Python to run Sandy, and a C compiler (`cc`, `gcc`, or `clang`)
to build native binaries.

```bash
python -m sandy run program.sy      # run a program
python -m sandy check program.sy    # type-check without running
python -m sandy build program.sy    # compile to a native binary
python -m sandy                     # start the interactive REPL
```

---

## Table of contents

### Part I — Getting Started
1. [Introduction](01-introduction.md) — what Sandy is and why it exists
2. [Getting Started](02-getting-started.md) — install, run, and a whirlwind tour

### Part II — The Language
3. [Lexical Structure](03-lexical-structure.md) — tokens, comments, keywords, literals
4. [Values and Types](04-values-and-types.md) — the data Sandy works with
5. [Variables and Assignment](05-variables.md) — binding names to values
6. [Operators and Expressions](06-operators-and-expressions.md) — computing values
7. [Strings](07-strings.md) — text, interpolation, and methods
8. [Control Flow](08-control-flow.md) — `if`, `while`, `for`
9. [Functions](09-functions.md) — definition, closures, first-class functions
10. [Collections](10-collections.md) — lists and maps
11. [Structs](11-structs.md) — user-defined data types
12. [Error Handling](12-error-handling.md) — `try`, `catch`, `throw`
13. [Modules and Packages](13-modules-and-packages.md) — organizing and sharing code

### Part III — Types, Concurrency, Speed
14. [The Type System](14-the-type-system.md) — gradual typing in depth
15. [Concurrency](15-concurrency.md) — tasks and channels
16. [Compilation and Performance](16-compilation-and-performance.md) — the engines and the native compiler

### Part IV — Reference
17. [The Standard Library](17-standard-library.md) — every bundled module
18. [Built-in Functions](18-builtins.md) — every global function
19. [Tooling and the CLI](19-tooling-and-cli.md) — `run`, `build`, `fmt`, `lsp`, the playground
20. [Appendix: Grammar](20-appendix-grammar.md) — the formal syntax

---

*Sandy is young, but it is whole. This book describes the language as it is
today — a complete, working system — not a wish list.*
