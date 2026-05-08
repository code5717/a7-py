"""
Semantic analysis context for A7.

Tracks state during semantic analysis including current function,
loop depth, defer statements, and generic instantiations.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
from enum import Enum, auto

from a7.types import Type, GenericParamType
from a7.ast_nodes import ASTNode


class ContextKind(Enum):
    """Types of semantic contexts."""
    GLOBAL = auto()
    FUNCTION = auto()
    LOOP = auto()
    BLOCK = auto()
    DEFER = auto()


@dataclass
class FunctionContext:
    """
    Context information for a function being analyzed.

    Tracks function signature, return type, and analysis state.
    """
    name: str
    return_type: Optional[Type]
    node: ASTNode
    generic_params: Dict[str, GenericParamType] = field(default_factory=dict)
    has_return: bool = False  # Track if all paths return
    defer_count: int = 0  # Number of defer statements


@dataclass
class LoopContext:
    """
    Context information for a loop being analyzed.

    Tracks loop depth and label (if any).
    """
    depth: int
    label: Optional[str] = None
    has_break: bool = False
    has_continue: bool = False


@dataclass
class DeferContext:
    """
    Context for a defer statement.

    Tracks the deferred expression and its scope.
    """
    expression: ASTNode
    scope_depth: int


class SemanticContext:
    """
    Maintains state during semantic analysis.

    Provides context-aware validation (e.g., break only in loops,
    return type matches function signature, defer scoping, etc.)
    """

    def __init__(self):
        """Initialize with empty context."""
        self.current_function: Optional[FunctionContext] = None
        self.loop_stack: List[LoopContext] = []
        self.defer_stack: List[DeferContext] = []
        self.generic_instantiations: Dict[str, Type] = {}
        self.errors: List[str] = []

    # Function context management

    def enter_function(self, name: str, return_type: Optional[Type], node: ASTNode) -> None:
        """
        Enter a function context.

        Args:
            name: Function name
            return_type: Expected return type (None for void)
            node: Function declaration AST node
        """
        self.current_function = FunctionContext(
            name=name,
            return_type=return_type,
            node=node
        )

    def exit_function(self) -> Optional[FunctionContext]:
        """
        Exit the current function context.

        Returns:
            The function context being exited, or None if not in a function
        """
        func = self.current_function
        self.current_function = None
        return func

    def in_function(self) -> bool:
        """Check if currently analyzing a function."""
        return self.current_function is not None

    def get_function_return_type(self) -> Optional[Type]:
        """
        Get the expected return type of current function.

        Returns:
            Return type, or None if not in a function or function is void
        """
        return self.current_function.return_type if self.current_function else None

    def mark_function_returns(self) -> None:
        """Mark that the current function has a return statement."""
        if self.current_function:
            self.current_function.has_return = True

    def function_has_return(self) -> bool:
        """Check if current function has a return statement."""
        return self.current_function.has_return if self.current_function else False

    # Generic context management

    def add_generic_param(self, name: str, param_type: GenericParamType) -> None:
        """
        Add a generic parameter to current function context.

        Args:
            name: Parameter name (without $)
            param_type: The generic parameter type
        """
        if self.current_function:
            self.current_function.generic_params[name] = param_type

    def get_generic_param(self, name: str) -> Optional[GenericParamType]:
        """
        Get a generic parameter from current function context.

        Args:
            name: Parameter name (without $)

        Returns:
            Generic parameter type if found, None otherwise
        """
        if self.current_function:
            return self.current_function.generic_params.get(name)
        return None

    def instantiate_generic(self, param_name: str, concrete_type: Type) -> None:
        """
        Record a generic type instantiation.

        Args:
            param_name: Generic parameter name
            concrete_type: Concrete type being instantiated
        """
        self.generic_instantiations[param_name] = concrete_type

    def get_instantiated_type(self, param_name: str) -> Optional[Type]:
        """
        Get the concrete type for a generic parameter.

        Args:
            param_name: Generic parameter name

        Returns:
            Concrete type if instantiated, None otherwise
        """
        return self.generic_instantiations.get(param_name)

    # Loop context management

    def enter_loop(self, label: Optional[str] = None) -> None:
        """
        Enter a loop context.

        Args:
            label: Optional loop label
        """
        depth = len(self.loop_stack)
        self.loop_stack.append(LoopContext(depth=depth, label=label))

    def exit_loop(self) -> Optional[LoopContext]:
        """
        Exit the current loop context.

        Returns:
            The loop context being exited, or None if not in a loop
        """
        return self.loop_stack.pop() if self.loop_stack else None

    def in_loop(self) -> bool:
        """Check if currently inside a loop."""
        return len(self.loop_stack) > 0

    def get_loop_depth(self) -> int:
        """Get current loop nesting depth."""
        return len(self.loop_stack)

    def mark_loop_has_break(self) -> None:
        """Mark that current loop has a break statement."""
        if self.loop_stack:
            self.loop_stack[-1].has_break = True

    def mark_loop_has_continue(self) -> None:
        """Mark that current loop has a continue statement."""
        if self.loop_stack:
            self.loop_stack[-1].has_continue = True

    def find_loop_by_label(self, label: str) -> Optional[LoopContext]:
        """
        Find a loop context by label.

        Args:
            label: Loop label to find

        Returns:
            Loop context if found, None otherwise
        """
        for loop_ctx in reversed(self.loop_stack):
            if loop_ctx.label == label:
                return loop_ctx
        return None

    # Defer context management

    def add_defer(self, expression: ASTNode, scope_depth: int) -> None:
        """
        Add a defer statement.

        Args:
            expression: Expression to defer
            scope_depth: Current scope depth
        """
        self.defer_stack.append(DeferContext(expression=expression, scope_depth=scope_depth))
        if self.current_function:
            self.current_function.defer_count += 1

    def get_defers_at_depth(self, scope_depth: int) -> List[DeferContext]:
        """
        Get all defer statements at a given scope depth.

        Args:
            scope_depth: Scope depth to check

        Returns:
            List of defer contexts at that depth
        """
        return [d for d in self.defer_stack if d.scope_depth == scope_depth]

    def pop_defers_at_depth(self, scope_depth: int) -> List[DeferContext]:
        """
        Pop all defer statements at a given scope depth (when exiting scope).

        Args:
            scope_depth: Scope depth being exited

        Returns:
            List of defer contexts that were popped
        """
        defers_at_depth = self.get_defers_at_depth(scope_depth)
        self.defer_stack = [d for d in self.defer_stack if d.scope_depth != scope_depth]
        return defers_at_depth

    def get_defer_count(self) -> int:
        """Get number of active defer statements."""
        return len(self.defer_stack)

    # Error tracking

    def add_error(self, message: str) -> None:
        """
        Add a semantic error.

        Args:
            message: Error message
        """
        self.errors.append(message)

    def has_errors(self) -> bool:
        """Check if any errors have been recorded."""
        return len(self.errors) > 0

    def get_errors(self) -> List[str]:
        """Get all recorded errors."""
        return self.errors.copy()

    def clear_errors(self) -> None:
        """Clear all recorded errors."""
        self.errors.clear()

    # Validation helpers

    def validate_break(self, label: Optional[str] = None) -> bool:
        """
        Validate that a break statement is allowed.

        Args:
            label: Optional target label

        Returns:
            True if break is valid, False otherwise
        """
        if not self.in_loop():
            self.add_error("'break' statement outside of loop")
            return False

        if label:
            if not self.find_loop_by_label(label):
                self.add_error(f"Loop label '{label}' not found")
                return False

        return True

    def validate_continue(self, label: Optional[str] = None) -> bool:
        """
        Validate that a continue statement is allowed.

        Args:
            label: Optional target label

        Returns:
            True if continue is valid, False otherwise
        """
        if not self.in_loop():
            self.add_error("'continue' statement outside of loop")
            return False

        if label:
            if not self.find_loop_by_label(label):
                self.add_error(f"Loop label '{label}' not found")
                return False

        return True

    def validate_return(self, return_type: Optional[Type]) -> bool:
        """
        Validate that a return statement is allowed and has correct type.

        Args:
            return_type: Type of the return expression (None for void)

        Returns:
            True if return is valid, False otherwise
        """
        if not self.in_function():
            self.add_error("'return' statement outside of function")
            return False

        expected = self.get_function_return_type()

        # Void function
        if expected is None:
            if return_type is not None:
                self.add_error(f"Cannot return value from void function")
                return False
            return True

        # Non-void function
        if return_type is None:
            self.add_error(f"Function expects return type '{expected}', got void")
            return False

        # Type must match
        if not return_type.is_assignable_to(expected):
            self.add_error(f"Return type mismatch: expected '{expected}', got '{return_type}'")
            return False

        return True

    # Debug helpers

    def dump(self) -> str:
        """Generate a debug dump of current context."""
        lines = []
        lines.append("=== Semantic Context ===")

        if self.current_function:
            lines.append(f"Function: {self.current_function.name}")
            lines.append(f"  Return type: {self.current_function.return_type}")
            lines.append(f"  Has return: {self.current_function.has_return}")
            lines.append(f"  Defer count: {self.current_function.defer_count}")
            if self.current_function.generic_params:
                lines.append(f"  Generic params: {list(self.current_function.generic_params.keys())}")

        lines.append(f"Loop depth: {self.get_loop_depth()}")
        for i, loop in enumerate(self.loop_stack):
            label_str = f" (label: {loop.label})" if loop.label else ""
            lines.append(f"  Loop {i}{label_str}")

        lines.append(f"Active defers: {len(self.defer_stack)}")
        lines.append(f"Errors: {len(self.errors)}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  - {err}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        func = self.current_function.name if self.current_function else "None"
        return f"SemanticContext(function={func}, loops={len(self.loop_stack)}, defers={len(self.defer_stack)})"
