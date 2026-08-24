# A Tour of Sandy

A hands-on tour of the language, from your first program to compiling a native
binary and publishing a package. Every snippet here is real and runnable — the
outputs shown are what the program actually prints.

You only need Python to follow along. From the repository root:

```bash
python -m sandy run tour.sy      # run a program
python -m sandy check tour.sy    # type-check it without running
python -m sandy                  # start an interactive REPL
```

> New to the reference material? This tour teaches by example; the full
> [language reference](reference.md) is the exhaustive companion.

---

## 1. Hello, Sandy

Put this in `hello.sy` and run `python -m sandy run hello.sy`:

```sandy
name = "Sandy"
print("hello, {name}!")
```

```
hello, Sandy!
```

Strings interpolate with `{...}`. Any expression works inside the braces — write
`{{` and `}}` for literal braces.

## 2. Values and arithmetic

Variables are declared just by assigning. Numbers are `int` or `float`, and a
few operators are worth knowing up front:

```sandy
print(2 + 3 * 4)     # 14
print(10 / 4)        # 2.5   — division is ALWAYS float
print(2 ** 10)       # 1024  — ** is power
print(-7 % 3)        # 2     — % is Python-style floor modulo
```

`/` always produces a float; use it deliberately. `and`, `or`, and `not` are
the boolean operators, and they short-circuit.

## 3. Functions

```sandy
fn greet(who) {
    return "hi, " + who
}
print(greet("world"))     # hi, world
```

Functions are first-class values — pass them around, return them, store them:

```sandy
fn twice(f, x) { return f(f(x)) }
fn inc(n) { return n + 1 }
print(twice(inc, 10))     # 12
```

## 4. Types, when you want them

Sandy is **gradually typed**: annotations are optional. Code without them is
fully dynamic and runs unchanged. Where you *do* add types, the checker verifies
them **before the program runs**.

```sandy
fn area(w: int, h: int) -> int {
    return w * h
}
```

Call it wrong and `sandy check` catches it up front — even across files:

```sandy
print(area("wide", 3))
```

```
found 1 type error before running:
  TypeError (line 2): argument 1 of area() expects int, got string
```

Function values can be typed too: `fn(int) -> int` is the type of a function
taking an `int` and returning one. Add types where they earn their keep — hot
paths, public functions, tricky data — and leave the rest dynamic.

## 5. Control flow

`if` / `elif` / `else`, `while`, and `for` over a `range` or a collection.
Note that `elif`/`else` sit on the same line as the closing brace.

```sandy
total = 0
for i in range(1, 5) {      # 1, 2, 3, 4
    total += i
}
print(total)                # 10

n = 7
if n % 2 == 0 { print("even") } else { print("odd") }   # odd
```

## 6. Lists and maps

```sandy
xs: list<int> = [3, 1, 2]
push(xs, 4)
print(xs)            # [3, 1, 2, 4]
print(len(xs))       # 4
print(xs[-1])        # 4   — negative indexing works

m: map<string, int> = {"a": 1, "b": 2}
m["c"] = 3
print(m["a"])        # 1
print(has(m, "z"))   # false
for k in m {
    print(k + "=" + str(m[k]))   # a=1 / b=2 / c=3 (insertion order)
}
```

The `list<int>` / `map<string, int>` annotations are optional; without them the
collections are dynamic.

## 7. Structs

Group related data into a named type. Fields can be typed. Structs compare by
value and are mutable through `.`:

```sandy
struct Point { x: int, y: int }

p = Point(2, 3)
p.x += 10
print(p)                       # Point(x=12, y=3)
print(p == Point(12, 3))       # true
```

## 8. Errors: try / catch / throw

A runtime error jumps to the nearest `catch`, which binds the error **message**
(a string). Raise your own with `throw`. Built-in errors are catchable too.

```sandy
fn div(a: int, b: int) -> float {
    if b == 0 { throw "divide by zero" }
    return a / b
}

try {
    print(div(10, 0))
} catch e {
    print("caught: " + e)      # caught: divide by zero
}
```

## 9. Modules and the standard library

Split code across files with `import "file" as name`, and use the bundled
standard library the same way — imported by bare name:

```sandy
import "math" as math
import "lists" as lists
import "json" as json

print(math.gcd(48, 36))                 # 12

fn sq(n) { return n * n }
print(lists.map(sq, [1, 2, 3]))         # [1, 4, 9]

print(json.to_json({"ok": true, "xs": [1, 2]}))   # {"ok":true,"xs":[1,2]}
d = json.parse(json.to_json({"n": 42}))
print(d["n"])                           # 42
```

The library ships 17 modules — `math`, `strings`, `text`, `lists`, `sort`,
`sets`, `maps`, `json`, `csv`, `regex`, `random`, `time`, `os`, `http`,
`base64`, `hash`, `assert` — all written in Sandy itself. See the
[reference](reference.md#10-standard-library) for the full list.

## 10. Concurrency

Run work in the background with `spawn`, and let tasks communicate over
**channels** — "share memory by communicating," the way Go does it. A channel
`send`/`recv` blocks to synchronize, so results come out correctly even though
the work runs concurrently.

```sandy
results = channel(5)

fn work(n) {
    send(results, n * n)
}

for n in [1, 2, 3, 4, 5] {
    spawn(work, n)
}

total = 0
i = 0
while i < 5 {
    total += recv(results)
    i += 1
}
print(total)                # 55
```

`spawn(fn, args...)` returns a task; `wait(task)` blocks for its result.
`channel()` is an unbuffered rendezvous, `channel(n)` buffers `n` values.

## 11. Compiling to a native binary

This is the payoff. Any typed program (scalars, strings, lists, maps, structs,
functions, control flow, try/catch) compiles to a small native executable:

```sandy
fn fib(n: int) -> int {
    if n < 2 { return n }
    return fib(n - 1) + fib(n - 2)
}
print(fib(30))
```

```bash
python -m sandy build fib.sy --run
```

```
built native executable: fib
832040
```

The binary runs at C speed — **15–180× faster than CPython** on compute-bound
code (see [BENCHMARKS.md](../BENCHMARKS.md)). Develop against the instant
interpreter, then `sandy build` the hot paths. Add `--gc` for a garbage
collector on long-running programs.

## 12. Packages

A project has a manifest, `sandy.toml`:

```toml
[package]
name = "myapp"
version = "0.1.0"

[dependencies]
geometry = "^1.2.0"                     # a registry version constraint
utils    = { path = "../utils" }        # a local path dependency
```

```bash
sandy add geometry ^1.2.0    # add a dependency (version, path, or git URL)
sandy install                # resolve, vendor, and lock dependencies
sandy publish                # publish this project to the registry
```

Dependencies are then imported by bare name, exactly like the standard library,
and typed dependencies are checked across the package boundary. The registry can
be a local directory or an HTTP server (`sandy registry serve`); set it with
`SANDY_REGISTRY`.

## Where to go next

- Skim the [examples](../examples) — `functions.sy`, `concurrency.sy`, `wc.sy`,
  `structs.sy`, and more.
- Read the [language reference](reference.md) for the complete grammar,
  semantics, and type system.
- Try the browser [playground](../web/playground.html) — the real
  implementation, running in your browser.
- See [BENCHMARKS.md](../BENCHMARKS.md) for the speed numbers and how to
  reproduce them.

Happy hacking. Sandy is young, but it's whole: as easy as Python, and typed code
that compiles to a fast native binary.
