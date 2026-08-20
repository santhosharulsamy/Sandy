"""A stack-based virtual machine that executes Sandy bytecode.

The VM reuses the tree-walking Interpreter for its runtime helpers
(operators, indexing, builtins, value formatting) so both engines share
exactly one set of semantics. What the VM changes is *how* code is driven:
a flat instruction loop with an explicit frame stack, instead of recursive
AST walking. That removes per-node Python call overhead and lets hot
arithmetic take inlined fast paths.

The opcode dispatch below is ordered by how often each instruction runs in
tight loops (name/const loads, jumps, the loop step, add/compare) so the
hottest paths are found after the fewest comparisons.
"""

from .errors import RuntimeErrorSandy
from .interpreter import Interpreter, Environment
from .values import BuiltinFunction, is_truthy, to_str, type_name
from .builtins import resolve_method
from . import bytecode as B

_SENTINEL = object()


class VMFunction:
    __slots__ = ("name", "params", "param_types", "code", "closure")

    def __init__(self, name, params, code, closure):
        self.name = name
        self.params = params
        self.param_types = code.param_types
        self.code = code
        self.closure = closure

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.params)})>"


class _Frame:
    __slots__ = ("code", "ip", "stack", "env")

    def __init__(self, code, env):
        self.code = code
        self.ip = 0
        self.stack = []
        self.env = env


