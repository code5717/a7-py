"""
Tests for A7 to Zig code generation.

Every snippet goes through the full compiler pipeline, so a test cannot pin
Zig for a program the compiler rejects. Tests that take the `zig` fixture
build the output and run the binary.
"""

from pathlib import Path

import pytest

from a7.ast_nodes import ASTNode, BinaryOp, LiteralKind, NodeKind, UnaryOp
from a7.backends.zig import ZigCodeGenerator
from a7.errors import CodegenError, SourceSpan
from a7.parser import Parser
from a7.tokens import Tokenizer

from conftest import build_and_run, expect_exit, expect_ok
from pipeline_helpers import compile_to_zig as compile_a7_to_zig
from pipeline_helpers import pipeline_tmp  # noqa: F401


class TestCodePatterns:
    """Test that specific A7 constructs produce expected Zig patterns."""

    def test_unsupported_expression_raises_codegen_error(self):
        codegen = ZigCodeGenerator()

        with pytest.raises(CodegenError, match="unsupported expression node 'FALL'"):
            codegen._emit_expr(ASTNode(NodeKind.FALL))

    def test_fall_statement_raises_codegen_error(self):
        codegen = ZigCodeGenerator()

        with pytest.raises(CodegenError, match="fall used outside"):
            codegen.visit(ASTNode(NodeKind.FALL))

    def test_match_fallthrough_compiles_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    x := 1
    match x {
        case 1: {
            io.println("one")
            fall
        }
        case 2: {
            io.println("two")
        }
        else: {
            io.println("else")
        }
    }

    y := 3
    match y {
        case 1: {
            fall
        }
        case 2: {
            io.println("bad")
        }
        else: {
            defer io.println("cleanup else")
            io.println("else")
        }
    }
}
'''
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stderr == ""
        assert run.stdout.splitlines() == [
            "one",
            "two",
            "else",
            "cleanup else",
        ]

    def test_hello_world(self):
        source = '''
io :: import "std/io"
main :: fn() {
    io.println("Hello, World!")
}
'''
        zig = compile_a7_to_zig(source)
        assert 'const std = @import("std");' in zig
        assert 'pub fn main(init: std.process.Init) void' in zig
        assert 'std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf)' in zig
        assert 'fn __a7_user_main() void' in zig
        assert '__a7_stdout_print("Hello, World!\\n", .{})' in zig

    def test_string_escapes_are_emitted_as_zig_escapes(self):
        source = r'''
io :: import "std/io"
main :: fn() {
    io.print("line\nquote: \"A\"\x21")
}
'''
        zig = compile_a7_to_zig(source)
        assert '__a7_stdout_print("line\\nquote: \\"A\\"!", .{})' in zig

    def test_stdlib_import_aliases_emit_zig_stdlib_calls(self):
        """Arbitrary aliases for std/io and std/math should still lower as stdlib."""
        source = """
console :: import "std/io"
mathlib :: import "std/math"

main :: fn() {
    console.println("{}", mathlib.sqrt(9.0))
}
"""
        zig = compile_a7_to_zig(source)
        assert 'const std = @import("std");' in zig
        # A finite literal whose decimal text round-trips to the same bits
        # is emitted as written; only values with no faithful literal keep
        # the @bitCast form. The numeric value is pinned in
        # test_exact_constants.py.
        assert '__a7_stdout_print("{}\\n", .{@sqrt(' in zig
        assert '@sqrt(9.0)' in zig
        assert "console.println" not in zig
        assert "mathlib.sqrt" not in zig

    def test_io_println_writes_stdout_and_eprintln_writes_stderr(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    io.print("{}:", "out")
    io.println("{} {}", 1, true)
    io.eprintln("{}:", "err")
}
'''
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout == "out:1 true\n"
        assert run.stderr == "err:\n"
        generated = compile_a7_to_zig(source)
        assert generated.count("std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf)") == 1
        assert generated.count("std.Io.File.stderr().writerStreaming(__a7_io.?, &__a7_stream_buf)") == 1
        assert "std.os.linux.write" not in generated

    def test_integer_remainder_matches_truncating_division(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    a: i32 = -17
    b: i32 = 5
    io.println("{} {}", a / b, a % b)
}
'''
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout.strip() == "-3 -2"
        assert run.stderr == ""

    def test_slice_ptr_and_len_fields_emit_zig_slice_fields(self, tmp_path, zig):
        source = '''
