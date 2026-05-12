# Pipeline

Canonical page: [Compiler and Tests](/a7-py/docs/compiler.md).

```mermaid
flowchart LR
    Src[Source .a7] --> Tok[Tokenizer]
    Tok --> Par[Parser]
    Par --> Sem[Semantic Analysis]
    Sem --> Safe[Safety Proof Plan]
    Safe --> Pre[AST Preprocessing]
    Pre --> Gen[Codegen]
    Gen --> Zig[Zig output]
```

```text
Source (.a7) -> Tokenizer -> Parser -> Semantic Analysis -> AST Preprocessing -> Backend Codegen -> Zig output
```

Use this alias when an agent guesses `/docs/pipeline.md`. The full compiler notes live in `compiler.md`.
