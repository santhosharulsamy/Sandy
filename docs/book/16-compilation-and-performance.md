# Chapter 16 — Compilation and Performance

Sandy runs the same source three ways. This chapter explains each, what compiles
natively, and the performance you can expect.

## Three engines, one language

| Engine | Command | What it's for |
| --- | --- | --- |
| Tree-walking interpreter | `sandy run` | development — instant, no build |
| Bytecode VM | `sandy --vm run` | a faster interpreter; behavior-identical |
| Native compiler | `sandy build` | production speed for the typed subset |

The interpreter and VM run **all** of Sandy, including closures, dynamic values,
and concurrency. The VM compiles to bytecode and runs a stack machine; it is
kept output-identical to the interpreter by an equivalence test suite.

## An honest baseline

The interpreter and VM are themselves written in Python. A Python program
interpreting Sandy is necessarily *slower* than Python running Python — so on
raw throughput the interpreter and VM lose to CPython. They exist for the
edit-run loop, not for speed. All of Sandy's performance advantage comes from the
native compiler.

## Native compilation

`sandy build program.sy` translates the **statically typed subset** of Sandy to
C and compiles it with the system C compiler (`cc`/`gcc`/`clang`) at `-O2`,
producing a standalone executable:

```bash
sandy build fib.sy            # produces ./fib
sandy build fib.sy --run      # build and run
sandy build fib.sy -o app     # choose the output name
sandy build fib.sy --emit-c   # also keep the generated C
sandy build fib.sy --gc       # link a garbage collector (see below)
```

### What compiles

The native backend handles the typed core, which is most of the language:

- scalars (`int`, `float`, `bool`, `string`) and all arithmetic, comparison, and
  logic;
- typed **lists** `list<T>` and **maps** `map<K, V>` as unboxed C arrays and hash
  tables;
- **structs** with typed fields (including list and map fields), with value
  equality and reference semantics preserved;
- **functions** with typed parameters and a return type, including recursion and
  first-class *top-level* functions;
- all **control flow**, and **try / catch / throw**;
- `print`, string operations, and the numeric builtins.

### What does not

Features that are inherently dynamic run on the interpreter/VM instead, and the
compiler rejects them with a clear message: dynamic `any` values, capturing
closures (top-level functions are fine), the OS/network builtins, and
concurrency. When `sandy build` refuses, it tells you exactly why and points you
to `sandy run`.

### Types are the enabler

The compiler needs to know a value's type to emit unboxed code — an `int` as a
machine integer, a `list<int>` as a contiguous array — with no runtime type
tags. That is why the same annotations that make your code *safe* (Chapter 14)
also make it *fast*. Untyped code cannot be compiled natively, because there is
nothing for the compiler to specialize.

### Memory

By default, native programs never free heap memory — which is fine for the
short-lived tools the backend targets, and is the fastest option. For a
long-running program, `sandy build --gc` links a conservative mark-sweep garbage
collector, so memory stays bounded. Output and behavior are identical either
way.

## The numbers

On compute-bound benchmarks (CPython 3.11, `cc -O2`), native Sandy runs
**15–180× faster than CPython**:

| Benchmark | Python | Sandy native | Speedup |
| --- | ---: | ---: | ---: |
| `fib(30)` recursive | 138 ms | 3.2 ms | 43× |
| count primes `< 40k` | 61 ms | 3.9 ms | 16× |
| `sum i*i` to 2,000,000 | 293 ms | 1.6 ms | 183× |

The exact numbers vary by machine; the ratios are the point. The tight numeric
loop shows the largest gap, where a compiler pulls furthest ahead of an
interpreter. Reproduce it with `python bench/compare.py`, and see `BENCHMARKS.md`
for the methodology (the Sandy and Python versions are checked to compute the
same result, so the comparison is fair).

## The recommended workflow

1. Write and iterate with `sandy run` — instant feedback, full language.
2. Add types where they matter, and let `sandy check` guard them.
3. When you need speed, `sandy build` the typed program into a binary that runs
   at C speed.

You never leave the language or rewrite in C or Rust to get there. That is the
lane Sandy is built for.

The remaining chapters are references: the standard library, the builtins, the
tooling, and the grammar.
