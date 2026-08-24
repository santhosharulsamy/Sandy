# Chapter 10 — Collections

Sandy has two built-in containers: the **list**, an ordered sequence, and the
**map**, a key-value table. Both are mutable and grow on demand.

## Lists

### Creating and reading

```sandy
xs = [10, 20, 30]
print(xs[0])         # 10
print(xs[-1])        # 30   (negative indexes count from the end)
print(len(xs))       # 3
```

Indexing out of range is a runtime error (catchable with `try`, Chapter 12).

### Growing and mutating

```sandy
xs = [1, 2, 3]
push(xs, 4)          # append; xs is now [1, 2, 3, 4]
xs[0] = 99           # replace an element
last = pop(xs)       # remove and return the last element
print(last)          # 4
```

### Iterating

```sandy
for x in [1, 2, 3] {
    print(x * x)     # 1, 4, 9
}
```

### Building a list

A common pattern is to start empty and `push`:

```sandy
squares = []
for i in range(1, 6) {
    push(squares, i * i)
}
print(squares)       # [1, 4, 9, 16, 25]
```

### Concatenation and repetition

```sandy
print([1, 2] + [3, 4])   # [1, 2, 3, 4]
print([0] * 3)           # [0, 0, 0]
```

### Equality

Lists compare element-by-element:

```sandy
print([1, 2, 3] == [1, 2, 3])   # true
```

### Typed lists

Annotate a list with an element type to have it checked, and to make it eligible
for native compilation:

```sandy
nums: list<int> = [1, 2, 3]
```

The `lists` standard-library module adds higher-order helpers — `map`, `filter`,
`reduce`, `reverse`, `unique`, and more (Chapter 17). The `sort` module sorts.

## Maps

### Creating and reading

```sandy
ages = {"ada": 36, "bob": 41}
print(ages["ada"])       # 36
print(has(ages, "cy"))   # false
```

Looking up a missing key is a runtime error; guard with `has`, or use
`maps.get(m, key, default)` from the standard library.

### Adding and updating

```sandy
ages = {"ada": 36}
ages["bob"] = 41         # add a new entry
ages["ada"] = 37         # update an existing one
print(len(ages))         # 2
```

### Keys, values, and iteration

Maps preserve **insertion order**. Iterating a map yields its keys:

```sandy
m = {"a": 1, "b": 2, "c": 3}
for k in m {
    print(k + " = " + str(m[k]))
}
print(keys(m))       # ["a", "b", "c"]
print(values(m))     # [1, 2, 3]
```

### Equality

Maps compare by their key-value pairs, regardless of order:

```sandy
print({"a": 1, "b": 2} == {"b": 2, "a": 1})   # true
```

### Typed maps

Annotate with key and value types:

```sandy
scores: map<string, int> = {}
```

For native compilation, keys are `int` or `string` and values are scalars or
strings.

### Map helpers

The `maps` module (Chapter 17) adds `get`, `items`, `from_pairs`, `merge`,
`invert`, `map_values`, and `pick`.

## Choosing between them

Use a **list** for an ordered collection you iterate or index by position; use a
**map** when you look values up by a key. Both are covered further — with
worked examples — in the standard-library chapter.

The next chapter introduces the way to define your own structured types.
