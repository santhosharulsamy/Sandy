"""Compile a Sandy AST into bytecode CodeObjects for the VM."""

from .errors import ParseError
from . import nodes as N
from . import bytecode as B


class _Loop:
    """Tracks jump targets for break/continue while compiling a loop."""
    __slots__ = ("kind", "continue_target", "break_sites")

    def __init__(self, kind, continue_target):
        self.kind = kind                 # "while" or "for"
        self.continue_target = continue_target
        self.break_sites = []            # indices of JUMP ops to patch to end


# Arithmetic operators whose result is numeric when both operands are.
_ARITH = {"+", "-", "*", "/", "%", "**"}

# Generic op -> type-specialized (numeric) op.
_NUMERIC_FAST = {
    B.BINARY_ADD: B.BINARY_ADD_NUM,
    B.BINARY_SUB: B.BINARY_SUB_NUM,
    B.BINARY_MUL: B.BINARY_MUL_NUM,
    B.CMP_LT: B.CMP_LT_NUM,
    B.CMP_GT: B.CMP_GT_NUM,
    B.CMP_LE: B.CMP_LE_NUM,
    B.CMP_GE: B.CMP_GE_NUM,
}


class Compiler:
    def __init__(self, name="<main>", params=(), param_types=None, numeric=None):
        self.name = name
        self.params = list(params)
        self.param_types = list(param_types) if param_types is not None else [None] * len(params)
        self.numeric = numeric or set()  # names proven to hold numbers
        self.ops = []
        self.lines = []
        self.consts = []
        self.loops = []

    # -- low-level emit helpers --
    def _emit(self, op, arg, line):
        self.ops.append((op, arg))
        self.lines.append(line)
        return len(self.ops) - 1

    def _emit_jump(self, op, line):
        return self._emit(op, None, line)

    def _patch(self, index, target):
        op, _ = self.ops[index]
        self.ops[index] = (op, target)

    def _here(self):
        return len(self.ops)

    def _const(self, value):
        # Deduplicate simple, hashable constants.
        try:
            for i, c in enumerate(self.consts):
                if type(c) is type(value) and c == value:
                    return i
        except Exception:
            pass
        self.consts.append(value)
        return len(self.consts) - 1

    # -- public entry --
    def compile_program(self, block):
        self.numeric = analyze_numeric([], [], block)
        self._compile_block(block)
        self._emit(B.LOAD_CONST, self._const(None), 0)
        self._emit(B.RETURN, None, 0)
        return self._code()

    def _code(self):
        # Drop the annotation list entirely when nothing is annotated, so
        # untyped calls pay no boundary-check cost.
        pts = self.param_types if any(t is not None for t in self.param_types) else None
        return B.CodeObject(self.name, self.params, self.ops, self.consts,
                            self.lines, pts)

    def _numeric(self, node):
        """True if `node` provably evaluates to a number (so a specialized
        numeric opcode is safe)."""
        t = type(node)
        if t is N.IntLit or t is N.FloatLit:
            return True
        if t is N.Identifier:
            return node.name in self.numeric
        if t is N.BinaryOp:
            return (node.op in _ARITH
                    and self._numeric(node.left) and self._numeric(node.right))
        if t is N.UnaryOp:
            return node.op == "-" and self._numeric(node.operand)
        return False

    def _binary_opcode(self, op, left, right):
        base = B.BINARY_OPS[op]
        if self._numeric(left) and self._numeric(right):
            return _NUMERIC_FAST.get(base, base)
        return base

    def _compile_block(self, block):
        for stmt in block.statements:
            self._compile_stmt(stmt)

    # -- statements --
    def _compile_stmt(self, node):
        m = self._STMT.get(type(node))
        if m is None:
            raise ParseError(
                f"cannot compile {type(node).__name__}", getattr(node, "line", None))
        m(self, node)

    def _c_expr_stmt(self, node):
        self._compile_expr(node.expr)
        self._emit(B.POP, None, node.line)

    def _c_assign(self, node):
        target = node.target
        if isinstance(target, N.Identifier):
            if node.op == "=":
                self._compile_expr(node.value)
            else:
                self._emit(B.LOAD_NAME, target.name, node.line)
                self._compile_expr(node.value)
                self._emit(self._binary_opcode(node.op[0], target, node.value),
                           None, node.line)
            self._emit(B.STORE_NAME, target.name, node.line)
        elif isinstance(target, N.Index):
            if node.op == "=":
                self._compile_expr(target.target)
                self._compile_expr(target.index)
                self._compile_expr(node.value)
            else:
                self._compile_expr(target.target)
                self._compile_expr(target.index)
                self._emit(B.DUP_TWO, None, node.line)
                self._emit(B.INDEX_GET, None, node.line)
                self._compile_expr(node.value)
                self._emit(B.BINARY_OPS[node.op[0]], None, node.line)
            self._emit(B.INDEX_SET, None, node.line)
        else:
            raise ParseError("invalid assignment target", node.line)

    def _c_if(self, node):
        end_sites = []
        for cond, block in node.branches:
            self._compile_expr(cond)
            skip = self._emit_jump(B.JUMP_IF_FALSE, node.line)
            self._compile_block(block)
            end_sites.append(self._emit_jump(B.JUMP, node.line))
            self._patch(skip, self._here())
        if node.else_block is not None:
            self._compile_block(node.else_block)
        for s in end_sites:
            self._patch(s, self._here())

    def _c_while(self, node):
        start = self._here()
        self._compile_expr(node.cond)
        exit_jump = self._emit_jump(B.JUMP_IF_FALSE, node.line)
        loop = _Loop("while", start)
        self.loops.append(loop)
        self._compile_block(node.body)
        self.loops.pop()
        self._emit(B.JUMP, start, node.line)
        end = self._here()
        self._patch(exit_jump, end)
        for site in loop.break_sites:
            self._patch(site, end)

    def _c_for(self, node):
        self._compile_expr(node.iterable)
        self._emit(B.GET_ITER, None, node.line)
        iter_ip = self._here()
        for_iter = self._emit_jump(B.FOR_ITER, node.line)
        self._emit(B.DEFINE_NAME, node.var, node.line)
        loop = _Loop("for", iter_ip)
        self.loops.append(loop)
        self._compile_block(node.body)
        self.loops.pop()
        self._emit(B.JUMP, iter_ip, node.line)
        end = self._here()
        self._patch(for_iter, end)
        for site in loop.break_sites:
            self._patch(site, end)

    def _c_funcdef(self, node):
        code = _compile_function(node)
        self._emit(B.MAKE_FUNCTION, self._const(code), node.line)
        self._emit(B.DEFINE_NAME, node.name, node.line)

    def _c_return(self, node):
        if node.value is None:
            self._emit(B.LOAD_CONST, self._const(None), node.line)
        else:
            self._compile_expr(node.value)
        self._emit(B.RETURN, None, node.line)

    def _c_break(self, node):
        if not self.loops:
            raise ParseError("'break' outside a loop", node.line)
        loop = self.loops[-1]
        if loop.kind == "for":
            self._emit(B.POP, None, node.line)  # discard the iterator
        loop.break_sites.append(self._emit_jump(B.JUMP, node.line))

    def _c_continue(self, node):
        if not self.loops:
            raise ParseError("'continue' outside a loop", node.line)
        self._emit(B.JUMP, self.loops[-1].continue_target, node.line)

    # -- expressions --
    def _compile_expr(self, node):
        m = self._EXPR.get(type(node))
        if m is None:
            raise ParseError(
                f"cannot compile {type(node).__name__}", getattr(node, "line", None))
        m(self, node)

    def _c_const(self, node):
        self._emit(B.LOAD_CONST, self._const(node.value), node.line)

    def _c_nil(self, node):
        self._emit(B.LOAD_CONST, self._const(None), node.line)

    def _c_interp(self, node):
        for kind, payload in node.parts:
            if kind == "lit":
                self._emit(B.LOAD_CONST, self._const(payload), node.line)
            else:
                self._compile_expr(payload)
                self._emit(B.STR_COERCE, None, node.line)
        self._emit(B.BUILD_INTERP, len(node.parts), node.line)

    def _c_list(self, node):
        for item in node.items:
            self._compile_expr(item)
        self._emit(B.BUILD_LIST, len(node.items), node.line)

    def _c_map(self, node):
        for key, value in node.pairs:
            self._compile_expr(key)
            self._compile_expr(value)
        self._emit(B.BUILD_MAP, len(node.pairs), node.line)

    def _c_identifier(self, node):
        self._emit(B.LOAD_NAME, node.name, node.line)

    def _c_binary(self, node):
        self._compile_expr(node.left)
        self._compile_expr(node.right)
        self._emit(self._binary_opcode(node.op, node.left, node.right),
                   None, node.line)

    def _c_unary(self, node):
        self._compile_expr(node.operand)
        self._emit(B.UNARY_NOT if node.op == "not" else B.UNARY_NEG, None, node.line)

    def _c_logical(self, node):
        self._compile_expr(node.left)
        if node.op == "and":
            jump = self._emit_jump(B.JUMP_IF_FALSE_OR_POP, node.line)
        else:
            jump = self._emit_jump(B.JUMP_IF_TRUE_OR_POP, node.line)
        self._compile_expr(node.right)
        self._patch(jump, self._here())

    def _c_call(self, node):
        self._compile_expr(node.callee)
        for arg in node.args:
            self._compile_expr(arg)
        self._emit(B.CALL, len(node.args), node.line)

    def _c_index(self, node):
        self._compile_expr(node.target)
        self._compile_expr(node.index)
        self._emit(B.INDEX_GET, None, node.line)

    def _c_attribute(self, node):
        self._compile_expr(node.target)
        self._emit(B.GET_ATTR, node.name, node.line)


