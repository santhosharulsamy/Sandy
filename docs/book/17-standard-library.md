# Chapter 17 — The Standard Library

Sandy ships with a standard library of modules, **written in Sandy itself** and
imported by bare name. A local file of the same name shadows a standard module,
so you can override any of them. This chapter documents each module.

```sandy
import "math" as math
import "json" as json
# ... etc.
```

---

## `math` — numbers and statistics

Constants `pi`, `e`, `tau`, and:

| Function | Result |
| --- | --- |
| `sign(x)` | `-1`, `0`, or `1` |
| `clamp(x, lo, hi)` | `x` limited to the range |
| `gcd(a, b)` / `lcm(a, b)` | greatest common divisor / least common multiple |
| `factorial(n)` | `n!` |
| `is_prime(n)` | primality test |
| `mean(xs)` / `median(xs)` | average / middle value |
| `variance(xs)` / `stddev(xs)` | spread |
| `hypot(a, b)` | `sqrt(a*a + b*b)` |
| `deg2rad(d)` / `rad2deg(r)` | angle conversions |
| `log_base(x, base)` | logarithm in an arbitrary base |

```sandy
print(math.gcd(48, 36))          # 12
print(math.median([3, 1, 2]))    # 2
```

(Trigonometric and exponential functions — `sin`, `cos`, `tan`, `exp`, `log`,
`log10`, `sqrt`, `pow` — are global builtins; see Chapter 18.)

## `strings` — string helpers

`reverse`, `capitalize`, `repeat(s, n)`, `pad_left(s, width, ch)`,
`pad_right(s, width, ch)`, `count(s, sub)`, `contains(s, sub)`.

```sandy
import "strings" as strings
print(strings.reverse("abc"))    # cba
print(strings.pad_left("7", 3, "0"))   # 007
```

## `text` — characters and tokenizing

Character predicates take a one-character string: `is_digit`, `is_alpha`,
`is_alnum`, `is_space`, `is_upper`, `is_lower`. Plus `chars(s)` (list of
characters), `lines(s)`, `words(s)` (split on whitespace runs), `title(s)`
(capitalize each word), and `count(s, sub)`.

```sandy
import "text" as text
print(text.words("  a   b c "))  # ["a", "b", "c"]
print(text.title("hello there")) # Hello There
```

## `lists` — higher-order list operations

`map(f, xs)`, `filter(pred, xs)`, `reduce(f, acc, xs)`, `reverse(xs)`,
`unique(xs)`, `contains(xs, x)`, `index_of(xs, x)`, `take(xs, n)`,
`drop(xs, n)`, `first(xs)`, `last(xs)`.

```sandy
import "lists" as lists
fn even(n) { return n % 2 == 0 }
print(lists.filter(even, [1, 2, 3, 4]))   # [2, 4]
```

## `sort` — sorting

`sort(xs)`, `sort_by(xs, key)`, `sort_desc(xs)`, `is_sorted(xs)`. A stable,
non-destructive insertion sort over numbers or strings.

```sandy
import "sort" as sort
print(sort.sort([3, 1, 2]))               # [1, 2, 3]
fn length(s) { return len(s) }
print(sort.sort_by(["ccc", "a", "bb"], length))   # ["a", "bb", "ccc"]
```

## `sets` — set operations over lists

`union`, `intersection`, `difference`, `symmetric_difference`, `is_subset`,
`is_disjoint`, `contains`, `unique`. Sets are lists of unique values.

```sandy
import "sets" as sets
print(sets.union([1, 2], [2, 3]))         # [1, 2, 3]
print(sets.intersection([1, 2, 3], [2, 4])) # [2]
```

## `maps` — map helpers

`get(m, k, default)`, `items(m)` (list of `[key, value]` pairs), `from_pairs`,
`merge(a, b)`, `invert(m)`, `map_values(m, f)`, `pick(m, keys)`.

