"""Built-in functions and type methods for Sandy.

Global builtins (print, len, range, ...) are created by make_builtins().
Method-style calls (text.upper(), list.push(x), ...) are resolved by
resolve_method(), which returns a bound BuiltinFunction.
"""

import math

from .errors import RuntimeErrorSandy
from .values import BuiltinFunction, to_str, type_name, is_truthy


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def make_builtins(interp):
    B = {}

    def reg(name, arity):
        def deco(fn):
            B[name] = BuiltinFunction(name, fn, arity)
            return fn
        return deco

    @reg("print", None)
    def _print(args, line):
        text = " ".join(to_str(a) for a in args)
        if interp.out is not None:
            interp.out.write(text + "\n")
        else:
            print(text)
        return None

    @reg("input", (0, 1))
    def _input(args, line):
        prompt = to_str(args[0]) if args else ""
        try:
            return input(prompt)
        except EOFError:
            return ""

    @reg("len", 1)
    def _len(args, line):
        v = args[0]
        if isinstance(v, (str, list, dict)):
            return len(v)
        raise RuntimeErrorSandy(f"cannot take len of a {type_name(v)}", line)

    @reg("type", 1)
    def _type(args, line):
        return type_name(args[0])

    @reg("str", 1)
    def _str(args, line):
        return to_str(args[0])

    @reg("int", 1)
    def _int(args, line):
        v = args[0]
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            try:
                return int(v.strip())
            except ValueError:
                raise RuntimeErrorSandy(f"cannot convert {v!r} to int", line)
        raise RuntimeErrorSandy(f"cannot convert {type_name(v)} to int", line)

    @reg("float", 1)
    def _float(args, line):
        v = args[0]
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.strip())
            except ValueError:
                raise RuntimeErrorSandy(f"cannot convert {v!r} to float", line)
        raise RuntimeErrorSandy(f"cannot convert {type_name(v)} to float", line)

    @reg("bool", 1)
    def _bool(args, line):
        return is_truthy(args[0])

    @reg("range", (1, 3))
    def _range(args, line):
        for a in args:
            if not _is_int(a):
                raise RuntimeErrorSandy("range() arguments must be ints", line)
        if len(args) == 1:
            return list(range(args[0]))
        if len(args) == 2:
            return list(range(args[0], args[1]))
        if args[2] == 0:
            raise RuntimeErrorSandy("range() step cannot be zero", line)
        return list(range(args[0], args[1], args[2]))

    @reg("abs", 1)
    def _abs(args, line):
        v = args[0]
        if not _is_num(v):
            raise RuntimeErrorSandy(f"abs() needs a number, got {type_name(v)}", line)
        return abs(v)

    @reg("min", None)
    def _min(args, line):
        return _reduce_minmax(args, line, min, "min")

    @reg("max", None)
    def _max(args, line):
        return _reduce_minmax(args, line, max, "max")

    def _reduce_minmax(args, line, fn, name):
        if len(args) == 1 and isinstance(args[0], list):
            items = args[0]
        else:
            items = args
        if not items:
            raise RuntimeErrorSandy(f"{name}() needs at least one value", line)
        for it in items:
            if not _is_num(it):
                raise RuntimeErrorSandy(f"{name}() needs numbers", line)
        return fn(items)

    @reg("sum", 1)
    def _sum(args, line):
        v = args[0]
        if not isinstance(v, list):
            raise RuntimeErrorSandy("sum() needs a list", line)
        total = 0
        for it in v:
            if not _is_num(it):
                raise RuntimeErrorSandy("sum() needs a list of numbers", line)
            total += it
        return total

    @reg("round", (1, 2))
    def _round(args, line):
        v = args[0]
        if not _is_num(v):
            raise RuntimeErrorSandy("round() needs a number", line)
        if len(args) == 2:
            if not _is_int(args[1]):
                raise RuntimeErrorSandy("round() digits must be an int", line)
            return round(v, args[1])
        return round(v)

    @reg("sqrt", 1)
    def _sqrt(args, line):
        v = args[0]
        if not _is_num(v):
            raise RuntimeErrorSandy("sqrt() needs a number", line)
        if v < 0:
            raise RuntimeErrorSandy("sqrt() of a negative number", line)
        return math.sqrt(v)

    @reg("floor", 1)
    def _floor(args, line):
        if not _is_num(args[0]):
            raise RuntimeErrorSandy("floor() needs a number", line)
        return math.floor(args[0])

    @reg("ceil", 1)
    def _ceil(args, line):
        if not _is_num(args[0]):
            raise RuntimeErrorSandy("ceil() needs a number", line)
        return math.ceil(args[0])

    @reg("pow", 2)
    def _pow(args, line):
        a, b = args
        if not (_is_num(a) and _is_num(b)):
            raise RuntimeErrorSandy("pow() needs numbers", line)
        return a ** b

    # -- list helpers as globals too --
    @reg("push", 2)
    def _push(args, line):
        lst, val = args
        if not isinstance(lst, list):
            raise RuntimeErrorSandy("push() needs a list", line)
        lst.append(val)
        return lst

    @reg("pop", (1, 2))
    def _pop(args, line):
        lst = args[0]
        if not isinstance(lst, list):
            raise RuntimeErrorSandy("pop() needs a list", line)
        if not lst:
            raise RuntimeErrorSandy("pop() from empty list", line)
        if len(args) == 2:
            if not _is_int(args[1]):
                raise RuntimeErrorSandy("pop() index must be an int", line)
            idx = args[1]
            if idx < 0 or idx >= len(lst):
                raise RuntimeErrorSandy(f"pop() index {idx} out of range", line)
            return lst.pop(idx)
        return lst.pop()

    @reg("keys", 1)
    def _keys(args, line):
        m = args[0]
        if not isinstance(m, dict):
            raise RuntimeErrorSandy("keys() needs a map", line)
        return list(m.keys())

    @reg("values", 1)
    def _values(args, line):
        m = args[0]
        if not isinstance(m, dict):
            raise RuntimeErrorSandy("values() needs a map", line)
        return list(m.values())

    @reg("has", 2)
    def _has(args, line):
        container, item = args
        if isinstance(container, dict):
            return item in container
        if isinstance(container, (list, str)):
            return item in container
        raise RuntimeErrorSandy(f"has() cannot search a {type_name(container)}", line)

    @reg("upper", 1)
    def _upper(args, line):
        return _need_str(args[0], "upper", line).upper()

    @reg("lower", 1)
    def _lower(args, line):
        return _need_str(args[0], "lower", line).lower()

    @reg("trim", 1)
    def _trim(args, line):
        return _need_str(args[0], "trim", line).strip()

    @reg("split", (1, 2))
    def _split(args, line):
        s = _need_str(args[0], "split", line)
        if len(args) == 2:
            sep = _need_str(args[1], "split", line)
            return s.split(sep)
        return s.split()

    @reg("join", 2)
    def _join(args, line):
        lst, sep = args
        if not isinstance(lst, list):
            raise RuntimeErrorSandy("join() needs a list", line)
        sep = _need_str(sep, "join", line)
        return sep.join(to_str(x) for x in lst)

    # -- file input / output --
    @reg("read_file", 1)
    def _read_file(args, line):
        path = _need_str(args[0], "read_file", line)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            raise RuntimeErrorSandy(f"cannot read {path!r}: {e.strerror}", line)

    @reg("read_lines", 1)
    def _read_lines(args, line):
        path = _need_str(args[0], "read_lines", line)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().splitlines()
        except OSError as e:
            raise RuntimeErrorSandy(f"cannot read {path!r}: {e.strerror}", line)

    @reg("write_file", 2)
    def _write_file(args, line):
        path = _need_str(args[0], "write_file", line)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_str(args[1]))
        except OSError as e:
            raise RuntimeErrorSandy(f"cannot write {path!r}: {e.strerror}", line)
        return None

    @reg("append_file", 2)
    def _append_file(args, line):
        path = _need_str(args[0], "append_file", line)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(to_str(args[1]))
        except OSError as e:
            raise RuntimeErrorSandy(f"cannot append {path!r}: {e.strerror}", line)
        return None

    return B


