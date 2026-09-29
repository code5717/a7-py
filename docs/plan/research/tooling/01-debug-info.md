# Debug information: how a compiled language shows the user their own source

Report 01 of the [debugging, testing and analysis research program](README.md).
Written 2026-09-18; every source below was read that day, and two delegated
lookups (Eiffel/cfront, Elm) were folded in on 2026-09-19.

The question: how does a compiled language let a debugger, a profiler and a
crash report show the user their own source, and what must a compiler emit to
make that work? A7 compiles to Zig and then to a native binary, and today the
binary contains no reference to any `.a7` file at all, so a user debugging a
crash sees generated Zig they never wrote
(`docs/audits/2026-09-18/production-readiness.md`, PRD-7).

**The answer, up front.** Everything a native debugger, profiler or crash report
shows the user comes from one artifact: the DWARF line-number program, which maps
each instruction address to a file, a line and a column, plus the declaration
coordinates and variable location expressions hung off the DIE tree. A compiler
that wants the user's own file names in that table has three ways to get them:
emit the DWARF itself, feed a downstream compiler a line directive it already
understands (C's `#line`), or rewrite the table afterwards. Zig offers the first
only to its own backend and the second not at all — the language has no `#line`,
and the request for one was rejected upstream on 2026-04-21 (§2.4).

For A7 that splits into three different crashes needing three different answers
(§5.5): a panic A7's own backend emits, where a baked-in `file:line` constant
works and survives `-fstrip`; a Zig safety check, which passes only a return
address and so needs a map plus a runtime DWARF lookup, in Debug and ReleaseSafe
only; and a ReleaseFast fault, which today prints nothing at all. The
recommendation is therefore three deliverables in order: build the
file-identified span map the plan already schedules, bake A7 `file:line` into
every panic A7 emits, and ship `a7 symbolize` to translate a pasted trace
offline. Full stepping and variable inspection need more — rewriting the emitted
`.debug_line` (§8d) or a Cython-style debugger plugin (§8c) — and the demo in §7
prices both: each generated A7 compilation unit has a **one-entry** DWARF file
table whose single string is `004_func.zig`, and the variables in it already
carry the user's own A7 names.

**Not covered here.** Runtime sanitizers and hardware tagging are in
[`docs/lang-safety/02-sanitizers.md`](../../../lang-safety/02-sanitizers.md) and
[`03-hardware.md`](../../../lang-safety/03-hardware.md); this report cites them
rather than repeating them. Profilers as instruments (sampling, tracing,
coverage) are report 04; this report covers only the part of a profiler's job
that debug information supplies — turning an address back into a source line.
LSP and DAP are report 05.

**Sources.** Every quotation below was fetched to
`tmp/research/debug-info/sources/` on 2026-09-18 and quoted from the local copy;
`tmp/research/debug-info/manifest.txt` lists each URL, the date and the local
file. Commands and raw output for the demo in section 7 are in
`tmp/research/debug-info/demo-commands.md` and the `demo/`, `cdemo/` and
`override/` directories beside it.

---

## 1. DWARF, from the producer's side

### 1.1 The line-number program is the whole game

DWARF's address-to-source mapping is conceptually a matrix and physically a
bytecode. From the DWARF 5 standard, §6.2 (<https://dwarfstd.org/doc/DWARF5.pdf>,
read 2026-09-18, page 149):

> If space were not a consideration, the information provided in the
> `.debug_line` section could be represented as a large matrix, with one row for
> each instruction in the emitted object code. The matrix would have columns for:
> • the source file name • the source line number • the source column number
> • whether this instruction is the beginning of a source statement • whether
> this instruction is the beginning of a basic block • and so on
> Such a matrix, however, would be impractically large. We shrink it with two
> techniques. First, we delete from the matrix each row whose file, line, source
> column and discriminator is identical with that of its predecessors. […]
> Second, we design a byte-coded language for a state machine and store a stream
> of bytes in the object file instead of the matrix.

The registers a producer drives are listed in Table 6.3 (pages 150-151). The four
that matter to a source-language front end:

> `file` An unsigned integer indicating the identity of the source file
> corresponding to a machine instruction.
> `line` An unsigned integer indicating a source line number. Lines are numbered
> beginning at 1. The compiler may emit the value 0 in cases where an
> instruction cannot be attributed to any source line.
> `column` An unsigned integer indicating a column number within a source line.
> Columns are numbered beginning at 1. The value 0 is reserved to indicate that
> a statement begins at the "left edge" of the line.
> `is_stmt` A boolean indicating that the current instruction is a recommended
> breakpoint location. A recommended breakpoint location is intended to
> "represent" a line, a statement and/or a semantically distinct subpart of a
> statement.

`is_stmt` is the register a language implementer under-estimates. It is not
decoration: it is what a debugger uses to decide where `break file:line` lands
and where `step` stops. Two more registers, `prologue_end` and `epilogue_begin`,
mark "where execution should be suspended for a breakpoint at the entry of a
function" and just before exit — that is how `break main` skips the frame setup.

### 1.2 The line-program header carries the file table

The header (§6.2.4, pages 157-158) is where the file names themselves live. Two
of its fields are the ones a source-to-source compiler cares about:

> 18. `file_name_entry_format` (sequence of ULEB128 pairs) A sequence of file
> entry format descriptions. Each description consists of a pair of ULEB128
> values: • A content type code (see below) • A form code using the attribute
> form codes
> […]
> 20. `file_names` (sequence of file name entries) […] The first entry in the
> sequence is the primary source file whose file name exactly matches that given
> in the `DW_AT_name` attribute in the compilation unit debugging information
> entry.

And the DWARF 5 change that matters, stated in the standard's own non-normative
note:

> Prior to DWARF Version 5, the current compilation file name was not
> represented in the `file_names` field. In DWARF Version 5, the current
> compilation file name is explicitly present and has index 0. This is needed to
> support the common practice of stripping all but the line number sections
> (`.debug_line` and `.debug_line_str`) from an executable.

That note is A7-relevant twice over. It says the file table is self-contained in
DWARF 5, so a rewriter does not have to keep `.debug_info` in sync to fix the
line table; and it names the practice — ship a binary with only `.debug_line`
kept — that gives file-and-line without the cost of full debug info.

### 1.3 Subprograms, scopes and declaration coordinates

`DW_TAG_subprogram` is the DIE for a function; `DW_TAG_lexical_block` nests
scopes inside it; both carry address ranges (`DW_AT_low_pc`/`DW_AT_high_pc` or
`DW_AT_ranges`). The link back to source text is §2.14, "Declaration
Coordinates" (page 50):

> Any debugging information entry representing the declaration of an object,
> module, subprogram or type may have `DW_AT_decl_file`, `DW_AT_decl_line` and
> `DW_AT_decl_column` attributes, each of whose value is an unsigned integer
> constant. The value of the `DW_AT_decl_file` attribute corresponds to a file
> number from the line number information table for the compilation unit
> containing the debugging information entry and represents the source file in
> which the declaration appeared (see Section 6.2 on page 148). The value 0
> indicates that no source file has been specified.

Note the coupling: `DW_AT_decl_file` is an *index into the line table's file
table*, not a string. Rewrite the file table and every `DW_AT_decl_file` in the
unit follows for free. That is a load-bearing fact for option (d) in section 8.

### 1.4 Variable locations, and why a variable is unavailable at `-O2`

§2.6 (page 38):

> Information about the location of program objects is provided by location
> descriptions. Location descriptions can be either of two forms:
> 1. Single location descriptions […] They are sufficient for describing the
> location of any object as long as its lifetime is either static or the same as
> the lexical block that owns it, and it does not move during its lifetime.
> 2. Location lists, which are used to describe objects that have a limited
> lifetime or change their location during their lifetime.

The spec's own name for "optimized out" is the empty location description
(§2.6.1.1.1, page 39):

> An empty location description consists of a DWARF expression containing no
> operations. It represents a piece or all of an object that is present in the
> source but not in the object code (perhaps due to optimization).

And for a partially-covered location list (§2.6.2, page 43):

> If all of the address ranges in a given location list do not collectively
> cover the entire range over which the object in question is defined, and there
> is no following default location description, it is assumed that the object is
> not available for the portion of the range that is not covered.

So "optimized out" is not a debugger failure; it is the format faithfully
reporting that the optimizer deleted the thing. LLVM's
`HowToUpdateDebugInfo.html` (<https://llvm.org/docs/HowToUpdateDebugInfo.html>,
read 2026-09-18) states the mechanism from inside the optimizer:

> When an Instruction is deleted, its debug uses change to undef. This is a loss
> of debug info: the value of one or more source variables becomes unavailable,
> starting with the `#dbg_value(undef, ...)`. When there is no way to
> reconstitute the value of the lost instruction, this is the best possible
> outcome. However, it's often possible to do better: If the dying instruction
> can be RAUW'd, do so. […] If the dying instruction cannot be RAUW'd, call
> `llvm::salvageDebugInfo` on it. This makes a best-effort attempt to rewrite
> debug uses of the dying instruction by describing its effect as a
> `DIExpression`.

The same document is explicit that dropping a *location* is sometimes the
correct answer, and why:

> A transformation should drop debug locations if the rules for preserving and
> merging debug locations do not apply. The API to use is
> `Instruction::dropLocation()`. The purpose of this rule is to prevent erratic
> or misleading single-stepping behavior in situations in which an instruction
> has no clear, unambiguous relationship to a source location.

and on merged instructions:

> The purpose of this rule is to ensure that a) the single merged instruction
> has a location with an accurate scope attached, and b) to prevent misleading
> single-stepping (or breakpoint) behavior. Often, merged instructions are
> memory accesses which can trap: having an accurate scope attached greatly
> assists in crash triage by identifying the (possibly inlined) function where
> the bad memory access occurred.

That paragraph is the best short argument in the literature for why a
source-to-source compiler should not simply emit *any* plausible line: a wrong
line is worse than no line, because the debugger cannot tell it is wrong.

### 1.5 Inlined frames

DWARF 5 §3.3.8.2 (page 83):

> Each inline expansion of a subroutine is represented by a debugging
> information entry with the tag `DW_TAG_inlined_subroutine`. Each such entry is
> a direct child of the entry that represents the scope within which the
> inlining occurs. […] An inlined subroutine entry may also have
> `DW_AT_call_file`, `DW_AT_call_line` and `DW_AT_call_column` attributes, each
> of whose value is an integer constant. These attributes represent the source
> file, source line number, and source column number, respectively, of the first
> character of the statement or expression that caused the inline expansion.

`DW_AT_call_file` is again an index into the same file table. Section 7 shows a
real `DW_TAG_inlined_subroutine` with `DW_AT_call_file: 43` in an A7-generated
release binary.

