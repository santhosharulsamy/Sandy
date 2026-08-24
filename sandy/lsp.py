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
from .tokens import TokenType
from .typecheck import TypeChecker
from .formatter import format_source
from .builtins import BUILTIN_NAMES

# One-line signatures shown on hover for builtins.
BUILTIN_SIGS = {
    "print": "print(...) — print values, then a newline",
    "input": "input(prompt?) -> string",
    "len": "len(x) -> int — length of a string, list, or map",
    "type": "type(x) -> string — the value's type name",
    "str": "str(x) -> string", "int": "int(x) -> int",
    "float": "float(x) -> float", "bool": "bool(x) -> bool",
    "range": "range(n) / range(a, b) / range(a, b, step) -> list",
    "abs": "abs(x) -> number", "min": "min(list) -> value",
    "max": "max(list) -> value", "sum": "sum(list) -> number",
    "round": "round(x, ndigits?) -> number", "pow": "pow(a, b) -> number",
    "sqrt": "sqrt(x) -> float", "floor": "floor(x) -> int",
    "ceil": "ceil(x) -> int",
    "ord": "ord(char) -> int — Unicode code point of a 1-char string",
    "chr": "chr(code) -> string — the 1-char string for a code point",
    "sin": "sin(x) -> float", "cos": "cos(x) -> float",
    "tan": "tan(x) -> float", "exp": "exp(x) -> float",
    "log": "log(x, base?) -> float — natural log, or log base `base`",
    "log10": "log10(x) -> float",
    "sha256": "sha256(s) -> string — hex SHA-256 digest of the UTF-8 text",
    "md5": "md5(s) -> string — hex MD5 digest of the UTF-8 text",
    "base64_encode": "base64_encode(s) -> string",
    "base64_decode": "base64_decode(s) -> string",
    "push": "push(list, x) -> list", "pop": "pop(list) -> value",
    "keys": "keys(map) -> list", "values": "values(map) -> list",
    "has": "has(container, x) -> bool",
    "upper": "upper(s) -> string", "lower": "lower(s) -> string",
    "trim": "trim(s) -> string", "split": "split(s, sep?) -> list",
    "join": "join(list, sep) -> string",
    "read_file": "read_file(path) -> string",
    "read_lines": "read_lines(path) -> list",
    "write_file": "write_file(path, text)",
    "append_file": "append_file(path, text)",
    "now": "now() -> float — wall-clock seconds since the epoch",
    "clock": "clock() -> float — monotonic seconds, for measuring elapsed time",
    "sleep": "sleep(seconds) — pause for the given number of seconds",
    "env": "env(name, default?) -> string — an environment variable, or default",
    "exit": "exit(code?) — end the program with an exit code (default 0)",
    "args": "args() -> list — the program's command-line arguments",
    "cwd": "cwd() -> string — the current working directory",
    "exists": "exists(path) -> bool",
    "is_file": "is_file(path) -> bool",
    "is_dir": "is_dir(path) -> bool",
    "list_dir": "list_dir(path) -> list — sorted directory entries",
    "make_dir": "make_dir(path) — create a directory (and parents)",
    "remove_file": "remove_file(path) — delete a file",
    "http_get": "http_get(url, timeout?) -> map — {status, ok, body}",
    "http_post": "http_post(url, body, content_type?, timeout?) -> map — "
                 "{status, ok, body}",
    "re_test": "re_test(pattern, s) -> bool — does the pattern match anywhere",
    "re_find": "re_find(pattern, s) -> string — first match, or nil",
    "re_find_all": "re_find_all(pattern, s) -> list — all matches",
    "re_groups": "re_groups(pattern, s) -> list — capture groups of the first "
                 "match, or nil",
    "re_replace": "re_replace(pattern, s, repl) -> string (\\1 backrefs)",
    "re_split": "re_split(pattern, s) -> list — split s on the pattern",
    "spawn": "spawn(fn, args...) -> task — run fn concurrently",
    "wait": "wait(task) -> value — block for a task and get its result",
    "channel": "channel(capacity?) -> channel — capacity 0 is unbuffered",
    "send": "send(channel, value) — send a value (may block)",
    "recv": "recv(channel) -> value — receive a value (blocks; nil when "
            "closed and drained)",
    "close": "close(channel) — close a channel",
}

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


# ---- hover and go-to-definition (position-based, via token positions) ----

def _safe_parse(text):
    try:
        return parse(tokenize(text))
    except SandyError:
        return None


