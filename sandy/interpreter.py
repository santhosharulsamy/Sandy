"""Tree-walking evaluator for Sandy."""

from .errors import RuntimeErrorSandy
from . import nodes as N
from .values import (
    Function, BuiltinFunction, StructType, StructInstance,
    is_truthy, type_name, to_str,
)
from .builtins import make_builtins
from .suggest import closest_name


# -- control-flow signals (not user errors) --
class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class Environment:
    __slots__ = ("vars", "parent")

    def __init__(self, parent=None):
        self.vars = {}
        self.parent = parent

    def get(self, name, line):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        msg = f"undefined variable '{name}'"
        guess = closest_name(name, self._all_names())
        if guess is not None:
            msg += f" (did you mean '{guess}'?)"
        raise RuntimeErrorSandy(msg, line)

    def _all_names(self):
        names = set()
        env = self
        while env is not None:
            names.update(env.vars.keys())
            env = env.parent
        return names

    def assign(self, name, value):
        # Update the nearest existing binding; otherwise define here.
        env = self
        while env is not None:
            if name in env.vars:
                env.vars[name] = value
                return
            env = env.parent
        self.vars[name] = value

    def define(self, name, value):
        self.vars[name] = value


class Interpreter:
    def __init__(self, out=None):
        self.globals = Environment()
        for name, fn in make_builtins(self).items():
            self.globals.define(name, fn)
        self.out = out  # optional writer override for print (tests)

    # -- public API --
    def run(self, program):
        self._exec_block(program, self.globals)

    # -- statement execution --
    def _exec_block(self, block, env):
        for stmt in block.statements:
            self._exec(stmt, env)

    def _exec(self, node, env):
        method = self._STMT_DISPATCH.get(type(node))
        if method is None:
            # expression used as a statement path handled below
            raise RuntimeErrorSandy(
                f"cannot execute node {type(node).__name__}", getattr(node, "line", None))
        return method(self, node, env)

    def _exec_expr_stmt(self, node, env):
        self._eval(node.expr, env)

    def _exec_assign(self, node, env):
        value = self._eval(node.value, env)
        target = node.target
        if isinstance(target, N.Identifier):
            if node.op != "=":
                current = env.get(target.name, node.line)
                value = self._apply_compound(node.op, current, value, node.line)
            env.assign(target.name, value)
        elif isinstance(target, N.Index):
            container = self._eval(target.target, env)
            key = self._eval(target.index, env)
            if node.op != "=":
                current = self._index_get(container, key, node.line)
                value = self._apply_compound(node.op, current, value, node.line)
            self._index_set(container, key, value, node.line)
        elif isinstance(target, N.Attribute):
            obj = self._eval(target.target, env)
            if node.op != "=":
                current = self._get_field(obj, target.name, node.line)
                value = self._apply_compound(node.op, current, value, node.line)
            self._set_field(obj, target.name, value, node.line)
        else:
            raise RuntimeErrorSandy("invalid assignment target", node.line)

    def _get_field(self, obj, name, line):
        if isinstance(obj, StructInstance):
            if name not in obj.values:
                raise RuntimeErrorSandy(
                    f"{obj.struct.name} has no field '{name}'", line)
            return obj.values[name]
        raise RuntimeErrorSandy(
            f"cannot read field '{name}' of a {type_name(obj)}", line)

    def _set_field(self, obj, name, value, line):
        if isinstance(obj, StructInstance):
            if name not in obj.values:
                raise RuntimeErrorSandy(
                    f"{obj.struct.name} has no field '{name}'", line)
            obj.values[name] = value
            return
        raise RuntimeErrorSandy(
            f"cannot set field '{name}' on a {type_name(obj)}", line)

    def _apply_compound(self, op, current, value, line):
        return self._binary(op[0], current, value, line)

    def _exec_if(self, node, env):
        # Sandy uses function-level scoping: blocks share the enclosing
        # scope rather than creating a new one (like Python/JS locals).
        for cond, block in node.branches:
            if is_truthy(self._eval(cond, env)):
                self._exec_block(block, env)
                return
        if node.else_block is not None:
            self._exec_block(node.else_block, env)

    def _exec_while(self, node, env):
        while is_truthy(self._eval(node.cond, env)):
            try:
                self._exec_block(node.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _exec_for(self, node, env):
        iterable = self._eval(node.iterable, env)
        items = self._as_iterable(iterable, node.line)
        for item in items:
            env.define(node.var, item)
            try:
                self._exec_block(node.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _exec_funcdef(self, node, env):
        fn = Function(node.name, node.params, node.body, env, node.param_types)
        env.define(node.name, fn)

    def _exec_return(self, node, env):
        value = None if node.value is None else self._eval(node.value, env)
        raise _Return(value)

    def _exec_break(self, node, env):
        raise _Break()

    def _exec_continue(self, node, env):
        raise _Continue()

    def _exec_try(self, node, env):
        try:
            self._exec_block(node.body, env)
        except RuntimeErrorSandy as e:
            # Bind the error message to the catch variable and run the handler.
            # Control-flow signals (_Return/_Break/_Continue) are not caught.
            env.define(node.catch_var, e.message)
            self._exec_block(node.handler, env)

    def _exec_throw(self, node, env):
        value = self._eval(node.value, env)
        raise RuntimeErrorSandy(to_str(value), node.line)

    def _exec_structdef(self, node, env):
        env.define(node.name,
                   StructType(node.name, node.fields, node.field_types))

    # -- expression evaluation --
    def _eval(self, node, env):
        method = self._EXPR_DISPATCH.get(type(node))
        if method is None:
            raise RuntimeErrorSandy(
                f"cannot evaluate node {type(node).__name__}", getattr(node, "line", None))
        return method(self, node, env)

    def _eval_int(self, node, env):
        return node.value

    def _eval_float(self, node, env):
        return node.value

    def _eval_str(self, node, env):
        return node.value

    def _eval_interp(self, node, env):
        out = []
        for kind, payload in node.parts:
            if kind == "lit":
                out.append(payload)
            else:
                out.append(to_str(self._eval(payload, env)))
        return "".join(out)

    def _eval_bool(self, node, env):
        return node.value

    def _eval_nil(self, node, env):
        return None

    def _eval_list(self, node, env):
        return [self._eval(item, env) for item in node.items]

    def _eval_map(self, node, env):
        result = {}
        for key_node, val_node in node.pairs:
            key = self._eval(key_node, env)
            if isinstance(key, (list, dict)):
                raise RuntimeErrorSandy(
                    f"map key cannot be a {type_name(key)}", node.line)
            result[key] = self._eval(val_node, env)
        return result

    def _eval_identifier(self, node, env):
        return env.get(node.name, node.line)

    def _eval_binary(self, node, env):
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        return self._binary(node.op, left, right, node.line)

    def _eval_unary(self, node, env):
        if node.op == "not":
            return not is_truthy(self._eval(node.operand, env))
        operand = self._eval(node.operand, env)
        if node.op == "-":
            if isinstance(operand, bool) or not isinstance(operand, (int, float)):
                raise RuntimeErrorSandy(
                    f"cannot negate a {type_name(operand)}", node.line)
            return -operand
        raise RuntimeErrorSandy(f"unknown unary operator {node.op}", node.line)

    def _eval_logical(self, node, env):
        left = self._eval(node.left, env)
        if node.op == "and":
            if not is_truthy(left):
                return left
            return self._eval(node.right, env)
        else:  # or
            if is_truthy(left):
                return left
            return self._eval(node.right, env)

    def _eval_call(self, node, env):
        callee = self._eval(node.callee, env)
        args = [self._eval(a, env) for a in node.args]
        return self.call(callee, args, node.line)

    def _eval_index(self, node, env):
        container = self._eval(node.target, env)
        key = self._eval(node.index, env)
        return self._index_get(container, key, node.line)

    def _eval_attribute(self, node, env):
        target = self._eval(node.target, env)
        # Struct field access takes precedence over method resolution.
        if isinstance(target, StructInstance):
            return self._get_field(target, node.name, node.line)
        from .builtins import resolve_method
        return resolve_method(self, target, node.name, node.line)

    def _construct(self, struct, args, line):
        if len(args) != len(struct.fields):
            raise RuntimeErrorSandy(
                f"{struct.name}() expects {len(struct.fields)} field(s) "
                f"({', '.join(struct.fields)}), got {len(args)}", line)
        return StructInstance(struct, dict(zip(struct.fields, args)))

    # -- calling --
    def call(self, callee, args, line):
        if isinstance(callee, StructType):
            return self._construct(callee, args, line)
        if isinstance(callee, BuiltinFunction):
            self._check_arity(callee, args, line)
            return callee.fn(args, line)
        if isinstance(callee, Function):
            if len(args) != len(callee.params):
                raise RuntimeErrorSandy(
                    f"{callee.name}() expects {len(callee.params)} argument(s), "
                    f"got {len(args)}", line)
            local = Environment(callee.closure)
            for param, arg in zip(callee.params, args):
                local.define(param, arg)
            try:
                self._exec_block(callee.body, local)
            except _Return as r:
                return r.value
            return None
        raise RuntimeErrorSandy(
            f"'{type_name(callee)}' value is not callable", line)

    def _check_arity(self, builtin, args, line):
        arity = builtin.arity
        if arity is None:
            return
        if isinstance(arity, tuple):
            lo, hi = arity
            if not (lo <= len(args) <= (hi if hi is not None else 1 << 30)):
                exp = f"{lo}" if hi == lo else (f"{lo}+" if hi is None else f"{lo}-{hi}")
                raise RuntimeErrorSandy(
                    f"{builtin.name}() expects {exp} argument(s), got {len(args)}", line)
        elif len(args) != arity:
            raise RuntimeErrorSandy(
                f"{builtin.name}() expects {arity} argument(s), got {len(args)}", line)

    # -- operators --
    def _binary(self, op, left, right, line):
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            if self._is_num(left) and self._is_num(right):
                return left + right
            raise RuntimeErrorSandy(
                f"cannot add {type_name(left)} and {type_name(right)}", line)
        if op == "-":
            self._need_num(left, right, "subtract", line)
            return left - right
        if op == "*":
            if isinstance(left, str) and self._is_int(right):
                return left * right
            if isinstance(right, str) and self._is_int(left):
                return right * left
            if isinstance(left, list) and self._is_int(right):
                return left * right
            if isinstance(right, list) and self._is_int(left):
                return right * left
            self._need_num(left, right, "multiply", line)
            return left * right
        if op == "/":
            self._need_num(left, right, "divide", line)
            if right == 0:
                raise RuntimeErrorSandy("division by zero", line)
            return left / right
        if op == "%":
            self._need_num(left, right, "take modulo of", line)
            if right == 0:
                raise RuntimeErrorSandy("modulo by zero", line)
            return left % right
        if op == "**":
            self._need_num(left, right, "raise to a power", line)
            return left ** right
        if op == "==":
            return self._equals(left, right)
        if op == "!=":
            return not self._equals(left, right)
        if op in ("<", ">", "<=", ">="):
            return self._compare(op, left, right, line)
        raise RuntimeErrorSandy(f"unknown operator {op}", line)

    def _equals(self, a, b):
        # bool is a subclass of int in Python; keep true==1 out of surprises
        if isinstance(a, bool) or isinstance(b, bool):
            return a is b
        if self._is_num(a) and self._is_num(b):
            return a == b
        if isinstance(a, StructInstance) and isinstance(b, StructInstance):
            return (a.struct.name == b.struct.name
                    and a.values.keys() == b.values.keys()
                    and all(self._equals(a.values[k], b.values[k])
                            for k in a.values))
        if type(a) is type(b):
            return a == b
        return False

    def _compare(self, op, a, b, line):
        ok = (self._is_num(a) and self._is_num(b)) or \
             (isinstance(a, str) and isinstance(b, str))
        if not ok:
            raise RuntimeErrorSandy(
                f"cannot compare {type_name(a)} and {type_name(b)}", line)
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "<=":
            return a <= b
        return a >= b

    # -- indexing --
    def _index_get(self, container, key, line):
        if isinstance(container, (list, str)):
            if not self._is_int(key):
                raise RuntimeErrorSandy(
                    f"{type_name(container)} index must be an int, "
                    f"got {type_name(key)}", line)
            length = len(container)
            idx = key + length if key < 0 else key
            if idx < 0 or idx >= length:
                raise RuntimeErrorSandy(
                    f"index {key} out of range (length {length})", line)
            return container[idx]
        if isinstance(container, dict):
            if key not in container:
                raise RuntimeErrorSandy(f"key {key!r} not found in map", line)
            return container[key]
        raise RuntimeErrorSandy(
            f"cannot index a {type_name(container)}", line)

    def _index_set(self, container, key, value, line):
        if isinstance(container, list):
            if not self._is_int(key):
                raise RuntimeErrorSandy(
                    f"list index must be an int, got {type_name(key)}", line)
            length = len(container)
            idx = key + length if key < 0 else key
            if idx < 0 or idx >= length:
                raise RuntimeErrorSandy(
                    f"index {key} out of range (length {length})", line)
            container[idx] = value
        elif isinstance(container, dict):
            if isinstance(key, (list, dict)):
                raise RuntimeErrorSandy(
                    f"map key cannot be a {type_name(key)}", line)
            container[key] = value
        elif isinstance(container, str):
            raise RuntimeErrorSandy("strings are immutable", line)
        else:
            raise RuntimeErrorSandy(
                f"cannot index-assign a {type_name(container)}", line)

    # -- iteration --
    def _as_iterable(self, value, line):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return list(value)
        if isinstance(value, dict):
            return list(value.keys())
        raise RuntimeErrorSandy(
            f"cannot iterate over a {type_name(value)}", line)

    # -- helpers --
    @staticmethod
    def _is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    @staticmethod
    def _is_int(v):
        return isinstance(v, int) and not isinstance(v, bool)

    def _need_num(self, left, right, verb, line):
        if not (self._is_num(left) and self._is_num(right)):
            raise RuntimeErrorSandy(
                f"cannot {verb} {type_name(left)} and {type_name(right)}", line)


# Dispatch tables (filled after class body).
Interpreter._STMT_DISPATCH = {
    N.ExprStmt: Interpreter._exec_expr_stmt,
    N.Assign: Interpreter._exec_assign,
    N.If: Interpreter._exec_if,
    N.While: Interpreter._exec_while,
    N.For: Interpreter._exec_for,
    N.FuncDef: Interpreter._exec_funcdef,
    N.Return: Interpreter._exec_return,
    N.Break: Interpreter._exec_break,
    N.Continue: Interpreter._exec_continue,
    N.Try: Interpreter._exec_try,
    N.Throw: Interpreter._exec_throw,
    N.StructDef: Interpreter._exec_structdef,
}

Interpreter._EXPR_DISPATCH = {
    N.IntLit: Interpreter._eval_int,
    N.FloatLit: Interpreter._eval_float,
    N.StrLit: Interpreter._eval_str,
    N.InterpStr: Interpreter._eval_interp,
    N.BoolLit: Interpreter._eval_bool,
    N.NilLit: Interpreter._eval_nil,
    N.ListLit: Interpreter._eval_list,
    N.MapLit: Interpreter._eval_map,
    N.Identifier: Interpreter._eval_identifier,
    N.BinaryOp: Interpreter._eval_binary,
    N.UnaryOp: Interpreter._eval_unary,
    N.LogicalOp: Interpreter._eval_logical,
    N.Call: Interpreter._eval_call,
    N.Index: Interpreter._eval_index,
    N.Attribute: Interpreter._eval_attribute,
}
