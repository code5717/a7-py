"""Regression tests for parser constructs that were once missing."""

from a7.parser import parse_a7
from a7.ast_nodes import NodeKind
from a7.errors import ParseError


class TestMissingStructs:
    """Test struct declarations - BASIC STRUCTS NOW IMPLEMENTED."""

    def test_simple_struct_declaration(self):
        """Test parsing simple struct declarations."""
        code = """
        Person :: struct {
            name: string
            age: u32
        }
        """
        ast = parse_a7(code)
        struct_decl = ast.declarations[0]
        assert struct_decl.kind == NodeKind.STRUCT
        assert struct_decl.name == "Person"
        assert len(struct_decl.fields) == 2

    def test_generic_struct_declaration(self):
        """Test parsing generic struct declarations."""
        code = """
        Pair :: struct {
            first: $T
            second: $U
        }
        """
        ast = parse_a7(code)
        struct_decl = ast.declarations[0]
        assert struct_decl.kind == NodeKind.STRUCT
        assert struct_decl.name == "Pair"
        # No explicit generic declarations needed - generics inferred from field usage
        assert len(struct_decl.fields) == 2
        assert struct_decl.fields[0].field_type.kind == NodeKind.TYPE_GENERIC
        assert struct_decl.fields[0].field_type.name == "T"
        assert struct_decl.fields[1].field_type.kind == NodeKind.TYPE_GENERIC
        assert struct_decl.fields[1].field_type.name == "U"

    def test_struct_initialization(self):
        """Test parsing struct initialization expressions."""
        code = """
        main :: fn() {
            p := Person{name: "John", age: 30}
        }
        """
        ast = parse_a7(code)
        # Should parse struct initialization expression
        func_decl = ast.declarations[0]
        var_decl = func_decl.body.statements[0]
        init_expr = var_decl.value
        assert init_expr.kind == NodeKind.STRUCT_INIT


class TestMissingEnums:
    """Test enum declarations - BASIC ENUMS NOW IMPLEMENTED."""

    def test_simple_enum_declaration(self):
        """Test parsing simple enum declarations."""
        code = """
        Color :: enum {
            Red,
            Green,
            Blue
        }
        """
        ast = parse_a7(code)
        enum_decl = ast.declarations[0]
        assert enum_decl.kind == NodeKind.ENUM
        assert enum_decl.name == "Color"
        assert len(enum_decl.variants) == 3

    def test_enum_with_explicit_values(self):
        """Test parsing enums with explicit values."""
        code = """
        StatusCode :: enum {
            Ok = 200,
            NotFound = 404,
            Error = 500
        }
        """
        ast = parse_a7(code)
        enum_decl = ast.declarations[0]
        assert enum_decl.kind == NodeKind.ENUM
        assert enum_decl.name == "StatusCode"


class TestMissingUnions:
    """Test union declaration parsing behavior."""

    def test_simple_union_declaration(self):
        """Test parsing simple union declarations."""
        code = """
        Number :: union {
            i: i32
            f: f32
        }
        """
        ast = parse_a7(code)
        union_decl = ast.declarations[0]
        assert union_decl.kind == NodeKind.UNION
        assert union_decl.name == "Number"
        assert len(union_decl.fields) == 2

    def test_tagged_union_declaration(self):
        """Test parsing tagged union declarations."""
        code = """
        Result :: union(tag) {
            ok: i32
            err: string
        }
        """
        ast = parse_a7(code)
        union_decl = ast.declarations[0]
        assert union_decl.kind == NodeKind.UNION
        assert union_decl.name == "Result"
        assert union_decl.is_tagged is True


