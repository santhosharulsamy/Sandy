# Chapter 14 — The Type System

Sandy's type system is **gradual**: annotations are optional, and code without
them is fully dynamic and runs unchanged. Where you add annotations, a checker
verifies them *before* the program runs. This chapter explains what the checker
does, what it deliberately does not do, and how to run it.

## The core promise

> Unannotated code produces **zero** type errors and behaves exactly as if the
> checker did not exist. Annotations only ever *add* checks; they never change
> runtime behavior.

This is what "gradual" means. You can write an entire program with no types, add
a few where a bug would be costly, and never be forced to annotate the rest.

## `any`

Every unannotated value has the type `any`. `any` is compatible with every type,
in both directions — you can pass an `any` where an `int` is expected, and an
`int` where `any` is expected. This is the mechanism that keeps dynamic code
error-free:

```sandy
fn double(x: int) -> int { return x * 2 }
fn get(m, k) { return m[k] }        # untyped -> returns any

print(double(get(m, "n")))          # any flows into int: no error
```

## Where annotations go

```sandy
fn add(a: int, b: int) -> int { return a + b }   # parameters and return
score: int = 0                                     # variables
struct Point { x: int, y: int }                    # struct fields
apply: fn(int) -> int = double                     # function-typed variables
```

## What is checked

The checker reports an error only when two **known, non-`any`** types definitely
conflict. Specifically it verifies:

- **Assignment** to an annotated variable, and later reassignment, match the
  declared type.
- **Return** values match a function's declared return type.
- **Call arity and argument types** against annotated parameters — including
  calls made through a value of function type `fn(...) -> R`.
- **Operators** — e.g. `int + string` is rejected when both sides are known.
- **List and map element types** via `list<T>` and `map<K, V>`; indexing a
  `list<string>` yields a `string`, so `xs[0] + 1` is caught.
- **Structs** — construction (arity and field types), field access (an unknown
  field is an error), and field assignment.
- **Imported modules** — calls to a module's functions and its struct
  construction are checked across the file (and package) boundary.
- **Unknown type names** in annotations are reported.

```sandy
fn area(w: int, h: int) -> int { return w * h }
print(area("wide", 3))
```

```
TypeError (line 2): argument 1 of area() expects int, got string
```

## Parameterized types

Lists and maps take type parameters:

```sandy
nums: list<int> = [1, 2, 3]
table: map<string, int> = {"a": 1}
```

An unparameterized `list` or `map` is treated as fully gradual (element type
`any`). Element and value types are checked when known, and `any` on either side
always passes.

## Function types

`fn(T1, T2) -> R` is the type of a function taking `T1, T2` and returning `R`;
omit `-> R` for a function that returns nothing. A bare `fn` means "any
function" and stays gradual. Calls made through a typed function value are
checked for arity and argument types.

## Int widens to float

An `int` is accepted where a `float` is expected (it widens automatically); the
reverse is not allowed without an explicit `int(x)`:

```sandy
x: float = 3        # fine — int widens to float
```

## Running the checker

The checker runs automatically before `sandy run` and `sandy build`. To check
without running:

```bash
sandy check program.sy
```

```
program.sy: no type errors ✓
```

Use `--no-check` to skip the pre-run check (for quick throwaway runs). The
compiler always type-checks, because it needs the types to generate code.

## Types and speed

The annotations are not only for safety — they drive the native compiler. When
the typed subset of a program is compiled (Chapter 16), the known types let the
compiler emit unboxed C: an `int` becomes a machine integer, a `list<int>`
becomes a contiguous array, with no runtime type dispatch. The same annotations
that catch your bugs make your code fast.

The next chapter covers doing several things at once.
