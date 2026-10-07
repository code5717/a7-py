# Feature coverage and evidence

This inventory maps every heading in `docs/SPEC.md`, the preserved array-proposal subsections in
`docs/design/array-programming.md`, every lexer keyword and operator spelling, every registered standard-library operation, every current example file, proposed tensor APIs, and the broader proposed standard-library signatures to a documentation topic and disposition. `content/features.json` is the machine-readable source.

A disposition records what readers should rely on. It does not turn parser acceptance, a registry entry, or a source revision into execution evidence. The example records link the separate verification report and its dated compiler/native results for the files it checked. Supported means an implemented documented form with linked source/example evidence, not a general safety guarantee.

## Historical probe conflicts and remaining questions

The observations below describe the 2026-09-19 probe state. Later SPEC repairs
resolved several documentation conflicts, including generic-name digits,
escapes, and scalar-fill arrays. The current matrix follows the current source
inventories; the linked probe report retains its original evidence.

- Typed `name: Type = value` creates a mutable variable in `Parser.parse_declaration`. SPEC sections 4.1 and 4.2 include contradictory immutable comments. The website follows the parser. Compiler behavior is unchanged.
- SPEC's keyword list differs from `Tokenizer.KEYWORDS`. The builtin page gives both dispositions. `cast` is context-sensitive parser syntax.
- The generic name rule forbids digits in SPEC, while the lexer accepts them after the initial letter. The reference recommends letter-only parameters and marks broader support unverified.
- Appendix D lists `\b`, `\f`, `\v`, and `\a`, but tokenizer escape handling omits them. The website publishes the actual lexer escape set.
- Appendix C's implementation-limit table is not proven to match enforced limits. The lexer evidence establishes 100-character identifiers and numeric spellings. Other limit claims remain unverified.
- SPEC evaluation order is published as a requirement, with exhaustive side-effect order qualification still unverified.
- SPEC section 9 and the broad section 11.2 API list are planned design. They are never listed as runnable functions.
- Memory and safety claims follow `SAFETY_CONTRACT.md`'s current-enforcement paragraph, including its explicit gaps.

- A fresh native probe rejects `filled: [3]i32 = 7` during semantic analysis, contradicting SPEC's scalar-fill array claim. Zero initialization without an initializer and nested array literals passed native execution.
- Direct `text.len` on `string` fails semantic analysis. The string slice `text[0..1]` supports `.len`, verified natively. The metadata distinguishes both operations.
- A local `@type_set` alias passes semantic analysis but fails codegen with `unsupported expression node TYPE_SET`. Constraint semantics are not a claim of general native type-set support.

These findings are recorded with source programs and diagnostics in
[the reference probe report](reference-probes.json).

## Coverage matrix