def _need_str(v, name, line):
    if not isinstance(v, str):
        raise RuntimeErrorSandy(f"{name}() needs a string, got {type_name(v)}", line)
    return v


# ---- method-style dispatch (obj.method(...)) ----

def resolve_method(interp, target, name, line):
    """Return a BuiltinFunction bound to `target` for `target.name(...)`."""
    methods = _METHODS.get(_kind(target))
    if methods and name in methods:
        impl = methods[name]

        def bound(args, line, _impl=impl, _t=target):
            return _impl(_t, args, line)

        return BuiltinFunction(f"{name}", bound, None)
    raise RuntimeErrorSandy(
        f"{type_name(target)} has no method '{name}'", line)


def _kind(v):
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "map"
    return type_name(v)


def _m_arity(args, n, name, line):
    if len(args) != n:
        raise RuntimeErrorSandy(
            f"{name}() expects {n} argument(s), got {len(args)}", line)


_METHODS = {
    "string": {
        "upper": lambda t, a, l: t.upper(),
        "lower": lambda t, a, l: t.lower(),
        "trim": lambda t, a, l: t.strip(),
        "length": lambda t, a, l: len(t),
        "split": lambda t, a, l: (t.split(_need_str(a[0], "split", l)) if a else t.split()),
        "starts_with": lambda t, a, l: t.startswith(_need_str(a[0], "starts_with", l)),
        "ends_with": lambda t, a, l: t.endswith(_need_str(a[0], "ends_with", l)),
        "replace": lambda t, a, l: t.replace(_need_str(a[0], "replace", l), _need_str(a[1], "replace", l)),
        "has": lambda t, a, l: _need_str(a[0], "has", l) in t,
    },
    "list": {
        "push": lambda t, a, l: (t.append(a[0]), t)[1],
        "pop": lambda t, a, l: (t.pop() if t else _err("pop() from empty list", l)),
        "length": lambda t, a, l: len(t),
        "has": lambda t, a, l: a[0] in t,
        "reverse": lambda t, a, l: t[::-1],
        "sort": lambda t, a, l: _sorted(t, l),
    },
    "map": {
        "keys": lambda t, a, l: list(t.keys()),
        "values": lambda t, a, l: list(t.values()),
        "has": lambda t, a, l: a[0] in t,
        "length": lambda t, a, l: len(t),
        "remove": lambda t, a, l: (t.pop(a[0], None), t)[1],
    },
}


def _err(msg, line):
    raise RuntimeErrorSandy(msg, line)


def _sorted(t, line):
    try:
        return sorted(t)
    except TypeError:
        raise RuntimeErrorSandy("sort() needs comparable items", line)
