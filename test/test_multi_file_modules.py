"""Multi-file module repairs: sibling calls, alias-call checking, transitive
imports, and struct generic constraints.

Every runnable case compiles through the real CLI, builds the emitted Zig in
Debug and ReleaseFast, and checks hand-derived output. Rejection cases pin
the CLI exit code and the diagnostic.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_zig_backend_runtime import build, compile_with_cli, run_piped, zig, zig_cache


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("Debug", "ReleaseFast")


def write_module(tmp_path, name, source):
    (tmp_path / f"{name}.a7").write_text(source, encoding="utf-8")


def cli_check(tmp_path, name):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), str(tmp_path / f"{name}.a7"),
         "--mode", "compile", "--output", str(tmp_path / f"{name}.zig")],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )


HELPER = '''
helper :: fn() i32 {
    ret 40
}

pub value :: fn() i32 {
    ret helper() + 2
}

pub identity($T) :: fn(v: $T) $T {
    ret v
}
'''


def test_sibling_call_in_imported_module_builds(tmp_path, zig, zig_cache):
    write_module(tmp_path, "helper", HELPER)
    output = compile_with_cli(tmp_path, '''
h :: import "helper"
io :: import "std/io"

main :: fn() {
    io.println("{}", h.value())
}
''')
    emitted = output.read_text(encoding="utf-8")
    # The declaration and the sibling call inside the module share the
    # module prefix; a bare `helper()` would not build.
    assert "module_helper__helper" in emitted
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "42\n"


def test_generic_call_through_alias_keeps_comptime_argument(tmp_path, zig, zig_cache):
    write_module(tmp_path, "helper", HELPER)
    output = compile_with_cli(tmp_path, '''
h :: import "helper"
io :: import "std/io"

main :: fn() {
    io.println("{}", h.identity(7))
}
''')
    emitted = output.read_text(encoding="utf-8")
    assert "module_helper__identity(i32, 7)" in emitted
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "7\n"


def test_missing_callee_in_imported_module_is_rejected(tmp_path):
    write_module(tmp_path, "helper", HELPER)
    (tmp_path / "main.a7").write_text(
        'h :: import "helper"\nio :: import "std/io"\n\n'
        'main :: fn() {\n    io.println("{}", h.answer())\n}\n',
        encoding="utf-8",
    )
    process = cli_check(tmp_path, "main")
    assert process.returncode == 6, process.stdout + process.stderr
    combined = " ".join((process.stdout + process.stderr).split())
    assert "Cannot call 'h.answer'" in combined
    assert "not defined in the imported module" in combined


def test_transitive_import_chain_builds(tmp_path, zig, zig_cache):
    write_module(tmp_path, "leaf", 'pub leaf_value :: fn() i32 {\n    ret 7\n}\n')
    write_module(tmp_path, "mid", '''
l :: import "leaf"

pub mid_value :: fn() i32 {
    ret l.leaf_value() * 6
}
''')
    output = compile_with_cli(tmp_path, '''
m :: import "mid"
io :: import "std/io"

main :: fn() {
    io.println("{}", m.mid_value())
}
''')
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "42\n"


def test_struct_constraint_violation_is_rejected(tmp_path):
    # Module-qualified struct literals (b.Box(...)) do not parse yet, so the
    # constraint check is pinned with a local struct instantiation.
    (tmp_path / "main.a7").write_text(
        'Box($T: Numeric) :: struct { value: $T }\n\n'
        'main :: fn() {\n'
        '    bad := Box(string){value: 1}\n'
        '    bad.value = bad.value\n'
        '}\n',
        encoding="utf-8",
    )
    process = cli_check(tmp_path, "main")
    assert process.returncode == 6, process.stdout + process.stderr
    combined = " ".join((process.stdout + process.stderr).split())
    assert "Generic constraint violation" in combined
    assert "'$T' of Box requires Numeric, got string" in combined


def test_struct_constraint_satisfied_still_builds(tmp_path, zig, zig_cache):
    output = compile_with_cli(tmp_path, '''
io :: import "std/io"

Box($T: Numeric) :: struct { value: $T }

main :: fn() {
    box := Box(i32){value: 5}
    io.println("{}", box.value)
}
''')
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "5\n"


def test_sibling_call_with_local_shadow_stays_local(tmp_path, zig, zig_cache):
    # A nested function sharing a sibling's plain name must capture bare
    # calls after its declaration; the emit-time rewrite keyed on plain
    # names called the sibling instead.
    write_module(tmp_path, "helper", '''
pub work :: fn() i32 {
    ret 1
}

pub shadow :: fn() i32 {
    work :: fn() i32 {
        ret 5
    }
    ret work()
}
''')
    output = compile_with_cli(tmp_path, '''
h :: import "helper"
io :: import "std/io"

main :: fn() {
    io.println("{}", h.shadow())
}
''')
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "5\n"


def test_sibling_call_passes_ref_argument(tmp_path, zig, zig_cache):
    # Bare sibling calls go through the module-call path, which must wrap
    # implicit ref arguments with `&` like direct calls do.
    write_module(tmp_path, "helper", '''
pub increment :: fn(x: ref i32) {
    x += 1
}

pub run :: fn() i32 {
    count := 0
    increment(count)
    ret count * 10
}
''')
    output = compile_with_cli(tmp_path, '''
h :: import "helper"
io :: import "std/io"

main :: fn() {
    io.println("{}", h.run())
}
''')
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "10\n"


def test_alias_call_ignores_local_named_like_callee(tmp_path, zig, zig_cache):
    # The alias callee resolves in the merged program's global scope, so a
    # local sharing the callee's plain name cannot change which function
    # runs or reject the program.
    write_module(tmp_path, "helper", 'pub work :: fn() i32 {\n    ret 1\n}\n')
    output = compile_with_cli(tmp_path, '''
h :: import "helper"
io :: import "std/io"

main :: fn() {
    work := 7
    io.println("{} {}", h.work(), work)
}
''')
    for profile in PROFILES:
        binary = build(zig, zig_cache, tmp_path, output, profile)
        stdout, _ = run_piped(binary)
        assert stdout == "1 7\n"


def test_unresolvable_generic_return_raises_instead_of_void():
    """A generic return type no parameter carries must fail closed.

    The old emitter wrote a silent `void` fallback here (ZIG-36). The CLI
    cannot reach this path because parameter checking rejects first, so the
    emitter is exercised directly on a synthetic declaration.
    """
    from a7.ast_nodes import ASTNode, NodeKind
    from a7.backends.zig import ZigCodeGenerator
    from a7.errors import CodegenError

    program = ASTNode(
        kind=NodeKind.PROGRAM,
        declarations=[
            ASTNode(
                kind=NodeKind.FUNCTION,
                name="leak",
                parameters=[ASTNode(kind=NodeKind.PARAMETER, name="n",
                                     param_type=ASTNode(kind=NodeKind.TYPE_PRIMITIVE,
                                                        type_name="i32"))],
                return_type=ASTNode(kind=NodeKind.TYPE_GENERIC, name="T"),
                body=ASTNode(kind=NodeKind.BLOCK, statements=[]),
            ),
        ],
    )
    with pytest.raises(CodegenError, match="cannot resolve generic return type"):
        ZigCodeGenerator().generate(program)
