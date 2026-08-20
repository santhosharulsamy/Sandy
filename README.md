# Sandy 🏖️

**Sandy** is a small, friendly scripting language — designed to be *easy to
learn, easy to write, and fast enough to be useful*. If you like Python, you
already know most of Sandy. Programs live in `.sy` files.

```sandy
fn greet(name) {
    return "Hello, " + name + "!"
}

print(greet("Sandy"))
```

```
$ sandy hello.sy
Hello, Sandy!
```

This repository contains the reference interpreter for Sandy, written in
Python. It's a clean tree-walking interpreter: a lexer, a parser, and an
evaluator — easy to read, easy to extend.

---

## Quick start

No installation needed — you just need Python 3.8+.

```bash
# Run a program
python -m sandy examples/hello.sy
# ...or with the launcher
./sandy.py examples/hello.sy

# Start the interactive REPL
python -m sandy

# Show the version / help
python -m sandy --version
python -m sandy --help
```

Optionally install it so `sandy` is on your PATH:

```bash
pip install -e .
sandy examples/fizzbuzz.sy
```

Run the tests:

```bash
python -m unittest discover -s tests
```

---

## Language tour

### Comments and printing

```sandy
# This is a comment.
print("Hello")          # print writes a line to the screen
print(1, 2, 3)          # prints: 1 2 3
```

### Variables

No keyword needed — just assign. Reassigning updates the nearest variable
that already exists.

```sandy
x = 10
name = "Sandy"
pi = 3.14159
ready = true
nothing = nil
```

Compound assignment works too:

```sandy
count = 0
count += 1
count -= 1
count *= 2
count /= 4
```

### Types

| Type    | Example                       |
| ------- | ----------------------------- |
| int     | `42`, `-7`                    |
| float   | `3.14`, `2.0`                 |
| string  | `"hi"`, `'also hi'`           |
| bool    | `true`, `false`               |
| nil     | `nil`                         |
| list    | `[1, 2, 3]`                   |
| map     | `{ "a": 1, "b": 2 }`          |

### Operators

```sandy
# Arithmetic
2 + 3        # 5
10 - 4       # 6
6 * 7        # 42
10 / 4       # 2.5   (division always gives a float, like Python 3)
17 % 5       # 2
2 ** 10      # 1024  (** is right-associative)

# Comparison
a == b   a != b   a < b   a > b   a <= b   a >= b

# Logical (words — easy to read, and they short-circuit)
true and false      # false
true or false       # true
not true            # false

# Strings and lists
"foo" + "bar"       # "foobar"
"ab" * 3            # "ababab"
[1, 2] + [3]        # [1, 2, 3]
```

### Conditionals

```sandy
if score > 90 {
    print("A")
} elif score > 80 {
    print("B")
} else {
    print("C")
}
```

### Loops

```sandy
# while
i = 0
while i < 5 {
    print(i)
    i += 1
}

# for-in over a range
for n in range(1, 4) {
    print(n)          # 1, 2, 3
}

# for-in over a list, string, or map keys
for item in [10, 20, 30] { print(item) }
for ch in "hey"        { print(ch) }
for key in { "a": 1 }  { print(key) }

# break / continue
for n in range(100) {
    if n == 5 { break }
    if n % 2 == 0 { continue }
    print(n)          # 1, 3
}
```

### Functions

Functions are first-class values. They can be passed around, returned, and
they close over the variables in scope where they were defined.

```sandy
fn add(a, b) {
    return a + b
}

fn make_counter() {
    count = 0
    fn tick() {
        count += 1
        return count
    }
    return tick               # returns a closure
}

next = make_counter()
print(next())   # 1
print(next())   # 2
```

### Lists

```sandy
nums = [3, 1, 2]
print(nums[0])          # 3
print(nums[-1])         # 2   (negative indexing counts from the end)
nums[0] = 99            # index assignment

push(nums, 4)           # append (also: nums.push(4))
last = pop(nums)        # remove & return the last item
print(len(nums))
print(nums.sort())      # [1, 2, 99]
print(nums.reverse())
```

### Maps

