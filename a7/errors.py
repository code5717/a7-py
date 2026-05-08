"""
Compiler error types and exception classes with Rich formatting support.
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich import box
from rich.rule import Rule


class ErrorSeverity(Enum):
    """Error severity levels for different types of errors."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    NOTE = "note"


class TokenizerErrorType(Enum):
    """Specific tokenizer error types with descriptive messages and advice."""

    OUT_OF_MEMORY = "out_of_memory"
    INVALID_CHARACTER = "invalid_character"
    TOO_LONG_IDENTIFIER = "too_long_identifier"
    TOO_LONG_NUMBER = "too_long_number"
    TOO_LONG_STRING = "too_long_string"
    NOT_CLOSED_CHAR = "not_closed_char"
    NOT_CLOSED_STRING = "not_closed_string"
    END_OF_FILE = "end_of_file"
    FILE_EMPTY = "file_empty"
    # Diagnostic code, not a credential.
    BAD_TOKEN_AT_GLOBAL = "bad_token_at_global"  # nosec B105
    TABS_UNSUPPORTED = "tabs_unsupported"
    INVALID_ESCAPE_CHAR = "invalid_escape_char"
    NOT_CLOSED_COMMENT = "not_closed_comment"
    INVALID_SCIENTIFIC_NOTATION = "invalid_scientific_notation"
    INVALID_HEX_NUMBER = "invalid_hex_number"
    INVALID_BINARY_NUMBER = "invalid_binary_number"
    INVALID_OCTAL_NUMBER = "invalid_octal_number"
    INVALID_GENERIC_SYNTAX = "invalid_generic_syntax"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class SemanticErrorType(Enum):
    """Specific semantic error types (name resolution, scoping, validation)."""

    # Name resolution errors
    UNDEFINED_IDENTIFIER = "undefined_identifier"
    ALREADY_DEFINED = "already_defined"
    DUPLICATE_PARAMETER = "duplicate_parameter"
    DUPLICATE_FIELD = "duplicate_field"
    DUPLICATE_VARIANT = "duplicate_variant"
    DUPLICATE_GENERIC_PARAM = "duplicate_generic_param"

    # Scope errors
    BREAK_OUTSIDE_LOOP = "break_outside_loop"
    BREAK_UNDEFINED_LABEL = "break_undefined_label"
    CONTINUE_OUTSIDE_LOOP = "continue_outside_loop"
    CONTINUE_UNDEFINED_LABEL = "continue_undefined_label"
    RETURN_OUTSIDE_FUNCTION = "return_outside_function"
    DEFER_OUTSIDE_FUNCTION = "defer_outside_function"

    # Semantic validation
    UNREACHABLE_CODE = "unreachable_code"
    MISSING_RETURN = "missing_return"
    CANNOT_ASSIGN_TO_IMMUTABLE = "cannot_assign_to_immutable"
    INVALID_DEFER_SCOPE = "invalid_defer_scope"
    MEMORY_LEAK = "memory_leak"
    DOUBLE_FREE = "double_free"
    DELETE_NON_REFERENCE = "delete_non_reference"
    NIL_NOT_REFERENCE_TYPE = "nil_not_reference_type"
    MISSING_TYPE_ANNOTATION = "missing_type_annotation"
    NON_EXHAUSTIVE_MATCH = "non_exhaustive_match"
    INVALID_PATTERN = "invalid_pattern"
    UNSUPPORTED_FALLTHROUGH = "unsupported_fallthrough"
    RECURSION_NOT_ALLOWED = "recursion_not_allowed"

    # Import errors
    CIRCULAR_IMPORT = "circular_import"
    MODULE_NOT_FOUND = "module_not_found"
    IMPORT_NAME_CONFLICT = "import_name_conflict"

    # Generic errors
    GENERIC_PARAM_MISMATCH = "generic_param_mismatch"
    CONSTRAINT_VIOLATION = "constraint_violation"

    # General
    UNEXPECTED_NODE_KIND = "unexpected_node_kind"
    UNKNOWN = "unknown"


