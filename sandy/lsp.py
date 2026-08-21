"""A minimal Language Server for Sandy (`sandy lsp`).

Speaks LSP over stdio (JSON-RPC with Content-Length framing) and reuses the
existing lexer, parser, type checker, and formatter to provide:

  * diagnostics (syntax + type errors) on open/change
  * whole-document formatting
  * completion (keywords, builtins, and the file's own definitions)
  * a document-symbol outline (functions, structs, top-level variables)

The analysis is exposed as pure functions (compute_diagnostics, completions,
document_symbols) so it can be unit-tested without the stdio loop.
"""

import json
import os
import sys

from . import nodes as N
from .errors import SandyError, LexError, ParseError
from .lexer import tokenize
from .parser import parse
from .typecheck import TypeChecker
from .formatter import format_source
from .builtins import BUILTIN_NAMES

_SEVERITY_ERROR = 1

KEYWORDS = [
    "fn", "return", "if", "elif", "else", "while", "for", "in", "break",
    "continue", "try", "catch", "throw", "struct", "import", "true", "false",
    "nil", "and", "or", "not",
]

# LSP SymbolKind / CompletionItemKind codes we use.
_KIND_FUNCTION = 12
_KIND_STRUCT = 23
_KIND_VARIABLE = 13
_KIND_KEYWORD = 14
_KIND_FUNCTION_C = 3   # CompletionItemKind.Function


# ---- pure analysis (testable without the server) ----

def _point_range(lines, line, col):
    idx = max(0, line - 1)
    start = max(0, (col or 1) - 1)
    end = len(lines[idx]) if idx < len(lines) else start + 1
    end = max(end, start + 1)
    return {"start": {"line": idx, "character": start},
            "end": {"line": idx, "character": end}}


def _line_range(lines, line):
    idx = max(0, line - 1)
    if idx < len(lines):
        s = lines[idx]
        start = len(s) - len(s.lstrip())
        return {"start": {"line": idx, "character": start},
                "end": {"line": idx, "character": max(start + 1, len(s))}}
    return {"start": {"line": idx, "character": 0},
            "end": {"line": idx, "character": 1}}


def compute_diagnostics(text, base_dir=None):
    """Return a list of LSP Diagnostic dicts for a Sandy source string."""
    lines = text.split("\n")
    try:
        program = parse(tokenize(text))
    except (LexError, ParseError) as e:
        rng = _point_range(lines, e.line or 1, getattr(e, "col", None))
        return [{"range": rng, "severity": _SEVERITY_ERROR,
                 "source": "sandy", "message": e.message}]
    except SandyError as e:
        return [{"range": _line_range(lines, e.line or 1),
                 "severity": _SEVERITY_ERROR, "source": "sandy",
                 "message": e.message}]
    diags = []
    try:
        errors = TypeChecker(base_dir=base_dir).check(program)
    except SandyError:
        errors = []
    for message, line in errors:
        diags.append({"range": _line_range(lines, line or 1),
                      "severity": _SEVERITY_ERROR, "source": "sandy-types",
                      "message": message})
    return diags


def _top_level_names(program):
    """(name, kind) for every top-level definition in a program."""
    out = []
    for stmt in program.statements:
        if isinstance(stmt, N.FuncDef):
            out.append((stmt.name, _KIND_FUNCTION))
        elif isinstance(stmt, N.StructDef):
            out.append((stmt.name, _KIND_STRUCT))
        elif isinstance(stmt, N.Assign) and isinstance(stmt.target, N.Identifier):
            out.append((stmt.target.name, _KIND_VARIABLE))
    return out


def completions(text):
    """Completion items: keywords, builtins, and the file's own top-level
    definitions."""
    items = [{"label": kw, "kind": _KIND_KEYWORD} for kw in KEYWORDS]
    items += [{"label": b, "kind": _KIND_FUNCTION_C} for b in sorted(BUILTIN_NAMES)]
    try:
        program = parse(tokenize(text))
    except SandyError:
        return items
    seen = set()
    for name, kind in _top_level_names(program):
        if name not in seen:
            seen.add(name)
            items.append({"label": name, "kind": kind})
    return items


