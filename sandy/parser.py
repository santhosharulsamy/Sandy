"""Recursive-descent parser for Sandy.

Produces an AST (see nodes.py) from the token stream. Operator precedence
is handled with a small precedence-climbing table.
"""

from .errors import ParseError, SandyError
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

# Valid type names that can appear in an annotation (besides 'nil' and 'fn',
# which are keywords). 'any' opts a binding out of static checking.
_TYPE_NAMES = {"int", "float", "string", "bool", "list", "map", "any"}


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
            raise ParseError(f"expected {what}, got {got!r}", tok.line, tok.col)
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
        if t == T.IMPORT:
            return self._import_stmt()
        if t == T.STRUCT:
            return self._struct_def()
        if t == T.TRY:
            return self._try_stmt()
        if t == T.THROW:
            line = self._advance().line
            value = self._expression()
            return N.Throw(value, line)
        return self._assign_or_expr()

    def _import_stmt(self):
        line = self._advance().line  # 'import'
        tok = self._expect(T.STRING, "a module path string after 'import'")
        path = tok.value
        # Optional `as NAME` (soft keyword); otherwise derive from the filename.
        if self._check(T.IDENT) and self._cur().value == "as":
            self._advance()
            alias = self._expect(T.IDENT, "a module alias after 'as'").value
        else:
            base = path.rsplit("/", 1)[-1]
            alias = base[:-3] if base.endswith(".sy") else base
        return N.Import(path, alias, line)

    def _struct_def(self):
        line = self._advance().line  # 'struct'
        name = self._expect(T.IDENT, "struct name").value
        self._expect(T.LBRACE, "'{'")
        self._skip_newlines()
        fields, field_types = [], []
        while not self._check(T.RBRACE) and not self._check(T.EOF):
            fields.append(self._expect(T.IDENT, "field name").value)
            field_types.append(self._opt_type_annotation())
            self._match(T.COMMA)   # comma between fields is optional
            self._skip_newlines()
        end_line = self._cur().line
        self._expect(T.RBRACE, "'}'")
        return N.StructDef(name, fields, field_types, line, end_line)

    def _try_stmt(self):
        line = self._advance().line  # 'try'
        body = self._block()
        self._skip_newlines()
        self._expect(T.CATCH, "'catch' after a try block")
        catch_var = self._expect(T.IDENT, "a name to bind the error to").value
        handler = self._block()
        return N.Try(body, catch_var, handler, line)

    def _block(self):
        self._expect(T.LBRACE, "'{'")
        self._skip_newlines()
        statements = []
        while not self._check(T.RBRACE) and not self._check(T.EOF):
            statements.append(self._statement())
            self._skip_newlines()
        end_line = self._cur().line
        self._expect(T.RBRACE, "'}'")
        return N.Block(statements, end_line)

    def _func_def(self):
        line = self._advance().line  # 'fn'
        name = self._expect(T.IDENT, "function name").value
        self._expect(T.LPAREN, "'('")
        params = []
        param_types = []
        if not self._check(T.RPAREN):
            params.append(self._expect(T.IDENT, "parameter name").value)
            param_types.append(self._opt_type_annotation())
            while self._match(T.COMMA):
                params.append(self._expect(T.IDENT, "parameter name").value)
                param_types.append(self._opt_type_annotation())
        self._expect(T.RPAREN, "')'")
        ret_type = None
        if self._match(T.ARROW):
            ret_type = self._type_annotation()
        body = self._block()
        return N.FuncDef(name, params, body, line, param_types, ret_type)

    def _opt_type_annotation(self):
        if self._match(T.COLON):
            return self._type_annotation()
        return None

    def _type_annotation(self):
        tok = self._cur()
        if tok.type == T.NIL:
            self._advance(); return "nil"
        if tok.type == T.FN:
            self._advance(); return "fn"
        if tok.type == T.IDENT:
            # Any identifier is accepted as a type name here; the type checker
            # validates it (a primitive, list/map, `any`, or a struct name).
            base = tok.value
            self._advance()
            # Parameterized types: list<T>, map<K, V>
            if base in ("list", "map") and self._check(T.LT):
                self._advance()  # '<'
                args = [self._type_annotation()]
                if base == "map":
                    self._expect(T.COMMA, "',' between map key and value types")
                    args.append(self._type_annotation())
                self._expect(T.GT, "'>' to close the type parameters")
                return f"{base}<{','.join(args)}>"
            return base
        got = tok.value if tok.value is not None else tok.type
        raise ParseError(
            f"expected a type name, got {got!r}", tok.line, tok.col)

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
        # Annotated variable declaration:  name: type = value
        if isinstance(expr, N.Identifier) and self._check(T.COLON):
            line = self._advance().line  # ':'
            annotation = self._type_annotation()
            self._expect(T.ASSIGN, "'=' (an annotated variable needs a value)")
            value = self._expression()
            return N.Assign(expr, "=", value, line, annotation)
        op_tok = self._cur()
        if op_tok.type in _ASSIGN_OPS:
            if not isinstance(expr, (N.Identifier, N.Index, N.Attribute)):
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
        if t == T.FSTRING:
            self._advance(); return self._interp_string(tok)
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
        raise ParseError(f"unexpected {got!r}", tok.line, tok.col)

    def _interp_string(self, tok):
        """Build an InterpStr node from an FSTRING token, parsing each
        embedded expression's raw source into an AST."""
        parts = []
        for part in tok.value:
            if part[0] == "lit":
                parts.append(("lit", part[1]))
            else:
                _, raw, line = part
                parts.append(("expr", _parse_embedded_expr(raw, line)))
        return N.InterpStr(parts, tok.line)

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


def _parse_embedded_expr(raw, line):
    """Parse the raw source of a string interpolation into a single
    expression node. Reports errors against the string's line."""
    from .lexer import tokenize
    try:
        tokens = tokenize(raw)
    except SandyError:
        raise ParseError("invalid expression in interpolation", line)
    sub = Parser(tokens)
    if sub._check(T.EOF):
        raise ParseError("empty interpolation in string", line)
    node = sub._expression()
    sub._skip_newlines()
    if not sub._check(T.EOF):
        raise ParseError("invalid expression in interpolation", line)
    return node


def parse(tokens):
    return Parser(tokens).parse()
