# Chapter 13 — Modules and Packages

A program larger than one file is organized into **modules**, and code shared
between projects is distributed as **packages**. Both use the same `import`.

## Importing a file

`import` runs another `.sy` file once and binds its top-level definitions —
functions, structs, and variables — as a namespaced module value:

```sandy
# geometry.sy
fn area(w, h) { return w * h }
fn perimeter(w, h) { return 2 * (w + h) }
```

```sandy
# main.sy
import "geometry" as geo

print(geo.area(3, 4))        # 12
print(geo.perimeter(3, 4))   # 14
```

Access a module's members with `module.member`. The `.sy` extension is optional
in the path (`"geometry"` finds `geometry.sy`).

## Resolution and semantics

- Paths resolve **relative to the importing file**, then against installed
  package dependencies, then against the bundled standard library.
- A module is **cached by absolute path** — imported once, even through diamond
  import graphs where several files import the same module.
- **Circular imports** are detected and reported rather than looping.
- A module runs on the **same engine** as its importer, so a callback you pass
  into a module function behaves identically on the interpreter and the VM.

A local file always shadows a package, which shadows the standard library. This
lets you override any module by dropping a file of the same name next to your
program.

## The standard library

The standard library is a set of modules, written in Sandy itself, imported by
bare name from anywhere:

```sandy
import "math" as math
import "json" as json

print(math.gcd(48, 36))                # 12
print(json.to_json({"ok": true}))      # {"ok":true}
```

Chapter 17 documents every module.

## Packages

A **project** is a directory with a manifest, `sandy.toml`:

```toml
[package]
name = "myapp"
version = "0.1.0"

[dependencies]
geometry = "^1.2.0"                     # a registry version constraint
utils    = { path = "../utils" }        # a local path dependency
webby    = { git = "https://example.com/webby.git" }  # a git dependency
```

### The commands

```bash
sandy add geometry ^1.2.0    # add a dependency (version, path, or git URL)
sandy install                # resolve dependencies, vendor them, write sandy.lock
sandy publish                # publish this project to the registry
```

`sandy install` resolves every dependency, copies it into `sandy_modules/`, and
records exactly what was chosen in `sandy.lock` so builds are reproducible.
Dependencies are then imported by bare name, just like the standard library.

### Version constraints

Registry dependencies use semantic-version constraints:

| Constraint | Matches |
| --- | --- |
| `1.2.3` | exactly that version |
| `^1.2.0` | compatible: `>= 1.2.0` and `< 2.0.0` |
| `~1.2.0` | `>= 1.2.0` and `< 1.3.0` |
| `>=1.0.0,<2.0.0` | a range (comma-separated `and`) |
| `*` | any version |

`sandy install` picks the highest published version that satisfies the
constraint.

### The registry

The registry can be a local directory or an HTTP server, selected with the
`SANDY_REGISTRY` environment variable (default `~/.sandy/registry`). Sandy
includes a reference registry server:

```bash
sandy registry serve --port 8377 --dir ./registry
export SANDY_REGISTRY=http://localhost:8377
```

Published versions are immutable. Because dependencies are ordinary Sandy code,
**typed dependencies are type-checked across the package boundary** — calling a
dependency's function with the wrong argument type is caught before your program
runs, even though it lives in another package.

The next chapter goes deep on the type system that makes that possible.
