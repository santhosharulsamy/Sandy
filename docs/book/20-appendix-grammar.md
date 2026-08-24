# Chapter 20 — Appendix: Grammar

This appendix gives the formal syntax of Sandy, the keyword and operator
reference, and a compact summary of the language.

## Grammar

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

## Operator precedence

From lowest (binds loosest) to highest (binds tightest):

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

## Keywords

Reserved words that cannot be used as identifiers:

```
fn   return   if   elif   else   while   for   in   break   continue
try   catch   throw   struct   import   true   false   nil   and   or   not
```

`as` is a soft keyword, meaningful only in `import "x" as name`.

## Escape sequences in strings

```
\n   newline        \"   double quote
\t   tab            \\   backslash
\r   carriage return
{expr}  interpolation      {{  literal {      }}  literal }
```

## Semantic quick reference

A few rules that are easy to forget:

- Statements are separated by **newlines**; there is no `;`.
- `elif` and `else` sit on the **same line** as the preceding `}`.
- **`/` always produces a float**; there is no integer-division operator (use
  `floor(a / b)`).
- `%` is **floor modulo** (the result has the sign of the divisor).
- `**` is exponentiation and is **right-associative**.
- Scope is **function-level**; loop and `if` blocks do not create a new scope.
- Structs, lists, and maps are **reference values**; scalars and strings are
  passed by value.
- A caught error is always a **string** (the message).
- `type()` returns the type name; struct instances report their struct's name.

## The language in one screen

```sandy
# variables, interpolation
name = "Sandy"
print("hello {name}")

# functions, optional types
fn add(a: int, b: int) -> int { return a + b }

# control flow
for i in range(3) {
    if i % 2 == 0 { print("{i} even") } else { print("{i} odd") }
}

# collections
xs = [1, 2, 3]
push(xs, 4)
m = {"a": 1}
m["b"] = 2

# structs
struct Point { x: int, y: int }
p = Point(1, 2)
p.y += 5

# errors
try { throw "nope" } catch e { print(e) }

# modules
import "math" as math
print(math.gcd(12, 18))

# concurrency
ch = channel()
fn worker() { send(ch, 42) }
spawn(worker)
print(recv(ch))
```

---

*This is the end of the book. You now know all of Sandy: the syntax, the type
system, the standard library, the tools, and how to compile it for speed. The
[reference](../reference.md) is the terse companion, the
[examples](../../examples) are runnable, and the source is yours to read —
Sandy is a small language, and reading its implementation is one of the best
ways to understand it.*