io :: import "std/io"
main :: fn() {
    arr: [4]i32 = [10, 20, 30, 40]
    tail := arr[1..4]
    ptr := tail.ptr
    io.println("{}", tail.len)
}
'''
        generated = compile_a7_to_zig(source)
        assert "tail.ptr" in generated
        assert "tail.len" in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "3\n"

    def test_address_taken_local_uses_mutable_storage(self, tmp_path, zig):
        source = '''
touch :: fn(p: ref i32) {
    p += 1
}

main :: fn() {
    x: i32 = 7
    touch(x)
}
'''
        generated = compile_a7_to_zig(source)
        assert "var x: i32 = 7;" in generated
        assert "touch(&x);" in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr

    def test_string_slices_compile_and_run(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    text: string = "abcdef"
    for ch in text[1..4] {
        io.print("{}", ch)
    }
    for ch in text[4..] {
        io.print("{}", ch)
    }
    io.println("")
}
'''
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stderr == ""
        assert run.stdout.strip() == "bcdef"

    def test_constant_declaration(self):
        # A `::` declaration is an exact compile-time constant, so it is
        # substituted at its use site rather than emitted as a Zig `const`.
        # This test pins that lowering, which is what the file-level constant
        # is for; a file with no `main` is covered separately below.
        zig = compile_a7_to_zig("""
io :: import "std/io"

MAX :: 4

main :: fn() {
    x: i32 = MAX
    io.println("{}", x)
}
""")
        assert "const x: i32 = 4;" in zig
        assert "MAX" not in zig

    def test_library_with_only_a_constant_emits_empty_translation_unit(self):
        """A `::` constant is substituted at use sites, so a library that
        holds only one emits no Zig."""
        zig = compile_a7_to_zig('PI :: 3.14\n')
        assert zig.strip() == ""

    def test_variable_declaration(self):
        source = 'x := 42\n'
        zig = compile_a7_to_zig(source)
        assert 'var x: i32 = 42' in zig

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
        assert 'return (a +% b)' in zig

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
        assert 'i +%= 1' in zig

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
        assert 'i +%= 1' in zig

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
        assert 'return (x *% 2)' in zig

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

    def test_fixed_array_addition_assignment(self):
        source = '''
main :: fn() {
    a: [4]f64 = [1.0, 2.0, 3.0, 4.0]
    b: [4]f64 = [5.0, 6.0, 7.0, 8.0]
    c: [4]f64
    c = a + b
}
'''
        zig = compile_a7_to_zig(source)
        assert 'c = (@as(@Vector(4, f64), a) + @as(@Vector(4, f64), b));' in zig
        assert 'c[0] = a[0] + b[0];' not in zig
        assert 'c = (a + b);' not in zig

    def test_fixed_array_addition_expression_contexts(self, tmp_path, zig):
        source = '''
io :: import "std/io"

first :: fn(xs: [4]f64) f64 {
    ret xs[0]
}

main :: fn() {
    a: [4]f64 = [1.0, 2.0, 3.0, 4.0]
    b: [4]f64 = [5.0, 6.0, 7.0, 8.0]
    value := first(a + b)
    item := (a + b)[2]
    io.println("{} {}", value, item)
}
'''
        generated = compile_a7_to_zig(source)
        assert 'first((@as(@Vector(4, f64), a) + @as(@Vector(4, f64), b)))' in generated
        assert '(@as(@Vector(4, f64), a) + @as(@Vector(4, f64), b))[2]' in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "6 10\n"

    def test_void_call_statement_does_not_emit_discard(self, tmp_path, zig):
        source = '''
noop :: fn() {
}

main :: fn() {
    noop()
}
'''
        generated = compile_a7_to_zig(source)
        assert "noop();" in generated
        assert "_ = noop();" not in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr

    def test_generic_call_uses_declared_type_parameter_order(self, tmp_path, zig):
        source = '''
io :: import "std/io"

choose($U, $T) :: fn(left: $U, right: $T) $T {
    ret right
}

main :: fn() {
    answer := choose("left", 42)
    io.println("{}", answer)
}
'''
        generated = compile_a7_to_zig(source)
        assert "fn choose(comptime U: type, comptime T: type, _: U, right: T) T" in generated
        assert 'choose([]const u8, i32, "left", 42)' in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "42\n"

    def test_usize_index_does_not_emit_intcast(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    arr: [3]i32 = [10, 20, 30]
    i: usize = 1
    value := arr[i]
    io.println("{}", value)
}
'''
        generated = compile_a7_to_zig(source)
        assert "arr[i]" in generated
        assert "arr[@intCast(i)]" not in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "20\n"

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
    @outer_break while true {
        break outer_break
    }

    @outer_continue for i := 0; i < 2; i += 1 {
        continue outer_continue
    }
}
'''
        zig = compile_a7_to_zig(source)
        assert 'a7_loop_outer_break: while' in zig
        assert 'break :a7_loop_outer_break;' in zig
        assert 'a7_loop_outer_continue: while' in zig
        assert 'continue :a7_loop_outer_continue;' in zig

    def test_labeled_for_in_and_indexed_for_in_runtime(self, tmp_path, zig):
        source = '''
io :: import "std/io"

main :: fn() {
    arr: [3]i32 = [1, 2, 3]

    break_total := 0
    @outer_break for x in arr {
        if x == 2 {
            break outer_break
        }
        break_total += x
    }

    continue_total := 0
    @outer_continue for x in arr {
        if x == 2 {
            continue outer_continue
        }
        continue_total += x
    }

    indexed_total: usize = 0
    @outer_indexed for i, x in arr {
        if i == 2 {
            break outer_indexed
        }
        if x == 0 {
            indexed_total += 100
        }
        indexed_total += i
    }

    io.println("{} {} {}", break_total, continue_total, indexed_total)
}
'''
        generated = compile_a7_to_zig(source)
        assert "a7_loop_outer_break: for" in generated
        assert "break :a7_loop_outer_break" in generated
        assert "a7_loop_outer_continue: for" in generated
        assert "continue :a7_loop_outer_continue" in generated
        assert "a7_loop_outer_indexed: for" in generated
        assert "for (arr, 0..) |x, i|" in generated
        assert "@intCast(i)" not in generated
        assert "break :a7_loop_outer_indexed" in generated

        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "1 4 1\n"

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

    def test_new_and_del_build_and_run(self, tmp_path, zig):
        source = '''
io :: import "std/io"
Box :: struct {
    value: i32
}
main :: fn() {
    value_box := new Box
    if value_box == nil {
        io.println("allocation failed")
        ret
    }
    value_box.value = 42
    io.println("heap value = {}", value_box.value)
    del value_box
    io.println("deleted")
}
'''
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout.splitlines() == ["heap value = 42", "deleted"]

    def test_del_non_reference_reports_span(self):
        from a7.types import PrimitiveType
        codegen = ZigCodeGenerator()
        target_span = SourceSpan(start_line=2, start_column=9, end_line=2, end_column=10)
        target = ASTNode(NodeKind.IDENTIFIER, name="x", span=target_span)
        codegen._type_map = {id(target): PrimitiveType("i32")}
        node = ASTNode(
            NodeKind.DEL,
            expression=target,
            span=SourceSpan(start_line=2, start_column=5, end_line=2, end_column=10),
        )
        with pytest.raises(CodegenError, match="del requires a reference type") as exc_info:
            codegen._visit_del(node)
        assert exc_info.value.span is target_span

    def test_unsupported_pattern_reports_span(self):
        codegen = ZigCodeGenerator()
        span = SourceSpan(start_line=3, start_column=5, end_line=3, end_column=9)
        with pytest.raises(CodegenError, match="unsupported match pattern") as exc_info:
            codegen._emit_pattern(ASTNode(NodeKind.FALL, span=span))
        assert exc_info.value.span is span

    def test_negative_range_bounds_emit_as_expressions(self):
        codegen = ZigCodeGenerator()
        codegen._type_map = {}
        operand = ASTNode(
            NodeKind.LITERAL,
            literal_kind=LiteralKind.INTEGER,
            literal_value=5,
            raw_text="5",
        )
        neg = ASTNode(NodeKind.UNARY, operator=UnaryOp.NEG, operand=operand)
        node = ASTNode(NodeKind.PATTERN_RANGE, start=neg, end=neg)
        assert codegen._emit_pattern(node) == "(-5)...(-5)"

    def test_spanless_errors_carry_spans(self):
        codegen = ZigCodeGenerator()
        span = SourceSpan(start_line=4, start_column=3, end_line=4, end_column=10)

        class _BogusOp:
            name = "BOGUS"

            def __hash__(self):
                return hash("BOGUS")

            def __eq__(self, other):
                return False

        with pytest.raises(CodegenError, match="unsupported binary operator") as exc_info:
            codegen._binary_op_to_zig(_BogusOp(), span)
        assert exc_info.value.span is span
        with pytest.raises(CodegenError, match="missing array binary operand") as exc_info:
            codegen._emit_array_operand_expr(None, "Zig", span)
        assert exc_info.value.span is span
        with pytest.raises(CodegenError, match="missing type node") as exc_info:
            codegen._emit_type_node(None, span=span)
        assert exc_info.value.span is span
        with pytest.raises(CodegenError, match="missing type leaf") as exc_info:
            codegen._emit_type_leaf(None, span=span)
        assert exc_info.value.span is span

    def test_array_binary_missing_operand_reports_binary_span(self):
        from a7.types import ArrayType, PrimitiveType
        codegen = ZigCodeGenerator()
        span = SourceSpan(start_line=4, start_column=3, end_line=4, end_column=10)
        value = ASTNode(NodeKind.BINARY, operator=BinaryOp.ADD, left=None, right=None, span=span)
        codegen._type_map = {id(value): ArrayType(PrimitiveType("i32"), 4)}
        target = ASTNode(NodeKind.IDENTIFIER, name="arr")
        with pytest.raises(CodegenError, match="missing array binary operand") as exc_info:
            codegen._emit_array_binary_assignment(target, value)
        assert exc_info.value.span is span

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
    if b == 0 { ret 0 }
    ret a / b
}
'''
        zig = compile_a7_to_zig(source)
        assert '@divTrunc' in zig

    def test_approved_numeric_cast_uses_int_cast(self):
        source = '''
