# Benchmarks

Sandy's core promise is *"as easy as Python, but it compiles to a fast native
binary."* This is the evidence for the second half. We measure; we don't claim.

Reproduce it yourself:

```bash
python bench/compare.py          # the numbers below
python bench/compare.py --quick  # a fast smoke run
```

Each benchmark is one algorithm written twice — once in Sandy (typed, so it
compiles natively) and once in equivalent Python — and run as a subprocess so
the timing is the wall-clock time a user actually waits for. The two versions
are checked to compute the same result (`tests/test_bench.py`), so the
comparison is fair.

## Results

CPython 3.11, `cc -O2`, best of 2 runs. Sizes: `fib(30)`, primes `< 40000`,
`sum of i*i to 2,000,000`.

| Benchmark            | Python | Sandy interp | Sandy VM | **Sandy native** | native vs Python |
| -------------------- | -----: | -----------: | -------: | ---------------: | ---------------: |
| `fib(30)` recursive  |  138ms |     23,300ms |  8,300ms |         **3.2ms** |        **43×** |
| count primes `<40k`  |   61ms |      4,480ms |  3,650ms |         **3.9ms** |        **16×** |
| `sum i*i` to 2M      |  293ms |      8,580ms |  4,950ms |         **1.6ms** |       **183×** |

(Exact numbers vary by machine; the ratios are the point.)

## What this says — honestly

**The native backend is the story.** Typed Sandy compiled to a native binary
runs **15–180× faster than CPython** on these programs, because it *is* compiled
C — no interpreter loop, unboxed integers, and the C compiler's `-O2` optimizer
on top. The tight numeric loop (`sum i*i`) is where a compiler pulls furthest
ahead of a bytecode interpreter.

**The interpreter and VM are slower than CPython — and that's expected.** They
are themselves written in Python (a Python program interpreting Sandy), so they
carry Python's per-operation cost plus their own. They exist for fast startup
and development — you edit and `sandy run` with no build step — not for raw
throughput. The VM is consistently ~1.5–3× faster than the tree-walker, as
designed.

**The workflow this enables:** develop against the instant-feedback interpreter,
then `sandy build` the typed hot paths into a binary that beats CPython by an
order of magnitude — without leaving the language or rewriting in C/Rust. That
is the lane Sandy is built to win: Python's ease, a compiled language's speed.

## Caveats

- These are compute-bound microbenchmarks (recursion, loops, integer math) —
  exactly the code where a native compiler helps most. They are not a claim
  about every workload; I/O-bound or allocation-heavy programs will differ.
- Only the statically typed subset compiles natively. Dynamic Sandy runs on the
  interpreter/VM, at interpreter/VM speed.
- Startup is included in the wall-clock time, which is realistic; for the native
  binary startup is ~0, for `sandy run` it includes Python + Sandy import cost.
