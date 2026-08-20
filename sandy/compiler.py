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


class Compiler:
    def __init__(self, name="<main>", params=()):
        self.name = name
        self.params = list(params)
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
        self._compile_block(block)
        self._emit(B.LOAD_CONST, self._const(None), 0)
        self._emit(B.RETURN, None, 0)
        return self._code()

    def _code(self):
        return B.CodeObject(self.name, self.params, self.ops, self.consts, self.lines)

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
                self._emit(B.BINARY_OPS[node.op[0]], None, node.line)
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
        self._emit(B.BINARY_OPS[node.op], None, node.line)

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
    c = Compiler(node.name, node.params)
    c._compile_block(node.body)
    # implicit `return nil` if control falls off the end
    c._emit(B.LOAD_CONST, c._const(None), node.line)
    c._emit(B.RETURN, None, node.line)
    return c._code()


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