main :: fn() {
    x: i32 = 42
    if x < 0 { ret }
    y := cast(usize, x)
}
'''
        zig = compile_a7_to_zig(source)
        assert '@intCast' in zig

    def test_unclassified_cast_is_rejected_by_zig_codegen(self):
        source = '''
main :: fn() {
    x: i32 = 42
    y := cast(i64, x)
}
'''
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()
        ast = Parser(tokens).parse()
        codegen = ZigCodeGenerator()
        with pytest.raises(CodegenError, match="not approved"):
            codegen.generate(ast)

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

    def test_union_field_initialization_and_access(self, tmp_path, zig):
        source = '''
io :: import "std/io"

Value :: union {
    int_val: i32
    float_val: f64
}

main :: fn() {
    v := Value{int_val: 42}
    io.println("{}", v.int_val)
}
'''
        generated = compile_a7_to_zig(source)
        assert 'const v = Value{ .int_val = 42 };' in generated
        assert 'v.int_val' in generated
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "42\n"


    def test_io_println_with_format(self):
        source = '''
io :: import "std/io"
main :: fn() {
        x := 42
        io.println("Value: {}", x)
    }
    '''
        zig = compile_a7_to_zig(source)
        assert 'std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf)' in zig
        assert 'std.os.linux.write' not in zig
        main_part = zig[zig.index("pub fn main"):]
        assert '__a7_stdout_writer = std.Io.File.stdout()' in main_part
        assert main_part.index('__a7_user_main();') < main_part.index('__a7_stdout_flush();')
        assert '"Value: {}\\n"' in zig  # typed integer placeholder stays stable

    def test_helper_prints_use_generated_stdout_helper(self, tmp_path, zig):
        source = '''
