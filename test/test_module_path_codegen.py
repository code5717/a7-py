"""Imported call names follow the resolved file, including nested relative paths."""

from conftest import expect_exit, run_all_profiles


def test_parent_relative_import_builds_one_native_program(tmp_path, zig):
    (tmp_path / "sub").mkdir()
    (tmp_path / "shared.a7").write_text("shared_value :: fn() i32 { ret 7 }\n")
    (tmp_path / "sub/helper.a7").write_text(
        's :: import "../shared"\nhelper_value :: fn() i32 { ret s.shared_value() }\n'
    )
    source = '''h :: import "sub/helper"
io :: import "std/io"
main :: fn() { io.println("{}", h.helper_value()) }
'''
    assert run_all_profiles(source, tmp_path, zig) == "7\n"


def test_alias_spellings_share_one_emitted_module(tmp_path, zig):
    (tmp_path / "sub").mkdir()
    (tmp_path / "shared.a7").write_text("shared_value :: fn() i32 { ret 7 }\n")
    (tmp_path / "sub/helper.a7").write_text(
        's :: import "../shared"\nhelper_value :: fn() i32 { ret s.shared_value() + 1 }\n'
    )
    source = '''h :: import "sub/helper"
s :: import "./shared"
io :: import "std/io"
main :: fn() { io.println("{} {}", h.helper_value(), s.shared_value()) }
'''
    assert run_all_profiles(source, tmp_path, zig) == "8 7\n"


def test_parent_relative_import_cannot_leave_entry_directory(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (tmp_path / "outside.a7").write_text("outside_value :: fn() i32 { ret 7 }\n")
    expect_exit(
        'outside :: import "../outside"\nmain :: fn() {}\n',
        root, 3, "not found",
    )
