# The Sandy Language Reference

This is the precise reference for Sandy. For a gentle tour, see the
[README](../README.md); this document is the authoritative description of the
grammar, semantics, type system, and runtime. For a gentler, example-driven
introduction, start with the [Tour of Sandy](tour.md).

Sandy files use the `.sy` extension.

---

## 1. Lexical structure

### 1.1 Comments

A comment starts with `#` and runs to the end of the line. Comments are
ignored by the compiler.

```sandy
# a full-line comment
x = 1   # a trailing comment
```

### 1.2 Whitespace and newlines

Newlines separate statements. Spaces and tabs are otherwise insignificant.
A newline is **ignored** (treated as line continuation) when:

- it appears inside `(` … `)` or `[` … `]`, or
- the previous token cannot end a statement — an operator, a comma, a colon,
  a dot, or an opening `(` `[` `{`.

This lets lists, maps, and long expressions span multiple lines naturally:

```sandy
total = 1 +
        2 +
        3
nums = [
    1, 2, 3,
]
```

### 1.3 Identifiers

An identifier begins with a letter or `_` and continues with letters, digits,
or `_`. Identifiers are case-sensitive.

### 1.4 Keywords

```
fn  return  if  elif  else  while  for  in  break  continue
try  catch  throw  struct  import  true  false  nil  and  or  not
```

`as` is a soft keyword used only in `import … as name`; it is otherwise a
normal identifier.

### 1.5 Literals

| Kind | Examples |
| --- | --- |
| Integer | `0`, `42`, `1000` |
| Float | `3.14`, `2.0`, `.5` |
| String | `"hello"`, `'hi'` |
| Boolean | `true`, `false` |
| Nil | `nil` |
| List | `[1, 2, 3]`, `[]` |
| Map | `{ "a": 1, "b": 2 }`, `{}` |

Integers are 64-bit; floats are IEEE-754 doubles.

### 1.6 String escapes and interpolation

Strings accept the escapes `\n \t \r \\ \" \' \0`. Any string may contain
interpolations: `{ expr }` evaluates `expr` and inserts its `print` form.
Double a brace to get a literal one: `{{` → `{`, `}}` → `}`.

```sandy
name = "Sandy"
print("hi {name}, {2 + 3}!")   # hi Sandy, 5!
print("{{literal braces}}")    # {literal braces}
```

Any expression is allowed inside `{ }`, including calls, indexing, method
calls, and nested strings.

---

## 2. Grammar

Approximate EBNF (`*` = zero or more, `?` = optional, `|` = alternative).
Newlines separate statements inside a block.

```ebnf
program    = statement* ;

statement  = funcdef | structdef | import | if | while | for
           | return | break | continue | try | throw | assign | exprstmt ;

funcdef    = "fn" IDENT "(" params? ")" ( "->" type )? block ;
params     = param ( "," param )* ;
param      = IDENT ( ":" type )? ;

structdef  = "struct" IDENT "{" ( field ","? )* "}" ;
field      = IDENT ( ":" type )? ;

import     = "import" STRING ( "as" IDENT )? ;

if         = "if" expr block ( "elif" expr block )* ( "else" block )? ;
while      = "while" expr block ;
for        = "for" IDENT "in" expr block ;
return     = "return" expr? ;
break      = "break" ;
continue   = "continue" ;
try        = "try" block "catch" IDENT block ;
throw      = "throw" expr ;

assign     = target ( "=" | "+=" | "-=" | "*=" | "/=" ) expr
           | IDENT ":" type "=" expr ;
target     = IDENT | postfix "[" expr "]" | postfix "." IDENT ;
exprstmt   = expr ;

block      = "{" statement* "}" ;

expr       = or ;
or         = and ( "or" and )* ;
and        = not ( "and" not )* ;
not        = "not" not | comparison ;
comparison = additive ( ( "==" | "!=" | "<" | ">" | "<=" | ">=" ) additive )* ;
additive   = multiplicative ( ( "+" | "-" ) multiplicative )* ;
multiplicative = power ( ( "*" | "/" | "%" ) power )* ;
power      = unary ( "**" power )? ;
unary      = "-" unary | postfix ;
postfix    = primary ( call | index | attr )* ;
call       = "(" ( expr ( "," expr )* )? ")" ;
index      = "[" expr "]" ;
attr       = "." IDENT ;
primary    = INT | FLOAT | STRING | "true" | "false" | "nil"
           | IDENT | "(" expr ")" | list | map ;
list       = "[" ( expr ( "," expr )* ","? )? "]" ;
map        = "{" ( entry ( "," entry )* ","? )? "}" ;
entry      = expr ":" expr ;

type       = "int" | "float" | "string" | "bool" | "nil" | "any"
           | "fn" ( "(" ( type ( "," type )* )? ")" ( "->" type )? )?
           | "list" ( "<" type ">" )?
           | "map" ( "<" type "," type ">" )?
           | IDENT ;   (* a struct name *)
```