class TestMissingMatchStatements:
    """Test match statements - BASIC MATCH NOW IMPLEMENTED."""

    def test_simple_match_statement(self):
        """Test parsing simple match statements."""
        code = """
        main :: fn() {
            value :: 1
            match value {
                case 1: {
                    print("One")
                }
                case 2: {
                    print("Two")
                }
                else: {
                    print("Other")
                }
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[1]
        assert match_stmt.kind == NodeKind.MATCH
        assert len(match_stmt.cases) == 2
        assert match_stmt.else_case is not None

    def test_match_multiple_patterns(self):
        """Test parsing match with multiple patterns."""
        code = """
        main :: fn() {
            value :: 3
            match value {
                case 1, 2, 3: {
                    print("Small")
                }
                case 4..10: {
                    print("Medium")
                }
            }
        }
        """
        ast = parse_a7(code)
        # Should parse match with multiple patterns and ranges

    def test_match_wildcard_pattern(self):
        """Test parsing wildcard pattern '_' in match statements."""
        code = """
        main :: fn() {
            value :: 3
            match value {
                case _: {
                    print("Any")
                }
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        match_stmt = func_decl.body.statements[1]
        case_branch = match_stmt.cases[0]
        assert case_branch.patterns[0].kind == NodeKind.PATTERN_WILDCARD


class TestMissingDeferStatements:
    """Test defer statement parsing behavior."""

    def test_defer_statement(self):
        """Test parsing defer statements."""
        code = """
        main :: fn() {
            ptr := new i32
            defer del ptr
            ptr.val = 42
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        defer_stmt = func_decl.body.statements[1]
        assert defer_stmt.kind == NodeKind.DEFER
        assert defer_stmt.statement is not None


class TestMissingForLoopVariants:
    """Test complex for loop variants - NOW IMPLEMENTED."""

    def test_c_style_for_loop(self):
        """Test parsing C-style for loops."""
        code = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                print("Loop")
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        for_stmt = func_decl.body.statements[0]
        assert for_stmt.kind == NodeKind.FOR
        assert for_stmt.init is not None
        assert for_stmt.condition is not None
        assert for_stmt.update is not None

    def test_range_based_for_loop(self):
        """Test parsing range-based for loops."""
        code = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            for value in arr {
                print("Value")
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        for_stmt = func_decl.body.statements[1]
        assert for_stmt.kind == NodeKind.FOR_IN
        assert for_stmt.iterator is not None
        assert for_stmt.iterable is not None

    def test_for_loop_with_index(self):
        """Test parsing for loops with index."""
        code = """
        main :: fn() {
            arr: [3]i32 = [1, 2, 3]
            for i, value in arr {
                print("Index and value")
            }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        for_stmt = func_decl.body.statements[1]
        assert for_stmt.kind == NodeKind.FOR_IN_INDEXED
        assert for_stmt.index_var is not None
        assert for_stmt.iterator is not None


class TestMissingExpressionConstructs:
    """Regression tests for expression constructs."""

    def test_array_initialization(self):
        """Test parsing array initialization expressions."""
        code = """
        main :: fn() {
            arr := [1, 2, 3, 4, 5]
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        var_decl = func_decl.body.statements[0]
        array_init = var_decl.value
        assert array_init.kind == NodeKind.ARRAY_INIT
        assert len(array_init.elements) == 5

    def test_cast_expressions(self):
        """Test parsing cast expressions."""
        code = """
        main :: fn() {
            x := cast(i32, 3.14)
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        var_decl = func_decl.body.statements[0]
        cast_expr = var_decl.value
        assert cast_expr.kind == NodeKind.CAST

    def test_nested_field_access(self):
        """Test parsing nested field access."""
        code = """
        main :: fn() {
            x := employee.person.name
        }
        """
        ast = parse_a7(code)
        # Should parse nested field access correctly


class TestMissingTypeAnnotations:
    """Regression tests for explicit type annotations."""

    def test_variable_with_explicit_type(self):
        """Test parsing variables with explicit type annotations."""
        code = """
        main :: fn() {
            x: i32 = 42
            y: string = "hello"
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        var_decl1 = func_decl.body.statements[0]
        assert var_decl1.explicit_type is not None
        assert var_decl1.explicit_type.type_name == "i32"


class TestMissingGenericFunctions:
    """Regression tests for generic function constructs."""

    def test_generic_function_declaration(self):
        """Test parsing generic function declarations with new syntax."""
        code = """
        swap :: fn(a: ref $T, b: ref $T) {
            temp := a.val
            a.val = b.val
            b.val = temp
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        assert func_decl.name == "swap"
        # With new syntax, generics are not declared as parameters
        assert len(func_decl.parameters) == 2
        assert func_decl.parameters[0].param_type.kind == NodeKind.TYPE_POINTER
        assert func_decl.parameters[0].param_type.target_type.kind == NodeKind.TYPE_GENERIC
        assert func_decl.parameters[0].param_type.target_type.name == "T"

    def test_generic_function_with_return_type(self):
        """Test parsing generic functions with return type."""
        code = """
        abs :: fn(x: $T) $T {
            ret if x < 0 { -x } else { x }
        }
        """
        ast = parse_a7(code)
        func_decl = ast.declarations[0]
        # Generics used directly without declaration
        assert func_decl.parameters[0].param_type.kind == NodeKind.TYPE_GENERIC
        assert func_decl.parameters[0].param_type.name == "T"
        assert func_decl.return_type.kind == NodeKind.TYPE_GENERIC
        assert func_decl.return_type.name == "T"


class TestMissingNamedImports:
    """Regression tests for named import constructs."""

    def test_named_import(self):
        """Test parsing named import statements."""
        code = 'io :: import "std/io"'
        ast = parse_a7(code)
        import_decl = ast.declarations[0]
        assert import_decl.kind == NodeKind.IMPORT
        assert import_decl.alias == "io"
        assert import_decl.module_path == "std/io"


class TestCurrentlyWorkingFeatures:
    """Test cases that demonstrate implemented A7 language features."""

    def test_struct_keyword_works(self):
        """Demonstrate that struct keyword is now recognized."""
        ast = parse_a7("Person :: struct { name: string }")
        assert ast.declarations[0].kind == NodeKind.STRUCT
        assert ast.declarations[0].name == "Person"

    def test_enum_keyword_works(self):
        """Demonstrate that enum keyword is now recognized."""
        ast = parse_a7("Color :: enum { Red, Green, Blue }")
        assert ast.declarations[0].kind == NodeKind.ENUM
        assert ast.declarations[0].name == "Color"

    def test_union_keyword_works(self):
        """Demonstrate that union keyword is now recognized."""
        ast = parse_a7("Data :: union { i: i32, f: f32 }")
        assert ast.declarations[0].kind == NodeKind.UNION
        assert ast.declarations[0].name == "Data"

    def test_match_keyword_works(self):
        """Demonstrate that match keyword is now recognized."""
        code = """
        main :: fn() {
            match 1 {
                case 1: { print("one") }
            }
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        match_stmt = func.body.statements[0]
        assert match_stmt.kind == NodeKind.MATCH

    def test_defer_keyword_works(self):
        """Demonstrate that defer keyword is now recognized."""
        code = """
        main :: fn() {
            defer print("cleanup")
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        defer_stmt = func.body.statements[0]
        assert defer_stmt.kind == NodeKind.DEFER

    def test_simple_for_loop_works(self):
        """Demonstrate that simple for loops work."""
        code = """
        main :: fn() {
            for {
                print("loop")
            }
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        for_stmt = func.body.statements[0]
        assert for_stmt.kind == NodeKind.FOR
        assert for_stmt.body is not None

    def test_array_literal_works(self):
        """Demonstrate that array literals are now implemented."""
        code = """
        main :: fn() {
            arr := [1, 2, 3]
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        assert var_decl.kind == NodeKind.VAR
        assert var_decl.name == "arr"

    def test_struct_literal_works(self):
        """Demonstrate that struct literals are now implemented."""
        code = """
        main :: fn() {
            p := Person{name: "John", age: 30}
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        assert var_decl.kind == NodeKind.VAR
        assert var_decl.name == "p"

    def test_explicit_type_annotation_works(self):
        """Demonstrate that explicit type annotations are now implemented."""
        code = """
        main :: fn() {
            x: i32 = 42
        }
        """
        ast = parse_a7(code)
        func = ast.declarations[0]
        var_decl = func.body.statements[0]
        assert var_decl.kind == NodeKind.VAR
        assert var_decl.name == "x"
        assert hasattr(var_decl, "explicit_type") and var_decl.explicit_type is not None

    def test_named_import_now_works(self):
        """Demonstrate that named imports now work."""
        ast = parse_a7('io :: import "std/io"')
        assert ast is not None
