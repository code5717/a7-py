"""Import paths belong to their importing file; cache identity belongs to real files."""

import pytest

from a7.ast_nodes import ASTNode, NodeKind
from a7.errors import ImportError as A7ImportError, SemanticError
from a7.module_resolver import ModuleResolver


def write_module(root, relative, source="value :: 7\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_nested_import_uses_its_own_folder_and_allows_parent_inside_root(tmp_path):
    main = write_module(tmp_path, "main.a7", 'part :: import "sub/part"\nmain :: fn() {}\n')
    write_module(tmp_path, "sub/part.a7", 'local :: import "helper"\nshared :: import "../shared"\n')
    local = write_module(tmp_path, "sub/helper.a7", "local_value :: 2\n")
    shared = write_module(tmp_path, "shared.a7", "shared_value :: 3\n")
    write_module(tmp_path, "helper.a7", "wrong :: 99\n")
    resolver = ModuleResolver([str(tmp_path)])
    program = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.IMPORT, alias="part", module_path="sub/part"),
    ])
    loaded = resolver.load_program_dependencies(program, str(main))
    assert [module.path for module in loaded] == ["sub/part", "sub/helper", "shared"]
    importer = str(tmp_path / "sub/part.a7")
    assert resolver.get_module("helper", importer).file_path == str(local)
    assert resolver.get_module("../shared", importer).file_path == str(shared)
    assert resolver.get_module("helper") is None


def test_importer_relative_lookup_does_not_fall_back_to_entry_directory(tmp_path):
    write_module(tmp_path, "helper.a7")
    part = write_module(tmp_path, "sub/part.a7", 'h :: import "helper"\n')
    resolver = ModuleResolver([str(tmp_path)])
    with pytest.raises(A7ImportError, match="Module 'helper' not found") as caught:
        resolver.load_module("sub/part")
    assert caught.value.filename == str(part)


@pytest.mark.parametrize("spelling", ["../outside", "escape", "nested/../../outside"])
def test_parent_and_symlink_paths_cannot_escape_entry_root(tmp_path, spelling):
    root = tmp_path / "root"
    root.mkdir()
    (root / "nested").mkdir()
    outside = write_module(tmp_path, "outside.a7")
    (root / "escape.a7").symlink_to(outside)
    resolver = ModuleResolver([str(root), str(tmp_path)])
    assert resolver.resolve_module_path(spelling, str(root / "main.a7")) is None
    with pytest.raises(A7ImportError, match="not found"):
        resolver.load_module(spelling, str(root / "main.a7"))


def test_diamond_uses_one_real_file_across_relative_and_symlink_spellings(tmp_path):
    shared = write_module(tmp_path, "shared.a7")
    write_module(tmp_path, "left/part.a7", 'shared :: import "../shared"\n')
    write_module(tmp_path, "right/part.a7", 'shared :: import "alias"\n')
    (tmp_path / "right/alias.a7").symlink_to(shared)
    write_module(tmp_path, "root.a7", 'left :: import "left/part"\nright :: import "right/part"\n')
    resolver = ModuleResolver([str(tmp_path)])
    resolver.load_module("root")
    left = resolver.get_module("../shared", str(tmp_path / "left/part.a7"))
    right = resolver.get_module("alias", str(tmp_path / "right/part.a7"))
    assert left is right
    assert left.path == "shared"
    assert len(resolver.loaded_modules) == 4


def test_duplicate_imports_compare_real_files_in_importer_context(tmp_path):
    shared = write_module(tmp_path, "shared.a7")
    part = write_module(tmp_path, "sub/part.a7", 'a :: import "../shared"\nb :: import "alias"\n')
    (tmp_path / "sub/alias.a7").symlink_to(shared)
    resolver = ModuleResolver([str(tmp_path)])
    with pytest.raises(SemanticError, match="Duplicate import") as caught:
        resolver.load_module("sub/part")
    assert caught.value.filename == str(part)


def test_cycle_through_symlink_reports_import_origin_and_allows_retry(tmp_path):
    root = write_module(tmp_path, "root.a7", 'part :: import "sub/part"\n')
    part = write_module(tmp_path, "sub/part.a7", 'back :: import "back"\n')
    (tmp_path / "sub/back.a7").symlink_to(root)
    resolver = ModuleResolver([str(tmp_path)])
    with pytest.raises(SemanticError, match="root -> sub/part -> root") as caught:
        resolver.load_module("root")
    assert caught.value.filename == str(part)
    assert resolver.loaded_modules == {}
    assert resolver.loading_stack == []
    part.write_text("value :: 7\n")
    assert resolver.load_module("root").path == "root"


def test_directory_fallback_and_stdlib_names_keep_their_meaning(tmp_path):
    directory_module = write_module(tmp_path, "pkg/mod.a7")
    write_module(tmp_path, "io.a7", "local_only :: 9\n")
    resolver = ModuleResolver([str(tmp_path)])
    assert resolver.load_module("pkg").file_path == str(directory_module)
    io = resolver.load_module("io")
    assert io.ast is None
    assert resolver.load_module("std/io") is io
    assert resolver.get_module_table().resolve_qualified_name("std/io", "println") is not None
    assert set(resolver.topological_sort()) == {"pkg/mod", "io"}


def test_entry_path_sets_containment_root_and_alias_uses_canonical_identity(tmp_path):
    root = tmp_path / "project"
    main = write_module(root, "main.a7", "main :: fn() {}\n")
    write_module(root, "helper.a7")
    resolver = ModuleResolver([str(tmp_path)])
    program = ASTNode(kind=NodeKind.PROGRAM, declarations=[
        ASTNode(kind=NodeKind.IMPORT, alias="h", module_path="./helper"),
    ])
    resolver.load_program_dependencies(program, str(main))
    assert resolver.entry_root == root
    assert resolver.get_module("helper").file_path == str(root / "helper.a7")
    assert resolver.get_module_table().resolve_qualified_name("h", "value") is not None
    write_module(tmp_path, "outside.a7")
    assert resolver.resolve_module_path("../outside", str(main)) is None


def test_stdlib_cache_identity_cannot_collide_with_a_file_name(tmp_path):
    local = write_module(tmp_path, "virtual:io.a7", "local_only :: 9\n")
    resolver = ModuleResolver([str(tmp_path)])
    io = resolver.load_module("io")
    file_module = resolver.load_module("virtual:io")
    assert file_module.file_path == str(local)
    assert file_module is not io
    assert resolver.get_module("io") is io
