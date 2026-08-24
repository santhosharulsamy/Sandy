# Changelog

All notable changes to Sandy are recorded here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Language & engines
- Tree-walking interpreter and a bytecode VM that produce identical output on
  every program (kept in lock-step by equivalence tests).
- Gradual type system: optional annotations, `any`, `list<T>`, `map<K,V>`,
  struct types, and first-class function types (`fn(int) -> int`), checked
  across package boundaries.
- Native (C) backend for the typed subset — compiles with `cc`/`gcc`/`clang`
  at `-O2`, with support for `try`/`catch`/`throw`, structs containing list and
  map fields, and first-class (top-level) functions.
- Opt-in conservative mark-sweep garbage collector for native builds
  (`sandy build --gc`).

### Standard library
- Math, sorting, sets, maps, JSON, base64, hashing, random, time, OS access,
  HTTP, text, CSV, regular expressions, and assertions — written in Sandy.
- `queue` — immutable stacks (LIFO) and queues (FIFO) built on lists.

### Concurrency
- Real OS-thread tasks via `spawn`/`wait` and typed channels
  (`channel`/`send`/`recv`/`close`), following the "share memory by
  communicating" model.

### Tooling & ecosystem
- Package manager with a `sandy.toml` manifest, semantic-version constraints,
  a lockfile, and `sandy publish`.
- A registry client and a file- or HTTP-backed registry server
  (`sandy registry serve`).
- Formatter, language server, and a browser playground that runs the real
  implementation client-side.
- A VS Code extension with syntax highlighting kept in sync with the built-ins.

### Documentation
- A hands-on [Tour of Sandy](docs/tour.md), a terse
  [Language Reference](docs/reference.md), and the complete book
  [_The Sandy Programming Language_](docs/book/README.md), available as a
  downloadable PDF.
- A cross-runtime [benchmark suite](BENCHMARKS.md) comparing the interpreter,
  the VM, and native builds against CPython.

[Unreleased]: https://github.com/santhosharulsamy/Sandy
