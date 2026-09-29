# GLM review of the untyped-constant proposal

Date: 2026-09-20. Reviewer: GLM-5.3 through OpenCode
`zai-coding-plan/glm-5.3`. Process exited 0. Read-only advisory review; no
compiler behavior approval or release qualification. The reviewed draft preceded
some of the final context clarifications and native probe results. Line numbers
refer to that draft, not necessarily the final packet.

The raw review transcript follows. Its claim that a huge decimal literal is an
accepted, building program was based on source inspection, not a fresh native
probe. Treat that specific build claim as unverified. Separate native evidence
in `untyped-constants-native-2026-09-20.json` confirms only the listed cases.
The final packet records disposition of these findings. GLM has not re-reviewed
those documentation amendments.


> build · glm-5.3

→ Read docs/plan/decisions.md
→ Read docs/plan/packets/P-TYP-forward-globals.md
I'll review the two target documents and verify claims against related sources. Starting with the referenced history packet and research doc.
→ Read docs/plan/packets/P-TYP-forward-globals-strict-history.md
✱ Glob "docs/plan/research/global-constants-2026-09-20.md" 1 match
→ Read docs/plan/research/global-constants-2026-09-20.md
✱ Glob "docs/audits/2026-09-20-core-v1/*" 52 matches
Research doc cites specific source locations. Verifying them against the actual compiler code.
→ Read a7/passes/name_resolution.py [offset=330, limit=30]
→ Read a7/passes/type_checker.py [offset=175, limit=25]
→ Read a7/passes/type_checker.py [offset=635, limit=40]
→ Read a7/types.py [limit=40, offset=108]
→ Read a7/types.py [limit=12, offset=532]
→ Read a7/passes/type_checker.py [limit=50, offset=1195]
✱ Grep "class UnknownType|is_assignable_to" in a7/types.py · 17 matches
→ Read a7/passes/type_checker.py [limit=70, offset=2985]
→ Read a7/types.py [limit=20, offset=509]
✱ Glob "docs/plan/research/global-constants-evidence.json" 1 match
→ Read docs/plan/research/global-constants-evidence.json
✱ Grep "def .*const|fold|eval_const|constant_value" in a7 · 42 matches
→ Read docs/audits/2026-09-20-core-v1/forward-globals-native.json [limit=80]
`const_eval.py` is directly relevant to the packet's arithmetic claims. Reading it in full.
→ Read a7/const_eval.py
Now checking the lexer's float handling, the backend constant emission, and local const declarations — all cited or implied by the packet.
✱ Grep "float\(|FLOAT_LITERAL|parse_float|literal_value=float" in a7 · 14 matches
→ Read a7/backends/zig.py [limit=45, offset=729]
✱ Grep "DECLARE_CONST|parse_const_or_function_decl" in a7 · 8 matches
→ Read a7/backends/zig.py [limit=55, offset=1680]
→ Read a7/parser.py [limit=65, offset=345]
→ Read a7/parser.py [limit=30, offset=1005]
→ Read a7/ast_nodes.py [limit=25, offset=441]
→ Read a7/tokens.py [limit=20, offset=578]
✱ Grep "create_const_decl\(" in . · 4 matches
✱ Grep "::\s*(i32|f64|u8|usize)" in examples · 0 matches
Checking the Python version requirement (relevant to the int-to-string digit limit in exact-constant emission).
✱ Grep "requires-python|python" in pyproject.toml · 100 matches
Review complete. Advisory findings only; no files modified, no compiler or Zig invocations, no sub-agents or nested CLIs launched (recursion guard held; reviewer identity GLM-5.3, security section GLM-owned per L12).

# Design review: P-TYP-forward-globals.md + L47 (decisions.md:127-137)

**Verdict.** The packet is internally coherent, honors L47's "development, not implementation" scope, and does not conflict with L5/L33 or L3/L4. Two findings need resolution before the packet is presented for implementation approval: the loss of constant infinity (F1) and the unbounded-resource operator table (F2). Verified current-behavior claims listed at the end.

## Findings

**F1 — HIGH (L16 conflict surface, compatibility).** Constant nonfinite values become unwritable. Today `1e400` lexes to `inf` (`a7/tokens.py:591`, `a7/ast_nodes.py:590` both call Python `float()`), the checker accepts any float literal for `f32`/`f64` (`a7/passes/type_checker.py:2994-2995`), and the backend emits `std.math.inf` (`a7/backends/zig.py:1690-1691,1719-1734`) — an accepted, building program today. The packet rejects it (overflow-to-infinity rejection, packet:92-96), also rejects `1.0 / 0.0` (packet:156), and introduces no typed-constant spelling (packet:120-122) — so no route to a constant infinity remains, while L16 (decisions.md:51) makes "NaN and infinity ordinary values". Runtime typed inf survives, but the removal of an L16-supported capability must be an explicit approval item.
Fix: add "huge-decimal-literal → inf" and "constant div-by-zero" as named classes in the compatibility comparison (packet:39-42), and either retain a typed-destination inf route or present its removal to the user under the approval rule.

