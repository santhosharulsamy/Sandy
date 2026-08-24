"""Canonical source formatter for Sandy (`sandy fmt`).

Re-emits a program in a single canonical style by pretty-printing the AST.
Comments and blank lines between statements are preserved by consulting a
line -> comment map from the lexer and the `end_line` recorded on blocks.
"""

from . import nodes as N
from .lexer import tokenize, scan_comments
from .parser import parse

INDENT = "    "

_ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}


def _prec(node):
    """Expression precedence (higher binds tighter), matching the parser."""
    t = type(node)
    if t is N.LogicalOp:
        return 1 if node.op == "or" else 2
    if t is N.UnaryOp:
        # `not` sits below comparison; arithmetic `-` sits between `*` and `**`
        # (so `-x ** 2` parses as `-(x ** 2)`), matching the parser.
        return 3 if node.op == "not" else 7
    if t is N.BinaryOp:
        op = node.op
        if op in ("==", "!=", "<", ">", "<=", ">="):
            return 4
        if op in ("+", "-"):
            return 5
        if op in ("*", "/", "%"):
            return 6
        return 8  # ** (right-associative, tighter than unary minus)
    if t in (N.Call, N.Index, N.Attribute):
        return 9
    return 10


def format_source(source):
    """Return the canonically formatted form of Sandy source text."""
    program = parse(tokenize(source))
    return Formatter(source).format(program)


