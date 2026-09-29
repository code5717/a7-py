# Packet P0: plan confirmations

Status: proposed, 2026-09-16, revision 2 after an independent review. Nothing here
changes A7 syntax. P0.1 asks you to approve a list of bug fixes that would then
proceed without further packets; the other items are plan decisions. Partial
approval is expected. Decisions are recorded in the [ledger](../decisions.md).

Sources: the [execution plan](../execution.md), the
[inventory reproduction](../audit/2026-09-16-inventory-repro.md) and its two
ledgers (bracketed IDs below), and the [baseline](../../audits/2026-09-16/baseline.md).

## P0.1 Which fixes go ahead without asking you

### Proposed rule

A fix goes ahead without a packet only if it belongs to one of four classes, and
only if it appears in the list below. Anything not in the list, or anything whose
compatibility scan finds a change to an example, test or doc snippet, comes to you
as a packet.

| Class | What changes | Condition |
| --- | --- | --- |
| A. No program changes | Crashes, internal errors, diagnostic text and location, output format | No program changes whether it is accepted or what it prints |
| B. Programs that never worked | A7 accepts the program but Zig rejects the emitted code | The fix either rejects it with a clear message, or emits code that means what the source already means |
| C. Miscompiles | The program builds but computes something other than what the source says | SPEC or an existing A7 rule states the meaning; the program's output changes to the correct one |
| D. Wrongly rejected programs | A7 rejects a program it should accept | SPEC documents the construct |