```sandy
person = { "name": "Ada", "age": 36 }
print(person["name"])       # Ada
person["age"] = 37          # update / insert

print(keys(person))         # ["name", "age"]   (also: person.keys())
print(values(person))
print(person.has("name"))   # true
```

### Strings

```sandy
s = "Hello, World"
print(s.upper())              # HELLO, WORLD
print(s.lower())
print(s.split(", "))          # ["Hello", "World"]
print(s.starts_with("Hell"))  # true
print(s.replace("o", "0"))    # Hell0, W0rld
print(len(s))                 # 12
```

---

## Built-in functions

| Function | Purpose |
| --- | --- |
| `print(...)` | Print values separated by spaces, followed by a newline |
| `input(prompt?)` | Read a line of text from the user |
| `len(x)` | Length of a string, list, or map |
| `type(x)` | Type name as a string (`"int"`, `"list"`, ...) |
| `str(x)` `int(x)` `float(x)` `bool(x)` | Type conversions |
| `range(n)` / `range(a, b)` / `range(a, b, step)` | List of integers |
| `abs`, `min`, `max`, `sum`, `round`, `pow` | Numeric helpers |
| `sqrt`, `floor`, `ceil` | Math helpers |
| `push(list, x)`, `pop(list)` | Mutate a list |
| `keys(map)`, `values(map)`, `has(container, x)` | Collection helpers |
| `upper`, `lower`, `trim`, `split(s, sep?)`, `join(list, sep)` | String helpers |

Many of these also work as **methods**: `text.upper()`, `list.push(x)`,
`map.keys()`, `list.sort()`, `list.reverse()`, `str.replace(a, b)`, and more.

---

## Examples

The [`examples/`](examples/) directory has runnable programs:

| File | Shows off |
| --- | --- |
| `hello.sy` | The basics — printing and variables |
| `fizzbuzz.sy` | Loops and conditionals |
| `fib.sy` | Recursion and iteration |
| `data.sy` | Lists, maps, methods, higher-order functions |
| `closures.sy` | Closures and functions as values |

```bash
python -m sandy examples/data.sy
```

---

## How it works

The interpreter is a classic three-stage pipeline:

```
source (.sy)  ──▶  Lexer  ──▶  tokens  ──▶  Parser  ──▶  AST  ──▶  Interpreter  ──▶  result
```

| Module | Responsibility |
| --- | --- |
| `sandy/lexer.py` | Turns source text into tokens (handles comments, strings, smart line-continuation) |
| `sandy/tokens.py` | Token types and keywords |
| `sandy/parser.py` | Recursive-descent parser with precedence climbing → AST |
| `sandy/nodes.py` | AST node classes |
| `sandy/interpreter.py` | Tree-walking evaluator, scopes, closures, control flow |
| `sandy/values.py` | Runtime values and how they're displayed |
| `sandy/builtins.py` | Built-in functions and type methods |
| `sandy/runtime.py` | Glue: run a string or a file, report errors nicely |
| `sandy/repl.py` | The interactive prompt |
| `sandy/cli.py` | Command-line entry point |

Errors carry line numbers and print friendly diagnostics:

```
$ sandy broken.sy

broken.sy: RuntimeError (line 3): undefined variable 'total'
  3 | print(total)
```

---

## Design notes

- **Familiar first.** Sandy borrows Python's feel (dynamic typing, clean
  syntax, `and`/`or`/`not`, `range`, truthiness) so it's instantly readable.
- **Braces over indentation.** Blocks use `{ }`, statements end at newlines.
  This keeps the parser simple and copy-paste friendly, while newlines inside
  brackets and after operators are treated as continuations so multi-line
  lists, maps and expressions just work.
- **Small core, batteries included.** A compact set of builtins covers the
  common cases; everything else is an easy addition in `builtins.py`.

## Roadmap

Sandy 0.1 is a complete, working interpreter. Natural next steps:

- String interpolation (`"hi {name}"`)
- More iteration helpers (`map`, `filter`, `enumerate`)
- Modules / `import`
- A bytecode compiler + VM for extra speed

Contributions and ideas welcome.

## License

MIT
