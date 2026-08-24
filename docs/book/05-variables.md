# Chapter 5 — Variables and Assignment

## Declaring by assigning

There is no separate declaration keyword. Assigning to a name for the first time
creates it:

```sandy
count = 0
message = "ready"
```

A name can be reassigned freely, including to a value of a different type
(Sandy is dynamically typed):

```sandy
x = 10
x = "ten"        # allowed
```

## Optional type annotations

You may annotate a variable with a type at the point of first assignment:

```sandy
count: int = 0
name: string = "Sandy"
scores: map<string, int> = {}
```

The annotation is checked by `sandy check` and by the compiler: a later
assignment of an incompatible type is a type error (Chapter 14). Without an
annotation, the variable is dynamic.

## Compound assignment

The compound assignment operators update a variable in place:

```sandy
total = 0
total += 5       # total = total + 5
total -= 2       # subtract
total *= 3       # multiply
total /= 2       # divide (result is a float)
```

Compound assignment requires the variable to already exist.

Because `/=` uses division, it produces a float:

```sandy
x = 10
x /= 2
print(x)         # 5.0
```

## Scope

Sandy uses **function-level scope**. Names assigned at the top level of a file
are global to that file. Names assigned inside a function are local to that
function. A block (`{ }`) attached to `if`, `while`, or `for` does *not*
introduce a new scope — a variable first assigned inside a loop is visible after
it:

```sandy
for i in range(3) {
    last = i
}
print(last)      # 2  — `last` is visible here
```

Inside a function, assigning to a name creates or updates a *local* variable; it
does not modify a global of the same name. Functions can *read* enclosing
variables (see closures, Chapter 9), but a plain assignment inside a function
binds locally.

## Indexed and field assignment

Assignment also targets a list element, a map entry, or a struct field:

```sandy
xs = [1, 2, 3]
xs[0] = 99           # list element

m = {"a": 1}
m["b"] = 2           # map entry (creates it)

struct P { x: int }
p = P(1)
p.x = 42             # struct field
```

These do not create a new variable; they mutate the existing container or
instance.

## The value of assignment

Assignment is a statement, not an expression — it does not produce a value you
can use inline. This rules out the classic `if (x = f())` mistake; write the
assignment on its own line.

The next chapter covers the operators that combine these values into
expressions.