def document_symbols(text):
    """A flat outline of top-level functions, structs, and variables."""
    try:
        program = parse(tokenize(text))
    except SandyError:
        return []
    syms = []
    for stmt in program.statements:
        if isinstance(stmt, N.FuncDef):
            end = stmt.body.end_line or stmt.line
            syms.append(_symbol(stmt.name, _KIND_FUNCTION, stmt.line, end))
        elif isinstance(stmt, N.StructDef):
            end = stmt.end_line or stmt.line
            syms.append(_symbol(stmt.name, _KIND_STRUCT, stmt.line, end))
        elif isinstance(stmt, N.Assign) and isinstance(stmt.target, N.Identifier):
            syms.append(_symbol(stmt.target.name, _KIND_VARIABLE,
                                stmt.line, stmt.line))
    return syms


def _symbol(name, kind, start_line, end_line):
    rng = {"start": {"line": start_line - 1, "character": 0},
           "end": {"line": end_line - 1, "character": 0}}
    return {"name": name, "kind": kind, "range": rng, "selectionRange": rng}


def _uri_to_path(uri):
    if uri.startswith("file://"):
        from urllib.parse import unquote
        return unquote(uri[len("file://"):])
    return uri


# ---- stdio JSON-RPC server ----

class Server:
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.docs = {}       # uri -> text
        self.running = True

    def run(self):
        while self.running:
            msg = self._read()
            if msg is None:
                break
            self._dispatch(msg)

    def _read(self):
        headers = {}
        while True:
            line = self.stdin.readline()
            if not line:
                return None
            line = line.decode("ascii").strip()
            if line == "":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", 0))
        body = self.stdin.read(length)
        return json.loads(body.decode("utf-8"))

    def _write(self, obj):
        data = json.dumps(obj).encode("utf-8")
        self.stdout.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
        self.stdout.write(data)
        self.stdout.flush()

    def _respond(self, id_, result):
        self._write({"jsonrpc": "2.0", "id": id_, "result": result})

    def _notify(self, method, params):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _dispatch(self, msg):
        method = msg.get("method")
        id_ = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            self._respond(id_, {"capabilities": {
                "textDocumentSync": 1,   # full document sync
                "documentFormattingProvider": True,
                "documentSymbolProvider": True,
                "completionProvider": {"triggerCharacters": ["."]},
            }, "serverInfo": {"name": "sandy-lsp"}})
        elif method == "shutdown":
            self._respond(id_, None)
        elif method == "exit":
            self.running = False
        elif method == "textDocument/didOpen":
            doc = params["textDocument"]
            self.docs[doc["uri"]] = doc["text"]
            self._publish(doc["uri"])
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            self.docs[uri] = params["contentChanges"][-1]["text"]
            self._publish(uri)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            self.docs.pop(uri, None)
            self._notify("textDocument/publishDiagnostics",
                         {"uri": uri, "diagnostics": []})
        elif method == "textDocument/formatting":
            self._respond(id_, self._format(params["textDocument"]["uri"]))
        elif method == "textDocument/completion":
            self._respond(id_, completions(
                self.docs.get(params["textDocument"]["uri"], "")))
        elif method == "textDocument/documentSymbol":
            self._respond(id_, document_symbols(
                self.docs.get(params["textDocument"]["uri"], "")))
        elif id_ is not None:
            self._respond(id_, None)   # unknown request: don't hang the client

    def _publish(self, uri):
        base_dir = os.path.dirname(_uri_to_path(uri)) or None
        diags = compute_diagnostics(self.docs.get(uri, ""), base_dir=base_dir)
        self._notify("textDocument/publishDiagnostics",
                     {"uri": uri, "diagnostics": diags})

    def _format(self, uri):
        text = self.docs.get(uri, "")
        try:
            formatted = format_source(text)
        except SandyError:
            return []
        if formatted == text:
            return []
        lines = text.split("\n")
        end = {"line": len(lines) - 1, "character": len(lines[-1])}
        return [{"range": {"start": {"line": 0, "character": 0}, "end": end},
                 "newText": formatted}]


def main():
    Server().run()
    return 0