class TypeErrorType(Enum):
    """Specific type checking error types."""

    # Type mismatch errors
    TYPE_MISMATCH = "type_mismatch"
    RETURN_TYPE_MISMATCH = "return_type_mismatch"
    ASSIGNMENT_TYPE_MISMATCH = "assignment_type_mismatch"
    CONDITION_NOT_BOOL = "condition_not_bool"
    IF_EXPR_TYPE_MISMATCH = "if_expr_type_mismatch"

    # Type requirement errors
    REQUIRES_NUMERIC_TYPE = "requires_numeric_type"
    REQUIRES_INTEGER_TYPE = "requires_integer_type"
    REQUIRES_BOOL_TYPE = "requires_bool_type"
    REQUIRES_ARRAY_OR_SLICE = "requires_array_or_slice"
    REQUIRES_STRUCT_TYPE = "requires_struct_type"
    REQUIRES_POINTER_TYPE = "requires_pointer_type"
    REQUIRES_FUNCTION_TYPE = "requires_function_type"

    # Function call errors
    NOT_CALLABLE = "not_callable"
    WRONG_ARGUMENT_COUNT = "wrong_argument_count"
    ARGUMENT_TYPE_MISMATCH = "argument_type_mismatch"

    # Field/member access errors
    NO_SUCH_FIELD = "no_such_field"
    FIELD_ACCESS_ON_NON_STRUCT = "field_access_on_non_struct"

    # Index errors
    CANNOT_INDEX_TYPE = "cannot_index_type"
    INDEX_NOT_INTEGER = "index_not_integer"

    # Dereference errors
    CANNOT_DEREFERENCE = "cannot_dereference"

    # Nil errors
    NIL_NOT_ALLOWED = "nil_not_allowed"
    NIL_ONLY_FOR_REFERENCES = "nil_only_for_references"

    # Declaration errors
    MISSING_TYPE_OR_INITIALIZER = "missing_type_or_initializer"
    UNDEFINED_TYPE = "undefined_type"
    INCOMPATIBLE_TYPES = "incompatible_types"

    # Cast errors
    INVALID_CAST = "invalid_cast"
    UNSAFE_CAST = "unsafe_cast"

    # Operator errors
    OPERATOR_TYPE_MISMATCH = "operator_type_mismatch"

    # General
    UNKNOWN_TYPE = "unknown_type"
    UNKNOWN = "unknown"


def get_tokenizer_error_message(error_type: TokenizerErrorType) -> str:
    """Get the descriptive error message for a tokenizer error type."""
    messages = {
        TokenizerErrorType.OUT_OF_MEMORY: "Out of memory",
        TokenizerErrorType.INVALID_CHARACTER: "Invalid character",
        TokenizerErrorType.TOO_LONG_IDENTIFIER: "Identifier is too long",
        TokenizerErrorType.TOO_LONG_NUMBER: "Number is too long",
        TokenizerErrorType.TOO_LONG_STRING: "String is too long",
        TokenizerErrorType.NOT_CLOSED_CHAR: "The char is not closed",
        TokenizerErrorType.NOT_CLOSED_STRING: "The string is not closed",
        TokenizerErrorType.END_OF_FILE: "Reached end of file",
        TokenizerErrorType.FILE_EMPTY: "The file is empty",
        TokenizerErrorType.BAD_TOKEN_AT_GLOBAL: "Found global token at its forbidden scope",
        TokenizerErrorType.TABS_UNSUPPORTED: "Tabs '\\t' are unsupported",
        TokenizerErrorType.INVALID_ESCAPE_CHAR: "Invalid escaped char",
        TokenizerErrorType.NOT_CLOSED_COMMENT: "Comment not closed",
        TokenizerErrorType.INVALID_SCIENTIFIC_NOTATION: "Invalid scientific notation",
        TokenizerErrorType.INVALID_HEX_NUMBER: "Invalid hexadecimal number",
        TokenizerErrorType.INVALID_BINARY_NUMBER: "Invalid binary number",
        TokenizerErrorType.INVALID_OCTAL_NUMBER: "Invalid octal number",
        TokenizerErrorType.INVALID_GENERIC_SYNTAX: "Invalid generic type syntax",
        TokenizerErrorType.UNSUPPORTED: "Unsupported feature",
        TokenizerErrorType.UNKNOWN: "Unknown error",
    }
    return messages.get(error_type, "Unknown error")


def get_tokenizer_error_advice(error_type: TokenizerErrorType) -> str:
    """Get helpful advice for fixing a tokenizer error."""
    advice = {
        TokenizerErrorType.INVALID_ESCAPE_CHAR: "Change the letter after \\",
        TokenizerErrorType.NOT_CLOSED_COMMENT: "Close the comment with delimiter",
        TokenizerErrorType.INVALID_CHARACTER: "Remove this character",
        TokenizerErrorType.OUT_OF_MEMORY: "The compiler needs more memory",
        TokenizerErrorType.TOO_LONG_IDENTIFIER: "Identifier must not exceed 100 characters",
        TokenizerErrorType.TOO_LONG_NUMBER: "Number must not exceed 100 digits",
        TokenizerErrorType.TOO_LONG_STRING: "String must not exceed maximum length",
        TokenizerErrorType.NOT_CLOSED_CHAR: "Close the char with a quote",
        TokenizerErrorType.NOT_CLOSED_STRING: "Close the string with a double quote",
        TokenizerErrorType.END_OF_FILE: "Needs more code for compiling",
        TokenizerErrorType.FILE_EMPTY: "Do not compile empty files",
        TokenizerErrorType.BAD_TOKEN_AT_GLOBAL: "Do not put this token in global scope",
        TokenizerErrorType.TABS_UNSUPPORTED: "Convert the tabs to spaces",
        TokenizerErrorType.INVALID_SCIENTIFIC_NOTATION: "Add digits after the exponent",
        TokenizerErrorType.INVALID_HEX_NUMBER: "Use valid hexadecimal digits (0-9, a-f, A-F)",
        TokenizerErrorType.INVALID_BINARY_NUMBER: "Use only binary digits (0, 1)",
        TokenizerErrorType.INVALID_OCTAL_NUMBER: "Use only octal digits (0-7)",
        TokenizerErrorType.INVALID_GENERIC_SYNTAX: "Generic types must start with '$' followed by letters and underscores only",
        TokenizerErrorType.UNSUPPORTED: "This feature is not yet supported",
        TokenizerErrorType.UNKNOWN: "Please report this error",
    }
    return advice.get(error_type, "Please report this error")


