"""
Symbol table for A7 semantic analysis.

Manages scopes, symbol definitions, and name resolution.
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from enum import Enum, auto

from a7.types import Type
from a7.ast_nodes import ASTNode


class SymbolKind(Enum):
    """Categories of symbols."""
    VARIABLE = auto()
    CONSTANT = auto()
    FUNCTION = auto()
    TYPE = auto()
    STRUCT = auto()
    ENUM = auto()
    UNION = auto()
    ENUM_VARIANT = auto()
    GENERIC_PARAM = auto()
    MODULE = auto()


@dataclass
class Symbol:
    """
    Represents a named entity in the symbol table.

    Attributes:
        name: Symbol identifier
        kind: What kind of symbol this is
        type: The type of this symbol
        node: AST node where this was declared
        is_mutable: Whether this can be reassigned (for variables)
        is_used: Track if symbol has been referenced (for unused warnings)
    """
    name: str
    kind: SymbolKind
    type: Type
    node: Optional[ASTNode] = None
    is_mutable: bool = False
    is_used: bool = False

    def __str__(self) -> str:
        mutability = "mut" if self.is_mutable else "const"
        return f"Symbol({self.name}: {self.type} [{self.kind.name}, {mutability}])"


class Scope:
    """
    Represents a lexical scope in the program.

    Scopes are nested - each scope has a parent (except the global scope).
    """

    def __init__(self, name: str, parent: Optional['Scope'] = None):
        """
        Initialize a new scope.

        Args:
            name: Human-readable scope name (for debugging)
            parent: Parent scope (None for global scope)
        """
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []

        if parent:
            parent.children.append(self)

    def define(self, symbol: Symbol) -> bool:
        """
        Define a new symbol in this scope.

        Args:
            symbol: Symbol to define

        Returns:
            True if symbol was added, False if name already exists in this scope
        """
        if symbol.name in self.symbols:
            return False

        self.symbols[symbol.name] = symbol
        return True

    def lookup_local(self, name: str) -> Optional[Symbol]:
        """
        Look up a symbol in this scope only (not parent scopes).

        Args:
            name: Symbol name to find

        Returns:
            Symbol if found in this scope, None otherwise
        """
        return self.symbols.get(name)

    def lookup(self, name: str) -> Optional[Symbol]:
        """
        Look up a symbol in this scope or any parent scope.

        Args:
            name: Symbol name to find

        Returns:
            Symbol if found, None otherwise
        """
        # Try this scope first
        symbol = self.symbols.get(name)
        if symbol:
            return symbol

        # Try parent scopes
        if self.parent:
            return self.parent.lookup(name)

        return None

    def update_symbol(self, name: str, symbol: Symbol) -> bool:
        """
        Update an existing symbol in this scope.

        Args:
            name: Symbol name
            symbol: New symbol data

        Returns:
            True if updated, False if symbol doesn't exist
        """
        if name not in self.symbols:
            return False

        self.symbols[name] = symbol
        return True

    def get_all_symbols(self) -> Dict[str, Symbol]:
        """Get all symbols defined in this scope."""
        return self.symbols.copy()

    def __repr__(self) -> str:
        symbol_count = len(self.symbols)
        parent_name = self.parent.name if self.parent else "None"
        return f"Scope(name='{self.name}', parent='{parent_name}', symbols={symbol_count})"


class SymbolTable:
    """
    Manages hierarchical scopes and symbol resolution.

    The symbol table maintains a stack of scopes and provides
    operations for entering/exiting scopes and defining/looking up symbols.
    """

    def __init__(self):
        """Initialize with a global scope."""
        self.global_scope = Scope("global")
        self.current_scope = self.global_scope
        self.scope_stack: List[Scope] = [self.global_scope]

    def enter_scope(self, name: str, reuse_existing: bool = False) -> Scope:
        """
        Enter a nested scope.

        Args:
            name: Human-readable scope name
            reuse_existing: If True, try to enter an existing child scope with this name
                           instead of creating a new one.

        Returns:
            The scope entered (either new or existing)
        """
        if reuse_existing:
            # Try to find existing child scope with this name
            for child in self.current_scope.children:
                if child.name == name:
                    self.current_scope = child
                    self.scope_stack.append(child)
                    return child

        # Create a new scope
        new_scope = Scope(name, parent=self.current_scope)
        self.current_scope = new_scope
        self.scope_stack.append(new_scope)
        return new_scope

    def exit_scope(self) -> Optional[Scope]:
        """
        Exit the current scope and return to parent.

        Returns:
            The scope that was exited, or None if already at global scope
        """
        if len(self.scope_stack) <= 1:
            # Can't exit global scope
            return None

        exited_scope = self.scope_stack.pop()
        self.current_scope = self.scope_stack[-1]
        return exited_scope

    def define(self, symbol: Symbol) -> bool:
        """
        Define a symbol in the current scope.

        Args:
            symbol: Symbol to define

        Returns:
            True if defined successfully, False if name collision
        """
        return self.current_scope.define(symbol)

    def lookup(self, name: str) -> Optional[Symbol]:
        """
        Look up a symbol starting from current scope.

        Args:
            name: Symbol name to find

        Returns:
            Symbol if found in current or any parent scope, None otherwise
        """
        return self.current_scope.lookup(name)

    def lookup_type(self, name: str) -> Optional[Type]:
        """
        Look up a symbol and return its type.

        Args:
            name: Symbol name

        Returns:
            Type if symbol found, None otherwise
        """
        symbol = self.lookup(name)
        return symbol.type if symbol else None

    def lookup_in_scope(self, name: str, scope: Scope) -> Optional[Symbol]:
        """
        Look up a symbol in a specific scope.

        Args:
            name: Symbol name
            scope: Scope to search

        Returns:
            Symbol if found, None otherwise
        """
        return scope.lookup(name)

    def get_current_scope(self) -> Scope:
        """Get the current active scope."""
        return self.current_scope

    def get_global_scope(self) -> Scope:
        """Get the global scope."""
        return self.global_scope

    def is_global_scope(self) -> bool:
        """Check if we're currently in the global scope."""
        return self.current_scope == self.global_scope

    def get_scope_depth(self) -> int:
        """Get the current scope nesting depth (0 = global)."""
        return len(self.scope_stack) - 1

    def mark_used(self, name: str) -> bool:
        """
        Mark a symbol as used.

        Args:
            name: Symbol name

        Returns:
            True if symbol found and marked, False otherwise
        """
        symbol = self.lookup(name)
        if symbol:
            symbol.is_used = True
            return True
        return False

    def get_unused_symbols(self, scope: Optional[Scope] = None) -> List[Symbol]:
        """
        Get all unused symbols in a scope (for warnings).

        Args:
            scope: Scope to check (default: current scope)

        Returns:
            List of unused symbols
        """
        target_scope = scope if scope else self.current_scope
        return [s for s in target_scope.symbols.values() if not s.is_used]

    def dump(self, scope: Optional[Scope] = None, indent: int = 0) -> str:
        """
        Generate a debug dump of the symbol table.

        Args:
            scope: Starting scope (default: global)
            indent: Indentation level

        Returns:
            String representation of symbol table
        """
        if scope is None:
            scope = self.global_scope

        lines = []
        prefix = "  " * indent

        lines.append(f"{prefix}{scope.name}:")
        for name, symbol in sorted(scope.symbols.items()):
            used = "✓" if symbol.is_used else "✗"
            lines.append(f"{prefix}  [{used}] {symbol}")

        for child in scope.children:
            lines.append(self.dump(child, indent + 1))

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"SymbolTable(depth={self.get_scope_depth()}, current={self.current_scope.name})"


