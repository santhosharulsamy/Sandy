"""Native backend: transpile the typed scalar core of Sandy to C.

This is Stage 4 of the roadmap in miniature. A full native compiler for all
of Sandy (closures, dynamic `any`, lists/maps) is a large project; this
backend deliberately handles the *statically typed scalar subset* — exactly
where types make native code generation sound and worthwhile:

    * types int, float, bool, string
    * homogeneous typed lists list<int>/list<float>/list<string>/list<bool>:
      literals, indexing, index-assignment, len(), push(), for-iteration,
      and printing — compiled to unboxed growable C arrays (no tagging)
    * homogeneous typed maps map<K,V> (K int/string, V scalar): literals,
      indexing (get), index-assignment (set), has(), len(), keys(), values(),
      for-iteration (over keys), and printing — an unboxed open-addressing
      hash table that also tracks insertion order so output/iteration match
      the interpreter
    * structs with typed fields (scalar/string/struct fields): construction,
      field access and mutation, value equality, printing, and nesting —
      heap-allocated so they keep Sandy's reference semantics (aliasing and
      mutation-through-calls behave identically to the interpreter)
    * functions with typed parameters and a return type, incl. recursion
    * arithmetic, comparisons, and/or/not, unary minus
    * strings: concatenation (+), repetition (*), ordering, len(), str(),
      and the .upper()/.lower()/.trim()/.length() methods
    * if / elif / else, while, for i in range(...), break, continue, return
    * try / catch / throw: a setjmp/longjmp handler stack; the caught value is
      the error message string, and built-in runtime errors (division by zero,
      index/key errors) are catchable, exactly as in the interpreter
    * print(...) of scalars, lists, and interpolated strings

Anything outside this subset raises NativeUnsupported with a clear message,
pointing the user back to the `--vm` engine. The generated C is compiled with
the system C compiler at -O2, so typed programs run at native speed.

Semantics are matched to the interpreter on purpose: `/` is always float,
`%` is Python-style floor modulo, floats print as the interpreter shows them
(integral values as `N.0`), string ordering is lexicographic (strcmp), and
lists print as `[a, b, c]` with strings quoted.

Heap values (strings, lists, maps, structs) are allocated through a small set
of macros. By default they are never freed — fine for the short-lived programs
this backend targets. Building with `sandy build --gc` (`-DSANDY_GC`) instead
routes every allocation through a conservative mark-sweep garbage collector, so
long-running programs keep their memory bounded; correctness and iteration
order are identical either way. Dynamic `any` values and closures are not yet
supported natively.
"""

from .errors import SandyError
from . import nodes as N


class NativeUnsupported(SandyError):
    def format(self, kind="NativeError"):
        return super().format(kind)


C_TYPE = {"int": "long long", "float": "double", "bool": "int",
          "string": "const char*"}
_ZERO = {"int": "0", "float": "0.0", "bool": "0", "string": '""'}
_NUM = ("int", "float")

# Global builtins the native backend understands.
_NATIVE_BUILTINS = {"len", "str", "push", "has", "keys", "values"}

# String methods -> (C helper, result type).
_STRING_METHODS = {
    "upper": ("sy_upper", "string"),
    "lower": ("sy_lower", "string"),
    "trim": ("sy_trim", "string"),
    "length": ("sy_slen", "int"),
}

# Allocation macros + an optional conservative mark-sweep garbage collector.
# Compiling with -DSANDY_GC (the `sandy build --gc` flag) routes every heap
# allocation through the collector; without it, allocations use libc and leak
# (fine for short-lived tools). One generated program supports both modes.
_GC_RUNTIME = r"""
#ifdef SANDY_GC
#include <setjmp.h>
#include <stdint.h>
typedef struct { void* ptr; size_t size; int mark; } SyGCEntry;
static SyGCEntry* sy_gc_tab = NULL;
static size_t sy_gc_cap = 0, sy_gc_count = 0;
static size_t sy_gc_bytes = 0, sy_gc_threshold = 1u << 20;
static void* sy_gc_bottom = NULL;
static void sy_gc_init(void* bottom) { sy_gc_bottom = bottom; }
static size_t sy_gc_hash(void* p) { return (size_t)((uintptr_t)p >> 4) * 2654435761u; }
static void sy_gc_put(void* p, size_t size);
static void sy_gc_rehash(size_t newcap) {
    SyGCEntry* old = sy_gc_tab; size_t oc = sy_gc_cap;
    sy_gc_tab = (SyGCEntry*)calloc(newcap, sizeof(SyGCEntry));
    sy_gc_cap = newcap; sy_gc_count = 0;
    for (size_t i = 0; i < oc; i++) if (old[i].ptr) sy_gc_put(old[i].ptr, old[i].size);
    free(old);
}
static void sy_gc_put(void* p, size_t size) {
    if (sy_gc_cap == 0) sy_gc_rehash(1024);
    else if ((sy_gc_count + 1) * 10 >= sy_gc_cap * 7) sy_gc_rehash(sy_gc_cap * 2);
    size_t h = sy_gc_hash(p) & (sy_gc_cap - 1);
    while (sy_gc_tab[h].ptr) {
        if (sy_gc_tab[h].ptr == p) { sy_gc_tab[h].size = size; return; }
        h = (h + 1) & (sy_gc_cap - 1);
    }
    sy_gc_tab[h].ptr = p; sy_gc_tab[h].size = size; sy_gc_tab[h].mark = 0;
    sy_gc_count++;
}
static SyGCEntry* sy_gc_find(void* p) {
    if (!sy_gc_cap || !p) return NULL;
    size_t h = sy_gc_hash(p) & (sy_gc_cap - 1);
    while (sy_gc_tab[h].ptr) {
        if (sy_gc_tab[h].ptr == p) return &sy_gc_tab[h];
        h = (h + 1) & (sy_gc_cap - 1);
    }
    return NULL;
}
static void sy_gc_mark(char* lo, char* hi) {
    uintptr_t a = ((uintptr_t)lo + sizeof(void*) - 1) & ~(uintptr_t)(sizeof(void*) - 1);
    for (char* pp = (char*)a; pp + sizeof(void*) <= hi; pp += sizeof(void*)) {
        SyGCEntry* e = sy_gc_find(*(void**)pp);
        if (e && !e->mark) { e->mark = 1; sy_gc_mark((char*)e->ptr, (char*)e->ptr + e->size); }
    }
}
static void sy_gc_collect(void) {
    jmp_buf jb; setjmp(jb);              /* flush callee-saved registers to stack */
    char anchor; char* cur = &anchor;
    char* lo = cur < (char*)sy_gc_bottom ? cur : (char*)sy_gc_bottom;
    char* hi = cur < (char*)sy_gc_bottom ? (char*)sy_gc_bottom : cur;
    for (size_t i = 0; i < sy_gc_cap; i++) sy_gc_tab[i].mark = 0;
    sy_gc_mark(lo, hi);
    for (size_t i = 0; i < sy_gc_cap; i++)
        if (sy_gc_tab[i].ptr && !sy_gc_tab[i].mark) {
            free(sy_gc_tab[i].ptr); sy_gc_tab[i].ptr = NULL; sy_gc_count--;
        }
    sy_gc_bytes = 0;
}
static void* sy_gc_alloc(size_t n) {
    if (sy_gc_bytes > sy_gc_threshold) sy_gc_collect();
    void* p = malloc(n ? n : 1);
    sy_gc_put(p, n); sy_gc_bytes += n; return p;
}
static void* sy_gc_calloc(size_t a, size_t b) {
    void* p = sy_gc_alloc(a * b); memset(p, 0, a * b); return p;
}
static void* sy_gc_realloc(void* old, size_t n) {
    void* p = sy_gc_alloc(n);
    if (old) { SyGCEntry* e = sy_gc_find(old);
               size_t os = e ? e->size : 0; memcpy(p, old, os < n ? os : n); }
    return p;
}
#define SY_ALLOC(n) sy_gc_alloc(n)
#define SY_CALLOC(a, b) sy_gc_calloc(a, b)
#define SY_REALLOC(p, n) sy_gc_realloc(p, n)
#define SY_FREE(p) ((void)0)
#else
#define SY_ALLOC(n) malloc(n)
#define SY_CALLOC(a, b) calloc(a, b)
#define SY_REALLOC(p, n) realloc(p, n)
#define SY_FREE(p) free(p)
#endif
"""

