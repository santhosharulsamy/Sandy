# Sandy web playground

[`playground.html`](playground.html) is a self-contained, browser-based
playground for Sandy. It runs the **real** Sandy implementation in your
browser via [Pyodide](https://pyodide.org) (CPython compiled to WebAssembly)
— no server, no backend. Type a program, press **Run** (or Ctrl/Cmd+Enter),
and it lexes, type-checks, and executes entirely client-side.

## How it works

The entire `sandy` package (its `.py` modules and the `.sy` standard library)
is embedded into the HTML at build time, so the playground always runs the
exact code in this repository. On load, Pyodide writes those files into its
virtual filesystem and imports the package.

Pyodide itself is loaded from a CDN, so the page needs internet access the
first time it runs.

## Regenerating

After changing anything in `sandy/`, regenerate the page:

```bash
python web/build_playground.py
```

A test (`tests/test_playground.py`) fails if the committed page is stale, so
CI will remind you.

## Hosting

`playground.html` is a single static file — open it locally, or publish it
anywhere that serves static files (e.g. GitHub Pages):

```bash
# serve locally
python -m http.server -d web 8000
# then open http://localhost:8000/playground.html
```
