#!/usr/bin/env python3
"""Generate web/playground.html — a self-contained browser playground for
Sandy, powered by Pyodide (CPython compiled to WebAssembly).

The entire `sandy` package (its .py modules and the .sy standard library) is
embedded into the page, so the playground always runs the exact code in this
repository. Regenerate after changing the package:

    python web/build_playground.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "sandy")

EXAMPLES = {
    "Hello": '# Welcome to Sandy!\nprint("Hello, Sandy!")\n\n'
             'name = "world"\nprint("Hello, " + name + "!")',
    "Fibonacci": 'fn fib(n) {\n    if n < 2 { return n }\n'
                 '    return fib(n - 1) + fib(n - 2)\n}\n\n'
                 'for i in range(10) {\n    print(fib(i))\n}',
    "Structs": 'struct Point { x, y }\n\n'
               'fn dist2(a, b) {\n    dx = a.x - b.x\n    dy = a.y - b.y\n'
               '    return dx * dx + dy * dy\n}\n\n'
               'p = Point(0, 0)\nq = Point(3, 4)\n'
               'print("distance squared = {dist2(p, q)}")',
    "Standard library": 'import "math" as math\nimport "lists" as lists\n\n'
                        'print("gcd(48, 36) = {math.gcd(48, 36)}")\n'
                        'print("is_prime(97) = {math.is_prime(97)}")\n\n'
                        'fn square(n) { return n * n }\n'
                        'print(lists.map(square, [1, 2, 3, 4]))',
    "Types & errors": 'fn safe_div(a: int, b: int) -> float {\n'
                      '    if b == 0 { throw "division by zero" }\n'
                      '    return a / b\n}\n\n'
                      'try {\n    print(safe_div(10, 2))\n    print(safe_div(1, 0))\n'
                      '} catch e {\n    print("caught: " + e)\n}',
}


def collect_sources():
    files = {}
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".py"):
            with open(os.path.join(PKG, name), encoding="utf-8") as f:
                files["/sandy/" + name] = f.read()
    stdlib = os.path.join(PKG, "stdlib")
    for name in sorted(os.listdir(stdlib)):
        if name.endswith(".sy"):
            with open(os.path.join(stdlib, name), encoding="utf-8") as f:
                files["/sandy/stdlib/" + name] = f.read()
    return files


def render():
    """Return the playground HTML with the current package embedded."""
    html = PAGE.replace("/*__SOURCES__*/",
                        json.dumps(collect_sources(), ensure_ascii=False))
    return html.replace("/*__EXAMPLES__*/",
                        json.dumps(EXAMPLES, ensure_ascii=False))


def build():
    html = render()
    out = os.path.join(HERE, "playground.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out} ({len(html) // 1024} KB, "
          f"{len(collect_sources())} embedded files)")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sandy Playground</title>
<style>
  :root {
    --bg: #0f1720; --panel: #16212e; --edge: #24313f; --ink: #e6edf3;
    --muted: #8aa0b3; --accent: #ffb454; --accent2: #4cc38a; --err: #ff6b6b;
    --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    height: 100vh; display: flex; flex-direction: column;
  }
  header {
    display: flex; align-items: center; gap: 14px; padding: 12px 18px;
    border-bottom: 1px solid var(--edge); background: var(--panel);
  }
  header h1 { font-size: 18px; margin: 0; font-weight: 650; letter-spacing: .2px; }
  header .beach { font-size: 20px; }
  header .sub { color: var(--muted); font-size: 13px; }
  header .spacer { flex: 1; }
  select, button {
    font: inherit; color: var(--ink); background: #1c2836;
    border: 1px solid var(--edge); border-radius: 8px; padding: 7px 12px;
    cursor: pointer;
  }
  button.run {
    background: var(--accent); color: #23150a; border-color: var(--accent);
    font-weight: 650;
  }
  button.run:disabled { opacity: .55; cursor: default; }
  main { flex: 1; display: grid; grid-template-columns: 1fr 1fr; min-height: 0; }
  @media (max-width: 820px) { main { grid-template-columns: 1fr; } }
  .pane { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
  .pane + .pane { border-left: 1px solid var(--edge); }
  .label {
    padding: 8px 16px; color: var(--muted); font-size: 12px;
    text-transform: uppercase; letter-spacing: .08em; border-bottom: 1px solid var(--edge);
  }
  textarea {
    flex: 1; resize: none; border: 0; outline: none; padding: 16px;
    background: transparent; color: var(--ink); font-family: var(--mono);
    font-size: 14px; line-height: 1.55; tab-size: 4;
  }
  pre#out {
    flex: 1; margin: 0; padding: 16px; overflow: auto; white-space: pre-wrap;
    font-family: var(--mono); font-size: 14px; line-height: 1.55; color: var(--ink);
  }
  pre#out .err { color: var(--err); }
  pre#out .ok { color: var(--accent2); }
  .status { padding: 6px 16px; color: var(--muted); font-size: 12px;
            border-top: 1px solid var(--edge); }
</style>
</head>
<body>
<header>
  <span class="beach">&#127958;</span>
  <h1>Sandy Playground</h1>
  <span class="sub">runs entirely in your browser</span>
  <span class="spacer"></span>
  <select id="examples" title="Load an example"></select>
  <button class="run" id="run" disabled>Run &#9654;</button>
</header>
<main>
  <section class="pane">
    <div class="label">program.sy</div>
    <textarea id="code" spellcheck="false" autocomplete="off"></textarea>
  </section>
  <section class="pane">
    <div class="label">output</div>
    <pre id="out"></pre>
    <div class="status" id="status">Loading Python runtime&hellip;</div>
  </section>
</main>

<script src="https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"></script>
<script>
const SOURCES = /*__SOURCES__*/;
const EXAMPLES = /*__EXAMPLES__*/;

const codeEl = document.getElementById("code");
const outEl = document.getElementById("out");
const statusEl = document.getElementById("status");
const runBtn = document.getElementById("run");
const exSel = document.getElementById("examples");

for (const name of Object.keys(EXAMPLES)) {
  const opt = document.createElement("option");
  opt.value = name; opt.textContent = name; exSel.appendChild(opt);
}
exSel.onchange = () => { codeEl.value = EXAMPLES[exSel.value]; };
codeEl.value = EXAMPLES[Object.keys(EXAMPLES)[0]];

// Insert a tab (4 spaces) instead of leaving the textarea.
codeEl.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const s = codeEl.selectionStart, en = codeEl.selectionEnd;
    codeEl.value = codeEl.value.slice(0, s) + "    " + codeEl.value.slice(en);
    codeEl.selectionStart = codeEl.selectionEnd = s + 4;
  }
});

let pyodide = null;

async function boot() {
  pyodide = await loadPyodide();
  for (const [path, content] of Object.entries(SOURCES)) {
    const dir = path.slice(0, path.lastIndexOf("/"));
    pyodide.FS.mkdirTree(dir);
    pyodide.FS.writeFile(path, content, { encoding: "utf8" });
  }
  pyodide.runPython(`
import sys, io
sys.path.insert(0, "/")
from sandy.runtime import run_source, type_check_source
from sandy.interpreter import Interpreter
from sandy.errors import SandyError

def run_sandy(code):
    errs = type_check_source(code)
    if errs:
        out = ["✗ " + str(len(errs)) + " type error(s):"]
        for msg, line in sorted(errs, key=lambda e: (e[1] or 0)):
            where = " (line " + str(line) + ")" if line else ""
            out.append("  TypeError" + where + ": " + msg)
        return {"text": "\\n".join(out), "error": True}
    buf = io.StringIO()
    try:
        run_source(code, Interpreter(out=buf))
    except SandyError as e:
        return {"text": buf.getvalue() + e.format("Error"), "error": True}
    except RecursionError:
        return {"text": buf.getvalue() + "RuntimeError: too much recursion", "error": True}
    return {"text": buf.getvalue(), "error": False}
`);
  statusEl.textContent = "Ready.";
  runBtn.disabled = false;
  runBtn.onclick = run;
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run();
  });
}

function run() {
  if (!pyodide) return;
  runBtn.disabled = true;
  statusEl.textContent = "Running…";
  outEl.textContent = "";
  // Let the UI paint "Running…" before the (synchronous) run.
  setTimeout(() => {
    let result;
    const t0 = performance.now();
    try {
      const fn = pyodide.globals.get("run_sandy");
      result = fn(codeEl.value).toJs({ dict_converter: Object.fromEntries });
      fn.destroy();
    } catch (err) {
      result = { text: String(err), error: true };
    }
    const ms = (performance.now() - t0).toFixed(0);
    outEl.textContent = result.text || (result.error ? "" : "(no output)");
    outEl.className = "";
    if (result.error) {
      const span = document.createElement("span");
      span.className = "err"; span.textContent = outEl.textContent;
      outEl.textContent = ""; outEl.appendChild(span);
    }
    statusEl.textContent = "Done in " + ms + " ms.";
    runBtn.disabled = false;
  }, 20);
}

boot().catch((e) => { statusEl.textContent = "Failed to load: " + e; });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
