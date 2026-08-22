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
- [x] Carets that underline the exact spot of a syntax error (the lexer tracks
      columns; errors render `^` under the offending token, in files and REPL)
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
- [x] Parameterized types `list<T>` and `map<K, V>`: literals infer element
      types, and typed indexing returns the element/value type (catching e.g.
      `xs[0] + 1` on a `list<string>`)
- [x] Types feed the compiler so typed code generates faster paths → fast.
      A whole-function fixpoint proves which values are numeric (sound across
      loops); the compiler emits specialized numeric opcodes, guarded so
      gradual `any` values stay safe. **Measured:** typed `fib` now runs
      *faster* than untyped, and the VM is ~1.6× over the tree-walker overall.
- [ ] Flow-sensitive narrowing
- This is the keystone that lets Sandy be easy *and* safe *and* fast at once.

**Honest note on the speed win:** in a pure-Python VM the type-directed
specialization is a real but modest gain — the *decisive* payoff comes when
the same typed bytecode is fed to a native backend (Stage 4). The design is
in place now; Stage 4 is where it compounds.

### Stage 4 — Native compilation ⚡ (the big leap) — *in progress*
Turn Sandy into real machine code and single-file binaries.
- [x] Transpile the **typed scalar core** to C (`sandy/cbackend.py`),
      compiled with the system C compiler at `-O2`
- [x] `sandy build app.sy` → a standalone native executable (`--run`, `-o`,
      `--emit-c`); unsupported features are rejected with a clear message
- [x] Semantics matched to the interpreter (float division, floor modulo,
      number formatting) and verified by compile-and-run tests
- [x] Native **strings**: concatenation, repetition, ordering, `len`, `str`,
      and `.upper()/.lower()/.trim()/.length()` (heap-allocated; a small
      string runtime in the generated C)
- [x] Native **typed lists** `list<int>/<float>/<string>/<bool>` as unboxed
      growable C arrays: literals, indexing, index-set, `len`, `push`,
      for-iteration, printing. ~100× faster per element than the VM. Stays on
      the "typed = fast" thesis — no boxing, no runtime type dispatch.
- [x] Native **typed maps** `map<K,V>` (K int/string, V scalar) as an unboxed
      open-addressing hash table: literals, get, set, `has`, `len`, `keys`,
      `values`, for-iteration and printing — with growth/rehash and
      insertion-order tracking so output/iteration match the interpreter.
- [x] Native **structs** with typed scalar/string/struct/list/map fields:
      construction, field access/mutation, deep value equality (including list
      and map fields), printing, nesting — heap-allocated for reference
      semantics (aliasing + mutation-through-calls match the interpreter).
      List and map fields support access, indexing, iteration, `push`, and
      whole-field reassignment; `==` on lists and maps also compiles natively.
- [x] Native **try / catch / throw**: a setjmp/longjmp handler stack. `throw`
      unwinds across call frames to the innermost handler; the caught value is
      the error message string, and built-in runtime errors (division by zero,
      out-of-range index, missing map key) are catchable — all matching the
      interpreter. Locals in a function that uses `try` are made `volatile` for
      longjmp-safety, and the handler stack is restored on every non-local exit
      (return/break/continue), so only programs that use `try` pay any cost.
- [ ] Heterogeneous/dynamic lists and maps (a tagged-value runtime)
- [x] Garbage collection: `sandy build --gc` routes every native allocation
      through a conservative mark-sweep collector (setjmp register flush +
      stack scan), so long-running programs keep memory bounded instead of
      leaking. Output and iteration order are identical to the leaking build;
      an allocation-heavy loop stays flat (~10 MB) where the leaking build
      climbs to hundreds of MB. Off by default (leak-and-go is faster for
      short-lived tools).
- [ ] Dynamic `any` values, closures, network I/O
- [ ] Consider an LLVM backend once the C route is fully proven
- **Measured:** `fib(35)` runs in **~0.02s** as a native binary vs **~96s**
  on the VM — several thousand× faster. Typed numeric Sandy now runs at C
  speed, because it *is* C. This is the payoff the whole roadmap was aiming
  at: the same types that keep Sandy easy and safe also make it genuinely
  fast once compiled.

### Stage 5 — Real programs need a real language 🎈🛡️ — *in progress*
- [x] Error handling: `try` / `catch` / `throw` (interpreter + VM, with sound
      cross-frame unwinding; the caught value is the error message string).
      Also compiles natively: a setjmp/longjmp handler stack, with built-in
      runtime errors (division by zero, index/key errors) catchable exactly as
      in the interpreter.
- [x] File I/O: `read_file`, `read_lines`, `write_file`, `append_file`
- [x] Modules: `import "file.sy" as name` — namespaced imports resolved
      relative to the importing file, run once (cached), with circular-import
      detection (interpreter + VM; native rejects). Members are functions,
      structs, and variables accessed as `name.member`.
- [x] Typed module members: the checker analyzes imported modules and verifies
      calls to module functions (arity + argument types), module struct
      construction, and member existence (`m.nope` → unknown member) — across
      file boundaries, before running.
- [x] User-defined types: `struct Name { fields }` — construction, `.` field
      access/mutation, value equality, `type()` reporting (interpreter + VM;
      native rejects for now).
- [x] Static struct type-checking: struct names are valid type annotations
      (`p: Point`), and the checker verifies construction (arity + field
      types), field access (`p.z` → unknown field), field assignment, and
      flags unknown type names — all before the program runs, no false
      positives on unannotated code.
- [ ] Network I/O
- [x] A standard library, written in Sandy itself: `math`, `strings`, `lists`
      (higher-order `map`/`filter`/`reduce`), imported by bare name. Ships in
      `sandy/stdlib/`; a local file of the same name shadows it. Modules run on
      the importer's engine, so callbacks stay native (works on both).

### Stage 6 — Scale & ecosystem 🎈💛
- [ ] Concurrency model (simple, safe — the Go lane done right)
- [ ] Package manager + registry
- [ ] Editor support (LSP): completion, go-to-def, inline errors
- [x] Formatter (`sandy fmt`): canonical pretty-printer that preserves
      comments and blank lines, with precedence-correct parenthesization;
      `--check` mode; verified idempotent and semantics-preserving.
- [x] Language reference (`docs/reference.md`): grammar, semantics, type system.
- [x] Editor support (LSP): `sandy lsp` speaks LSP over stdio — live
      diagnostics (syntax + type errors), formatting, completion (keywords,
      builtins, file definitions), and a symbol outline — reusing the same
      lexer/parser/checker/formatter.
- [x] Web playground: `web/playground.html` runs the real implementation in
      the browser via Pyodide (WASM), generated from the package sources and
      guarded against drift by a test.
- [x] Syntax highlighting: a TextMate grammar + VS Code extension in
      `editors/vscode/`; keyword/builtin lists kept in sync by a test.
- [x] Richer LSP: hover (function/struct/parameter/builtin signatures) and
      go-to-definition, resolved from token positions + the AST (scope-aware
      for parameters via block end-lines).
- [ ] Debugger, docs generator, find-references / rename

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
