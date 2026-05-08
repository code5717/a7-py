"""Regression tests for A7 module resolution."""

from pathlib import Path

from a7.ast_nodes import ASTNode, NodeKind
from a7.module_resolver import ModuleResolver


def test_virtual_stdlib_module_registers_symbols() -> None:
    resolver = ModuleResolver()

    module_info = resolver.load_module("std/io")

    assert module_info is not None
    assert module_info.file_path == "<stdlib:std/io>"
    assert resolver.is_loaded("std/io")
    assert resolver.get_module_table().resolve_qualified_name("std/io", "println") is not None


def test_virtual_stdlib_alias_resolves_like_file_module_alias() -> None:
    program = ASTNode(
        kind=NodeKind.PROGRAM,
        declarations=[
            ASTNode(kind=NodeKind.IMPORT, alias="console", module_path="std/io"),
        ],
    )
    resolver = ModuleResolver()

    loaded = resolver.load_program_dependencies(program, "main.a7")

    assert [module.path for module in loaded] == ["std/io"]
    symbol = resolver.get_module_table().resolve_qualified_name("console", "println")
    assert symbol is not None
    assert symbol.name == "println"


def test_module_resolver_rejects_path_traversal(tmp_path: Path) -> None:
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    outside = tmp_path / "outside.a7"
    outside.write_text("main :: fn() {}\n", encoding="utf-8")
    resolver = ModuleResolver(search_paths=[str(safe_root)])

    assert resolver.resolve_module_path("../outside") is None
    assert resolver.resolve_module_path(str(outside.with_suffix(""))) is None