_HELPERS = r"""
/* Exception runtime for try/catch/throw. Handlers form a stack of setjmp
   buffers; `throw` longjmps to the innermost one (or prints and exits if
   there is none). The caught value is the error message string, exactly as
   the interpreter binds it to the catch variable. sy_throw copies the message
   onto the heap so it survives the stack unwind; there is no allocation
   between setting sy_err_msg and the catch binding it to a (stack-rooted)
   local, so it is safe under the GC. */
typedef struct SyHandler { jmp_buf env; struct SyHandler* prev; } SyHandler;
static SyHandler* sy_handlers = NULL;
static const char* sy_err_msg = NULL;
__attribute__((noreturn))
static void sy_throw(const char* msg, int line) {
    if (sy_handlers) {
        size_t n = strlen(msg);
        char* m = (char*)SY_ALLOC(n + 1);
        memcpy(m, msg, n + 1);
        sy_err_msg = m;
        longjmp(sy_handlers->env, 1);
    }
    fprintf(stderr, "RuntimeError (line %d): %s\n", line, msg);
    exit(1);
}
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
    if (b == 0) sy_throw("division by zero", line);
    return a / b;
}
static long long sy_ckz(long long b, int line) {
    if (b == 0) sy_throw("modulo by zero", line);
    return b;
}
static void sy_pf(double v) {
    if (v == (long long)v && v < 1e16 && v > -1e16) printf("%.1f", v);
    else printf("%g", v);
}
/* String runtime. Sandy strings are immutable; these helpers return freshly
   heap-allocated buffers (via SY_ALLOC, so they are reclaimed under -DSANDY_GC
   and leak otherwise). */
static char* sy_concat(const char* a, const char* b) {
    size_t la = strlen(a), lb = strlen(b);
    char* r = (char*)SY_ALLOC(la + lb + 1);
    memcpy(r, a, la); memcpy(r + la, b, lb + 1);
    return r;
}
static char* sy_repeat(const char* s, long long n) {
    if (n < 0) n = 0;
    size_t ls = strlen(s);
    char* r = (char*)SY_ALLOC(ls * (size_t)n + 1);
    char* p = r;
    for (long long i = 0; i < n; i++) { memcpy(p, s, ls); p += ls; }
    *p = 0;
    return r;
}
static char* sy_from_ll(long long v) {
    char* r = (char*)SY_ALLOC(24);
    snprintf(r, 24, "%lld", v);
    return r;
}
static char* sy_from_double(double v) {
    char* r = (char*)SY_ALLOC(32);
    if (v == (long long)v && v < 1e16 && v > -1e16) snprintf(r, 32, "%.1f", v);
    else snprintf(r, 32, "%g", v);
    return r;
}
static long long sy_slen(const char* s) { return (long long)strlen(s); }
static char* sy_upper(const char* s) {
    size_t n = strlen(s); char* r = (char*)SY_ALLOC(n + 1);
    for (size_t i = 0; i < n; i++) r[i] = (char)toupper((unsigned char)s[i]);
    r[n] = 0; return r;
}
static char* sy_lower(const char* s) {
    size_t n = strlen(s); char* r = (char*)SY_ALLOC(n + 1);
    for (size_t i = 0; i < n; i++) r[i] = (char)tolower((unsigned char)s[i]);
    r[n] = 0; return r;
}
static char* sy_trim(const char* s) {
    while (*s && isspace((unsigned char)*s)) s++;
    size_t n = strlen(s);
    while (n > 0 && isspace((unsigned char)s[n - 1])) n--;
    char* r = (char*)SY_ALLOC(n + 1);
    memcpy(r, s, n); r[n] = 0; return r;
}
static void sy_prepr(const char* s) {  /* quoted form used inside lists */
    putchar('"');
    for (; *s; s++) { if (*s == '\\' || *s == '"') putchar('\\'); putchar(*s); }
    putchar('"');
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


# Element sandy type -> (struct suffix, element C type) for native lists.
_ELEM = {"int": ("i", "long long"), "float": ("d", "double"),
         "string": ("s", "const char*"), "bool": ("b", "int")}

# Map key types we support natively (values use _ELEM).
_KEY = {"string": ("s", "const char*"), "int": ("i", "long long")}


def _list_base(t):
    """'list' base of a type, or None if it isn't a list type."""
    if isinstance(t, str) and t.startswith("list<") and t.endswith(">"):
        return t[5:-1]
    return None


def _map_kv(t):
    """(key, value) types of a map<K,V>, or None if `t` isn't a map type."""
    if isinstance(t, str) and t.startswith("map<") and t.endswith(">"):
        inner = t[4:-1]
        depth, comma = 0, -1
        for i, ch in enumerate(inner):
            if ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0:
                comma = i
                break
        if comma != -1:
            return inner[:comma].strip(), inner[comma + 1:].strip()
    return None