| ID or source item | Status | Topic | Disposition |
| --- | --- | --- | --- |
| ascii-source | supported | [language/syntax](../public/docs/language/syntax.md) | Lexer-supported ASCII names, spacing, and escapes. This is a lexical disposition, not native-execution evidence for arbitrary source. |
| typed-variable | supported | [language/declarations](../public/docs/language/declarations.md) | Typed name: Type = value declarations are mutable; native-verified example 002 increments its explicitly typed i32 count. |
| numeric-types | limited | [language/types](../public/docs/language/types.md) | Explicit-width scalars and usize/isize. Integer addition, subtraction, and multiplication wrap; shift safety and other numeric edge cases remain incomplete. |
| casts | limited | [language/types](../public/docs/language/types.md) | Primitive casts require classification and range proof. |
| evaluation-order | unverified | [language/operators](../public/docs/language/operators.md) | SPEC states evaluation order; no exhaustive side-effect-order qualification is claimed. |
| loops-match | supported | [language/control-flow](../public/docs/language/control-flow.md) | Native probes verify literal/range/capture matches and statement fallthrough; example suite covers labels and loops. Fall placement is restricted. |
| recursion | unavailable | [language/functions](../public/docs/language/functions.md) | Direct and mutual recursion and known indirect cycles are rejected. |
| variadics | unavailable | [language/functions](../public/docs/language/functions.md) | Declarations may parse but user variadic runtime lowering is rejected. |
| multiple-returns | unavailable | [language/functions](../public/docs/language/functions.md) | Multiple returns and destructuring are not backend features; use a result struct. |
| method-call-sugar | planned | [language/functions](../public/docs/language/functions.md) | Use explicit receiver functions; dot-call methods are not current semantic support. |
| fixed-arrays | supported | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Native probes verify exactly sized nested/value array literals and zero initialization without an initializer. Scalar-fill initializers such as [3]i32 = 7 are rejected. |
| array-addition | limited | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Native probe verifies same-shape [2]f64 addition. This does not establish tensor broadcasting or every numeric array shape. |
| slices | limited | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Native probes verify half-open slicing, usize indexing, and slice .len. Full backing-storage lifetime enforcement remains incomplete. |
| heap-fixed-arrays | unavailable | [language/arrays-strings](../public/docs/language/arrays-strings.md) | new [N]T is rejected; use stack arrays or supported slice operations. |
| union-tags | unavailable | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Tagged-union inspection is reserved and discriminant safety is incomplete. |
| generics | limited | [language/generics](../public/docs/language/generics.md) | Concrete function/struct examples exist; composite and call-chain propagation are incomplete. |
| type-sets | limited | [language/generics](../public/docs/language/generics.md) | Constraint syntax and semantic checks exist. A local @type_set alias passed semantics but failed Zig emission with unsupported TYPE_SET; native support is limited. |
| reference-passing | limited | [language/memory](../public/docs/language/memory.md) | Ordinary lvalues pass to ref parameters; nil proof required for heap refs. |
| ownership | limited | [language/memory](../public/docs/language/memory.md) | Direct use-after-del checks do not establish full alias or lifetime enforcement. |
| automatic-memory | planned | [language/memory](../public/docs/language/memory.md) | Automatic memory management is planned and not the current manual new/del model. |
| file-modules | limited | [language/modules](../public/docs/language/modules.md) | Per-file scopes, underscore privacy, qualified types and struct literals emit one combined Zig file. Import aliases stay local; imported generic function values retain checking gaps. |
| selected-imports | unavailable | [language/modules](../public/docs/language/modules.md) | Resolver metadata is not runnable backend support. |
| using-import | unavailable | [language/modules](../public/docs/language/modules.md) | Not a supported public executable import workflow. |
| concurrency | planned | [language/builtins](../public/docs/language/builtins.md) | No implemented public concurrency model. |
| collections | planned | [language/builtins](../public/docs/language/builtins.md) | Collection modules remain planned; canonical prelude Option(T) and Result(T, E) are available. |
| 1. Introduction | limited | [language/syntax](../public/docs/language/syntax.md) | Design intent and project context, qualified by current implementation status. |
| 1.1 Language Overview | limited | [language/syntax](../public/docs/language/syntax.md) | Design intent and project context, qualified by current implementation status. |
| 1.2 Design Philosophy | limited | [language/syntax](../public/docs/language/syntax.md) | Design intent and project context, qualified by current implementation status. |
| 2. Lexical Structure | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.1 Source Encoding | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.2 Comments | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.3 Identifiers | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.4 Keywords | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.5 Operators and Punctuation | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 2.6 Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Integer Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Floating-Point Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Character Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| String Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Boolean Literals | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Nil Literal | limited | [language/syntax](../public/docs/language/syntax.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 3. Type System | limited | [language/types](../public/docs/language/types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 3.1 Type Categories | limited | [language/types](../public/docs/language/types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 3.2 Primitive Types | limited | [language/types](../public/docs/language/types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 3.3 Composite Types | limited | [language/types](../public/docs/language/types.md) | See individual array, slice, struct, and reference restrictions. String .len and scalar-filled array initialization described by SPEC are rejected. |
| Arrays | limited | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Fixed/nested literals and zero initialization are verified. SPEC scalar-fill initialization conflicts with current semantic rejection. |
| Slices | limited | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Native probes verify slicing, usize indexing, and slice .len. Full backing-storage lifetime enforcement is incomplete. |
| Strings | limited | [language/arrays-strings](../public/docs/language/arrays-strings.md) | String slicing and iteration are verified. Direct string .len is rejected with a non-struct-field semantic error; a slice .len works. |
| References (Pointers) | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Structs | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Unions | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Enums | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Plain enums support explicit integer values; emitted tag uses the first of i32, u32, i64, u64 that fits all variants. Regression tests cover wide values. |
| 3.4 Type Aliases | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 3.5 Reference Semantics | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 4. Declarations and Expressions | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 4.1 Variable Declarations | limited | [language/declarations](../public/docs/language/declarations.md) | Typed declarations are mutable. Fixed arrays zero-initialize without an initializer; scalar-fill initializers are rejected despite SPEC prose. |
| 4.2 Declaration Rules | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 4.3 Expression Categories | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Primary Expressions | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Postfix Expressions | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Unary Expressions | limited | [language/operators](../public/docs/language/operators.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Binary Expressions | limited | [language/operators](../public/docs/language/operators.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| Cast Expressions | limited | [language/types](../public/docs/language/types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 5. Control Flow | limited | [language/control-flow](../public/docs/language/control-flow.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 5.1 Conditional Statements | limited | [language/control-flow](../public/docs/language/control-flow.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 5.2 Pattern Matching | limited | [language/control-flow](../public/docs/language/control-flow.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 5.3 Loops | limited | [language/control-flow](../public/docs/language/control-flow.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 5.4 Jump Statements | limited | [language/control-flow](../public/docs/language/control-flow.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 6. Functions | limited | [language/functions](../public/docs/language/functions.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 6.1 Function Declarations | limited | [language/functions](../public/docs/language/functions.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 6.2 Recursion | unavailable | [language/functions](../public/docs/language/functions.md) | Recursion is banned; user variadic runtime lowering is unavailable. See the function restrictions. |
| 6.3 Function Parameter Immutability | limited | [language/functions](../public/docs/language/functions.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 6.4 Function Types | limited | [language/functions](../public/docs/language/functions.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 6.5 Methods | limited | [language/functions](../public/docs/language/functions.md) | Explicit receiver functions exist; dot-call method sugar is planned. |
| 6.6 Variadic Functions | unavailable | [language/functions](../public/docs/language/functions.md) | Recursion is banned; user variadic runtime lowering is unavailable. See the function restrictions. |
| 7. Generics | limited | [language/generics](../public/docs/language/generics.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 7.1 Generic System Design | limited | [language/generics](../public/docs/language/generics.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 7.2 Generic Types | limited | [language/generics](../public/docs/language/generics.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 7.3 Type Sets and Constraints | limited | [language/generics](../public/docs/language/generics.md) | Semantic type-set constraints exist, but a local @type_set alias fails codegen with unsupported TYPE_SET. Parser/semantic support is not native support. |
| 7.4 Generic Specialization | limited | [language/generics](../public/docs/language/generics.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 8. Memory Management | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 8.1 Stack Allocation | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 8.2 Heap Allocation | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 8.3 Defer Statement | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 8.4 Memory Safety Status | limited | [language/memory](../public/docs/language/memory.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 9. Planned Array Programming for AI | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | SPEC section 9 links to the separate historical array-programming proposal; tensor APIs are not current executable support. |
| 9.1 Multidimensional Arrays | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Tensor Types | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Array Literals and Initialization | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.2 Broadcasting and Vectorized Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Automatic Broadcasting | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Vectorized Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.3 Tensor Manipulation and Reshaping | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Shape Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Axis Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.4 Reduction Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.5 Linear Algebra Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.6 AI-Specific Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Neural Network Primitives | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Gradient Operations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.7 Memory Layout and Performance | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Memory Layout Control | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Performance Annotations | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.8 Indexing and Slicing | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Advanced Indexing | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.9 Built-in Tensor Functions | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 9.10 Array Programming Examples | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Machine Learning Example | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| Scientific Computing Example | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Historical array-programming proposal, not implemented syntax or approved API spelling. |
| 10. Modules and Visibility | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.1 File-Based Module Model | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.2 Import Statements | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.2.1 Module identity and resolution | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.2.2 Cycles and entry | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.3 Standard Library Status | limited | [language/modules](../public/docs/language/modules.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 10.4 Visibility rules | limited | [language/modules](../public/docs/language/modules.md) | Per-file scopes enforce underscore privacy and keep import aliases local. Local double-underscore names and pub parsing retain their existing behavior. |
| 11. Built-in Functions and Operators | limited | [language/builtins](../public/docs/language/builtins.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 11.1 Builtin Functions | limited | [language/builtins](../public/docs/language/builtins.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| 11.2 Standard Library Functions | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual IO/math functions are current; broader signature catalogue is planned API shape. |
| 12. Tokens and AST Components | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 12.1 Token Types | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 12.2 AST Node Types | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 12.3 AST Node Structure | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 12.4 Parsing Precedence | limited | [language/operators](../public/docs/language/operators.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 13. Grammar Summary | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 13.1 Top-Level Grammar | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 13.2 Type Grammar | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 13.3 Expression Grammar | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| 13.4 Statement Grammar | limited | [language/syntax](../public/docs/language/syntax.md) | Compiler token/AST or grammar description; does not independently establish executable feature support. |
| Appendix A: Language Semantics | limited | [language/builtins](../public/docs/language/builtins.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| A.1 Evaluation Order | unverified | [language/operators](../public/docs/language/operators.md) | Specification requirement; exhaustive runtime ordering has not been qualified by this documentation work. |
| A.2 Type Conversions | limited | [language/types](../public/docs/language/types.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| A.3 Name Resolution | limited | [language/declarations](../public/docs/language/declarations.md) | Documented with current implementation restrictions; SPEC prose alone is not native execution evidence. |
| A.4 Lifetime Rules | limited | [language/memory](../public/docs/language/memory.md) | Required lifetime constraints; complete ownership and alias enforcement remain incomplete. |
| Appendix B: Standard Compiler Diagnostics | limited | [compiler](../public/docs/compiler.md) | Diagnostic design and examples; do not infer that proposed E-code categories appear in every current diagnostic. |
| B.1 Error Categories | limited | [compiler](../public/docs/compiler.md) | Diagnostic design and examples; do not infer that proposed E-code categories appear in every current diagnostic. |
| B.2 Common Lexer Error Messages | limited | [compiler](../public/docs/compiler.md) | Diagnostic design and examples; do not infer that proposed E-code categories appear in every current diagnostic. |
| B.3 Warning Categories | limited | [compiler](../public/docs/compiler.md) | Diagnostic design and examples; do not infer that proposed E-code categories appear in every current diagnostic. |
| Appendix C: Implementation Limits | unverified | [language/syntax](../public/docs/language/syntax.md) | SPEC limit table is not a verified list of enforced implementation limits. Lexer name/literal limits are documented separately. |
| Appendix D: ASCII Character Set Support | limited | [language/syntax](../public/docs/language/syntax.md) | ASCII public model; escape support follows tokenizer, which omits several escapes listed in Appendix D. |
| Appendix E: Implementation Status (a7-py) | limited | [status](../public/docs/status.md) | Historical implementation snapshot; current STATUS and fresh checks take precedence. |
| E.1 Current Constraints and Open Gaps | limited | [status](../public/docs/status.md) | Historical implementation snapshot; current STATUS and fresh checks take precedence. |
| E.2 Source Of Truth | limited | [status](../public/docs/status.md) | Historical implementation snapshot; current STATUS and fresh checks take precedence. |
| and | limited | [language/operators](../public/docs/language/operators.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| as | unverified | [language/builtins](../public/docs/language/builtins.md) | Lexer reserves this spelling; it is not recommended here as a qualified native-execution form. |
| bool | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| break | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| case | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| char | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| continue | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| defer | limited | [language/memory](../public/docs/language/memory.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| del | limited | [language/memory](../public/docs/language/memory.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| else | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| enum | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| f32 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| f64 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| fall | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| false | limited | [language/syntax](../public/docs/language/syntax.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| float | unverified | [language/builtins](../public/docs/language/builtins.md) | Lexer reserves this spelling; it is not recommended here as a qualified native-execution form. |
| fn | limited | [language/functions](../public/docs/language/functions.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| for | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| i16 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| i32 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| i64 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| i8 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| if | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| import | limited | [language/modules](../public/docs/language/modules.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| in | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| int | unavailable | [language/builtins](../public/docs/language/builtins.md) | Lexically reserved, but rejected as a public integer alias; choose explicit width. |
| isize | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| let | unverified | [language/builtins](../public/docs/language/builtins.md) | Lexer reserves this spelling; it is not recommended here as a qualified native-execution form. |
| match | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| new | limited | [language/memory](../public/docs/language/memory.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| nil | limited | [language/syntax](../public/docs/language/syntax.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| not | limited | [language/operators](../public/docs/language/operators.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| or | limited | [language/operators](../public/docs/language/operators.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| pub | limited | [language/modules](../public/docs/language/modules.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| ref | limited | [language/memory](../public/docs/language/memory.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| ret | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| string | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| struct | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| true | limited | [language/syntax](../public/docs/language/syntax.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| u16 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| u32 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| u64 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| u8 | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| uint | unavailable | [language/builtins](../public/docs/language/builtins.md) | Lexically reserved, but rejected as a public integer alias; choose explicit width. |
| union | limited | [language/aggregate-types](../public/docs/language/aggregate-types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| usize | limited | [language/types](../public/docs/language/types.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| where | unverified | [language/generics](../public/docs/language/generics.md) | Lexer reserves this spelling; it is not recommended here as a qualified native-execution form. |
| while | limited | [language/control-flow](../public/docs/language/control-flow.md) | Reserved lexer keyword; executable use follows the linked topic restrictions. |
| cast | limited | [language/builtins](../public/docs/language/builtins.md) | Context-sensitive cast syntax, not a keyword. |
| const | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| self | limited | [language/builtins](../public/docs/language/builtins.md) | Ordinary identifier usable as a receiver parameter name. |
| size_of | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| type | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| using | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| var | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| number | unavailable | [language/builtins](../public/docs/language/builtins.md) | Not a current public declaration keyword or executable operation; specification mentions do not confer support. |
| ! | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| != | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| % | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| %= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| & | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| &= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ( | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ) | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| * | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| *= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| + | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| += | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| , | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| - | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| -= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| . | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| .. | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| / | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| /= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| : | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| :: | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| := | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ; | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| < | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| << | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| <<= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| <= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| = | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| == | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| > | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| >= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| >> | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| >>= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| [ | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ] | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ^ | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ^= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| { | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| \| | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| \|= | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| } | limited | [language/syntax](../public/docs/language/syntax.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| ~ | limited | [language/operators](../public/docs/language/operators.md) | Tokenized spelling; type rules, precedence, and operation-specific safety restrictions apply. No public address/dereference meaning. |
| std.io.println | limited | [stdlib](../public/docs/stdlib.md) | Native ordinary/empty output calls verified. Literal formats and matching bare {} arguments required; {{ and }} print literal braces without consuming arguments. |
| std.io.print | limited | [stdlib](../public/docs/stdlib.md) | Native ordinary/empty output calls verified. Literal formats and matching bare {} arguments required; {{ and }} print literal braces without consuming arguments. |
| std.io.eprintln | limited | [stdlib](../public/docs/stdlib.md) | Native ordinary/empty output calls verified. Literal formats and matching bare {} arguments required; {{ and }} print literal braces without consuming arguments. |
| std.io.println_ok | limited | [stdlib](../public/docs/stdlib.md) | Returns canonical Result(usize, io.IoErr); success counts written bytes including the newline. Saved and forwarded results support explicit match. |
| std.io.read_line | limited | [stdlib](../public/docs/stdlib.md) | Requires one mutable []u8 and returns canonical Result(usize, io.IoErr). Repeated reads preserve remaining input; EOF and full-buffer behavior have native controls. |
| std.math.sqrt | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.abs | limited | [stdlib](../public/docs/stdlib.md) | Floating and signed integer native calls verified. Signed results preserve the input type. The minimum signed input wraps to itself; the i32 edge is tested in all three native profiles. |
| std.math.floor | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.ceil | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.sin | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.cos | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.tan | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.log | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.exp | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.min | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| std.math.max | limited | [stdlib](../public/docs/stdlib.md) | Registered virtual operation with Zig mapping; signatures and numeric/format restrictions are documented in the stdlib reference. |
| tensor_arange | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_argmax | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_argmin | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_backward | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_backward_solve | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_batch_norm | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_c_layout | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_cast | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_clip_grad_norm | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_clone | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_concat | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_contiguous | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_copy | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_cross | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_det | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_device | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_dot | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_dtype | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_eig | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_expand_dims | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_eye | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_f_layout | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_flatten | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_forward_solve | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_from_data | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_gelu | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_grad_enable | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_inv | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_layer_norm | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_linspace | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_load | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_lu | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_lu_pivot | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_matmul | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_max | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_mean | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_min | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_ndim | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_no_grad | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_norm | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_ones | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_operation | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_print | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_qr | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_random | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_range | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_relu | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_reshape | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_save | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_shape | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_sigmoid | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_size | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_softmax | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_split | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_squeeze | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_stack | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_std | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_strided | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_sum | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_svd | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_to_cpu | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_to_gpu | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_trace | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_transpose | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_unsqueeze | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_var | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_view | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_where | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_zeros | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| abs_f32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| abs_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| abs_i32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| abs_i64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| assert | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| assert_msg | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_is_alpha | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_is_digit | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_is_lower | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_is_upper | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_to_lower | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| char_to_upper | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| cos_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| eprint | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| eprintln | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| max_f32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| max_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| max_i32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| max_i64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_alloc | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_compare | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_copy | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_free | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_move | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_realloc | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_set | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| mem_zero | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| min_f32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| min_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| min_i32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| min_i64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| panic | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| pow_f32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| pow_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| print | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| print_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| print_i32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| printf | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| sin_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| sqrt_f32 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| sqrt_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_compare | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_contains | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_copy | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_ends_with | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_find | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_len | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| str_starts_with | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| tan_f64 | planned | [stdlib](../public/docs/stdlib.md) | Illustrative future standalone API, not a current registered stdlib function. Use the actual module-qualified registry. |
| @size_of | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @align_of | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @type_id | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @type_name | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @unreachable | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @likely | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| @unlikely | unavailable | [language/builtins](../public/docs/language/builtins.md) | Reserved or parsed intrinsic spelling without current semantic resolution and backend lowering. |
| 000_empty.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 001_hello.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 002_var.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 003_comments.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 004_func.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 005_for_loop.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 006_if.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 007_while.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 008_switch.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 009_struct.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 010_enum.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 011_memory.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 012_arrays.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 013_pointers.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 014_generics.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 015_types.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 016_unions.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 017_methods.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 018_modules.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 019_literals.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 020_operators.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 021_control_flow.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 022_function_pointers.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 023_inline_structs.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 024_defer.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 025_linked_list.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 026_binary_tree.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 027_callbacks.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 028_state_machine.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 029_sorting.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 030_calculator.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 031_number_guessing.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 032_prime_numbers.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 033_fibonacci.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 034_string_utils.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 035_matrix.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 036_control_flow_edges.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 037_language_tour.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 038_inventory_report.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 039_text_analyzer.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 040_task_board.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 041_route_simulation.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 042_gradebook.a7 | supported | [examples](../public/docs/examples.md) | Fresh example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-09-19. This establishes this example only. |
| 043_math_library.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 044_indexing_rules.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 045_formatting.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 046_match_full.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 047_safety_obligations.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 048_worklist_traversal.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-01. This establishes this example only. |
| 049_expense_ledger.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-04. This establishes this example only. |
| 050_tip_split.a7 | supported | [examples](../public/docs/examples.md) | Example-suite verification passed A7 compile, Zig validation/build, native run, and golden-output comparison on 2026-10-04. This establishes this example only. |
| Scalar-fill array initializer | unavailable | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Unavailable: filled: [3]i32 = 7 is rejected at semantic analysis with expected [3]i32, got i32. Use a full literal or a loop. |
| String .len | unavailable | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Unavailable: text.len on string is rejected as field access on a non-struct type. A verified string slice has .len. |
| tensor_conv2d | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_maxpool2d | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_to_f32 | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| tensor_to_i32 | planned | [language/arrays-strings](../public/docs/language/arrays-strings.md) | Proposed API preserved in docs/design/array-programming.md; no current executable implementation. |
| 4.2.1 Untyped numeric constants | limited | [language/types](../public/docs/language/types.md) | Approved P-TYP contract with implementation and release verification in progress; exact-value fitting per SPEC, not yet fully verified. |
| Nested functions | limited | [language/functions](../public/docs/language/functions.md) | Capture-free nested functions can be called or returned as function values. Reading an enclosing local or parameter is rejected during code generation with exit 7. |

## Reference excerpt integration check

On 2026-09-19, the [combined reference smoke program](evidence/reference-smoke.a7)
passed A7 compilation, native Zig compilation, and execution. It covers typed
mutable declarations, nested arrays, loops, primitive casting, reference
mutation, union initialization, and concrete generic functions and structs.
[Commands and observed output](evidence/reference-smoke.txt) record the result.

The first native build rejected an unused local constant. The checked source
consumes that constant and then passes. Code fragments in the reference pages
are syntax excerpts, not standalone programs unless they include all required
declarations and a `main` function. This smoke check does not qualify every
possible composition of these features.

## Inventory validation

The 2026-09-19 inventory assertion checked all 117 specification headings, all 48 lexer
keywords, all 43 example filenames, all feature topic paths, and every evidence
file. The 428 feature IDs are unique, and every status uses the five-value schema.
The operator inventory was extracted from `Tokenizer._try_operator`, including
all 42 actual operator and punctuation spellings. The standard-library inventory
comes from `StdlibRegistry`, not the specification's proposed API list.

The refreshed native probes verify escaped IO format braces and signed
`math.abs` results. The minimum signed input wraps to itself.
[`test_checked_arithmetic_edges.py`](../../test/test_checked_arithmetic_edges.py)
checks the i32 minimum in debug, release and fast profiles. The earlier
[observed probe results](content-verification.md) remain historical evidence.