**F2 — HIGH (GLM security review: compiler resource use).** The operator table admits double-exponential blowup from tiny source. Left shift carries only a nonnegativity precondition (packet:159-160): `1 << (1 << 30)` is a 128 MiB integer; nested shifts grow bit length as 2^(bit length). Exact `*` (packet:152) doubles bit length per squaring — ~30 multiplications reach gigabit values. Exact rationals from `/` (packet:154) grow denominators identically. The packet defers bounds to "a separate reviewed policy" (packet:257-258); that policy must be a **blocking prerequisite** for implementation approval, and the packet should say so at the operator table, not only in remaining-work. Two concrete hazards for that policy: (a) diagnostics that print "the exact offending value" (packet:224-225) must truncate rendering — a 100 MB integer in an error message is itself a DoS; (b) on the required Python ≥3.13 (`pyproject.toml:6`), `str(int)` beyond 4300 digits raises `ValueError` (`sys.set_int_max_str_digits`) — emission and diagnostics will crash, not degrade, unless handled.

**F3 — MEDIUM (internal consistency).** Packet:99-101 defers "operations producing nonfinite untyped values" as outside scope, but the table at packet:156 already decides `1.0 / 0.0` → reject. Pick one: either own the decision (and record current behavior — `const_eval.py:113-118` leaves it unfolded for Zig comptime; its Zig-side outcome is unverified by me) or defer it with the rest.

**F4 — MEDIUM (clarity).** Stated preconditions without stated failure modes: negative shift counts (packet:159-160) and the out-of-range default where no destination exists, e.g. variadic formatting (packet:185) — the "ask for an explicit destination type" remedy (packet:106-108) does not apply there. Neither appears in the diagnostics list (packet:224-227).

**F5 — MEDIUM (compat evidence).** Untyped integer `/` truncates toward zero (packet:153), matching today's folding (`const_eval.py:77-82`) and L33's approved convention (decisions.md:72-78), but typed integer division/remainder is explicitly undecided under gate G3 (decisions.md:141-145). Add one sentence noting the dependency so G3 is later decided knowing untyped constants precommit the sign convention.

**F6 — LOW (clarity).** `2.0 & 3` rejects (floating category excluded by packet:158 despite integrality per packet:147-149) — no example says so. Unary `~` on negative mathematical integers is implied by "sign extension" but unstated.

**F7 — LOW (implementation constraint for packet:256-257).** f32 materialization must round decimal→f32 in one correctly rounded step; converting via Python `float` (f64) then narrowing double-rounds and can violate round-to-nearest-ties-to-even at destination width (packet:92-93).

**F8 — INFO.** Mixed comparison asymmetry is stated but split across sections: `x: f64 = 0.1; x == 0.1` is true via operand fitting (packet:184) while untyped `0.1 + 0.2 == 0.3` is true exactly (packet:142-144). One combined example would prevent user confusion. Truncating division vs arithmetic (floor) right shift (packet:153,160) is stated and matches C/Zig; no action.

## Verified claims (source-checked)

- Forward/backward `RATE` asymmetry: `a7/passes/name_resolution.py:342-353` (UNKNOWN registration), `a7/passes/type_checker.py:183-185` (source-order checking), `a7/types.py:108-140` (f64→i32 rejected), `a7/types.py:518-520` (UnknownType accepts all).
- Defaults i32/f64 "retained": `a7/passes/type_checker.py:1203-1208`.
- Float rounding happens before the checker: lexer/AST store Python floats (`a7/tokens.py:591`, `a7/ast_nodes.py:589-590`); `9007199254740993.0` losing its last digit is real.
- String `{any}` vs `{s}` byte-list claim: preserved native evidence (`docs/audits/2026-09-20-core-v1/forward-globals-native.json:28-30,59-61`).
- Packet:120-122's open question is answerable now: no typed `::` const syntax exists — all three `create_const_decl` call sites (`a7/parser.py:288,404,1044`) omit `explicit_type`, making `type_checker.py:652` unreachable for consts.
- L5 consistency: typed wrapping preserved (packet:132-133, 240-241); L33 consistency: untyped `%` formula and sign match `const_eval.py:77-82,116` and decisions.md:72-78; L3/L4: untyped is compiler-internal with no runtime bignum (packet:55-56, 257).

## Unverified areas

- No compiler, Zig, or example execution (docs-only review; runtime claims rest on the preserved evidence JSONs).
- Zig comptime behavior of unfolded `1.0 / 0.0` (relevant to F3).
- The 135/255 corpus numbers in the history packet (taken as recorded, not re-measured).
- Odin's primary documentation (read only via the research summary).
- Whether existing `examples/`/`test/` sources contain huge literals or nonfinite constants that would newly reject — that scan is the packet's own pending compatibility work.
