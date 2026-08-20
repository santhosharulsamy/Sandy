# Sandy Roadmap — the plan to lead

**The aim:** make Sandy the best language in the world in its lane —
*as easy as Python, as fast as a compiled language, safe where it counts,
and a joy to use.*

**The honest reality:** no language is best at everything, because language
design is a set of tradeoffs — at their extremes, ease, speed, safety and
simplicity fight each other. So we don't chase all four at once. We chase
them **in order**, where each early step happens to serve several goals at
once. That's how Sandy climbs toward all four without stalling.

This document is the committed plan. It turns four ambitions into staged,
checkable milestones.

---

## The four lanes

| Lane | Goal | Primary rival to beat |
| --- | --- | --- |
| ⚡ **Fast** | Native-code speed | Python (slow), while staying easier than Rust |
| 🎈 **Easy** | Python-level ease, less ceremony | Rust / C / Java (hard) |
| 🛡️ **Safe** | Catch bugs early, no crashes-by-default | Python / JS (runtime surprises) |
| 💛 **Lovable** | Best errors, tooling, zero-config | Everyone (DX is universally underinvested) |

The single design point that unifies them:

> **"Sandy is as easy to write as Python, but it compiles to a fast native
> binary, tells you exactly what's wrong before you ship, and needs zero
> setup to run."**

Nail that and Sandy is genuinely *ahead of Python* (speed, safety) and
*ahead of Rust/C* (ease) — in one focused, defensible lane.

---

## Where Sandy is today (v0.1)

✅ A complete, working language: lexer → parser → tree-walking interpreter,
CLI, REPL, closures, lists/maps, string interpolation, ~30 builtins, a
friendly test suite.

⚠️ **Speed:** slowest of the pack — a tree-walker written in Python.
⚠️ No native compilation, no static types, no modules, no error handling.

v0.1 is the *foundation*. Everything below builds on it.

---

## The staged plan

Each stage lists which lanes it advances. Notice the early stages are cheap
and multi-lane — that's deliberate.

### Stage 1 — Make it lovable *now* 💛 (cheap, immediate)
The fastest wins, and they cost almost nothing. Do these first because they
make Sandy pleasant even before it's fast.
- [x] Friendly, line-numbered error messages
- [x] "Did you mean …?" suggestions for typos
- [ ] Carets that underline the exact spot of an error (needs column tracking)
- [ ] Contextual hints ("strings are immutable — build a new one with +")
- [ ] One-command install / single self-contained launcher
- [ ] A fast, comfortable REPL (history, multi-line editing)

### Stage 2 — Bytecode compiler + VM ⚡ (the first real speed jump) — *in progress*
Replace tree-walking with a compile-to-bytecode + stack VM design (the same
architecture CPython and Lua use).
- [x] Compile the AST to a flat bytecode instruction set (`sandy/bytecode.py`, `sandy/compiler.py`)
- [x] Stack-based VM executing that bytecode (`sandy/vm.py`), run with `sandy --vm file.sy`
- [x] Inlined fast paths for arithmetic/comparison + frequency-ordered dispatch
- [x] **Benchmark harness** comparing against the tree-walker (`bench/bench.py`)
- [x] Equivalence tests: VM output matches the interpreter on every program
- [ ] Constant folding + peephole optimizations
- [ ] Local-variable slots (skip the name lookup on hot paths)
- **Result so far (pure-Python VM):** ~1.5× faster overall, 1.7× on
  recursion-heavy code. Bigger multipliers come from the local-slot work
  above and, decisively, from Stages 3–4 (types + native compilation).

### Stage 3 — Gradual types 🛡️⚡ (safety *and* speed, together) — *in progress*
Optional type annotations that you can add where you want them.
- [x] Syntax: `fn add(a: int, b: int) -> int { ... }` and `x: int = 5`
- [x] A type checker that runs before execution (`sandy/typecheck.py`), so
      bugs are caught up front → safe. `sandy check file.sy` checks only.
- [x] Gradual: unannotated code is `any`, runs unchanged, zero false positives
- [ ] Types feed the compiler so typed code generates faster paths → fast
- [ ] Parameterized types (`list<int>`, `map<string, int>`)
- [ ] Flow-sensitive narrowing
- This is the keystone that lets Sandy be easy *and* safe *and* fast at once.

### Stage 4 — Native compilation ⚡ (the big leap)
Turn Sandy into real machine code and single-file binaries.
- [ ] Emit LLVM IR (or transpile to C) from typed bytecode
- [ ] `sandy build app.sy` → a standalone native executable
- [ ] Runtime for dynamic values, garbage collection strategy
- **Expected:** competitive-with-compiled-language speed for typed code.

### Stage 5 — Real programs need a real language 🎈🛡️
- [ ] Error handling (`try` / `catch`, or a Result-style approach)
- [ ] Modules / `import` and a project layout
- [ ] User-defined types (structs / records)
- [ ] File & network I/O
- [ ] A standard library worth reaching for

### Stage 6 — Scale & ecosystem 🎈💛
- [ ] Concurrency model (simple, safe — the Go lane done right)
- [ ] Package manager + registry
- [ ] Editor support (LSP): completion, go-to-def, inline errors
- [ ] Formatter, debugger, docs generator

---

## How we'll know we're winning

We measure, we don't claim. Each stage ships with evidence:
- **Speed:** a public benchmark suite vs Python/Node on the same programs.
- **Safety:** a corpus of bug-y programs we catch before runtime.
- **Ease:** line-count and "time to first working program" vs other languages.
- **Love:** the error messages speak for themselves — put them side by side.

"Ahead of everything" is a slogan. **"Fastest easy language, with the
friendliest errors, that compiles to a single binary"** is a scoreboard we
can actually top.

---

## Next up

**Stage 2: the bytecode VM.** It's the first change that turns "fast" from
an aspiration into a number we can measure. Everything after it (types,
native compilation) builds on that bytecode. That's what we build next.