class ModuleTable:
    """
    Manages imported modules and their symbols.

    Tracks module imports, aliases, and provides qualified name resolution.
    """

    def __init__(self):
        """Initialize empty module table."""
        self.modules: Dict[str, SymbolTable] = {}  # module_path -> symbol table
        self.aliases: Dict[str, str] = {}  # alias -> module_path
        self.using_imports: List[str] = []  # modules imported with 'using'
        self.named_imports: Dict[str, str] = {}  # imported_name -> module_path

    def register_module(self, path: str, symbol_table: SymbolTable) -> None:
        """
        Register a module's symbol table.

        Args:
            path: Module path (e.g., "io", "math/vector")
            symbol_table: The module's symbol table
        """
        self.modules[path] = symbol_table

    def add_alias(self, alias: str, module_path: str) -> bool:
        """
        Add a module alias: import "io" as console

        Args:
            alias: Alias name
            module_path: Original module path

        Returns:
            True if added, False if alias already exists
        """
        if alias in self.aliases:
            return False

        self.aliases[alias] = module_path
        return True

    def add_using_import(self, module_path: str) -> None:
        """
        Add a using import: using import "io"

        Args:
            module_path: Module to import
        """
        if module_path not in self.using_imports:
            self.using_imports.append(module_path)

    def add_named_import(self, name: str, module_path: str) -> bool:
        """
        Add a named import: import "vector" { Vec3, dot }

        Args:
            name: Imported symbol name
            module_path: Source module

        Returns:
            True if added, False if name already imported
        """
        if name in self.named_imports:
            return False

        self.named_imports[name] = module_path
        return True

    def resolve_qualified_name(self, qualifier: str, name: str) -> Optional[Symbol]:
        """
        Resolve a qualified name: io.println

        Args:
            qualifier: Module name or alias
            name: Symbol name

        Returns:
            Symbol if found, None otherwise
        """
        # Resolve alias if present
        module_path = self.aliases.get(qualifier, qualifier)

        # Get module's symbol table
        module_symbols = self.modules.get(module_path)
        if not module_symbols:
            return None

        # Look up symbol in module's global scope
        return module_symbols.get_global_scope().lookup_local(name)

    def resolve_using_import(self, name: str) -> Optional[Symbol]:
        """
        Resolve a name from using imports.

        Args:
            name: Symbol name

        Returns:
            Symbol if found in any using import, None otherwise
        """
        for module_path in self.using_imports:
            module_symbols = self.modules.get(module_path)
            if module_symbols:
                symbol = module_symbols.get_global_scope().lookup_local(name)
                if symbol:
                    return symbol

        return None

    def resolve_named_import(self, name: str) -> Optional[Symbol]:
        """
        Resolve a name from named imports.

        Args:
            name: Symbol name

        Returns:
            Symbol if found, None otherwise
        """
        module_path = self.named_imports.get(name)
        if not module_path:
            return None

        module_symbols = self.modules.get(module_path)
        if not module_symbols:
            return None

        return module_symbols.get_global_scope().lookup_local(name)

    def get_module(self, path: str) -> Optional[SymbolTable]:
        """Get a module's symbol table by path."""
        return self.modules.get(path)

    def __repr__(self) -> str:
        return f"ModuleTable(modules={len(self.modules)}, aliases={len(self.aliases)})"
