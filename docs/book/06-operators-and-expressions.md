# Chapter 6 — Operators and Expressions

An expression computes a value. This chapter covers every operator, how they
combine, and the precedence that decides who binds first.

## Arithmetic

| Operator | Meaning | Note |
| --- | --- | --- |
| `+` | addition | also concatenates strings and lists |
| `-` | subtraction | also unary negation |
| `*` | multiplication | also repeats strings/lists |
| `/` | division | **always produces a float** |
| `%` | modulo | Python-style *floor* modulo |
| `**` | exponentiation | right-associative |

```sandy
print(2 + 3)       # 5
print(2 ** 3 ** 2) # 512   — ** is right-associative: 2 ** (3 ** 2)
print(7 / 2)       # 3.5
print(-7 % 3)      # 2     — result has the sign of the divisor
print(7 % -3)      # -2
```

Arithmetic between an `int` and a `float` yields a `float`. Division always
yields a `float`, even for evenly divisible integers (`9 / 3` is `3.0`).

There is no integer-division operator; use `floor(a / b)` when you need one.

## Comparison

`==`, `!=`, `<`, `>`, `<=`, `>=` compare two values and produce a bool. Numbers
compare numerically and strings lexicographically. Structs, lists, and maps
compare by value with `==`:

```sandy
print(3 < 5)                 # true
print("apple" < "banana")    # true
print([1, 2] == [1, 2])      # true
```

Ordering (`<`, `>`, …) is defined for numbers and strings. `==` and `!=` work on
any two values.

## Logical operators

`and`, `or`, and `not` are the boolean operators, and `and`/`or` **short-circuit**
— the right operand is not evaluated if the left already decides the result:

```sandy
print(true and false)   # false
print(false or "yes")   # yes
print(not nil)          # true
```

`and` returns its first falsy operand or the last operand; `or` returns its
first truthy operand. Combined with truthiness (below), this gives the familiar
`x or default` idiom.

## Truthiness

A value used as a condition is tested for *truthiness*. These are **falsy**:

- `nil`
- `false`
- `0` and `0.0`
- the empty string `""`
- the empty list `[]` and empty map `{}`

Everything else is truthy.

## String and list operators

`+` concatenates, and `*` repeats:

```sandy
print("ab" + "cd")     # abcd
print("ab" * 3)        # ababab
print([1] + [2, 3])    # [1, 2, 3]
```

## Indexing and calls

Postfix operators access parts of a value:

```sandy
xs[0]          # list/string index (negative counts from the end)
m["key"]       # map lookup
p.field        # struct field or module member
f(a, b)        # function call
s.upper()      # method call
```

## Precedence

From highest (binds tightest) to lowest:

1. Postfix: calls `f(...)`, indexing `[...]`, member `.`
2. Unary: `-x`, `not x`
3. `**` (right-associative)
4. `*`, `/`, `%`
5. `+`, `-`
6. Comparisons: `<`, `>`, `<=`, `>=`, `==`, `!=`
7. `and`
8. `or`

Use parentheses to group when in doubt; they always override precedence:

```sandy
print(2 + 3 * 4)     # 14
print((2 + 3) * 4)   # 20
```

The next chapter looks closely at one of the most-used types: strings.
