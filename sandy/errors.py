"""Error types for the Sandy language.

Every user-facing error carries a line number so we can point at the
offending source line with a friendly message.
"""


class SandyError(Exception):
    """Base class for all Sandy errors (lexing, parsing, runtime)."""

    def __init__(self, message, line=None):
        self.message = message
        self.line = line
        super().__init__(message)

    def format(self, kind):
        where = f" (line {self.line})" if self.line is not None else ""
        return f"{kind}{where}: {self.message}"


class LexError(SandyError):
    def format(self, kind="SyntaxError"):
        return super().format(kind)


class ParseError(SandyError):
    def format(self, kind="SyntaxError"):
        return super().format(kind)


class RuntimeErrorSandy(SandyError):
    def format(self, kind="RuntimeError"):
        return super().format(kind)


class TypeCheckError(SandyError):
    def format(self, kind="TypeError"):
        return super().format(kind)
