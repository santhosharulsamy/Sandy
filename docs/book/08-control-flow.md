# Chapter 8 — Control Flow

Control-flow statements decide which code runs and how often. Sandy has three:
`if`, `while`, and `for`. All use brace-delimited blocks.

## if / elif / else

```sandy
n = 7
if n < 0 {
    print("negative")
} elif n == 0 {
    print("zero")
} else {
    print("positive")
}
```

The condition is any expression, tested for truthiness (Chapter 6) — it need not
be a bool. There may be any number of `elif` branches and an optional final
`else`.

**A syntax rule worth stating plainly:** `elif` and `else` must appear on the
*same line* as the preceding closing brace:

```sandy
if x { ... } else { ... }        # correct

if x { ... }
else { ... }                     # WRONG — `else` must follow the `}`
```

This is because a newline ends the `if` statement. Keep `} elif` and `} else`
together.

## while

`while` repeats its block as long as the condition is truthy:

```sandy
i = 0
while i < 5 {
    print(i)
    i += 1
}
```

```
0
1
2
3
4
```

## for

`for` iterates over a sequence: a range, a list, or a map.

### Over a range

`range` produces integers. It comes in three forms:

```sandy
for i in range(3) { print(i) }          # 0, 1, 2
for i in range(1, 4) { print(i) }       # 1, 2, 3
for i in range(0, 10, 2) { print(i) }   # 0, 2, 4, 6, 8
```

`range(n)` counts from 0 up to (not including) `n`. `range(a, b)` counts from
`a` to `b`. `range(a, b, step)` uses a stride, which may be negative:

```sandy
for i in range(3, 0, -1) { print(i) }   # 3, 2, 1
```

### Over a list

```sandy
for name in ["Ada", "Bob", "Cy"] {
    print(name)
}
```

### Over a map

Iterating a map yields its **keys**, in insertion order:

```sandy
scores = {"ada": 10, "bob": 7}
for who in scores {
    print(who + ": " + str(scores[who]))
}
```

```
ada: 10
bob: 7
```

## break and continue

`break` exits the nearest enclosing loop; `continue` skips to its next
iteration:

```sandy
total = 0
for i in range(100) {
    if i == 10 { break }
    if i % 2 == 1 { continue }
    total += i
}
print(total)     # 0 + 2 + 4 + 6 + 8 = 20
```

## Everything is a statement

Control-flow constructs are statements, not expressions — they do not produce a
value. To choose a value, assign inside the branches, or use `or` for a default
(Chapter 6). This keeps control flow explicit and readable.

The next chapter covers the unit that organizes all this logic: the function.
