# Chapter 3 — Lexical Structure

Before Sandy understands your program, it breaks the source text into *tokens*:
names, keywords, numbers, strings, operators, and punctuation. This chapter
describes those raw ingredients and the small number of rules about whitespace
and comments.

## Source files

A Sandy program is a UTF-8 text file, conventionally ending in `.sy`. A program
is a sequence of statements. There is no required top-level function; execution
begins at the first statement.

## Statements end at newlines

Sandy separates statements by **newlines**, not semicolons. There is no `;`
statement terminator, and you cannot put two statements on one line with a
separator:

```sandy
x = 1
y = 2          # correct: one statement per line
```

Blank lines and indentation are insignificant except as readability — Sandy is
brace-delimited, not indentation-delimited. Blocks are written with `{ }`.

## Comments

A comment starts with `#` and runs to the end of the line:

```sandy
# this is a comment
x = 42        # so is this
```

There are no block comments; use `#` on each line.

## Identifiers

An identifier names a variable, function, struct, parameter, or module. It
starts with a letter or underscore and continues with letters, digits, or
underscores:

```
count   _total   isReady   fib2   snake_case_name
```

By convention, a leading underscore (`_helper`) marks something internal.

## Keywords

The following words are reserved and cannot be used as identifiers:

```
fn   return   if   elif   else   while   for   in   break   continue
try   catch   throw   struct   import   true   false   nil   and   or   not
```

`as` is a *soft* keyword: it has special meaning only in `import "x" as name`,
and is otherwise an ordinary identifier.

## Literals

**Integers** are written in the usual way. They have arbitrary precision on the
interpreter and VM (they are Python integers), and 64-bit range when compiled
natively.

```
0    42    1000000
```

**Floats** contain a decimal point:

```
3.14    0.5    10.0
```

**Booleans** are `true` and `false`. **Nil**, the absence of a value, is `nil`.

**Strings** are enclosed in double quotes and may contain escape sequences and
interpolation (Chapter 7):

```sandy
"hello"
"line one\nline two"
"total: {count}"
```

**List and map literals** use brackets and braces:

```sandy
[1, 2, 3]
{"a": 1, "b": 2}
```

## Operators and punctuation

The operator and punctuation tokens are:

```
+  -  *  /  %  **            arithmetic
==  !=  <  >  <=  >=         comparison
=  +=  -=  *=  /=            assignment
(  )  [  ]  {  }             grouping, indexing, blocks/maps
,  :  .  ->                  separators and annotations
```

The words `and`, `or`, and `not` are the logical operators (Chapter 6).

## A note on braces inside strings

Because `{` begins interpolation inside a string, a *literal* brace in a string
is written by doubling it: `"{{"` produces `{` and `"}}"` produces `}`. This
only matters inside string literals; everywhere else braces delimit blocks and
maps as usual. See Chapter 7.

With the tokens established, the next chapter describes the values those tokens
denote.
