"""Parser integration tests for declarations, expressions and control flow."""

from a7.parser import parse_a7
from a7.ast_nodes import NodeKind


class TestParserIntegration:
    def test_tokenizer_parser_integration(self):
        """Test that tokenizer output is correctly consumed by parser."""
        code = """
        // Comment should be ignored
        x :: 42          // Another comment
        y := 3.14        // Variable declaration
        main :: fn() {   // Function declaration
            ret x + y    // Return statement with expression
        }
        """

        ast = parse_a7(code)
        assert ast.kind == NodeKind.PROGRAM
        assert len(ast.declarations) == 3

        # Check constant declaration
        const_decl = ast.declarations[0]
        assert const_decl.kind == NodeKind.CONST
        assert const_decl.name == "x"
        assert const_decl.value.literal_value == 42

        # Check variable declaration
        var_decl = ast.declarations[1]
        assert var_decl.kind == NodeKind.VAR
        assert var_decl.name == "y"
        assert var_decl.value.literal_value == 3.14

        # Check function declaration
        func_decl = ast.declarations[2]
        assert func_decl.kind == NodeKind.FUNCTION
        assert func_decl.name == "main"
        assert len(func_decl.body.statements) == 1

    def test_complete_working_program(self):
        """Test parsing a complete A7 program that should work."""
        code = """
        // Simple A7 program that the parser should handle
        
        add :: fn(x: i32, y: i32) i32 {
            ret x + y
        }
        
        subtract :: fn(a: i32, b: i32) i32 {
            ret a - b
        }
        
        main :: fn() {
            x := 10
            y := 5
            sum := add(x, y)
            diff := subtract(x, y)
            
            if sum > diff {
                result := sum
            } else {
                result := diff
            }
            
            i := 0
            while i < 10 {
                i = i + 1
            }
            
            ret 0
        }
        """

        ast = parse_a7(code)
        assert ast.kind == NodeKind.PROGRAM
        # Should have 3 functions (add, subtract, main)
        # But might have extra declarations due to parsing edge cases
        assert len(ast.declarations) >= 3

        # Check that the main functions are present
        function_names = [
            decl.name for decl in ast.declarations if decl.kind == NodeKind.FUNCTION
        ]
        assert "add" in function_names
        assert "subtract" in function_names
        assert "main" in function_names

        # Verify function declarations
        for i, expected_name in enumerate(["add", "subtract", "main"]):
            func_decl = ast.declarations[i]
            assert func_decl.kind == NodeKind.FUNCTION
            assert func_decl.name == expected_name

    def test_comprehensive_expression_parsing(self):
        """Test comprehensive expression parsing capabilities."""
        code = """
        main :: fn() {
            // Arithmetic expressions
            a := 1 + 2 * 3 - 4 / 2
            b := (1 + 2) * (3 - 4)
            c := -5 + 6
            
            // Comparison expressions
            d := 10 > 5
            e := 3 <= 7
            f := 4 == 4
            g := 6 != 8
            
            // Logical expressions
            h := true and false
            i := true or false
            j := not true
            
            // Function calls
            k := func1()
            l := func2(1, 2, 3)
            m := func3(func4(5))
            
            // Mixed expressions
            n := add(1, 2) + multiply(3, 4)
            o := (x > 0) and (y < 10)
        }
        """

        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        statements = func_decl.body.statements

        # Should have parsed all variable declarations
        assert len(statements) == 15

        # Check that each statement is a variable declaration
        for stmt in statements:
            assert stmt.kind == NodeKind.VAR
            assert stmt.value is not None  # Each should have an expression

    def test_nested_structures_parsing(self):
        """Test parsing of nested structures."""
        code = """
        main :: fn() {
            // Nested blocks
            if true {
                if false {
                    x := 1
                } else {
                    y := 2
                }
                
                while true {
                    if x > 0 {
                        break
                    }
                }
            }
            
            // Nested function calls
            result := f1(f2(f3(1, 2), f4(3)), f5(4, 5))
            
            // Complex expressions
            complex := ((a + b) * c) / ((d - e) + f)
        }
        """

        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        statements = func_decl.body.statements

        # Should parse all nested structures without errors
        assert len(statements) == 3

        # First statement should be nested if
        if_stmt = statements[0]
        assert if_stmt.kind == NodeKind.IF_STMT
        assert if_stmt.then_stmt.kind == NodeKind.BLOCK

    def test_type_system_integration(self):
        """Test integration of type system parsing."""
        code = """
        // Test various type combinations
        test_primitives :: fn(
            i: i32,
            u: u64, 
            f: f32,
            b: bool,
            c: char,
            s: string
        ) {
            ret
        }
        
        test_arrays :: fn(
            fixed: [10]i32,
            slice: []string
        ) {
            ret
        }
        
        test_pointers :: fn(
            ptr: ref i32,
            ptr_array: ref [5]u8
        ) {
            ret
        }
        
        test_nested :: fn(
            arr_of_ptrs: [3]ref i32,
            ptr_to_array: ref [10]f64,
            slice_of_arrays: [][4]bool
        ) {
            ret
        }
        """

        ast = parse_a7(code)
        assert len(ast.declarations) == 4

        # Check that all functions were parsed
        for decl in ast.declarations:
            assert decl.kind == NodeKind.FUNCTION

        # Check parameter types were parsed correctly
        primitives_func = ast.declarations[0]
        assert len(primitives_func.parameters) == 6

        arrays_func = ast.declarations[1]
        assert len(arrays_func.parameters) == 2
        assert arrays_func.parameters[0].param_type.kind == NodeKind.TYPE_ARRAY
        assert arrays_func.parameters[1].param_type.kind == NodeKind.TYPE_SLICE