def _list_runtime(et):
    """C source for a growable list of element type `et` (int/float/...)."""
    sfx, ct = _ELEM[et]
    return f"""
typedef struct {{ {ct}* data; long long len, cap; }} SyList_{sfx};
static SyList_{sfx}* sy_lnew_{sfx}(void) {{
    SyList_{sfx}* L = (SyList_{sfx}*)SY_ALLOC(sizeof(SyList_{sfx}));
    L->data = NULL; L->len = 0; L->cap = 0; return L;
}}
static SyList_{sfx}* sy_lpush_{sfx}(SyList_{sfx}* L, {ct} v) {{
    if (L->len == L->cap) {{
        L->cap = L->cap ? L->cap * 2 : 8;
        L->data = ({ct}*)SY_REALLOC(L->data, (size_t)L->cap * sizeof({ct}));
    }}
    L->data[L->len++] = v; return L;
}}
static {ct} sy_lget_{sfx}(SyList_{sfx}* L, long long i, int line) {{
    long long o = i; if (i < 0) i += L->len;
    if (i < 0 || i >= L->len) {{ char b[80]; snprintf(b, sizeof b, "index %lld out of range (length %lld)", o, L->len); sy_throw(b, line); }}
    return L->data[i];
}}
static void sy_lset_{sfx}(SyList_{sfx}* L, long long i, {ct} v, int line) {{
    long long o = i; if (i < 0) i += L->len;
    if (i < 0 || i >= L->len) {{ char b[80]; snprintf(b, sizeof b, "index %lld out of range (length %lld)", o, L->len); sy_throw(b, line); }}
    L->data[i] = v;
}}
"""


def _map_key_helpers(kt):
    """Hash and equality for a native map key type (emitted once per key type)."""
    ks, kc = _KEY[kt]
    if kt == "string":
        return f"""
static unsigned long sy_hash_{ks}(const char* s) {{
    unsigned long h = 1469598103934665603UL;
    while (*s) {{ h ^= (unsigned char)*s++; h *= 1099511628211UL; }}
    return h;
}}
static int sy_keq_{ks}(const char* a, const char* b) {{ return strcmp(a, b) == 0; }}
"""
    return f"""
static unsigned long sy_hash_{ks}(long long k) {{
    unsigned long x = (unsigned long)k; x *= 0x9E3779B97F4A7C15UL; return x ^ (x >> 29);
}}
static int sy_keq_{ks}(long long a, long long b) {{ return a == b; }}
"""


def _map_runtime(kt, vt):
    """C source for an open-addressing hash map from `kt` keys to `vt` values."""
    ks, kc = _KEY[kt]
    vs, vc = _ELEM[vt]
    mt = f"SyMap_{ks}_{vs}"
    if kt == "string":
        notfound = ('{ char* _b = (char*)SY_ALLOC(strlen(k) + 40); '
                    'sprintf(_b, "key \'%s\' not found in map", k); '
                    'sy_throw(_b, line); }')
    else:
        notfound = ('{ char _b[64]; snprintf(_b, sizeof _b, '
                    '"key %lld not found in map", (long long)k); '
                    'sy_throw(_b, line); }')
    return f"""
typedef struct {{ {kc}* keys; {vc}* vals; char* used; {kc}* order;
                  long long cap, len, ocap; }} {mt};
static {mt}* sy_mnew_{ks}_{vs}(void) {{
    {mt}* m = ({mt}*)SY_ALLOC(sizeof({mt}));
    m->cap = 8; m->len = 0; m->ocap = 0; m->order = NULL;
    m->keys = ({kc}*)SY_CALLOC(8, sizeof({kc}));
    m->vals = ({vc}*)SY_ALLOC(8 * sizeof({vc}));
    m->used = (char*)SY_CALLOC(8, 1);
    return m;
}}
static void sy_mgrow_{ks}_{vs}({mt}* m) {{  /* rehash slots; keep len and order */
    long long oc = m->cap; {kc}* ok = m->keys; {vc}* ov = m->vals; char* ou = m->used;
    m->cap = oc * 2;
    m->keys = ({kc}*)SY_CALLOC((size_t)m->cap, sizeof({kc}));
    m->vals = ({vc}*)SY_ALLOC((size_t)m->cap * sizeof({vc}));
    m->used = (char*)SY_CALLOC((size_t)m->cap, 1);
    for (long long i = 0; i < oc; i++) if (ou[i]) {{
        unsigned long h = sy_hash_{ks}(ok[i]) & (unsigned long)(m->cap - 1);
        while (m->used[h]) h = (h + 1) & (unsigned long)(m->cap - 1);
        m->used[h] = 1; m->keys[h] = ok[i]; m->vals[h] = ov[i];
    }}
    SY_FREE(ok); SY_FREE(ov); SY_FREE(ou);
}}
static void sy_mput_{ks}_{vs}({mt}* m, {kc} k, {vc} v) {{
    if ((m->len + 1) * 10 >= m->cap * 7) sy_mgrow_{ks}_{vs}(m);
    unsigned long h = sy_hash_{ks}(k) & (unsigned long)(m->cap - 1);
    while (m->used[h]) {{ if (sy_keq_{ks}(m->keys[h], k)) {{ m->vals[h] = v; return; }} h = (h + 1) & (unsigned long)(m->cap - 1); }}
    m->used[h] = 1; m->keys[h] = k; m->vals[h] = v;
    if (m->len == m->ocap) {{ m->ocap = m->ocap ? m->ocap * 2 : 8; m->order = ({kc}*)SY_REALLOC(m->order, (size_t)m->ocap * sizeof({kc})); }}
    m->order[m->len] = k; m->len++;
}}
static {vc} sy_mget_{ks}_{vs}({mt}* m, {kc} k, int line) {{
    unsigned long h = sy_hash_{ks}(k) & (unsigned long)(m->cap - 1);
    while (m->used[h]) {{ if (sy_keq_{ks}(m->keys[h], k)) return m->vals[h]; h = (h + 1) & (unsigned long)(m->cap - 1); }}
    {notfound}
}}
static int sy_mhas_{ks}_{vs}({mt}* m, {kc} k) {{
    unsigned long h = sy_hash_{ks}(k) & (unsigned long)(m->cap - 1);
    while (m->used[h]) {{ if (sy_keq_{ks}(m->keys[h], k)) return 1; h = (h + 1) & (unsigned long)(m->cap - 1); }}
    return 0;
}}
"""


class _Sig:
    __slots__ = ("params", "ptypes", "ret")

    def __init__(self, params, ptypes, ret):
        self.params = params
        self.ptypes = ptypes
        self.ret = ret  # sandy type name or None (void)


