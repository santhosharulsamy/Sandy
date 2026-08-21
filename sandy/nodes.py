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


class InterpStr(Node):
    # parts: list of ("lit", text) or ("expr", node)
    __slots__ = ("parts", "line")
    def __init__(self, parts, line):
        self.parts = parts; self.line = line


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
    # target: Identifier/Index; annotation: optional type name (str) or None
    __slots__ = ("target", "op", "value", "line", "annotation")
    def __init__(self, target, op, value, line, annotation=None):
        self.target = target; self.op = op; self.value = value
        self.line = line; self.annotation = annotation


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
    # param_types: list aligned with params (each a type name str or None)
    # ret_type: return type name str or None
    __slots__ = ("name", "params", "body", "line", "param_types", "ret_type")
    def __init__(self, name, params, body, line, param_types=None, ret_type=None):
        self.name = name; self.params = params; self.body = body; self.line = line
        self.param_types = param_types if param_types is not None else [None] * len(params)
        self.ret_type = ret_type


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


class Try(Node):
    # body: Block; catch_var: str; handler: Block
    __slots__ = ("body", "catch_var", "handler", "line")
    def __init__(self, body, catch_var, handler, line):
        self.body = body; self.catch_var = catch_var
        self.handler = handler; self.line = line


class Throw(Node):
    __slots__ = ("value", "line")
    def __init__(self, value, line):
        self.value = value; self.line = line


class StructDef(Node):
    # fields: list of field names; field_types: aligned list (str or None)
    __slots__ = ("name", "fields", "field_types", "line")
    def __init__(self, name, fields, field_types, line):
        self.name = name; self.fields = fields
        self.field_types = field_types; self.line = line


class Import(Node):
    # path: source string; alias: local name bound to the module
    __slots__ = ("path", "alias", "line")
    def __init__(self, path, alias, line):
        self.path = path; self.alias = alias; self.line = line
