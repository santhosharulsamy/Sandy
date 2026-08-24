# Chapter 1 — Introduction

## What Sandy is

Sandy is a general-purpose programming language. Programs are stored in files
ending in `.sy`. It looks and feels like a modern scripting language — clean
syntax, dynamic by default, batteries included — but it is built around one
idea that scripting languages usually give up on: **the typed parts of your
program can be compiled to a small, fast, standalone native executable.**

That single idea shapes everything:

- You can start writing with no ceremony — no type declarations, no build step,
  no boilerplate `main`.
- You can add type annotations gradually, and a checker verifies them *before*
  the program runs, turning a class of bugs into compile-time errors.
- When a piece of code needs to be fast, you compile it. Typed Sandy lowers to
  C and runs at C speed — many times faster than an interpreter.

## Why it exists

Every popular language is a set of tradeoffs. Python is wonderfully easy but
slow and dynamically checked. C and Rust are fast and safe but demand ceremony.
Most projects pick one language and live with its weak side.

Sandy aims at a specific, defensible lane between them:

> *As easy to write as Python, but it compiles to a fast native binary, tells
> you exactly what's wrong before you ship, and needs zero setup to run.*

It does not try to be the best at everything — no language is. It tries to be
the best **easy language that produces a fast native binary with types checked
up front.** Python cannot produce that binary; C and Rust are not this easy.

## The four goals

Sandy is designed around four goals, pursued in a deliberate order because at
their extremes they pull against each other:

| Goal | What it means |
| --- | --- |
| **Easy** | Python-level readability, minimal ceremony |
| **Fast** | Native-code speed for the typed core |
| **Safe** | Catch mistakes before the program runs |
| **Lovable** | Great errors, good tools, zero configuration |

The key design decision — **gradual types** — serves three of these at once:
types keep the language *easy* (they're optional), make it *safe* (they're
checked early), and make it *fast* (the compiler uses them to generate
unboxed native code).

## A first taste

Here is a complete Sandy program:

```sandy
fn greet(name: string) -> string {
    return "hello, " + name
}

for who in ["world", "Sandy"] {
    print(greet(who))
}
```

```
hello, world
hello, Sandy
```

Notice what is *not* there: no imports for basic output, no `main` function, no
semicolons, no manual memory management. The `: string` and `-> string`
annotations are optional — the program runs identically without them — but with
them, the checker verifies every call to `greet` before the program starts.

## How Sandy runs your code

Sandy has three ways to execute a program, all from the same source:

1. **The interpreter** (`sandy run`) — a tree-walking evaluator. Instant, no
   build step. This is where you develop.
2. **The bytecode VM** (`sandy --vm run`) — compiles to bytecode and runs it on
   a stack machine; a faster interpreter, kept behavior-identical to the first.
3. **The native compiler** (`sandy build`) — translates the typed subset to C
   and compiles it to a real executable that runs at C speed.

The interpreter and VM run *all* of Sandy, including its most dynamic features.
The native compiler runs the statically typed subset — which is most of the
language — and is where the speed comes from.

## An honest word

Because the interpreter and VM are themselves written in Python, they run Sandy
programs *slower* than CPython runs Python. They exist for instant feedback
while you develop, not for raw throughput. The speed advantage — 15 to 180
times faster than CPython on compute-bound code — comes from the **native
compiler**. Develop against the interpreter; ship the compiled binary.

The rest of this book shows you the whole language. The next chapter gets you
running code in a few minutes.
