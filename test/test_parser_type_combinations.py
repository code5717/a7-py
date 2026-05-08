"""
Comprehensive tests for type combinations and complex scenarios.

This module tests the interaction between different type features:
- Function types
- Inline struct types
- Arrays, slices, pointers
- Generic types
- Complex nested combinations

Tests ensure parser robustness with extreme scenarios.
"""

import pytest
from a7.tokens import Tokenizer
from a7.parser import Parser
from a7.errors import ParseError


class TestFunctionAndStructCombinations:
    """Test combinations of function types and inline struct types."""

    def test_struct_containing_function_pointers(self):
        """Test struct with multiple function pointer fields."""
        code = """
Handler :: struct {
    init: fn() void
    process: fn(i32) bool
    cleanup: fn() void
    error_handler: fn(string) void
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_returning_inline_struct_with_functions(self):
        """Test function returning inline struct containing function pointers."""
        code = """
get_callbacks :: fn() struct {
    on_init: fn() void
    on_update: fn(f64) void
    on_cleanup: fn() void
} {
    ret cast(struct {
        on_init: fn() void
        on_update: fn(f64) void
        on_cleanup: fn() void
    }, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_taking_inline_struct_with_functions(self):
        """Test function parameter with inline struct containing functions."""
        code = """
register_handlers :: fn(callbacks: struct {
    on_success: fn(i32) void
    on_error: fn(string) void
}) void {
    ret
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_nested_inline_structs_with_functions(self):
        """Test deeply nested inline structs with function types."""
        code = """main :: fn() {
    system: struct {
        name: string
        handlers: struct {
            init: fn() bool
            update: fn(f64) void
            render: fn() void
        }
        config: struct {
            validator: fn(string) bool
            parser: fn(string) i32
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_array_of_inline_structs_with_functions(self):
        """Test array of inline structs containing function pointers."""
        code = """main :: fn() {
    handlers: [10]struct {
        name: string
        callback: fn(i32) bool
        priority: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_returning_function_with_inline_struct_param(self):
        """Test higher-order function with inline struct."""
        code = """
make_handler :: fn() fn(struct { x: i32, y: i32 }) void {
    ret cast(fn(struct { x: i32, y: i32 }) void, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestPointerTypeCombinations:
    """Test pointer combinations with new type features."""

    def test_pointer_to_function_type(self):
        """Test ref fn() patterns."""
        code = """main :: fn() {
    callback_ptr: ref fn(i32) bool = nil
    handler_ptr: ref fn() void = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_returning_pointer_to_inline_struct(self):
        """Test function returning pointer to inline struct."""
        code = """
create_data :: fn() ref struct {
    id: u64
    values: [256]u8
} {
    ret nil
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_multiple_pointer_levels(self):
        """Test multiple levels of pointers in inline struct."""
        code = """main :: fn() {
    data: struct {
        value: i32
        ptr1: ref struct {
            id: i32
            ptr2: ref struct {
                data: string
            }
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_array_of_pointers_to_inline_structs(self):
        """Test arrays of pointers to inline structs."""
        code = """main :: fn() {
    nodes: [100]ref struct {
        id: i32
        data: string
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_pointer_to_array_of_inline_structs(self):
        """Test pointer to array of inline structs."""
        code = """main :: fn() {
    grid_ptr: ref [10][10]struct {
        x: i32
        y: i32
        occupied: bool
    } = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_pointer_returning_pointer_to_struct(self):
        """Test function pointer that returns pointer to inline struct."""
        code = """main :: fn() {
    factory: fn() ref struct {
        id: i32
        active: bool
    } = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestArrayAndSliceCombinations:
    """Test array and slice combinations with new types."""

    def test_multi_dimensional_array_of_function_pointers(self):
        """Test 2D array of function pointers."""
        code = """main :: fn() {
    callbacks: [5][5]fn(i32) bool
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_slice_of_inline_structs_with_slices(self):
        """Test slice containing inline structs with slice fields."""
        code = """main :: fn() {
    data: []struct {
        name: string
        values: []i32
        tags: []string
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_array_of_arrays_of_inline_structs(self):
        """Test 3D array of inline structs."""
        code = """main :: fn() {
    grid: [10][10][10]struct {
        value: i32
        active: bool
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_array_and_function_fields(self):
        """Test inline struct with both array and function fields."""
        code = """main :: fn() {
    processor: struct {
        data: [1024]u8
        process: fn([]u8) bool
        results: [64]i32
        validator: fn(i32) bool
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_taking_slice_of_inline_structs(self):
        """Test function parameter with slice of inline structs."""
        code = """
process_items :: fn(items: []struct {
    id: i32
    name: string
    active: bool
}) i32 {
    ret 0
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestGenericTypeCombinations:
    """Test generic type combinations with new features."""

    def test_inline_struct_with_generic_fields(self):
        """Test inline struct containing generic type fields."""
        code = """main :: fn() {
    container: struct {
        data: $T
        size: i32
        transform: fn($T) $T
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_with_generic_inline_struct_return(self):
        """Test function returning inline struct with generics."""
        code = """
make_pair :: fn() struct {
    first: $T
    second: $U
} {
    ret cast(struct {
        first: $T
        second: $U
    }, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_generic_function_pointer_in_struct(self):
        """Test inline struct with generic function pointer."""
        code = """main :: fn() {
    handler: struct {
        process: fn($T) $U
        data: $T
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestComplexNestedStructures:
    """Test extremely complex nested type structures."""

    def test_deeply_nested_all_features(self):
        """Test all type features nested together."""
        code = """main :: fn() {
    complex: struct {
        callbacks: [10]fn(struct {
            id: i32
            data: []struct {
                key: string
                handler: fn(i32) bool
            }
        }) bool
        state: ref struct {
            active: bool
            children: []ref struct {
                id: i32
                callback: fn() void
            }
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_maze(self):
        """Test complex function type nesting."""
        code = """main :: fn() {
    orchestrator: fn(
        fn(
            fn(i32) bool
        ) fn(string) void
    ) fn(
        fn() i32
    ) bool = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_struct_maze(self):
        """Test complex inline struct nesting."""
        code = """main :: fn() {
    data: struct {
        level1: struct {
            level2: struct {
                level3: struct {
                    level4: struct {
                        value: i32
                    }
                }
            }
        }
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_mixed_collection_types(self):
        """Test arrays, slices, and pointers all mixed."""
        code = """main :: fn() {
    mixed: [5][]ref [10]ref struct {
        arrays: [3][]ref i32
        pointers: ref [10]ref bool
        nested: []ref []i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestFunctionDeclarationVariations:
    """Test various function declaration patterns with new types."""

    def test_function_with_inline_struct_params_and_return(self):
        """Test function with inline structs in params and return."""
        code = """
transform :: fn(
    input: struct { x: i32, y: i32 },
    config: struct { scale: f64, offset: i32 }
) struct { x: i32, y: i32 } {
    ret cast(struct { x: i32, y: i32 }, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_with_multiple_function_pointer_params(self):
        """Test function taking multiple function pointers."""
        code = """
combine :: fn(
    f1: fn(i32) i32,
    f2: fn(i32) i32,
    f3: fn(i32) i32
) fn(i32) i32 {
    ret cast(fn(i32) i32, nil)
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_with_array_of_inline_struct_param(self):
        """Test function parameter with fixed-size array of inline structs."""
        code = """
process_batch :: fn(items: [100]struct {
    id: i32
    active: bool
    priority: i32
}) i32 {
    ret 0
}
"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestTypeRobustness:
    """Test parser robustness with extreme type scenarios."""

    def test_empty_inline_struct(self):
        """Test inline struct with no fields."""
        code = """main :: fn() {
    empty: struct {
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_with_many_params(self):
        """Test function type with many parameters."""
        code = """main :: fn() {
    processor: fn(
        i32, i32, i32, i32, i32,
        bool, bool, bool,
        string, string, string,
        f64, f64, f64
    ) void = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_with_many_fields(self):
        """Test inline struct with many fields."""
        code = """main :: fn() {
    data: struct {
        f1: i32
        f2: i32
        f3: i32
        f4: bool
        f5: bool
        f6: string
        f7: f64
        f8: f64
        f9: []i32
        f10: []bool
        f11: fn(i32) bool
        f12: fn() void
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_large_array_sizes(self):
        """Test arrays with large size expressions."""
        code = """main :: fn() {
    huge: [1000000]i32
    grid: [1000][1000]struct {
        value: i32
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None


class TestRegressionScenarios:
    """Regression tests for previously found issues."""

    def test_function_type_no_return_type(self):
        """Test function type without explicit return (void)."""
        code = """main :: fn() {
    callback: fn(i32)
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_trailing_commas_in_inline_struct(self):
        """Test inline struct with trailing comma."""
        code = """main :: fn() {
    data: struct {
        x: i32,
        y: i32,
    }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_inline_struct_single_line(self):
        """Test inline struct on single line."""
        code = """main :: fn() {
    point: struct { x: i32, y: i32, z: i32 }
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None

    def test_function_type_with_trailing_comma(self):
        """Test function type with trailing comma in params."""
        code = """main :: fn() {
    callback: fn(i32, bool,) void = nil
}"""
        lexer = Tokenizer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, code)
        ast = parser.parse()
        assert ast is not None
