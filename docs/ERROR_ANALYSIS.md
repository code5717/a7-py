# A7 Compiler Error Analysis

> Historical snapshot.
>
> This report records an older compiler state and is kept only as debugging
> history. It does not describe the current release status. For current example
> verification, run `uv run python scripts/verify_examples_e2e.py`,
> `uv run python scripts/build_examples.py --profile release --backend zig --clean`,
> or `./run_all_tests.sh`.
> Current gaps are tracked in `MISSING_FEATURES.md` and `TODO.md`.

Analysis of semantic/type errors across the historical 36-example suite that
existed when this report was written.

## Summary Statistics

- **Total files**: 36
- **Files without errors**: 5 (14%)
- **Files with errors**: 31 (86%)
- **Total unique error types**: ~30

## Files Without Errors ✅

1. `000_empty.a7` - Empty program
2. `003_comments.a7` - Comments only
3. `008_switch.a7` - Match statement
4. `015_types.a7` - Type definitions
5. `023_inline_structs.a7` - Inline struct types

## Error Categories

### 1. Module/Import System (HIGHEST PRIORITY)
**Impact**: 29/31 files with errors (94%)

**Pattern**: Missing `io` module causes cascading errors
```
error: Undefined type (Identifier 'io')
error: Cannot access field on non-struct type (Cannot access field 'println' on undefined identifier 'io')
error: Type is not callable (Cannot call 'io.println' (undefined identifier))
```

**Affected examples**: Nearly every example file that uses I/O

**Root cause**: No module resolution system implemented
- Standard library modules (`io`, etc.) not available
- Import statements parsed but not resolved
- Module-qualified access (`io.println`) treated as field access

**Fix needed**: Implement module resolution system
- Standard library modules (io, math, etc.)
- Import statement processing
- Module-qualified name lookup
- Consider built-in symbols vs. imported symbols

### 2. Symbol Resolution (HIGH PRIORITY)
**Impact**: All files with expressions

**Pattern**: Variables and parameters not found in symbol table
```
error: Undefined type (Identifier 'n')
error: Undefined type (Identifier 'count')
error: Undefined type (Identifier 'i')
```

**Examples**:
- Loop variables (`i`, `j`)
- Function parameters (`n`, `a`, `b`)
- Local variables (`count`, `value`)

**Root cause**: Symbol table not properly tracking:
- Function parameters
- Loop iteration variables
- Local variable declarations
- Expression evaluation context

**Fix needed**: Enhance name resolution pass
- Properly register function parameters in scope
- Track loop variable declarations
- Ensure variable declarations are added to symbol table
- Check scope management (enter/exit)

### 3. Type Inference (HIGH PRIORITY)
**Impact**: All files with variable declarations

**Pattern**: Variables have `unknown type` instead of inferred types
```
error: Assignment type mismatch: expected 'unknown type', got 'i32'
error: Cannot index this type: got 'unknown type'
error: Requires pointer type: got 'unknown type'
```

**Examples**:
```a7
count := 0           // Should infer i32, but gets unknown type
count += 5           // Error: expected 'unknown type', got 'i32'
```

**Root cause**: Type checker not inferring types from initializers
- Variable declarations (`:=`) don't propagate type from value
- Compound assignments fail because target has unknown type
- Array/pointer operations fail on unknown types

**Fix needed**: Implement type inference
- Infer variable types from initialization expressions
- Propagate types through assignments
- Handle generic type instantiation

### 4. Return Type Checking (MEDIUM PRIORITY)
**Impact**: Most functions with return values

**Pattern**: All returns show type mismatch
```
error: Return type mismatch: expected 'i32', got 'None'
```

**Examples**:
```a7
add :: fn(x: i32, y: i32) i32 {
    ret x + y  // Error: expected 'i32', got 'None'
}
```

**Root cause**: Return expression types not evaluated
- `visit_return_stmt` gets `None` as return type
- Expression type not computed before comparison
- Possibly returning Python `None` instead of actual type

**Fix needed**:
- Compute return expression type before checking
- Handle void returns (no expression)
- Track return types through control flow

### 5. Field Access on Enums (MEDIUM PRIORITY)
**Impact**: Enum-heavy examples

**Pattern**: Enum variant access treated as struct field access
```
error: Cannot access field on non-struct type: got 'Color'
error: Cannot access field on non-struct type: got 'StatusCode'
```

**Examples**:
```a7
color := Color.Red  // Error: Cannot access field on non-struct type
```

**Root cause**: Enum variant access (`.Red`) confused with struct field access
- Enums should allow variant access via `.`
- Type checker expects only structs to use `.` operator

**Fix needed**:
- Add enum variant resolution
- Distinguish struct field access from enum variant access
- Check variant exists in enum definition

### 6. Duplicate Symbol Detection (LOW PRIORITY)
**Impact**: 1 file (032_prime_numbers.a7)

**Pattern**: Variable redefinition in nested scopes
```
error: Already defined: Variable 'count'
error: Already defined: Variable 'i'
```

**Root cause**: Scope shadowing not implemented or too strict
- Loop variables `i` redeclared in different loops
- Variables with same name in different scopes

**Fix needed**:
- Allow variable shadowing in nested scopes
- Only error on redefinition in same scope

## Error Frequency by Type

### Top 10 Most Common Errors:

1. **Undefined type (Identifier 'io')** - ~600+ occurrences
   - Module system not implemented

2. **Cannot access field on non-struct type (io.println)** - ~400+ occurrences
   - Module qualified access not supported

