"""Native backend: transpile the typed scalar core of Sandy to C.

This is Stage 4 of the roadmap in miniature. A full native compiler for all
of Sandy (closures, dynamic `any`, lists/maps) is a large project; this
backend deliberately handles the *statically typed scalar subset* — exactly
where types make native code generation sound and worthwhile:

    * types int, float, bool, string (string literals only)
    * functions with typed parameters and a return type, incl. recursion
    * arithmetic, comparisons, and/or/not, unary minus
    * if / elif / else, while, for i in range(...), break, continue, return
    * print(...) of scalars and interpolated strings

Anything outside this subset raises NativeUnsupported with a clear message,
pointing the user back to the `--vm` engine. The generated C is compiled with
the system C compiler at -O2, so typed numeric programs run at native speed.

Semantics are matched to the interpreter on purpose: `/` is always float,
`%` is Python-style floor modulo, and floats print as the interpreter shows
them (integral values as `N.0`).
"""

from .errors import SandyError
from . import nodes as N


class NativeUnsupported(SandyError):
    def format(self, kind="NativeError"):
        return super().format(kind)


C_TYPE = {"int": "long long", "float": "double", "bool": "int",
          "string": "const char*"}
_ZERO = {"int": "0", "float": "0.0", "bool": "0", "string": "NULL"}
_NUM = ("int", "float")

_HELPERS = r"""
static long long sy_ipow(long long base, long long exp) {
    long long r = 1;
    while (exp > 0) { if (exp & 1) r *= base; base *= base; exp >>= 1; }
    return r;
}
static long long sy_imod(long long a, long long b) {
    long long m = a % b;
    if (m != 0 && ((m < 0) != (b < 0))) m += b;
    return m;
}
static double sy_fmod(double a, double b) {
    double m = fmod(a, b);
    if (m != 0 && ((m < 0) != (b < 0))) m += b;
    return m;
}
static double sy_divf(double a, double b, int line) {
    if (b == 0) { fprintf(stderr, "RuntimeError (line %d): division by zero\n", line); exit(1); }
    return a / b;
}
static long long sy_ckz(long long b, int line) {
    if (b == 0) { fprintf(stderr, "RuntimeError (line %d): modulo by zero\n", line); exit(1); }
    return b;
}
static void sy_pf(double v) {
    if (v == (long long)v && v < 1e16 && v > -1e16) printf("%.1f", v);
    else printf("%g", v);
}
"""


def _int_literal(node):
    """Return the value of an integer literal (allowing a unary minus), or
    None if the node isn't a compile-time integer constant."""
    if isinstance(node, N.IntLit):
        return node.value
    if isinstance(node, N.UnaryOp) and node.op == "-" \
            and isinstance(node.operand, N.IntLit):
        return -node.operand.value
    return None


def _cstr(s):
    out = ['"']
    for ch in s:
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
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


class _Sig:
    __slots__ = ("params", "ptypes", "ret")

    def __init__(self, params, ptypes, ret):
        self.params = params
        self.ptypes = ptypes
        self.ret = ret  # sandy type name or None (void)


