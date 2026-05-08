# Why A7

A7 is a small systems-language compiler project focused on readable source, explicit control flow, and direct Zig output.

## Design Goals

- Keep the language surface small enough to audit.
- Prefer loops, explicit stacks, and worklists over recursion.
- Make compiler stages visible: tokenize, parse, validate, preprocess, codegen.
- Keep generated artifacts inspectable in Zig.
- Document gaps honestly instead of presenting planned features as shipped.

## Current Fit

A7 is useful as a compiler and language-design project, a testbed for compiler stages, and a compact examples corpus. It is not a sandbox for untrusted code.

## Non-Goals

- No source recursion.
- No fake stdlib surface in docs.
- No claim of ownership, borrowing, or lifetime safety until those checks exist.
- No GPU, tensor, or AI runtime support until a real design and implementation exist.