### 2.1 Operator precedence

From lowest to highest:

| Level | Operators | Associativity |
| --- | --- | --- |
| 1 | `or` | left |
| 2 | `and` | left |
| 3 | `not` (unary) | right |
| 4 | `==` `!=` `<` `>` `<=` `>=` | left |
| 5 | `+` `-` | left |
| 6 | `*` `/` `%` | left |
| 7 | `**` | right |
| 8 | unary `-` | right |
| 9 | postfix `()` `[]` `.` | left |

---

## 3. Values and types

Sandy has these runtime types:

| Type | Notes |
| --- | --- |
| `int` | 64-bit signed integer |
| `float` | 64-bit IEEE-754 double |
| `string` | immutable text |
| `bool` | `true` / `false` |
| `nil` | the single absent value |
| `list` | ordered, mutable, heterogeneous |
| `map` | insertion-ordered key→value; keys are scalars |
| struct | a user-defined record (see §7) |
| function | a named or nested function value (closure) |
| module | an imported namespace (see §8) |

`type(x)` returns the type name as a string; for a struct instance it returns
the struct's name.

### 3.1 Truthiness

Falsy values are `nil`, `false`, `0`, `0.0`, `""`, `[]`, and `{}`. Everything
else is truthy.

### 3.2 Equality

`==` compares by value. Different types are never equal (so `1 == true` is
`false` and `1 == 1.0` is `true` only among numbers). Structs are equal when
they have the same type and equal fields.

---

## 4. Operators

- Arithmetic `+ - * /` `%` `**` on numbers. `/` **always** produces a float.
  `%` is floor modulo (the result takes the sign of the divisor), matching the
  interpreter and the native backend.
- `+` also concatenates two strings or two lists.
- `*` also repeats: `string * int` and `list * int`.
- Comparisons `< > <= >=` work on two numbers or two strings (lexicographic).
- `and` / `or` short-circuit and return one of their operands (not a coerced
  bool); `not` returns a bool.
- Division or modulo by zero is a runtime error.

---

## 5. Statements

### 5.1 Variables and assignment

Assignment creates or updates a binding. There is no separate declaration
keyword; `x = 5` binds `x`. Assignment updates the nearest existing binding in
an enclosing scope, otherwise binds in the current function scope.

```sandy
x = 5
x += 3          # compound: += -= *= /=
x: int = 10     # optional type annotation (see §9)
```

Sandy uses **function-level scoping**: blocks (`if`, `while`, `for` bodies) do
not introduce a new scope; only a function call does.

### 5.2 Conditionals

```sandy
if cond { … } elif other { … } else { … }
```

### 5.3 Loops

```sandy
while cond { … }
for x in iterable { … }     # iterable: list, string (chars), map (keys), range
```

`break` exits the nearest loop; `continue` skips to its next iteration.
`range(n)`, `range(a, b)`, and `range(a, b, step)` produce integer sequences.

### 5.4 Functions

```sandy
fn add(a, b) { return a + b }
```

Functions are first-class values and close over their defining scope. A
function that reaches its end without `return` yields `nil`. Parameters and the
return type may be annotated (§9).

### 5.5 Error handling

```sandy
try {
    risky()
} catch e {
    print("failed: " + e)   # e is the error message (a string)
}
throw "some message"        # raise a runtime error
```

A runtime error inside `try` transfers control to `catch`, binding the error
message to the named variable. Errors propagate through function calls until a
`try` catches them; an uncaught error stops the program. `throw expr` raises an
error whose message is `expr` rendered as a string.

