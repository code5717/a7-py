# P-STD: collections, string, and mem scope

Proposed decision, not approved or implemented. Track 5 of the rewrite
roadmap deferred a full collections stdlib from the surface-cut PR. This
packet states the scope and example outline that need user approval before
any `std/list`, `std/map`, `std/string`, or `std/mem` work lands.

Authority already on disk: L42 (list assignment shares identity; explicit
copy), L68 (hybrid typed hooks plus shipped `.a7` sources; U1–U14 take the
stdlib proposal's recommended options), L17/L19/L21 (no allocator parameters
in public signatures), L39 (prefer proof; checked `get` where proof fails).
Design detail lives in
[stdlib-proposal.md](../../audits/2026-10-04/stdlib-proposal.md) §§3.4,
3.18–3.19 and related Phase B notes. This packet does not re-open L68's
architecture choice.

## Choice

Ship compiler-known growable collections and thin string/mem helpers under
`std/`, not as ordinary A7 structs that copy on assignment. Keep fixed arrays
and slices as the current non-growable surface until this packet is approved.

| Module | Role | Why not A7-only today |
| --- | --- | --- |
| `std/list` | Growable `List(T)` handle | L42 shared identity; no runtime-sized heap buffer (`new [N]T` rejected); generic returns still limited |
| `std/map` / `std/set` | Growable maps/sets | Same blockers plus string equality/hash hooks |
| `std/string` (or `std/strings`) | Read-only `string` views and builders | Needs `len`/`eq`/`sub` hooks; owning string waits on memory mechanism |
| `std/mem` | Small byte/copy helpers over caller buffers | Avoids allocator APIs; complements slices without inventing a heap |

Out of this packet: package registry, networking, regex, fresh crypto, and
any automatic-memory mechanism selection (Track 3 / L38). Those stay separate
approvals.

## Compatibility

Before:

- `import "std/list"` / `std/map` / `std/string` / `std/mem` fail at resolution.
- Growable containers are not a language type. Authors use fixed arrays,
  slices, and manual structs.
- User variadics and destructuring are cut; they are not a substitute API.

After (if approved and implemented):

```a7
io :: import "std/io"
list :: import "std/list"

main :: fn() {
    xs := list.make(i32)
    list.push(xs, 3)
    ys := xs
    list.push(ys, 4)
    io.println("{}", list.len(xs))  // 2 under L42 shared identity
}
```

```a7
io :: import "std/io"
map :: import "std/map"

main :: fn() {
    counts := map.make(string, i64)
    map.put(counts, "a", 1)
    match map.get(counts, "a") {
        case .some(n): { io.println("{}", n) }
        case .none: { io.println("absent") }
    }
}
```

```a7
io :: import "std/io"
strings :: import "std/strings"

main :: fn() {
    io.println("{} {}", strings.len("hello"), strings.count_char("banana", 'a'))
}
```

```a7
mem :: import "std/mem"

main :: fn() {
    dst: [4]u8
    src: [4]u8 = [1, 2, 3, 4]
    _ := mem.copy(dst[0..4], src[0..4])
}
```

Breaking risk once shipped: programs that invent their own `List` / `Map`
type names may collide with package-owned identities (same class of rule as
`Option` / `Result`). The implementation PR must state the collision rule
before merge.

## Proposed API outline (approval target)

`std/list`: `make`, `push`, `pop` → `Option(T)`, `get` → `Option(T)`, `set`,
`len`, `items` (view), `copy` (L42 explicit copy), `clear`.

`std/map`: `make`, `put`, `get` → `Option(V)`, `has`, `remove`, `len`.
v1 keys: integers, `bool`, `char`, enums, `string`. Insertion-order
iteration. `Set(K)` as map-shaped helpers or a thin alias.

`std/strings`: `len`, `eq`/`compare`, `starts_with`, `ends_with`, `contains`,
`count_char`, `index_of_char` → `Option(usize)`, `sub`, `trim`. Read-only
views first; owning builder only after memory mechanism selection.

`std/mem`: caller-buffer `copy`, `eq`, and small fill helpers. No allocator
argument. Growth and ownership stay outside this module.

Error style follows existing `Option` / `Result` prelude types. Panic-only
`unwrap` is not proposed here.

## Examples outline (need approval before adding under `examples/`)

1. `0xx_list_share_copy.a7` — L42 share on `b := a`, then `list.copy`.
2. `0xx_map_counts.a7` — string keys, `get` match on `Option`.
3. `0xx_strings_scan.a7` — `len` / `contains` / `sub` over literals.
4. `0xx_mem_copy.a7` — `mem.copy` between stack byte slices.
5. Keep existing array/slice examples as the non-growable baseline.

Each example must pass debug/release/fast E2E after implementation. No example
may imply user variadics or destructuring.

## Prerequisites called out for a later implementation PR

- Memory / handle lowering for growable buffers (Track 3 mechanism still
  unselected for automatic memory; collections may still ship as explicit
  runtime handles under L68 hooks).
- Generic functions that return `List(T)` / `Option(T)` (proposal D6).
- String equality and map hashing hooks.
- Index/key policy: proof-or-reject for plain `xs[i]`; optional `get` for
  dynamic lookup (L39).

## Disposition

Record the user's approve / revise / reject answer in
[decisions.md](../decisions.md). Until that entry exists, do not add
`std/list`, `std/map`, `std/string`, or `std/mem` modules, examples, or
runnable docs claims for them.