### 1.6 What is cheap and what is real work

| DWARF part | Effort for a producer | What the user gets |
| --- | --- | --- |
| Line-program header + file table | **Cheap.** A handful of strings and ULEB128 counts; DWARF 5 makes it self-contained. | The file name shown in traces and `list` |
| Line-number program rows (file, line, `is_stmt`) | **Cheap to do badly, moderate to do well.** One row per statement is easy; correct `is_stmt`, `prologue_end` and non-monotonic rows need thought. | Panic lines, breakpoints by line, profiler attribution |
| `DW_AT_decl_file/line/column` on subprograms | **Cheap.** Three integer attributes per DIE, and the file is an index you already have. | Right file in `info functions`, `break func` |
| `DW_TAG_subprogram` + `DW_TAG_lexical_block` ranges | **Moderate.** You must know each scope's address range, which means cooperating with the code generator. | Scoped variable lookup, correct `frame` display |
| Variable location expressions (`DW_AT_location`) | **Real work at -O0, hard at -O2.** At -O0 a frame-base offset per variable. Under optimization it is location lists that must track every move, and `salvageDebugInfo`-style upkeep in every transform. | `print x`, `frame variable` |
| Type DIEs | **Real work.** The whole type graph, deduplicated. | Typed values instead of raw words |
| `DW_TAG_inlined_subroutine` + call coordinates | **Hard.** Requires the inliner to report what it did. | Correct stack traces in optimized builds |

INFERENCE: for A7 the first four rows are reachable without owning a backend
(sections 8b–8d); the last three are not, because the Zig compiler and LLVM, not
A7, decide where values live and what gets inlined.

---

## 2. The two-stage problem: a language that compiles to another language's source

### 2.1 C's `#line`, and exactly what it preserves

The C standard specifies only the *presumed* position, not debug info. ISO/IEC
9899:2024 working draft N3220 §6.10.6
(<https://www.open-std.org/jtc1/sc22/wg14/www/docs/n3220.pdf>, read 2026-09-18,
page 185):

> A preprocessing directive of the form `# line digit-sequence new-line` causes
> the implementation to behave as if the following sequence of source lines
> begins with a source line that has a line number as specified by the digit
> sequence […]. A preprocessing directive of the form
> `# line digit-sequence " s-char-sequence_opt " new-line` sets the presumed
> line number similarly and changes the presumed name of the source file to be
> the contents of the character string literal.

GCC's manual states the intent and the limits (Line Control,
<https://gcc.gnu.org/onlinedocs/cpp/Line-Control.html>, read 2026-09-18):

> If you write a program which generates source code, such as the bison parser
> generator, you may want to adjust the preprocessor's notion of the current
> file name and line number by hand. […] You would like compiler error messages
> and symbolic debuggers to be able to refer to bison's input file. bison or any
> such program can arrange this by writing '#line' directives into the output
> file.

and, for what it does *not* do:

> '#line' directives alter the results of the `__FILE__` and `__LINE__`
> predefined macros from that point on. […] They do not have any effect on
> '#include''s idea of the directory containing the current file.

So `#line` gives file, line and — through the compiler's ordinary debug-info
path — the DWARF line table and `DW_AT_decl_file`. It does **not** give columns
(there is no `#column`), does not rename anything, does not carry scopes, and
cannot describe a generated construct that has no origin line at all. Section
2.2 shows how Vala handles that last gap.

**Demonstrated, not assumed** (`tmp/research/debug-info/cdemo/`, 2026-09-18).
Five lines of C claiming to be A7:

```c
#include <stdio.h>
#line 5 "hello.a7"
int add(int x, int y) { return x + y; }
#line 9 "hello.a7"
int main(void) { printf("%d\n", add(2, 3)); return 0; }
```

```
$ zig cc -g -O0 gen.c -o gen_zigcc
$ readelf --debug-dump=decodedline gen_zigcc | grep -iE "hello.a7|gen.c" | head -6
CU: hello.a7:
hello.a7                                   5           0x101df90               x
hello.a7                                   5           0x101df9e               x
hello.a7                                   5           0x101dfa4
hello.a7                                   5           0x101dfaa
hello.a7                                   0           0x101dfb8
```

The `x` column is `is_stmt`; the `0` line is the "cannot be attributed to any
source line" case from §1.1. The compilation-unit DIE shows the split precisely:

```
 <0><b>: Abbrev Number: 1 (DW_TAG_compile_unit)
    <c>   DW_AT_producer    : clang version 21.1.0
    <10>   DW_AT_language    : 29	(C11)
    <12>   DW_AT_name        : gen.c
    <1a>   DW_AT_comp_dir    : /home/cx89/.../cdemo
 <1><2a>: Abbrev Number: 2 (DW_TAG_variable)
    <2f>   DW_AT_decl_file   : 1
    <30>   DW_AT_decl_line   : 9
```

`DW_AT_name` stays `gen.c` — the file the compiler was actually handed — while
the line table and `DW_AT_decl_file` point at `hello.a7`. A `#line`-based scheme
therefore leaves one honest trace of the real input and redirects everything the
user sees. This same toolchain, `zig cc`, does this for C today; it cannot do it
for Zig (section 2.3).

### 2.2 Who uses it

| Language | Mechanism | Source (read 2026-09-18) |
| --- | --- | --- |
| **Vala** | Emits `#line` into the generated C, including a *reset* directive when generated code has no Vala origin | Compiler source, below |
| **Nim** | `--lineDir:on` emits `#line` into generated C; `--debugger:native` selects "use native debugger (gdb)" | `nim-lang.org/docs/nimc.html` |
| **Cython** | Both: `--line-directives` emits `#line` into the generated C, *and* `--gdb` exports a side-car debug description for the `cygdb` plugin | `Cython/Compiler/CmdLine.py`; `docs.cython.org/.../debugging.html` |
| **f2c** | `-g` "Include original Fortran line numbers in `#line` lines." | `netlib.org/f2c/f2c.1` |
| **Haxe** | Targets JS: source maps, not `#line` | `haxe.org/manual/debugging-source-map.html` |
| **Eiffel** (ISE EiffelStudio, Gobo `gec`) | A "line generation" setting emits `#line <n> "<eiffel-file>"` into the generated C. Liberty Eiffel and SmartEiffel do **not**; they ship their own `-sedb` debugger instead. | Grok lookup, below |
| **cfront** | Emitted line markers into the generated C from its first release; `+L` switched them to the `#line` spelling. | Grok lookup, below |
| **Modula-3** (SRC, C-generating era), **Sather** | Both emitted or documented C-level line mapping to the original source. | Grok lookup, below |

Vala, verbatim from `ccode/valaccodewriter.vala`
(<https://raw.githubusercontent.com/GNOME/vala/main/ccode/valaccodewriter.vala>,
read 2026-09-18):

```vala
	public void write_indent (CCodeLineDirective? line = null) {
		if (line_directives) {
			if (line != null) {
				line.write (this);
				using_line_directive = true;
			} else if (using_line_directive) {
				// no corresponding Vala line, emit line directive for C line
				write_string ("#line %d \"%s\"".printf (current_line_number + 1, Path.get_basename (filename)));
				write_newline ();
				using_line_directive = false;
			}
		}
```

That `else if` branch is the part every generator gets wrong first: when the
emitted code has no user-source origin, you must point the directive back at the
generated file rather than leave the previous user line in force. Otherwise a
crash inside compiler-generated glue is reported at an innocent user line — the
"misleading" failure LLVM warns about in §1.4.