def _ident_at(text, line, character):
    """The identifier token at a 0-based (line, character), or None."""
    try:
        toks = tokenize(text)
    except SandyError:
        return None
    tl, tc = line + 1, character + 1
    for t in toks:
        if t.type == TokenType.IDENT and t.line == tl:
            if t.col <= tc <= t.col + len(t.value):
                return t
    return None


def _func_sig(fn):
    params = [f"{p}: {a}" if a else p
              for p, a in zip(fn.params, fn.param_types)]
    sig = f"fn {fn.name}(" + ", ".join(params) + ")"
    return sig + (f" -> {fn.ret_type}" if fn.ret_type else "")


def _struct_sig(sd):
    fields = [f"{f}: {a}" if a else f
              for f, a in zip(sd.fields, sd.field_types)]
    return f"struct {sd.name} {{ " + ", ".join(fields) + " }"


def _walk_blocks(block):
    """Yield every Block nested inside `block` (including itself)."""
    yield block
    for stmt in block.statements:
        t = type(stmt)
        if t is N.FuncDef:
            yield from _walk_blocks(stmt.body)
        elif t is N.If:
            for _, b in stmt.branches:
                yield from _walk_blocks(b)
            if stmt.else_block is not None:
                yield from _walk_blocks(stmt.else_block)
        elif t in (N.While, N.For):
            yield from _walk_blocks(stmt.body)
        elif t is N.Try:
            yield from _walk_blocks(stmt.body)
            yield from _walk_blocks(stmt.handler)


def _definitions(program):
    """name -> (kind, line, detail) for functions, structs, and variables."""
    defs = {}
    for block in _walk_blocks(program):
        for stmt in block.statements:
            t = type(stmt)
            if t is N.FuncDef:
                defs.setdefault(stmt.name, ("function", stmt.line, _func_sig(stmt)))
            elif t is N.StructDef:
                defs.setdefault(stmt.name, ("struct", stmt.line, _struct_sig(stmt)))
            elif t is N.Assign and isinstance(stmt.target, N.Identifier):
                defs.setdefault(stmt.target.name,
                                ("variable", stmt.line, stmt.target.name))
    return defs


def _enclosing_function(program, line):
    """The innermost FuncDef whose body spans a 1-based line, or None."""
    best = None
    for block in _walk_blocks(program):
        for stmt in block.statements:
            if type(stmt) is N.FuncDef:
                end = stmt.body.end_line or stmt.line
                if stmt.line <= line <= end:
                    if best is None or stmt.line >= best.line:
                        best = stmt
    return best


def hover_info(text, line, character):
    """A short signature/description for the identifier at a position."""
    tok = _ident_at(text, line, character)
    if tok is None:
        return None
    name = tok.value
    program = _safe_parse(text)
    if program is not None:
        fn = _enclosing_function(program, line + 1)
        if fn is not None:
            for p, a in zip(fn.params, fn.param_types):
                if p == name:
                    return f"(parameter) {name}" + (f": {a}" if a else "")
        detail = _definitions(program).get(name)
        if detail is not None:
            kind, _, text_detail = detail
            return text_detail if kind != "variable" else f"(variable) {name}"
    return BUILTIN_SIGS.get(name)


def definition_line(text, line, character):
    """The 1-based line where the identifier at a position is defined, or None."""
    tok = _ident_at(text, line, character)
    if tok is None:
        return None
    program = _safe_parse(text)
    if program is None:
        return None
    name = tok.value
    fn = _enclosing_function(program, line + 1)
    if fn is not None and name in fn.params:
        return fn.line
    detail = _definitions(program).get(name)
    return detail[1] if detail is not None else None


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
                "hoverProvider": True,
                "definitionProvider": True,
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
        elif method == "textDocument/hover":
            self._respond(id_, self._hover(params))
        elif method == "textDocument/definition":
            self._respond(id_, self._definition(params))
        elif id_ is not None:
            self._respond(id_, None)   # unknown request: don't hang the client

    def _hover(self, params):
        text = self.docs.get(params["textDocument"]["uri"], "")
        pos = params["position"]
        info = hover_info(text, pos["line"], pos["character"])
        if info is None:
            return None
        return {"contents": {"kind": "markdown",
                             "value": "```sandy\n" + info + "\n```"}}

    def _definition(self, params):
        uri = params["textDocument"]["uri"]
        pos = params["position"]
        line = definition_line(self.docs.get(uri, ""), pos["line"],
                               pos["character"])
        if line is None:
            return None
        rng = {"start": {"line": line - 1, "character": 0},
               "end": {"line": line - 1, "character": 0}}
        return {"uri": uri, "range": rng}

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
