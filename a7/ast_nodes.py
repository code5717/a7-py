"""
Abstract Syntax Tree (AST) node definitions for the A7 programming language.

Simple, enum-based design with minimal inheritance and visitor pattern.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, Any
from enum import Enum, auto

from .tokens import Token, TokenType
from .errors import SourceSpan


class NodeKind(Enum):
    """All AST node types."""

    # Top-level
    PROGRAM = auto()
    IMPORT = auto()
    FUNCTION = auto()
    STRUCT = auto()
    UNION = auto()
    ENUM = auto()
    TYPE_ALIAS = auto()
    CONST = auto()
    VAR = auto()

    # Types
    TYPE_PRIMITIVE = auto()
    TYPE_IDENTIFIER = auto()
    TYPE_GENERIC = auto()
    TYPE_POINTER = auto()
    TYPE_ARRAY = auto()
    TYPE_SLICE = auto()
    TYPE_FUNCTION = auto()
    TYPE_STRUCT = auto()  # Inline/anonymous struct types
    TYPE_SET = auto()

    # Expressions
    LITERAL = auto()
    IDENTIFIER = auto()
    BINARY = auto()
    UNARY = auto()
    CALL = auto()
    INDEX = auto()
    SLICE = auto()
    FIELD_ACCESS = auto()
    ADDRESS_OF = auto()  # Internal address-of node inserted by typed lowering
    DEREF = auto()       # Internal dereference node inserted by typed lowering
    CAST = auto()
    IF_EXPR = auto()
    MATCH_EXPR = auto()
    STRUCT_INIT = auto()
    ARRAY_INIT = auto()
    NEW_EXPR = auto()  # new allocation expression

    # Statements
    EXPRESSION_STMT = auto()
    BLOCK = auto()
    IF_STMT = auto()
    WHILE = auto()
    FOR = auto()
    FOR_IN = auto()  # for value in iterable
    FOR_IN_INDEXED = auto()  # for i, value in iterable
    MATCH = auto()
    BREAK = auto()
    CONTINUE = auto()
    FALL = auto()  # fallthrough statement
    RETURN = auto()
    DEFER = auto()
    DEL = auto()  # del statement for memory deallocation
    ASSIGNMENT = auto()

    # Patterns
    PATTERN_LITERAL = auto()
    PATTERN_IDENTIFIER = auto()
    PATTERN_ENUM = auto()
    PATTERN_RANGE = auto()
    PATTERN_WILDCARD = auto()

    # Utility
    PARAMETER = auto()
    FIELD = auto()
    ENUM_VARIANT = auto()
    CASE_BRANCH = auto()
    GENERIC_PARAM = auto()
    FIELD_INIT = auto()


class LiteralKind(Enum):
    """Literal value types."""

    INTEGER = auto()
    FLOAT = auto()
    CHAR = auto()
    STRING = auto()
    BOOLEAN = auto()
    NIL = auto()


class BinaryOp(Enum):
    """Binary operators."""

    # Arithmetic
    ADD = auto()  # +
    SUB = auto()  # -
    MUL = auto()  # *
    DIV = auto()  # /
    MOD = auto()  # %

    # Comparison
    EQ = auto()  # ==
    NE = auto()  # !=
    LT = auto()  # <
    LE = auto()  # <=
    GT = auto()  # >
    GE = auto()  # >=

    # Logical
    AND = auto()  # and
    OR = auto()  # or

    # Bitwise
    BIT_AND = auto()  # &
    BIT_OR = auto()  # |
    BIT_XOR = auto()  # ^
    BIT_SHL = auto()  # <<
    BIT_SHR = auto()  # >>


class UnaryOp(Enum):
    """Unary operators."""

    NEG = auto()  # -
    NOT = auto()  # !
    BIT_NOT = auto()  # ~


class AssignOp(Enum):
    """Assignment operators."""

    ASSIGN = auto()  # =
    ADD_ASSIGN = auto()  # +=
    SUB_ASSIGN = auto()  # -=
    MUL_ASSIGN = auto()  # *=
    DIV_ASSIGN = auto()  # /=
    MOD_ASSIGN = auto()  # %=
    AND_ASSIGN = auto()  # &=
    OR_ASSIGN = auto()  # |=
    XOR_ASSIGN = auto()  # ^=
    SHL_ASSIGN = auto()  # <<=
    SHR_ASSIGN = auto()  # >>=


# Simple AST node - no inheritance
@dataclass
class ASTNode:
    """Single AST node type with discriminated union via kind field."""

    kind: NodeKind
    span: Optional[SourceSpan] = None

    # All possible data fields (only relevant ones are used based on kind)
    # Declarations
    name: Optional[str] = None
    declarations: Optional[List["ASTNode"]] = None  # For PROGRAM
    module_path: Optional[str] = None  # For IMPORT
    alias: Optional[str] = None
    imported_items: Optional[List[str]] = None
    is_using: bool = False
    is_public: bool = False

    # Function-specific
    parameters: Optional[List["ASTNode"]] = None
    return_type: Optional["ASTNode"] = None
    body: Optional["ASTNode"] = None
    generic_params: Optional[List["ASTNode"]] = None

    # Struct/Union/Enum-specific
    fields: Optional[List["ASTNode"]] = None
    variants: Optional[List["ASTNode"]] = None
    is_tagged: bool = False  # For tagged unions

    # Variable/Const-specific
    value: Optional["ASTNode"] = None
    explicit_type: Optional["ASTNode"] = None

    # Type-specific
    type_name: Optional[str] = None
    target_type: Optional["ASTNode"] = None
    element_type: Optional["ASTNode"] = None
    size: Optional["ASTNode"] = None  # For array size
    parameter_types: Optional[List["ASTNode"]] = None
    type_args: Optional[List["ASTNode"]] = None
    types: Optional[List["ASTNode"]] = None  # For type sets

    # Expression-specific
    literal_kind: Optional[LiteralKind] = None
    literal_value: Any = None
    raw_text: Optional[str] = None
    left: Optional["ASTNode"] = None
    right: Optional["ASTNode"] = None
    operator: Optional[Union[BinaryOp, UnaryOp, AssignOp]] = None
    operand: Optional["ASTNode"] = None
    function: Optional["ASTNode"] = None
    arguments: Optional[List["ASTNode"]] = None
    type_arguments: Optional[List["ASTNode"]] = None
    object: Optional["ASTNode"] = None
    index: Optional["ASTNode"] = None
    start: Optional["ASTNode"] = None
    end: Optional["ASTNode"] = None
    field: Optional[str] = None
    pointer: Optional["ASTNode"] = None
    expression: Optional["ASTNode"] = None
    condition: Optional["ASTNode"] = None
    then_expr: Optional["ASTNode"] = None
    else_expr: Optional["ASTNode"] = None
    struct_type: Optional["ASTNode"] = None
    field_inits: Optional[List["ASTNode"]] = None
    elements: Optional[List["ASTNode"]] = None

    # Statement-specific
    statements: Optional[List["ASTNode"]] = None
    then_stmt: Optional["ASTNode"] = None
    else_stmt: Optional["ASTNode"] = None
    init: Optional["ASTNode"] = None
    update: Optional["ASTNode"] = None
    iterator: Optional[str] = None
    index_var: Optional[str] = None
    iterable: Optional["ASTNode"] = None
    cases: Optional[List["ASTNode"]] = None
    else_case: Optional[List["ASTNode"]] = None
    label: Optional[str] = None
    statement: Optional["ASTNode"] = None
    target: Optional["ASTNode"] = None

    # Pattern-specific
    literal: Optional["ASTNode"] = None
    enum_type: Optional[str] = None
    variant: Optional[str] = None
    is_capture_pattern: bool = False

    # Utility node data
    param_type: Optional["ASTNode"] = None
    field_type: Optional["ASTNode"] = None
    variant_type: Optional["ASTNode"] = None
    is_variadic: bool = False
    constraint: Optional["ASTNode"] = None
    patterns: Optional[List["ASTNode"]] = None
    has_fallthrough: bool = False

    # Preprocessor annotations (populated by ASTPreprocessor, read by backends)
    is_mutable: bool = False              # VAR: assigned to after init
    is_used: bool = True                  # VAR/PARAMETER: referenced somewhere
    emit_name: Optional[str] = None       # Renamed identifier (shadow resolution)
    resolved_type: Optional["ASTNode"] = None  # Inferred type annotation
    hoisted: bool = False                 # FUNCTION: was hoisted from nested position
    stdlib_canonical: Optional[str] = None  # Canonical stdlib call name


# Utility functions for creating common AST nodes
def create_program(
    declarations: List[ASTNode] = None, span: SourceSpan = None
) -> ASTNode:
    """Create a program node."""
    return ASTNode(kind=NodeKind.PROGRAM, declarations=declarations or [], span=span)


def create_literal(
    kind: LiteralKind, value: Any, raw_text: str, span: SourceSpan = None
) -> ASTNode:
    """Create a literal expression node."""
    return ASTNode(
        kind=NodeKind.LITERAL,
        literal_kind=kind,
        literal_value=value,
        raw_text=raw_text,
        span=span,
    )


def create_identifier(name: str, span: SourceSpan = None) -> ASTNode:
    """Create an identifier expression node."""
    return ASTNode(kind=NodeKind.IDENTIFIER, name=name, span=span)


def create_binary_expr(
    left: ASTNode, op: BinaryOp, right: ASTNode, span: SourceSpan = None
) -> ASTNode:
    """Create a binary expression node."""
    return ASTNode(kind=NodeKind.BINARY, left=left, operator=op, right=right, span=span)


def create_cast_expr(
    target_type: ASTNode, expression: ASTNode, span: SourceSpan = None
) -> ASTNode:
    """Create a cast expression node."""
    return ASTNode(
        kind=NodeKind.CAST, target_type=target_type, expression=expression, span=span
    )


def create_function_decl(
    name: str,
    parameters: List[ASTNode] = None,
    return_type: ASTNode = None,
    body: ASTNode = None,
    is_public: bool = False,
    span: SourceSpan = None,
) -> ASTNode:
    """Create a function declaration node."""
    return ASTNode(
        kind=NodeKind.FUNCTION,
        name=name,
        parameters=parameters or [],
        return_type=return_type,
        body=body,
        is_public=is_public,
        span=span,
    )


def create_primitive_type(type_name: str, span: SourceSpan = None) -> ASTNode:
    """Create a primitive type node."""
    return ASTNode(kind=NodeKind.TYPE_PRIMITIVE, type_name=type_name, span=span)


def create_block(statements: List[ASTNode] = None, span: SourceSpan = None) -> ASTNode:
    """Create a block statement node."""
    return ASTNode(kind=NodeKind.BLOCK, statements=statements or [], span=span)


def create_parameter(
    name: str, param_type: ASTNode, is_variadic: bool = False, span: SourceSpan = None
) -> ASTNode:
    """Create a parameter node."""
    return ASTNode(
        kind=NodeKind.PARAMETER,
        name=name,
        param_type=param_type,
        is_variadic=is_variadic,
        span=span,
    )


def create_function_type(
    param_types: List[ASTNode], return_type: ASTNode = None, span: SourceSpan = None
) -> ASTNode:
    """Create a function type node for function pointers/type declarations.

    Args:
        param_types: List of type nodes for function parameters
        return_type: Type node for return value (None for void)
        span: Source span for error reporting

    Returns:
        ASTNode with kind=TYPE_FUNCTION
    """
    return ASTNode(
        kind=NodeKind.TYPE_FUNCTION,
        parameter_types=param_types,
        return_type=return_type,
        span=span,
    )


def create_inline_struct_type(
    fields: List[ASTNode], span: SourceSpan = None
) -> ASTNode:
    """Create an inline/anonymous struct type node.

    Args:
        fields: List of FIELD nodes defining the struct's fields
        span: Source span for error reporting

    Returns:
        ASTNode with kind=TYPE_STRUCT

    Note: Inline struct types are VALUE types, not reference types.
    They cannot be assigned nil. Use ref struct {...} for nullable struct types.
    """
    return ASTNode(
        kind=NodeKind.TYPE_STRUCT,
        fields=fields,
        span=span,
    )


def create_return_stmt(value: ASTNode = None, span: SourceSpan = None) -> ASTNode:
    """Create a return statement node."""
    return ASTNode(kind=NodeKind.RETURN, value=value, span=span)


def create_new_expr(type_node: ASTNode, span: SourceSpan = None) -> ASTNode:
    """Create a new (allocation) expression node."""
    return ASTNode(kind=NodeKind.NEW_EXPR, target_type=type_node, span=span)


def create_del_stmt(expr: ASTNode, span: SourceSpan = None) -> ASTNode:
    """Create a del (deallocation) statement node."""
    return ASTNode(kind=NodeKind.DEL, expression=expr, span=span)


def create_call_expr(
    function: ASTNode, arguments: List[ASTNode] = None, span: SourceSpan = None
) -> ASTNode:
    """Create a function call expression node."""
    return ASTNode(
        kind=NodeKind.CALL, function=function, arguments=arguments or [], span=span
    )


def create_assignment_stmt(
    target: ASTNode, op: AssignOp, value: ASTNode, span: SourceSpan = None
) -> ASTNode:
    """Create an assignment statement node."""
    return ASTNode(
        kind=NodeKind.ASSIGNMENT, target=target, operator=op, value=value, span=span
    )


def create_var_decl(
    name: str,
    value: ASTNode,
    explicit_type: ASTNode = None,
    is_public: bool = False,
    span: SourceSpan = None,
) -> ASTNode:
    """Create a variable declaration node."""
    return ASTNode(
        kind=NodeKind.VAR,
        name=name,
        value=value,
        explicit_type=explicit_type,
        is_public=is_public,
        span=span,
    )


def create_const_decl(
    name: str,
    value: ASTNode,
    explicit_type: ASTNode = None,
    is_public: bool = False,
    span: SourceSpan = None,
) -> ASTNode:
    """Create a constant declaration node."""
    return ASTNode(
        kind=NodeKind.CONST,
        name=name,
        value=value,
        explicit_type=explicit_type,
        is_public=is_public,
        span=span,
    )


# Conversion functions from tokens to operators
def token_to_binary_op(token_type: TokenType) -> Optional[BinaryOp]:
    """Convert a token type to a binary operator."""
    mapping = {
        TokenType.PLUS: BinaryOp.ADD,
        TokenType.MINUS: BinaryOp.SUB,
        TokenType.MULTIPLY: BinaryOp.MUL,
        TokenType.DIVIDE: BinaryOp.DIV,
        TokenType.MODULO: BinaryOp.MOD,
        TokenType.EQUAL: BinaryOp.EQ,
        TokenType.NOT_EQUAL: BinaryOp.NE,
        TokenType.LESS_THAN: BinaryOp.LT,
        TokenType.LESS_EQUAL: BinaryOp.LE,
        TokenType.GREATER_THAN: BinaryOp.GT,
        TokenType.GREATER_EQUAL: BinaryOp.GE,
        TokenType.AND: BinaryOp.AND,
        TokenType.OR: BinaryOp.OR,
        TokenType.BITWISE_AND: BinaryOp.BIT_AND,
        TokenType.BITWISE_OR: BinaryOp.BIT_OR,
        TokenType.BITWISE_XOR: BinaryOp.BIT_XOR,
        TokenType.LEFT_SHIFT: BinaryOp.BIT_SHL,
        TokenType.RIGHT_SHIFT: BinaryOp.BIT_SHR,
    }
    return mapping.get(token_type)


def token_to_unary_op(token_type: TokenType) -> Optional[UnaryOp]:
    """Convert a token type to a unary operator."""
    mapping = {
        TokenType.MINUS: UnaryOp.NEG,
        TokenType.NOT: UnaryOp.NOT,
        TokenType.LOGICAL_NOT: UnaryOp.NOT,
        TokenType.BITWISE_NOT: UnaryOp.BIT_NOT,
    }
    return mapping.get(token_type)


def token_to_assign_op(token_type: TokenType) -> Optional[AssignOp]:
    """Convert a token type to an assignment operator."""
    mapping = {
        TokenType.ASSIGN: AssignOp.ASSIGN,
        TokenType.PLUS_ASSIGN: AssignOp.ADD_ASSIGN,
        TokenType.MINUS_ASSIGN: AssignOp.SUB_ASSIGN,
        TokenType.MULTIPLY_ASSIGN: AssignOp.MUL_ASSIGN,
        TokenType.DIVIDE_ASSIGN: AssignOp.DIV_ASSIGN,
        TokenType.MODULO_ASSIGN: AssignOp.MOD_ASSIGN,
        TokenType.BITWISE_AND_ASSIGN: AssignOp.AND_ASSIGN,
        TokenType.BITWISE_OR_ASSIGN: AssignOp.OR_ASSIGN,
        TokenType.BITWISE_XOR_ASSIGN: AssignOp.XOR_ASSIGN,
        TokenType.LEFT_SHIFT_ASSIGN: AssignOp.SHL_ASSIGN,
        TokenType.RIGHT_SHIFT_ASSIGN: AssignOp.SHR_ASSIGN,
    }
    return mapping.get(token_type)


# Helper functions for creating AST nodes with source spans
def create_span_from_token(token: Token) -> SourceSpan:
    """Create a SourceSpan from a single token."""
    return SourceSpan(
        start_line=token.line,
        start_column=token.column,
        end_line=token.line,
        end_column=token.column + token.length,
        length=token.length,
    )


def create_span_from_tokens(start_token: Token, end_token: Token) -> SourceSpan:
    """Create a SourceSpan that covers from start_token to end_token."""
    return SourceSpan(
        start_line=start_token.line,
        start_column=start_token.column,
        end_line=end_token.line,
        end_column=end_token.column + end_token.length,
    )


def _unescape_literal_content(content: str) -> str:
    """Decode tokenizer-validated escape sequences from literal content."""
    escapes = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "\\": "\\",
        "'": "'",
        '"': '"',
        "0": "\0",
    }
    out: list[str] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        if i + 1 >= len(content):
            out.append("\\")
            i += 1
            continue

        escape = content[i + 1]
        if escape == "x" and i + 3 < len(content):
            out.append(chr(int(content[i + 2 : i + 4], 16)))
            i += 4
            continue

        out.append(escapes.get(escape, escape))
        i += 2

    return "".join(out)


def create_literal_from_token(token: Token) -> ASTNode:
    """Create a literal AST node from a token."""
    span = create_span_from_token(token)

    if token.type == TokenType.INTEGER_LITERAL:
        # Parse integer value
        value_str = token.value
        if value_str.startswith("0x"):
            value = int(value_str, 16)
        elif value_str.startswith("0b"):
            value = int(value_str, 2)
        elif value_str.startswith("0o"):
            value = int(value_str, 8)
        else:
            value = int(value_str)
        return create_literal(LiteralKind.INTEGER, value, token.value, span)
    elif token.type == TokenType.FLOAT_LITERAL:
        return create_literal(LiteralKind.FLOAT, float(token.value), token.value, span)
    elif token.type == TokenType.CHAR_LITERAL:
        char_content = token.value[1:-1]  # Remove quotes
        value = _unescape_literal_content(char_content)
        return create_literal(LiteralKind.CHAR, value, token.value, span)
    elif token.type == TokenType.STRING_LITERAL:
        string_content = token.value[1:-1]  # Remove quotes
        value = _unescape_literal_content(string_content)
        return create_literal(LiteralKind.STRING, value, token.value, span)
    elif token.type == TokenType.TRUE_LITERAL:
        return create_literal(LiteralKind.BOOLEAN, True, token.value, span)
    elif token.type == TokenType.FALSE_LITERAL:
        return create_literal(LiteralKind.BOOLEAN, False, token.value, span)
    elif token.type == TokenType.NIL_LITERAL:
        return create_literal(LiteralKind.NIL, None, token.value, span)
    else:
        raise ValueError(f"Cannot create literal from token type: {token.type}")


def get_binary_precedence(op: BinaryOp) -> int:
    """Get precedence for binary operators (higher number = higher precedence)."""
    precedence = {
        # Multiplicative (highest)
        BinaryOp.MUL: 12,
        BinaryOp.DIV: 12,
        BinaryOp.MOD: 12,
        # Additive
        BinaryOp.ADD: 11,
        BinaryOp.SUB: 11,
        # Shift
        BinaryOp.BIT_SHL: 10,
        BinaryOp.BIT_SHR: 10,
        # Relational
        BinaryOp.LT: 9,
        BinaryOp.GT: 9,
        BinaryOp.LE: 9,
        BinaryOp.GE: 9,
        # Equality
        BinaryOp.EQ: 8,
        BinaryOp.NE: 8,
        # Bitwise AND
        BinaryOp.BIT_AND: 7,
        # Bitwise XOR
        BinaryOp.BIT_XOR: 6,
        # Bitwise OR
        BinaryOp.BIT_OR: 5,
        # Logical AND
        BinaryOp.AND: 4,
        # Logical OR (lowest)
        BinaryOp.OR: 3,
    }
    return precedence.get(op, 0)
