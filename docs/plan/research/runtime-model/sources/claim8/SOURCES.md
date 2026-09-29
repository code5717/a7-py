<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim8/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 8 sources — cross-architecture IR and remote hot reload

All read 2026-09-18. Quotes grep-verified against the saved files.

### Zig 0.15.1 release notes — self-hosted x86_64 backend
URL: https://ziglang.org/download/0.15.1/release-notes.html
Saved: zig_0_15.html / zig_flat.txt
Kind: project claim with a measured figure
Quote: "Debug compilation is 5 times faster with Zig's <a href="#x86-Backend">x86 Backend</a> selected by default"
Quote: "Compilation time is significantly improved&mdash;around a 5x decrease compared to LLVM in most cases."
Quote: "the self-hosted x86 backend already passes a larger subset of our &quot;behavior test suite&quot; than the LLVM backend does (1984/2008 vs 1977/2008)"
Quote: "Our work on self-hosted code generation backends is a part of our long-term plan to transition LLVM to an optional dependency and decouple it from the compiler implementation. Achieving this goal will lead to large decreases in compile time, good support for incremental compilation in Debug builds"
Note: The measured number behind "ultra-fast direct translation": roughly 5x over LLVM, for Debug-quality code, on one architecture, from the project itself. Benchmark conditions are not given beyond "in most cases". This is the number that matters most to A7, which emits Zig.

### Zig 0.15.1 release notes — aarch64 backend
Saved: zig_0_15.html / zig_flat.txt
Quote: "This backend is passing 1656/1972 (84%) behavior tests relative to LLVM, so is not ready to be enabled by default, nor is it currently usable in any real use case."
Note: Prices the "multiple instruction set architectures" half. A serious full-time effort has one architecture done and the second at 84% of a behavior suite after a release cycle.

### Zig 0.15.1 release notes — incremental compilation and threaded codegen
Saved: zig_0_15.html / zig_flat.txt
Quote: "This feature is still experimental&mdash;it has known bugs and can lead to miscompilations or incorrect compile errors."
Quote: "building the Zig compiler using its own x86_64 backend got 27% faster on one system from this change, with the wall-clock time going from 13.8s to 10.0s."
Note: A measured wall-clock figure with its conditions stated ("on one system"). Also: incremental compilation, the thing a fast edit loop needs, is still experimental in the toolchain A7 targets.

### QBE
URL: https://c9x.me/compile/
Saved: qbe.html
Kind: project claim
Quote (whitespace-normalized): "QBE is a compiler backend that aims to provide 70% of the performance of industrial optimizing compilers in 10% of the code."
Note: States the code-quality tradeoff of a small multi-target backend. It is a goal statement, not a measurement, and it says nothing about compile throughput.

### rustc_codegen_cranelift README
URL: https://raw.githubusercontent.com/rust-lang/rustc_codegen_cranelift/master/Readme.md
Saved: cgclif.md
Kind: project claim
Quote: "This has the potential to improve compilation times in debug mode."
Note: The project's own README claims a potential, not a measured speedup. No compile-throughput figure appears in it. Any specific multiplier for Cranelift vs LLVM must come from elsewhere; none was obtained here.

### Live++ documentation — architecture and remote bridge
URL: https://liveplusplus.tech/docs/documentation.html
Saved: livepp.txt (copy of the claim7 fetch)
Kind: vendor doc
Quote: "The Agent ships as a small shared library (e.g. .dll on Windows and Xbox) which is loaded into the target application"
Quote: "Bridge and Broker communicate with each other via TCP/IP using the host name or IP address configured in the global preferences on port 12216."
Note: The commercial existence proof for the remote half: a broker on the developer machine, an agent inside the running target process, a network link between them, and console support in the product line. Confirms the shape; the console-specific SDK material is not public.

### Linux kernel livepatch — what replacing live code requires
URL: https://docs.kernel.org/livepatch/livepatch.html
Saved: livepatch.html / livepatch.txt (also under claim7)
Kind: kernel doc
Quote: "Only functions that can be traced could be patched."
Quote: "Livepatch works reliably only when the dynamic ftrace is located at the very beginning of the function. The function need to be redirected before the stack or the function parameters are modified in any way. For example, livepatch requires using -fentry gcc compiler option on x86_64."
Note: Live replacement of native code needs a compile-time-reserved patch point in every function, plus a per-task safety argument. It is a build-configuration decision, not a runtime one.

### Zephyr LLEXT (linkable loadable extensions) — loading
URL: https://docs.zephyrproject.org/latest/services/llext/load.html
Saved: llext_load.html / llext_load.txt
Kind: project doc
Quote: "Once an extension is built and the ELF file is available, it can be loaded into the Zephyr application using the LLEXT API, which provides a way to load the extension into memory, access its symbols and call its functions."
Note: The embedded analogue of the remote half. What the target must carry: an ELF file, a loader implementation, and a symbol table to resolve against. The index page at .../llext/index.html is JavaScript-rendered and yielded no body text; the build and load subpages did.

## Not obtained
- A measured Cranelift-vs-LLVM compile-time multiplier from a primary source: not obtained.
- Console devkit deployment documentation: not public. No source exists to cite; the Live++ architecture above is the nearest public evidence.
