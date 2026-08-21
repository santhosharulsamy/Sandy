# Sandy 🏖️

[![CI](https://github.com/santhosharulsamy/Sandy/actions/workflows/ci.yml/badge.svg)](https://github.com/santhosharulsamy/Sandy/actions/workflows/ci.yml)

**Sandy** is a small, friendly scripting language — designed to be *easy to
learn, easy to write, and fast enough to be useful*. If you like Python, you
already know most of Sandy. Programs live in `.sy` files.

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

📖 For the precise grammar, semantics, and type-system rules, see the
**[Language Reference](docs/reference.md)**. This README is the guided tour.

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
- functions, recursion, loops, conditionals

Compiled this way, typed code runs at native (C) speed: `fib(35)` takes about
**0.02s** as a compiled binary versus roughly **96s** on the VM, and list
operations run ~**100×** faster per element than the VM. Features outside this
core (closures, dynamic `any`, heterogeneous collections) are reported
clearly — run those with `sandy run` or `sandy --vm` instead. A C compiler
(`cc`, `gcc`, or `clang`) is required.

Native strings, lists and maps are heap-allocated and not yet garbage-
collected, which is fine for short-lived programs but not long-running ones —
a GC is on the roadmap.

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
| `math` | `pi`, `e`, `tau`, `gcd`, `factorial`, `is_prime`, `clamp`, `sign`, `mean` |
| `strings` | `reverse`, `capitalize`, `repeat`, `pad_left`, `pad_right`, `count`, `contains` |
| `lists` | `map`, `filter`, `reduce`, `reverse`, `unique`, `contains`, `index_of`, `take`, `drop`, `first`, `last` |

The library lives in [`sandy/stdlib/`](sandy/stdlib) — plain `.sy` files you
can read to learn the language. A local file of the same name takes precedence,
so you can shadow or replace any module.

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
| `push(list, x)`, `pop(list)` | Mutate a list |
| `keys(map)`, `values(map)`, `has(container, x)` | Collection helpers |
| `upper`, `lower`, `trim`, `split(s, sep?)`, `join(list, sep)` | String helpers |
| `read_file(path)`, `read_lines(path)` | Read a file (whole, or as a list of lines) |
| `write_file(path, text)`, `append_file(path, text)` | Write/append a file |

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

Contributions and ideas welcome.

## License

MIT