class CBackend:
    def __init__(self):
        self.funcs = {}
        self.structs = {}          # name -> (fields, field_types)
        self.structs_needed = []   # struct names used, in definition order
        self.lists_needed = set()  # element types of lists used (for runtime)
        self.maps_needed = set()   # (key, value) type pairs of maps used
        self._tmp = 0
        # C variables holding the saved handler stack to restore on a non-local
        # exit from a `try` (return -> function entry, break/continue -> loop
        # entry). None when the current function contains no `try`.
        self._hsave_func = None
        self._hsave_loop = None

    # -- entry --
    def compile(self, program):
        structdefs = [s for s in program.statements if isinstance(s, N.StructDef)]
        funcdefs = [s for s in program.statements if isinstance(s, N.FuncDef)]
        topstmts = [s for s in program.statements
                    if not isinstance(s, (N.FuncDef, N.StructDef))]
        for sd in structdefs:
            self.structs[sd.name] = (list(sd.fields), list(sd.field_types))
        for sd in structdefs:
            self._validate_struct(sd)
        for fd in funcdefs:
            self._register(fd)
        sections = [self._emit_function(fd) for fd in funcdefs]
        main_body = self._emit_main(topstmts)
        return self._assemble(sections, main_body)

    def _validate_struct(self, sd):
        # Fields must be typed as a scalar, a string, or another struct.
        for fname, ft in zip(sd.fields, sd.field_types):
            if ft is None:
                raise NativeUnsupported(
                    f"native struct '{sd.name}' needs a type on field "
                    f"'{fname}' (e.g. `{fname}: int`)", sd.line)
            if ft not in C_TYPE and ft not in self.structs:
                raise NativeUnsupported(
                    f"native struct field '{sd.name}.{fname}' must be a scalar, "
                    f"string, or struct type, not '{ft}' (list/map fields aren't "
                    f"supported by the native backend yet)", sd.line)

    # C type / zero-value for a (possibly list/map) Sandy type.
    def _cty(self, t):
        et = _list_base(t)
        if et is not None:
            if et not in _ELEM:
                raise NativeUnsupported(
                    f"native lists support element types int/float/bool/"
                    f"string, not '{et}'", None)
            self.lists_needed.add(et)
            return f"SyList_{_ELEM[et][0]}*"
        kv = _map_kv(t)
        if kv is not None:
            kt, vt = kv
            if kt not in _KEY or vt not in _ELEM:
                raise NativeUnsupported(
                    f"native maps support key int/string and scalar values, "
                    f"not map<{kt},{vt}>", None)
            self.maps_needed.add((kt, vt))
            return f"SyMap_{_KEY[kt][0]}_{_ELEM[vt][0]}*"
        if t in self.structs:
            if t not in self.structs_needed:
                self.structs_needed.append(t)
            return f"SyStruct_{t}*"
        if t not in C_TYPE:
            raise NativeUnsupported(f"unsupported native type '{t or 'any'}'", None)
        return C_TYPE[t]

    def _czero(self, t):
        if (_list_base(t) is not None or _map_kv(t) is not None
                or t in self.structs):
            return "NULL"
        return _ZERO[t]

    def _is_native_type(self, t):
        return (t in C_TYPE or t in self.structs
                or _list_base(t) is not None or _map_kv(t) is not None)

    def _newtmp(self):
        self._tmp += 1
        return f"_t{self._tmp}"

    def _register(self, fd):
        for pt in fd.param_types:
            if not self._is_native_type(pt):
                raise NativeUnsupported(
                    f"native function '{fd.name}' needs typed parameters "
                    f"(int/float/bool/string/list<T>/map<K,V>/struct); got "
                    f"'{pt or 'any'}'", fd.line)
        ret = fd.ret_type
        if ret is not None and not self._is_native_type(ret):
            raise NativeUnsupported(
                f"native function '{fd.name}' has unsupported return type "
                f"'{ret}'", fd.line)
        self.funcs[fd.name] = _Sig(fd.params, list(fd.param_types), ret)

    # -- functions --
    def _emit_function(self, fd):
        sig = self.funcs[fd.name]
        scope = dict(zip(sig.params, sig.ptypes))
        locals_ = self._infer_locals(fd.body, scope, sig)
        has_try = self._has_try(fd.body)
        # Locals and parameters modified inside a try body have indeterminate
        # values after a longjmp unless volatile, so qualify them when the
        # function uses try. A top-level volatile on a parameter doesn't change
        # the function's type, so the (unqualified) prototype still matches.
        vol = "volatile " if has_try else ""
        params = ", ".join(f"{self._cty(t)} {vol}{n}"
                           for n, t in zip(sig.params, sig.ptypes))
        ret_c = self._cty(sig.ret) if sig.ret else "void"
        lines = [f"{ret_c} {fd.name}({params or 'void'}) {{"]
        for n, t in locals_:
            lines.append(f"    {self._cty(t)} {vol}{n} = {self._czero(t)};")
        self._hsave_func = None
        self._hsave_loop = None
        if has_try:
            self._hsave_func = "_hsave"
            lines.append("    SyHandler* _hsave = sy_handlers;")
        lines += self._emit_block(fd.body, scope, sig, 1)
        lines.append("}")
        return "\n".join(lines)

    def _emit_main(self, stmts):
        scope = {}
        pseudo = _Sig([], [], None)
        block = N.Block(stmts)
        locals_ = self._infer_locals(block, scope, pseudo)
        lines = ["int main(void) {"]
        lines.append("#ifdef SANDY_GC")
        lines.append("    sy_gc_init(__builtin_frame_address(0));")
        lines.append("#endif")
        has_try = self._has_try(block)
        vol = "volatile " if has_try else ""
        for n, t in locals_:
            lines.append(f"    {self._cty(t)} {vol}{n} = {self._czero(t)};")
        self._hsave_func = None
        self._hsave_loop = None
        if has_try:
            self._hsave_func = "_hsave"
            lines.append("    SyHandler* _hsave = sy_handlers;")
        lines += self._emit_block(block, scope, pseudo, 1)
        lines.append("    return 0;")
        lines.append("}")
        return "\n".join(lines)

    def _has_try(self, block):
        """Whether a block contains a `try` anywhere in its control flow."""
        for s in block.statements:
            t = type(s)
            if t is N.Try:
                return True
            if t is N.If:
                if any(self._has_try(b) for _, b in s.branches):
                    return True
                if s.else_block is not None and self._has_try(s.else_block):
                    return True
            elif t is N.While or t is N.For:
                if self._has_try(s.body):
                    return True
        return False

    # -- local hoisting / type inference --
    def _infer_locals(self, block, scope, sig):
        found = []

        def visit(b):
            for s in b.statements:
                t = type(s)
                if t is N.Assign:
                    if isinstance(s.target, (N.Index, N.Attribute)):
                        continue  # field/index assignment declares no new variable
                    if not isinstance(s.target, N.Identifier):
                        raise NativeUnsupported(
                            "native mode supports only simple variable "
                            "assignment", s.line)
                    name = s.target.name
                    if s.annotation is not None:
                        vt = s.annotation
                        if not self._is_native_type(vt):
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
                        vt = self._forvar_type(s, scope, sig)
                        scope[s.var] = vt
                        found.append((s.var, vt))
                    visit(s.body)
                elif t is N.Try:
                    # The catch variable is bound to the error message string.
                    cv = s.catch_var
                    if cv not in scope:
                        scope[cv] = "string"
                        found.append((cv, "string"))
                    elif scope[cv] != "string":
                        raise NativeUnsupported(
                            f"catch variable '{cv}' is also used as "
                            f"{scope[cv]}; in native mode it must be a string",
                            s.line)
                    visit(s.body)
                    visit(s.handler)
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
            if isinstance(s.target, N.Index):
                return self._emit_index_set(s, scope, sig, ind)
            if isinstance(s.target, N.Attribute):
                return self._emit_field_set(s, scope, sig, ind)
            name = s.target.name
            declared = scope[name]
            if s.op == "=":
                value = s.value
            else:
                value = N.BinaryOp(s.op[0], s.target, s.value, s.line)
            if isinstance(value, N.ListLit):
                code, vt = self._list_literal(value, scope, sig, declared)
            elif isinstance(value, N.MapLit):
                code, vt = self._map_literal(value, scope, sig, declared)
            else:
                code, vt = self._expr(value, scope, sig)
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
            lines = []
            saved = self._enter_loop(lines, ind)
            lines.append(f"{ind}while ({cc}) {{")
            lines += self._emit_block(s.body, scope, sig, indent + 1)
            lines.append(f"{ind}}}")
            self._hsave_loop = saved
            return lines
        if t is N.For:
            return self._emit_for(s, scope, sig, indent)
        if t is N.Return:
            # A try left via return must restore the handler stack to the
            # function's entry state so it isn't stranded. The return value is
            # computed *before* the restore (into a temp), so a throw in the
            # return expression is still caught by the enclosing try.
            restore = self._hsave_func
            if s.value is None:
                pre = [f"{ind}sy_handlers = {restore};"] if restore else []
                return pre + [f"{ind}return;"]
            if sig.ret is None:
                raise NativeUnsupported(
                    "this native function returns a value but has no return "
                    "type annotation", s.line)
            code, vt = self._expr(s.value, scope, sig)
            self._check_assignable(sig.ret, vt, s.line, "return value")
            if sig.ret == "float" and vt == "int":
                code = f"(double)({code})"
            if restore:
                tmp = self._newtmp()
                return [f"{ind}{self._cty(sig.ret)} {tmp} = {code};",
                        f"{ind}sy_handlers = {restore};",
                        f"{ind}return {tmp};"]
            return [f"{ind}return {code};"]
        if t is N.Break:
            pre = ([f"{ind}sy_handlers = {self._hsave_loop};"]
                   if self._hsave_loop else [])
            return pre + [f"{ind}break;"]
        if t is N.Continue:
            pre = ([f"{ind}sy_handlers = {self._hsave_loop};"]
                   if self._hsave_loop else [])
            return pre + [f"{ind}continue;"]
        if t is N.Throw:
            code, vt = self._expr(s.value, scope, sig)
            return [f"{ind}sy_throw({self._stringify(code, vt, s.line)}, "
                    f"{s.line});"]
        if t is N.Try:
            return self._emit_try(s, scope, sig, indent)
        if t is N.StructDef:
            return []   # declarations are emitted from compile(), not inline
        if t is N.Import:
            raise NativeUnsupported(
                "import is not supported by the native backend; run with the "
                "interpreter or `--vm`", getattr(s, "line", None))
        raise NativeUnsupported(
            f"{type(s).__name__} is not supported in native mode",
            getattr(s, "line", None))

    def _enter_loop(self, lines, ind):
        """Record the handler stack at loop entry (when the function uses try)
        so break/continue can restore it. Returns the prior loop-save var to
        put back once the loop body has been emitted."""
        saved = self._hsave_loop
        if self._hsave_func:
            var = self._newtmp()
            lines.append(f"{ind}SyHandler* {var} = sy_handlers;")
            self._hsave_loop = var
        return saved

    def _emit_try(self, s, scope, sig, indent):
        ind = "    " * indent
        h = "_h" + self._newtmp()
        lines = [f"{ind}{{",
                 f"{ind}    SyHandler {h}; {h}.prev = sy_handlers; "
                 f"sy_handlers = &{h};",
                 f"{ind}    if (setjmp({h}.env) == 0) {{"]
        lines += self._emit_block(s.body, scope, sig, indent + 2)
        lines.append(f"{ind}        sy_handlers = {h}.prev;")
        lines.append(f"{ind}    }} else {{")
        lines.append(f"{ind}        sy_handlers = {h}.prev;")
        lines.append(f"{ind}        {s.catch_var} = sy_err_msg;")
        lines += self._emit_block(s.handler, scope, sig, indent + 2)
        lines.append(f"{ind}    }}")
        lines.append(f"{ind}}}")
        return lines

    def _stringify(self, code, typ, line):
        """A `const char*` C expression for the Sandy string form of `code`."""
        if typ == "string":
            return code
        if typ == "int":
            return f"sy_from_ll({code})"
        if typ == "float":
            return f"sy_from_double({code})"
        if typ == "bool":
            return f'(({code}) ? "true" : "false")'
        raise NativeUnsupported(
            f"cannot convert a {typ} to a string in native mode", line)

    def _emit_field_set(self, s, scope, sig, ind):
        target = s.target
        tc, tt = self._expr(target.target, scope, sig)
        if tt not in self.structs:
            raise NativeUnsupported(
                f"cannot set field '{target.name}' on a {tt}", s.line)
        fields, ftypes = self.structs[tt]
        if target.name not in fields:
            raise NativeUnsupported(f"{tt} has no field '{target.name}'", s.line)
        ft = ftypes[fields.index(target.name)]
        lhs = f"({tc})->{target.name}"
        if s.op == "=":
            vc, vt = self._expr(s.value, scope, sig)
        else:
            vc, vt = self._binary(
                N.BinaryOp(s.op[0], target, s.value, s.line), scope, sig)
        self._check_assignable(ft, vt, s.line, f"field '{target.name}'")
        if ft == "float" and vt == "int":
            vc = f"(double)({vc})"
        return [f"{ind}{lhs} = {vc};"]

    def _emit_index_set(self, s, scope, sig, ind):
        target = s.target
        tc, tt = self._expr(target.target, scope, sig)
        et = _list_base(tt)
        kv = _map_kv(tt)
        if et is None and kv is None:
            raise NativeUnsupported(
                f"cannot index-assign into a {tt} in native mode", s.line)
        if s.op == "=":
            value = s.value
        else:
            value = N.BinaryOp(s.op[0], target, s.value, s.line)
        if et is not None:
            ic, it = self._expr(target.index, scope, sig)
            if it != "int":
                raise NativeUnsupported("list index must be an int", s.line)
            vc, vt = self._expr(value, scope, sig)
            self._check_assignable(et, vt, s.line, "list element")
            if et == "float" and vt == "int":
                vc = f"(double)({vc})"
            return [f"{ind}sy_lset_{_ELEM[et][0]}({tc}, {ic}, {vc}, {s.line});"]
        # map index-assignment
        kt, mvt = kv
        kc, kct = self._expr(target.index, scope, sig)
        self._check_assignable(kt, kct, s.line, "map key")
        vc, vt = self._expr(value, scope, sig)
        self._check_assignable(mvt, vt, s.line, "map value")
        if mvt == "float" and vt == "int":
            vc = f"(double)({vc})"
        ks, vs = _KEY[kt][0], _ELEM[mvt][0]
        return [f"{ind}sy_mput_{ks}_{vs}({tc}, {kc}, {vc});"]

    def _forvar_type(self, s, scope, sig):
        it = s.iterable
        if isinstance(it, N.Call) and isinstance(it.callee, N.Identifier) \
                and it.callee.name == "range":
            return "int"
        _, itt = self._expr(it, scope, sig)
        et = _list_base(itt)
        if et is not None:
            return et
        kv = _map_kv(itt)
        if kv is not None:
            return kv[0]  # iterating a map yields its keys
        raise NativeUnsupported(
            "native for-loops iterate over range(...), a list, or a map",
            s.line)

    def _emit_for(self, s, scope, sig, indent):
        ind = "    " * indent
        it = s.iterable
        if not (isinstance(it, N.Call) and isinstance(it.callee, N.Identifier)
                and it.callee.name == "range"):
            return self._emit_for_list(s, scope, sig, indent)
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
        lines = []
        saved = self._enter_loop(lines, ind)
        lines.append(
            f"{ind}for ({v} = {start}; {v} {cmp} {stop}; {v} += {step}) {{")
        lines += self._emit_block(s.body, scope, sig, indent + 1)
        lines.append(f"{ind}}}")
        self._hsave_loop = saved
        return lines

    def _emit_for_list(self, s, scope, sig, indent):
        ind = "    " * indent
        code, itt = self._expr(s.iterable, scope, sig)
        et = _list_base(itt)
        if et is not None:
            sfx = _ELEM[et][0]
            lst, i = self._newtmp(), self._newtmp()
            elem = f"{lst}->data[{i}]"
            head = f"SyList_{sfx}* {lst} = {code};"
            length = f"{lst}->len"
        else:
            kv = _map_kv(itt)
            if kv is None:
                raise NativeUnsupported(
                    "native for-loops iterate over range(...), a list, or a "
                    "map", s.line)
            ks, vs = _KEY[kv[0]][0], _ELEM[kv[1]][0]
            m, i = self._newtmp(), self._newtmp()
            elem = f"{m}->order[{i}]"    # iterating a map yields its keys
            head = f"SyMap_{ks}_{vs}* {m} = {code};"
            length = f"{m}->len"
        lines = [f"{ind}{{ {head}"]
        saved = self._enter_loop(lines, ind)
        lines += [
            f"{ind}for (long long {i} = 0; {i} < {length}; {i}++) {{",
            f"{ind}    {s.var} = {elem};",
        ]
        lines += self._emit_block(s.body, scope, sig, indent + 1)
        lines.append(f"{ind}}} }}")
        self._hsave_loop = saved
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
        if _list_base(t) is not None:
            return self._emit_list_print(code, t, ind)
        if _map_kv(t) is not None:
            return self._emit_map_print(code, t, ind)
        if t in self.structs:
            return [f"{ind}sy_print_{t}({code});"]
        raise NativeUnsupported(f"cannot print a {t} value in native mode",
                                getattr(expr, "line", None))

    def _scalar_repr(self, code, typ):
        """A C statement that prints `code` in the interpreter's `to_repr`
        form (strings quoted) — used inside list/map output."""
        if typ == "int":
            return f'printf("%lld", (long long)({code}));'
        if typ == "float":
            return f"sy_pf({code});"
        if typ == "bool":
            return f'fputs(({code}) ? "true" : "false", stdout);'
        if typ == "string":
            return f"sy_prepr({code});"
        raise NativeUnsupported(f"cannot format a {typ} value natively", None)

    def _emit_list_print(self, code, t, ind):
        et = _list_base(t)
        sfx = _ELEM[et][0]
        lst, i = self._newtmp(), self._newtmp()
        show = self._scalar_repr(f"{lst}->data[{i}]", et)
        return [
            f"{ind}{{ SyList_{sfx}* {lst} = {code};",
            f'{ind}fputs("[", stdout);',
            f"{ind}for (long long {i} = 0; {i} < {lst}->len; {i}++) {{",
            f'{ind}    if ({i}) fputs(", ", stdout);',
            f"{ind}    {show}",
            f"{ind}}}",
            f'{ind}fputs("]", stdout);',
            f"{ind}}}",
        ]

    def _emit_map_print(self, code, t, ind):
        kt, vt = _map_kv(t)
        ks, vs = _KEY[kt][0], _ELEM[vt][0]
        m, i = self._newtmp(), self._newtmp()
        key = f"{m}->order[{i}]"
        show_k = self._scalar_repr(key, kt)
        show_v = self._scalar_repr(f"sy_mget_{ks}_{vs}({m}, {key}, 0)", vt)
        return [
            f"{ind}{{ SyMap_{ks}_{vs}* {m} = {code};",
            f'{ind}fputs("{{", stdout);',
            f"{ind}for (long long {i} = 0; {i} < {m}->len; {i}++) {{",
            f'{ind}    if ({i}) fputs(", ", stdout);',
            f"{ind}    {show_k}",
            f'{ind}    fputs(": ", stdout);',
            f"{ind}    {show_v}",
            f"{ind}}}",
            f'{ind}fputs("}}", stdout);',
            f"{ind}}}",
        ]

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
        if t is N.ListLit:
            return self._list_literal(e, scope, sig, None)
        if t is N.MapLit:
            return self._map_literal(e, scope, sig, None)
        if t is N.Index:
            return self._index(e, scope, sig)
        if t is N.Attribute:
            return self._field(e, scope, sig)
        raise NativeUnsupported(
            f"{type(e).__name__} expressions are not supported in native mode",
            getattr(e, "line", None))

    def _construct(self, name, e, scope, sig):
        fields, ftypes = self.structs[name]
        if len(e.args) != len(fields):
            raise NativeUnsupported(
                f"{name}() expects {len(fields)} field(s) "
                f"({', '.join(fields)}), got {len(e.args)}", e.line)
        if name not in self.structs_needed:
            self.structs_needed.append(name)
        tmp = self._newtmp()
        stmts = [f"SyStruct_{name}* {tmp} = "
                 f"(SyStruct_{name}*)SY_ALLOC(sizeof(SyStruct_{name}));"]
        for fname, ft, arg in zip(fields, ftypes, e.args):
            ac, at = self._expr(arg, scope, sig)
            self._check_assignable(ft, at, e.line, f"field '{fname}' of {name}")
            if ft == "float" and at == "int":
                ac = f"(double)({ac})"
            stmts.append(f"{tmp}->{fname} = {ac};")
        return ("({ " + " ".join(stmts) + f" {tmp}; }})", name)

    def _field(self, e, scope, sig):
        tc, tt = self._expr(e.target, scope, sig)
        if tt not in self.structs:
            raise NativeUnsupported(
                f"'.{e.name}' field access needs a struct, got {tt}", e.line)
        fields, ftypes = self.structs[tt]
        if e.name not in fields:
            raise NativeUnsupported(
                f"{tt} has no field '{e.name}'", e.line)
        return (f"({tc})->{e.name}", ftypes[fields.index(e.name)])

    def _map_literal(self, e, scope, sig, expected):
        kt = vt = None
        pairs = []
        for k, v in e.pairs:
            kc, kct = self._expr(k, scope, sig)
            vc, vct = self._expr(v, scope, sig)
            kt = kct if kt is None else kt
            vt = vct if vt is None else vt
            if kct != kt or vct != vt:
                raise NativeUnsupported(
                    "native map literals must be homogeneous", e.line)
            pairs.append((kc, vc))
        if kt is None:  # empty literal
            kv = _map_kv(expected) if expected else None
            if kv is None:
                raise NativeUnsupported(
                    "empty map needs a type annotation in native mode, "
                    "e.g. `m: map<string, int> = {}`", e.line)
            kt, vt = kv
        if kt not in _KEY or vt not in _ELEM:
            raise NativeUnsupported(
                f"native maps don't support map<{kt},{vt}>", e.line)
        ks, vs = _KEY[kt][0], _ELEM[vt][0]
        self.maps_needed.add((kt, vt))
        tmp = self._newtmp()
        stmts = [f"SyMap_{ks}_{vs}* {tmp} = sy_mnew_{ks}_{vs}();"]
        for kc, vc in pairs:
            stmts.append(f"sy_mput_{ks}_{vs}({tmp}, {kc}, {vc});")
        return ("({ " + " ".join(stmts) + f" {tmp}; }})", f"map<{kt},{vt}>")

    def _list_literal(self, e, scope, sig, expected):
        """Build a native list. `expected` is the list type from context (used
        to type an empty literal, e.g. `xs: list<int> = []`)."""
        et = None
        for item in e.items:
            _, it = self._expr(item, scope, sig)
            et = it if et is None else et
            if it != et:
                raise NativeUnsupported(
                    "native list literals must be homogeneous "
                    f"(saw {et} and {it})", e.line)
        if et is None:  # empty literal
            eb = _list_base(expected) if expected else None
            if eb is None:
                raise NativeUnsupported(
                    "empty list needs a type annotation in native mode, "
                    "e.g. `xs: list<int> = []`", e.line)
            et = eb
        if et not in _ELEM:
            raise NativeUnsupported(
                f"native lists don't support element type '{et}'", e.line)
        sfx = _ELEM[et][0]
        self.lists_needed.add(et)
        tmp = self._newtmp()
        stmts = [f"SyList_{sfx}* {tmp} = sy_lnew_{sfx}();"]
        for item in e.items:
            ic, _ = self._expr(item, scope, sig)
            stmts.append(f"sy_lpush_{sfx}({tmp}, {ic});")
        # GNU statement expression: run the pushes, yield the list pointer.
        return ("({ " + " ".join(stmts) + f" {tmp}; }})", f"list<{et}>")

    def _index(self, e, scope, sig):
        tc, tt = self._expr(e.target, scope, sig)
        et = _list_base(tt)
        if et is not None:
            ic, it = self._expr(e.index, scope, sig)
            if it != "int":
                raise NativeUnsupported("list index must be an int", e.line)
            return (f"sy_lget_{_ELEM[et][0]}({tc}, {ic}, {e.line})", et)
        kv = _map_kv(tt)
        if kv is not None:
            kt, vt = kv
            kc, kct = self._expr(e.index, scope, sig)
            self._check_assignable(kt, kct, e.line, "map key")
            ks, vs = _KEY[kt][0], _ELEM[vt][0]
            return (f"sy_mget_{ks}_{vs}({tc}, {kc}, {e.line})", vt)
        raise NativeUnsupported(f"cannot index a {tt} in native mode", e.line)

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
            if lt == rt and lt in self.structs:
                eq = f"sy_eq_{lt}({lc}, {rc})"
                return ((eq if op == "==" else f"(!{eq})"), "bool")
            raise NativeUnsupported(
                f"cannot compare {lt} and {rt} in native mode", line)
        if op in ("<", ">", "<=", ">="):
            if lt == "string" and rt == "string":
                return (f"(strcmp({lc}, {rc}) {op} 0)", "bool")
            self._need_num(lt, line, "compare"); self._need_num(rt, line, "compare")
            return (f"({lc} {op} {rc})", "bool")
        # string concatenation and repetition
        if op == "+" and lt == "string" and rt == "string":
            return (f"sy_concat({lc}, {rc})", "string")
        if op == "*" and lt == "string" and rt == "int":
            return (f"sy_repeat({lc}, {rc})", "string")
        if op == "*" and lt == "int" and rt == "string":
            return (f"sy_repeat({rc}, {lc})", "string")
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
        # Method call: s.upper(), s.lower(), s.trim(), s.length()
        if isinstance(e.callee, N.Attribute):
            return self._method_call(e, scope, sig)
        if not isinstance(e.callee, N.Identifier):
            raise NativeUnsupported(
                "native calls must be to named functions", e.line)
        name = e.callee.name
        if name in _NATIVE_BUILTINS:
            return self._builtin_call(name, e, scope, sig)
        if name in self.structs:
            return self._construct(name, e, scope, sig)
        if name not in self.funcs:
            raise NativeUnsupported(
                f"'{name}' cannot be called in native mode (only user "
                f"functions, structs, and len/str are supported)", e.line)
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

    def _builtin_call(self, name, e, scope, sig):
        if name == "push":
            if len(e.args) != 2:
                raise NativeUnsupported("push() expects 2 arguments", e.line)
            lc, lt = self._expr(e.args[0], scope, sig)
            et = _list_base(lt)
            if et is None:
                raise NativeUnsupported(
                    f"push() needs a list, got {lt}", e.line)
            vc, vt = self._expr(e.args[1], scope, sig)
            self._check_assignable(et, vt, e.line, "push() value")
            if et == "float" and vt == "int":
                vc = f"(double)({vc})"
            return (f"sy_lpush_{_ELEM[et][0]}({lc}, {vc})", lt)
        if name == "has":
            if len(e.args) != 2:
                raise NativeUnsupported("has() expects 2 arguments", e.line)
            mc, mt = self._expr(e.args[0], scope, sig)
            kv = _map_kv(mt)
            if kv is None:
                raise NativeUnsupported(
                    f"native has() needs a map, got {mt}", e.line)
            kt, vt = kv
            kc, kct = self._expr(e.args[1], scope, sig)
            self._check_assignable(kt, kct, e.line, "has() key")
            return (f"sy_mhas_{_KEY[kt][0]}_{_ELEM[vt][0]}({mc}, {kc})", "bool")
        if name in ("keys", "values"):
            if len(e.args) != 1:
                raise NativeUnsupported(f"{name}() expects 1 argument", e.line)
            mc, mt = self._expr(e.args[0], scope, sig)
            kv = _map_kv(mt)
            if kv is None:
                raise NativeUnsupported(
                    f"native {name}() needs a map, got {mt}", e.line)
            kt, vt = kv
            ks, vs = _KEY[kt][0], _ELEM[vt][0]
            et = kt if name == "keys" else vt
            esfx = _ELEM[et][0]
            self.lists_needed.add(et)
            m, i, lst = self._newtmp(), self._newtmp(), self._newtmp()
            item = (f"{m}->order[{i}]" if name == "keys"
                    else f"sy_mget_{ks}_{vs}({m}, {m}->order[{i}], 0)")
            code = (f"({{ SyMap_{ks}_{vs}* {m} = {mc}; "
                    f"SyList_{esfx}* {lst} = sy_lnew_{esfx}(); "
                    f"for (long long {i} = 0; {i} < {m}->len; {i}++) "
                    f"sy_lpush_{esfx}({lst}, {item}); {lst}; }})")
            return (code, f"list<{et}>")
        if len(e.args) != 1:
            raise NativeUnsupported(
                f"{name}() expects 1 argument in native mode", e.line)
        ac, at = self._expr(e.args[0], scope, sig)
        if name == "len":
            if at == "string":
                return (f"((long long)strlen({ac}))", "int")
            if _list_base(at) is not None:
                return (f"({ac}->len)", "int")
            if _map_kv(at) is not None:
                return (f"({ac}->len)", "int")
            raise NativeUnsupported(
                f"native len() supports strings, lists and maps, got {at}",
                e.line)
        # str(x): convert a scalar to its Sandy string form
        return (self._stringify(ac, at, e.line), "string")

    def _method_call(self, e, scope, sig):
        method = e.callee.name
        if method not in _STRING_METHODS:
            raise NativeUnsupported(
                f"native mode supports string methods {sorted(_STRING_METHODS)}, "
                f"not '.{method}()'", e.line)
        tc, tt = self._expr(e.callee.target, scope, sig)
        if tt != "string":
            raise NativeUnsupported(
                f"'.{method}()' is a string method, but the target is {tt}",
                e.line)
        if e.args:
            raise NativeUnsupported(
                f"native '.{method}()' takes no arguments", e.line)
        helper, rtype = _STRING_METHODS[method]
        return (f"{helper}({tc})", rtype)

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
            params = ", ".join(self._cty(t) for t in sig.ptypes) or "void"
            ret_c = self._cty(sig.ret) if sig.ret else "void"
            protos.append(f"{ret_c} {name}({params});")
        # List/map runtimes must precede everything that uses their structs.
        list_rt = "".join(_list_runtime(et)
                          for et in ("int", "float", "string", "bool")
                          if et in self.lists_needed)
        key_rt = "".join(_map_key_helpers(kt)
                         for kt in ("string", "int")
                         if any(k == kt for k, _ in self.maps_needed))
        map_rt = "".join(_map_runtime(kt, vt)
                         for kt in ("string", "int")
                         for vt in ("int", "float", "string", "bool")
                         if (kt, vt) in self.maps_needed)
        # Expand needed structs to include those referenced by struct fields.
        i = 0
        while i < len(self.structs_needed):
            for ft in self.structs[self.structs_needed[i]][1]:
                if ft in self.structs and ft not in self.structs_needed:
                    self.structs_needed.append(ft)
            i += 1
        needed = self.structs_needed
        struct_fwd = "".join(f"typedef struct SyStruct_{n} SyStruct_{n};\n"
                             for n in needed)
        struct_body = "".join(self._struct_body(n) for n in needed)
        struct_protos = "".join(
            f"static void sy_print_{n}(SyStruct_{n}*);\n"
            f"static int sy_eq_{n}(SyStruct_{n}*, SyStruct_{n}*);\n"
            for n in needed)
        struct_helpers = "".join(self._struct_helpers(n) for n in needed)
        parts = [
            "#include <stdio.h>",
            "#include <math.h>",
            "#include <string.h>",
            "#include <stdlib.h>",
            "#include <ctype.h>",
            "#include <setjmp.h>",
            _GC_RUNTIME,
            _HELPERS,
            list_rt,
            key_rt,
            map_rt,
            struct_fwd,
            struct_body,
            struct_protos,
            struct_helpers,
            "\n".join(protos),
            "",
            "\n\n".join(sections),
            "",
            main_body,
            "",
        ]
        return "\n".join(parts)

    def _struct_body(self, name):
        fields, ftypes = self.structs[name]
        if fields:
            decls = " ".join(f"{self._cty(ft)} {fn};"
                             for fn, ft in zip(fields, ftypes))
        else:
            decls = "char _unused;"
        return f"struct SyStruct_{name} {{ {decls} }};\n"

    def _field_repr(self, code, ft):
        if ft in self.structs:
            return f"sy_print_{ft}({code});"
        return self._scalar_repr(code, ft)

    def _field_eq(self, a, b, ft):
        if ft in self.structs:
            return f"sy_eq_{ft}({a}, {b})"
        if ft == "string":
            return f"(strcmp({a}, {b}) == 0)"
        return f"({a} == {b})"

    def _struct_helpers(self, name):
        fields, ftypes = self.structs[name]
        out = [f"static void sy_print_{name}(SyStruct_{name}* v) {{",
               f'    fputs("{name}(", stdout);']
        for i, (fn, ft) in enumerate(zip(fields, ftypes)):
            if i:
                out.append('    fputs(", ", stdout);')
            out.append(f'    fputs("{fn}=", stdout);')
            out.append("    " + self._field_repr(f"v->{fn}", ft))
        out.append('    fputs(")", stdout);')
        out.append("}")
        conds = " && ".join(self._field_eq(f"a->{fn}", f"b->{fn}", ft)
                            for fn, ft in zip(fields, ftypes)) or "1"
        out.append(f"static int sy_eq_{name}(SyStruct_{name}* a, "
                   f"SyStruct_{name}* b) {{ return {conds}; }}")
        return "\n".join(out) + "\n"


def to_c(program):
    return CBackend().compile(program)
