"""
A7 Standard Library Registry.

Maps A7 stdlib modules/functions to canonical names. Each backend lowers a
canonical name itself.
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
    """A standard library function and its canonical name."""
    module: str              # "io"
    name: str                # "println"
    canonical: str           # "std.io.println"
    signature: Optional[str] = None
    argument_policy: str = "fixed"


@dataclass
class StdlibModule:
    """A standard library module containing functions."""
    name: str
    functions: Dict[str, StdlibFunction] = field(default_factory=dict)


class StdlibRegistry:
    """Registry of all A7 standard library modules and functions."""

    def __init__(self):
        self.modules: Dict[str, StdlibModule] = {}

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

    def resolve_call(self, module_name: str, method_name: str) -> Optional[str]:
        """Resolve a module.method call to its canonical name."""
        module_name = self.canonical_module_name(module_name) or module_name
        module = self.modules.get(module_name)
        if module:
            func = module.functions.get(method_name)
            if func:
                return func.canonical
        return None


__all__ = ["StdlibRegistry", "StdlibFunction", "StdlibModule", "STDLIB_MODULE_ALIASES"]
