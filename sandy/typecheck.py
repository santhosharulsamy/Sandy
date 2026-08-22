"""A gradual static type checker for Sandy.

Gradual means: annotations are optional. Anything without a type is treated
as `any`, and `any` is compatible with everything, so fully dynamic Sandy
code produces zero type errors and behaves exactly as before. Where you *do*
add annotations, the checker proves types line up before the program runs —
catching a class of bugs at "compile" time instead of at runtime.

The checker is intentionally conservative: it only reports an error when two
*known, non-any* types definitely conflict. It never guesses.
"""

import os

from . import nodes as N

NUM = ("int", "float")

# Sentinel marking a module mid-analysis (to break import cycles).
_ANALYZING = object()
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


class StructDecl:
    """A struct type known to the checker: field names and their types."""
    __slots__ = ("name", "fields", "field_types")

    def __init__(self, name, fields, field_types):
        self.name = name
        self.fields = fields              # list of field names
        self.field_types = field_types    # dict field -> normalized type


class ModuleType:
    """An imported module's exported members and their types."""
    __slots__ = ("name", "members")

    def __init__(self, name, members):
        self.name = name
        self.members = members            # dict name -> type / FuncType / StructDecl


def type_name(t):
    if isinstance(t, FuncType):
        if t.params is None:
            return "fn"
        return (f"fn({', '.join(type_name(p) for p in t.params)}) -> "
                f"{type_name(t.ret)}")
    if isinstance(t, StructDecl):
        return t.name
    return t if t is not None else "any"


def _norm(t):
    """Normalize an annotation (None -> 'any'; a function type -> FuncType)."""
    if t is None:
        return "any"
    if isinstance(t, str) and (t == "fn" or t.startswith("fn(")):
        params, ret = _fn_sig(t)
        return FuncType(None if params is None else [_norm(p) for p in params],
                        _norm(ret))
    return t


def _base(t):
    """Base name of a (possibly parameterized) type: list<int> -> list."""
    if isinstance(t, str) and "<" in t:
        return t[:t.index("<")]
    return t