`valac(1)` documents the switch only as `-g, --debug  Produce debug information`
(<https://man.archlinux.org/man/valac.1>, read 2026-09-18); the mechanism is
visible only in the source above.

**The historical compile-to-C languages, from a Grok lookup**
(`tmp/ai/linedirs-history.md`, 2026-09-18). **UNVERIFIED** — I did not read these
sources myself; they are recorded here because they answer the brief's question
about Eiffel and cfront, and because two of them bear on A7 directly.

- **cfront** emitted line control from the start. The lookup quotes
  `lex.c`'s `void loc::putline() { … fprintf(out_file,line_format,line,f); … }`
  and `main.c`'s `char* line_format = "\n# %d \"%s\"\n";`, with
  `case 'L': line_format = "\n#line %d \"%s\"\n";` — that is, the **default**
  was the bare cpp linemarker `# N "file"` and the `#line` spelling was opt-in
  under `+L`, while AT&T's `CC(1)` man page calls them "#line directives"
  regardless. The lookup flags that implementation/documentation disagreement
  itself (<https://www.tuhs.org/cgi-bin/utree.pl?file=V9/cmd/cfront/cfront/main.c>,
  <https://softwarepreservation.computerhistory.org/c_plus_plus/cfront/release_3.0.3/source/man/man1/CC.1>).
- **Stroustrup rejected the "you can't debug a translator's output" claim**, in a
  January 1989 DDJ interview the lookup quotes: "One of the things that people
  have said about the translators is that you can't do symbolic debugging.
  That's just plain wrong because the information is passed through to the
  second pass and you can do debugging of C++ at the source level. Using the 2.0
  translator we're doing that. That 1.2 versions didn't have quite enough finesse
  to do it, and people didn't invest enough in modifying debuggers and the
  system-build operations to give good symbolic debugging."
  (<https://www.stroustrup.com/From-C-to-Cpp-bs.pdf>). The cost he does not
  dispute is the one A7 shares: cfront mangled names and invented temporaries in
  the generated C, and AT&T shipped `-gdem` and a `demangle(1)` tool so that
  "tools such as symbolic debuggers and profilers [can] be used more easily".
- **Eiffel** splits. ISE EiffelStudio has a per-target "Line generation" option,
  and the lookup traces it to `BYTE_NODE.generate_line_info`:
  `if line_number > 0 and then System.line_generation then` … with
  `LINE_INFO: STRING = "#line "`. Gobo's `gec` added the same as an ECF setting —
  "Added support for the ECF setting `line_generation`, with preprocessor
  statements `#line` now included in the generated C code" (Gobo `History.md`,
  22.01.09.4). Liberty Eiffel and SmartEiffel took the other road: no `#line`
  anywhere in their C backends, and a bundled source-level debugger, `-sedb`,
  instead.
- **Modula-3's SRC compiler, in its C-generating era,** is the closest
  documented parallel to A7 and the most sobering. Per the lookup, its 2.07
  manual described emitting `#line` liberally so a C debugger would report
  Modula-3 file names and line numbers — *and in the same section* noted that
  stock C debug info still relates the executable to the generated C, not to
  Modula-3. Bill Kalsow's later history is quoted as agreeing that line numbers
  worked while data-structure debug info was "almost non-existent", and by 3.6
  the documentation had switched to "use `m3gdb`, not a stock C debugger".
  **INFERENCE:** that is the ceiling of any line-directive scheme, including the
  line-table rewrite in option (d) — it fixes *where you are*, never *what your
  values are*, and the language eventually needs its own tooling anyway.

Nim's manual describes both halves, and is careful that the line directive is a
*debugging aid*, not the stack-trace mechanism
(<https://nim-lang.org/docs/nimc.html>, read 2026-09-18):

> **LineDir option** — The `--lineDir` option can be turned on or off. If turned
> on the generated C code contains `#line` directives. This may be helpful for
> debugging with GDB.
> **StackTrace option** — If the `--stackTrace` option is turned on, the
> generated C contains code to ensure that proper stack traces are given if the
> program crashes or some uncaught exception is raised.
> **LineTrace option** — The `--lineTrace` option implies the stackTrace option.
> If turned on, the generated C contains code to ensure that proper stack traces
> with line number information are given if the program crashes or an uncaught
> exception is raised.

Nim therefore ships *both* traditions at once: `#line` for the debugger, and an
explicit runtime shadow stack for crash traces. Cython does the same, by a
different pairing (`--line-directives` for the C compiler's DWARF,
`--gdb` plus `cygdb` for everything else). That combination — a cheap mechanism
that names the user's file when the program dies, plus a separate, richer one for
interactive debugging — is the single most transferable design in this section,
and it is the shape of the recommendation in section 8.

Cython ships both traditions too, and the side-car half is the most relevant
precedent for A7 because it does not try to make a stock debugger understand the
generated language. The `#line` half is one CLI switch
(<https://raw.githubusercontent.com/cython/cython/master/Cython/Compiler/CmdLine.py>,
read 2026-09-18):

```python
    parser.add_argument("--line-directives", dest='emit_linenums', action='store_true',
                      help='Produce #line directives pointing to the .pyx source')
```

The side-car half is separate and richer. From the Cython debugging guide
(<https://docs.cython.org/en/latest/src/userguide/debugging.html>, read
2026-09-18):

> The debugger will need debug information that the Cython compiler can export.
> This can be achieved from within the setup script by passing `gdb_debug=True`
> to `cythonize()` […] When invoking Cython from the command line directly you
> can have it write debug information using the `--gdb` flag […] To run the
> Cython debugger and have it import the debug information exported by Cython,
> run `cygdb` in the build directory

What the plugin then provides is a complete parallel command set — not a subset:

> `cy break` Break in a Python, Cython or C function. […] You can also break on
> Cython line numbers: `(gdb) cy break :14`
> `cy step` Step through Python, Cython or C code. […]
> `cy print varname` Print a local or global Cython, Python or C variable
> (depending on the context).
> `cy locals` / `cy globals` Print all the local and global variables and their
> values.
> `cy list` List the source code surrounding the current line.

So a side-car file plus a debugger plugin buys breakpoints by original line,
stepping, and variable inspection in the original language's terms. It does not
buy any of that for a user who runs plain `gdb`.

### 2.3 Own-the-backend languages, for contrast

**GHC** emits DWARF directly and extends it. From the GHC users guide
(<https://ghc.gitlab.haskell.org/ghc/doc/users_guide/debug-info.html>, read
2026-09-18):

> `-g⟨n⟩` Emit debug information in object code. Currently only DWARF debug
> information is supported on x86-64 and i386. Currently debug levels 0 through
> 3 are accepted: `-g0`: no debug information produced; `-g1`: produces stack
> unwinding records for top-level functions (sufficient for basic backtraces);
> `-g2`: produces stack unwinding records for top-level functions as well as
> inner blocks (allowing more precise backtraces than with `-g1`); `-g3`:
> produces GHC-specific DWARF information for use by more sophisticated
> Haskell-aware debugging tools

and its vendor extension, which exists precisely because a lazy functional
language's code does not correspond to one source line:

> `DW_TAG_ghc_src_note` DIEs (tag 0x5b01) are found as children of
> `DW_TAG_lexical_block` DIEs. They describe source spans which gave rise to the
> block; formally these spans are causally responsible for produced code:
> changes to code in the given span may change the code within the block;
> conversely changes outside the span are guaranteed not to affect the code in
> the block.

A7 has the same shape of problem in miniature — one A7 `for` header becomes
several Zig lines — and GHC's answer (a *span*, with an explicit causal
definition, rather than a point) is the right mental model for what A7's map
entries should hold.

**Kotlin/Native** owns an LLVM backend and gets everything, with one instructive
wart (<https://kotlinlang.org/docs/native-debugging.html>, read 2026-09-18):

> The debug information is compatible with the DWARF 2 specification, so modern
> debugger tools, like LLDB and GDB can: Set breakpoints; Use stepping; Inspect
> variable and type information. Supporting the DWARF 2 specification means that
> the debugger tool recognizes Kotlin as C89, because before the DWARF 5
> specification, there is no identifier for the Kotlin language type in the
> specification.

Its breakpoints are set on `hello.kt:2` and `fr var` prints Kotlin values — the
full prize. For crash reports it uses split debug info:

> The Kotlin/Native compiler generates `.dSYM` files for release (optimized)
> binaries on Apple platforms by default. […] On other platforms, you can add
> debug information into the produced binaries (which increases their size)
> using the `-Xadd-light-debug` compiler option

**Scala Native.** The sbt page I read myself
(<https://scala-native.org/en/latest/user/sbt.html>, read 2026-09-18) documents
linking modes ("debug. (default) […] Similar to clang's `-O0`") and says nothing
about DWARF. The rest of this paragraph is a **Grok lookup**
(`tmp/ai/dbg-scalanative.md`, 2026-09-18) and is **UNVERIFIED** — I did not read
these files or pages directly:

- The user-facing switch is `nativeConfig ~= { c =>
  c.withSourceLevelDebuggingConfig(_.enableAll).withOptimize(false).withMode(Mode.debug) }`,
  documented at <https://scala-native.org/en/latest/user/testing.html>; it is off
  by default and was introduced in 0.5.0.
- The toolchain passes clang `-gdwarf-4` when it is enabled, per
  `tools/.../build/LLVM.scala`: "newer LLVM uses DWARFv5 by default on Linux. We
  support only DWARFv4 for now", and codegen emits `DIFile`, `DISubprogram`,
  `DILocation`, `DILocalVariable` metadata.
- Compile units are tagged `DW_LANG_C_plus_plus` with a TODO to "update once SN
  has its own DWARF language code" — the same borrowed-language-code wart as
  Kotlin/Native, and as A7's own binaries in §7.
- The documented limitations are that the feature is "initial support", that the
  Scala Native and LLVM optimizers "can remove some of the optimized out debug
  information", and that macOS exception traces give approximated lines ("best
  effort, might not point to exact line, but rather to function definitions").
  Official debugger guidance is LLDB; the lookup found no mention of gdb.

The transferable point, if it holds: a language that owns its LLVM backend still
ships source-level debugging *off by default*, with an explicit
"disable the optimizer too" instruction, because optimized builds lose the
information anyway (§1.4, §4.2).

### 2.4 Does Zig have an equivalent of `#line`? No.

Three independent checks, all negative.

**The language reference.** The Zig 0.16.0 language reference
(<https://ziglang.org/documentation/0.16.0/>, fetched 2026-09-18, 18,128 lines
of extracted text) contains no occurrence of `#line`; the only match for
"directive" in the whole document is inside an unrelated `zig cc` command line.
The master reference (<https://ziglang.org/documentation/master/>, same date)
contains zero occurrences of either. The only source-position facility the
language exposes is `@src`:

> `@src() std.builtin.SourceLocation` — Returns a `SourceLocation` struct
> representing the function's name and location in the source code. This must be
> called in a function.

and it reports the position in the **Zig** file, as its own test in the
reference shows (`src.line == 10`, `src.file` ends with
`test_src_builtin.zig`). There is no way to set it.

**The issue tracker.** `ziglang/zig` issue 1833, "source maps", opened
2018-12-15, closed **2026-04-21** (read via `gh issue view 1833`, 2026-09-18).
The request:

> I'm not a Zig user (yet), but I was wondering if Zig had anything similar to
> the [line control macros](https://gcc.gnu.org/onlinedocs/cpp/Line-Control.html)
> that you see in GCC. I am very interested in using writing programs in Zig
> using [my literate programming environment], which utilize these macros to
> make debugging possible.

The 2018 answer from thejoshwolfe:

> Line control macros do not exist in Zig. There is no current plan to implement
> them, but there probably should be. The line control macros should probably be
> in Zig comments, rather than being "macros" (which Zig doesn't have), keywords
> and first-class syntactic constructs, or a builtin functions. […] Line control
> macros can be generalized into source maps.

The 2026 closure from mlugg, which is the current upstream position and should
be treated as settling the question:

> Rejected for a few reasons. Zig is primarily a human-to-programming-language
> interface rather than a programming-language-to-programming-language
> interface. Additionally, if generating Zig code, it is preferable to generate
> readable Zig code where possible so that this feature is unnecessary. Lastly,
> this would incur a non-trivial language complexity cost due to Zig lacking any
> kind of preprocessor.

A 2025 comment on the same issue sketches what a Zig-idiomatic version would
have looked like — a `pub const source_location_map: std.builtin.SourceLocationMap`
declaration at file scope, "store that information separately as a data
structure, and emit it at the end" rather than `#line` noise inline — and argues
against directives on their own terms:

> `#line` directives kinda suck, they make the generated code really noisy and
> they force one-pass generation, there's extra book-keeping for the file
> itself, and besides, (fortunately) Zig doesn't have the preprocessor mechanism
> anyway so there's no obvious way to do it outside of magic comments (which
> should be resisted).

Searches for `"#line"`, `source map`, `transpiler debug info` and
`generated code line numbers` across `ziglang/zig` issues (2026-09-18) surfaced
no other proposal; 1833 is the only one, and it is closed as rejected.

**The compiler's own DWARF writer.** `src/link/Dwarf.zig` at master commit
`738d2be9d6b6ef3ff3559130c05159ef53336224` (read 2026-09-18; the released tags
stop at 0.15.2, so 0.16.0 here is a development build) builds the line-program
header from the module's own file paths. INFERENCE, from a grep of that file for
`LNCT`, `file_names` and `debug_line`: no hook to override the emitted file name
was found, and the path string's origin was not traced further. It does use one
interesting extension in that header — `DW.LNCT.LLVM_source` —
which embeds source *text* in `.debug_line_str`; section 7 shows the effect.

**A fourth check, secondary.** A Grok lookup run for this report
(`tmp/ai/grok-smoke2.md`, 2026-09-18) reaches the same conclusion from a
different source and is recorded here as corroboration, not as primary reading —
**UNVERIFIED**, since I did not open the thread myself: it quotes dimdin on
Ziggit, "No, there is no way to set the filename or the line number"
(<https://ziggit.dev/t/file-line-equivalents-in-generated-zig-files/6954>), and
makes the structural point that Zig has no preprocessing step at all, so there is
no stage at which a directive could act. That matches the language reference
directly: `@src()` is documented as returning "the function's name and location
in the source code", with no way to set either.

**Conclusion.** For A7 there is no `#line`. The alternatives, in ascending cost,
are: a side-car map consumed by A7's own tooling; a panic-time translation using
Zig's documented panic extension points; a debugger plugin in Cython's style;
post-processing the emitted `.debug_line`; emitting C with `#line` through
`zig cc` instead of Zig; and owning DWARF emission outright. Section 8 prices
each.

---

## 3. Source maps, the other tradition

### 3.1 What the format is for

Source maps are now an Ecma standard. ECMA-426, 1st edition
(<https://tc39.es/ecma426/>, read 2026-09-18), Introduction:

> This Ecma Standard defines the Source map format, used for mapping transpiled
> source code back to the original sources. The source map format has the
> following goals: Support source-level debugging allowing bidirectional
> mapping; Support server-side stack trace deobfuscation.

and §1 Scope:

> This Standard defines the source map format, used by different types of
> developer tools to improve the debugging experience of code compiled to
> JavaScript, WebAssembly, and CSS.

The history, in the standard's own words, explains the version numbering
confusion:

> The original source map format (v1) was created by Joseph Schorr for use by
> Closure Inspector […] The v2 format […] was created by trading some simplicity
> and flexibility to reduce the overall size of the source map. […] The v3
> format is based on suggestions made by Pavel Podivilov (Google). The source
> map format does not have version numbers anymore, and it is instead hard-coded
> to always be "3". In 2023-2024, the source map format was developed into a
> more precise Ecma standard

### 3.2 What it can express

The whole payload is a JSON object with a handful of fields (§7, ECMA-426):

> The `sources` field is a list of original sources used by the `mappings`
> field. […]
> The `sourcesContent` field is an optional list of source content (i.e. the
> original source) strings, used when the source cannot be hosted. […]
> The `names` field is an optional list of symbol names which may be used by the
> `mappings` field.
> The `mappings` field is a string with the encoded mapping data […]
> The `ignoreList` field is an optional list of indices of files that should be
> considered third party code, such as framework code or bundler-generated code.
> This allows developer tools to avoid code that developers likely don't want to
> see or step through

A mapping segment is one to five VLQ numbers, and the standard states what each
arity means — including the case A7 would hit constantly, generated code with no
original:

> Segments with one field are intended to represent generated code that is
> unmapped because there is no corresponding original source code, such as code
> that is generated by a compiler. Segments with four fields represent mapped
> code where a corresponding name does not exist. Segments with five fields
> represent mapped code that also has a mapped name.

`sourcesContent` is worth flagging for A7: the format anticipates that the
original source will not be on the machine where debugging happens and lets the
producer embed it. DWARF's `DW_LNCT_LLVM_source` (section 2.4, 7) is the same
idea in the other tradition.

### 3.3 What it cannot express — per its own authors

The limits are not inferred here; they are the stated motivation of the
committee's own Stage 3 extension proposal. From
`proposals/scopes.md` in `tc39/ecma426`
(<https://raw.githubusercontent.com/tc39/ecma426/main/proposals/scopes.md>, read
2026-09-18), authors Holger Benl and Simon Zünd:

> Currently source maps enable a debugger to map locations in the generated
> source to corresponding locations in the original source. This allows the
> debugger to let the user work with original sources when adding breakpoints
> and stepping through the code. However, this information is generally
> insufficient to reconstruct the original frames, scopes and bindings:
> - when the debugger is paused in a function the was inlined, the stack doesn't
>   contain a frame for the inlined function but the debugger should be able to
>   reconstruct that frame
> - the debugger should be able to reconstruct scopes that were removed by the
>   compiler
> - the debugger should be able to hide scopes that were added by the compiler
> - when a variable was renamed in the generated source, the debugger should be
>   able to get its original name; this is possible with the current source maps
>   format by looking for mappings that map the declaration of a generated
>   variable to one of an original variable and optionally using the `names`
>   array, but this approach requires parsing the sources, is hard to implement
>   and experience shows that it doesn't work in all situations
> - the debugger should be able to reconstruct original bindings that have no
>   corresponding variables in the generated source
> - the debugger should be able to hide generated bindings that have no
>   corresponding variables in the original source
> - it should be possible to find the original function names for frames in a
>   stack trace

That list is the honest statement of what a position-only map buys and what it
does not: positions and (weakly) names, never values, scopes, frames or stepping
semantics. The repository README
(<https://raw.githubusercontent.com/tc39/source-map/main/README.md>, read
2026-09-18) records Scopes at **Stage 3**, with Range Mappings and Debug ID at
Stage 2 and Env at Stage 1 — that is, after fourteen years the format is only
now acquiring what DWARF had in 1992.

### 3.4 Who produces and consumes them

- **TypeScript**: `sourceMap` in `tsconfig`; `inlineSources` "will include the
  original content of the `.ts` file as an embedded string in the source map
  (using the source map's `sourcesContent` property)"
  (<https://www.typescriptlang.org/tsconfig/>, read 2026-09-18).
- **Babel**: `sourceMaps`, `Type: boolean | "inline" | "both"`, `Default: false`
  (<https://babeljs.io/docs/options>, read 2026-09-18).
- **ClojureScript**: `:source-map` is a documented compiler option, used in the
  advanced-optimizations example config
  (<https://clojurescript.org/reference/compiler-options>, read 2026-09-18).
- **Haxe**: "Haxe is able to generate source maps, allowing debuggers to map
  from a generated source back to the original Haxe source. This makes reading
  error stack traces, debugging with breakpoints, and profiling much easier. […]
  Compiling with the `-debug` flag will create a source map (`.map`) file
  alongside the `.js` file."
  (<https://haxe.org/manual/debugging-source-map.html>, read 2026-09-18).
- **Elm**: **it does not**, and the reasoning is the most interesting thing in
  this section. This paragraph is a **Grok lookup** (`tmp/ai/elm-sourcemaps.md`,
  2026-09-18) and is **UNVERIFIED** — I did not open these pages myself. The
  lookup reports that `elm make` has no source-map flag (documented flags are
  `--debug`, `--optimize`, `--output`, `--report`, `--docs`), that the JS code
  generator emits no `sourceMappingURL` and no `.map` side-car, and that the JS
  printer's AST carries no original Elm source locations at all, so it could not
  encode mappings even if asked. The request is `elm/compiler` issue #1273,
  "javascript sourcemaps", opened 2016-02-01 and closed by Evan Czaplicki eleven
  days later with this reasoning:

  > Having talked to pretty much all companies using Elm in production, I have
  > never heard this feature requested from them. If we were ClojureScript or
  > TypeScript where you would see runtime errors in practice, this would make a
  > ton more sense. For the existing production users of Elm, they just do not
  > have Elm-related runtime errors, so they never find themselves in a position
  > where they want this feature. […] That said, it could be added, but I'm not
  > sure it makes sense to make the compiler more complicated for a feature that
  > Elm users do not want.

  (quoted by the lookup from a Wayback snapshot of
  <https://github.com/elm/compiler/issues/1273#issuecomment-183518010>; the
  lookup notes later commenters on the thread disagreed, citing breakpoints and
  coverage.) What Elm ships instead is `elm make --debug`: "Turn on the
  time-travelling debugger. It allows you to rewind and replay events."

  **This is a real position, not an oversight, and it bears directly on A7.** A
  language that has designed out the runtime-error class buys less from a source
  map than one that has not — which is an argument A7 could make about its own
  compile-time safety proofs, but *cannot* make yet: A7's crashes today are Zig
  safety panics and faults (§5.5), and they are the thing the user hits first.
  Elm also reaches for a replay debugger rather than a mapping, which is report
  08's subject, not this one.
- **Browsers**: Chrome DevTools documents the workflow as "Debug your original
  code instead of deployed with source maps" and exposes the `ignoreList`
  extension and a Developer Resources panel to "View and manually load source
  maps" (<https://developer.chrome.com/docs/devtools/javascript/source-maps>,
  read 2026-09-18). The map is fetched out-of-band via a `sourceMappingURL`
  comment; ECMA-426 §11 also specifies a WebAssembly custom section, noting that
  "Since WebAssembly is not a textual format and it does not support comments,
  it supports a single unambiguous extraction method."

**Where the traditions differ, stated plainly.** DWARF describes *machine state*
— where a value lives, in which register, over which address range. Source maps
describe *text* — which output character came from which input character. A
native language cannot substitute one for the other: no debugger on Linux reads
a source map, and no browser reads DWARF (excepting the C/C++ WebAssembly
extension, which is out of scope here). For A7 the useful lesson is structural,
not directly reusable: the format that a small team can produce, version and
ship is a positions-and-names table, and everything beyond it costs an order of
magnitude more.

---

## 4. What the debugger does with it

### 4.1 Resolving a source line

Both gdb and lldb do the same two lookups: address → (file index, line) via the
line-number program, then file index → file table entry → a path on disk to
open. The second step is where builds go wrong, because the path recorded is the
build machine's.

GDB's manual on the recorded-versus-actual path problem (Source Path,
<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Source-Path.html>, read
2026-09-18):

> A rule is made of two strings, the first specifying what needs to be rewritten
> in the path, and the second specifying how it should be rewritten. In `set
> substitute-path`, we name these two parts `from` and `to` respectively. GDB
> does a simple string replacement of `from` with `to` at the start of the
> directory part of the source file name, and uses that result instead of the
> original file name to look up the sources.

and why it differs from just adding a search directory:

> `set substitute-path` is also more than just a shortcut command. The source
> path is only used if the file at the original location no longer exists. On
> the other hand, `set substitute-path` modifies the debugger behavior to look
> at the rewritten location instead.

LLDB's equivalent, from its gdb-to-lldb map
(<https://lldb.llvm.org/use/map.html>, read 2026-09-18):

> `(gdb) set pathname-substitutions /buildbot/path /my/path` →
> `(lldb) settings set target.source-map /buildbot/path /my/path`
> […] Supply a catchall directory to search for source files in: `(gdb)
> directory /my/path` — There is no equivalent LLDB command, use
> `target.source-map` instead.

The base against which relative paths resolve is `DW_AT_comp_dir` on the
compilation unit. Section 7 shows A7's release binaries carrying a full absolute
build path there — the leakage the brief asks about.

### 4.2 "Optimized out"

GDB's manual is explicit that this is the compiler's doing, not the debugger's
(Variables,
<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Variables.html>, read
2026-09-18):

> This may also happen when the compiler does significant optimizations. To be
> sure of always seeing accurate values, turn off all optimization when
> compiling. Another possible effect of compiler optimizations is to optimize
> unused variables out of existence, or assign variables to registers (as
> opposed to memory addresses). Depending on the support for such cases offered
> by the debug info format used by the compiler, GDB might not be able to
> display values for such local variables. If that happens, GDB will print a
> message like this: `No symbol "foo" in current context.` To solve such
> problems, either recompile without optimizations, or use a different debug
> info format, if the compiler supports several such formats.

It also warns about the prologue/epilogue window, which is exactly what
`prologue_end` exists to mitigate:

> Warning: Occasionally, a local variable may appear to have the wrong
> value at certain points in a function—just after entry to a new scope, and
> just before exit. […] on most machines, it takes more than one instruction to
> set up a stack frame (including local variable definitions); if you are
> stepping by machine instructions, variables may appear to have the wrong
> values until the stack frame is completely built.

### 4.3 `-Og` and `-fstandalone-debug`

GCC's `-Og` (<https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html>, read
2026-09-18):

> Optimize while keeping in mind debugging experience. `-Og` should be the
> optimization level of choice for the standard edit-compile-debug cycle,
> offering a reasonable blend of optimization, fast compilation and debugging
> experience especially for code with a high abstraction penalty. In contrast to
> `-O0`, this enables `-fvar-tracking-assignments` and `-fvar-tracking` which
> handle debug information in the prologue and epilogue of functions better than
> `-O0`. Like `-O0`, `-Og` completely skips a number of optimization passes so
> that individual options controlling them have no effect. Otherwise `-Og`
> enables all `-O1` optimization flags except for those known to greatly
> interfere with debugging

Clang's `-fstandalone-debug` is about *type* completeness, not variables
(<https://clang.llvm.org/docs/UsersManual.html>, read 2026-09-18):

> Clang supports a number of optimizations to reduce the size of debug
> information in the binary. They work based on the assumption that the debug
> type information can be spread out over multiple compilation units.
> Specifically, the optimizations are: [it] will not emit type definitions for
> types that are not needed by a module and could be replaced with a forward
> declaration […] The `-fstandalone-debug` option turns off these optimizations.
> This is useful when working with 3rd-party libraries that don't come with
> debug information. […] On Darwin `-fstandalone-debug` is enabled by default.

Zig has no `-Og`. Its four modes are `Debug`, `ReleaseSafe`, `ReleaseFast`,
`ReleaseSmall`, and debug info is controlled separately by `-fstrip` — which
section 7 measures.

### 4.4 Split debug info

`-gsplit-dwarf` (<https://gcc.gnu.org/onlinedocs/gcc/Debugging-Options.html>,
read 2026-09-18):

> If DWARF debugging information is enabled, separate as much debugging
> information as possible into a separate output file with the extension `.dwo`.
> This option allows the build system to avoid linking files with debug
> information. To be useful, this option requires a debugger capable of reading
> `.dwo` files.

And `debuginfod`, which is how a distribution ships stripped binaries and still
lets a user debug them
(<https://sourceware.org/gdb/current/onlinedocs/gdb.html/Debuginfod.html>, read
2026-09-18):

> `debuginfod` is an HTTP server for distributing ELF, DWARF and source files.
> With the debuginfod client library, `libdebuginfod`, GDB can query servers
> using the build IDs associated with missing debug info, executables and source
> files in order to download them on demand.

Note "and source files": debuginfod distributes the *sources* too, which is the
distribution-scale answer to the `comp_dir` problem in §4.1.

---

## 5. Panics, stack traces and crash reports

This is the part a user hits first, before any debugger, and it is where the two
plausible designs diverge most sharply.

### 5.1 Unwinding: two mechanisms

A stack trace needs the return-address chain. Either the frame pointer is kept
in a register (walk it, cheap and simple, costs a register and some instructions
everywhere), or the compiler emits unwind tables and the tracer interprets them.
The table format on Linux is `.eh_frame`, per LSB Core
(<https://refspecs.linuxfoundation.org/LSB_5.0.0/LSB-Core-generic/LSB-Core-generic/ehframechpt.html>,
read 2026-09-18):

> When using languages that support exceptions, such as C++, additional
> information must be provided to the runtime environment that describes the
> call frames that must be unwound during the processing of an exception. This
> information is contained in the special sections `.eh_frame` and
> `.eh_framehdr`. Note: The format of the `.eh_frame` section is similar in
> format and purpose to the `.debug_frame` section which is specified in DWARF
> Debugging Information Format, Version 4.

The trade-off is measured. Fedora's change proposal to restore frame pointers
distribution-wide
(<https://fedoraproject.org/wiki/Changes/fno-omit-frame-pointer>, read
2026-09-18) reports:

> Compiling the kernel with GCC is 2.4% slower with frame pointers
> Running Blender to render a frame is 2% slower on our specific testcase
> openssl/botan/zstd do not seem to be affected significantly when built with
> frame pointers
> The impact on CPython benchmarks can be anywhere from 1-10% depending on the
> specific benchmark
> Redis benchmarks do not seem to be significantly impacted when built with
> frame pointers

and on the alternative:

> DWARF data - The compiler can emit extra information that allows us to find
> the beginning of the frame without the frame pointer […] The perf tool allows
> you to use the DWARF data with `--call-graph=dwarf`, but this means that it
> copies the full stack on every event and unwinds in user space. This has very
> high overhead.

That last sentence is the profiler-facing half of the answer: a profiler needs
*cheap* unwinding at high sample rates, which is why frame pointers came back.

### 5.2 What Zig does on panic

The default handler is `std.debug.defaultPanic`
(`lib/std/debug.zig:489` in the installed Zig 0.16.0 at
`/home/cx89/.local/share/mise/installs/zig/0.16.0/lib`, read 2026-09-18):

```zig
/// Dumps a stack trace to standard error, then aborts.
pub fn defaultPanic(msg: []const u8, first_trace_addr: ?usize) noreturn {
```

and it is selected through an overridable declaration in `std.builtin`
(`lib/std/builtin.zig:1220-1241`, elisions marked `[...]`):

```zig
/// This namespace is used by the Zig compiler to emit various kinds of safety
/// panics. These can be overridden by making a public `panic` namespace in the
/// root source file.
pub const panic: type = p: {
    if (@hasDecl(root, "panic")) {
        [...]
        break :p root.panic;
    }
    break :p switch (builtin.zig_backend) {
        [...]
        else => std.debug.FullPanic(std.debug.defaultPanic),
    };
};
```

The decisive detail for A7 is **how** the trace is turned into text. Zig resolves
each address against its own DWARF at run time, then opens the file the DWARF
names and prints the line from disk. `printLineInfo` (`lib/std/debug.zig`):

```zig
    if (symbol.source_location) |*sl| {
        if (sl.column == 0) {
            try writer.print("{s}:{d}", .{ sl.file_name, sl.line });
        } else {
            try writer.print("{s}:{d}:{d}", .{ sl.file_name, sl.line, sl.column });
        }
    } else {
        try writer.writeAll("???:?:?");
    }
```

and `printLineFromFile`:

```zig
    const cwd: Io.Dir = .cwd();
    var file = try cwd.openFile(io, source_location.file_name, .{});
```

Two consequences follow, and they point in opposite directions:

1. **Zig's panic trace dies with `strip`.** There is no baked-in file/line
   constant anywhere; the text comes from `.debug_line` read at run time.
   Measured, on the probe below rebuilt with `-fstrip` (2026-09-18): the trace
   does not degrade, it disappears.

   ```
   $ zig build-exe probe2.zig -ODebug -fstrip -femit-bin=probe2_strip
   $ ./probe2_strip            # exit 134
   thread 1777848 panic: a7: probe panic
   Cannot print stack trace: stack tracing is disabled
   ```
2. **If the DWARF said `004_func.a7:7:5`, Zig's own panic printer would open the
   A7 file and print the A7 line, with a caret.** No Zig change required. That
   is the strongest single argument for the line-table options in section 8.

The trace A7 produces today, from the audit's controlled `@panic` build
(`tmp/audit/2026-09-18/production/dbg/panic.err`, cited rather than re-run):

```
thread 1109491 panic: a7 stdout write failed
/home/.../panicdemo.zig:2:18: 0x11d7fea in deep (panicdemo.zig)
fn deep() void { @panic("a7 stdout write failed"); }
                 ^
/home/.../panicdemo.zig:3:58: 0x11d7f1c in main (panicdemo.zig)
pub fn main(init: std.process.Init) void { _ = init; deep(); }
                                                         ^
/home/cx89/.local/share/mise/installs/zig/0.16.0/lib/std/start.zig:737:30: 0x11d2a53 in callMain (std.zig)
```

Zig documents two override points that A7 could use without touching DWARF
(`lib/std/debug.zig:31-38`):

> The Zig Standard Library provides default implementations of `SelfInfo` for
> common targets, but the implementation can be overriden by exposing
> `root.debug.SelfInfo`. Setting `SelfInfo` to `void` indicates that the
> `SelfInfo` API is not supported.

and, inside `printLineFromFile`:

> `// Allow overriding the target-agnostic source line printing logic by exposing `root.debug.printLineFromFile`.`

**Probed, both of them** (`tmp/research/debug-info/override/`, 2026-09-18). The
`SelfInfo` override cannot simply wrap the standard one, because the standard
one *is* the root's:

```
$ zig build-exe probe.zig -ODebug
error: dependency loop with length 2
    .../lib/std/debug.zig:65:15: note: value of declaration 'debug.SelfInfo' uses value of declaration 'probe.debug.SelfInfo' here
    probe.zig:6:35: note: value of declaration 'probe.debug.SelfInfo' uses value of declaration 'debug.SelfInfo' here
```

The `printLineFromFile` override works, and its effect is exactly half of what
A7 needs:

```
$ zig build-exe probe2.zig -ODebug -femit-bin=probe2 && ./probe2
thread 1734188 panic: a7: probe panic
/home/.../probe2.zig:17:5: 0x11d985a in boom (probe2.zig)
[a7] would print 004_func.a7 for /home/.../probe2.zig:17
    ^
/home/.../probe2.zig:22:9: 0x11d978c in main (probe2.zig)
[a7] would print 004_func.a7 for /home/.../probe2.zig:22
```

The hook replaces the *source line* but not the `file:line:col` header, which
`printLineInfo` prints and which is not overridable. So a hook-only approach
gets A7 source text into the trace but leaves Zig coordinates in the header. A
full replacement means overriding the root `panic` namespace and printing the
whole trace yourself — for which `std.debug.getSelfDebugInfo()` and
`SelfInfo.getSymbols` are public, but the stack unwinder iterator in 0.16.0 is
not, so A7 would have to walk frame pointers itself. INFERENCE, from reading
`lib/std/debug.zig`: this is a bounded but real piece of work, and it is
target-specific.

### 5.3 What Rust does, and why it survives `strip`

Rust's panic location is not debug information. It is a compile-time constant
that the compiler threads through annotated call sites. From the Rust Reference
(<https://doc.rust-lang.org/reference/attributes/codegen.html>, read
2026-09-18):

> Applying the attribute to a function `f` allows code within `f` to get a hint
> of the `Location` of the "topmost" tracked call that led to `f`'s invocation.
> At the point of observation, an implementation behaves as if it walks up the
> stack from `f`'s frame to find the nearest frame of an unattributed function
> `outer`, and it returns the `Location` of the tracked call in `outer`.
> […] Note: `core` provides `core::panic::Location::caller` for observing caller
> locations. It wraps the `core::intrinsics::caller_location` intrinsic
> implemented by `rustc`.

and from the standard library
(<https://doc.rust-lang.org/std/panic/struct.Location.html>, read 2026-09-18):

> A struct containing information about the location of a panic. This structure
> is created by `PanicHookInfo::location()` and `PanicInfo::location()`.
> […] `pub const fn caller() -> &'static Location<'static>` Returns the source
> location of the caller of this function. If that function's caller is
> annotated then its call location will be returned, and so on up the stack to
> the first call within a non-tracked function body.

### 5.4 What a language must keep to name its own file in a crash

The contrast in §5.2 and §5.3 is the answer, and it is a design choice, not an
implementation detail:

- **Rust's model:** the file and line are *data in the program* — a static
  `Location` emitted at the panicking call site. It costs a few bytes of rodata
  per tracked site and a pointer argument; it survives `strip`, needs no DWARF,
  no unwinder and no source file on the machine. It gives you the *panic site*
  only; a full backtrace still needs unwind tables and symbols.
- **Zig's model:** the file and line are *metadata about the program* — read out
  of DWARF at run time, then the source file is opened from disk. It gives a
  full multi-frame trace with source excerpts and costs nothing at run time
  until something crashes, but it dies with `strip`, needs the sources present,
  and — decisively for A7 — can only ever name whatever file the DWARF names,
  which today is `.zig`.

Nim ships both (§2.2: `--lineDir` for the debugger, `--stackTrace`/`--lineTrace`
for crash traces). For A7 the Rust-shaped half is available immediately and
cheaply — but only for the panics A7's own backend emits, which is a narrower
class than it first appears.

### 5.5 Which crash class each mechanism can reach

An A7 program can die in three ways, and they need three different answers.

**1. A panic A7's backend emitted itself.** Today that is the two stdout calls
in the generated prelude (`a7/backends/zig.py:173-174`,
`@panic("a7 stdout write failed")`), and in future any A7-level check. Here the
backend writes the `@panic` call, so it can write an A7 `file:line` into the
message string. **Costs a few bytes of rodata, needs no DWARF, no unwinder and
no source file, and survives `-fstrip`.** This is the Rust model, and it is the
only mechanism in this report that works in a stripped binary.

**2. A Zig compiler-inserted safety check** — bounds, overflow, division by
zero, null unwrap — at `-ODebug` or `-OReleaseSafe`. These do *not* go through
A7's code. The compiler calls into the `std.builtin.panic` namespace, and every
one of those functions receives only a return address
(`lib/std/debug.zig`, `FullPanic`, read 2026-09-18):

```zig
        pub fn outOfBounds(index: usize, len: usize) noreturn {
            @branchHint(.cold);
            std.debug.panicExtra(@returnAddress(), "index out of bounds: index {d}, len {d}", .{ index, len });
        }
        pub fn integerOverflow() noreturn {
            @branchHint(.cold);
            call("integer overflow", @returnAddress());
        }
        pub fn divideByZero() noreturn {
            @branchHint(.cold);
            call("division by zero", @returnAddress());
        }
```

Overriding the namespace therefore gets A7 the *message* but not a location: the
return address is meaningful only once resolved through DWARF
(`getSelfDebugInfo().getSymbols`), which yields **Zig** coordinates that a
side-car map must then translate. So this class needs the map *and* the runtime
DWARF lookup, works only in Debug/ReleaseSafe, and disappears under `-fstrip`
exactly as measured in §5.2. No baked constant can cover it, because A7 never
writes the call.

**3. A fault in `-OReleaseFast`.** Safety checks are off, so the failure is a
signal, not a panic — and Zig's segfault handler is not installed either.
`lib/std/debug.zig:1490`:

```zig
pub const default_enable_segfault_handler = runtime_safety and have_segfault_handling_support;
```

with `runtime_safety` (`:237`) being `.Debug, .ReleaseSafe => true` and false
otherwise. INFERENCE, from reading those two declarations: a ReleaseFast A7
binary that faults dies with a bare `SIGSEGV` and prints nothing at all, unless
the program opts back in via `std.options.enable_segfault_handler`. Naming an A7
line here needs either a core dump plus separately-shipped debug info (§4.4), or
option (d)'s rewritten line table, or an A7-level check that turns the fault into
class 1 before it happens.

This three-way split is what prices option (b) honestly in section 8.

---

## 6. Cost

### 6.1 Binary size

Measured on this repository's own example, `examples/004_func.a7`, on
2026-09-18 with zig 0.16.0 (full commands in §7):

| Build | Binary size | `.debug_*` total | `.eh_frame` |
| --- | ---: | ---: | ---: |
| `-ODebug` | 10,278,392 B | 3,244,988 B | 0x1d19c (119 KB) |
| `-OReleaseFast` | 3,835,656 B | 3,254,024 B | 0x16308 (90 KB) |
| `-ODebug -fstrip` | 3,160,184 B | 0 | 0x28378 (165 KB) |

(`.debug_*` totals summed with
`readelf -S -W <bin> | grep '\.debug' | awk '{s+=strtonum("0x"$6)} END {print s}'`.)

Two findings worth stating plainly. First, **`-OReleaseFast` carries as much
debug information as `-ODebug`** — 3,254,024 B against 3,244,988 B, because Zig
does not strip unless asked; the release binary is smaller only because the code
is. Second, stripping a Debug build removes about 69% of the file. `.eh_frame`
survives stripping in all three — so the *unwinder* is intact and C++-style
exception handling would still work — but Zig's panic path does not fall back to
a trace of bare addresses; it declines to print one at all (§5.2). Debug
information is not optional decoration in Zig's crash path; it is the crash
path.

The classic large-scale figures come from the GCC Fission page
(<https://gcc.gnu.org/wiki/DebugFission>, updated January 24, 2013, read
2026-09-18):

> In a large C++ application compiled with `-O2` and `-g`, the debug information
> accounts for 87% of the total size of the object files sent as inputs to the
> link step, and 84% of the total size of the output binary.

with the per-section breakdown (percentages of total object file size):

> Debug Information Entries - `.debug_info` (11%) […] Type Units -
> `.debug_types` (12%) […] Strings - `.debug_str` (25%) […] Range tables -
> `.debug_ranges` (2%) and `.debug_aranges` (0.1%) […] Location lists -
> `.debug_loc` (2%) […] **Line number tables - `.debug_line` (1%)** […] Debug
> abbreviation codes - `.debug_abbrev` (<1%) […] Relocations for debug
> information (46%)

**The line table is one percent.** That is the single most important cost fact
in this report for A7: the part that gives file names, line numbers, panic
locations, breakpoints-by-line and profiler attribution is the cheapest section
in DWARF by an order of magnitude. Types and locations — the parts A7 cannot
produce without owning a backend — are what cost.

### 6.2 Build time and link time

Fission's motivation is link time, not binary size:

> Large applications compiled with debug information experience slow link times,
> possible out-of-memory conditions at link time, and slow gdb startup times.
> […] As a rule of thumb, the link job total memory requirements can be
> estimated at about 200% of the total size of its input files.

and the estimated benefit of moving to `.dwo`:

> Total estimated benefit: 70% reduction

Measured locally, the A7 example's three builds all completed well inside the
5-minute timeout; no per-build timing was captured, so **no build-time number is
claimed here.**

### 6.3 Runtime overhead

Debug information is inert: it occupies file space and is read only by a
debugger or by a panic handler. The runtime costs in this area come from the
*unwinding* mechanism, not the debug info — the Fedora numbers in §5.1 (2.4% on
a kernel build, 1-10% on CPython benchmarks) are the price of frame pointers,
and the "very high overhead" note is the price of DWARF unwinding at profiler
sample rates.

### 6.4 Stripping and shipping separately

Yes, and it is the standard practice for every mechanism in this report:
`-gsplit-dwarf`/`.dwo` (§4.4), Apple `.dSYM` — which Kotlin/Native generates by
default for release binaries on Apple platforms (§2.3) — and `debuginfod` for
distribution-scale on-demand download of "ELF, DWARF and source files" (§4.4).
DWARF 5's explicit file-index-0 rule (§1.2) exists precisely "to support the
common practice of stripping all but the line number sections (`.debug_line` and
`.debug_line_str`) from an executable", which is the cheapest useful shipping
configuration: file and line, nothing else.

---

## 7. What an A7 binary contains today

All commands below were run on 2026-09-18 in
`tmp/research/debug-info/demo/` with `uv 0.12.15`, zig 0.16.0 and
`readelf` from GNU binutils; raw output is in that directory.

```
$ uv run a7 tmp/research/debug-info/demo/004_func.a7 -o tmp/research/debug-info/demo/004_func.zig
Compiled .../004_func.a7 -> .../004_func.zig (1583 bytes, 7 ms)
$ zig build-exe 004_func.zig -ODebug -femit-bin=004_func_dbg
$ ./004_func_dbg
=== Functions ===
5 + 7 = 12
Hello, World!
17 / 5 = 3 remainder 2
5! = 120
max(10, 20) = 20
```

**The `.a7` file appears nowhere.**

```
$ strings 004_func_dbg | grep -c '\.a7'
0
```

**Symbols are Zig's, with A7 names inside them.**

```
$ nm 004_func_dbg | grep -E '004_func\.'
00000000011d8050 t 004_func.__a7_user_main
00000000011dd0e0 t 004_func.add
00000000011dc000 t 004_func.divide
00000000011db9d0 t 004_func.factorial
00000000011dc5c0 t 004_func.greet
00000000011d7ef0 t 004_func.main
```

`main` is the Zig entry wrapper; the user's A7 `main` is `__a7_user_main`.

**The compilation unit names the Zig file and leaks the build path.**

```
$ readelf --debug-dump=info 004_func_dbg 2>/dev/null | head -14
Contents of the .debug_info section:

  Compilation Unit @ offset 0:
   Length:        0x13ebb (32-bit)
   Version:       5
   Unit Type:     DW_UT_compile (1)
   Abbrev Offset: 0
   Pointer Size:  8
 <0><c>: Abbrev Number: 42 (DW_TAG_compile_unit)
    <d>   DW_AT_language    : 39	(unknown: 0x27)
    <e>   DW_AT_producer    : (indirect line string, offset: 0xe5): zig 0.16.0
    <12>   DW_AT_comp_dir    : (indirect line string, offset: 0xa7): /home/cx89/Projects/pl-dev/a7-py/tmp/research/debug-info/demo
    <16>   DW_AT_name        : (indirect line string, offset: 0x111): 004_func.zig
    <1a>   DW_AT_base_types  : <0x13ecb>
```

(`2>/dev/null` here and below drops four `readelf` warnings about a "Bogus
end-of-siblings marker" in Zig's `.debug_info`, which are not this report's
subject.)

`readelf` reports language 0x27 as unknown; Zig's own `lib/std/dwarf/LANG.zig:39`
defines `pub const Zig = 0x0027`, and a grep of the DWARF 5 text for `0x27` finds
it only as `DW_TAG_constant`, `DW_AT_prototyped`, `DW_FORM_strx3` and `DW_OP_xor`
— never as a language code. INFERENCE: the code is a post-DWARF-5 registration.
A consumer that does not know it falls back to generic behavior — the same wart
Kotlin/Native and Scala Native document in §2.3, from the other direction.

**The line table maps addresses to Zig lines only.**

```
$ readelf --debug-dump=decodedline 004_func_dbg 2>/dev/null | sed -n '/^004_func.zig:$/,+12p'
004_func.zig:
File name                        Line number    Starting address    View    Stmt

/home/cx89/Projects/pl-dev/a7-py/tmp/research/debug-info/demo/004_func.zig:
004_func.zig                               9           0x11d7ef0               x
004_func.zig                              10           0x11d7f3f               x
004_func.zig                              11           0x11d7f8b               x
004_func.zig                              11           0x11d7f90               x
004_func.zig                              12           0x11d7f95
004_func.zig                               -           0x11d7f95
```

**The file table for the A7 compilation unit has exactly one entry.** This is
the finding that prices option (d) in section 8:

```
$ readelf --debug-dump=rawline 004_func_dbg 2>/dev/null | grep -A16 'The Directory Table (offset 0x53160'
 The Directory Table (offset 0x53160, lines 1, columns 1):
  Entry	Name
  0	(indirect line string, offset: 0xa7): /home/cx89/Projects/pl-dev/a7-py/tmp/research/debug-info/demo

 The File Name Table (offset 0x5316d, lines 1, columns 3):
  Entry	Dir	(Unknown format content type 8193)	Name
  0	0	(indirect line string, offset: 0x128): 	(indirect line string, offset: 0x111): 004_func.zig

 Line Number Statements:
  [0x00053176]  Extended opcode 2: set Address to 0x11d7ef0
  [0x00053181]  Set File Name to entry 0 in the File Name Table
  [0x00053183]  Set column to 42
  [0x00053185]  Special opcode 13: advance Address by 0 to 0x11d7ef0 and Line by 8 to 9
  [0x00053186]  Set prologue_end to true
```

Content type 8193 is `0x2001`, which `lib/std/dwarf.zig:126` names in its `LNCT`
namespace (`pub const LLVM_source = 0x2001;`): Zig's self-hosted DWARF writer
emits a source-text column in the file table, matching the `DW.LNCT.LLVM_source`
use found in `src/link/Dwarf.zig` (§2.4). For the generated `builtin.zig` unit that column
actually contains the file's text; for the A7 unit it is empty. INFERENCE: a
producer can therefore embed source text in `.debug_line_str`, which is the
DWARF equivalent of `sourcesContent` and would let a stripped-of-sources machine
still show A7 lines.

**Variables and scopes are fully described in Debug — under A7's own names.**

```
$ readelf --debug-dump=info 004_func_dbg 2>/dev/null | grep -A18 'DW_AT_linkage_name.*004_func\.factorial'
    <53c>   DW_AT_linkage_name: (indirect string, offset: 0x5488c): 004_func.factorial
    <540>   DW_AT_type        : <0x18a6b>
    <544>   DW_AT_low_pc      : 0x11db9d0
    <54c>   DW_AT_high_pc     : 0xb4
    <550>   DW_AT_alignment   : 16
    <551>   DW_AT_external    : 0
    <552>   DW_AT_noreturn    : 0
 <3><553>: Abbrev Number: 102 (DW_TAG_formal_parameter)
    <554>   DW_AT_name        : (indirect string, offset: 0x19d61): n
    <558>   DW_AT_type        : <0x18a6b>
    <55c>   DW_AT_location    : 2 byte block: 77 20 	(DW_OP_breg7 (rsp): 32)
 <3><55f>: Abbrev Number: 113 (DW_TAG_variable)
    <560>   DW_AT_name        : (indirect string, offset: 0x1a872): result
    <564>   DW_AT_type        : <0x18a6b>
    <568>   DW_AT_location    : 2 byte block: 77 24 	(DW_OP_breg7 (rsp): 36)
 <3><56b>: Abbrev Number: 99 (DW_TAG_lexical_block)
    <56c>   DW_AT_low_pc      : 0x11db9e4
    <574>   DW_AT_high_pc     : 0x97
 <4><578>: Abbrev Number: 113 (DW_TAG_variable)
```

(The entries cut off by `-A18` are `DW_AT_name: i` with
`DW_AT_location: 2 byte block: 77 28  (DW_OP_breg7 (rsp): 40)`.)

`n`, `result` and `i` are the identifiers from `examples/004_func.a7` — the
backend passes user names through unchanged. **Only the coordinates are wrong,
not the names.** A debugger attached to this binary can already print the user's
variables by the user's names; it simply cannot tell the user which A7 line it
is stopped on.

**In ReleaseFast the functions cease to exist as frames.**

```
$ nm 004_func_rel | grep -E '004_func\.'
000000000108b000 b 004_func.__a7_io
000000000101ceb0 t 004_func.main
$ readelf --debug-dump=info 004_func_rel 2>/dev/null | grep -A14 'DW_AT_name.*: main$' | head -16
    <11010>   DW_AT_name        : (indirect string, offset: 0x14a7f): main
    <11014>   DW_AT_decl_file   : 43
    <11015>   DW_AT_decl_line   : 9
    <11016>   DW_AT_type        : <0x355>
 <2><1101a>: Abbrev Number: 87 (DW_TAG_formal_parameter)
    <1101b>   DW_AT_location    : 0x809f (location list)
    <1101f>   DW_AT_name        : (indirect string, offset: 0xb1a8): init
    <11023>   DW_AT_decl_file   : 43
    <11024>   DW_AT_decl_line   : 9
    <11025>   DW_AT_type        : <0x89206>
 <2><11029>: Abbrev Number: 73 (DW_TAG_inlined_subroutine)
    <1102a>   DW_AT_abstract_origin: <0x10bca>
    <1102e>   DW_AT_ranges      : 0x20b0
    <11032>   DW_AT_call_file   : 43
    <11033>   DW_AT_call_line   : 11
```

Every user function was inlined into `main`; what survives is
`DW_TAG_inlined_subroutine` with `DW_AT_call_file: 43` and a location *list* for
the parameter. File 43 resolves through the DWARF 4 file table LLVM emits here:

```
$ readelf --debug-dump=rawline 004_func_rel | grep -E '^  (42|43|44)\b'
  42	1	0	0	elf.zig
  43	0	0	0	004_func.zig
  44	11	0	0	cpu_context.zig
```

This is §1.5 and §4.2 happening to A7 code: the release binary's stack trace, if
one were produced, would show a single frame with inline records, and any
variable inspection would depend on location lists that cover only part of each
range.

**Everything above is the SRC-MAP gap.** `docs/plan/execution.md:157` puts
SRC-MAP in Wave 3 ("Wave 3 adds **SRC-MAP** (TOK-23, TOK-29) with the IR
builder") and `docs/plan/fix-program/frontend-fix-plan.md:310` describes it as
"One source map per file (file ID, offsets, line table); tokens carry offsets,
end positions and decoded values; spans can cover several lines." The frontend
half is already partly there: `a7/ast_nodes.py:162` gives every node an optional
`span: SourceSpan`, and `a7/errors.py:437-444` defines `SourceSpan` with
`start_line`, `start_column`, `end_line`, `end_column`, `length` — **but no file
identity**, which is exactly the gap the plan row names. What is missing is
entirely on the backend side. `a7/backends/zig.py` already *reads* `node.span`
— 25 occurrences, all of them attaching a span to a `CodegenError` — but it
builds its output by appending strings to a `lines` list and never records which
A7 span produced which emitted line. The information exists at the moment of
emission and is thrown away.

---

## 8. For A7: the options

Seven options, in ascending cost. "Panic lines" means a runtime failure names
the `.a7` file and line; "stepping" means `break file.a7:14` and `next` work in a
stock debugger; "variables" means `print x` shows the A7 variable. Each option
also carries the two verdicts [EVALUATION.md](../EVALUATION.md) requires, agent
value weighted higher.

| Option | Panic lines | Stepping | Variables | Cost | Agent / human value |
| --- | --- | --- | --- | --- | --- |
| (a) provenance comments | no | no | no | ~0 | low / moderate |
| (b1) baked A7 `file:line` constants | class 1, incl. stripped | no | no | small | **high** / high |
| (b2) panic override + map | classes 1-2, Debug/ReleaseSafe | no | no | medium | high / moderate |
| (c) gdb plugin | via plugin | yes, via plugin | yes, via plugin | medium-large | low / **high** |
| (c′) `a7 symbolize` | classes 1-2, offline | no | no | small | **high** / moderate |
| (d) rewrite `.debug_line` | yes, stock tools | yes, stock tools | partly | large | moderate / high |
| (e) emit C with `#line` | yes | yes | yes | rewrite | high / high, but rejected |
| (f) own DWARF emission | yes | yes | yes | a different project | high / high |

"Class 1/2/3" are the crash classes of §5.5.

### (a) Provenance comments in the generated Zig

Emit `// a7: 004_func.a7:7:5` above each emitted statement.

- **Takes:** thread `node.span` into `a7/backends/zig.py`'s emitters; a file
  identity on `SourceSpan` (the SRC-MAP TOK-29 row).
- **Gives:** nothing to any tool. A human reading the `.zig` can find the
  origin; a debugger, profiler and crash report see exactly what they see today.
- **Costs:** near zero; larger `.zig` output.
- **Verdict:** worth doing as a by-product of (b), not as an end.
  **Agent value: low** — an agent can read the map directly and does not need it
  restated in comments. **Human value: moderate**, when reading generated code.

### (b) A side-car map plus an A7-aware panic handler

Emit a map from generated-Zig position to A7 span, as a `004_func.a7.map` file
and/or a `comptime` table in the generated Zig, and use it at panic time.

- **Takes:** the span plumbing from (a); a stable map format; a generated Zig
  prelude. Two sub-variants, and §5.5 says which crash each reaches:
  - **b1, baked constants (Rust's model).** The backend writes an A7
    `file:line` into every `@panic` string it emits itself. No unwinder, no
    DWARF, no map lookup at run time, survives `-fstrip`. Reaches crash class 1
    only — today the two prelude panics, tomorrow every A7-level check.
  - **b2, panic-namespace override plus map.** Overriding root `panic` gets the
    message for Zig's own safety checks (class 2), but those pass only
    `@returnAddress()` (§5.5), so the location still needs
    `getSelfDebugInfo().getSymbols` to produce Zig coordinates and the map to
    translate them. `printLineFromFile` is proven to work (§5.2) and fixes the
    *source excerpt*; the `file:line:col` header needs a full trace printer,
    for which the unwinder iterator is not public in 0.16.0, so frame-pointer
    walking would be A7's job. Debug and ReleaseSafe only.
  - Neither reaches class 3, a ReleaseFast fault.
- **Gives:** panic lines. No stepping, no variables.
- **Costs:** b1, a few bytes of rodata per site and no runtime cost. b2, a map
  file plus a trace printer, and nothing at run time until a crash.
- **Verdict:** b1 is the highest value per unit of work in this list and should
  land first; b2 is worth doing only alongside the map that (c) and (d) also
  need. **Agent value: high** — a machine-parseable `file:line` in the crash
  output is what an agent greps for and feeds back into an edit loop; it makes a
  failing run self-localizing without a debugger session. **Human value: high**
  for b1, moderate for b2.

### (c) A debugger plugin (Cython's road)

Ship `a7-gdb`, a gdb Python plugin that reads the side-car map from (b) and
provides `a7 break file.a7:14`, `a7 step`, `a7 list`, `a7 locals`.

- **Takes:** the map from (b), plus a gdb Python extension. Cython's `cygdb`
  (§2.2) is the existence proof that this reaches breakpoints-by-original-line,
  stepping and variable printing.
- **Gives:** stepping and variables — *for users who use the plugin*. A user
  running plain `gdb` or `lldb`, or a crash reporter, still sees Zig. Two
  debuggers means two plugins.
- **Costs:** a new deliverable to build, test and version against gdb releases.
- **Verdict:** the right second step for a human, and it is where A7's existing
  advantage pays off — §7 shows the variables are already named `n`, `result`,
  `i`, so the plugin's job is coordinate translation, not variable
  reconstruction. **Agent value: low** — an interactive debugger session is the
  wrong shape for an agent. **Human value: high.**

### (c′) `a7 symbolize` — the agent-facing twin of (c)

Per [EVALUATION.md](../EVALUATION.md), the visual/interactive idea usually has a
queryable twin, and here it is a better deliverable than the thing it twins. Ship
a subcommand that reads a pasted Zig panic trace (or a `--json` trace) on stdin
and rewrites every `*.zig:LINE:COL` into `*.a7:LINE:COL` using the same map.

- **Takes:** only the map from (b). A few hundred lines; no debugger, no DWARF
  writer, no gdb version matrix.
- **Gives:** A7 coordinates for any trace that carries a Zig `file:line` — that
  is crash classes 1 and 2 (§5.5) — from any machine, after the fact, including
  a trace copied out of CI logs where the binary is long gone. A class-3
  ReleaseFast fault produces no trace to paste; the only input it can offer is a
  `bt` from a core dump, and only if debug info was shipped separately (§4.4).
- **Costs:** near zero, and it is testable with a golden-file test rather than a
  debugger harness.
- **Verdict:** **agent value: high** — deterministic, offline, machine-readable,
  runnable thousands of times, and it turns a log line into a file the agent can
  open. **Human value: moderate** — useful for CI triage, no help while
  stepping.

### (d) Post-process `.debug_line` after the Zig build

Rewrite the emitted binary's line table: substitute the file name and remap line
numbers through the side-car map.

- **Takes:** a DWARF writer for `.debug_line` (and `.debug_line_str`) in the
  compiler or a `a7 build` post-step. The demo in §7 prices it precisely: the A7
  compilation unit's file table has **one** entry, one directory, and every
  `DW_AT_decl_file` in the unit is an *index* into it (§1.3), so changing the
  name is one string. Remapping the *line numbers* means re-encoding the line
  program's special opcodes — real work, and it must handle the Vala case (§2.2)
  where emitted code has no A7 origin, by pointing those rows at the `.zig` file
  rather than at a wrong A7 line (§1.4). No off-the-shelf tool does this;
  `objcopy` cannot.
- **Gives:** panic lines *and* stepping in stock gdb/lldb, because §5.2 shows
  Zig's own panic printer opens whatever file the DWARF names. Variables come
  along partly for free at `-ODebug` since the DIE names are already A7's — but
  the scopes remain Zig's shape.
- **Ceiling, from the one documented precedent** (§2.2, Grok lookup,
  UNVERIFIED): Modula-3's SRC compiler emitted `#line` into its generated C and
  its own manual still said stock C debug info describes the *generated* file,
  with data-structure debug info "almost non-existent" — and the project
  eventually shipped `m3gdb` anyway. A rewritten line table fixes *where you
  are*, never *what your values are*.
- **Costs:** a DWARF encoder to maintain; brittleness against Zig backend
  changes (self-hosted x86_64 emits DWARF 5 with `DW_LNCT_LLVM_source`, the LLVM
  path emits DWARF 4 — the demo shows both in one project); and it only works
  where A7 controls the link step.
- **Verdict:** the highest-value option that does not require owning a backend,
  and the only one that makes stock tools work — but it is a real compiler
  component, not a script. **Agent value: moderate** — it improves every tool at
  once, including `perf` attribution and core-dump analysis, but an agent gets
  most of that benefit from (c′) at a fraction of the cost. **Human value:
  high.**

### (e) Emit C with `#line` instead of Zig, built with `zig cc`

- **Takes:** a second backend. `zig cc` is already in the toolchain and §2.1
  proves it honors `#line` into DWARF today.
- **Gives:** panic lines, stepping and variables, from stock tools, with no
  DWARF code of A7's own — the whole prize, by reusing Clang's debug-info
  pipeline.
- **Costs:** abandons the Zig standard library, Zig's safety checks and the
  entire existing backend; contradicts the project's architecture
  (`CLAUDE.md`: "an ahead-of-time compiler from `.a7` source to Zig source").
  Columns are still unavailable (`#line` carries no column).
- **Verdict:** rejected on architecture, but it is the correct benchmark: any
  other option should be judged against "what `#line` would have given us".
  **Agent value: high** if it existed; **human value: high** — which is exactly
  why it is the benchmark.

### (f) Own DWARF emission — an IR and a real backend

- **Takes:** the Wave 3 IR builder plus a code generator that knows addresses.
- **Gives:** everything, including inlined frames and location lists.
- **Costs:** a different project.
- **Verdict:** the destination the plan already names, not a next step.
  **Agent and human value: high**, at a cost neither can pay this year.

### Recommendation

**Build the map (the SRC-MAP row), then ship b1 and (c′) on top of it. Treat (d)
as the next milestone and (c) as optional.**

That is three deliverables in order: a file-identified span map; baked A7
`file:line` constants in every panic A7 emits; and `a7 symbolize`, which
translates a pasted trace offline. Reasons, in order of weight:

1. **The prerequisite is shared by every option.** All of (a)-(d) and (c′) need
   the same thing: a file-identified span on every emitted construct. That is
   the SRC-MAP row (TOK-23/TOK-29), and the missing piece is concrete —
   `SourceSpan` (`a7/errors.py:437-444`) carries lines and columns but no file
   identity, and `a7/backends/zig.py` reads spans only to attach them to errors.
   Build it once and everything else becomes an addition.
2. **b1 is the failure the user hits first, and the only thing that survives
   a release build.** Per §5.5, a baked constant reaches the panics A7 itself
   emits, needs no DWARF, no unwinder and no sources on the machine, and works
   under `-fstrip`. Everything else in this report stops working there.
3. **(c′) is the cheapest way to reach crash class 2, and it is the highest
   agent-value item in the list.** A trace that a human reads once in a terminal
   is a trace an agent parses in a loop; `a7 symbolize` gives A7 coordinates for
   a Zig safety panic pasted out of CI, with no debugger, no `.zig-cache` and no
   binary, and it is golden-file testable. It cannot help with class 3, which
   prints nothing to translate — that one needs (d), shipped debug info, or an
   A7-level check that converts the fault into class 1 first.
4. **The cheap win is genuinely cheap and the expensive win is genuinely
   expensive.** `.debug_line` is 1% of DWARF (§6.1) and the A7 unit's file table
   has exactly one entry (§7), so (d)'s file-name half is trivial; but
   re-encoding a line program correctly — `is_stmt`, `prologue_end`, and honest
   handling of emitted code with no A7 origin (§2.2's Vala reset directive) — is
   compiler work, and getting it subtly wrong produces the "misleading
   single-stepping" LLVM warns against (§1.4), which is worse than the honest
   Zig coordinates A7 shows today.
5. **A7's variables already carry the user's names** (§7). The translation
   problem is coordinates only. That is what makes (d) a milestone rather than a
   research project, and it is why a Cython-style plugin (c) would be mostly
   plumbing — but (c) buys a human an interactive session that (c′) buys an
   agent for a tenth of the work, so (c) goes last.

For the map format itself, take GHC's lesson (§2.3) over the source-map one: an
entry should be a **span**, not a point, because one A7 `for` header already
becomes several Zig lines in the demo output, and the scopes proposal's
fourteen-year history (§3.3) is what happens when a format starts with points
and has to grow the rest later. Record, per entry, whether the emitted line has
an A7 origin at all — the Vala reset case — so that (d) can later point
origin-less rows at the `.zig` file instead of a wrong `.a7` line.

Two things to fix regardless of which option is chosen, both visible in §7:
`DW_AT_comp_dir` puts the full build path of the build machine into every binary
including release ones, and `-OReleaseFast` ships 3,254,024 B of debug
information — as much as `-ODebug` — because Zig does not strip unless asked.