3. **Type is not callable (io.println)** - ~400+ occurrences
   - Cascades from undefined io module

4. **Undefined type (local variables)** - ~300+ occurrences
   - Symbol table not tracking variables

5. **Assignment type mismatch: expected 'unknown type'** - ~150+ occurrences
   - Type inference not working

6. **Cannot index this type: got 'unknown type'** - ~100+ occurrences
   - Type inference failure

7. **Return type mismatch: expected 'X', got 'None'** - ~80+ occurrences
   - Return expression type not computed

8. **Requires pointer type: got 'unknown type'** - ~80+ occurrences
   - Type inference + pointer operations

9. **Requires numeric type** - ~40+ occurrences
   - Expression type checking

10. **Condition must be bool** - ~15 occurrences
    - Control flow type checking

## Implementation Priority

### P0 - Critical (Blocks most examples)
1. **Module system** - Implement standard library resolution
   - Add built-in `io` module
   - Module qualified access (`io.println`)
   - Import statement processing

2. **Symbol resolution** - Fix variable/parameter lookup
   - Function parameters in scope
   - Local variable declarations
   - Loop variable tracking

3. **Type inference** - Infer types from initializers
   - Variable declaration type inference
   - Expression type propagation
   - Generic instantiation

### P1 - High (Improves many examples)
4. **Return type evaluation** - Compute return expression types
   - Expression type before return check
   - Void return handling
   - Control flow analysis

5. **Enum variant access** - Support enum member access
   - Variant lookup in enum types
   - Distinguish from struct fields

### P2 - Medium (Improves specific features)
6. **Pointer operations** - Type checking for pointer ops
   - `.adr` and `.val` operations
   - Pointer arithmetic type rules

7. **Array operations** - Type checking for arrays
   - Indexing type rules
   - Slice operations
   - Multi-dimensional arrays

### P3 - Low (Polish and edge cases)
8. **Scope shadowing** - Allow variable shadowing
   - Nested scope handling
   - Loop variable redeclaration

9. **Error message quality** - Improve error context
   - Better span precision
   - More specific error messages
   - Suggest fixes

## Next Steps

### Immediate Actions:
1. **Implement basic module system**
   - Create `io` module with `println` function
   - Add module symbol table
   - Support module.function syntax

2. **Fix symbol resolution**
   - Debug why parameters aren't in scope
   - Ensure variable declarations are tracked
   - Test with simple examples first

3. **Implement type inference**
   - Start with simple cases (`:= literal`)
   - Propagate through assignments
   - Handle function returns

### Testing Strategy:
1. Start with simplest examples (001_hello.a7, 002_var.a7)
2. Verify each fix reduces error count
3. Move to more complex examples progressively
4. Track error count reduction as metric

### Success Metrics:
- **Phase 1**: Examples 001-007 compile cleanly (basic I/O, variables, loops)
- **Phase 2**: Examples 008-020 compile cleanly (structs, enums, arrays)
- **Phase 3**: Examples 021-035 compile cleanly (advanced features)

## File-by-File Error Counts

| File | Error Count | Primary Issues |
|------|-------------|----------------|
| 000_empty.a7 | 0 | ✅ None |
| 001_hello.a7 | 3 | io module |
| 002_var.a7 | 20 | io module, type inference |
| 003_comments.a7 | 0 | ✅ None |
| 004_func.a7 | 28 | io module, return types, symbol resolution |
| 005_for_loop.a7 | 80 | io module, loop vars, type inference |
| 006_if.a7 | 59 | io module, symbol resolution |
| 007_while.a7 | 58 | io module, loop vars, type inference |
| 008_switch.a7 | 0 | ✅ None |
| 009_struct.a7 | 19 | io module, struct field access |
| 010_enum.a7 | 8 | enum variant access |
| 011_memory.a7 | 266 | io module, pointer ops, symbol resolution |
| 012_arrays.a7 | 178 | io module, array indexing, type inference |
| 013_pointers.a7 | 223 | io module, pointer ops, type inference |
| 014_generics.a7 | 46 | io module, generic instantiation |
| 015_types.a7 | 0 | ✅ None |
| 016_unions.a7 | 3 | union tag access |
| 017_methods.a7 | 72 | method resolution, symbol resolution |
| 018_modules.a7 | 30 | module system, type checking |
| 019_literals.a7 | 79 | io module |
| 020_operators.a7 | 134 | io module, compound assignments |
| 021_control_flow.a7 | 13 | io module, return types |
| 022_function_pointers.a7 | 46 | function pointer types, symbol resolution |
| 023_inline_structs.a7 | 0 | ✅ None |
| 024_defer.a7 | 61 | io module, defer semantics, pointer ops |
| 025_linked_list.a7 | 142 | pointer ops, struct access, symbol resolution |
| 026_binary_tree.a7 | 176 | pointer ops, tree traversal, symbol resolution |
| 027_callbacks.a7 | 133 | function pointers, struct access |
| 028_state_machine.a7 | 167 | state transitions, function pointers |
| 029_sorting.a7 | 192 | array ops, function pointers, symbol resolution |
| 030_calculator.a7 | 114 | io module, return types |
| 031_number_guessing.a7 | 145 | io module, struct access, RNG |
| 032_prime_numbers.a7 | 4 | variable shadowing |
| 033_fibonacci.a7 | 111 | iterative sequence generation, memoization-style storage, array ops |
| 034_string_utils.a7 | 161 | string ops, array ops, symbol resolution |
| 035_matrix.a7 | 204 | 2D arrays, array ops, symbol resolution |

**Total errors across all files**: ~3,300+
