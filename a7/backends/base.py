"""
Base code generator interface for A7 compiler backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Set
from io import StringIO

from ..parser import ASTNode
from ..errors import CodegenError


class CodeGenerator(ABC):
    """Abstract base class for all code generators."""

    def __init__(self):
        self.output = StringIO()
        self.indent_level = 0
        self.imports = set()
        self.current_function = None

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
    def generate(self, ast: ASTNode) -> str:
        """Generate target code from the AST."""
        pass

    @abstractmethod
    def visit(self, node: ASTNode):
        """Visit an AST node and generate appropriate code."""
        pass

    def generic_visit(self, node: ASTNode):
        """Default visitor that visits all children."""
        for child in node.children:
            self.visit(child)

    def write(self, text: str):
        """Write text to the output buffer with automatic indentation."""
        if (
            text.startswith("\n")
            or self.output.tell() == 0
            or self.output.getvalue().endswith("\n")
        ):
            # Add indentation at the start of a new line
            if text != "\n" and not text.startswith("\n"):
                self.output.write("    " * self.indent_level)
        self.output.write(text)

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
        self.imports.clear()
        self.current_function = None
