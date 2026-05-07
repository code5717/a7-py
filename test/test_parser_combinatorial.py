"""
Combinatorial and systematic tests for parser.

Tests systematic combinations of language features to ensure
all valid combinations parse correctly.
"""

import pytest
from src.parser import parse_a7
from src.ast_nodes import NodeKind
from src.errors import ParseError


class TestTypeCombinations:
    """Systematic tests for type combinations."""

    def test_all_primitive_types_in_arrays(self):
        """Test arrays of each primitive type."""
        code = """
        main :: fn() {
            // Integer types
            arr_i8: [10]i8
            arr_i16: [10]i16
            arr_i32: [10]i32
            arr_i64: [10]i64

            arr_u8: [10]u8
            arr_u16: [10]u16
            arr_u32: [10]u32
            arr_u64: [10]u64

            // Float types
            arr_f32: [10]f32
            arr_f64: [10]f64

            // Other types
            arr_bool: [10]bool
            arr_char: [10]char
            arr_string: [10]string
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_all_primitive_types_in_pointers(self):
        """Test pointers to each primitive type."""
        code = """
        main :: fn() {
            // Integer types
            ptr_i8: ref i8
            ptr_i16: ref i16
            ptr_i32: ref i32
            ptr_i64: ref i64

            ptr_u8: ref u8
            ptr_u16: ref u16
            ptr_u32: ref u32
            ptr_u64: ref u64

            // Float types
            ptr_f32: ref f32
            ptr_f64: ref f64

            // Other types
            ptr_bool: ref bool
            ptr_char: ref char
            ptr_string: ref string
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_all_primitive_types_in_functions(self):
        """Test functions with each primitive type."""
        code = """
        // Integer parameter functions
        f_i8 :: fn(x: i8) i8 { ret x }
        f_i16 :: fn(x: i16) i16 { ret x }
        f_i32 :: fn(x: i32) i32 { ret x }
        f_i64 :: fn(x: i64) i64 { ret x }

        f_u8 :: fn(x: u8) u8 { ret x }
        f_u16 :: fn(x: u16) u16 { ret x }
        f_u32 :: fn(x: u32) u32 { ret x }
        f_u64 :: fn(x: u64) u64 { ret x }

        // Float parameter functions
        f_f32 :: fn(x: f32) f32 { ret x }
        f_f64 :: fn(x: f64) f64 { ret x }

        // Other types
        f_bool :: fn(x: bool) bool { ret x }
        f_char :: fn(x: char) char { ret x }
        f_string :: fn(x: string) string { ret x }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_nested_type_combinations(self):
        """Test various nested type combinations."""
        code = """
        main :: fn() {
            // Array of pointers
            arr_of_ptr: [10]ref i32

            // Pointer to array
            ptr_to_arr: ref [10]i32

            // Array of arrays
            arr_of_arr: [5][10]i32

            // Pointer to pointer
            ptr_to_ptr: ref ref i32

            // Array of array of pointer
            complex1: [5][10]ref i32

            // Pointer to array of array
            complex2: ref [5][10]i32

            // Array of pointer to array
            complex3: [5]ref [10]i32

            // Triple nesting
            triple1: [3][4][5]i32
            triple2: ref ref ref i32
            triple3: [3]ref [4]ref [5]i32
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestOperatorCombinations:
    """Systematic tests for operator combinations."""

    def test_all_binary_operators(self):
        """Test all binary operators."""
        code = """
        main :: fn() {
            // Arithmetic
            a := x + y
            b := x - y
            c := x * y
            d := x / y
            e := x % y

            // Bitwise
            f := x & y
            g := x | y
            h := x ^ y
            i := x << y
            j := x >> y

            // Comparison
            k := x == y
            l := x != y
            m := x < y
            n := x <= y
            o := x > y
            p := x >= y

            // Logical
            q := x and y
            r := x or y
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_all_unary_operators(self):
        """Test all unary operators."""
        code = """
        main :: fn() {
            // Logical not
            a := !x
            b := !true
            c := !false

            // Bitwise not
            d := ~x
            e := ~0xFF

            // Negative
            f := -x
            g := -42
            h := -3.14

            // Property-based (pointer operations)
            ptr := x.adr
            val := ptr.val
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_all_assignment_operators(self):
        """Test all assignment operators."""
        code = """
        main :: fn() {
            // Simple assignment
            x = 10

            // Compound assignments
            x += 5
            x -= 3
            x *= 2
            x /= 4
            x %= 3

            // Bitwise compound
            x &= 0xFF
            x |= 0x0F
            x ^= 0xAA
            x <<= 2
            x >>= 1
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_mixed_operator_precedence(self):
        """Test operator precedence combinations."""
        code = """
        main :: fn() {
            // Arithmetic precedence
            a := 1 + 2 * 3
            b := (1 + 2) * 3
            c := 1 * 2 + 3
            d := 1 + 2 - 3 + 4

            // With bitwise
            e := x & 0xFF + 1
            f := (x & 0xFF) + 1
            g := x & (0xFF + 1)

            // With logical
            h := a < b and c > d
            i := (a < b) and (c > d)
            j := a and b or c and d

            // Complex combinations
            k := a + b * c < d - e / f
            l := (x & mask) << shift | (y & mask)
            m := !a and b or !c and d
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestDeclarationCombinations:
    """Systematic tests for declaration combinations."""

    def test_variable_declaration_variants(self):
        """Test all variable declaration forms."""
        code = """
        main :: fn() {
            // Inferred type
            a := 42

            // Explicit type
            b: i32 = 42

            // Uninitialized
            c: i32

            // Complex types
            d: [10]i32
            e: ref i32 = nil
            f: struct { x: i32, y: i32 }

            // Multiple declarations
            x := 1
            y := 2
            z := 3
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_function_declaration_variants(self):
        """Test various function declaration forms."""
        code = """
        // No parameters, no return
        f1 :: fn() {
            work()
        }

        // One parameter, no return
        f2 :: fn(x: i32) {
            work()
        }

        // Multiple parameters, no return
        f3 :: fn(x: i32, y: i32, z: i32) {
            work()
        }

        // No parameters, with return
        f4 :: fn() i32 {
            ret 42
        }

        // Parameters and return
        f5 :: fn(x: i32, y: i32) i32 {
            ret x + y
        }

        // Generic
        f6 :: fn(x: $T) $T {
            ret x
        }

        // Multiple generics
        f7 :: fn(x: $T1, y: $T2) $T1 {
            ret x
        }

        // Complex return type
        f8 :: fn() struct { x: i32, y: i32 } {
            ret struct { x: i32, y: i32 } { x: 0, y: 0 }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_struct_declaration_variants(self):
        """Test various struct forms."""
        code = """
        // Empty struct
        Empty :: struct {
        }

        // Single field
        Single :: struct {
            value: i32
        }

        // Multiple fields
        Multi :: struct {
            a: i32
            b: f64
            c: string
        }

        // With arrays
        WithArray :: struct {
            data: [100]i32
            size: i32
        }

        // With pointers
        WithPointer :: struct {
            next: ref WithPointer
            value: i32
        }

        // With function pointers
        WithFunction :: struct {
            callback: fn(i32) bool
            state: i32
        }

        // Generic struct
        Generic($T) :: struct {
            data: $T
        }

        // Multiple generics
        Pair($T1, $T2) :: struct {
            first: $T1
            second: $T2
        }

        // Nested structs
        Nested :: struct {
            inner: struct {
                value: i32
            }
            outer: i32
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_enum_declaration_variants(self):
        """Test various enum forms."""
        code = """
        // Simple enum
        Color :: enum {
            RED
            GREEN
            BLUE
        }

        // With values
        Status :: enum {
            OK = 0
            ERROR = 1
            PENDING = 2
        }

        // Mixed (some with values)
        Mixed :: enum {
            FIRST
            SECOND = 100
            THIRD
        }

        // Single variant
        Single :: enum {
            ONLY
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestControlFlowCombinations:
    """Systematic tests for control flow combinations."""

    def test_if_statement_variants(self):
        """Test all if statement forms."""
        code = """
        main :: fn() {
            // Simple if
            if condition {
                work()
            }

            // If with else
            if condition {
                work1()
            } else {
                work2()
            }

            // If else-if
            if condition1 {
                work1()
            } else if condition2 {
                work2()
            }

            // If else-if else
            if condition1 {
                work1()
            } else if condition2 {
                work2()
            } else {
                work3()
            }

            // Multiple else-if
            if condition1 {
                work1()
            } else if condition2 {
                work2()
            } else if condition3 {
                work3()
            } else if condition4 {
                work4()
            } else {
                work5()
            }

            // Nested if
            if outer {
                if inner {
                    work()
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_loop_variants(self):
        """Test all loop forms."""
        code = """
        main :: fn() {
            // Infinite loop
            for {
                if done {
                    break
                }
            }

            // C-style for
            for i := 0; i < 10; i += 1 {
                work(i)
            }

            // Range iteration
            arr: [10]i32
            for val in arr {
                process(val)
            }

            // Indexed range iteration
            for i, val in arr {
                process(i, val)
            }

            // While loop
            while condition {
                work()
            }

            // With break
            for i := 0; i < 100; i += 1 {
                if should_stop {
                    break
                }
            }

            // With continue
            for i := 0; i < 100; i += 1 {
                if should_skip {
                    continue
                }
                work(i)
            }

            // Labeled loops
            outer: for i := 0; i < 10; i += 1 {
                inner: for j := 0; j < 10; j += 1 {
                    if done {
                        break outer
                    }
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_labeled_continue_and_nested_labeled_loops(self):
        """Labeled continue and nested loop labels should be preserved in the AST."""
        code = """
        main :: fn() {
            outer: for i := 0; i < 10; i += 1 {
                inner: while keep_going {
                    if should_skip {
                        continue outer
                    }
                    if should_stop {
                        break inner
                    }
                }
            }
        }
        """

        result = parse_a7(code)
        main = result.declarations[0]
        outer_loop = main.body.statements[0]
        inner_loop = outer_loop.body.statements[0]
        continue_stmt = inner_loop.body.statements[0].then_stmt.statements[0]
        break_stmt = inner_loop.body.statements[1].then_stmt.statements[0]

        assert outer_loop.kind == NodeKind.FOR
        assert outer_loop.label == "outer"
        assert inner_loop.kind == NodeKind.WHILE
        assert inner_loop.label == "inner"
        assert continue_stmt.kind == NodeKind.CONTINUE
        assert continue_stmt.label == "outer"
        assert break_stmt.kind == NodeKind.BREAK
        assert break_stmt.label == "inner"

    def test_labeled_for_in_and_indexed_for_in_parse_labels(self):
        """Labels should work on both for-in loop forms."""
        code = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]

            values: for value in arr {
                continue values
            }

            indexed: for i, value in arr {
                break indexed
            }
        }
        """

        result = parse_a7(code)
        main = result.declarations[0]
        for_in = main.body.statements[1]
        indexed_for_in = main.body.statements[2]

        assert for_in.kind == NodeKind.FOR_IN
        assert for_in.label == "values"
        assert for_in.body.statements[0].kind == NodeKind.CONTINUE
        assert for_in.body.statements[0].label == "values"
        assert indexed_for_in.kind == NodeKind.FOR_IN_INDEXED
        assert indexed_for_in.label == "indexed"
        assert indexed_for_in.index_var == "i"
        assert indexed_for_in.iterator == "value"
        assert indexed_for_in.body.statements[0].kind == NodeKind.BREAK
        assert indexed_for_in.body.statements[0].label == "indexed"

    @pytest.mark.parametrize(
        "code",
        [
            """
            main :: fn() {
                bad:
            }
            """,
            """
            main :: fn() {
                bad: if condition {
                    work()
                }
            }
            """,
            """
            main :: fn() {
                bad: continue
            }
            """,
        ],
    )
    def test_malformed_loop_labels_are_rejected(self, code):
        """Labels are only valid directly before loop statements."""
        with pytest.raises(ParseError):
            parse_a7(code)

    def test_match_statement_variants(self):
        """Test all match statement forms."""
        code = """
        main :: fn() {
            // Simple match
            match value {
                case 1: work1()
                case 2: work2()
                else: work3()
            }

            // Multiple values per case
            match value {
                case 1, 2, 3: work1()
                case 4, 5: work2()
                else: work3()
            }

            // Match expression
            result := match value {
                case 1: 100
                case 2: 200
                else: 300
            }

            // Nested match
            match outer {
                case 1: {
                    match inner {
                        case 1: work()
                        else: other()
                    }
                }
                else: default()
            }

            // Match with complex expressions
            match compute() {
                case 1: process(value1)
                case 2: process(value2)
                else: process(default_value)
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestExpressionCombinations:
    """Systematic tests for expression combinations."""

    def test_call_expression_variants(self):
        """Test various function call forms."""
        code = """
        main :: fn() {
            // No arguments
            result1 := func()

            // One argument
            result2 := func(42)

            // Multiple arguments
            result3 := func(1, 2, 3)

            // Nested calls
            result4 := outer(inner(value))

            // Chain calls
            result5 := obj.method1().method2().method3()

            // Generic instantiation
            result6 := generic_func(i32, 42)

            // Multiple generic parameters
            result7 := multi_generic(i32, f64, 42, 3.14)

            // With complex expressions as arguments
            result8 := func(a + b, c * d, e / f)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_member_access_variants(self):
        """Test various member access forms."""
        code = """
        main :: fn() {
            // Simple field access
            x := obj.field

            // Nested field access
            y := obj.field1.field2.field3

            // Array element access
            z := arr[0]

            // Multidimensional array
            w := matrix[i][j]

            // Mix of field and array
            v := obj.field[i].nested[j].value

            // Method call
            result := obj.method()

            // Chained methods
            result2 := obj.method1().method2()

            // Module qualified
            io.println("test")

            // Enum variant
            color := Color.RED
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_literal_expression_variants(self):
        """Test all literal forms."""
        code = """
        main :: fn() {
            // Integer literals
            dec := 42
            hex := 0xDEAD
            zero := 0

            // Float literals
            f1 := 3.14
            f2 := 0.5
            f3 := 100.0

            // String literals
            s1 := "hello"
            s2 := ""
            s3 := "with\nescapes"

            // Char literals
            c1 := 'a'
            c2 := '\n'
            c3 := '\x41'

            // Boolean literals
            t := true
            f := false

            // Nil literal
            ptr := nil

            // Array literals
            arr1 := [1, 2, 3]
            arr2 := []

            // Struct literals
            point := Point{x: 1, y: 2}
            empty := Point{}
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestMemoryOperationCombinations:
    """Systematic tests for memory operations."""

    def test_new_del_combinations(self):
        """Test new/del with various types."""
        code = """
        main :: fn() {
            // Basic types
            p1 := new(i32)
            del p1

            p2 := new(f64)
            del p2

            p3 := new(bool)
            del p3

            // Complex types
            p4 := new([100]i32)
            del p4

            p5 := new(MyStruct)
            del p5

            // With immediate use
            ptr := new(i32)
            ptr.val = 42
            value := ptr.val
            del ptr

            // Multiple allocations
            arr: [10]ref i32
            for i := 0; i < 10; i += 1 {
                arr[i] = new(i32)
            }

            for i := 0; i < 10; i += 1 {
                del arr[i]
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_pointer_operations(self):
        """Test .adr and .val in combinations."""
        code = """
        main :: fn() {
            // Take address
            x := 42
            p := x.adr

            // Dereference
            value := p.val

            // Modify through pointer
            p.val = 100

            // Double pointer
            pp := p.adr
            value2 := pp.val.val

            // Triple pointer
            ppp := pp.adr
            value3 := ppp.val.val.val

            // Pointer to field
            obj := MyStruct{field: 10}
            field_ptr := obj.field.adr
            field_ptr.val = 20

            // Pointer to array element
            arr: [10]i32
            elem_ptr := arr[5].adr
            elem_ptr.val = 99
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
