"""A gradual static type checker for Sandy.

Gradual means: annotations are optional. Anything without a type is treated
as `any`, and `any` is compatible with everything, so fully dynamic Sandy
code produces zero type errors and behaves exactly as before. Where you *do*
add annotations, the checker proves types line up before the program runs —
catching a class of bugs at "compile" time instead of at runtime.

The checker is intentionally conservative: it only reports an error when two
*known, non-any* types definitely conflict. It never guesses.
"""

from . import nodes as N

NUM = ("int", "float")
_PRIMITIVES = ("int", "float", "string", "bool", "nil", "list", "map")


class FuncType:
    __slots__ = ("params", "ret")

    def __init__(self, params, ret):
        self.params = params      # list of type names (str), 'any' allowed
        self.ret = ret            # type name (str)


class Scope:
    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name):
        s = self
        while s is not None:
            if name in s.vars:
                return s.vars[name]
            s = s.parent
        return None

    def define(self, name, type_):
        self.vars[name] = type_


def type_name(t):
    if isinstance(t, FuncType):
        return "function"
    return t if t is not None else "any"


def _norm(t):
    """Normalize an annotation (None -> 'any')."""
    return "any" if t is None else t


def _base(t):
    """Base name of a (possibly parameterized) type: list<int> -> list."""
    if isinstance(t, str) and "<" in t:
        return t[:t.index("<")]
    return t