class VM:
    def __init__(self, out=None):
        # Reuse an Interpreter purely for its runtime helpers + builtins.
        self.rt = Interpreter(out=out)
        self.genv = self.rt.globals

    def run(self, code):
        frames = [_Frame(code, self.genv)]
        rt = self.rt
        _binary = rt._binary
        _truthy = is_truthy

        while frames:
            frame = frames[-1]
            ops = frame.code.ops
            consts = frame.code.consts
            lines = frame.code.lines
            stack = frame.stack
            env = frame.env
            push = stack.append
            switched = False
            ip = frame.ip

            while True:
                op, arg = ops[ip]
                ip += 1

                # --- hottest: loads ---
                if op == B.LOAD_NAME:
                    e = env
                    while e is not None:
                        d = e.vars
                        if arg in d:
                            push(d[arg])
                            break
                        e = e.parent
                    else:
                        env.get(arg, lines[ip - 1])  # raises with a suggestion
                elif op == B.LOAD_CONST:
                    push(consts[arg])

                # --- stack / control that runs every loop turn ---
                elif op == B.POP:
                    stack.pop()
                elif op == B.JUMP:
                    ip = arg
                elif op == B.JUMP_IF_FALSE:
                    if not _truthy(stack.pop()):
                        ip = arg
                elif op == B.STORE_NAME:
                    env.assign(arg, stack.pop())
                elif op == B.FOR_ITER:
                    nxt = next(stack[-1], _SENTINEL)
                    if nxt is _SENTINEL:
                        stack.pop()
                        ip = arg
                    else:
                        push(nxt)
                elif op == B.DEFINE_NAME:
                    env.vars[arg] = stack.pop()

                # --- hot arithmetic / comparison (specialized + generic) ---
                # The specialized *_NUM ops are emitted when the compiler has
                # proven both operands numeric, so the common path skips type
                # dispatch. They stay sound under gradual typing via a cheap
                # guard: CPython 3.11 exception tables make the try free when
                # no error occurs, and any surprise value falls back to the
                # fully-checked operator (raising the proper Sandy error). Each
                # *_NUM sits next to its generic twin to keep dispatch short
                # for both typed and untyped code.
                elif op == B.BINARY_ADD_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] + b
                    except TypeError:
                        stack[-1] = _binary("+", stack[-1], b, lines[ip - 1])
                elif op == B.BINARY_ADD:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a + b)
                    else:
                        push(_binary("+", a, b, lines[ip - 1]))
                elif op == B.CMP_LT_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] < b
                    except TypeError:
                        stack[-1] = _binary("<", stack[-1], b, lines[ip - 1])
                elif op == B.CMP_LT:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a < b)
                    else:
                        push(_binary("<", a, b, lines[ip - 1]))
                elif op == B.BINARY_SUB_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] - b
                    except TypeError:
                        stack[-1] = _binary("-", stack[-1], b, lines[ip - 1])
                elif op == B.BINARY_SUB:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a - b)
                    else:
                        push(_binary("-", a, b, lines[ip - 1]))

                # --- calls / returns (once per invocation) ---
                elif op == B.CALL:
                    argc = arg
                    if argc:
                        args = stack[-argc:]
                        del stack[-argc:]
                    else:
                        args = []
                    callee = stack.pop()
                    tc = type(callee)
                    if tc is VMFunction:
                        if len(args) != len(callee.params):
                            raise RuntimeErrorSandy(
                                f"{callee.name}() expects {len(callee.params)} "
                                f"argument(s), got {len(args)}", lines[ip - 1])
                        newenv = Environment(callee.closure)
                        nv = newenv.vars
                        for p, a in zip(callee.params, args):
                            nv[p] = a
                        frame.ip = ip
                        frames.append(_Frame(callee.code, newenv))
                        switched = True
                        break
                    elif tc is BuiltinFunction:
                        rt._check_arity(callee, args, lines[ip - 1])
                        push(callee.fn(args, lines[ip - 1]))
                    else:
                        raise RuntimeErrorSandy(
                            f"'{type_name(callee)}' value is not callable",
                            lines[ip - 1])
                elif op == B.RETURN:
                    retval = stack.pop()
                    frames.pop()
                    if not frames:
                        return retval
                    frames[-1].stack.append(retval)
                    switched = True
                    break

                # --- remaining comparisons ---
                elif op == B.CMP_EQ:
                    b = stack.pop(); a = stack.pop()
                    push(rt._equals(a, b))
                elif op == B.CMP_GT_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] > b
                    except TypeError:
                        stack[-1] = _binary(">", stack[-1], b, lines[ip - 1])
                elif op == B.CMP_GT:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a > b)
                    else:
                        push(_binary(">", a, b, lines[ip - 1]))
                elif op == B.CMP_NE:
                    b = stack.pop(); a = stack.pop()
                    push(not rt._equals(a, b))
                elif op == B.CMP_LE_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] <= b
                    except TypeError:
                        stack[-1] = _binary("<=", stack[-1], b, lines[ip - 1])
                elif op == B.CMP_LE:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a <= b)
                    else:
                        push(_binary("<=", a, b, lines[ip - 1]))
                elif op == B.CMP_GE_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] >= b
                    except TypeError:
                        stack[-1] = _binary(">=", stack[-1], b, lines[ip - 1])
                elif op == B.CMP_GE:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a >= b)
                    else:
                        push(_binary(">=", a, b, lines[ip - 1]))

                # --- remaining arithmetic ---
                elif op == B.BINARY_MUL_NUM:
                    b = stack.pop()
                    try:
                        stack[-1] = stack[-1] * b
                    except TypeError:
                        stack[-1] = _binary("*", stack[-1], b, lines[ip - 1])
                elif op == B.BINARY_MUL:
                    b = stack.pop(); a = stack.pop()
                    ta = type(a); tb = type(b)
                    if (ta is int or ta is float) and (tb is int or tb is float):
                        push(a * b)
                    else:
                        push(_binary("*", a, b, lines[ip - 1]))
                elif op == B.BINARY_DIV:
                    b = stack.pop(); a = stack.pop()
                    push(_binary("/", a, b, lines[ip - 1]))
                elif op == B.BINARY_MOD:
                    b = stack.pop(); a = stack.pop()
                    push(_binary("%", a, b, lines[ip - 1]))
                elif op == B.BINARY_POW:
                    b = stack.pop(); a = stack.pop()
                    push(_binary("**", a, b, lines[ip - 1]))

                # --- iteration setup, indexing, short-circuit ---
                elif op == B.GET_ITER:
                    push(iter(rt._as_iterable(stack.pop(), lines[ip - 1])))
                elif op == B.INDEX_GET:
                    idx = stack.pop(); cont = stack.pop()
                    push(rt._index_get(cont, idx, lines[ip - 1]))
                elif op == B.INDEX_SET:
                    val = stack.pop(); idx = stack.pop(); cont = stack.pop()
                    rt._index_set(cont, idx, val, lines[ip - 1])
                elif op == B.JUMP_IF_FALSE_OR_POP:
                    if not _truthy(stack[-1]):
                        ip = arg
                    else:
                        stack.pop()
                elif op == B.JUMP_IF_TRUE_OR_POP:
                    if _truthy(stack[-1]):
                        ip = arg
                    else:
                        stack.pop()
                elif op == B.DUP_TWO:
                    push(stack[-2]); push(stack[-2])

                # --- unary, building, attrs, functions ---
                elif op == B.UNARY_NOT:
                    push(not _truthy(stack.pop()))
                elif op == B.UNARY_NEG:
                    a = stack.pop()
                    if type(a) is int or type(a) is float:
                        push(-a)
                    else:
                        raise RuntimeErrorSandy(
                            f"cannot negate a {type_name(a)}", lines[ip - 1])
                elif op == B.GET_ATTR:
                    push(resolve_method(rt, stack.pop(), arg, lines[ip - 1]))
                elif op == B.BUILD_LIST:
                    if arg:
                        items = stack[-arg:]
                        del stack[-arg:]
                        push(items)
                    else:
                        push([])
                elif op == B.BUILD_MAP:
                    d = {}
                    if arg:
                        flat = stack[-2 * arg:]
                        del stack[-2 * arg:]
                        for i in range(0, len(flat), 2):
                            k = flat[i]
                            if isinstance(k, (list, dict)):
                                raise RuntimeErrorSandy(
                                    f"map key cannot be a {type_name(k)}",
                                    lines[ip - 1])
                            d[k] = flat[i + 1]
                    push(d)
                elif op == B.BUILD_INTERP:
                    if arg:
                        parts = stack[-arg:]
                        del stack[-arg:]
                        push("".join(parts))
                    else:
                        push("")
                elif op == B.STR_COERCE:
                    push(to_str(stack.pop()))
                elif op == B.MAKE_FUNCTION:
                    tmpl = consts[arg]
                    push(VMFunction(tmpl.name, tmpl.params, tmpl, env))
                else:
                    raise RuntimeErrorSandy(f"unknown opcode {op}", lines[ip - 1])

            if switched:
                continue
        return None


def run_program(program, out=None):
    from .compiler import compile_program
    code = compile_program(program)
    return VM(out=out).run(code)
