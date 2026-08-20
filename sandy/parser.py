"""Recursive-descent parser for Sandy.

Produces an AST (see nodes.py) from the token stream. Operator precedence
is handled with a small precedence-climbing table.
"""

from .errors import ParseError
from .tokens import TokenType as T
from . import nodes as N


# Binary operator precedence (higher binds tighter). Comparison and
# arithmetic live here; 'and'/'or' are handled separately (short-circuit),
# and '**' is right-associative.
_BINARY_PRECEDENCE = {
    T.EQ: 1, T.NEQ: 1, T.LT: 1, T.GT: 1, T.LE: 1, T.GE: 1,
    T.PLUS: 2, T.MINUS: 2,
    T.STAR: 3, T.SLASH: 3, T.PERCENT: 3,
}

_ASSIGN_OPS = {
    T.ASSIGN: "=", T.PLUS_EQ: "+=", T.MINUS_EQ: "-=",
    T.STAR_EQ: "*=", T.SLASH_EQ: "/=",
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # -- token helpers --
    def _peek(self, offset=0):
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else self.tokens[-1]

    def _cur(self):
        return self.tokens[self.pos]

    def _advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _check(self, type_):
        return self._cur().type == type_

    def _match(self, *types):
        if self._cur().type in types:
            return self._advance()
        return None

    def _expect(self, type_, what):
        if self._cur().type != type_:
            tok = self._cur()
            got = tok.value if tok.value is not None else tok.type
            raise ParseError(f"expected {what}, got {got!r}", tok.line)
        return self._advance()

    def _skip_newlines(self):
        while self._check(T.NEWLINE):
            self._advance()

    # -- entry point --
    def parse(self):
        statements = []
        self._skip_newlines()
        while not self._check(T.EOF):
            statements.append(self._statement())
            self._skip_newlines()
        return N.Block(statements)

    # -- statements --
    def _statement(self):
        t = self._cur().type
        if t == T.FN:
            return self._func_def()
        if t == T.IF:
            return self._if_stmt()
        if t == T.WHILE:
            return self._while_stmt()
        if t == T.FOR:
            return self._for_stmt()
        if t == T.RETURN:
            return self._return_stmt()
        if t == T.BREAK:
            line = self._advance().line
            return N.Break(line)
        if t == T.CONTINUE:
            line = self._advance().line
            return N.Continue(line)
        return self._assign_or_expr()

    def _block(self):
        self._expect(T.LBRACE, "'{'")
        self._skip_newlines()
        statements = []
        while not self._check(T.RBRACE) and not self._check(T.EOF):
            statements.append(self._statement())
            self._skip_newlines()
        self._expect(T.RBRACE, "'}'")
        return N.Block(statements)

    def _func_def(self):
        line = self._advance().line  # 'fn'
        name = self._expect(T.IDENT, "function name").value
        self._expect(T.LPAREN, "'('")
        params = []
        if not self._check(T.RPAREN):
            params.append(self._expect(T.IDENT, "parameter name").value)
            while self._match(T.COMMA):
                params.append(self._expect(T.IDENT, "parameter name").value)
        self._expect(T.RPAREN, "')'")
        body = self._block()
        return N.FuncDef(name, params, body, line)

    def _if_stmt(self):
        line = self._advance().line  # 'if'
        branches = []
        cond = self._expression()
        block = self._block()
        branches.append((cond, block))
        else_block = None
        while self._check(T.ELIF):
            self._advance()
            c = self._expression()
            b = self._block()
            branches.append((c, b))
        if self._match(T.ELSE):
            else_block = self._block()
        return N.If(branches, else_block, line)

    def _while_stmt(self):
        line = self._advance().line
        cond = self._expression()
        body = self._block()
        return N.While(cond, body, line)

    def _for_stmt(self):
        line = self._advance().line
        var = self._expect(T.IDENT, "loop variable").value
        self._expect(T.IN, "'in'")
        iterable = self._expression()
        body = self._block()
        return N.For(var, iterable, body, line)

    def _return_stmt(self):
        line = self._advance().line
        if self._check(T.NEWLINE) or self._check(T.RBRACE) or self._check(T.EOF):
            return N.Return(None, line)
        value = self._expression()
        return N.Return(value, line)

    def _assign_or_expr(self):
        expr = self._expression()
        op_tok = self._cur()
        if op_tok.type in _ASSIGN_OPS:
            if not isinstance(expr, (N.Identifier, N.Index)):
                raise ParseError("invalid assignment target", op_tok.line)
            self._advance()
            value = self._expression()
            return N.Assign(expr, _ASSIGN_OPS[op_tok.type], value, op_tok.line)
        return N.ExprStmt(expr, op_tok.line)

    # -- expressions (precedence climbing) --
    def _expression(self):
        return self._or_expr()

    def _or_expr(self):
        left = self._and_expr()
        while self._check(T.OR):
            line = self._advance().line
            right = self._and_expr()
            left = N.LogicalOp("or", left, right, line)
        return left

    def _and_expr(self):
        left = self._not_expr()
        while self._check(T.AND):
            line = self._advance().line
            right = self._not_expr()
            left = N.LogicalOp("and", left, right, line)
        return left

    def _not_expr(self):
        if self._check(T.NOT):
            line = self._advance().line
            operand = self._not_expr()
            return N.UnaryOp("not", operand, line)
        return self._binary(1)

    def _binary(self, min_prec):
        left = self._unary()
        while True:
            t = self._cur().type
            prec = _BINARY_PRECEDENCE.get(t)
            if prec is None or prec < min_prec:
                break
            op_tok = self._advance()
            right = self._binary(prec + 1)
            left = N.BinaryOp(op_tok.value, left, right, op_tok.line)
        return left

    def _unary(self):
        if self._check(T.MINUS):
            line = self._advance().line
            operand = self._unary()
            return N.UnaryOp("-", operand, line)
        if self._check(T.PLUS):
            self._advance()
            return self._unary()
        return self._power()

    def _power(self):
        base = self._postfix()
        if self._check(T.STARSTAR):
            line = self._advance().line
            # right-associative: exponent may itself be a unary/power expr
            exponent = self._unary()
            return N.BinaryOp("**", base, exponent, line)
        return base

    def _postfix(self):
        expr = self._primary()
        while True:
            t = self._cur().type
            if t == T.LPAREN:
                line = self._advance().line
                args = self._arg_list()
                self._expect(T.RPAREN, "')'")
                expr = N.Call(expr, args, line)
            elif t == T.LBRACKET:
                line = self._advance().line
                index = self._expression()
                self._expect(T.RBRACKET, "']'")
                expr = N.Index(expr, index, line)
            elif t == T.DOT:
                line = self._advance().line
                name = self._expect(T.IDENT, "attribute name").value
                expr = N.Attribute(expr, name, line)
            else:
                break
        return expr

    def _arg_list(self):
        args = []
        if not self._check(T.RPAREN):
            args.append(self._expression())
            while self._match(T.COMMA):
                if self._check(T.RPAREN):
                    break
                args.append(self._expression())
        return args

    def _primary(self):
        tok = self._cur()
        t = tok.type
        if t == T.INT:
            self._advance(); return N.IntLit(tok.value, tok.line)
        if t == T.FLOAT:
            self._advance(); return N.FloatLit(tok.value, tok.line)
        if t == T.STRING:
            self._advance(); return N.StrLit(tok.value, tok.line)
        if t == T.TRUE:
            self._advance(); return N.BoolLit(True, tok.line)
        if t == T.FALSE:
            self._advance(); return N.BoolLit(False, tok.line)
        if t == T.NIL:
            self._advance(); return N.NilLit(tok.line)
        if t == T.IDENT:
            self._advance(); return N.Identifier(tok.value, tok.line)
        if t == T.LPAREN:
            self._advance()
            expr = self._expression()
            self._expect(T.RPAREN, "')'")
            return expr
        if t == T.LBRACKET:
            return self._list_literal()
        if t == T.LBRACE:
            return self._map_literal()
        got = tok.value if tok.value is not None else tok.type
        raise ParseError(f"unexpected {got!r}", tok.line)

    def _list_literal(self):
        line = self._advance().line  # '['
        items = []
        if not self._check(T.RBRACKET):
            items.append(self._expression())
            while self._match(T.COMMA):
                if self._check(T.RBRACKET):
                    break
                items.append(self._expression())
        self._expect(T.RBRACKET, "']'")
        return N.ListLit(items, line)

    def _map_literal(self):
        line = self._advance().line  # '{'
        pairs = []
        self._skip_newlines()
        if not self._check(T.RBRACE):
            pairs.append(self._map_pair())
            while self._match(T.COMMA):
                self._skip_newlines()
                if self._check(T.RBRACE):
                    break
                pairs.append(self._map_pair())
        self._skip_newlines()
        self._expect(T.RBRACE, "'}'")
        return N.MapLit(pairs, line)

    def _map_pair(self):
        key = self._expression()
        self._expect(T.COLON, "':'")
        value = self._expression()
        return (key, value)


def parse(tokens):
    return Parser(tokens).parse()