def get_semantic_error_message(error_type: SemanticErrorType) -> str:
    """Get the descriptive error message for a semantic error type."""
    messages = {
        # Name resolution errors
        SemanticErrorType.UNDEFINED_IDENTIFIER: "Undefined identifier",
        SemanticErrorType.ALREADY_DEFINED: "Already defined",
        SemanticErrorType.DUPLICATE_PARAMETER: "Duplicate parameter",
        SemanticErrorType.DUPLICATE_FIELD: "Duplicate field",
        SemanticErrorType.DUPLICATE_VARIANT: "Duplicate enum variant",
        SemanticErrorType.DUPLICATE_GENERIC_PARAM: "Duplicate generic parameter",

        # Scope errors
        SemanticErrorType.BREAK_OUTSIDE_LOOP: "Break statement outside loop",
        SemanticErrorType.BREAK_UNDEFINED_LABEL: "Break label is not defined",
        SemanticErrorType.CONTINUE_OUTSIDE_LOOP: "Continue statement outside loop",
        SemanticErrorType.CONTINUE_UNDEFINED_LABEL: "Continue label is not defined",
        SemanticErrorType.RETURN_OUTSIDE_FUNCTION: "Return statement outside function",
        SemanticErrorType.DEFER_OUTSIDE_FUNCTION: "Defer statement outside function",

        # Semantic validation
        SemanticErrorType.UNREACHABLE_CODE: "Unreachable code",
        SemanticErrorType.MISSING_RETURN: "Missing return statement",
        SemanticErrorType.CANNOT_ASSIGN_TO_IMMUTABLE: "Cannot assign to immutable binding",
        SemanticErrorType.INVALID_DEFER_SCOPE: "Invalid defer scope",
        SemanticErrorType.MEMORY_LEAK: "Potential memory leak",
        SemanticErrorType.DOUBLE_FREE: "Potential double free",
        SemanticErrorType.DELETE_NON_REFERENCE: "Delete requires a reference type",
        SemanticErrorType.NIL_NOT_REFERENCE_TYPE: "Nil requires a reference type",
        SemanticErrorType.MISSING_TYPE_ANNOTATION: "Missing type annotation",
        SemanticErrorType.NON_EXHAUSTIVE_MATCH: "Non-exhaustive match",
        SemanticErrorType.UNSUPPORTED_FALLTHROUGH: "Invalid fallthrough",
        SemanticErrorType.RECURSION_NOT_ALLOWED: "Recursion is not allowed",

        # Import errors
        SemanticErrorType.CIRCULAR_IMPORT: "Circular import detected",
        SemanticErrorType.MODULE_NOT_FOUND: "Module not found",
        SemanticErrorType.IMPORT_NAME_CONFLICT: "Import name conflicts with existing definition",

        # Generic errors
        SemanticErrorType.GENERIC_PARAM_MISMATCH: "Generic parameter count mismatch",
        SemanticErrorType.CONSTRAINT_VIOLATION: "Generic constraint violation",

        # General
        SemanticErrorType.UNEXPECTED_NODE_KIND: "Unexpected AST node kind",
        SemanticErrorType.UNKNOWN: "Unknown semantic error",
    }
    return messages.get(error_type, "Unknown semantic error")


