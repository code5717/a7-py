"""
Base code generator interface for A7 compiler backends.
"""

from abc import ABC, abstractmethod
from io import StringIO
from typing import Dict, Optional

from ..parser import ASTNode


class CodeGenerator(ABC):
    """Abstract base class for all code generators."""

    def __init__(self):
        self.output = StringIO()
        self.indent_level = 0

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension for generated files (e.g., '.zig', '.c', '.cpp')."""
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable name of the target language."""
        pass

    @abstractmethod
    def generate(self, ast: ASTNode, type_map: Optional[Dict] = None,
                 symbol_table=None, backend_plan=None,
                 profile: str = "debug", no_nonwrap: bool = False) -> str:
        """Generate target code from the AST and the semantic results."""
        pass

    @abstractmethod
    def visit(self, node: ASTNode):
        """Visit an AST node and generate appropriate code."""
        pass

    def indent(self):
        """Increase indentation level."""
        self.indent_level += 1

    def dedent(self):
        """Decrease indentation level."""
        if self.indent_level > 0:
            self.indent_level -= 1

    def reset(self):
        """Reset the generator state for a new compilation."""
        self.output = StringIO()
        self.indent_level = 0
