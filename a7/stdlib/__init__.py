"""
A7 Standard Library Registry.

Maps A7 stdlib modules/functions to canonical names and backend-specific implementations.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Set


STDLIB_MODULE_ALIASES: Dict[str, str] = {
    "io": "io",
    "std/io": "io",
    "math": "math",
    "std/math": "math",
}


@dataclass
class StdlibFunction:
    """A standard library function with backend mappings."""
    module: str              # "io"
    name: str                # "println"
    canonical: str           # "std.io.println"
    backend_map: Dict[str, str] = field(default_factory=dict)


@dataclass
class StdlibModule:
    """A standard library module containing functions."""
    name: str
    functions: Dict[str, StdlibFunction] = field(default_factory=dict)


class StdlibRegistry:
    """Registry of all A7 standard library modules and functions."""

    def __init__(self):
        self.modules: Dict[str, StdlibModule] = {}
        self._builtin_map: Dict[str, StdlibFunction] = {}  # bare name -> function

        # Auto-register built-in modules
        self._register_defaults()

    def _register_defaults(self):
        """Register default stdlib modules."""
        from .io import register_io_module
        from .math import register_math_module
        register_io_module(self)
        register_math_module(self)

    def register_module(self, module: StdlibModule):
        """Register a stdlib module."""
        self.modules[module.name] = module

    def canonical_module_name(self, module_name: str) -> Optional[str]:
        """Return the registry module name for a public stdlib import path."""
        return STDLIB_MODULE_ALIASES.get(module_name)

    def public_module_paths(self) -> Set[str]:
        """Return all public import paths provided by the built-in stdlib."""
        return set(STDLIB_MODULE_ALIASES)

    def register_builtin(self, bare_name: str, func: StdlibFunction):
        """Register a bare builtin name (e.g., sqrt_f32) that maps to a stdlib function."""
        self._builtin_map[bare_name] = func

    def resolve_call(self, module_name: str, method_name: str) -> Optional[str]:
        """Resolve a module.method call to its canonical name."""
        module_name = self.canonical_module_name(module_name) or module_name
        module = self.modules.get(module_name)
        if module:
            func = module.functions.get(method_name)
            if func:
                return func.canonical
        return None

    def resolve_builtin(self, name: str) -> Optional[str]:
        """Resolve a bare builtin name to its canonical name."""
        func = self._builtin_map.get(name)
        if func:
            return func.canonical
        return None

    def get_backend_mapping(self, canonical: str, backend: str) -> Optional[str]:
        """Get the backend-specific code for a canonical stdlib function."""
        for module in self.modules.values():
            for func in module.functions.values():
                if func.canonical == canonical:
                    return func.backend_map.get(backend)
        # Also check builtins
        for func in self._builtin_map.values():
            if func.canonical == canonical:
                return func.backend_map.get(backend)
        return None

    def is_io_call(self, module_name: str, method_name: str) -> bool:
        """Check if a call is an I/O call (needs special statement-level handling)."""
        canonical = self.resolve_call(module_name, method_name)
        return canonical is not None and canonical.startswith("std.io.")


__all__ = ["StdlibRegistry", "StdlibFunction", "StdlibModule", "STDLIB_MODULE_ALIASES"]
