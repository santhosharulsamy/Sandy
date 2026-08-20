"""AST node definitions for Sandy.

Plain, lightweight classes. Each node keeps the source line for error
reporting during evaluation.
"""


class Node:
    __slots__ = ()


# ---- Expressions ----

class IntLit(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class FloatLit(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class StrLit(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class BoolLit(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class NilLit(Node):
    __slots__ = ("line",)
    def __init__(self, line):
        self.line = line


class ListLit(Node):
    __slots__ = ("items", "line")
    def __init__(self, items, line):
        self.items = items; self.line = line


class MapLit(Node):
    __slots__ = ("pairs", "line")  # list of (key_node, value_node)
    def __init__(self, pairs, line):
        self.pairs = pairs; self.line = line


class Identifier(Node):
    __slots__ = ("name", "line")
    def __init__(self, name, line):
        self.name = name; self.line = line


class BinaryOp(Node):
    __slots__ = ("op", "left", "right", "line")
    def __init__(self, op, left, right, line):
        self.op = op; self.left = left; self.right = right; self.line = line


class UnaryOp(Node):
    __slots__ = ("op", "operand", "line")
    def __init__(self, op, operand, line):
        self.op = op; self.operand = operand; self.line = line


class LogicalOp(Node):
    __slots__ = ("op", "left", "right", "line")  # 'and' / 'or' (short-circuit)
    def __init__(self, op, left, right, line):
        self.op = op; self.left = left; self.right = right; self.line = line


class Call(Node):
    __slots__ = ("callee", "args", "line")
    def __init__(self, callee, args, line):
        self.callee = callee; self.args = args; self.line = line


class Index(Node):
    __slots__ = ("target", "index", "line")
    def __init__(self, target, index, line):
        self.target = target; self.index = index; self.line = line


class Attribute(Node):
    __slots__ = ("target", "name", "line")
    def __init__(self, target, name, line):
        self.target = target; self.name = name; self.line = line


# ---- Statements ----

class ExprStmt(Node):
    __slots__ = ("expr", "line")
    def __init__(self, expr, line):
        self.expr = expr; self.line = line


class Assign(Node):
    __slots__ = ("target", "op", "value", "line")  # target: Identifier/Index
    def __init__(self, target, op, value, line):
        self.target = target; self.op = op; self.value = value; self.line = line


class Block(Node):
    __slots__ = ("statements",)
    def __init__(self, statements):
        self.statements = statements


class If(Node):
    __slots__ = ("branches", "else_block", "line")  # branches: list of (cond, block)
    def __init__(self, branches, else_block, line):
        self.branches = branches; self.else_block = else_block; self.line = line


class While(Node):
    __slots__ = ("cond", "body", "line")
    def __init__(self, cond, body, line):
        self.cond = cond; self.body = body; self.line = line


class For(Node):
    __slots__ = ("var", "iterable", "body", "line")
    def __init__(self, var, iterable, body, line):
        self.var = var; self.iterable = iterable; self.body = body; self.line = line


class FuncDef(Node):
    __slots__ = ("name", "params", "body", "line")
    def __init__(self, name, params, body, line):
        self.name = name; self.params = params; self.body = body; self.line = line


class Return(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class Break(Node):
    __slots__ = ("line",)
    def __init__(self, line):
        self.line = line


class Continue(Node):
    __slots__ = ("line",)
    def __init__(self, line):
        self.line = line