def _split_top(s):
    """Split a comma list at the top nesting level, respecting both <> and ()
    so function types nest correctly: 'string,fn(int,int)->int'."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(s):
        if ch in "<(":
            depth += 1
        elif ch in ">)":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(s[start:i]); start = i + 1
    parts.append(s[start:])
    return parts


def _fn_sig(t):
    """Parse a function-type string. Returns (params, ret):
    'fn(int,int)->int' -> (['int','int'], 'int'); 'fn(int)' -> (['int'], 'nil');
    'fn' -> (None, 'any') for the fully-gradual bare form."""
    if t == "fn":
        return None, "any"
    depth = 0
    for i in range(2, len(t)):  # scan from the '(' after 'fn'
        if t[i] == "(":
            depth += 1
        elif t[i] == ")":
            depth -= 1
            if depth == 0:
                inner = t[3:i].strip()
                rest = t[i + 1:]
                params = [p.strip() for p in _split_top(inner)] if inner else []
                ret = rest[2:].strip() if rest.startswith("->") else "nil"
                return params, (ret or "nil")
    return None, "any"


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
    if isinstance(expected, StructDecl) or isinstance(actual, StructDecl):
        return True  # struct-type values used as data are gradual
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
    def __init__(self, base_dir=None, module_cache=None):
        self.errors = []  # list of (message, line)
        self.structs = {}  # struct name -> StructDecl (for field lookups)
        self.base_dir = base_dir            # for resolving imports
        self.module_cache = {} if module_cache is None else module_cache

    def error(self, msg, line):
        self.errors.append((msg, line))

    def check(self, program):
        scope = Scope()
        self._check_block(program, scope, expected_ret=None)
        return self.errors

    # -- module analysis (extract exported member types) --
    def _resolve_module(self, path):
        rel = path if path.endswith(".sy") else path + ".sy"
        base = self.base_dir or os.getcwd()
        candidate = os.path.abspath(os.path.join(base, rel))
        if os.path.exists(candidate):
            return candidate
        stdlib = os.path.join(os.path.dirname(__file__), "stdlib", rel)
        if os.path.exists(stdlib):
            return os.path.abspath(stdlib)
        return None

    def _analyze_module(self, path):
        """Return a ModuleType for an import, or None if it can't be analyzed
        (missing file, syntax error, or an import cycle — the runtime reports
        real load failures; the checker just stays gradual)."""
        abspath = self._resolve_module(path)
        if abspath is None:
            return None
        cached = self.module_cache.get(abspath)
        if cached is _ANALYZING:
            return None  # cycle: treat members as `any`
        if cached is not None:
            self._merge_structs(cached)
            return cached
        self.module_cache[abspath] = _ANALYZING
        try:
            from .lexer import tokenize
            from .parser import parse
            with open(abspath, "r", encoding="utf-8") as f:
                program = parse(tokenize(f.read()))
        except Exception:
            self.module_cache.pop(abspath, None)
            return None
        sub = TypeChecker(base_dir=os.path.dirname(abspath),
                          module_cache=self.module_cache)
        scope = Scope()
        sub._check_block(program, scope, expected_ret=None)  # errors ignored
        name = os.path.splitext(os.path.basename(abspath))[0]
        module = ModuleType(name, dict(scope.vars))
        self.module_cache[abspath] = module
        self._merge_structs(module)
        return module

    def _merge_structs(self, module):
        # Make imported struct types available for field-access checking.
        for member in module.members.values():
            if isinstance(member, StructDecl) and member.name not in self.structs:
                self.structs[member.name] = member

    # -- statements --
    def _collect_structs(self, block, scope):
        for stmt in block.statements:
            if isinstance(stmt, N.StructDef):
                ftypes = {f: _norm(t)
                          for f, t in zip(stmt.fields, stmt.field_types)}
                decl = StructDecl(stmt.name, list(stmt.fields), ftypes)
                scope.define(stmt.name, decl)
                self.structs[stmt.name] = decl

    def _collect_functions(self, block, scope):
        """Register function signatures first so recursion and forward
        references type-check."""
        for stmt in block.statements:
            if isinstance(stmt, N.FuncDef):
                params = [_norm(t) for t in stmt.param_types]
                scope.define(stmt.name, FuncType(params, _norm(stmt.ret_type)))

    def _check_block(self, block, scope, expected_ret):
        self._collect_structs(block, scope)
        self._collect_functions(block, scope)
        for stmt in block.statements:
            self._check_stmt(stmt, scope, expected_ret)

    def _check_type(self, t, line):
        """Report a type annotation that names no known type."""
        if t is None:
            return
        if isinstance(t, str) and (t == "fn" or t.startswith("fn(")):
            params, ret = _fn_sig(t)
            if params is not None:
                for p in params:
                    self._check_type(p, line)
                self._check_type(ret, line)
            return
        base = _base(t)
        if base in ("list", "map"):
            for arg in _type_args(t):
                self._check_type(arg, line)
            return
        if base in _PRIMITIVES or base in ("any", "fn"):
            return
        if base in self.structs:
            return
        self.error(f"unknown type '{t}'", line)

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
        elif t is N.Try:
            self._check_block(node.body, scope, expected_ret)
            # The caught error is always a string message.
            scope.define(node.catch_var, "string")
            self._check_block(node.handler, scope, expected_ret)
        elif t is N.Throw:
            self._infer(node.value, scope)
        elif t is N.Import:
            module = self._analyze_module(node.path)
            scope.define(node.alias, module if module is not None else "any")
        elif t is N.StructDef:
            for ft in node.field_types:
                self._check_type(ft, node.line)
        # Break / Continue: nothing to check

    def _check_assign(self, node, scope):
        value_t = self._infer(node.value, scope)
        target = node.target
        if isinstance(target, N.Identifier):
            if node.annotation is not None:
                # Annotated declaration: value must fit the annotation.
                self._check_type(node.annotation, node.line)
                ann = _norm(node.annotation)
                if not assignable(ann, value_t):
                    self.error(
                        f"cannot assign {type_name(value_t)} to '{target.name}' "
                        f"declared as {type_name(ann)}", node.line)
                scope.define(target.name, ann)
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
        elif isinstance(target, N.Attribute):
            decl = self.structs.get(self._infer(target.target, scope))
            if decl is not None:
                if target.name not in decl.field_types:
                    self.error(
                        f"{decl.name} has no field '{target.name}'", node.line)
                elif not assignable(decl.field_types[target.name], value_t):
                    self.error(
                        f"cannot assign {type_name(value_t)} to field "
                        f"'{target.name}' of {decl.name} "
                        f"(expects {type_name(decl.field_types[target.name])})",
                        node.line)
        else:
            # Index assignment: evaluate parts to surface nested errors.
            self._infer(target, scope)

    def _check_funcdef(self, node, scope):
        fn_scope = Scope(scope)
        for name, ann in zip(node.params, node.param_types):
            self._check_type(ann, node.line)
            fn_scope.define(name, _norm(ann))
        self._check_type(node.ret_type, node.line)
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
        kts, vts = [], []
        for k, v in node.pairs:
            kts.append(self._infer(k, scope))
            vts.append(self._infer(v, scope))
        if kts and all(k == kts[0] and k not in ("any", None) for k in kts) \
                and all(v == vts[0] and v not in ("any", None) for v in vts):
            return f"map<{kts[0]},{vts[0]}>"
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
        if isinstance(callee_t, StructDecl):
            # Struct construction: one argument per field, types must fit.
            if len(arg_types) != len(callee_t.fields):
                self.error(
                    f"{callee_t.name}() expects {len(callee_t.fields)} "
                    f"field(s), got {len(arg_types)}", node.line)
            else:
                for i, (f, at) in enumerate(zip(callee_t.fields, arg_types)):
                    ft = callee_t.field_types[f]
                    if not assignable(ft, at):
                        self.error(
                            f"field '{f}' of {callee_t.name} expects "
                            f"{type_name(ft)}, got {type_name(at)}",
                            node.args[i].line)
            return callee_t.name   # an instance's type is the struct's name
        if isinstance(callee_t, FuncType):
            if callee_t.params is None:
                return callee_t.ret  # bare `fn`: fully gradual, no arity check
            if isinstance(node.callee, (N.Identifier, N.Attribute)):
                fname = node.callee.name + "()"
            else:
                fname = "function"
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
        target_t = self._infer(node.target, scope)
        if isinstance(target_t, ModuleType):
            if node.name in target_t.members:
                return target_t.members[node.name]
            self.error(
                f"module '{target_t.name}' has no member '{node.name}'",
                node.line)
            return "any"
        decl = self.structs.get(target_t)
        if decl is not None:
            if node.name in decl.field_types:
                return decl.field_types[node.name]
            self.error(f"{decl.name} has no field '{node.name}'", node.line)
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