class CBackend:
    def __init__(self):
        self.funcs = {}

    # -- entry --
    def compile(self, program):
        funcdefs = [s for s in program.statements if isinstance(s, N.FuncDef)]
        topstmts = [s for s in program.statements if not isinstance(s, N.FuncDef)]
        for fd in funcdefs:
            self._register(fd)
        sections = [self._emit_function(fd) for fd in funcdefs]
        main_body = self._emit_main(topstmts)
        return self._assemble(sections, main_body)

    def _register(self, fd):
        for pt in fd.param_types:
            if pt not in C_TYPE:
                raise NativeUnsupported(
                    f"native function '{fd.name}' needs typed parameters "
                    f"(int/float/bool/string); got '{pt or 'any'}'", fd.line)
        ret = fd.ret_type
        if ret is not None and ret not in C_TYPE:
            raise NativeUnsupported(
                f"native function '{fd.name}' has unsupported return type "
                f"'{ret}'", fd.line)
        self.funcs[fd.name] = _Sig(fd.params, list(fd.param_types), ret)

    # -- functions --
    def _emit_function(self, fd):
        sig = self.funcs[fd.name]
        scope = dict(zip(sig.params, sig.ptypes))
        locals_ = self._infer_locals(fd.body, scope, sig)
        params = ", ".join(f"{C_TYPE[t]} {n}" for n, t in zip(sig.params, sig.ptypes))
        ret_c = C_TYPE[sig.ret] if sig.ret else "void"
        lines = [f"{ret_c} {fd.name}({params or 'void'}) {{"]
        for n, t in locals_:
            lines.append(f"    {C_TYPE[t]} {n} = {_ZERO[t]};")
        lines += self._emit_block(fd.body, scope, sig, 1)
        lines.append("}")
        return "\n".join(lines)

    def _emit_main(self, stmts):
        scope = {}
        pseudo = _Sig([], [], None)
        block = N.Block(stmts)
        locals_ = self._infer_locals(block, scope, pseudo)
        lines = ["int main(void) {"]
        for n, t in locals_:
            lines.append(f"    {C_TYPE[t]} {n} = {_ZERO[t]};")
        lines += self._emit_block(block, scope, pseudo, 1)
        lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines)

    # -- local hoisting / type inference --
    def _infer_locals(self, block, scope, sig):
        found = []

        def visit(b):
            for s in b.statements:
                t = type(s)
                if t is N.Assign:
                    if not isinstance(s.target, N.Identifier):
                        raise NativeUnsupported(
                            "native mode supports only simple variable "
                            "assignment", s.line)
                    name = s.target.name
                    if s.annotation is not None:
                        vt = s.annotation
                        if vt not in C_TYPE:
                            raise NativeUnsupported(
                                f"unsupported native type '{vt}'", s.line)
                    elif s.op != "=":  # compound needs existing var
                        if name not in scope:
                            raise NativeUnsupported(
                                f"'{name}' used before assignment", s.line)
                        vt = scope[name]
                    else:
                        vt = self._type(s.value, scope, sig)
                    if name not in scope:
                        scope[name] = vt
                        found.append((name, vt))
                    else:
                        self._check_assignable(scope[name], vt, s.line, name)
                elif t is N.If:
                    for _, blk in s.branches:
                        visit(blk)
                    if s.else_block is not None:
                        visit(s.else_block)
                elif t is N.While:
                    visit(s.body)
                elif t is N.For:
                    if s.var not in scope:
                        scope[s.var] = "int"
                        found.append((s.var, "int"))
                    visit(s.body)
                elif t is N.FuncDef:
                    raise NativeUnsupported(
                        "nested functions are not supported in native mode yet",
                        s.line)
        visit(block)
        return found

    # -- statements --
    def _emit_block(self, block, scope, sig, indent):
        lines = []
        for s in block.statements:
            lines += self._emit_stmt(s, scope, sig, indent)
        return lines

    def _emit_stmt(self, s, scope, sig, indent):
        ind = "    " * indent
        t = type(s)
        if t is N.ExprStmt:
            e = s.expr
            if isinstance(e, N.Call) and isinstance(e.callee, N.Identifier) \
                    and e.callee.name == "print":
                return self._emit_print(e.args, scope, sig, ind)
            code, _ = self._expr(e, scope, sig, allow_void=True)
            return [f"{ind}{code};"]
        if t is N.Assign:
            name = s.target.name
            if s.op == "=":
                value = s.value
            else:
                value = N.BinaryOp(s.op[0], s.target, s.value, s.line)
            code, vt = self._expr(value, scope, sig)
            declared = scope[name]
            self._check_assignable(declared, vt, s.line, name)
            if declared == "float" and vt == "int":
                code = f"(double)({code})"
            return [f"{ind}{name} = {code};"]
        if t is N.If:
            lines = []
            for i, (cond, blk) in enumerate(s.branches):
                cc = self._bool(cond, scope, sig)
                kw = "if" if i == 0 else "} else if"
                lines.append(f"{ind}{kw} ({cc}) {{")
                lines += self._emit_block(blk, scope, sig, indent + 1)
            if s.else_block is not None:
                lines.append(f"{ind}}} else {{")
                lines += self._emit_block(s.else_block, scope, sig, indent + 1)
            lines.append(f"{ind}}}")
            return lines
        if t is N.While:
            cc = self._bool(s.cond, scope, sig)
            lines = [f"{ind}while ({cc}) {{"]
            lines += self._emit_block(s.body, scope, sig, indent + 1)
            lines.append(f"{ind}}}")
            return lines
        if t is N.For:
            return self._emit_for(s, scope, sig, indent)
        if t is N.Return:
            if s.value is None:
                return [f"{ind}return;"]
            if sig.ret is None:
                raise NativeUnsupported(
                    "this native function returns a value but has no return "
                    "type annotation", s.line)
            code, vt = self._expr(s.value, scope, sig)
            self._check_assignable(sig.ret, vt, s.line, "return value")
            if sig.ret == "float" and vt == "int":
                code = f"(double)({code})"
            return [f"{ind}return {code};"]
        if t is N.Break:
            return [f"{ind}break;"]
        if t is N.Continue:
            return [f"{ind}continue;"]
        raise NativeUnsupported(
            f"{type(s).__name__} is not supported in native mode",
            getattr(s, "line", None))

    def _emit_for(self, s, scope, sig, indent):
        ind = "    " * indent
        it = s.iterable
        if not (isinstance(it, N.Call) and isinstance(it.callee, N.Identifier)
                and it.callee.name == "range"):
            raise NativeUnsupported(
                "native for-loops must iterate over range(...)", s.line)
        args = it.args
        if not 1 <= len(args) <= 3:
            raise NativeUnsupported("range expects 1 to 3 arguments", s.line)
        for a in args:
            if self._type(a, scope, sig) != "int":
                raise NativeUnsupported("range arguments must be int", s.line)
        v = s.var
        if len(args) == 1:
            start, stop, step = "0", self._expr(args[0], scope, sig)[0], "1"
        elif len(args) == 2:
            start = self._expr(args[0], scope, sig)[0]
            stop = self._expr(args[1], scope, sig)[0]
            step = "1"
        else:
            start = self._expr(args[0], scope, sig)[0]
            stop = self._expr(args[1], scope, sig)[0]
            step_val = _int_literal(args[2])
            if step_val is None or step_val == 0:
                raise NativeUnsupported(
                    "native range step must be a non-zero integer literal",
                    s.line)
            step = str(step_val)
        cmp = ">" if step.startswith("-") else "<"
        lines = [f"{ind}for ({v} = {start}; {v} {cmp} {stop}; {v} += {step}) {{"]
        lines += self._emit_block(s.body, scope, sig, indent + 1)
        lines.append(f"{ind}}}")
        return lines

    def _emit_print(self, args, scope, sig, ind):
        lines = []
        for i, arg in enumerate(args):
            if i > 0:
                lines.append(f'{ind}fputs(" ", stdout);')
            lines += self._emit_value(arg, scope, sig, ind)
        lines.append(f'{ind}fputs("\\n", stdout);')
        return lines

    def _emit_value(self, expr, scope, sig, ind):
        if isinstance(expr, N.InterpStr):
            out = []
            for kind, payload in expr.parts:
                if kind == "lit":
                    out.append(f"{ind}fputs({_cstr(payload)}, stdout);")
                else:
                    out += self._emit_scalar(payload, scope, sig, ind)
            return out
        return self._emit_scalar(expr, scope, sig, ind)

    def _emit_scalar(self, expr, scope, sig, ind):
        code, t = self._expr(expr, scope, sig)
        if t == "int":
            return [f'{ind}printf("%lld", (long long)({code}));']
        if t == "float":
            return [f"{ind}sy_pf({code});"]
        if t == "bool":
            return [f'{ind}fputs(({code}) ? "true" : "false", stdout);']
        if t == "string":
            return [f"{ind}fputs({code}, stdout);"]
        raise NativeUnsupported(f"cannot print a {t} value in native mode",
                                getattr(expr, "line", None))

    # -- expressions: return (c_code, sandy_type) --
    def _expr(self, e, scope, sig, allow_void=False):
        t = type(e)
        if t is N.IntLit:
            return (f"{e.value}LL", "int")
        if t is N.FloatLit:
            return (repr(float(e.value)), "float")
        if t is N.BoolLit:
            return ("1" if e.value else "0", "bool")
        if t is N.StrLit:
            return (_cstr(e.value), "string")
        if t is N.Identifier:
            if e.name not in scope:
                raise NativeUnsupported(
                    f"'{e.name}' is not a supported native value here "
                    f"(only parameters, locals, and typed globals)", e.line)
            return (e.name, scope[e.name])
        if t is N.UnaryOp:
            code, ct = self._expr(e.operand, scope, sig)
            if e.op == "-":
                self._need_num(ct, e.line, "negate")
                return (f"(-{code})", ct)
            # not
            self._need_bool(ct, e.line)
            return (f"(!{code})", "bool")
        if t is N.LogicalOp:
            lc = self._bool(e.left, scope, sig)
            rc = self._bool(e.right, scope, sig)
            op = "&&" if e.op == "and" else "||"
            return (f"({lc} {op} {rc})", "bool")
        if t is N.BinaryOp:
            return self._binary(e, scope, sig)
        if t is N.Call:
            return self._call(e, scope, sig, allow_void)
        raise NativeUnsupported(
            f"{type(e).__name__} expressions are not supported in native mode",
            getattr(e, "line", None))

    def _binary(self, e, scope, sig):
        lc, lt = self._expr(e.left, scope, sig)
        rc, rt = self._expr(e.right, scope, sig)
        op = e.op
        line = e.line
        if op in ("==", "!="):
            if lt == "string" and rt == "string":
                cmp = "==" if op == "==" else "!="
                return (f"(strcmp({lc}, {rc}) {cmp} 0)", "bool")
            if lt in _NUM and rt in _NUM or (lt == rt == "bool"):
                return (f"({lc} {op} {rc})", "bool")
            raise NativeUnsupported(
                f"cannot compare {lt} and {rt} in native mode", line)
        if op in ("<", ">", "<=", ">="):
            self._need_num(lt, line, "compare"); self._need_num(rt, line, "compare")
            return (f"({lc} {op} {rc})", "bool")
        # arithmetic
        self._need_num(lt, line, "use arithmetic on")
        self._need_num(rt, line, "use arithmetic on")
        rtype = "int" if (lt == "int" and rt == "int") else "float"
        if op in ("+", "-", "*"):
            return (f"({lc} {op} {rc})", rtype)
        if op == "/":
            return (f"sy_divf((double)({lc}), (double)({rc}), {line})", "float")
        if op == "%":
            if rtype == "int":
                return (f"sy_imod({lc}, sy_ckz({rc}, {line}))", "int")
            return (f"sy_fmod((double)({lc}), (double)({rc}))", "float")
        if op == "**":
            if rtype == "int":
                return (f"sy_ipow({lc}, {rc})", "int")
            return (f"pow((double)({lc}), (double)({rc}))", "float")
        raise NativeUnsupported(f"operator '{op}' not supported natively", line)

    def _call(self, e, scope, sig, allow_void):
        if not isinstance(e.callee, N.Identifier):
            raise NativeUnsupported(
                "native calls must be to named functions", e.line)
        name = e.callee.name
        if name not in self.funcs:
            raise NativeUnsupported(
                f"'{name}' cannot be called in native mode (only user "
                f"functions are supported)", e.line)
        fn = self.funcs[name]
        if len(e.args) != len(fn.params):
            raise NativeUnsupported(
                f"{name}() expects {len(fn.params)} argument(s), "
                f"got {len(e.args)}", e.line)
        parts = []
        for arg, pt in zip(e.args, fn.ptypes):
            ac, at = self._expr(arg, scope, sig)
            self._check_assignable(pt, at, e.line, f"argument to {name}")
            if pt == "float" and at == "int":
                ac = f"(double)({ac})"
            parts.append(ac)
        if fn.ret is None and not allow_void:
            raise NativeUnsupported(
                f"{name}() returns nothing and cannot be used as a value",
                e.line)
        return (f"{name}({', '.join(parts)})", fn.ret)

    # -- helpers --
    def _bool(self, expr, scope, sig):
        code, t = self._expr(expr, scope, sig)
        if t != "bool":
            raise NativeUnsupported(
                f"condition must be a bool in native mode, got {t}",
                getattr(expr, "line", None))
        return code

    def _need_num(self, t, line, verb):
        if t not in _NUM:
            raise NativeUnsupported(f"cannot {verb} a {t} in native mode", line)

    def _need_bool(self, t, line):
        if t != "bool":
            raise NativeUnsupported(f"expected bool, got {t}", line)

    def _check_assignable(self, declared, actual, line, what):
        if declared == actual:
            return
        if declared == "float" and actual == "int":
            return
        raise NativeUnsupported(
            f"{what}: expected {declared}, got {actual}", line)

    def _type(self, e, scope, sig):
        return self._expr(e, scope, sig, allow_void=True)[1]

    def _assemble(self, sections, main_body):
        protos = []
        for name, sig in self.funcs.items():
            params = ", ".join(C_TYPE[t] for t in sig.ptypes) or "void"
            ret_c = C_TYPE[sig.ret] if sig.ret else "void"
            protos.append(f"{ret_c} {name}({params});")
        parts = [
            "#include <stdio.h>",
            "#include <math.h>",
            "#include <string.h>",
            "#include <stdlib.h>",
            _HELPERS,
            "\n".join(protos),
            "",
            "\n\n".join(sections),
            "",
            main_body,
            "",
        ]
        return "\n".join(parts)


def to_c(program):
    return CBackend().compile(program)