def get_semantic_error_advice(error_type: SemanticErrorType) -> str:
    """Get helpful advice for fixing a semantic error."""
    advice = {
        # Name resolution errors
        SemanticErrorType.UNDEFINED_IDENTIFIER: "Check the identifier name and ensure it's declared before use",
        SemanticErrorType.ALREADY_DEFINED: "Choose a different name or remove the previous definition",
        SemanticErrorType.DUPLICATE_PARAMETER: "Each parameter must have a unique name",
        SemanticErrorType.DUPLICATE_FIELD: "Each field must have a unique name",
        SemanticErrorType.DUPLICATE_VARIANT: "Each enum variant must have a unique name",
        SemanticErrorType.DUPLICATE_GENERIC_PARAM: "Each generic parameter must have a unique name",

        # Scope errors
        SemanticErrorType.BREAK_OUTSIDE_LOOP: "Break can only be used inside a loop",
        SemanticErrorType.BREAK_UNDEFINED_LABEL: "Use a label that is visible from this break statement",
        SemanticErrorType.CONTINUE_OUTSIDE_LOOP: "Continue can only be used inside a loop",
        SemanticErrorType.CONTINUE_UNDEFINED_LABEL: "Use a label that is visible from this continue statement",
        SemanticErrorType.RETURN_OUTSIDE_FUNCTION: "Return can only be used inside a function",
        SemanticErrorType.DEFER_OUTSIDE_FUNCTION: "Defer can only be used inside a function",

        # Semantic validation
        SemanticErrorType.UNREACHABLE_CODE: "Remove unreachable code or fix control flow",
        SemanticErrorType.MISSING_RETURN: "Add a return statement that covers all code paths",
        SemanticErrorType.CANNOT_ASSIGN_TO_IMMUTABLE: "Declare the binding with := if it needs to be reassigned",
        SemanticErrorType.INVALID_DEFER_SCOPE: "Defer statements must be used carefully with scoping rules",
        SemanticErrorType.MEMORY_LEAK: "Ensure all allocated memory is freed",
        SemanticErrorType.DOUBLE_FREE: "Ensure memory is only freed once",
        SemanticErrorType.DELETE_NON_REFERENCE: "Only values with reference type can be deleted",
        SemanticErrorType.NIL_NOT_REFERENCE_TYPE: "Use nil only where a reference type is expected",
        SemanticErrorType.MISSING_TYPE_ANNOTATION: "Add a type annotation or an initializer for this declaration",
        SemanticErrorType.NON_EXHAUSTIVE_MATCH: "Add missing cases or an else/wildcard branch to cover remaining values",
        SemanticErrorType.UNSUPPORTED_FALLTHROUGH: "Use fall only as the final statement of a non-final match case",
        SemanticErrorType.RECURSION_NOT_ALLOWED: "Rewrite the function using loops, explicit stacks, or another iterative structure",

        # Import errors
        SemanticErrorType.CIRCULAR_IMPORT: "Reorganize modules to remove circular dependencies",
        SemanticErrorType.MODULE_NOT_FOUND: "Check the module path and ensure the file exists",
        SemanticErrorType.IMPORT_NAME_CONFLICT: "Use an alias for the import or rename the conflicting definition",

        # Generic errors
        SemanticErrorType.GENERIC_PARAM_MISMATCH: "Provide the correct number of generic type arguments",
        SemanticErrorType.CONSTRAINT_VIOLATION: "Ensure the type satisfies the generic constraint",

        # General
        SemanticErrorType.UNEXPECTED_NODE_KIND: "This is likely a compiler bug, please report it",
        SemanticErrorType.UNKNOWN: "Please report this error",
    }
    return advice.get(error_type, "Please report this error")


def get_type_error_message(error_type: TypeErrorType) -> str:
    """Get the descriptive error message for a type error type."""
    messages = {
        # Type mismatch errors
        TypeErrorType.TYPE_MISMATCH: "Type mismatch",
        TypeErrorType.RETURN_TYPE_MISMATCH: "Return type mismatch",
        TypeErrorType.ASSIGNMENT_TYPE_MISMATCH: "Assignment type mismatch",
        TypeErrorType.CONDITION_NOT_BOOL: "Condition must be bool",
        TypeErrorType.IF_EXPR_TYPE_MISMATCH: "If expression branches have different types",

        # Type requirement errors
        TypeErrorType.REQUIRES_NUMERIC_TYPE: "Requires numeric type",
        TypeErrorType.REQUIRES_INTEGER_TYPE: "Requires integer type",
        TypeErrorType.REQUIRES_BOOL_TYPE: "Requires bool type",
        TypeErrorType.REQUIRES_ARRAY_OR_SLICE: "Requires array or slice type",
        TypeErrorType.REQUIRES_STRUCT_TYPE: "Requires struct type",
        TypeErrorType.REQUIRES_POINTER_TYPE: "Requires pointer type",
        TypeErrorType.REQUIRES_FUNCTION_TYPE: "Requires function type",

        # Function call errors
        TypeErrorType.NOT_CALLABLE: "Type is not callable",
        TypeErrorType.WRONG_ARGUMENT_COUNT: "Wrong number of arguments",
        TypeErrorType.ARGUMENT_TYPE_MISMATCH: "Argument type mismatch",

        # Field/member access errors
        TypeErrorType.NO_SUCH_FIELD: "Struct has no such field",
        TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT: "Cannot access field on non-struct type",

        # Index errors
        TypeErrorType.CANNOT_INDEX_TYPE: "Cannot index this type",
        TypeErrorType.INDEX_NOT_INTEGER: "Array index must be integer",

        # Dereference errors
        TypeErrorType.CANNOT_DEREFERENCE: "Cannot dereference non-pointer type",

        # Nil errors
        TypeErrorType.NIL_NOT_ALLOWED: "Nil not allowed for this type",
        TypeErrorType.NIL_ONLY_FOR_REFERENCES: "Nil only allowed for reference types",

        # Declaration errors
        TypeErrorType.MISSING_TYPE_OR_INITIALIZER: "Variable requires type annotation or initializer",
        TypeErrorType.UNDEFINED_TYPE: "Undefined type",
        TypeErrorType.INCOMPATIBLE_TYPES: "Incompatible types",

        # Cast errors
        TypeErrorType.INVALID_CAST: "Invalid type cast",
        TypeErrorType.UNSAFE_CAST: "Unsafe type cast",

        # Operator errors
        TypeErrorType.OPERATOR_TYPE_MISMATCH: "Operator requires compatible types",

        # General
        TypeErrorType.UNKNOWN_TYPE: "Unknown type",
        TypeErrorType.UNKNOWN: "Unknown type error",
    }
    return messages.get(error_type, "Unknown type error")


