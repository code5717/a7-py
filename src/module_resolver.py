"""
Module resolution system for A7.

Handles import statements, module loading, and dependency management.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import os

from src.ast_nodes import ASTNode, NodeKind
from src.symbol_table import Symbol, SymbolKind, SymbolTable, ModuleTable
from src.errors import SemanticError
from src.stdlib import StdlibRegistry
from src.types import UNKNOWN


@dataclass
class ModuleInfo:
    """Information about a loaded module."""
    path: str  # Module path (e.g., "io", "math/vector")
    file_path: str  # Actual file path
    ast: Optional[ASTNode] = None  # Parsed AST
    symbols: Optional[SymbolTable] = None  # Symbol table after analysis
    dependencies: List[str] = None  # List of imported module paths

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class ModuleResolver:
    """
    Resolves and loads A7 modules.

    Handles:
    1. Module path resolution (finding files)
    2. Module loading and parsing
    3. Dependency management
    4. Circular dependency detection
    5. Import statement processing
    """

    def __init__(self, search_paths: Optional[List[str]] = None):
        """
        Initialize module resolver.

        Args:
            search_paths: Directories to search for modules
        """
        self.search_paths = search_paths or ["."]
        self.loaded_modules: Dict[str, ModuleInfo] = {}
        self.module_table = ModuleTable()
        self.stdlib = StdlibRegistry()

        # Track currently loading modules for circular dependency detection
        self.loading_stack: List[str] = []

        # Built-in stdlib modules are virtual modules backed by StdlibRegistry
        # symbols and backend mappings rather than on-disk .a7 files.
        self.virtual_modules: Set[str] = self.stdlib.public_module_paths()

    def is_virtual_module(self, module_path: str) -> bool:
        """Return True when an import is provided by the built-in stdlib registry."""
        return module_path in self.virtual_modules

    def resolve_module_path(self, module_path: str) -> Optional[str]:
        """
        Resolve a module path to a file path.

        Args:
            module_path: Module path (e.g., "io", "math/vector")

        Returns:
            Absolute file path, or None if not found
        """
        # Try each search path
        for search_path in self.search_paths:
            # Convert module path to file path
            # "io" -> "io.a7"
            # "math/vector" -> "math/vector.a7"
            candidates = [
                Path(search_path) / f"{module_path}.a7",
                Path(search_path) / module_path / "mod.a7",  # Directory module
            ]

            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    return str(candidate.resolve())

        return None

    def load_module(self, module_path: str) -> Optional[ModuleInfo]:
        """
        Load a module and its dependencies.

        Args:
            module_path: Module path to load

        Returns:
            ModuleInfo if loaded successfully, None otherwise
        """
        # Check if already loaded
        if module_path in self.loaded_modules:
            return self.loaded_modules[module_path]

        if self.is_virtual_module(module_path):
            return self._load_virtual_module(module_path)

        # Check for circular dependency
        if module_path in self.loading_stack:
            cycle = " -> ".join(self.loading_stack + [module_path])
            raise SemanticError(
                f"Circular dependency detected: {cycle}"
            )

        # Resolve module path to file
        file_path = self.resolve_module_path(module_path)
        if not file_path:
            raise SemanticError(
                f"Module '{module_path}' not found in search paths: {self.search_paths}"
            )

        # Mark as loading
        self.loading_stack.append(module_path)

        try:
            # Read the source file
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # Tokenize and parse
            from src.tokens import Tokenizer
            from src.parser import Parser

            tokenizer = Tokenizer(source, file_path)
            tokens = tokenizer.tokenize()
            source_lines = source.splitlines()
            parser = Parser(tokens, file_path, source_lines)
            ast = parser.parse()

            # Run name resolution to build symbol table
            from src.passes.name_resolution import NameResolutionPass
            name_pass = NameResolutionPass()
            name_pass.analyze(ast, file_path)
            symbols = name_pass.symbols

            # Extract dependencies for this module
            deps = []
            for decl in (ast.declarations or []):
                if decl.kind == NodeKind.IMPORT:
                    dep_path = decl.module_path or ""
                    deps.append(dep_path)

            module_info = ModuleInfo(
                path=module_path,
                file_path=file_path,
                ast=ast,
                symbols=symbols,
                dependencies=deps,
            )

            # Register module in the module table
            self.module_table.register_module(module_path, symbols)

            # Cache the module
            self.loaded_modules[module_path] = module_info

            # Recursively load dependencies
            for dep_path in deps:
                self.load_module(dep_path)

            return module_info

        finally:
            # Remove from loading stack
            self.loading_stack.pop()

    def process_imports(self, program: ASTNode) -> List[str]:
        """
        Extract and process all import statements from a program.

        Args:
            program: Program AST node

        Returns:
            List of imported module paths
        """
        imports = []

        if program.kind != NodeKind.PROGRAM:
            return imports

        # Find all import declarations
        for decl in program.declarations or []:
            if decl.kind == NodeKind.IMPORT:
                module_path = decl.module_path or ""
                imports.append(module_path)

                # Process different import types
                if decl.alias:
                    # import "io" as console
                    self.module_table.add_alias(decl.alias, module_path)
                elif decl.is_using:
                    # using import "io"
                    self.module_table.add_using_import(module_path)
                elif decl.imported_items:
                    # import "vector" { Vec3, dot }
                    for item in decl.imported_items:
                        self.module_table.add_named_import(item, module_path)

        return imports

    def load_program_dependencies(self, program: ASTNode, current_path: str) -> List[ModuleInfo]:
        """
        Load all dependencies of a program.

        Args:
            program: Program AST node
            current_path: Current module path

        Returns:
            List of loaded module infos
        """
        # Extract imports
        import_paths = self.process_imports(program)

        # Load each imported module
        loaded = []
        for module_path in import_paths:
            try:
                module_info = self.load_module(module_path)
                if module_info:
                    loaded.append(module_info)
            except SemanticError as e:
                # Re-raise with better context
                raise SemanticError(
                    f"Error loading module '{module_path}' imported by '{current_path}': {str(e)}"
                )

        return loaded

    def get_module(self, module_path: str) -> Optional[ModuleInfo]:
        """Get a loaded module by path."""
        return self.loaded_modules.get(module_path)

    def is_loaded(self, module_path: str) -> bool:
        """Check if a module is loaded."""
        return module_path in self.loaded_modules

    def get_module_table(self) -> ModuleTable:
        """Get the module table."""
        return self.module_table

    def _load_virtual_module(self, module_path: str) -> ModuleInfo:
        """Load a built-in stdlib module into the same cache/table as file modules."""
        if module_path in self.loaded_modules:
            return self.loaded_modules[module_path]

        canonical_name = self.stdlib.canonical_module_name(module_path)
        if canonical_name is None:
            raise SemanticError(f"Unknown virtual stdlib module '{module_path}'")

        module = self.stdlib.modules.get(canonical_name)
        if module is None:
            raise SemanticError(f"Stdlib module '{module_path}' is not registered")

        symbols = SymbolTable()
        for func in module.functions.values():
            symbols.define(Symbol(
                name=func.name,
                kind=SymbolKind.FUNCTION,
                type=UNKNOWN,
                is_mutable=False,
            ))

        module_info = ModuleInfo(
            path=module_path,
            file_path=f"<stdlib:{module_path}>",
            ast=None,
            symbols=symbols,
            dependencies=[],
        )
        self.module_table.register_module(module_path, symbols)
        if canonical_name != module_path:
            self.module_table.register_module(canonical_name, symbols)
        self.loaded_modules[module_path] = module_info
        return module_info

    def topological_sort(self) -> List[str]:
        """
        Get modules in dependency order (topological sort).

        Returns:
            List of module paths in order such that dependencies come first
        """
        # Build dependency graph
        graph: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}

        for module_path, module_info in self.loaded_modules.items():
            graph[module_path] = module_info.dependencies
            in_degree[module_path] = 0

        # Calculate in-degrees
        for dependencies in graph.values():
            for dep in dependencies:
                if dep in in_degree:
                    in_degree[dep] += 1

        # Kahn's algorithm
        queue = [m for m, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            module = queue.pop(0)
            result.append(module)

            for dep in graph.get(module, []):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        # Check for cycles
        if len(result) != len(self.loaded_modules):
            raise SemanticError(
                "Circular dependency detected in module graph"
            )

        return result

    def clear(self) -> None:
        """Clear all loaded modules."""
        self.loaded_modules.clear()
        self.loading_stack.clear()

    def add_search_path(self, path: str) -> None:
        """Add a directory to the module search path."""
        if path not in self.search_paths:
            self.search_paths.append(path)

    def remove_search_path(self, path: str) -> None:
        """Remove a directory from the module search path."""
        if path in self.search_paths:
            self.search_paths.remove(path)

    def get_search_paths(self) -> List[str]:
        """Get the current module search paths."""
        return self.search_paths.copy()
