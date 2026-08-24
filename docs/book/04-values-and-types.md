# Chapter 4 — Values and Types

Every value in Sandy has a type. This chapter surveys the built-in types; later
chapters cover each in depth. The `type(x)` builtin returns a value's type name
as a string, which is a good way to explore in the REPL.

## The type names

| Type | Example values | `type(x)` |
| --- | --- | --- |
| nil | `nil` | `"nil"` |
| bool | `true`, `false` | `"bool"` |
| int | `0`, `42`, `-7` | `"int"` |
| float | `3.14`, `10.0` | `"float"` |
| string | `"hi"` | `"string"` |
| list | `[1, 2, 3]` | `"list"` |
| map | `{"a": 1}` | `"map"` |
| struct instance | `Point(1, 2)` | the struct's name, e.g. `"Point"` |
| function | `fn f() {}` | `"function"` |

Concurrency values add two more: a `channel` and a `task` (Chapter 15).

## Nil

`nil` is the absence of a value. Functions that don't return anything yield
`nil`, and `recv` on a closed, drained channel returns `nil`. `nil` is *falsy*
(Chapter 6).

## Booleans

`true` and `false`. They are produced by comparisons and consumed by conditions
and the logical operators.

## Numbers: int and float

Sandy has two numeric types. Integers are whole numbers; floats have a fractional
part. The important rule to internalize early:

> **Division `/` always produces a float.** `10 / 2` is `5.0`, not `5`.

```sandy
print(type(10 + 2))    # int
print(type(10 / 2))    # float
print(type(10.0))      # float
```

Mixed arithmetic (`int` with `float`) produces a `float`. Convert explicitly
with `int(x)` and `float(x)`:

```sandy
print(int(3.9))    # 3   (truncates toward zero)
print(float(3))    # 3.0
```

Integers on the interpreter and VM have arbitrary precision. When you compile a
program natively, integers are 64-bit — a deliberate tradeoff for speed.

## Strings

A string is an immutable sequence of characters. String operations produce new
strings; they never modify the original. Strings support concatenation, indexing,
iteration, interpolation, and a set of methods — all of Chapter 7.

```sandy
s = "hello"
print(len(s))        # 5
print(s[0])          # h
print(s.upper())     # HELLO
```

## Lists

A list is an ordered, growable, mutable sequence. Elements may be of any type,
though the native compiler requires them to be homogeneous (all the same type).

```sandy
xs = [10, 20, 30]
push(xs, 40)
print(xs[1])         # 20
print(xs[-1])        # 40   (negative indexes count from the end)
```

Lists are covered in Chapter 10.

## Maps

A map associates keys with values and preserves insertion order. Keys are
typically strings or integers.

```sandy
m = {"one": 1, "two": 2}
m["three"] = 3
print(m["two"])      # 2
print(has(m, "four")) # false
```

Maps are covered in Chapter 10.

## Structs

A struct is a user-defined type: a named bundle of fields. Struct instances are
compared by value and passed by reference.

```sandy
struct Point { x: int, y: int }
p = Point(3, 4)
print(p.x)           # 3
```

Structs are covered in Chapter 11.

## Functions are values

A function is a first-class value. You can store it in a variable, pass it as an
argument, and return it from another function.

```sandy
fn square(n) { return n * n }
f = square
print(f(9))          # 81
```

Functions are covered in Chapter 9.

## Dynamic by default, typed by choice

Sandy is dynamically typed: a variable can hold any type, and can be reassigned
to a value of a different type. The optional type annotations you saw in Chapter
2 do not change how values behave at runtime — they add checks that run *before*
the program does. The type system is the subject of Chapter 14.

```sandy
x = 5
x = "now a string"   # fine — x is dynamic
print(x)             # now a string
```

The next chapter covers how names get bound to these values.