```sandy
import "maps" as maps
print(maps.get({"a": 1}, "z", 0))         # 0
print(maps.merge({"a": 1}, {"b": 2}))     # {"a": 1, "b": 2}
```

## `json` — JSON encoding and decoding

`to_json(value)` encodes a Sandy value to a JSON string; `parse(text)` decodes
JSON back into Sandy values.

```sandy
import "json" as json
text = json.to_json({"name": "Sandy", "xs": [1, 2, 3]})
print(text)                      # {"name":"Sandy","xs":[1,2,3]}
data = json.parse(text)
print(data["name"])              # Sandy
```

## `csv` — comma-separated values

`parse(text)` returns a list of rows (each a list of string fields);
`format(rows)` produces CSV text. RFC 4180-style quoting handles commas,
newlines, and quotes inside fields. Also `parse_line` and `format_row`.

```sandy
import "csv" as csv
rows = csv.parse("name,age\nAda,36")
print(rows[1][0])                # Ada
```

## `regex` — regular expressions

`test(pattern, s)`, `find(pattern, s)`, `find_all(pattern, s)`,
`groups(pattern, s)`, `replace(pattern, s, repl)`, `split(pattern, s)`. Uses the
host regex syntax (`\d`, `\w`, anchors, groups, quantifiers). `find`/`groups`
return `nil` when there is no match; `replace` supports `\1` backreferences.

```sandy
import "regex" as regex
print(regex.find_all("\\w+", "a, bb, ccc"))   # ["a", "bb", "ccc"]
print(regex.replace("\\s+", "a   b", "_"))    # a_b
```

## `random` — pseudo-random numbers

A seedable, deterministic generator: `seed(n)`, `next()` (float in `[0, 1)`),
`randint(lo, hi)` (inclusive), `boolean()`, `choice(xs)`, `shuffle(xs)` (a new
list), `sample(xs, k)` (k distinct elements).

```sandy
import "random" as random
random.seed(42)
print(random.randint(1, 6))      # a repeatable "die roll" for that seed
```

## `time` — clocks and durations

`epoch()` (wall-clock seconds), `monotonic()` (for measuring elapsed time),
`since(start)`, `sleep_ms(ms)`, and `format(seconds)` for a human-readable
duration.

```sandy
import "time" as time
print(time.format(3723))         # 1h 02m 03s
```

## `os` — paths (with filesystem builtins)

Path helpers `join(a, b)`, `basename(path)`, `dirname(path)`, `extension(path)`,
`stem(path)`. These pair with the filesystem builtins `cwd`, `exists`, `is_file`,
`is_dir`, `list_dir`, `make_dir`, `remove_file`, and `args` (Chapter 18).

```sandy
import "os" as os
print(os.basename("a/b/c.sy"))   # c.sy
print(os.extension("photo.png")) # png
```

## `http` — web requests

`get_json(url)` and `post_json(url, value)` fetch and decode JSON;
`status(response)`, `body(response)`, `ok(response)` read a raw response from the
`http_get`/`http_post` builtins. A non-2xx status or a transport failure throws.

```sandy
import "http" as http
data = http.get_json("https://api.example.com/thing")
print(data["name"])
```

## `base64` — Base64 encoding

`encode(s)` and `decode(s)` over the UTF-8 bytes of a string.

```sandy
import "base64" as base64
print(base64.encode("hello"))    # aGVsbG8=
```

## `hash` — a non-cryptographic hash

`djb2(s)` — a fast, stable integer hash for buckets and checksums. For
cryptographic digests use the global `sha256(s)` and `md5(s)` builtins.

## `assert` — assertions for tests

`eq(actual, expected, msg)`, `neq`, `is_true(cond, msg)`, `is_false`. Each
throws a descriptive message on failure, so you can write tests in Sandy itself.

```sandy
import "assert" as assert
assert.eq(2 + 2, 4, "arithmetic")
```

The next chapter documents the global built-in functions these modules build on.
