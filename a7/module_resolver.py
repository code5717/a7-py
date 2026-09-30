"""
Module resolution system for A7.

Handles import statements, module loading, and dependency management.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from a7.ast_nodes import ASTNode, NodeKind
from a7.symbol_table import Symbol, SymbolKind, SymbolTable, ModuleTable
from a7.errors import CompilerError, SemanticError
from a7.stdlib import StdlibRegistry
from a7.types import UNKNOWN


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
        self.resolved_search_paths = [Path(path).resolve() for path in self.search_paths]
        self.loaded_modules: Dict[str, ModuleInfo] = {}
        self.module_table = ModuleTable()
        self.stdlib = StdlibRegistry()

        # Track currently loading modules for circular dependency detection
        self.loading_stack: List[str] = []

        # Built-in stdlib modules are virtual modules backed by StdlibRegistry
        # symbols and backend mappings rather than on-disk .a7 files.
        self.virtual_modules: Set[str] = self.stdlib.public_module_paths()

    def _is_safe_module_path(self, module_path: str) -> bool:
        # Reject null bytes (would crash Path.exists with ValueError),
        # backslashes (cross-platform path-traversal vector), and any
        # absolute or parent-relative segments. Empty or whitespace-only
        # paths are also rejected.
        if not module_path or not module_path.strip():
            return False
        if "\x00" in module_path or "\\" in module_path:
            return False
        path = Path(module_path)
        return not path.is_absolute() and ".." not in path.parts

    def _is_within_search_path(self, candidate: Path) -> bool:
        resolved = candidate.resolve()
        return any(resolved.is_relative_to(search_path) for search_path in self.resolved_search_paths)

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
        if not self._is_safe_module_path(module_path):
            return None

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
                if candidate.exists() and candidate.is_file() and self._is_within_search_path(candidate):
                    return str(candidate.resolve())

        return None

    def load_module(self, module_path: str) -> Optional[ModuleInfo]:
        """Load dependencies in source order without using the Python call stack."""
        initial_depth = len(self.loading_stack)
        active = set(self.loading_stack)
        # An exit event completes a cached module after all its imports finish.
        # Enter events carry the importing declaration for unlocated errors.
        pending = [(False, module_path, None)]
        try:
            while pending:
                exiting, path, origin = pending.pop()
                if exiting:
                    active.remove(self.loading_stack.pop())
                    continue
                try:
                    # Check active modules before the cache so cycles cannot
                    # masquerade as already completed imports.
                    if path in active:
                        cycle = " -> ".join(self.loading_stack + [path])
                        raise SemanticError(f"Circular dependency detected: {cycle}")
                    if path in self.loaded_modules:
                        continue
                    if self.is_virtual_module(path):
                        self._load_virtual_module(path)
                        continue
                    file_path = self.resolve_module_path(path)
                    if not file_path:
                        raise SemanticError(
                            f"Module '{path}' not found in search paths: {self.search_paths}"
                        )
                    self.loading_stack.append(path)
                    active.add(path)
                    module_info, imports, source_lines = self._read_module(path, file_path)
                    self.module_table.register_module(path, module_info.symbols)
                    self.loaded_modules[path] = module_info
                    pending.append((True, path, None))
                    for declaration in reversed(imports):
                        pending.append((False, declaration.module_path or "",
                                        (declaration, file_path, source_lines)))
                except CompilerError as error:
                    if error.span is not None or origin is None:
                        raise
                    declaration, filename, lines = origin
                    raise SemanticError(
                        error.message, span=declaration.span, filename=filename,
                        source_lines=lines,
                    ) from error
            return self.loaded_modules[module_path]
        except BaseException:
            # A partially loaded module must not become a successful cache hit
            # on retry. Completed dependencies retain their existing identities.
            for path in self.loading_stack[initial_depth:]:
                self.loaded_modules.pop(path, None)
                self.module_table.modules.pop(path, None)
            raise
        finally:
            del self.loading_stack[initial_depth:]

    def _read_module(
        self, module_path: str, file_path: str,
    ) -> tuple[ModuleInfo, List[ASTNode], List[str]]:
        """Parse one file and collect its imports without loading dependencies."""
        from a7.tokens import Tokenizer
        from a7.parser import Parser
        from a7.passes.name_resolution import NameResolutionPass

        with open(file_path, "r", encoding="utf-8") as source_file:
            source = source_file.read()
        tokens = Tokenizer(source, file_path).tokenize()
        source_lines = source.splitlines()
        ast = Parser(tokens, file_path, source_lines).parse()
        self._attach_source_context(ast, file_path, source_lines)
        name_pass = NameResolutionPass()
        name_pass.analyze(ast, file_path)
        imports = [decl for decl in ast.declarations or [] if decl.kind == NodeKind.IMPORT]
        module_info = ModuleInfo(
            path=module_path,
            file_path=file_path,
            ast=ast,
            symbols=name_pass.symbols,
            dependencies=[decl.module_path or "" for decl in imports],
        )
        return module_info, imports, source_lines

    @staticmethod
    def _attach_source_context(root: ASTNode, filename: str, lines: List[str]) -> None:
        """Keep module origins when declarations enter the combined program."""
        stack = [root]
        seen = set()
        while stack:
            node = stack.pop()
            if id(node) in seen:
                continue
            seen.add(id(node))
            if node.span is not None:
                node.span.origin_file = filename
                node.span.origin_lines = lines
            for value in node.__dict__.values():
                if isinstance(value, ASTNode):
                    stack.append(value)
                elif isinstance(value, (list, tuple)):
                    stack.extend(child for child in value if isinstance(child, ASTNode))

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

        import_declarations = {
            decl.module_path or "": decl for decl in program.declarations or []
            if decl.kind == NodeKind.IMPORT
        }
        # Load each imported module and, transitively, every module they
        # import. FIFO order keeps the combined-program merge deterministic:
        # direct imports first, then their dependencies.
        loaded = []
        seen: Set[str] = set()
        queue = list(import_paths)
        while queue:
            module_path = queue.pop(0)
            if module_path in seen:
                continue
            seen.add(module_path)
            try:
                module_info = self.load_module(module_path)
            except CompilerError as error:
                if error.span is not None:
                    raise
                declaration = import_declarations.get(module_path)
                if declaration is not None:
                    raise SemanticError(
                        f"Error loading module '{module_path}': {error.message}",
                        span=declaration.span, filename=current_path,
                    ) from error
                raise
            if module_info:
                loaded.append(module_info)
                for transitive in module_info.dependencies:
                    if transitive not in seen:
                        queue.append(transitive)

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