def _compile_function(node):
    numeric = analyze_numeric(node.params, node.param_types, node.body)
    c = Compiler(node.name, node.params, node.param_types, numeric)
    c._compile_block(node.body)
    # implicit `return nil` if control falls off the end
    c._emit(B.LOAD_CONST, c._const(None), node.line)
    c._emit(B.RETURN, None, node.line)
    return c._code()


# ---- numeric-locals analysis (sound across loops via a fixpoint) ----

def _numeric_under(node, names):
    t = type(node)
    if t is N.IntLit or t is N.FloatLit:
        return True
    if t is N.Identifier:
        return node.name in names
    if t is N.BinaryOp:
        return (node.op in _ARITH
                and _numeric_under(node.left, names)
                and _numeric_under(node.right, names))
    if t is N.UnaryOp:
        return node.op == "-" and _numeric_under(node.operand, names)
    return False


def _collect_assigns(block, assigns, forvars):
    """Gather identifier assignments and for-loop variables in a body,
    without descending into nested function definitions (separate scope)."""
    for stmt in block.statements:
        t = type(stmt)
        if t is N.Assign:
            if isinstance(stmt.target, N.Identifier):
                assigns.append(stmt)
        elif t is N.If:
            for _, b in stmt.branches:
                _collect_assigns(b, assigns, forvars)
            if stmt.else_block is not None:
                _collect_assigns(stmt.else_block, assigns, forvars)
        elif t is N.While:
            _collect_assigns(stmt.body, assigns, forvars)
        elif t is N.For:
            forvars.add(stmt.var)
            _collect_assigns(stmt.body, assigns, forvars)


