"""Built-in functions and type methods for Sandy.

Global builtins (print, len, range, ...) are created by make_builtins().
Method-style calls (text.upper(), list.push(x), ...) are resolved by
resolve_method(), which returns a bound BuiltinFunction.
"""

import math
import os
import time as _time

from .errors import RuntimeErrorSandy
from .values import BuiltinFunction, Function, to_str, type_name, is_truthy

# Names of all global builtins (kept in sync with the @reg registrations in
# make_builtins below). Used by tooling — completion and the compiler.
BUILTIN_NAMES = frozenset({
    "print", "input", "len", "type", "str", "int", "float", "bool", "range",
    "abs", "min", "max", "sum", "round", "sqrt", "floor", "ceil", "pow",
    "ord", "chr", "sin", "cos", "tan", "exp", "log", "log10",
    "sha256", "md5", "base64_encode", "base64_decode",
    "push", "pop", "keys", "values", "has", "upper", "lower", "trim", "split",
    "join", "read_file", "read_lines", "write_file", "append_file",
    "now", "clock", "sleep", "env", "exit",
    "args", "cwd", "exists", "is_file", "is_dir", "list_dir", "make_dir",
    "remove_file", "http_get", "http_post",
    "re_test", "re_find", "re_find_all", "re_groups", "re_replace", "re_split",
    "spawn", "wait", "channel", "send", "recv", "close",
})