io :: import "std/io"

helper :: fn() {
    io.println("helper")
}

main :: fn() {
    io.println("before")
    helper()
    io.println("after")
}
'''
        generated = compile_a7_to_zig(source)
        assert generated.count("fn __a7_stdout_print") == 1
        assert generated.count("std.Io.File.stdout().writerStreaming(__a7_io.?, &__a7_stdout_buf)") == 1
        assert "std.os.linux.write" not in generated
        assert "fn helper() void {\n    __a7_stdout_print" in generated
        assert "fn helper() void {\n    defer " not in generated

        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stdout + run.stderr
        assert run.stdout == "before\nhelper\nafter\n"

    def test_char_escape_newline(self, tmp_path, zig):
        source = r'''
io :: import "std/io"
main :: fn() {
    nl := '\n'
    io.print("a{}b", nl)
}
'''
        # The Zig char literal keeps the escape; a raw newline would not build.
        assert r"const nl: u8 = '\n';" in compile_a7_to_zig(source)
        run = build_and_run(source, tmp_path, zig)
        assert run.returncode == 0, run.stderr
        assert run.stdout == "a\nb"

    def test_program_without_main_needs_library_mode(self, tmp_path):
        source = "// empty\n"
        expect_exit(source, tmp_path, 6, "No entry point: file defines no 'main :: fn()'")
        result = expect_ok(source, tmp_path, is_library=True)
        assert Path(result.output_path).read_text(encoding="utf-8") == ""

    def test_release_nonwrap_proven_literals(self):
        source = '''
main :: fn() {
    x := 5
    y := 3
    s := x + y
}
'''
        release = compile_a7_to_zig(source, profile="release")
        assert '(x + y)' in release
        assert '+%' not in release
        debug = compile_a7_to_zig(source, profile="debug")
        assert '(x +% y)' in debug

    def test_release_wrap_unproven_params(self):
        source = '''