---

## 6. Structs

```sandy
struct Point { x, y }              # fields may be typed: { x: int, y: int }

p = Point(3, 4)                    # construct positionally
p.x                                # field access
p.y = 10                           # field mutation (also p.y += 1)
type(p)                            # "Point"
Point(1, 2) == Point(1, 2)         # true (by value)
```

Constructing a struct requires exactly one argument per field, in order.

---

## 7. Modules

```sandy
import "geometry.sy" as geo        # or: import "geometry"  (alias = filename)
geo.area(geo.Circle(5))
```

`import` runs another `.sy` file once and binds its top-level definitions
(functions, structs, variables) as a namespaced module value. Access members
with `module.member`.

- Paths resolve **relative to the importing file**; then against installed
  package dependencies (§7.1); then the bundled standard library (§11).
- Modules are cached by absolute path — imported once, even through diamond
  import graphs.
- Circular imports are detected and reported.
- A module runs on the **same engine** as its importer, so callbacks passed
  into module functions behave identically on the interpreter and the VM.

### 7.1 Packages

A project is a directory with a manifest, `sandy.toml`:

```toml
[package]
name = "myapp"
version = "0.1.0"

[dependencies]
geometry = "^1.2.0"                                  # registry version constraint
utils    = { path = "../utils" }                     # local path dependency
webby    = { git = "https://example.com/webby.git" } # git dependency
```

- `sandy add NAME SPEC` adds a dependency (a version, a path, or a git URL).
- `sandy install` resolves every dependency to a directory (path deps in place;
  registry and git deps vendored into `sandy_modules/`), verifies each exposes
  an importable module, and writes `sandy.lock` for reproducible resolution.
- `sandy publish` copies the current project into the registry as
  `<name>/<version>/`; published versions are immutable.
- **Version constraints** are semver: `1.2.3` (exact), `^1.2.0` (compatible,
  same left-most non-zero), `~1.2.0` (same major.minor), comparators like
  `>=1.0.0,<2.0.0`, or `*`. The highest published version that satisfies the
  constraint is chosen. The registry is named by `$SANDY_REGISTRY` (default
  `~/.sandy/registry`) and can be either a local **directory** or an **HTTP
  URL**. `sandy registry serve` runs a bundled HTTP registry server
  (`GET /packages/<name>`, `GET /packages/<name>/<version>`, `PUT` to publish);
  the client speaks the same protocol for listing, fetching, and publishing.
- A package directory is itself a project; its importable module is
  `<dir>/<name>.sy` or `<dir>/src/<name>.sy`, and `import "name/sub"` imports a
  submodule.
- A dependency is then imported by **bare name** (`import "geometry"`), and if
  it carries type annotations, calls into it are checked **across the package
  boundary** before the program runs.
- A local file of the same name shadows a dependency, which shadows the standard
  library.

### 7.2 Concurrency

A Go-flavored model of tasks and channels:

- `spawn(fn, args...)` runs `fn(args...)` as a background **task** and returns a
  handle. `wait(task)` blocks until it finishes and returns its value (or
  re-raises the error it hit).
- `channel(capacity?)` makes a **channel**. `send(ch, v)` and `recv(ch)` pass
  values between tasks and block to synchronize: an unbuffered channel
  (`channel()`) is a rendezvous, a buffered one (`channel(n)`) holds up to `n`
  values before a sender blocks. `close(ch)` closes it; `recv` on a drained,
  closed channel returns `nil`.