def get_type_error_advice(error_type: TypeErrorType) -> str:
    """Get helpful advice for fixing a type error."""
    advice = {
        # Type mismatch errors
        TypeErrorType.TYPE_MISMATCH: "Ensure the types match or use an explicit cast",
        TypeErrorType.RETURN_TYPE_MISMATCH: "Return value must match the function's return type",
        TypeErrorType.ASSIGNMENT_TYPE_MISMATCH: "The assigned value must match the variable's type",
        TypeErrorType.CONDITION_NOT_BOOL: "Use a boolean expression for the condition",
        TypeErrorType.IF_EXPR_TYPE_MISMATCH: "Both branches of if expression must have the same type",

        # Type requirement errors
        TypeErrorType.REQUIRES_NUMERIC_TYPE: "Use i8, i16, i32, i64, isize, u8, u16, u32, u64, usize, f32, or f64",
        TypeErrorType.REQUIRES_INTEGER_TYPE: "Use i8, i16, i32, i64, isize, u8, u16, u32, u64, or usize",
        TypeErrorType.REQUIRES_BOOL_TYPE: "Use a bool value (true or false)",
        TypeErrorType.REQUIRES_ARRAY_OR_SLICE: "Use an array or slice type",
        TypeErrorType.REQUIRES_STRUCT_TYPE: "Use a struct type",
        TypeErrorType.REQUIRES_POINTER_TYPE: "Use a pointer (ref) type",
        TypeErrorType.REQUIRES_FUNCTION_TYPE: "Use a function or function pointer",

        # Function call errors
        TypeErrorType.NOT_CALLABLE: "Only functions can be called",
        TypeErrorType.WRONG_ARGUMENT_COUNT: "Provide the correct number of arguments",
        TypeErrorType.ARGUMENT_TYPE_MISMATCH: "Ensure argument types match parameter types",

        # Field/member access errors
        TypeErrorType.NO_SUCH_FIELD: "Check the field name and struct definition",
        TypeErrorType.FIELD_ACCESS_ON_NON_STRUCT: "Field access requires a struct type",

        # Index errors
        TypeErrorType.CANNOT_INDEX_TYPE: "Only arrays and slices can be indexed",
        TypeErrorType.INDEX_NOT_INTEGER: "Use an integer type for array indexing",

        # Dereference errors
        TypeErrorType.CANNOT_DEREFERENCE: "Only pointers can be dereferenced using .val",

        # Nil errors
        TypeErrorType.NIL_NOT_ALLOWED: "This type cannot be nil",
        TypeErrorType.NIL_ONLY_FOR_REFERENCES: "Only reference (ref) types can be nil",

        # Declaration errors
        TypeErrorType.MISSING_TYPE_OR_INITIALIZER: "Add either a type annotation or an initializer",
        TypeErrorType.UNDEFINED_TYPE: "Ensure the type is defined before use",
        TypeErrorType.INCOMPATIBLE_TYPES: "These types cannot be used together",

        # Cast errors
        TypeErrorType.INVALID_CAST: "These types cannot be cast to each other",
        TypeErrorType.UNSAFE_CAST: "This cast may lose information or cause undefined behavior",

        # Operator errors
        TypeErrorType.OPERATOR_TYPE_MISMATCH: "Ensure operand types are compatible with the operator",

        # General
        TypeErrorType.UNKNOWN_TYPE: "The type could not be determined",
        TypeErrorType.UNKNOWN: "Please report this error",
    }
    return advice.get(error_type, "Please report this error")