class Formatter:
    def __init__(self, source):
        self.comments = scan_comments(source)
        self.blanks = {i + 1 for i, line in enumerate(source.splitlines())
                       if line.strip() == ""}
        self.total = len(source.splitlines())
        self.out = []
        self.cursor = 1   # next unconsumed source line

    def format(self, program):
        self._emit_body(program, 0)
        self._emit_gap(self.total + 1, 0)
        return "\n".join(self.out).rstrip("\n") + "\n"

    # -- comment / blank preservation --
    def _blank(self):
        if self.out and self.out[-1] != "" \
                and not self.out[-1].rstrip().endswith("{"):
            self.out.append("")

    def _emit_gap(self, target_line, indent):
        """Emit standalone comments and collapsed blank lines for the source
        lines in [cursor, target_line)."""
        pad = INDENT * indent
        pending_blank = False
        for line in range(self.cursor, target_line):
            if line in self.comments:
                if pending_blank:
                    self._blank()
                self.out.append(pad + self.comments[line])
                pending_blank = False
            elif line in self.blanks:
                pending_blank = True
        if pending_blank:
            self._blank()
        if target_line > self.cursor:
            self.cursor = target_line

    def _header(self, text, indent, line):
        s = INDENT * indent + text
        if line in self.comments:      # trailing comment on the header line
            s += "  " + self.comments[line]
        self.out.append(s)
        self.cursor = line + 1

    # -- statements --
    def _emit_body(self, block, indent):
        for stmt in block.statements:
            self._emit_gap(stmt.line, indent)
            self._emit_stmt(stmt, indent)

    def _emit_stmt(self, node, indent):
        t = type(node)
        handler = self._STMT.get(t)
        if handler is not None:
            handler(self, node, indent)
        else:
            self._line(self._simple_text(node), indent, node.line)

    def _line(self, text, indent, line):
        s = INDENT * indent + text
        if line in self.comments:
            s += "  " + self.comments[line]
        self.out.append(s)
        self.cursor = line + 1

    def _simple_text(self, node):
        t = type(node)
        if t is N.ExprStmt:
            return self._expr(node.expr, 0)
        if t is N.Assign:
            return self._assign_text(node)
        if t is N.Return:
            return "return" if node.value is None else "return " + self._expr(node.value, 0)
        if t is N.Break:
            return "break"
        if t is N.Continue:
            return "continue"
        if t is N.Throw:
            return "throw " + self._expr(node.value, 0)
        if t is N.Import:
            return f'import "{node.path}" as {node.alias}'
        return "?"

    def _assign_text(self, node):
        target = self._expr(node.target, 9)
        if node.annotation is not None:
            return f"{target}: {node.annotation} = {self._expr(node.value, 0)}"
        return f"{target} {node.op} {self._expr(node.value, 0)}"

    def _emit_if(self, node, indent):
        for i, (cond, block) in enumerate(node.branches):
            head = ("if " if i == 0 else "} elif ") + self._expr(cond, 0) + " {"
            if i == 0:
                self._header(head, indent, node.line)
            else:
                self.out.append(INDENT * indent + head)
            self._emit_body(block, indent + 1)
            self._emit_gap(block.end_line, indent + 1)
            self.cursor = block.end_line + 1
        if node.else_block is not None:
            self.out.append(INDENT * indent + "} else {")
            self._emit_body(node.else_block, indent + 1)
            self._emit_gap(node.else_block.end_line, indent + 1)
            self.out.append(INDENT * indent + "}")
            self.cursor = node.else_block.end_line + 1
        else:
            self.out.append(INDENT * indent + "}")

    def _emit_braced(self, header, block, indent, node_line):
        self._header(header, indent, node_line)
        self._emit_body(block, indent + 1)
        self._emit_gap(block.end_line, indent + 1)
        self.out.append(INDENT * indent + "}")
        self.cursor = block.end_line + 1

    def _emit_while(self, node, indent):
        self._emit_braced("while " + self._expr(node.cond, 0) + " {",
                          node.body, indent, node.line)

    def _emit_for(self, node, indent):
        self._emit_braced(
            f"for {node.var} in " + self._expr(node.iterable, 0) + " {",
            node.body, indent, node.line)

    def _emit_funcdef(self, node, indent):
        params = []
        for name, ann in zip(node.params, node.param_types):
            params.append(f"{name}: {ann}" if ann is not None else name)
        head = f"fn {node.name}(" + ", ".join(params) + ")"
        if node.ret_type is not None:
            head += f" -> {node.ret_type}"
        self._emit_braced(head + " {", node.body, indent, node.line)

    def _emit_try(self, node, indent):
        self._header("try {", indent, node.line)
        self._emit_body(node.body, indent + 1)
        self._emit_gap(node.body.end_line, indent + 1)
        self.out.append(INDENT * indent + "} catch " + node.catch_var + " {")
        self.cursor = node.body.end_line + 1
        self._emit_body(node.handler, indent + 1)
        self._emit_gap(node.handler.end_line, indent + 1)
        self.out.append(INDENT * indent + "}")
        self.cursor = node.handler.end_line + 1

    def _emit_structdef(self, node, indent):
        self._header(f"struct {node.name} {{", indent, node.line)
        for name, ann in zip(node.fields, node.field_types):
            field = f"{name}: {ann}" if ann is not None else name
            self.out.append(INDENT * (indent + 1) + field)
        self.out.append(INDENT * indent + "}")
        if node.end_line is not None:
            self.cursor = node.end_line + 1

    # -- expressions --
    def _expr(self, node, min_prec):
        s = self._fmt(node)
        return f"({s})" if _prec(node) < min_prec else s

    def _fmt(self, node):
        t = type(node)
        if t is N.IntLit:
            return str(node.value)
        if t is N.FloatLit:
            return repr(node.value)
        if t is N.StrLit:
            return self._string(node.value)
        if t is N.BoolLit:
            return "true" if node.value else "false"
        if t is N.NilLit:
            return "nil"
        if t is N.InterpStr:
            return self._interp(node)
        if t is N.ListLit:
            return "[" + ", ".join(self._expr(i, 0) for i in node.items) + "]"
        if t is N.MapLit:
            inner = ", ".join(f"{self._expr(k, 0)}: {self._expr(v, 0)}"
                              for k, v in node.pairs)
            return "{" + inner + "}"
        if t is N.Identifier:
            return node.name
        if t is N.BinaryOp:
            if node.op == "**":
                # left operand is parsed at postfix level; right at unary level
                left = self._expr(node.left, 9)
                right = self._expr(node.right, 7)
            else:
                p = _prec(node)
                left, right = self._expr(node.left, p), self._expr(node.right, p + 1)
            return f"{left} {node.op} {right}"
        if t is N.LogicalOp:
            p = _prec(node)
            return f"{self._expr(node.left, p)} {node.op} {self._expr(node.right, p + 1)}"
        if t is N.UnaryOp:
            if node.op == "not":
                return "not " + self._expr(node.operand, 3)
            return "-" + self._expr(node.operand, 7)
        if t is N.Call:
            args = ", ".join(self._expr(a, 0) for a in node.args)
            return f"{self._expr(node.callee, 9)}({args})"
        if t is N.Index:
            return f"{self._expr(node.target, 9)}[{self._expr(node.index, 0)}]"
        if t is N.Attribute:
            return f"{self._expr(node.target, 9)}.{node.name}"
        return "?"

    def _string(self, value):
        return '"' + _escape(value, quote_only=True) + '"'

    def _interp(self, node):
        out = ['"']
        for kind, payload in node.parts:
            if kind == "lit":
                out.append(_escape(payload, quote_only=False))
            else:
                out.append("{" + self._expr(payload, 0) + "}")
        out.append('"')
        return "".join(out)


def _escape(text, quote_only):
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif not quote_only and ch == "{":
            out.append("{{")
        elif not quote_only and ch == "}":
            out.append("}}")
        else:
            out.append(ch)
    return "".join(out)


Formatter._STMT = {
    N.If: Formatter._emit_if,
    N.While: Formatter._emit_while,
    N.For: Formatter._emit_for,
    N.FuncDef: Formatter._emit_funcdef,
    N.Try: Formatter._emit_try,
    N.StructDef: Formatter._emit_structdef,
}
