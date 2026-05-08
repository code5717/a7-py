"""
A7 Compiler Backend System

Provides pluggable code generation backends for different target languages.
"""

from .base import CodeGenerator
from .zig import ZigCodeGenerator

# Registry of available backends
BACKENDS = {
    "zig": ZigCodeGenerator,
}


def get_backend(name: str) -> CodeGenerator:
    """Get a code generator instance for the specified backend."""
    if name not in BACKENDS:
        available = ", ".join(BACKENDS.keys())
        raise ValueError(f"Unknown backend '{name}'. Available backends: {available}")

    return BACKENDS[name]()


def list_backends():
    """Return a list of available backend names."""
    return list(BACKENDS.keys())


__all__ = ["CodeGenerator", "get_backend", "list_backends"]