@dataclass
class SourceSpan:
    """Represents a span of source code for error reporting."""

    start_line: int
    start_column: int
    end_line: int
    end_column: int
    length: int = 0

    def __post_init__(self):
        if self.length == 0:
            # Calculate character length for single-line spans
            if self.start_line == self.end_line:
                self.length = self.end_column - self.start_column
            else:
                self.length = 1  # Multi-line spans default to 1


class ErrorFormatter:
    """Rich-based error formatter with source code context."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def format_error(self, error: "CompilerError", context_lines: int = 2) -> None:
        """Format and display an error with source code context."""
        # Determine error type and severity for styling
        if isinstance(error, TokenizerError):
            severity = ErrorSeverity.ERROR
        elif isinstance(error, ParseError):
            severity = ErrorSeverity.ERROR
        elif isinstance(error, (SemanticError, TypeCheckError)):
            severity = ErrorSeverity.ERROR
        else:
            severity = ErrorSeverity.ERROR

        # Build enhanced error message with improved styling
        error_msg = Text()
        error_msg.append("error", style="red bold")
        error_msg.append(": ", style="red")
        error_msg.append(error.message, style="red")

        if error.span:
            error_msg.append(" ", style="red")
            error_msg.append("[line ", style="dim white")
            error_msg.append(str(error.span.start_line), style="yellow bold")
            error_msg.append(": col ", style="dim white")
            error_msg.append(str(error.span.start_column), style="yellow bold")
            error_msg.append("]", style="dim white")

        self.console.print(error_msg)

        # Show source code context if available
        if error.source_lines and error.span:
            # Add a subtle separator before source context
            separator = Rule(characters="─", style="black")
            self.console.print(separator)

            context_text = self._build_source_context(
                error.source_lines, error.span, context_lines
            )
            self.console.print(context_text)

            # Add subtle separator after context
            separator_bottom = Rule(characters="─", style="black")
            self.console.print(separator_bottom)

        # Show advice if available (for errors with error_type) - after context
        if hasattr(error, "error_type") and error.error_type:
            advice = None
            if isinstance(error, TokenizerError):
                advice = get_tokenizer_error_advice(error.error_type)
            elif isinstance(error, SemanticError):
                advice = get_semantic_error_advice(error.error_type)
            elif isinstance(error, TypeCheckError):
                advice = get_type_error_advice(error.error_type)

            if advice:
                advice_msg = Text()
                advice_msg.append("hint", style="cyan bold")
                advice_msg.append(": ", style="cyan")
                advice_msg.append(advice, style="cyan dim")
                self.console.print(advice_msg)

        # Add a blank line after each error
        self.console.print()

    def _build_source_context(
        self, source_lines: List[str], span: SourceSpan, context_lines: int
    ) -> Text:
        """Build syntax-highlighted source code context with error highlighting."""
        # For small files, ensure we show reasonable context
        total_lines = len(source_lines)

        if total_lines <= 5:
            # For very small files, show all lines
            start_show = 1
            end_show = total_lines
        else:
            # For larger files, use the requested context
            start_show = max(1, span.start_line - context_lines)
            end_show = min(total_lines, span.end_line + context_lines)

            # Ensure we show at least one line of context if possible
            if start_show == span.start_line and start_show > 1:
                start_show = max(1, start_show - 1)
            if end_show == span.end_line and end_show < total_lines:
                end_show = min(total_lines, end_show + 1)

        context_text = Text()

        for line_num in range(start_show, end_show + 1):
            line_content = (
                source_lines[line_num - 1] if line_num <= len(source_lines) else ""
            )
            line_num_str = f"{line_num:4d}"
            separator = " ┃ "

            # Enhanced styling: blue for line numbers and separators
            if span.start_line <= line_num <= span.end_line:
                # Error line - use brighter colors
                context_text.append(line_num_str, style="blue bold")
                context_text.append(separator, style="blue bold")
            else:
                # Context line - use dimmer colors
                context_text.append(line_num_str, style="blue dim")
                context_text.append(separator, style="blue dim")

            # Determine line styling
            if span.start_line <= line_num <= span.end_line:
                # This line contains the error
                if line_num == span.start_line == span.end_line:
                    # Single line error - highlight the exact span
                    # Columns are 1-based, so subtract 1 for 0-based indexing
                    before = line_content[: span.start_column - 1]
                    error_part = line_content[span.start_column - 1 : span.end_column - 1]
                    after = line_content[span.end_column - 1 :]

                    # White/default color for code
                    context_text.append(before, style="white")
                    context_text.append(error_part, style="black on red")
                    context_text.append(after, style="white")
                else:
                    # Multi-line error
                    if line_num == span.start_line:
                        # Columns are 1-based, so subtract 1 for 0-based indexing
                        before = line_content[: span.start_column - 1]
                        error_part = line_content[span.start_column - 1 :]
                        context_text.append(before, style="white")
                        context_text.append(error_part, style="black on red")
                    elif line_num == span.end_line:
                        # Columns are 1-based, so subtract 1 for 0-based indexing
                        error_part = line_content[: span.end_column - 1]
                        after = line_content[span.end_column - 1 :]
                        context_text.append(error_part, style="black on red")
                        context_text.append(after, style="white")
                    else:
                        context_text.append(line_content, style="black on red")

                context_text.append("\n")

                # Add underline pointer line for single-line errors
                if line_num == span.start_line == span.end_line:
                    pointer_prefix = " " * 4 + " ┃ "
                    # Column is 1-based, so subtract 1 for 0-based spacing
                    pointer_spaces = " " * (span.start_column - 1)
                    # Use a mix of characters dynamically sized to the error
                    if span.length > 1:
                        # Create underline that matches the exact error span length, pointing up
                        underline = "└" + "─" * max(0, span.length - 2) + "┘"
                    else:
                        underline = "▲"

                    context_text.append(pointer_prefix, style="blue dim")
                    context_text.append(pointer_spaces, style="white")
                    context_text.append(underline, style="red bold")
                    context_text.append("\n")
            else:
                # Context line - not part of error - white/default color for code
                context_text.append(line_content, style="white")
                context_text.append("\n")

        return context_text


class CompilerError(Exception):
    """Base class for all compiler errors with rich formatting support."""

    def __init__(
        self,
        message: str,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
    ):
        self.message = message
        self.span = span
        self.filename = filename
        self.source_lines = source_lines or []
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with location information."""
        parts = []

        if self.filename:
            parts.append(f"{Path(self.filename).name}")

        if self.span:
            if self.span.start_line == self.span.end_line:
                parts.append(f"{self.span.start_line}:{self.span.start_column}")
            else:
                parts.append(
                    f"{self.span.start_line}:{self.span.start_column}-{self.span.end_line}:{self.span.end_column}"
                )

        if parts:
            return f"{':'.join(parts)}: {self.message}"
        else:
            return self.message

    def display(
        self, console: Optional[Console] = None, context_lines: int = 2
    ) -> None:
        """Display this error with rich formatting and source context."""
        formatter = ErrorFormatter(console)
        formatter.format_error(self, context_lines)

    @classmethod
    def from_token(
        cls,
        message: str,
        token,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
    ):
        """Create an error from a token's location information."""
        span = SourceSpan(
            start_line=token.line,
            start_column=token.column,
            end_line=token.line,
            end_column=token.column + token.length,
            length=token.length,
        )
        return cls(message, span, filename, source_lines)

    @classmethod
    def from_location(
        cls,
        message: str,
        line: int,
        column: int,
        length: int = 1,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
    ):
        """Create an error from explicit location information."""
        span = SourceSpan(
            start_line=line,
            start_column=column,
            end_line=line,
            end_column=column + length,
            length=length,
        )
        return cls(message, span, filename, source_lines)


