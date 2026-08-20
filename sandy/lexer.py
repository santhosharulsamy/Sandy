"""The Sandy lexer: turns source text into a list of tokens.

Newlines are significant (they separate statements), but the lexer is
smart about line continuations:

  * newlines inside ( ) and [ ] are ignored,
  * a newline right after an operator / comma / open-delimiter is ignored,

so lists, maps and long expressions can span multiple lines naturally.
"""

from .errors import LexError
from .tokens import Token, TokenType, KEYWORDS, CONTINUATION_TYPES

_SINGLE = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "%": TokenType.PERCENT,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    ",": TokenType.COMMA,
    ":": TokenType.COLON,
    ".": TokenType.DOT,
}

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "0": "\0",
}


class Lexer:
    def __init__(self, source):
        self.src = source
        self.pos = 0
        self.line = 1
        self.tokens = []

    def error(self, msg):
        raise LexError(msg, self.line)

    def _peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else ""

    def _add(self, type_, value):
        self.tokens.append(Token(type_, value, self.line))

    def tokenize(self):
        src = self.src
        n = len(src)
        while self.pos < n:
            c = src[self.pos]

            # Whitespace (not newline).
            if c in " \t\r":
                self.pos += 1
                continue

            # Comments run to end of line.
            if c == "#":
                while self.pos < n and src[self.pos] != "\n":
                    self.pos += 1
                continue

            if c == "\n":
                self._add(TokenType.NEWLINE, "\n")
                self.pos += 1
                self.line += 1
                continue

            if c.isdigit() or (c == "." and self._peek(1).isdigit()):
                self._number()
                continue

            if c.isalpha() or c == "_":
                self._identifier()
                continue

            if c == '"' or c == "'":
                self._string(c)
                continue

            self._operator()

        self._add(TokenType.NEWLINE, "\n")
        self._add(TokenType.EOF, None)
        return self._post_process()

    def _number(self):
        start = self.pos
        src = self.src
        n = len(src)
        is_float = False
        while self.pos < n and src[self.pos].isdigit():
            self.pos += 1
        if self.pos < n and src[self.pos] == "." and self._peek(1) != ".":
            is_float = True
            self.pos += 1
            while self.pos < n and src[self.pos].isdigit():
                self.pos += 1
        text = src[start:self.pos]
        if is_float:
            self._add(TokenType.FLOAT, float(text))
        else:
            self._add(TokenType.INT, int(text))

    def _identifier(self):
        start = self.pos
        src = self.src
        n = len(src)
        while self.pos < n and (src[self.pos].isalnum() or src[self.pos] == "_"):
            self.pos += 1
        text = src[start:self.pos]
        kw = KEYWORDS.get(text)
        if kw:
            self._add(kw, text)
        else:
            self._add(TokenType.IDENT, text)

    def _string(self, quote):
        """Scan a string literal, supporting {expr} interpolation.

        `{{` and `}}` produce literal `{` and `}`. A string with no
        interpolation becomes a plain STRING token; otherwise it becomes an
        FSTRING token whose value is a list of parts, each either
        ("lit", text) or ("expr", raw_source, line).
        """
        src = self.src
        n = len(src)
        self.pos += 1  # opening quote
        parts = []
        buf = []
        has_interp = False

        def flush_lit():
            if buf:
                parts.append(("lit", "".join(buf)))
                buf.clear()

        while self.pos < n and src[self.pos] != quote:
            ch = src[self.pos]
            if ch == "\n":
                self.error("unterminated string literal")
            if ch == "\\":
                self.pos += 1
                if self.pos >= n:
                    self.error("unterminated string literal")
                buf.append(_ESCAPES.get(src[self.pos], src[self.pos]))
                self.pos += 1
                continue
            if ch == "{":
                if self._peek(1) == "{":  # escaped brace
                    buf.append("{")
                    self.pos += 2
                    continue
                has_interp = True
                flush_lit()
                self.pos += 1  # consume '{'
                raw, line = self._scan_interp()
                if raw.strip() == "":
                    self.error("empty interpolation in string")
                parts.append(("expr", raw, line))
                continue
            if ch == "}":
                if self._peek(1) == "}":  # escaped brace
                    buf.append("}")
                    self.pos += 2
                    continue
                buf.append("}")
                self.pos += 1
                continue
            buf.append(ch)
            self.pos += 1

        if self.pos >= n:
            self.error("unterminated string literal")
        self.pos += 1  # closing quote
        flush_lit()

        if has_interp:
            self._add(TokenType.FSTRING, parts)
        else:
            text = parts[0][1] if parts else ""
            self._add(TokenType.STRING, text)

    def _scan_interp(self):
        """Read the raw source of a `{ ... }` interpolation (self.pos is just
        past the '{'). Tracks brace depth and skips nested strings so that
        maps and quoted braces inside the expression don't end it early.
        Returns (raw_source, line) and leaves self.pos just past the '}'.
        """
        src = self.src
        n = len(src)
        start = self.pos
        line = self.line
        depth = 1
        while self.pos < n:
            c = src[self.pos]
            if c == "\n":
                self.error("unterminated interpolation in string")
            if c == '"' or c == "'":
                self._skip_nested_string(c)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    raw = src[start:self.pos]
                    self.pos += 1  # consume '}'
                    return raw, line
            self.pos += 1
        self.error("unterminated interpolation in string")

    def _skip_nested_string(self, quote):
        """Advance past a nested string literal inside an interpolation."""
        src = self.src
        n = len(src)
        self.pos += 1  # opening quote
        while self.pos < n and src[self.pos] != quote:
            if src[self.pos] == "\\":
                self.pos += 2
                continue
            if src[self.pos] == "\n":
                self.error("unterminated string in interpolation")
            self.pos += 1
        if self.pos >= n:
            self.error("unterminated string in interpolation")
        self.pos += 1  # closing quote

    def _operator(self):
        src = self.src
        c = src[self.pos]
        two = src[self.pos:self.pos + 2]

        two_map = {
            "**": TokenType.STARSTAR,
            "==": TokenType.EQ,
            "!=": TokenType.NEQ,
            "<=": TokenType.LE,
            ">=": TokenType.GE,
            "+=": TokenType.PLUS_EQ,
            "-=": TokenType.MINUS_EQ,
            "*=": TokenType.STAR_EQ,
            "/=": TokenType.SLASH_EQ,
        }
        if two in two_map:
            self._add(two_map[two], two)
            self.pos += 2
            return

        if c == "*":
            self._add(TokenType.STAR, c)
        elif c == "/":
            self._add(TokenType.SLASH, c)
        elif c == "=":
            self._add(TokenType.ASSIGN, c)
        elif c == "<":
            self._add(TokenType.LT, c)
        elif c == ">":
            self._add(TokenType.GT, c)
        elif c in _SINGLE:
            self._add(_SINGLE[c], c)
        else:
            self.error(f"unexpected character {c!r}")
        self.pos += 1

    def _post_process(self):
        """Drop newlines that are really line-continuations, collapse runs,
        and strip leading newlines. Newlines inside ( ) [ ] are suppressed.
        """
        result = []
        depth = 0  # only () and [] count as grouping for newlines
        prev_significant = None
        for tok in self.tokens:
            t = tok.type
            if t in (TokenType.LPAREN, TokenType.LBRACKET):
                depth += 1
            elif t in (TokenType.RPAREN, TokenType.RBRACKET):
                depth = max(0, depth - 1)

            if t == TokenType.NEWLINE:
                if depth > 0:
                    continue
                if prev_significant is None:
                    continue  # leading blank lines
                if prev_significant in CONTINUATION_TYPES:
                    continue  # continuation after operator/comma/open
                if result and result[-1].type == TokenType.NEWLINE:
                    continue  # collapse consecutive newlines
                result.append(tok)
            else:
                result.append(tok)
                prev_significant = t
        return result


def tokenize(source):
    return Lexer(source).tokenize()