Everything else needs a packet, including rejecting unsafe programs that build today
(packet P0b), new defined behavior (for example L16's NaN), and cases where SPEC
contradicts itself.

### The list

| ID | Class | Fix | Evidence |
| --- | --- | --- | --- |
| 1 | A | Parser warnings go to stderr, so `--format json` output stays valid JSON | [F4] |
| 2 | A | `--format json` on a match that yields a struct no longer crashes; internal errors exit 8 | [F5] |
| 3 | A | `--output` or `--doc-out` equal to the input file is refused instead of overwriting the source; failed compiles never report a stale artifact | 4 failing baseline tests |
| 4 | A | Diagnostics point at the right line for parse errors, missing imports, and errors inside imported files | 4 failing baseline tests |
| 5 | B | A shadowed local's uses get the renamed name its declaration already has | [B10] |
| 6 | B | `defer x = 1` emits a deferred assignment instead of `defer void;` | [B11] |
| 7 | B | Locals named `test`, `var`, `const`, `std` or `allocator` are escaped or renamed consistently | [B12]; 3 failing baseline tests |
| 8 | B | `del` of a variable named `p` no longer collides with the emitted `\|p\|` capture | [B9] |
| 9 | B | Signed `x /= y` and `x %= y` emit the same code as `x = x / y` and `x = x % y` already do | [B13] |
| 10 | B | A write through a slice marks its backing array mutable, so the emitted `const` no longer fails | edge-case audit, `docs/plan/research/memory/edge-case-audit.md:118` |
| 11 | B | Rejected with a message: `[n]u8` with an unbound `n`; `z := z` with no outer `z`; string `==` between parameters; a mutated untyped global holding a number literal; a write into a by-value array parameter | [T1, T2, B3, B6, B7] |
| 12 | C | `arr = [arr[1], arr[0]]` prints `2 1`, not `2 2` | [B1]; SPEC A.1 item 3 |
| 13 | C | A call through a function-pointer field of a local named `math` calls that function instead of `@sqrt` | [B14] |
| 14 | C | Constant folding gives the same result as run time: `9007199254740993 / 1` and float `%` with negative operands | [S13, D7]; 1 failing baseline test |
| 15 | D | `ret 0` from a function returning `u32` or `usize`, and a literal argument to a `usize` parameter | [T3, C6 note]; SPEC A.2 |
| 16 | D | `.len` on a fixed array or string | [S12]; `docs/SPEC.md:259, 276` |
| 17 | D | A negative float literal divisor such as `-2.0` | [D7] |
| 18 | D | `del p` in one function no longer makes an unrelated `p` in another function an error | [S4] |
| 19 | D | Files with more than 1000 top-level declarations | [F3] |

Item 11 rejects only the forms that Zig rejects today. Rejecting every untyped global
would change 2 tests and 7 SPEC snippets, so it is not in the list.

Compatibility scan hits for the list, all in design notes under `docs/lang-safety/`
rather than in examples or tests; the notes are updated with each fix:

- Item 11: `edge-cases/03-definite-assignment.md:233` (`z := z`) and
  `edge-cases/05-stack-budget.md:111` (`dynamic: [n]u8`) become rejections.
- Item 15: five `ret 0` sites (`edge-cases/04-nonzero-division.md:122, 129`,
  `edge-cases/06-typed-arithmetic.md:139, 189`, `narrowing.md:692`) stop failing
  on the return type; their "Rejected (exit 6)" comments go stale, and later checks
  may still reject them.

### Examples

```a7
// Item 11, class B. A7 accepts (exit 0); Zig rejects the emitted
// `var counter = 0;` with "variable of type 'comptime_int' must be const or comptime".
io :: import "std/io"
counter := 0
main :: fn() {
    counter += 1
    io.println("{}", counter)
}
// Proposed: A7 rejects it and asks for a type, for example `counter: i32 = 0`.
// Message wording not yet written.
```

```a7
// Item 12, class C. Prints "2 2" today in Debug and ReleaseFast. SPEC A.1 lists
// "Assignment: right-to-left" (docs/SPEC.md:2065), which we read as: the right
// side is evaluated before the store. Proposed: prints "2 1".
io :: import "std/io"
main :: fn() {
    arr: [2]i32 = [1, 2]
    arr = [arr[1], arr[0]]
    io.println("{} {}", arr[0], arr[1])
}
```

```a7
// Item 15, class D. Rejected today (exit 6). SPEC A.2 allows "Integer literals
// to any integer type if in range" (docs/SPEC.md:2073). Proposed: accepted.
zero :: fn() u32 { ret 0 }
```

```a7
// Not in the list: needs packet P0b. Builds today and divides by zero.
main :: fn() {
    x := 5
    { x = 0 }
    y := 10 / x
}
```

```a7
// Not in the list: needs packet P4. Rejected today (exit 6, "divisor may be
// zero"). Accepting it gives new behavior under L16 (the result is NaN).
main :: fn() {
    zero: f64 = 0.0
    ratio := zero / zero
}
```

**Decision requested:** approve the rule and the list, remove items from the list, or
decline.

## P0.2 Reading of L20

L20 records: "I want a powerful, super simple, super fast (C like) performance";
"its like C in performance and memory usage"; "not even like C++".
`docs/plan/decisions.md:74-75` reads this as **C's performance and simplicity
without C++'s complexity or hidden costs**, and notes you have not confirmed it.

**Decision requested:** confirm this reading, or restate it.

## P0.3 L17 and L19: new concepts

L17 says the compiler groups allocations into arenas and pools and "we need new
concepts". L19 says programmers "shouldnt care about memory in general". The memory
plan introduces `Table(T)`, `Id(T)` and move-only resources, which a Python-style
programmer must learn. Kimi's review points out that the plan assumes L19 wins
without a decision (`docs/plan/memory.md:777-780`).

```a7
// Proposed syntax from docs/plan/memory.md:317-335 (not approved, does not
// compile today), shortened.
Node :: struct {
    value: i32
    parent: ?Id(Node)
}

Tree :: struct {
    nodes: Table(Node)
}

add_child :: fn(tree: ref Tree, parent: ?Id(Node), value: i32) Id(Node) {
    ret tree.nodes.insert(Node{value: value, parent: parent})
}
```

| Option | What it means | Cost |
| --- | --- | --- |
| (a) New concepts are fine | `Table(T)`, `Id(T)` and similar types are part of ordinary A7 | More for users to learn; the compiler stays simpler and memory behavior is easier to predict |
| (b) Keep them out of ordinary code where possible | The compiler infers more; the L19 metric (gate M48) counts how many concepts a typical program needs | More compiler work, and more programs the compiler must reject or copy when it cannot infer |
| (c) Something else | You describe it | Depends |

**Recommendation:** (b), because L19 is recorded as refining L17. This is a product
choice, so treat the recommendation lightly.

**Decision requested:** choose (a), (b) or (c).

## P0.4 Track split in the v1 plan

On 2026-09-16 the v1 plan's tracks were split to remove two dependency cycles. This
is already written into `docs/plan/README.md` and `docs/plan/memory.md`; you can
confirm it or ask for it to be reverted. It changes no language decision.

| Before | After |
| --- | --- |
| 3 Numeric semantics | 3a wrapping (L5); 3b other numerics (G1, G3) |
| 6 Memory model | 6a phases B, C1, C1′, D, E, C2; 6b phases F and G, after tracks 9, 10, 11 |
| 7 Errors and composites | 7a optionals and matching; 7b results and errors |
| 8 Standard library | 8a core collections, which phase C1 needs; 8b the rest |

Also proposed, not yet applied: minimal buffer-based input and output (packet P9) may
land before track 8b, so interactive example programs can exist earlier.

**Decision requested:** confirm or revert the split; approve or decline the P9
exception.

## P0.5 Test gate: remove one duplicate run

`./run_all_tests.sh` takes 542 s. It runs `scripts/verify_examples_e2e.py` twice:
once as its own step, and again inside the full pytest step through
`test/test_examples_e2e.py`.

- **Proposed:** remove the standalone step from `run_all_tests.sh`. The pytest run
  still executes the script, and the script itself stays, because CI, `CLAUDE.md:75`,
  `README.md` and the site docs refer to it.
- **Also proposed:** a `--jobs N` option so examples build in parallel. Results are
  unchanged.

**Decision requested:** approve or decline each.

## P0.6 Ignore `tmp/` in repository checks

The fix program keeps scratch files, agent reports and output from GLM-5.3 (the
second-opinion model used for reviews, ledger L12) in `tmp/`. The secrets check
scans `tmp/`, and it failed the baseline on a file there. Proposed: add `tmp/` to
`.gitignore`, to the skip list in `scripts/check_no_secrets.py`, and to pytest's
ignored paths. It is already excluded locally through `.git/info/exclude`.

**Decision requested:** approve or decline.

## P0.7 Corrections to `CLAUDE.md` and `AGENTS.md`

Three statements in the agent guides are wrong about the current compiler. These
files change only on your instruction.

1. `CLAUDE.md:36-37` says file-backed local imports "currently fail closed before
   codegen". They compile: `a7/compile.py:237-261` and `:597-627` merge imported
   files into one program. Declaring the same struct name in two files is rejected
   with "Already defined" (exit 6). `AGENTS.md` does not make this claim.
2. `CLAUDE.md:42-49` says semantic passes use explicit stacks. These recurse:
   the safety pass (`a7/safety.py`, `_visit_stmt`), the type checker's statement
   visits (`a7/passes/type_checker.py`, `visit_statement`), and parts of the semantic
   validator (`a7/passes/semantic_validator.py:379, 1224-1225, 1272, 1282`).
   `AGENTS.md` does not make this claim.
3. `CLAUDE.md:163-164` and `AGENTS.md:107-108` say "Compiler internals already use
   iterative AST traversals". The same three components recurse.

Proposed wording for 2 and 3: the passes above still recurse, the fix program removes
that recursion in Waves 2 and 3 (see the execution plan), and new compiler code must
use explicit stacks.

**Decision requested:** approve the corrections, or leave the guides unchanged.
