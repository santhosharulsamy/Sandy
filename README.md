# Sandy 🏖️

[![CI](https://github.com/santhosharulsamy/Sandy/actions/workflows/ci.yml/badge.svg)](https://github.com/santhosharulsamy/Sandy/actions/workflows/ci.yml)

**Sandy** is a small, friendly scripting language — designed to be *easy to
learn, easy to write, and fast enough to be useful*. If you like Python, you
already know most of Sandy. Programs live in `.sy` files.

*Created and maintained by **Santhosh Arulsamy**.*

▶️ **[Try Sandy live in your browser →](https://santhosharulsamy.github.io/Sandy/)** — no install, runs the real language right on the page.

```sandy
fn greet(name) {
    return "Hello, " + name + "!"
}

print(greet("Sandy"))
```

```
$ sandy hello.sy
Hello, Sandy!
```

This repository contains the reference implementation of Sandy, written in
Python: a tree-walking interpreter, a bytecode VM, a gradual type checker, and
a native (C) backend for the typed subset.

📖 New here? Take the **[Tour of Sandy](docs/tour.md)** for a hands-on
walk-through in a few minutes, read **[_The Sandy Programming Language_](docs/book/README.md)**
— the complete book, cover to cover — or consult the terse
**[Language Reference](docs/reference.md)** for exact rules.

🏖️ **Try Sandy in your browser** — the
**[live playground](https://santhosharulsamy.github.io/Sandy/)** runs the real
implementation client-side (nothing to install). The same page lives in the repo
at [`web/playground.html`](web/playground.html) if you want to host your own.

---

## Install & run — from zero

New to all this? Here's the whole path, start to finish. You only need **Python
3.8 or newer** — Sandy has no other dependencies.

**1. Install Python** (skip if you already have it).
Download it from [python.org/downloads](https://www.python.org/downloads/) and
run the installer. On Windows, tick **"Add Python to PATH"** during setup. To
check it worked, open a terminal and run:

```bash
python --version
```

**2. Get Sandy.** Download this repository (green **Code** button →
**Download ZIP**) and unzip it, or clone it:

```bash
git clone https://github.com/santhosharulsamy/Sandy.git
cd Sandy
```

**3. Run your first program.**

```bash
python -m sandy examples/hello.sy
```

You should see it print a greeting. That's it — you're running Sandy. 🎉

**4. Write your own.** Create a file called `hi.sy` with:

```sandy
fn main() {
    print("Sandy is running!")
}

main()
```

…and run it:

```bash
python -m sandy hi.sy
```

**Want the `sandy` command everywhere?** Install it once, then drop the
`python -m` prefix:

```bash
pip install -e .
sandy hi.sy
```

For everything else — the bytecode VM, native compilation, the formatter, and
the REPL — see the command reference just below.

---

## Quick start

No installation needed — you just need Python 3.8+.

```bash
# Run a program
python -m sandy examples/hello.sy
# ...or with the launcher
./sandy.py examples/hello.sy

# ...or install it and use the `sandy` command
pip install -e .
sandy examples/hello.sy

# Run on the experimental bytecode VM (faster engine)
python -m sandy --vm examples/fib.sy

# Compile a typed program to a native executable (needs a C compiler)
python -m sandy build examples/native.sy --run

# Format a program in canonical style (comments preserved)
python -m sandy fmt examples/hello.sy

# Start the language server for your editor (LSP over stdio)
python -m sandy lsp

# Start the interactive REPL
python -m sandy

# Show the version / help
python -m sandy --version
python -m sandy --help
```

Optionally install it so `sandy` is on your PATH:

```bash
pip install -e .
sandy examples/fizzbuzz.sy
```

Run the tests:

```bash
python -m unittest discover -s tests
```

Benchmark the two engines (tree-walker vs bytecode VM):

```bash
python bench/bench.py
```

---

## Language tour

### Comments and printing

```sandy
# This is a comment.
print("Hello")          # print writes a line to the screen
print(1, 2, 3)          # prints: 1 2 3
```

### Variables

No keyword needed — just assign. Reassigning updates the nearest variable
that already exists.

```sandy
x = 10
name = "Sandy"
pi = 3.14159
ready = true
nothing = nil
```

Compound assignment works too:

```sandy
count = 0
count += 1
count -= 1
count *= 2
count /= 4
```

### Types

| Type    | Example                       |
| ------- | ----------------------------- |
| int     | `42`, `-7`                    |
| float   | `3.14`, `2.0`                 |
| string  | `"hi"`, `'also hi'`           |
| bool    | `true`, `false`               |
| nil     | `nil`                         |
| list    | `[1, 2, 3]`                   |
| map     | `{ "a": 1, "b": 2 }`          |

### Operators

```sandy
# Arithmetic
2 + 3        # 5
10 - 4       # 6
6 * 7        # 42
10 / 4       # 2.5   (division always gives a float, like Python 3)
17 % 5       # 2
2 ** 10      # 1024  (** is right-associative)

# Comparison
a == b   a != b   a < b   a > b   a <= b   a >= b

# Logical (words — easy to read, and they short-circuit)
true and false      # false
true or false       # true
not true            # false

# Strings and lists
"foo" + "bar"       # "foobar"
"ab" * 3            # "ababab"
[1, 2] + [3]        # [1, 2, 3]
```

### Conditionals

```sandy
if score > 90 {
    print("A")
} elif score > 80 {
    print("B")
} else {
    print("C")
}
```

### Loops

```sandy
# while
i = 0
while i < 5 {
    print(i)
    i += 1
}

# for-in over a range
for n in range(1, 4) {
    print(n)          # 1, 2, 3
}

# for-in over a list, string, or map keys
for item in [10, 20, 30] { print(item) }
for ch in "hey"        { print(ch) }
for key in { "a": 1 }  { print(key) }

# break / continue
for n in range(100) {
    if n == 5 { break }
    if n % 2 == 0 { continue }
    print(n)          # 1, 3
}
```

### Error handling

A runtime error inside a `try` block jumps to its `catch`, which binds the
error **message** (a string) to a name. Raise your own errors with `throw`.
Errors propagate up through function calls until a `try` catches them.

```sandy
try {
    amount = int("oops")      # built-in errors are catchable
} catch e {
    print("failed: " + e)     # failed: cannot convert 'oops' to int
}

fn withdraw(balance, amount) {
    if amount > balance {
        throw "insufficient funds"
    }
    return balance - amount
}

try {
    print(withdraw(100, 250))
} catch e {
    print("declined: " + e)   # declined: insufficient funds
}
```

### Concurrency

Run work in the background with `spawn`, and let tasks talk to each other over
**channels** — "share memory by communicating," the way Go does it. A channel
`send`/`recv` blocks to synchronize, so results come out in order even though
the work runs concurrently.

```sandy
fn work(n) { return n * n }

t = spawn(work, 12)          # run in the background
print(wait(t))               # 144 — block for the result

# a producer streams values, then closes the channel
ch = channel()
fn produce() {
    for k in range(1, 4) { send(ch, k) }
    close(ch)
}
spawn(produce)

v = recv(ch)
while v != nil {             # recv returns nil once closed and drained
    print(v)                 # 1, 2, 3
    v = recv(ch)
}
```

`channel(n)` makes a buffered channel that holds `n` values before a sender
blocks; `channel()` is an unbuffered rendezvous. Concurrency runs on the
default engine.

### Structs

Group related data into a named type. Construct with the struct name, access
and mutate fields with `.`, and compare by value. `type(x)` returns the
struct's name.

```sandy
struct Point { x, y }        # fields can be typed too: { x: int, y: int }

p = Point(3, 4)
print(p)                     # Point(x=3, y=4)
print(p.x)                   # 3
p.y += 10                    # fields are mutable
print(type(p))               # Point
print(Point(1, 2) == Point(1, 2))   # true — equality is by value
```

### Modules

Split a program across files. `import` runs another `.sy` file once and binds
its top-level definitions (functions, structs, variables) as a namespaced
module. Paths resolve **relative to the importing file**, so a program works
from any working directory.

```sandy
# geometry.sy
pi = 3.14159
struct Circle { radius }
fn area(c) { return pi * c.radius * c.radius }
```

```sandy
# app.sy
import "geometry.sy" as geo      # or: import "geometry"  (alias -> geometry)

c = geo.Circle(5)
print(geo.area(c))               # 78.53975
```

Modules are cached (imported once, even via diamonds) and circular imports
are detected with a clear error. See [`examples/modules/`](examples/modules).

Imports are **type-checked across the boundary**: the checker reads the
module's exported function and struct signatures, so `math.gcd(1)` (wrong
arity), `geo.Circle("x")` (wrong field type), and `m.nope` (unknown member)
are all caught before the program runs.

### Gradual types (optional)

Sandy is dynamic by default, but you can *optionally* annotate functions and
variables. Annotations are **checked before the program runs**, so a whole
class of bugs is caught up front — while unannotated code stays fully
dynamic. This is *gradual* typing: add types where they help, skip them where
they don't.

```sandy
fn add(a: int, b: int) -> int {
    return a + b
}

score: int = 0
score += add(10, 5)      # fine

# These would be caught BEFORE running:
#   score = "oops"       -> cannot assign string to 'score' declared as int
#   add(1)               -> add() expects 2 argument(s), got 1
#   add(1, "x")          -> argument 2 of add() expects int, got string
```

Type names: `int`, `float`, `string`, `bool`, `nil`, `list`, `map`, any
**struct name**, and `any` (opts out of checking). Anything unannotated is
`any`. Lists and maps can be parameterized — `list<int>`, `map<string, int>` —
so indexing knows the element type (e.g. `xs[0] + 1` is flagged when `xs` is a
`list<string>`).

Struct types are checked too. Given `struct Point { x: int, y: int }`, the
checker knows each field's type:

```sandy
fn move(p: Point, dx: int) -> Point { return Point(p.x + dx, p.y) }

# Caught before running:
#   Point("a", 2)        -> field 'x' of Point expects int, got string
#   p: Point = Point(1, 2)
#   p.z                  -> Point has no field 'z'
#   p.x = "no"           -> cannot assign string to field 'x' of Point
```

```bash
sandy check program.sy      # type-check without running
sandy --no-check program.sy # run without the type checker
```

Types also feed the compiler: on the `--vm` engine, code the compiler can
prove is numeric is compiled to specialized numeric opcodes, so typed numeric
functions run faster than untyped ones (see `bench/bench.py`).

### Native compilation

Typed programs can be compiled to a **native executable** via C:

```bash
sandy build program.sy          # produces ./program
sandy build program.sy --run    # build and run it
sandy build program.sy --emit-c # also keep the generated C
sandy build program.sy --gc     # manage memory with a garbage collector
```

The native backend handles Sandy's **typed core**:

- `int`, `float`, `bool`, and `string` (concatenation, repetition, ordering,
  `len`, `str`, and `.upper()/.lower()/.trim()/.length()`)
- **typed lists** `list<int>` / `list<float>` / `list<string>` — literals,
  indexing, `push`, index-assignment, `for`-iteration, printing — compiled to
  unboxed growable C arrays (no boxing, no runtime type dispatch)
- **typed maps** `map<K,V>` (`K` int/string) — literals, get, set, `has`,
  `len`, `keys`, `values`, `for`-iteration, and printing — compiled to an
  unboxed open-addressing hash table (insertion order preserved)
- **structs** with typed fields (scalars, strings, structs, and `list<T>` /
  `map<K,V>` fields) — construction, field access/mutation, deep value
  equality, printing, and nesting; heap-allocated so they keep Sandy's
  reference semantics
- **try / catch / throw** — a setjmp/longjmp handler stack; `throw` unwinds
  across call frames, and built-in runtime errors (division by zero,
  out-of-range index, missing map key) are catchable, exactly as in the
  interpreter
- **first-class functions** — a top-level function typed as `fn(int) -> int`
  can be passed as an argument, stored in a variable, returned, and called
  through; it compiles to a plain C function pointer (no boxing)
- functions, recursion, loops, conditionals

Compiled this way, typed code runs at native (C) speed — **15–180× faster than
CPython** on compute-bound programs (see [BENCHMARKS.md](BENCHMARKS.md); run
`python bench/compare.py` to reproduce). `fib(35)` takes about **0.02s** as a
compiled binary versus roughly **96s** on the VM, and list operations run
~**100×** faster per element than the VM. Features outside this
core (capturing closures, dynamic `any`, heterogeneous collections) are
reported clearly — run those with `sandy run` or `sandy --vm` instead. A C
compiler (`cc`, `gcc`, or `clang`) is required.

Native heap values (strings, lists, maps, structs) leak by default — fine for
short-lived tools, where leak-and-exit is the fastest thing to do. For
long-running programs, `sandy build --gc` routes every allocation through a
conservative mark-sweep garbage collector, so memory stays bounded (an
allocation-heavy loop that climbs to hundreds of MB without it stays flat at
~10 MB); output and iteration order are identical either way.

### Functions

Functions are first-class values. They can be passed around, returned, and
they close over the variables in scope where they were defined.

```sandy
fn add(a, b) {
    return a + b
}

fn make_counter() {
    count = 0
    fn tick() {
        count += 1
        return count
    }
    return tick               # returns a closure
}

next = make_counter()
print(next())   # 1
print(next())   # 2
```

Functions can also be **typed**, so the checker verifies calls made through
them and they compile natively:

```sandy
fn apply(f: fn(int) -> int, x: int) -> int {
    return f(x)
}
fn twice(n: int) -> int { return n * 2 }

print(apply(twice, 21))   # 42
```

### Lists

```sandy
nums = [3, 1, 2]
print(nums[0])          # 3
print(nums[-1])         # 2   (negative indexing counts from the end)
nums[0] = 99            # index assignment

push(nums, 4)           # append (also: nums.push(4))
last = pop(nums)        # remove & return the last item
print(len(nums))
print(nums.sort())      # [1, 2, 99]
print(nums.reverse())
```

### Maps

```sandy
person = { "name": "Ada", "age": 36 }
print(person["name"])       # Ada
person["age"] = 37          # update / insert

print(keys(person))         # ["name", "age"]   (also: person.keys())
print(values(person))
print(person.has("name"))   # true
```

### Strings

```sandy
s = "Hello, World"
print(s.upper())              # HELLO, WORLD
print(s.lower())
print(s.split(", "))          # ["Hello", "World"]
print(s.starts_with("Hell"))  # true
print(s.replace("o", "0"))    # Hell0, W0rld
print(len(s))                 # 12
```

### String interpolation

Drop any expression into a string with `{ }` — it's evaluated and inserted
using the same formatting `print` uses:

```sandy
name = "Sandy"
age = 3

print("Hi, {name}!")                    # Hi, Sandy!
print("{name} is {age} years old.")     # Sandy is 3 years old.
print("Next year: {age + 1}")           # Next year: 4
print("Shouting: {name.upper()}")       # Shouting: SANDY

scores = { "math": 90 }
print("Math: {scores["math"]}")         # Math: 90 (nested quotes are fine)

# Want a literal brace? Double it:
print("{{not interpolated}}")           # {not interpolated}
```

Any expression works inside `{ }` — arithmetic, function calls, indexing,
method calls, even nested strings.

### Standard library

Sandy ships with a small standard library, **written in Sandy itself** and
imported by bare name from anywhere:

```sandy
import "math" as math
import "lists" as lists

print(math.gcd(48, 36))              # 12
print(math.is_prime(97))             # true

fn square(n) { return n * n }
print(lists.map(square, [1, 2, 3]))  # [1, 4, 9]  — pass your own functions in
```

| Module | Highlights |
| --- | --- |
| `math` | `pi`, `e`, `tau`, `gcd`, `lcm`, `factorial`, `is_prime`, `clamp`, `sign`, `mean`, `median`, `variance`, `stddev`, `hypot`, `deg2rad`, `rad2deg`, `log_base` |
| `maps` | `get`, `items`, `from_pairs`, `merge`, `invert`, `map_values`, `pick` |
| `strings` | `reverse`, `capitalize`, `repeat`, `pad_left`, `pad_right`, `count`, `contains` |
| `lists` | `map`, `filter`, `reduce`, `reverse`, `unique`, `contains`, `index_of`, `take`, `drop`, `first`, `last` |
| `sort` | `sort`, `sort_by`, `sort_desc`, `is_sorted` (stable, non-destructive) |
| `sets` | `union`, `intersection`, `difference`, `symmetric_difference`, `is_subset`, `is_disjoint`, `unique` |
| `json` | `to_json` (encode) and `parse` (decode) between Sandy values and JSON text |
| `random` | seedable PRNG: `seed`, `next`, `randint`, `boolean`, `choice`, `shuffle`, `sample` |
| `time` | `epoch`, `monotonic`, `since`, `sleep_ms`, `format` (human-readable durations) |
| `os` | path helpers: `join`, `basename`, `dirname`, `extension`, `stem` |
| `http` | `get_json`, `post_json`, `status`, `body`, `ok` (JSON-aware HTTP) |
| `text` | char predicates (`is_digit`/`is_alpha`/…), `chars`, `words`, `lines`, `title`, `count` |
| `csv` | `parse`, `parse_line`, `format`, `format_row` (RFC 4180-style quoting) |
| `regex` | `test`, `find`, `find_all`, `groups`, `replace`, `split` |
| `base64` | `encode`, `decode` |
| `hash` | `djb2` (fast non-crypto string hash; `sha256`/`md5` are builtins) |
| `assert` | `eq`, `neq`, `is_true`, `is_false` — for writing tests in Sandy itself |

The library lives in [`sandy/stdlib/`](sandy/stdlib) — plain `.sy` files you
can read to learn the language. A local file of the same name takes precedence,
so you can shadow or replace any module.

### Packages

Beyond the standard library, a project can depend on other people's Sandy code.
A project has a manifest, `sandy.toml`:

```toml
[package]
name = "myapp"
version = "0.1.0"

[dependencies]
geometry = "^1.2.0"                                  # a registry version constraint
utils    = { path = "../utils" }                     # a local path dependency
webby    = { git = "https://example.com/webby.git" } # a git dependency
```

Then:

```bash
sandy add geometry ^1.2.0        # add a dependency (version, path, or git URL)
sandy install                    # resolve dependencies, write sandy.lock
sandy publish                    # publish this project to the registry
```

Version constraints follow semver: `1.2.3` (exact), `^1.2.0` (compatible —
same major), `~1.2.0` (same major.minor), `>=1.0.0,<2.0.0` (a range), or `*`
(any). `sandy install` picks the highest published version that satisfies the
constraint and records it in `sandy.lock`. Published versions are immutable.

The registry can be a **local directory** or an **HTTP server**. Point clients
at it with `SANDY_REGISTRY` (default `~/.sandy/registry`):

```bash
# run the bundled registry server (stores packages under --dir)
sandy registry serve --port 8377 --dir ./registry

# elsewhere, publish/consume against it
export SANDY_REGISTRY=http://localhost:8377
sandy publish
sandy install
```

The server (`sandy/registry_server.py`) is a small, dependency-free reference
implementation — a starting point for a hosted, shared package registry.

Once resolved, a dependency is imported by bare name, exactly like the standard
library — and if it ships type annotations, calls into it are **checked across
the package boundary** before your program runs:

```sandy
import "geometry" as geo
import "geometry/shapes" as shapes   # a submodule of the package
print(geo.area(3, 4))
```

Resolution order is: a local file, then a declared dependency, then the
standard library. `sandy.lock` records exactly what was resolved so builds are
reproducible; registry and git dependencies are vendored into `sandy_modules/`.

---

## Built-in functions

| Function | Purpose |
| --- | --- |
| `print(...)` | Print values separated by spaces, followed by a newline |
| `input(prompt?)` | Read a line of text from the user |
| `len(x)` | Length of a string, list, or map |
| `type(x)` | Type name as a string (`"int"`, `"list"`, ...) |
| `str(x)` `int(x)` `float(x)` `bool(x)` | Type conversions |
| `range(n)` / `range(a, b)` / `range(a, b, step)` | List of integers |
| `abs`, `min`, `max`, `sum`, `round`, `pow` | Numeric helpers |
| `sqrt`, `floor`, `ceil` | Math helpers |
| `ord(char)`, `chr(code)` | Character ↔ Unicode code point |
| `sin`, `cos`, `tan`, `exp`, `log(x, base?)`, `log10` | Trig, exponential, logarithms |
| `sha256(s)`, `md5(s)` | Hex cryptographic digests of UTF-8 text |
| `base64_encode(s)`, `base64_decode(s)` | Base64 encoding |
| `push(list, x)`, `pop(list)` | Mutate a list |
| `keys(map)`, `values(map)`, `has(container, x)` | Collection helpers |
| `upper`, `lower`, `trim`, `split(s, sep?)`, `join(list, sep)` | String helpers |
| `read_file(path)`, `read_lines(path)` | Read a file (whole, or as a list of lines) |
| `write_file(path, text)`, `append_file(path, text)` | Write/append a file |
| `now()`, `clock()` | Wall-clock epoch seconds; monotonic seconds for timing |
| `sleep(seconds)` | Pause execution |
| `env(name, default?)` | Read an environment variable |
| `exit(code?)` | End the program with an exit code |
| `args()` | The program's command-line arguments (a list of strings) |
| `cwd()`, `exists(p)`, `is_file(p)`, `is_dir(p)` | Query the filesystem |
| `list_dir(p)`, `make_dir(p)`, `remove_file(p)` | List / create / delete |
| `http_get(url)`, `http_post(url, body)` | HTTP requests → `{status, ok, body}` |
| `spawn(fn, args...)`, `wait(task)` | Run a function concurrently; await its result |
| `channel(capacity?)`, `send(ch, v)`, `recv(ch)`, `close(ch)` | Communicate between tasks |

Many of these also work as **methods**: `text.upper()`, `list.push(x)`,
`map.keys()`, `list.sort()`, `list.reverse()`, `str.replace(a, b)`, and more.

---

## Examples

The [`examples/`](examples/) directory has runnable programs:

| File | Shows off |
| --- | --- |
| `hello.sy` | The basics — printing and variables |
| `greet.sy` | String interpolation |
| `typed.sy` | Gradual type annotations |
| `fizzbuzz.sy` | Loops and conditionals |
| `fib.sy` | Recursion and iteration |
| `data.sy` | Lists, maps, methods, higher-order functions |
| `closures.sy` | Closures and functions as values |

```bash
python -m sandy examples/data.sy
```

---

## Editor support

Sandy ships a language server (`sandy lsp`, LSP over stdio) that reuses the
same lexer, parser, type checker, and formatter. It provides:

- **diagnostics** — syntax and type errors as you type
- **hover** — signatures for functions, structs, parameters, and builtins
- **go-to-definition** — jump to where a name is defined
- **formatting** — the same canonical output as `sandy fmt`
- **completion** — keywords, builtins, and the file's own definitions
- **outline** — functions, structs, and top-level variables

Point any LSP-capable editor at the command `sandy lsp` for `.sy` files. For
example, a generic client config just needs `command: "sandy", args: ["lsp"]`.

For **syntax highlighting**, there's a VS Code extension (and a portable
TextMate grammar) in [`editors/vscode/`](editors/vscode) — keywords, strings
with interpolation, types, builtins, and more.

---

## How it works

The interpreter is a classic three-stage pipeline:

```
source (.sy)  ──▶  Lexer  ──▶  tokens  ──▶  Parser  ──▶  AST  ──▶  Interpreter  ──▶  result
```

| Module | Responsibility |
| --- | --- |
| `sandy/lexer.py` | Turns source text into tokens (handles comments, strings, smart line-continuation) |
| `sandy/tokens.py` | Token types and keywords |
| `sandy/parser.py` | Recursive-descent parser with precedence climbing → AST |
| `sandy/nodes.py` | AST node classes |
| `sandy/interpreter.py` | Tree-walking evaluator, scopes, closures, control flow |
| `sandy/values.py` | Runtime values and how they're displayed |
| `sandy/builtins.py` | Built-in functions and type methods |
| `sandy/bytecode.py` | Bytecode instruction set + code objects |
| `sandy/compiler.py` | Compiles the AST to bytecode |
| `sandy/vm.py` | Stack-based bytecode VM (the faster `--vm` engine) |
| `sandy/typecheck.py` | Gradual static type checker |
| `sandy/cbackend.py` | Native backend: transpiles the typed core to C |
| `sandy/typecheck.py` | Gradual static type checker (runs before execution) |
| `sandy/runtime.py` | Glue: run a string or a file, report errors nicely |
| `sandy/repl.py` | The interactive prompt |
| `sandy/cli.py` | Command-line entry point |

Errors carry line numbers and print friendly diagnostics:

```
$ sandy broken.sy

broken.sy: RuntimeError (line 3): undefined variable 'total'
  3 | print(total)
```

---

## Design notes

- **Familiar first.** Sandy borrows Python's feel (dynamic typing, clean
  syntax, `and`/`or`/`not`, `range`, truthiness) so it's instantly readable.
- **Braces over indentation.** Blocks use `{ }`, statements end at newlines.
  This keeps the parser simple and copy-paste friendly, while newlines inside
  brackets and after operators are treated as continuations so multi-line
  lists, maps and expressions just work.
- **Small core, batteries included.** A compact set of builtins covers the
  common cases; everything else is an easy addition in `builtins.py`.

## Roadmap

Sandy 0.1 is a complete, working interpreter — the foundation. The aim from
here is bold: to make Sandy the best language *in its lane* — as easy as
Python, but compiled to fast native code, safe where it counts, and a joy to
use.

That's a staged plan, not a slogan. See **[ROADMAP.md](ROADMAP.md)** for the
full four-lane plan (Fast ⚡ / Easy 🎈 / Safe 🛡️ / Lovable 💛) and milestones.
Next up: a bytecode compiler + VM — the first real speed jump.

## Contributing

Contributions of all sizes are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
to get started, and [AUTHORS.md](AUTHORS.md) for credits.

## Author

Created and maintained by **Santhosh Arulsamy**
([@santhosharulsamy](https://github.com/santhosharulsamy)).

## License

MIT — Copyright © 2026 Santhosh Arulsamy. See [LICENSE](LICENSE).
