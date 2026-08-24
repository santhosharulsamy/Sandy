# Chapter 9 — Functions

Functions are the primary unit of organization in Sandy. They are also
first-class values: you can store them, pass them, and return them.

## Defining and calling

A function is introduced with `fn`, a name, a parenthesized parameter list, and a
brace-delimited body:

```sandy
fn add(a, b) {
    return a + b
}

print(add(2, 3))     # 5
```

`return` yields a value and ends the function. A function that falls off the end,
or uses a bare `return`, yields `nil`.

## Parameters and return types

Parameters and the return may be annotated (Chapter 14). The annotations are
optional and are checked before the program runs:

```sandy
fn area(w: int, h: int) -> int {
    return w * h
}
```

Arguments are passed by value for scalars and strings, and by reference for
lists, maps, and structs — that is, the callee receives the same container the
caller has, so mutations are visible to both (see Chapter 11 for the details).

## Recursion

A function may call itself. Names are resolved so that a function can refer to
itself and to functions defined later in the same file:

```sandy
fn fib(n) {
    if n < 2 { return n }
    return fib(n - 1) + fib(n - 2)
}
print(fib(10))       # 55
```

## First-class functions

A function is a value. Assign it, pass it, return it:

```sandy
fn square(n) { return n * n }

apply = square
print(apply(6))              # 36

fn twice(f, x) { return f(f(x)) }
fn inc(n) { return n + 1 }
print(twice(inc, 10))        # 12
```

This is what makes higher-order library functions like `lists.map`,
`lists.filter`, and `lists.reduce` possible (Chapter 17).

## Function types

When you want to *annotate* a function-valued parameter, the type is written
`fn(ParamTypes) -> ReturnType`:

```sandy
fn apply(f: fn(int) -> int, x: int) -> int {
    return f(x)
}
fn double(n: int) -> int { return n * 2 }

print(apply(double, 21))     # 42
```

A bare `fn` means "any function" and stays fully dynamic. With a precise
signature, the checker verifies calls made through the value (arity and argument
types). Typed top-level functions used as values also compile natively (Chapter
16).

## Closures

A function defined inside another function *closes over* the variables in scope
where it was defined — it can read and update them even after the outer function
has returned. This makes stateful helpers and factories easy:

```sandy
fn make_counter() {
    count = 0
    fn tick() {
        count += 1
        return count
    }
    return tick
}

next = make_counter()
print(next())    # 1
print(next())    # 2
print(next())    # 3
```

Each call to `make_counter` creates a fresh `count`, so two counters are
independent.

Closures run on the interpreter and VM. The native compiler supports first-class
*top-level* functions but not capturing closures (Chapter 16); the checker and
interpreter support them everywhere.

## Order of definitions

Top-level functions may be *called* before their definition appears in the file
(calls are resolved after the whole file is read). But using a function as a
*value* — assigning it, passing it — requires its definition to have run first,
because that is when the function value comes into existence. In practice, define
before you pass.

The next chapter covers the two workhorse container types: lists and maps.
