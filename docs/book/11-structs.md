# Chapter 11 — Structs

A struct is a user-defined type: a named group of fields. Structs give a program
its vocabulary — `Point`, `Account`, `Request` — instead of loose maps and
tuples.

## Defining a struct

```sandy
struct Point { x: int, y: int }
```

Fields may be typed (as above) or untyped:

```sandy
struct Tag { name, weight }     # untyped fields — dynamic
```

Typed fields are checked and are required for native compilation. Field types may
be scalars, strings, other structs, or (natively) typed lists and maps.

## Creating an instance

Construct with the struct's name, passing one argument per field in order:

```sandy
p = Point(3, 4)
print(p.x)       # 3
print(p.y)       # 4
```

Printing a struct shows its name and fields:

```sandy
print(p)         # Point(x=3, y=4)
```

## Reading and mutating fields

Fields are read and assigned with `.`:

```sandy
p.x = 10
p.y += 5
print(p)         # Point(x=10, y=9)
```

## Value equality

Two struct instances are equal when they have the same type and equal fields,
compared deeply:

```sandy
print(Point(1, 2) == Point(1, 2))   # true
print(Point(1, 2) == Point(1, 9))   # false
```

## Reference semantics

Struct instances are **reference values**. Assigning one to another name, or
passing one to a function, shares the *same* instance — mutations are visible
everywhere it is referenced:

```sandy
struct Box { n: int }

a = Box(1)
b = a            # b refers to the same Box as a
b.n = 42
print(a.n)       # 42  — a and b are the same instance

fn bump(box) { box.n += 100 }
bump(a)
print(a.n)       # 142 — the function mutated the shared instance
```

This is the same model Python uses for objects: names are references, and
mutation is shared. If you need an independent copy, construct a new instance.

By contrast, scalars (`int`, `float`, `bool`) and strings are passed by value —
a function cannot change a caller's number.

## Nesting

A struct field may be another struct, and structs nest to any depth:

```sandy
struct Point { x: int, y: int }
struct Line { a: Point, b: Point }

seg = Line(Point(0, 0), Point(3, 4))
print(seg.b.x)       # 3
print(seg)           # Line(a=Point(x=0, y=0), b=Point(x=3, y=4))
```

## Structs as types

A struct name is a valid type annotation. The checker then verifies construction
(arity and field types), field access (an unknown field is an error), and
assignment — all before the program runs:

```sandy
fn distance_sq(p: Point) -> int {
    return p.x * p.x + p.y * p.y
}
```

Structs — including those with list and map fields — compile natively (Chapter
16), where they become heap-allocated C structs that preserve exactly this
reference semantics.

The next chapter covers what happens when things go wrong: error handling.