class TokenizerError(CompilerError):
    """Error during tokenization (lexical analysis)."""

    def __init__(
        self,
        message: str,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        error_type: Optional[TokenizerErrorType] = None,
    ):
        self.error_type = error_type
        super().__init__(message, span, filename, source_lines)

    @classmethod
    def from_type(
        cls,
        error_type: TokenizerErrorType,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
    ):
        """Create a TokenizerError from an error type."""
        message = custom_message or get_tokenizer_error_message(error_type)
        return cls(message, span, filename, source_lines, error_type)

    @classmethod
    def from_type_and_location(
        cls,
        error_type: TokenizerErrorType,
        line: int,
        column: int,
        length: int = 1,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
    ):
        """Create a TokenizerError from error type and location information."""
        span = SourceSpan(
            start_line=line,
            start_column=column,
            end_line=line,
            end_column=column + length,
            length=length,
        )
        message = custom_message or get_tokenizer_error_message(error_type)
        return cls(message, span, filename, source_lines, error_type)


class ParseError(CompilerError):
    """Error during parsing."""

    pass


class SemanticError(CompilerError):
    """Error during semantic analysis (name resolution, scoping, validation)."""

    def __init__(
        self,
        message: str,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        error_type: Optional[SemanticErrorType] = None,
    ):
        self.error_type = error_type
        super().__init__(message, span, filename, source_lines)

    @classmethod
    def from_type(
        cls,
        error_type: SemanticErrorType,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
        context: Optional[str] = None,
    ):
        """Create a SemanticError from an error type."""
        message = custom_message or get_semantic_error_message(error_type)
        if context:
            message = f"{message}: {context}"
        return cls(message, span, filename, source_lines, error_type)


