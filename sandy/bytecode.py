"""Bytecode instruction set and code objects for the Sandy VM.

Opcodes are small integers for fast dispatch. Each instruction is a
(op, arg) pair; a parallel `lines` list records the source line of each
instruction for error reporting.
"""

# --- opcodes ---
LOAD_CONST = 0
LOAD_NAME = 1
STORE_NAME = 2          # assign: update nearest binding, else define here
DEFINE_NAME = 3         # define in the current scope (params, funcs, for-var)
POP = 4

BUILD_LIST = 5
BUILD_MAP = 6
BUILD_INTERP = 7        # concatenate N string parts
STR_COERCE = 8          # convert top of stack to its display string

BINARY_ADD = 10
BINARY_SUB = 11
BINARY_MUL = 12
BINARY_DIV = 13
BINARY_MOD = 14
BINARY_POW = 15

# Type-specialized numeric ops: the compiler emits these only when it has
# *proven* both operands are numbers, so they skip all runtime type checks.
BINARY_ADD_NUM = 16
BINARY_SUB_NUM = 17
BINARY_MUL_NUM = 18

CMP_EQ = 20
CMP_NE = 21
CMP_LT = 22
CMP_GT = 23
CMP_LE = 24
CMP_GE = 25

CMP_LT_NUM = 26
CMP_GT_NUM = 27
CMP_LE_NUM = 28
CMP_GE_NUM = 29

UNARY_NEG = 30
UNARY_NOT = 31

JUMP = 40
JUMP_IF_FALSE = 41
JUMP_IF_FALSE_OR_POP = 42   # short-circuit 'and'
JUMP_IF_TRUE_OR_POP = 43    # short-circuit 'or'

GET_ITER = 50
FOR_ITER = 51           # arg = jump target when the iterator is exhausted

DUP_TWO = 60
INDEX_GET = 61
INDEX_SET = 62
GET_ATTR = 63

MAKE_FUNCTION = 70
CALL = 71               # arg = number of arguments
RETURN = 72

OPNAMES = {v: k for k, v in list(globals().items()) if isinstance(v, int)}

# Binary operator token-string -> opcode.
BINARY_OPS = {
    "+": BINARY_ADD, "-": BINARY_SUB, "*": BINARY_MUL,
    "/": BINARY_DIV, "%": BINARY_MOD, "**": BINARY_POW,
    "==": CMP_EQ, "!=": CMP_NE, "<": CMP_LT, ">": CMP_GT,
    "<=": CMP_LE, ">=": CMP_GE,
}


class CodeObject:
    """A compiled chunk of Sandy code (a program or a function body)."""
    __slots__ = ("name", "params", "param_types", "ops", "consts", "lines")

    def __init__(self, name, params, ops, consts, lines, param_types=None):
        self.name = name
        self.params = params
        self.param_types = param_types  # None means no annotations (no checks)
        self.ops = ops        # list of (op, arg)
        self.consts = consts  # list of constant values (incl. nested CodeObjects)
        self.lines = lines    # parallel to ops

    def __repr__(self):
        return f"<code {self.name} ({len(self.ops)} ops)>"


def disassemble(code, indent=0):
    """Return a human-readable listing of a CodeObject (for debugging)."""
    pad = "  " * indent
    out = [f"{pad}code {code.name}({', '.join(code.params)}):"]
    for i, (op, arg) in enumerate(code.ops):
        name = OPNAMES.get(op, str(op))
        if arg is None:
            out.append(f"{pad}  {i:3} {name}")
        elif isinstance(arg, int) and op == LOAD_CONST:
            out.append(f"{pad}  {i:3} {name} {arg} ({code.consts[arg]!r})")
        else:
            out.append(f"{pad}  {i:3} {name} {arg!r}")
    for c in code.consts:
        if isinstance(c, CodeObject):
            out.append(disassemble(c, indent + 1))
    return "\n".join(out)
