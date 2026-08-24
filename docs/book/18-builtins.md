# Chapter 18 — Built-in Functions

These functions are always available — no import needed. They are grouped here by
purpose. Many string and collection builtins also work as methods
(`s.upper()`, `xs.push(x)`); the reference notes where.

## Core

| Function | Description |
| --- | --- |
| `print(...)` | print the arguments separated by spaces, then a newline |
| `input(prompt?)` | read a line of text from standard input |
| `len(x)` | length of a string, list, or map |
| `type(x)` | the value's type name, as a string |
| `range(n)` / `range(a, b)` / `range(a, b, step)` | a sequence of integers to loop over |

## Conversions

| Function | Description |
| --- | --- |
| `str(x)` | the display string of any value |
| `int(x)` | convert a number or numeric string to an integer (truncates floats) |
| `float(x)` | convert a number or numeric string to a float |
| `bool(x)` | the truthiness of a value |
| `ord(ch)` | the Unicode code point of a one-character string |
| `chr(n)` | the one-character string for a code point |

## Math

| Function | Description |
| --- | --- |
| `abs(x)` | absolute value |
| `min(list)` / `max(list)` | smallest / largest element |
| `sum(list)` | sum of a list of numbers |
| `round(x, ndigits?)` | round to `ndigits` decimal places (default 0) |
| `sqrt(x)` | square root |
| `floor(x)` / `ceil(x)` | round down / up to an integer |
| `pow(a, b)` | `a` to the power `b` |
| `sin`, `cos`, `tan` | trigonometric functions (radians) |
| `exp(x)` | e to the power `x` |
| `log(x, base?)` | natural logarithm, or logarithm in `base` |
| `log10(x)` | base-10 logarithm |

## Lists and maps

| Function | Description |
| --- | --- |
| `push(list, x)` | append `x` to a list (also `list.push(x)`) |
| `pop(list)` | remove and return the last element |
| `keys(map)` | a list of the map's keys, in insertion order |
| `values(map)` | a list of the map's values |
| `has(container, x)` | whether a map has a key (or a list/string contains `x`) |

## Strings

| Function | Description |
| --- | --- |
| `upper(s)` / `lower(s)` | change case (also methods) |
| `trim(s)` | remove leading/trailing whitespace (also a method) |
| `split(s, sep?)` | split into a list (whitespace if `sep` omitted) |
| `join(list, sep)` | join a list of strings with a separator |

## Hashing and encoding

| Function | Description |
| --- | --- |
| `sha256(s)` / `md5(s)` | hex cryptographic digest of the UTF-8 text |
| `base64_encode(s)` / `base64_decode(s)` | Base64 encode / decode |

## Files

| Function | Description |
| --- | --- |
| `read_file(path)` | the whole file as a string |
| `read_lines(path)` | the file as a list of lines |
| `write_file(path, text)` | write text, replacing the file |
| `append_file(path, text)` | append text to the file |

## The operating system

| Function | Description |
| --- | --- |
| `args()` | the program's command-line arguments (a list of strings) |
| `env(name, default?)` | an environment variable, or the default / `nil` |
| `cwd()` | the current working directory |
| `exists(p)` / `is_file(p)` / `is_dir(p)` | filesystem queries |
| `list_dir(p)` | a sorted list of a directory's entries |
| `make_dir(p)` | create a directory (and any parents) |
| `remove_file(p)` | delete a file |
| `now()` | wall-clock seconds since the epoch |
| `clock()` | monotonic seconds, for measuring elapsed time |
| `sleep(seconds)` | pause execution |
| `exit(code?)` | end the program with an exit code |

## Regular expressions

| Function | Description |
| --- | --- |
| `re_test(pattern, s)` | whether the pattern matches anywhere |
| `re_find(pattern, s)` | the first match, or `nil` |
| `re_find_all(pattern, s)` | a list of all matches |
| `re_groups(pattern, s)` | capture groups of the first match, or `nil` |
| `re_replace(pattern, s, repl)` | replace matches (`\1` backreferences) |
| `re_split(pattern, s)` | split on the pattern |

The `regex` module (Chapter 17) wraps these with friendlier names.

## Concurrency

| Function | Description |
| --- | --- |
| `spawn(fn, args...)` | run `fn` as a background task; returns a task |
| `wait(task)` | block for a task and return its result |
| `channel(capacity?)` | create a channel (0 / omitted = unbuffered) |
| `send(ch, value)` | send a value (may block) |
| `recv(ch)` | receive a value (blocks; `nil` when closed and drained) |
| `close(ch)` | close a channel |

See Chapter 15 for the concurrency model.

## Note for compiled programs

The native compiler supports the numeric, string, list/map, and core builtins.
The OS-facing, networking, regex, hashing, and concurrency builtins are dynamic
and run on the interpreter/VM; `sandy build` reports clearly if a program uses
one.

The next chapter covers the command-line tools around the language.