def _http_request(method, url, body, ctype, timeout, line):
    """Perform an HTTP request, returning a Sandy map {status, ok, body}.

    HTTP error statuses (4xx/5xx) come back as a normal response with ok=false;
    only transport failures (bad URL, connection/DNS, timeout) raise."""
    import urllib.request
    import urllib.error
    data = body.encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if ctype:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        status = e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise RuntimeErrorSandy(f"http request to {url!r} failed: {e}", line)
    return {"status": status, "ok": 200 <= status < 300, "body": text}


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

    @reg("ord", 1)
    def _ord(args, line):
        v = args[0]
        if not isinstance(v, str) or len(v) != 1:
            raise RuntimeErrorSandy(
                "ord() needs a single-character string", line)
        return ord(v)

    @reg("chr", 1)
    def _chr(args, line):
        v = args[0]
        if isinstance(v, bool) or not isinstance(v, int):
            raise RuntimeErrorSandy(
                f"chr() needs an int code point, got {type_name(v)}", line)
        if v < 0 or v > 0x10FFFF:
            raise RuntimeErrorSandy(
                f"chr() code point {v} is out of range (0..1114111)", line)
        return chr(v)

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

    def _mathfn(name, fn):
        @reg(name, 1)
        def _f(args, line, _fn=fn, _name=name):
            if not _is_num(args[0]):
                raise RuntimeErrorSandy(f"{_name}() needs a number", line)
            try:
                return _fn(float(args[0]))
            except ValueError as e:
                raise RuntimeErrorSandy(f"{_name}(): {e}", line)
    _mathfn("sin", math.sin)
    _mathfn("cos", math.cos)
    _mathfn("tan", math.tan)
    _mathfn("exp", math.exp)
    _mathfn("log10", math.log10)

    @reg("log", (1, 2))
    def _log(args, line):
        x = args[0]
        if not _is_num(x):
            raise RuntimeErrorSandy("log() needs a number", line)
        base = args[1] if len(args) > 1 else None
        if base is not None and not _is_num(base):
            raise RuntimeErrorSandy("log() base must be a number", line)
        try:
            return math.log(float(x)) if base is None \
                else math.log(float(x), float(base))
        except ValueError as e:
            raise RuntimeErrorSandy(f"log(): {e}", line)

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

    # -- regular expressions (wrapping the host regex engine) --

    @reg("re_test", 2)
    def _re_test(args, line):
        pat = _re_compile(args[0], line)
        return pat.search(_need_str(args[1], "re_test", line)) is not None

    @reg("re_find", 2)
    def _re_find(args, line):
        pat = _re_compile(args[0], line)
        m = pat.search(_need_str(args[1], "re_find", line))
        return m.group(0) if m else None

    @reg("re_find_all", 2)
    def _re_find_all(args, line):
        pat = _re_compile(args[0], line)
        return [m.group(0)
                for m in pat.finditer(_need_str(args[1], "re_find_all", line))]

    @reg("re_groups", 2)
    def _re_groups(args, line):
        pat = _re_compile(args[0], line)
        m = pat.search(_need_str(args[1], "re_groups", line))
        return list(m.groups()) if m else None

    @reg("re_replace", 3)
    def _re_replace(args, line):
        pat = _re_compile(args[0], line)
        s = _need_str(args[1], "re_replace", line)
        repl = _need_str(args[2], "re_replace", line)
        try:
            return pat.sub(repl, s)
        except re_module().error as e:
            raise RuntimeErrorSandy(f"invalid regex replacement: {e}", line)

    @reg("re_split", 2)
    def _re_split(args, line):
        pat = _re_compile(args[0], line)
        return pat.split(_need_str(args[1], "re_split", line))

    # -- concurrency: tasks and channels --

    @reg("spawn", None)
    def _spawn(args, line):
        if not args:
            raise RuntimeErrorSandy("spawn() needs a function to run", line)
        fn = args[0]
        if not isinstance(fn, Function):
            raise RuntimeErrorSandy(
                "spawn() needs a Sandy function; concurrency runs on the "
                "default engine (run without --vm)", line)
        from . import concurrency
        return concurrency.spawn(interp, fn, list(args[1:]), line)

    @reg("wait", 1)
    def _wait(args, line):
        from . import concurrency
        if not isinstance(args[0], concurrency.Task):
            raise RuntimeErrorSandy(
                f"wait() needs a task, got {type_name(args[0])}", line)
        return concurrency.wait(args[0], line)

    @reg("channel", (0, 1))
    def _channel(args, line):
        from . import concurrency
        cap = args[0] if args else 0
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            raise RuntimeErrorSandy(
                "channel() capacity must be a non-negative int", line)
        return concurrency.Channel(cap)

    @reg("send", 2)
    def _send(args, line):
        from . import concurrency
        if not isinstance(args[0], concurrency.Channel):
            raise RuntimeErrorSandy(
                f"send() needs a channel, got {type_name(args[0])}", line)
        args[0].send(args[1], line)
        return None

    @reg("recv", 1)
    def _recv(args, line):
        from . import concurrency
        if not isinstance(args[0], concurrency.Channel):
            raise RuntimeErrorSandy(
                f"recv() needs a channel, got {type_name(args[0])}", line)
        return args[0].recv(line)

    @reg("close", 1)
    def _close(args, line):
        from . import concurrency
        if not isinstance(args[0], concurrency.Channel):
            raise RuntimeErrorSandy(
                f"close() needs a channel, got {type_name(args[0])}", line)
        args[0].close()
        return None

    # -- hashing and encoding --

    @reg("sha256", 1)
    def _sha256(args, line):
        import hashlib
        return hashlib.sha256(
            _need_str(args[0], "sha256", line).encode("utf-8")).hexdigest()

    @reg("md5", 1)
    def _md5(args, line):
        import hashlib
        return hashlib.md5(
            _need_str(args[0], "md5", line).encode("utf-8")).hexdigest()

    @reg("base64_encode", 1)
    def _b64enc(args, line):
        import base64
        return base64.b64encode(
            _need_str(args[0], "base64_encode", line).encode("utf-8")
        ).decode("ascii")

    @reg("base64_decode", 1)
    def _b64dec(args, line):
        import base64
        import binascii
        raw = _need_str(args[0], "base64_decode", line)
        try:
            return base64.b64decode(raw, validate=True).decode("utf-8")
        except (binascii.Error, ValueError, UnicodeDecodeError) as e:
            raise RuntimeErrorSandy(f"base64_decode: invalid input ({e})", line)

    # -- OS-facing builtins: time, environment, process --

    @reg("now", 0)
    def _now(args, line):
        return _time.time()            # wall-clock seconds since the epoch

    @reg("clock", 0)
    def _clock(args, line):
        return _time.perf_counter()    # monotonic seconds, for measuring elapsed time

    @reg("sleep", 1)
    def _sleep(args, line):
        secs = args[0]
        if isinstance(secs, bool) or not isinstance(secs, (int, float)):
            raise RuntimeErrorSandy(
                f"sleep() needs a number of seconds, got {type_name(secs)}", line)
        if secs < 0:
            raise RuntimeErrorSandy("sleep() seconds cannot be negative", line)
        _time.sleep(secs)
        return None

    @reg("env", (1, 2))
    def _env(args, line):
        name = _need_str(args[0], "env", line)
        default = args[1] if len(args) > 1 else None
        value = os.environ.get(name)
        return value if value is not None else default

    @reg("exit", (0, 1))
    def _exit(args, line):
        code = args[0] if args else 0
        if isinstance(code, bool) or not isinstance(code, int):
            raise RuntimeErrorSandy(
                f"exit() needs an integer code, got {type_name(code)}", line)
        raise SystemExit(code)

    # -- OS-facing builtins: command-line args and the filesystem --

    @reg("args", 0)
    def _args(args, line):
        return list(getattr(interp, "program_args", []))

    @reg("cwd", 0)
    def _cwd(args, line):
        return os.getcwd()

    @reg("exists", 1)
    def _exists(args, line):
        return os.path.exists(_need_str(args[0], "exists", line))

    @reg("is_file", 1)
    def _is_file(args, line):
        return os.path.isfile(_need_str(args[0], "is_file", line))

    @reg("is_dir", 1)
    def _is_dir(args, line):
        return os.path.isdir(_need_str(args[0], "is_dir", line))

    @reg("list_dir", 1)
    def _list_dir(args, line):
        path = _need_str(args[0], "list_dir", line)
        try:
            return sorted(os.listdir(path))
        except OSError as e:
            raise RuntimeErrorSandy(
                f"cannot list {path!r}: {e.strerror}", line)

    @reg("make_dir", 1)
    def _make_dir(args, line):
        path = _need_str(args[0], "make_dir", line)
        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            raise RuntimeErrorSandy(
                f"cannot create {path!r}: {e.strerror}", line)
        return None

    @reg("http_get", (1, 2))
    def _http_get(args, line):
        url = _need_str(args[0], "http_get", line)
        timeout = _need_timeout(args[1], line) if len(args) > 1 else 30
        return _http_request("GET", url, None, None, timeout, line)

    @reg("http_post", (2, 4))
    def _http_post(args, line):
        url = _need_str(args[0], "http_post", line)
        body = to_str(args[1])
        ctype = _need_str(args[2], "http_post", line) if len(args) > 2 \
            else "text/plain"
        timeout = _need_timeout(args[3], line) if len(args) > 3 else 30
        return _http_request("POST", url, body, ctype, timeout, line)

    @reg("remove_file", 1)
    def _remove_file(args, line):
        path = _need_str(args[0], "remove_file", line)
        if os.path.isdir(path):
            raise RuntimeErrorSandy(
                f"remove_file: {path!r} is a directory", line)
        try:
            os.remove(path)
        except OSError as e:
            raise RuntimeErrorSandy(
                f"cannot remove {path!r}: {e.strerror}", line)
        return None

    return B


def _need_str(v, name, line):
    if not isinstance(v, str):
        raise RuntimeErrorSandy(f"{name}() needs a string, got {type_name(v)}", line)
    return v


def _need_timeout(v, line):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        raise RuntimeErrorSandy(
            "http timeout must be a positive number of seconds", line)
    return v


def re_module():
    import re
    return re


def _re_compile(pattern, line):
    if not isinstance(pattern, str):
        raise RuntimeErrorSandy(
            f"regex pattern must be a string, got {type_name(pattern)}", line)
    try:
        return re_module().compile(pattern)
    except re_module().error as e:
        raise RuntimeErrorSandy(f"invalid regex {pattern!r}: {e}", line)


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
