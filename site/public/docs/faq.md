# FAQ

## Is recursion allowed

No. A7 rejects direct, mutual, local alias, and callback-trampoline source recursion during semantic validation. Use loops, explicit stacks, queues, or index-based worklists.

## Which integer type should examples use

Use `usize` for sizes, lengths, and indices. Use `isize` for signed pointer-sized offsets or position differences. Use fixed-width integers such as `i32`, `u64`, or `f64` when the data has a fixed width or numeric domain.

## Is A7 memory safe

Not yet. The compiler has basic checks around `del` and references, but it does not implement a full ownership, borrow, lifetime, double-free, or use-after-free model.

## Can I run untrusted A7 source

No. A7 emits Zig or C and then builds native programs with the host toolchain. Treat compiled programs like any other native executable.

## Which stdlib modules are current

Current virtual stdlib support is limited to `std/io` and `std/math`. `std/string`, `std/mem`, and collections are planned or stubbed but not public current modules.

## Is package-registry publishing configured

No. The current release workflow builds package artifacts and attaches them to
draft GitHub releases, but does not publish to a package registry.
