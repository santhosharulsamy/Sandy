"""Runtime values and their display formatting for Sandy.

Sandy reuses Python's native types where possible:
  int   -> int
  float -> float
  string-> str
  bool  -> bool
  nil   -> None
  list  -> list
  map   -> dict

Callable values are represented by Function / BuiltinFunction below.
"""


class Function:
    """A user-defined Sandy function (closure)."""
    __slots__ = ("name", "params", "body", "closure", "param_types")

    def __init__(self, name, params, body, closure, param_types=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure  # defining environment
        # None means no annotations; otherwise aligned with params.
        self.param_types = param_types if (param_types and any(param_types)) else None

    def __repr__(self):
        return f"<fn {self.name}({', '.join(self.params)})>"


class BuiltinFunction:
    """A built-in function implemented in Python."""
    __slots__ = ("name", "fn", "arity")

    def __init__(self, name, fn, arity=None):
        self.name = name
        self.fn = fn
        self.arity = arity  # None = variadic; int or (min, max) tuple

    def __repr__(self):
        return f"<builtin {self.name}>"


class StructType:
    """A user-defined struct type (the value bound to the struct's name)."""
    __slots__ = ("name", "fields", "field_types")

    def __init__(self, name, fields, field_types):
        self.name = name
        self.fields = fields            # list of field names
        self.field_types = field_types  # aligned list (str or None)

    def __repr__(self):
        return f"<struct {self.name}>"


class StructInstance:
    """An instance of a struct: its type plus a field -> value mapping."""
    __slots__ = ("struct", "values")

    def __init__(self, struct, values):
        self.struct = struct
        self.values = values            # dict field -> value (insertion order)

    def __repr__(self):
        return to_str(self)


def type_name(value):
    if value is None:
        return "nil"
    if value is True or value is False:
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    if isinstance(value, StructInstance):
        return value.struct.name
    if isinstance(value, StructType):
        return "struct"
    if isinstance(value, (Function, BuiltinFunction)):
        return "function"
    return "unknown"


def is_truthy(value):
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) != 0
    if isinstance(value, (list, dict)):
        return len(value) != 0
    return True


def to_str(value):
    """Human-facing string form (what print shows)."""
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        # Show a clean float: 3.0 not 3, but avoid trailing noise.
        if value == int(value) and abs(value) < 1e16:
            return f"{value:.1f}"
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(to_repr(v) for v in value) + "]"
    if isinstance(value, dict):
        inner = ", ".join(f"{to_repr(k)}: {to_repr(v)}" for k, v in value.items())
        return "{" + inner + "}"
    if isinstance(value, StructInstance):
        inner = ", ".join(f"{k}={to_repr(v)}" for k, v in value.values.items())
        return f"{value.struct.name}({inner})"
    if isinstance(value, StructType):
        return f"<struct {value.name}>"
    if isinstance(value, (Function, BuiltinFunction)):
        return repr(value)
    return str(value)


def to_repr(value):
    """Form used inside containers (strings get quotes)."""
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return to_str(value)