def analyze_numeric(params, param_types, body):
    """Return the set of variable names that provably hold numbers at every
    point in the scope. Params annotated int/float are numeric (their type is
    enforced at the call boundary); a local is numeric only if *every*
    assignment to it has a provably-numeric right-hand side. Computed as a
    fixpoint so the result is valid across loop back-edges.
    """
    assigns = []
    forvars = set()
    _collect_assigns(body, assigns, forvars)
    ptypes = param_types if param_types else [None] * len(params)
    numeric_params = {p for p, ty in zip(params, ptypes) if ty in ("int", "float")}
    assigned = {a.target.name for a in assigns}
    names = (numeric_params | assigned) - forvars
    changed = True
    while changed:
        changed = False
        for a in assigns:
            name = a.target.name
            if name in names and not _numeric_under(a.value, names):
                names.discard(name)
                changed = True
    return names


Compiler._STMT = {
    N.ExprStmt: Compiler._c_expr_stmt,
    N.Assign: Compiler._c_assign,
    N.If: Compiler._c_if,
    N.While: Compiler._c_while,
    N.For: Compiler._c_for,
    N.FuncDef: Compiler._c_funcdef,
    N.Return: Compiler._c_return,
    N.Break: Compiler._c_break,
    N.Continue: Compiler._c_continue,
}

Compiler._EXPR = {
    N.IntLit: Compiler._c_const,
    N.FloatLit: Compiler._c_const,
    N.StrLit: Compiler._c_const,
    N.BoolLit: Compiler._c_const,
    N.NilLit: Compiler._c_nil,
    N.InterpStr: Compiler._c_interp,
    N.ListLit: Compiler._c_list,
    N.MapLit: Compiler._c_map,
    N.Identifier: Compiler._c_identifier,
    N.BinaryOp: Compiler._c_binary,
    N.UnaryOp: Compiler._c_unary,
    N.LogicalOp: Compiler._c_logical,
    N.Call: Compiler._c_call,
    N.Index: Compiler._c_index,
    N.Attribute: Compiler._c_attribute,
}


def compile_program(program):
    return Compiler().compile_program(program)
