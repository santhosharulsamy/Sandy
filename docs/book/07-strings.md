# Chapter 7 — Strings

Strings are one of the most-used types, so Sandy gives them first-class syntax
and a useful set of operations. A string is an **immutable** sequence of
characters: every operation returns a new string.

## Literals and escapes

String literals are enclosed in double quotes:

```sandy
"hello"
```

Inside a literal, a backslash introduces an escape:

| Escape | Meaning |
| --- | --- |
| `\n` | newline |
| `\t` | tab |
| `\r` | carriage return |
| `\"` | double quote |
| `\\` | backslash |

```sandy
print("line one\nline two")
print("she said \"hi\"")
```

## Interpolation

A pair of braces inside a string embeds an expression, converted to a string:

```sandy
name = "Ada"
count = 3
print("hello {name}, you have {count} items")
print("2 + 2 = {2 + 2}")
```

```
hello Ada, you have 3 items
2 + 2 = 4
```

Any expression works inside `{...}`. To include a **literal** brace, double it:

```sandy
print("a set is written {{ }}")   # a set is written { }
```

This doubling rule is the one thing to remember when a string needs real braces
(for example, when producing JSON by hand — though the `json` module is the
better tool).

## Concatenation and repetition

```sandy
print("foo" + "bar")     # foobar
print("=" * 10)          # ==========
```

Only strings may be concatenated with `+`. To join a number, convert it first
with `str`:

```sandy
n = 42
print("answer: " + str(n))   # answer: 42
```

## Length, indexing, and iteration

```sandy
s = "hello"
print(len(s))        # 5
print(s[0])          # h
print(s[-1])         # o
for ch in s {
    print(ch)        # h e l l o, one per line
}
```

Indexing returns a one-character string. Negative indexes count from the end.

## Comparison

Strings compare lexicographically by character code:

```sandy
print("apple" < "banana")   # true
print("Zoo" < "apple")      # true  — uppercase sorts before lowercase
```

## Methods

Strings carry a set of methods, called with `.`:

| Method | Result |
| --- | --- |
| `s.upper()` | uppercase copy |
| `s.lower()` | lowercase copy |
| `s.trim()` | copy with leading/trailing whitespace removed |
| `s.length()` | length (same as `len(s)`) |
| `s.replace(a, b)` | copy with each `a` replaced by `b` |
| `s.starts_with(p)` | whether it begins with `p` |
| `s.ends_with(p)` | whether it ends with `p` |
| `s.has(sub)` | whether it contains `sub` |
| `s.split(sep)` | list of pieces (whitespace if `sep` omitted) |

```sandy
print("  Hello  ".trim().upper())   # HELLO
print("a,b,c".split(","))           # ["a", "b", "c"]
print("readme.sy".ends_with(".sy")) # true
```

Many of these also exist as global builtins (`upper(s)`, `split(s, sep)`,
`join(list, sep)` — Chapter 18), and character-level helpers plus `ord`/`chr`
live in the `text` module (Chapter 17).

## Converting to and from strings

`str(x)` converts any value to its display string; `int(s)` and `float(s)` parse
numbers:

```sandy
print(str(3.5))      # 3.5
print(int("42") + 1) # 43
```

The next chapter turns from data to control: how programs make decisions and
repeat work.
