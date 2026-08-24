# Chapter 12 — Error Handling

When something goes wrong at runtime — a division by zero, a missing map key, or
a condition your own code decides is invalid — Sandy raises an *error*. An error
unwinds the call stack until a `try` block catches it, or, if none does, stops
the program with a message.

## try / catch

Wrap code that might fail in `try`, and handle failure in `catch`:

```sandy
try {
    x = int("not a number")
    print(x)
} catch e {
    print("failed: " + e)
}
```

```
failed: cannot convert 'not a number' to int
```

The name after `catch` is bound to the error **message**, which is always a
string. That is the whole value of an error in Sandy — a human-readable message
— which keeps error handling simple.

## throw

Raise your own error with `throw`. The thrown value is converted to a string and
becomes the caught message:

```sandy
fn withdraw(balance, amount) {
    if amount > balance {
        throw "insufficient funds"
    }
    return balance - amount
}

try {
    print(withdraw(100, 250))
} catch e {
    print("declined: " + e)      # declined: insufficient funds
}
```

You can throw any value; it is stringified. In practice, throw a descriptive
string.

## Built-in errors are catchable

Errors raised by the language and its builtins are ordinary catchable errors —
there is no separate category. Division by zero, an out-of-range index, a
missing map key, and a failed conversion can all be caught:

```sandy
fn safe_get(xs, i) {
    try {
        return xs[i]
    } catch e {
        return nil
    }
}
print(safe_get([1, 2, 3], 10))   # nil
```

The messages match what the language reports — for example
`"index 10 out of range (length 3)"` and `"division by zero"`.

## Propagation

An error propagates outward through function calls until it meets a `try`. This
lets you handle failures far from where they occur:

```sandy
fn parse_row(line) {
    return int(line)      # may throw
}

fn total(lines) {
    sum = 0
    for line in lines {
        sum += parse_row(line)
    }
    return sum
}

try {
    print(total(["1", "2", "oops", "4"]))
} catch e {
    print("bad data: " + e)      # bad data: cannot convert 'oops' to int
}
```

`parse_row` doesn't handle the error; `total` doesn't either; the top-level
`try` does.

## What is *not* caught

`try`/`catch` catches runtime errors. It does not catch control flow — a
`return`, `break`, or `continue` inside a `try` body does the ordinary thing
(returns, breaks, continues); it is not intercepted by the `catch`.

## In compiled programs

`try`/`catch`/`throw` compiles natively (Chapter 16). The compiled program uses
the same semantics — the caught value is the message string, and built-in errors
are catchable — so error-handling code behaves identically whether interpreted
or compiled.

The next chapter covers organizing code across files and sharing it as packages.
