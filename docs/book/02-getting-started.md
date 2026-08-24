# Chapter 2 — Getting Started

## Installing

Sandy needs Python 3.11 or newer. Clone the repository and run it as a module —
there is nothing to compile or install:

```bash
git clone https://github.com/santhosharulsamy/Sandy.git
cd Sandy
python -m sandy --version
```

To build native binaries you also need a C compiler on your `PATH` — `cc`,
`gcc`, or `clang`. Almost every machine already has one.

## Your first program

Create a file `hello.sy`:

```sandy
print("Hello, Sandy!")
```

Run it:

```bash
python -m sandy run hello.sy
```

```
Hello, Sandy!
```

There is no `main` function and no boilerplate. Top-level statements run top to
bottom.

## The four commands you'll use most

```bash
python -m sandy run hello.sy       # run on the interpreter
python -m sandy check hello.sy     # type-check without running
python -m sandy build hello.sy     # compile to a native binary ./hello
python -m sandy                    # start an interactive REPL
```

In the REPL you can type expressions and see their values immediately — handy
for experimenting as you read this book.

## A whirlwind tour

The rest of this chapter is the entire language in miniature. Don't worry about
absorbing it all; each feature gets its own chapter later. Skim it to get the
shape of the language.

### Variables and printing

```sandy
name = "Ada"
age = 36
print("{name} is {age}")        # {name} is 36
```

Assign to declare. Strings interpolate with `{...}`.

### Numbers

```sandy
print(7 + 2)        # 9
print(7 / 2)        # 3.5   — division is always a float
print(7 % 2)        # 1
print(2 ** 8)       # 256
```

### Functions

```sandy
fn add(a, b) {
    return a + b
}
print(add(2, 3))    # 5
```

### Optional types

```sandy
fn area(w: int, h: int) -> int {
    return w * h
}
```

Add annotations and `sandy check` verifies them before running. Leave them off
and the code is fully dynamic.

### Control flow

```sandy
for i in range(3) {
    if i % 2 == 0 { print("{i} even") } else { print("{i} odd") }
}
```

```
0 even
1 odd
2 even
```

### Lists and maps

```sandy
xs = [1, 2, 3]
push(xs, 4)
print(xs)                    # [1, 2, 3, 4]

scores = {"ada": 10, "bob": 7}
print(scores["ada"])         # 10
```

### Structs

```sandy
struct Point { x: int, y: int }
p = Point(1, 2)
p.y += 5
print(p)                     # Point(x=1, y=7)
```

### Errors

```sandy
try {
    x = int("not a number")
} catch e {
    print("failed: " + e)    # failed: cannot convert 'not a number' to int
}
```

### Modules and the standard library

```sandy
import "math" as math
print(math.gcd(12, 18))      # 6
```

### Concurrency

```sandy
ch = channel()
fn worker() { send(ch, 42) }
spawn(worker)
print(recv(ch))              # 42
```

### Compiling to native

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

That is the whole language on one page. The chapters that follow take each piece
apart carefully, starting with the smallest — how Sandy reads your source text.