add :: fn(a: i32, b: i32) i32 {
    ret a + b
}
'''
        release = compile_a7_to_zig(source, profile="release")
        assert '(a +% b)' in release
        debug = compile_a7_to_zig(source, profile="debug")
        assert '(a +% b)' in debug

    def test_release_nonwrap_compound_assign(self):
        source = '''
main :: fn() {
    x := 10
    x += 5
}
'''
        release = compile_a7_to_zig(source, profile="release")
        assert 'x += 5' in release
        assert '+%=' not in release
        debug = compile_a7_to_zig(source, profile="debug")
        assert 'x +%= 5' in debug

    def test_release_nonwrap_guarded_loop_increment(self):
        source = '''
main :: fn() {
    i := 0
    while i < 9 {
        i += 1
    }
}
'''
        release = compile_a7_to_zig(source, profile="release")
        assert 'i += 1' in release
        assert '+%=' not in release
        debug = compile_a7_to_zig(source, profile="debug")
        assert 'i +%= 1' in debug

    def test_release_nonwrap_mul_overflow_unproven(self):
        source = '''
main :: fn() {
    a := 100000
    b := a * a * a
}
'''
        release = compile_a7_to_zig(source, profile="release")
        assert '*%' in release


# =============================================================================
# Generated Zig builds and runs
# =============================================================================

def run_stdout(source, tmp_path, zig):
    run = build_and_run(source, tmp_path, zig)
    assert run.returncode == 0, run.stderr
    return run.stdout


class TestZigBuildAndRun:
    """Small programs compile, build with Zig, and print the expected output."""

    def test_empty_main_builds_and_runs(self, tmp_path, zig):
        assert run_stdout('main :: fn() {}\n', tmp_path, zig) == ""

    def test_hello_world_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"
main :: fn() {
    io.println("Hello!")
}
'''
        assert run_stdout(source, tmp_path, zig) == "Hello!\n"

    def test_function_call_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"
add :: fn(a: i32, b: i32) i32 {
    ret a + b
}
main :: fn() {
    result := add(3, 4)
    io.println("{}", result)
}
'''
        assert run_stdout(source, tmp_path, zig) == "7\n"

    def test_labeled_loops_build_and_run(self, tmp_path, zig):
        source = '''
io :: import "std/io"
main :: fn() {
    passes := 0
    @outer_break while true {
        passes += 1
        break outer_break
    }

    @outer_continue for i := 0; i < 2; i += 1 {
        passes += 1
        continue outer_continue
    }
    io.println("{}", passes)
}
'''
        assert run_stdout(source, tmp_path, zig) == "3\n"

    def test_struct_and_enum_build_and_run(self, tmp_path, zig):
        source = '''
io :: import "std/io"
Color :: enum {
    Red
    Green
    Blue
}
Point :: struct {
    x: f64
    y: f64
}
main :: fn() {
    p := Point{x: 1.5, y: 2.5}
    c := Color.Green
    if c == Color.Green {
        io.println("{} {}", p.x, p.y)
    }
}
'''
        assert run_stdout(source, tmp_path, zig) == "1.5 2.5\n"

    def test_generic_struct_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"

Box :: struct {
    value: $T
}

main :: fn() {
    b: Box(i32) = Box(i32){value: 42}
    io.println("{}", b.value)
}
'''
        assert "Box(i32)" in compile_a7_to_zig(source)
        assert run_stdout(source, tmp_path, zig) == "42\n"

    def test_while_loop_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"
main :: fn() {
    i := 0
    while i < 10 {
        i += 1
    }
    io.println("{}", i)
}
'''
        assert run_stdout(source, tmp_path, zig) == "10\n"

    def test_if_else_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"
max :: fn(a: i32, b: i32) i32 {
    if a > b {
        ret a
    } else {
        ret b
    }
}
main :: fn() {
    io.println("{} {}", max(3, 7), max(9, 2))
}
'''
        assert run_stdout(source, tmp_path, zig) == "7 9\n"

    def test_enum_match_builds_and_runs(self, tmp_path, zig):
        source = '''
io :: import "std/io"
Color :: enum {
    Red
    Green
    Blue
}
main :: fn() {
    c := Color.Blue
    match c {
        case Color.Red: io.println("red")
        case Color.Green: io.println("green")
        case Color.Blue: io.println("blue")
    }
}
'''
        assert run_stdout(source, tmp_path, zig) == "blue\n"
