"""Token definitions for the Sandy lexer."""


class TokenType:
    # Literals
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    FSTRING = "FSTRING"  # interpolated string: value is a list of parts
    IDENT = "IDENT"

    # Keywords
    FN = "FN"
    RETURN = "RETURN"
    IF = "IF"
    ELIF = "ELIF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    IN = "IN"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NIL = "NIL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # Operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"
    STARSTAR = "STARSTAR"
    ASSIGN = "ASSIGN"
    PLUS_EQ = "PLUS_EQ"
    MINUS_EQ = "MINUS_EQ"
    STAR_EQ = "STAR_EQ"
    SLASH_EQ = "SLASH_EQ"
    EQ = "EQ"
    NEQ = "NEQ"
    LT = "LT"
    GT = "GT"
    LE = "LE"
    GE = "GE"

    # Delimiters
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COMMA = "COMMA"
    COLON = "COLON"
    DOT = "DOT"

    NEWLINE = "NEWLINE"
    EOF = "EOF"


KEYWORDS = {
    "fn": TokenType.FN,
    "return": TokenType.RETURN,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "nil": TokenType.NIL,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
}

# Tokens after which a NEWLINE is treated as line continuation (suppressed),
# because the statement clearly is not complete yet.
CONTINUATION_TYPES = {
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
    TokenType.PERCENT, TokenType.STARSTAR, TokenType.ASSIGN,
    TokenType.PLUS_EQ, TokenType.MINUS_EQ, TokenType.STAR_EQ, TokenType.SLASH_EQ,
    TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.GT, TokenType.LE,
    TokenType.GE, TokenType.AND, TokenType.OR, TokenType.NOT,
    TokenType.COMMA, TokenType.COLON, TokenType.DOT,
    TokenType.LPAREN, TokenType.LBRACKET, TokenType.LBRACE,
}


class Token:
    __slots__ = ("type", "value", "line")

    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"