Channels are the safe way to share data between tasks ("share memory by
communicating"); mutating a plain variable from two tasks without a channel is
a data race, as in Go. Tasks are real OS threads. `spawn` runs on the default
engine (the tree-walker); `channel`/`send`/`recv`/`close` work everywhere.

---

## 8. Gradual type system

Type annotations are **optional**. Unannotated code is fully dynamic: every
unannotated binding has type `any`, which is compatible with everything, so
dynamic programs produce **zero** type errors. Where you add annotations, the
checker verifies them **before the program runs**.

### 8.1 Where annotations go

```sandy
fn add(a: int, b: int) -> int { return a + b }
score: int = 0
struct Point { x: int, y: int }
fn move(p: Point, dx: int) -> Point { … }
apply: fn(int) -> int = add      # (illustrative) a function-typed binding
```

**Function types.** `fn(T1, T2) -> R` is the type of a function taking `T1, T2`
and returning `R` (omit `-> R` for a function that returns nothing). A bare
`fn` means "any function" and stays fully gradual. A function value — a
function passed as an argument, stored, or returned — is checked against such a
type, and calls through it are verified.

### 8.2 What is checked

- Assignment to an annotated variable, and later reassignment, must match.
- A function's `return` values must match its declared return type.
- Call arity and argument types against annotated parameters, including calls
  made through a value of function type `fn(...) -> R`.
- Operator operands (e.g. `int + string` is rejected when both are known).
- List/map element types via `list<T>` / `map<K, V>`.
- Struct construction (arity and field types), field access (unknown field),
  and field assignment.
- Imported module members: calls to module functions and module struct
  construction are checked across the file boundary.
- Unknown type names in annotations are reported.

`any` on either side of a check always passes, which is what keeps dynamic
code free of false positives. Run `sandy check file.sy` to type-check without
running.

---

## 9. Built-in functions

| Signature | Result |
| --- | --- |
| `print(...)` | print args separated by spaces, then a newline; returns nil |
| `input(prompt?)` | read a line of text |
| `len(x)` | length of a string, list, or map |
| `type(x)` | type name as a string |
| `str(x)` `int(x)` `float(x)` `bool(x)` | conversions |
| `range(n)` / `range(a,b)` / `range(a,b,step)` | list of integers |
| `abs`, `min(list)`, `max(list)`, `sum(list)`, `round(x, n?)`, `pow(a,b)` | numeric |
| `sqrt`, `floor`, `ceil` | math |
| `ord(char)`, `chr(code)` | Unicode code point of a 1-char string, and back |
| `sin`, `cos`, `tan`, `exp`, `log(x, base?)`, `log10` | trig, exponential, logarithms |
| `sha256(s)`, `md5(s)` | hex cryptographic digests of the UTF-8 text |
| `base64_encode(s)`, `base64_decode(s)` | Base64 encode / decode (UTF-8) |
| `push(list, x)`, `pop(list)` | mutate a list |
| `keys(map)`, `values(map)`, `has(container, x)` | collections |
| `upper`, `lower`, `trim`, `split(s, sep?)`, `join(list, sep)` | strings |
| `read_file(p)`, `read_lines(p)`, `write_file(p, t)`, `append_file(p, t)` | files |
| `now()`, `clock()` | wall-clock epoch seconds; monotonic seconds for timing |
| `sleep(seconds)`, `exit(code?)` | pause; end the program with an exit code |
| `env(name, default?)` | read an environment variable (nil/default if unset) |
| `args()` | the program's command-line arguments (list of strings) |
| `cwd()`, `exists(p)`, `is_file(p)`, `is_dir(p)` | query the filesystem |
| `list_dir(p)`, `make_dir(p)`, `remove_file(p)` | list / create / delete |
| `http_get(url, timeout?)` | HTTP GET → map `{status, ok, body}` |
| `http_post(url, body, content_type?, timeout?)` | HTTP POST → `{status, ok, body}` |
| `re_test`, `re_find`, `re_find_all`, `re_groups`, `re_replace`, `re_split` | regex (see the `regex` module) |
| `spawn(fn, args...)`, `wait(task)` | run a function as a task; await its result |
| `channel(capacity?)`, `send(ch, v)`, `recv(ch)`, `close(ch)` | task communication |

Many also work as methods: `text.upper()`, `list.push(x)`, `map.keys()`,
`list.sort()`, `list.reverse()`, `str.replace(a, b)`, `str.has(sub)`, and more.

---

## 10. Standard library

Bundled modules, written in Sandy, imported by bare name:

- **`math`** — `pi`, `e`, `tau`, `sign`, `clamp`, `gcd`, `lcm`, `factorial`,
  `is_prime`, `mean`, `median`, `variance`, `stddev`, `hypot`, `deg2rad`,
  `rad2deg`, `log_base`.
- **`maps`** — map helpers: `get(m, k, default)`, `items`, `from_pairs`,
  `merge`, `invert`, `map_values`, `pick`.
- **`base64`** — `encode` / `decode` (over the base64 builtins).
- **`hash`** — `djb2` (fast, non-cryptographic string hash; use the `sha256`
  / `md5` builtins for cryptographic digests).
- **`strings`** — `reverse`, `capitalize`, `repeat`, `pad_left`, `pad_right`,
  `count`, `contains`.
- **`lists`** — `map`, `filter`, `reduce`, `reverse`, `contains`, `index_of`,
  `unique`, `take`, `drop`, `first`, `last`.
- **`sort`** — `sort`, `sort_by`, `sort_desc`, `is_sorted` (a stable,
  non-destructive insertion sort).
- **`sets`** — `union`, `intersection`, `difference`, `symmetric_difference`,
  `is_subset`, `is_disjoint`, `contains`, `unique` (sets as lists of uniques).
- **`json`** — `to_json(value)` encodes Sandy values to a JSON string; `parse(text)`
  decodes JSON back into Sandy values.
- **`random`** — a seedable, deterministic PRNG: `seed`, `next` (float in
  `[0, 1)`), `randint(lo, hi)`, `boolean`, `choice`, `shuffle`, `sample`.
- **`time`** — `epoch`, `monotonic`, `since(start)`, `sleep_ms(ms)`, and
  `format(seconds)` for a human-readable duration; built on the `now`/`clock`/
  `sleep` builtins.
- **`os`** — path-string helpers `join`, `basename`, `dirname`, `extension`,
  `stem` (pairs with the `cwd`/`list_dir`/`exists`/… filesystem builtins).
- **`http`** — JSON-aware wrappers over the `http_get`/`http_post` builtins:
  `get_json(url)`, `post_json(url, value)`, and `status`/`body`/`ok`
  accessors. An HTTP error status throws; a transport failure throws too.
- **`text`** — character predicates (`is_digit`, `is_alpha`, `is_alnum`,
  `is_space`, `is_upper`, `is_lower`), plus `chars`, `lines`, `words`,
  `title`, and `count`.
- **`csv`** — `parse(text)` -> list of rows (lists of string fields) and
  `format(rows)` -> CSV text, with RFC 4180-style quoting; also `parse_line`
  and `format_row`.
- **`regex`** — `test`, `find`, `find_all`, `groups`, `replace` (with `\1`
  backreferences), and `split`, over the `re_*` builtins (host regex syntax).
- **`assert`** — `eq`, `neq`, `is_true`, `is_false`; each throws a descriptive
  message on failure, for writing tests in Sandy itself.

A local file of the same name takes precedence, so any module can be shadowed.

---

## 11. Execution model

Sandy has two interpreters that produce identical results:

- **Tree-walker** (default) — walks the AST directly.
- **Bytecode VM** (`sandy --vm file.sy`) — compiles to bytecode and executes
  on a stack machine with type-specialized numeric opcodes.

A **native backend** (`sandy build file.sy`) transpiles the statically typed
subset — scalars (`int`, `float`, `bool`, `string`), typed `list<T>` and
`map<K,V>`, structs, typed functions (including first-class *top-level*
functions via `fn(...) -> R`), control flow, and `try`/`catch`/`throw` — to C
and compiles it with the system C compiler. Heap memory leaks by default (fine
for short-lived tools); `sandy build --gc` adds a conservative garbage
collector for long-running programs. Dynamic features (untyped `any` values,
capturing closures, modules) are reported as unsupported rather than
mis-compiled.

---

## 12. Command-line interface

```
sandy                 start the REPL
sandy FILE.sy         run a program (tree-walker)
sandy run FILE.sy     run a program (explicit)
sandy --vm FILE.sy    run on the bytecode VM
sandy check FILE.sy   type-check without running
sandy fmt FILE.sy     format in place (--check to only verify)
sandy add NAME SPEC   add a dependency (version, path, or git URL)
sandy install         resolve dependencies and write sandy.lock
sandy publish         publish the current project to the registry
sandy registry serve  run an HTTP registry server (--port, --dir, --host)
sandy lsp             start the language server over stdio (for editors)
sandy build FILE.sy   compile the typed subset to a native executable
sandy --no-check …    skip the static type checker
sandy --version       print the version
sandy --help          show help
```
