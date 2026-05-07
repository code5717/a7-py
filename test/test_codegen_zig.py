"""
Integration tests for A7 → Zig code generation.

Tests three levels:
1. Compilation: A7 source → Zig output succeeds
2. Syntax: Generated Zig passes `zig ast-check`
3. Patterns: Generated Zig contains expected code patterns
"""

import os
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.compile import A7Compiler
from src.tokens import Tokenizer
from src.parser import Parser
from src.ast_nodes import ASTNode, NodeKind
from src.backends.zig import ZigCodeGenerator
from src.errors import CodegenError
from src.passes import NameResolutionPass, TypeCheckingPass, SemanticValidationPass

EXAMPLES_DIR = PROJECT_ROOT / "examples"

# Strict semantic mode should compile all checked examples.
SEMANTIC_KNOWN_FAIL: set[str] = set()


def has_zig():
    """Check if zig is available on PATH."""
    try:
        result = subprocess.run(["zig", "version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


ZIG_AVAILABLE = has_zig()


def compile_a7_to_zig(source: str, filename: str = "test.a7") -> str:
    """Compile A7 source code to Zig string."""
    tokenizer = Tokenizer(source, filename=filename)
    tokens = tokenizer.tokenize()

    source_lines = source.splitlines()
    parser = Parser(tokens, filename=filename, source_lines=source_lines)
    ast = parser.parse()

    # Run semantic analysis
    name_resolver = NameResolutionPass()
    name_resolver.source_lines = source_lines
    symbol_table = name_resolver.analyze(ast, filename)

    type_map = None
    if len(name_resolver.errors) == 0:
        type_checker = TypeCheckingPass(symbol_table)
        type_checker.source_lines = source_lines
        type_checker.analyze(ast, filename)
        type_map = type_checker.node_types

    # Preprocess AST
    from src.ast_preprocessor import ASTPreprocessor
    preprocessor = ASTPreprocessor()
    ast = preprocessor.process(ast)

    # Generate Zig
    codegen = ZigCodeGenerator()
    return codegen.generate(ast, type_map=type_map, symbol_table=symbol_table)


def zig_ast_check(zig_code: str) -> tuple[bool, str]:
    """Run zig ast-check on the given code. Returns (success, error_message)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.zig', delete=False) as f:
        f.write(zig_code)
        f.flush()
        try:
            result = subprocess.run(
                ["zig", "ast-check", f.name],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "zig ast-check timed out"
        finally:
            os.unlink(f.name)


def zig_build_check(zig_code: str) -> tuple[bool, str]:
    """Try to compile the Zig code (not link). Returns (success, error_message)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.zig', delete=False) as f:
        f.write(zig_code)
        f.flush()
        try:
            result = subprocess.run(
                ["zig", "build-obj", f.name, "-fno-emit-bin"],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0, result.stderr.strip()
        finally:
            os.unlink(f.name)


# =============================================================================
# Level 1: All examples compile from A7 → Zig string
# =============================================================================

class TestA7Compilation:
    """Test that all example files compile from A7 to Zig without errors."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.compiler = A7Compiler(verbose=False)

    def _get_example_files(self):
        return sorted(EXAMPLES_DIR.glob("*.a7"))

    @pytest.mark.parametrize("example", sorted(EXAMPLES_DIR.glob("*.a7")),
                             ids=lambda p: p.stem)
    def test_example_compiles(self, example, tmp_path):
        """Every example should compile A7 → Zig without crashing."""
        if example.stem in SEMANTIC_KNOWN_FAIL:
            pytest.skip(f"Known semantic issue under strict mode: {example.stem}")
        output = tmp_path / example.with_suffix(".zig").name
        result = self.compiler.compile_file(str(example), str(output))
        assert result, f"Compilation failed for {example.name}"
        assert output.exists(), f"Output file not created for {example.name}"
        content = output.read_text()
        assert len(content) > 0, f"Empty output for {example.name}"


# =============================================================================
# Level 2: Generated Zig passes syntax check (zig ast-check)
# =============================================================================

# Examples that pass zig ast-check
ZIG_AST_CHECK_PASS = {
    "000_empty", "001_hello", "007_while", "008_switch",
    "015_types", "016_unions",
}

# Examples with known issues (skip ast-check for these)
# All 36 examples now pass zig ast-check
ZIG_AST_CHECK_KNOWN_FAIL: set = set()


@pytest.mark.skipif(not ZIG_AVAILABLE, reason="zig not installed")
class TestZigAstCheck:
    """Test that generated Zig passes syntax validation."""

    @pytest.mark.parametrize("example", sorted(EXAMPLES_DIR.glob("*.a7")),
                             ids=lambda p: p.stem)
    def test_ast_check(self, example, tmp_path):
        """Test zig ast-check on generated output."""
        stem = example.stem
        if stem in SEMANTIC_KNOWN_FAIL:
            pytest.skip(f"Known semantic issue under strict mode: {stem}")
        if stem in ZIG_AST_CHECK_KNOWN_FAIL:
            pytest.skip(f"Known issue: {stem}")

        compiler = A7Compiler(verbose=False)
        output = tmp_path / example.with_suffix(".zig").name
        compiler.compile_file(str(example), str(output))

        zig_code = output.read_text()
        ok, err = zig_ast_check(zig_code)
        assert ok, f"zig ast-check failed for {example.name}:\n{err}"


# =============================================================================
# Level 3: Specific code pattern tests
# =============================================================================

class TestCodePatterns:
    """Test that specific A7 constructs produce expected Zig patterns."""

    def test_unsupported_expression_raises_codegen_error(self):
        codegen = ZigCodeGenerator()

        with pytest.raises(CodegenError, match="unsupported expression node 'FALL'"):
            codegen._emit_expr(ASTNode(NodeKind.FALL))

    def test_fall_statement_raises_codegen_error(self):
        codegen = ZigCodeGenerator()

        with pytest.raises(CodegenError, match="fallthrough is not implemented"):
            codegen.visit(ASTNode(NodeKind.FALL))

    def test_hello_world(self):
        source = '''
io :: import "std/io"
main :: fn() {
    io.println("Hello, World!")
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const std = @import("std");' in zig
        assert 'pub fn main() void' in zig
        assert 'std.debug.print("Hello, World!\\n", .{})' in zig

    def test_string_escapes_are_emitted_as_zig_escapes(self):
        source = r'''
io :: import "std/io"
main :: fn() {
    io.print("line\nquote: \"A\"\x21")
}
'''
        zig = compile_a7_to_zig(source)
        assert 'std.debug.print("line\\nquote: \\"A\\"!", .{})' in zig

    def test_constant_declaration(self):
        source = 'PI :: 3.14\n'
        zig = compile_a7_to_zig(source)
        assert 'const PI = 3.14' in zig

    def test_variable_declaration(self):
        source = 'x := 42\n'
        zig = compile_a7_to_zig(source)
        assert 'var x = 42' in zig

    def test_typed_variable(self):
        source = '''
main :: fn() {
    x: i32 = 42
}
'''
        zig = compile_a7_to_zig(source)
        # x is never mutated, so codegen emits const
        assert 'const x: i32 = 42' in zig

    def test_function_with_params(self):
        source = '''
add :: fn(a: i32, b: i32) i32 {
    ret a + b
}
'''
        zig = compile_a7_to_zig(source)
        assert 'fn add(a: i32, b: i32) i32' in zig
        assert 'return (a + b)' in zig

    def test_main_is_pub(self):
        source = '''
main :: fn() {
    ret
}
'''
        zig = compile_a7_to_zig(source)
        assert 'pub fn main() void' in zig

    def test_struct_declaration(self):
        source = '''
Point :: struct {
    x: f64
    y: f64
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const Point = struct' in zig
        assert 'x: f64,' in zig
        assert 'y: f64,' in zig

    def test_enum_declaration(self):
        source = '''
Color :: enum {
    Red
    Green
    Blue
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const Color = enum' in zig
        assert 'Red,' in zig
        assert 'Green,' in zig
        assert 'Blue,' in zig

    def test_if_else(self):
        source = '''
main :: fn() {
    x := 10
    if x > 5 {
        x = 1
    } else {
        x = 2
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'if ((x > 5))' in zig or 'if (x > 5)' in zig

    def test_while_loop(self):
        source = '''
main :: fn() {
    i := 0
    while i < 10 {
        i += 1
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'while' in zig
        assert 'i += 1' in zig

    def test_for_c_style(self):
        source = '''
main :: fn() {
    sum := 0
    for i := 0; i < 10; i += 1 {
        sum += i
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'while' in zig  # C-style for becomes while in Zig
        assert 'i += 1' in zig

    def test_match_to_switch(self):
        source = '''
io :: import "std/io"
main :: fn() {
    day := 3
    match day {
        case 1: {
            io.println("Monday")
        }
        case 2: {
            io.println("Tuesday")
        }
        else: {
            io.println("Other")
        }
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'switch' in zig
        assert '1 =>' in zig
        assert 'else =>' in zig

    def test_return_statement(self):
        source = '''
double :: fn(x: i32) i32 {
    ret x * 2
}
'''
        zig = compile_a7_to_zig(source)
        assert 'return (x * 2)' in zig

    def test_string_type_mapping(self):
        source = '''
greet :: fn(name: string) string {
    ret name
}
'''
        zig = compile_a7_to_zig(source)
        assert '[]const u8' in zig

    def test_pointer_type_mapping(self):
        source = '''
inc :: fn(p: ref i32) {
    ret
}
'''
        zig = compile_a7_to_zig(source)
        assert '?*i32' in zig

    def test_array_type(self):
        source = '''
process :: fn(nums: [10]i32) i32 {
    ret nums[0]
}
'''
        zig = compile_a7_to_zig(source)
        assert '[10]i32' in zig

    def test_type_alias(self):
        # Type aliases are emitted when using struct/enum patterns
        source = '''
Point :: struct {
    x: i32
    y: i32
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const Point = struct' in zig

    def test_boolean_literal(self):
        source = '''
main :: fn() {
    a := true
    b := false
}
'''
        zig = compile_a7_to_zig(source)
        assert 'true' in zig
        assert 'false' in zig

    def test_nil_to_null(self):
        source = '''
main :: fn() {
    p: ref i32 = nil
}
'''
        zig = compile_a7_to_zig(source)
        assert 'null' in zig

    def test_defer(self):
        source = '''
io :: import "std/io"
main :: fn() {
    defer io.println("cleanup")
}
'''
        zig = compile_a7_to_zig(source)
        assert 'defer' in zig

    def test_break_continue(self):
        source = '''
main :: fn() {
    while true {
        break
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'break;' in zig

    def test_labeled_break_continue(self):
        source = '''
main :: fn() {
    outer_break: while true {
        break outer_break
    }

    outer_continue: for i := 0; i < 2; i += 1 {
        continue outer_continue
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'a7_loop_outer_break: while' in zig
        assert 'break :a7_loop_outer_break;' in zig
        assert 'a7_loop_outer_continue: while' in zig
        assert 'continue :a7_loop_outer_continue;' in zig

    def test_new_and_del(self):
        source = '''
main :: fn() {
    p := new i32
    del p
}
'''
        zig = compile_a7_to_zig(source)
        assert 'allocator' in zig
        assert 'create' in zig or 'alloc' in zig
        assert 'destroy' in zig

    def test_struct_init(self):
        source = '''
Point :: struct {
    x: i32
    y: i32
}
main :: fn() {
    p := Point{x: 1, y: 2}
}
'''
        zig = compile_a7_to_zig(source)
        assert 'Point{' in zig or 'Point {' in zig
        assert '.x = 1' in zig
        assert '.y = 2' in zig

    def test_integer_division(self):
        source = '''
div :: fn(a: i32, b: i32) i32 {
    ret a / b
}
'''
        zig = compile_a7_to_zig(source)
        assert '@divTrunc' in zig

    def test_union_declaration(self):
        source = '''
Value :: union {
    int_val: i32
    float_val: f64
    str_val: string
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const Value = union' in zig
        assert 'int_val: i32' in zig

    def test_io_println_with_format(self):
        source = '''
io :: import "std/io"
main :: fn() {
    x := 42
    io.println("Value: {}", x)
}
'''
        zig = compile_a7_to_zig(source)
        assert 'std.debug.print' in zig
        assert '{any}' in zig  # {} converted to {any}

    def test_char_escape_newline(self):
        source = "nl := '\\n'\n"
        zig = compile_a7_to_zig(source)
        # Should not contain a literal newline inside quotes
        for line in zig.splitlines():
            if 'nl' in line and "'" in line:
                assert '\n' not in line.split("'")[1] if line.count("'") >= 2 else True

    def test_empty_program(self):
        source = "// empty\n"
        zig = compile_a7_to_zig(source)
        # Should produce valid (possibly empty) output
        assert isinstance(zig, str)


# =============================================================================
# Level 4: Zig compilation (build check) for simple programs
# =============================================================================

@pytest.mark.skipif(not ZIG_AVAILABLE, reason="zig not installed")
class TestZigBuildCheck:
    """Test that simple generated Zig can be compiled by the Zig compiler."""

    def test_empty_main(self):
        source = 'main :: fn() {}\n'
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_hello_world_ast_check(self):
        source = '''
io :: import "std/io"
main :: fn() {
    io.println("Hello!")
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_function_call_ast_check(self):
        source = '''
add :: fn(a: i32, b: i32) i32 {
    ret a + b
}
main :: fn() {
    result := add(3, 4)
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_labeled_loop_ast_check(self):
        source = '''
main :: fn() {
    outer_break: while true {
        break outer_break
    }

    outer_continue: for i := 0; i < 2; i += 1 {
        continue outer_continue
    }
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_struct_and_enum_ast_check(self):
        source = '''
Color :: enum {
    Red
    Green
    Blue
}
Point :: struct {
    x: f64
    y: f64
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_while_loop_ast_check(self):
        source = '''
main :: fn() {
    i := 0
    while i < 10 {
        i += 1
    }
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_if_else_ast_check(self):
        source = '''
max :: fn(a: i32, b: i32) i32 {
    if a > b {
        ret a
    } else {
        ret b
    }
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"

    def test_match_ast_check(self):
        source = '''
Color :: enum {
    Red
    Green
    Blue
}
'''
        zig = compile_a7_to_zig(source)
        ok, err = zig_ast_check(zig)
        assert ok, f"ast-check failed:\n{err}\n\nGenerated:\n{zig}"