def _split_top(s):
    """Split a comma list at the top nesting level: 'string,list<int>'."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(s[start:i]); start = i + 1
    parts.append(s[start:])
    return parts


def _type_args(t):
    """Type arguments of a parameterized type. An unparameterized list/map is
    treated as fully gradual (element type `any`)."""
    if isinstance(t, str) and "<" in t:
        return tuple(_split_top(t[t.index("<") + 1:-1]))
    if t == "list":
        return ("any",)
    if t == "map":
        return ("any", "any")
    return ()


def assignable(expected, actual):
    """Can a value of `actual` type be used where `expected` is wanted?"""
    if expected is None or actual is None:
        return True
    if expected == "any" or actual == "any":
        return True
    if isinstance(expected, FuncType) or isinstance(actual, FuncType):
        return isinstance(expected, FuncType) and isinstance(actual, FuncType)
    eb, ab = _base(expected), _base(actual)
    if eb in ("list", "map") and ab == eb:
        # Element/value types checked gradually (any is compatible).
        return all(assignable(x, y)
                   for x, y in zip(_type_args(expected), _type_args(actual)))
    if eb == ab:
        return True
    if eb == "float" and ab == "int":
        return True  # int widens to float
    return False


class TypeChecker:
    def __init__(self):
        self.errors = []  # list of (message, line)

    def error(self, msg, line):
        self.errors.append((msg, line))

    def check(self, program):
        scope = Scope()
        self._check_block(program, scope, expected_ret=None)
        return self.errors

    # -- statements --
    def _collect_functions(self, block, scope):
        """Register function signatures first so recursion and forward
        references type-check."""
        for stmt in block.statements:
            if isinstance(stmt, N.FuncDef):
                params = [_norm(t) for t in stmt.param_types]
                scope.define(stmt.name, FuncType(params, _norm(stmt.ret_type)))

    def _check_block(self, block, scope, expected_ret):
        self._collect_functions(block, scope)
        for stmt in block.statements:
            self._check_stmt(stmt, scope, expected_ret)

    def _check_stmt(self, node, scope, expected_ret):
        t = type(node)
        if t is N.Assign:
            self._check_assign(node, scope)
        elif t is N.ExprStmt:
            self._infer(node.expr, scope)
        elif t is N.If:
            for cond, block in node.branches:
                self._infer(cond, scope)
                self._check_block(block, scope, expected_ret)
            if node.else_block is not None:
                self._check_block(node.else_block, scope, expected_ret)
        elif t is N.While:
            self._infer(node.cond, scope)
            self._check_block(node.body, scope, expected_ret)
        elif t is N.For:
            self._infer(node.iterable, scope)
            scope.define(node.var, "any")  # element type is not tracked yet
            self._check_block(node.body, scope, expected_ret)
        elif t is N.FuncDef:
            self._check_funcdef(node, scope)
        elif t is N.Return:
            self._check_return(node, scope, expected_ret)
        # Break / Continue: nothing to check

    def _check_assign(self, node, scope):
        value_t = self._infer(node.value, scope)
        target = node.target
        if isinstance(target, N.Identifier):
            if node.annotation is not None:
                # Annotated declaration: value must fit the annotation.
                if not assignable(node.annotation, value_t):
                    self.error(
                        f"cannot assign {type_name(value_t)} to '{target.name}' "
                        f"declared as {type_name(node.annotation)}", node.line)
                scope.define(target.name, node.annotation)
            else:
                declared = scope.get(target.name)
                if isinstance(declared, str) and declared not in ("any", None):
                    # Reassigning a previously-typed variable: must still fit.
                    if not assignable(declared, value_t):
                        self.error(
                            f"cannot assign {type_name(value_t)} to '{target.name}' "
                            f"declared as {type_name(declared)}", node.line)
                elif declared is None:
                    scope.define(target.name, "any")
        else:
            # Index assignment: evaluate parts to surface nested errors.
            self._infer(target, scope)

    def _check_funcdef(self, node, scope):
        fn_scope = Scope(scope)
        for name, ann in zip(node.params, node.param_types):
            fn_scope.define(name, _norm(ann))
        ret = _norm(node.ret_type)
        expected = None if ret == "any" else ret
        self._check_block(node.body, fn_scope, expected)

    def _check_return(self, node, scope, expected_ret):
        if node.value is None:
            actual = "nil"
        else:
            actual = self._infer(node.value, scope)
        if expected_ret is not None and not assignable(expected_ret, actual):
            self.error(
                f"return type mismatch: expected {type_name(expected_ret)}, "
                f"got {type_name(actual)}", node.line)

    # -- expression type inference --
    def _infer(self, node, scope):
        m = self._INFER.get(type(node))
        if m is None:
            return "any"
        return m(self, node, scope)

    def _i_int(self, node, scope):
        return "int"

    def _i_float(self, node, scope):
        return "float"

    def _i_str(self, node, scope):
        return "string"

    def _i_bool(self, node, scope):
        return "bool"

    def _i_nil(self, node, scope):
        return "nil"

    def _i_list(self, node, scope):
        elems = [self._infer(item, scope) for item in node.items]
        if elems and all(e == elems[0] and e not in ("any", None) for e in elems):
            return f"list<{elems[0]}>"
        return "list"

    def _i_map(self, node, scope):
        for k, v in node.pairs:
            self._infer(k, scope)
            self._infer(v, scope)
        return "map"

    def _i_interp(self, node, scope):
        for kind, payload in node.parts:
            if kind == "expr":
                self._infer(payload, scope)
        return "string"

    def _i_identifier(self, node, scope):
        t = scope.get(node.name)
        return t if t is not None else "any"

    def _i_binary(self, node, scope):
        lt = self._infer(node.left, scope)
        rt = self._infer(node.right, scope)
        return self._binary_type(node.op, lt, rt, node.line)

    def _i_unary(self, node, scope):
        t = self._infer(node.operand, scope)
        if node.op == "not":
            return "bool"
        # negation
        if t in ("any", None):
            return "any"
        if t in NUM:
            return t
        self.error(f"cannot negate a {type_name(t)}", node.line)
        return "any"

    def _i_logical(self, node, scope):
        self._infer(node.left, scope)
        self._infer(node.right, scope)
        return "any"  # result is one of the two operands

    def _i_call(self, node, scope):
        callee_t = self._infer(node.callee, scope)
        arg_types = [self._infer(a, scope) for a in node.args]
        if isinstance(callee_t, FuncType):
            fname = node.callee.name + "()" if isinstance(node.callee, N.Identifier) else "function"
            if len(arg_types) != len(callee_t.params):
                self.error(
                    f"{fname} expects {len(callee_t.params)} argument(s), "
                    f"got {len(arg_types)}", node.line)
            else:
                for i, (pt, at) in enumerate(zip(callee_t.params, arg_types)):
                    if not assignable(pt, at):
                        self.error(
                            f"argument {i + 1} of {fname} expects "
                            f"{type_name(pt)}, got {type_name(at)}",
                            node.args[i].line)
            return callee_t.ret
        return "any"

    def _i_index(self, node, scope):
        target_t = self._infer(node.target, scope)
        self._infer(node.index, scope)
        if target_t == "string":
            return "string"
        if _base(target_t) == "list":
            return _type_args(target_t)[0]      # element type
        if _base(target_t) == "map":
            return _type_args(target_t)[1]      # value type
        return "any"

    def _i_attribute(self, node, scope):
        self._infer(node.target, scope)
        return "any"

    def _binary_type(self, op, lt, rt, line):
        unknown = lt in ("any", None) or rt in ("any", None)
        if op in ("==", "!="):
            return "bool"
        if op in ("<", ">", "<=", ">="):
            if unknown:
                return "bool"
            if (lt in NUM and rt in NUM) or (lt == "string" and rt == "string"):
                return "bool"
            self.error(
                f"cannot compare {type_name(lt)} and {type_name(rt)}", line)
            return "bool"
        if unknown:
            return "any"
        if op == "+":
            if lt in NUM and rt in NUM:
                return self._num_result(op, lt, rt)
            if lt == "string" and rt == "string":
                return "string"
            if _base(lt) == "list" and _base(rt) == "list":
                return lt if lt == rt else "list"
            self.error(f"cannot add {type_name(lt)} and {type_name(rt)}", line)
            return "any"
        if op == "*":
            if lt in NUM and rt in NUM:
                return self._num_result(op, lt, rt)
            if (lt == "string" and rt == "int") or (lt == "int" and rt == "string"):
                return "string"
            if (_base(lt) == "list" and rt == "int"):
                return lt
            if (lt == "int" and _base(rt) == "list"):
                return rt
            self.error(f"cannot multiply {type_name(lt)} and {type_name(rt)}", line)
            return "any"
        # - / % **
        if lt in NUM and rt in NUM:
            if op == "/":
                return "float"
            return self._num_result(op, lt, rt)
        verb = {"-": "subtract", "/": "divide", "%": "take modulo of",
                "**": "raise to a power"}.get(op, "combine")
        self.error(
            f"cannot {verb} {type_name(lt)} and {type_name(rt)}", line)
        return "any"

    @staticmethod
    def _num_result(op, lt, rt):
        if op == "/":
            return "float"
        if lt == "float" or rt == "float":
            return "float"
        if op == "**":
            return "any"  # int ** negative-int is float; stay conservative
        return "int"


TypeChecker._INFER = {
    N.IntLit: TypeChecker._i_int,
    N.FloatLit: TypeChecker._i_float,
    N.StrLit: TypeChecker._i_str,
    N.BoolLit: TypeChecker._i_bool,
    N.NilLit: TypeChecker._i_nil,
    N.ListLit: TypeChecker._i_list,
    N.MapLit: TypeChecker._i_map,
    N.InterpStr: TypeChecker._i_interp,
    N.Identifier: TypeChecker._i_identifier,
    N.BinaryOp: TypeChecker._i_binary,
    N.UnaryOp: TypeChecker._i_unary,
    N.LogicalOp: TypeChecker._i_logical,
    N.Call: TypeChecker._i_call,
    N.Index: TypeChecker._i_index,
    N.Attribute: TypeChecker._i_attribute,
}


def check(program):
    """Type-check a parsed program. Returns a list of (message, line)."""
    return TypeChecker().check(program)
