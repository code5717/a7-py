"""
Creative and unique parser test cases.

Tests unusual but valid syntax patterns, creative combinations,
and interesting edge cases not covered elsewhere.
"""

import pytest
from src.parser import parse_a7
from src.ast_nodes import NodeKind


class TestCreativePatterns:
    """Creative syntax patterns and unusual combinations."""

    def test_chained_property_access(self):
        """Test deeply chained property-based pointer syntax."""
        code = """
        main :: fn() {
            a := 42
            p1 := a.adr
            p2 := p1.adr
            p3 := p2.adr
            p4 := p3.adr

            // Quad indirection
            value := p4.val.val.val.val
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_match_expression_in_various_contexts(self):
        """Test match expressions used in creative ways."""
        code = """
        main :: fn() {
            // Match in array index
            arr: [10]i32
            x := arr[match day { case 1: 0  case 2: 1  else: 2 }]

            // Match in function argument
            print(match status { case 0: "ok"  case 1: "error"  else: "unknown" })

            // Match in return
            result := match value {
                case 1: 100
                case 2: 200
                else: 300
            }

            // Nested match
            final := match a {
                case 1: match b {
                    case 1: 11
                    case 2: 12
                    else: 10
                }
                else: 0
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_anonymous_struct_with_complex_fields(self):
        """Test inline structs with function pointers and nested types."""
        code = """
        main :: fn() {
            // Complex inline struct
            handler: struct {
                id: u64
                callback: fn(ref struct { x: i32, y: i32 }) bool
                state: ref [100]u8
                nested: struct {
                    data: [5][5]f64
                    transform: fn(f64) f64
                }
            }

            // Array of complex inline structs
            handlers: [3]struct {
                name: string
                action: fn()
                priority: i32
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_deeply_nested_generic_types(self):
        """Test complex nested generic instantiations."""
        code = """
        main :: fn() {
            // Nested generics
            data1: List(Map(string, Vec(i32)))
            data2: Tree(Pair(Option(i32), Result(string)))
            data3: Graph(Node(Edge(Weight(f64))))

            // Generic with array types
            buffer: Ring([256]u8)
            matrix: Grid([10][10]f32)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_operator_precedence_extremes(self):
        """Test complex operator precedence scenarios."""
        code = """
        main :: fn() {
            // Multiple precedence levels
            a := 1 + 2 * 3 - 4 / 5 % 6
            b := x << 2 + y >> 1
            c := p and q or r and s
            d := !a and !b or !c

            // Bitwise with arithmetic
            e := (x & 0xFF) << 8 | (y & 0xFF)
            f := ~(a | b) & (c ^ d)

            // Mixed with comparisons
            g := a + b < c * d and e - f >= g / h
            h := (x == y or x > y) and (z != w or z <= w)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_unusual_array_patterns(self):
        """Test creative array usage patterns."""
        code = """
        main :: fn() {
            // Multidimensional with mixed access
            matrix: [5][5][5]i32
            slice := matrix[i][j]
            element := matrix[x][y][z]

            // Array of function pointers
            operations: [10]fn(i32, i32) i32
            result := operations[op_index](a, b)

            // Array of pointers to arrays
            buffers: [8]ref [256]u8

            // Complex array initialization context
            data: [3]struct { id: i32, values: [5]f32 }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_defer_in_complex_contexts(self):
        """Test defer statements in various scopes."""
        code = """
        main :: fn() {
            defer cleanup()

            if condition {
                defer local_cleanup()
                allocate_resource()
            }

            for i := 0; i < 10; i += 1 {
                defer release(i)
                acquire(i)
            }

            {
                defer nested_cleanup()
                {
                    defer deeply_nested_cleanup()
                    do_work()
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_creative_function_signatures(self):
        """Test unusual but valid function signatures."""
        code = """
        // Function returning function pointer
        get_handler :: fn() fn(i32) bool {
            ret default_handler
        }

        // Function taking function returning function
        meta :: fn(factory: fn() fn(i32) i32) i32 {
            handler := factory()
            ret handler(42)
        }

        // Generic function with complex constraints
        process :: fn(data: $T, compare: fn($T, $T) bool, transform: fn($T) $T) $T {
            ret transform(data)
        }

        // Function with inline struct parameters
        draw :: fn(rect: struct { x: i32, y: i32, w: i32, h: i32 }, style: struct { color: u32, border: i32 }) {
            do_drawing()
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestRealWorldPatterns:
    """Tests based on real-world coding patterns."""

    def test_state_machine_pattern(self):
        """Test typical state machine implementation."""
        code = """
        State :: enum {
            IDLE
            RUNNING
            PAUSED
            STOPPED
        }

        StateMachine :: struct {
            current: State
            on_enter: fn(State)
            on_exit: fn(State)
            handlers: [4]fn()
        }

        transition :: fn(sm: ref StateMachine, next: State) {
            sm.val.on_exit(sm.val.current)
            sm.val.current = next
            sm.val.on_enter(next)
        }

        main :: fn() {
            machine := StateMachine{current: State.IDLE}
            transition(machine.adr, State.RUNNING)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_callback_registry_pattern(self):
        """Test event/callback registry pattern."""
        code = """
        EventType :: enum {
            CLICK
            HOVER
            DRAG
            DROP
        }

        Callback :: struct {
            handler: fn(i32)
            priority: i32
            enabled: bool
        }

        Registry :: struct {
            callbacks: [100]Callback
            count: i32
        }

        register :: fn(reg: ref Registry, handler: fn(i32), prio: i32) {
            idx := reg.val.count
            reg.val.callbacks[idx].handler = handler
            reg.val.callbacks[idx].priority = prio
            reg.val.callbacks[idx].enabled = true
            reg.val.count += 1
        }

        dispatch :: fn(reg: ref Registry, event_data: i32) {
            for i := 0; i < reg.val.count; i += 1 {
                if reg.val.callbacks[i].enabled {
                    reg.val.callbacks[i].handler(event_data)
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_memory_pool_pattern(self):
        """Test memory pool/arena allocator pattern."""
        code = """
        Pool :: struct {
            buffer: [4096]u8
            used: u64
            alignment: u64
        }

        pool_init :: fn() Pool {
            ret Pool{used: 0, alignment: 8}
        }

        pool_alloc :: fn(pool: ref Pool, size: u64) ref u8 {
            // Align to boundary
            aligned := (pool.val.used + pool.val.alignment - 1) & ~(pool.val.alignment - 1)

            if aligned + size > 4096 {
                ret nil
            }

            ptr := pool.val.buffer[aligned].adr
            pool.val.used = aligned + size
            ret ptr
        }

        pool_reset :: fn(pool: ref Pool) {
            pool.val.used = 0
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_iterator_pattern(self):
        """Test iterator/generator pattern."""
        code = """
        Range :: struct {
            current: i32
            end: i32
            step: i32
        }

        range :: fn(start: i32, end: i32, step: i32) Range {
            ret Range{current: start, end: end, step: step}
        }

        next :: fn(r: ref Range) struct { value: i32, done: bool } {
            if r.val.current >= r.val.end {
                ret struct { value: i32, done: bool } { value: 0, done: true }
            }

            val := r.val.current
            r.val.current += r.val.step
            ret struct { value: i32, done: bool } { value: val, done: false }
        }

        main :: fn() {
            iter := range(0, 10, 2)
            iter_ref := iter.adr

            for {
                item := next(iter_ref)
                if item.done {
                    break
                }
                process(item.value)
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_builder_pattern(self):
        """Test builder/fluent interface pattern."""
        code = """
        Config :: struct {
            width: i32
            height: i32
            title: string
            fullscreen: bool
            vsync: bool
        }

        Builder :: struct {
            config: Config
        }

        new_builder :: fn() Builder {
            ret Builder{config: Config{width: 800, height: 600, fullscreen: false, vsync: true}}
        }

        with_size :: fn(b: ref Builder, w: i32, h: i32) ref Builder {
            b.val.config.width = w
            b.val.config.height = h
            ret b
        }

        with_title :: fn(b: ref Builder, t: string) ref Builder {
            b.val.config.title = t
            ret b
        }

        with_fullscreen :: fn(b: ref Builder) ref Builder {
            b.val.config.fullscreen = true
            ret b
        }

        build :: fn(b: ref Builder) Config {
            ret b.val.config
        }

        main :: fn() {
            builder := new_builder()
            b_ref := builder.adr

            config := build(with_fullscreen(with_title(with_size(b_ref, 1920, 1080), "Game")))
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestEdgeCaseExpressions:
    """Edge cases in expression parsing."""

    def test_complex_cast_expressions(self):
        """Test casts in various contexts."""
        code = """
        main :: fn() {
            // Cast in arithmetic
            a := cast(f64, x) + cast(f64, y)

            // Cast of cast
            b := cast(i64, cast(i32, byte_val))

            // Cast in array index
            arr: [100]i32
            idx := arr[cast(i32, float_index)]

            // Cast with pointer
            ptr := cast(ref i32, buffer.adr)

            // Cast in function argument
            result := process(cast(u64, size), cast(ref u8, data))

            // Cast in comparison
            if cast(i32, a) > cast(i32, b) {
                do_thing()
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_nested_struct_literals(self):
        """Test deeply nested struct literal initialization."""
        code = """
        main :: fn() {
            // Nested initialization
            config := Config{
                window: Window{
                    size: Size{width: 800, height: 600},
                    position: Point{x: 100, y: 100},
                    style: Style{
                        border: Border{width: 1, color: 0xFF000000},
                        background: 0xFFFFFFFF
                    }
                },
                audio: Audio{
                    sample_rate: 44100,
                    channels: 2
                }
            }

            // Inline nested structs
            point := struct {
                coords: struct { x: f64, y: f64 },
                metadata: struct { id: u32, label: string }
            } {
                coords: struct { x: f64, y: f64 } { x: 1.0, y: 2.0 },
                metadata: struct { id: u32, label: string } { id: 1, label: "origin" }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_complex_for_loop_variations(self):
        """Test various for loop patterns."""
        code = """
        main :: fn() {
            // Multiple operations in increment
            for i := 0; i < n; i += 1 {
                work(i)
            }

            // Complex condition
            for x := 0; x * x < 1000 and x < 100; x += 1 {
                process(x)
            }

            // Multiple variables (sequential declarations)
            for i := 0; i < 10; i += 1 {
                for j := 0; j < 10; j += 1 {
                    matrix[i][j] = i * j
                }
            }

            // Range iteration with index
            arr: [10]i32
            for i, val in arr {
                result[i] = val * 2
            }

            // Nested range iterations
            matrix: [5][5]i32
            for row in matrix {
                for val in row {
                    sum += val
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_unusual_member_access_chains(self):
        """Test complex member access patterns."""
        code = """
        main :: fn() {
            // Long access chain
            value := obj.field1.field2.field3.field4.field5

            // Mixed array and member access
            data := obj.array[i].field.nested[j].value

            // Pointer access chains
            ptr_val := ptr.val.field.adr.val.nested

            // Array of structs with pointers
            items: [10]Item
            ref_to_field := items[index].data.adr

            // Function call result access
            result := get_object().field.method().data[0]
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_pathological_parenthesization(self):
        """Test extreme but valid parenthesization."""
        code = """
        main :: fn() {
            // Excessive but valid parentheses
            a := (((1 + 2)))
            b := ((((x)))) + ((((y))))
            c := (((((a + b) * c) - d) / e) % f)

            // Parentheses with operators
            d := ((a and b) or (c and d))
            e := ((!a) and (!b)) or ((!c) and (!d))

            // In function calls
            result := func(((((arg1)))), ((arg2)))

            // In array access
            value := arr[(((index)))]
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestGenericEdgeCases:
    """Creative tests for generic type system."""

    def test_generic_with_array_types(self):
        """Test generics instantiated with array types."""
        code = """
        // Generic with fixed array
        process :: fn(data: $T) $T {
            ret data
        }

        main :: fn() {
            arr: [5]i32
            result1 := process([5]i32, arr)

            // Multidimensional
            matrix: [3][3]f64
            result2 := process([3][3]f64, matrix)

            // Array of structs
            items: [10]Item
            result3 := process([10]Item, items)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_generic_with_function_types(self):
        """Test generics with function pointer types."""
        code = """
        apply :: fn(f: $F, x: $T) $T {
            ret f(x)
        }

        main :: fn() {
            // Generic with function type
            callback: fn(i32) i32
            result := apply(fn(i32) i32, i32, callback, 42)

            // Complex function signature
            handler: fn(ref u8, u64) bool
            success := apply(fn(ref u8, u64) bool, bool, handler, true)
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_generic_struct_with_complex_fields(self):
        """Test generic structs with unusual field types."""
        code = """
        // Generic with function field
        Handler($T) :: struct {
            data: $T
            process: fn($T) $T
            compare: fn($T, $T) bool
        }

        // Generic with array field
        Buffer($T, $N) :: struct {
            data: [$N]$T
            size: i32
        }

        // Generic with nested generics
        Nested($T) :: struct {
            inner: Option($T)
            transform: fn($T) Result($T)
        }

        main :: fn() {
            h := Handler(i32){data: 42}
            b := Buffer(f64, 100){size: 0}
            n := Nested(string){}
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestStringAndLiteralEdgeCases:
    """Edge cases for string and literal parsing."""

    def test_string_with_all_escapes(self):
        """Test strings with various escape sequences."""
        code = r"""
        main :: fn() {
            // Standard escapes
            s1 := "line1\nline2\ttab\rcarriage\0null"

            // Quotes
            s2 := "say \"hello\" to 'world'"

            // Backslash
            s3 := "path\\to\\file"

            // Hex escapes
            s4 := "\x41\x42\x43"  // ABC
            s5 := "\x00\xFF\x7F"

            // Mixed
            s6 := "start\n\ttab\x20space\x0Anewline\"quote"
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_numeric_literals_variety(self):
        """Test various numeric literal formats."""
        code = """
        main :: fn() {
            // Integers
            a := 0
            b := 123456789
            c := 1_000_000

            // Floats
            f1 := 0.0
            f2 := 3.14159
            f3 := 1.0
            f4 := 0.123456789
            f5 := 999.999

            // Different bases
            hex := 0xDEADBEEF
            hex2 := 0xFF
            hex3 := 0x0

            // In expressions
            result := 0xFF + 255 - 0x100
            ratio := 3.14159 / 2.0
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_char_literals(self):
        """Test character literal edge cases."""
        code = r"""
        main :: fn() {
            // Regular chars
            a := 'a'
            z := 'z'
            zero := '0'
            nine := '9'

            // Special chars
            space := ' '
            newline := '\n'
            tab := '\t'
            quote := '\''
            backslash := '\\'

            // Hex escape
            null_char := '\x00'
            bell := '\x07'
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestControlFlowCreativity:
    """Creative control flow patterns."""

    def test_nested_match_in_loops(self):
        """Test match expressions nested in loops."""
        code = """
        main :: fn() {
            for i := 0; i < 10; i += 1 {
                action := match i {
                    case 0, 1: "start"
                    case 8, 9: "end"
                    else: "middle"
                }

                for j := 0; j < 5; j += 1 {
                    value := match action {
                        case "start": i * 10
                        case "end": i * 20
                        else: i * j
                    }
                    process(value)
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_break_continue_in_nested_loops(self):
        """Test break/continue in complex nesting."""
        code = """
        main :: fn() {
            @outer for i := 0; i < 10; i += 1 {
                for j := 0; j < 10; j += 1 {
                    if i == j {
                        continue
                    }

                    if i + j > 15 {
                        break
                    }

                    for k := 0; k < 5; k += 1 {
                        if k > i {
                            break
                        }
                        work(i, j, k)
                    }
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_if_else_chains(self):
        """Test long if-else if-else chains."""
        code = """
        main :: fn() {
            if score >= 90 {
                grade := 'A'
            } else if score >= 80 {
                grade := 'B'
            } else if score >= 70 {
                grade := 'C'
            } else if score >= 60 {
                grade := 'D'
            } else {
                grade := 'F'
            }

            // Nested
            if x > 0 {
                if y > 0 {
                    quadrant := 1
                } else {
                    quadrant := 4
                }
            } else {
                if y > 0 {
                    quadrant := 2
                } else {
                    quadrant := 3
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_while_with_complex_conditions(self):
        """Test while loops with elaborate conditions."""
        code = """
        main :: fn() {
            // Complex boolean
            while running and !error and (count < max or force) {
                do_work()
                count += 1
            }

            // With break/continue
            while true {
                input := get_input()

                if input == 0 {
                    break
                }

                if input < 0 {
                    continue
                }

                process(input)
            }

            // Nested
            while outer_condition {
                while inner_condition {
                    if should_exit {
                        break
                    }
                    work()
                }
                update()
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


class TestMemoryAndPointerPatterns:
    """Creative memory management and pointer patterns."""

    def test_complex_new_del_patterns(self):
        """Test new/del in various patterns."""
        code = """
        main :: fn() {
            // Simple allocation
            ptr := new(i32)
            ptr.val = 42
            del ptr

            // Array allocation
            arr := new([100]i32)
            arr.val[0] = 1
            del arr

            // Struct allocation
            obj := new(MyStruct)
            obj.val.field = 123
            del obj

            // Multiple allocations
            p1 := new(i32)
            p2 := new(i32)
            p3 := new(i32)

            defer {
                del p3
                del p2
                del p1
            }

            // In loop
            for i := 0; i < 10; i += 1 {
                temp := new(Buffer)
                use(temp)
                del temp
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_pointer_arithmetic_patterns(self):
        """Test pointer access patterns."""
        code = """
        main :: fn() {
            // Multiple indirection
            x := 42
            p1 := x.adr
            p2 := p1.adr
            p3 := p2.adr

            // Access through multiple levels
            value := p3.val.val.val

            // Modify through pointer
            p1.val = 100
            p2.val.val = 200
            p3.val.val.val = 300

            // Pointer to struct field
            obj := MyStruct{field: 10}
            field_ptr := obj.field.adr
            field_ptr.val = 20

            // Array element pointers
            arr: [10]i32
            elem_ptr := arr[5].adr
            elem_ptr.val = 99
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM

    def test_defer_with_allocations(self):
        """Test defer for resource management."""
        code = """
        process :: fn() {
            buffer := new([4096]u8)
            defer del buffer

            file := open_file("data.txt")
            defer close_file(file)

            lock := acquire_lock()
            defer release_lock(lock)

            // Multiple resources in nested scope
            {
                resource1 := allocate()
                defer free(resource1)

                {
                    resource2 := allocate()
                    defer free(resource2)

                    work(resource1, resource2)
                }
            }
        }
        """
        # Parse code
        # Parse code
        result = parse_a7(code)
        assert result.kind == NodeKind.PROGRAM


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