class TypeCheckError(CompilerError):
    """Error during type checking."""

    def __init__(
        self,
        message: str,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        error_type: Optional[TypeErrorType] = None,
        expected_type: Optional[str] = None,
        got_type: Optional[str] = None,
    ):
        self.error_type = error_type
        self.expected_type = expected_type
        self.got_type = got_type
        super().__init__(message, span, filename, source_lines)

    @classmethod
    def from_type(
        cls,
        error_type: TypeErrorType,
        span: Optional[SourceSpan] = None,
        filename: Optional[str] = None,
        source_lines: Optional[List[str]] = None,
        custom_message: Optional[str] = None,
        context: Optional[str] = None,
        expected_type: Optional[str] = None,
        got_type: Optional[str] = None,
    ):
        """Create a TypeCheckError from an error type."""
        message = custom_message or get_type_error_message(error_type)

        # Add type information to message if available
        if expected_type and got_type:
            message = f"{message}: expected '{expected_type}', got '{got_type}'"
        elif got_type:
            message = f"{message}: got '{got_type}'"
        elif expected_type:
            message = f"{message}: expected '{expected_type}'"

        if context:
            message = f"{message} ({context})"

        return cls(message, span, filename, source_lines, error_type, expected_type, got_type)


class CodegenError(CompilerError):
    """Error during code generation."""

    pass


class ImportError(CompilerError):
    """Error resolving imports."""

    pass


# Utility functions for error handling
def create_error_handler(
    filename: Optional[str] = None, source_code: Optional[str] = None
):
    """Create a convenient error handler for a specific file."""
    source_lines = source_code.splitlines() if source_code else []

    class ErrorHandler:
        def __init__(self):
            self.filename = filename
            self.source_lines = source_lines

        def tokenizer_error(
            self, message: str, line: int, column: int, length: int = 1
        ) -> TokenizerError:
            """Create a TokenizerError with current file context."""
            return TokenizerError.from_location(
                message, line, column, length, self.filename, self.source_lines
            )

        def parse_error(
            self, message: str, token=None, span: Optional[SourceSpan] = None
        ) -> ParseError:
            """Create a ParseError with current file context."""
            if token:
                return ParseError.from_token(
                    message, token, self.filename, self.source_lines
                )
            elif span:
                return ParseError(message, span, self.filename, self.source_lines)
            else:
                return ParseError(message, None, self.filename, self.source_lines)

        def semantic_error(
            self, message: str, token=None, span: Optional[SourceSpan] = None
        ) -> SemanticError:
            """Create a SemanticError with current file context."""
            if token:
                return SemanticError.from_token(
                    message, token, self.filename, self.source_lines
                )
            elif span:
                return SemanticError(message, span, self.filename, self.source_lines)
            else:
                return SemanticError(message, None, self.filename, self.source_lines)

        def codegen_error(
            self, message: str, token=None, span: Optional[SourceSpan] = None
        ) -> CodegenError:
            """Create a CodegenError with current file context."""
            if token:
                return CodegenError.from_token(
                    message, token, self.filename, self.source_lines
                )
            elif span:
                return CodegenError(message, span, self.filename, self.source_lines)
            else:
                return CodegenError(message, None, self.filename, self.source_lines)

    return ErrorHandler()


def display_error(
    error: CompilerError, console: Optional[Console] = None, context_lines: int = 2
):
    """Convenience function to display any compiler error with rich formatting."""
    error.display(console, context_lines)


def display_errors(
    errors: List[CompilerError], console: Optional[Console] = None, context_lines: int = 2
):
    """Display multiple errors with rich formatting."""
    if not errors:
        return

    console = console or Console()

    # Display header
    error_count = len(errors)
    error_word = "error" if error_count == 1 else "errors"
    console.print(f"\n[bold red]Found {error_count} {error_word}:[/bold red]\n")

    # Display each error
    for i, error in enumerate(errors, 1):
        # Add separator between errors (but not before the first one)
        if i > 1:
            separator = Rule(style="dim black")
            console.print(separator)
            console.print()  # Extra blank line

        console.print(f"[bold white]Error {i}/{error_count}:[/bold white]")
        error.display(console, context_lines)


def create_span_between_tokens(start_token, end_token) -> SourceSpan:
    """Create a SourceSpan that covers from start_token to end_token."""
    return SourceSpan(
        start_line=start_token.line,
        start_column=start_token.column,
        end_line=end_token.line,
        end_column=end_token.column + end_token.length,
    )


def create_span_from_tokens(tokens: List) -> SourceSpan:
    """Create a SourceSpan that covers all the given tokens."""
    if not tokens:
        raise ValueError("Cannot create span from empty token list")

    first_token = tokens[0]
    last_token = tokens[-1]

    return create_span_between_tokens(first_token, last_token)
