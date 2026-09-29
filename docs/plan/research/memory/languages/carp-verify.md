> **Source:** Claude research subagent, second pass. Verifies two claims in [carp.md](carp.md) that rested on DeepWiki, by reading `src/Memory.hs` and `src/Emit.hs` fetched from `raw.githubusercontent.com`.  
> **Date:** 2026-09-16.  
> **Status:** Advisory. Body preserved verbatim. The reuse finding is a negative result over two named files, not a proof of absence.

# Carp memory-management claims: primary-source verification

Sources fetched directly (raw GitHub, not DeepWiki):
- https://raw.githubusercontent.com/carp-lang/Carp/master/src/Memory.hs — fetched in full, read in full. [primary]
- https://raw.githubusercontent.com/carp-lang/Carp/master/src/Emit.hs — fetched in full (1499 lines incl. code fence), read in full across two passes. [primary]

Both fetches succeeded; no substitution with DeepWiki was used anywhere below.

---

## CLAIM A

> "Carp performs no compiler-inserted storage reuse — every managed value is a
> CARP_MALLOC and every dead one a CARP_FREE. Its only in-place reuse is
> hand-written library functions (endo-map, filter, aset!) operating on values
> you own."

**Verdict: Not falsified by source; no reuse/reset/recycling mechanism located
in `Memory.hs` or `Emit.hs`. Absence is not proven — see methodology note
below — but the search was a full read of both files, not a keyword grep.**

### What I searched for and did not find

I read `Memory.hs` (the whole file, ~500 lines) and `Emit.hs` (the whole file,
1499 lines) top to bottom, specifically looking for:

- Any token/handle-based "give away this storage" mechanism (Koka's reuse
  analysis / Lean's `reset`/`reuse` opcodes).
- Any place a `Deleter` or delete call is paired with, or replaced by, a
  subsequent allocation reusing the same pointer/slot.
- Any occurrence of the substrings "reuse", "reset" (as a memory-reuse
  concept — the only "reset" hit in the fetched text is a documentation
  string for `set!`, unrelated), "recycl", or a free-list/pool/token
  abstraction.

None of these appear in either file. [primary — negative result from a full
read of both files]

### What the deletion machinery actually is (Memory.hs)

`Memory.hs`'s job (per its own header comment) is only to compute *which*
deleters fire *where*; it does not touch allocation:

```haskell
-- | Find out what deleters are needed and where in an XObj.
-- | Deleters will be added to the info field on XObj so that
-- | the code emitter can access them and insert calls to destructors.
```

The `Deleter` values it produces are one of four constructors used
throughout the file: `ProperDeleter`, `FakeDeleter`, `PrimDeleter`,
`RefDeleter` (seen e.g. in `isAlive`, `deletersMatchingXObj`, `createDeleter`).
`createDeleter` is the constructor site:

```haskell
createDeleter :: TypeEnv -> Env -> XObj -> Maybe Deleter
createDeleter typeEnv globalEnv xobj =
  case xobjTy xobj of
    Just (RefTy _ _) -> Just (RefDeleter (varOfXObj xobj))
    Just t ->
      let var = varOfXObj xobj
       in if isManaged typeEnv globalEnv t
            then case nameOfPolymorphicFunction typeEnv globalEnv (FuncTy [t] UnitTy StaticLifetimeTy) "delete" of
              Just pathOfDeleteFunc ->
                Just (ProperDeleter pathOfDeleteFunc (getDropFunc typeEnv globalEnv (xobjInfo xobj) t) var)
              Nothing ->
                Just (FakeDeleter var)
            else Just (PrimDeleter var)
    Nothing -> error ("No type, can't manage " ++ show xobj)
```

Nothing here allocates, pools, or hands off storage — it only records the
path to a user's/generated `delete` function (and optionally a `drop`
function, see below) plus the variable name.

### What the deletion machinery actually is (Emit.hs)

The only place deleters become code is the `delete` function in `Emit.hs`:

```haskell
delete :: Int -> Set.Set Deleter -> State EmitterState ()
delete indent dels = mapM_ deleterToC dels
  where
    deleterToC :: Deleter -> State EmitterState ()
    deleterToC FakeDeleter {} =
      pure ()
    deleterToC PrimDeleter {} =
      pure ()
    deleterToC RefDeleter {} =
      pure ()
    deleterToC deleter@ProperDeleter {} = do
      let v = mangle (deleterVariable deleter)
      case dropPath deleter of
        Just path ->
          appendToSrc $ addIndent indent ++ "" ++ pathToC path ++ "(&" ++ v ++ ");\n"
        Nothing -> pure ()
      appendToSrc $ addIndent indent ++ "" ++ pathToC (deleterPath deleter) ++ "(" ++ v ++ ");\n"
```

Only `ProperDeleter` emits any code, and what it emits is a straight function
call — `<deleteFunctionName>(v);` — i.e. a call into the type's `delete`
function (which for managed heap types ultimately calls `CARP_FREE`, per the
runtime headers this task did not need to open since the claim was about the
*compiler*, not the runtime library). There is an optional `dropPath` call
emitted first (`<dropFunctionName>(&v);`). This `drop` mechanism is a
user-defined pre-destruction hook found via `getDropFunc`:

```haskell
getDropFunc :: TypeEnv -> Env -> Maybe Info -> Ty -> Maybe SymPath
getDropFunc typeEnv globalEnv i t =
  nameOfPolymorphicFunction typeEnv globalEnv (FuncTy [RefTy t (VarTy (makeTypeVariableNameFromInfo i))] UnitTy StaticLifetimeTy) "drop"
```

This is a "run this ref-taking function right before deleting" hook (akin to
a destructor callback / Drop trait), not a storage-reuse or reset mechanism:
it takes a *reference* to the value and returns Unit; it does not return or
repurpose storage for a new value. I did not find any code path where the
memory address freed by a `ProperDeleter`/`delete` call is captured and
handed to a subsequent `CARP_MALLOC`-avoiding allocation.

`CARP_MALLOC` appears only twice in `Emit.hs`, both plain allocations with no
paired reuse bookkeeping:
- Lambda environment struct allocation (`CARP_MALLOC(sizeof(<lambdaEnvType>))`).
- Array data allocation (`.data = CARP_MALLOC(sizeof(<innerTy>) * <len>)`).

`CARP_FREE` does not appear anywhere in `Emit.hs`'s text at all (the free
calls are always indirect, through the emitted `<Type>_delete(...)` function
name resolved by `pathToC (deleterPath deleter)`, not a literal `CARP_FREE`
call site in this file).

### Methodology caveat (as instructed)

This is a negative claim. I did not exhaustively verify that no reuse
mechanism exists anywhere in the ~15k-line Carp compiler (e.g. `Concretize.hs`,
`Deftype.hs`, `Lookup.hs`, template files, or the C runtime headers) — the
task scoped the check to `Memory.hs` and `Emit.hs`, which are the two files
that own, respectively, "decide what to delete" and "emit the delete/alloc
code." Within those two files, read in full, no reuse/reset/recycling
mechanism exists. **Absence outside those two files is not established by
this task and should not be asserted.**

---

## CLAIM B

> "Frees are inserted at the end of the owner's lexical scope, not at last
> use."

**Verdict: Confirmed by source. `manageMemory`'s `let`, `defn`, `while`, `if`,
and `match` cases all compute the delete set as "still-owned-and-unmanaged at
the end of the block" and attach it to the info of the enclosing scope form
(the `let`/`defn`/etc. node itself), not to the XObj that was last used.**
[primary]

### The `let` case (this is the clearest, most direct evidence)

From `manageMemory`'s `visitList`, the `LetPat` branch:

```haskell
-- Let
LetPat letExpr (XObj (Arr bindings) bindi bindt) body ->
  do
    preDeleters <- gets memStateDeleters
    visitedBindings <- mapM visitLetBinding (pairwise bindings)
    visitedBody <- visit body
    result <- unmanage typeEnv globalEnv body
    whenRight result $
      do
        postDeleters <- gets memStateDeleters
        let diff = postDeleters Set.\\ preDeleters
            newInfo = setDeletersOnInfo i diff
            survivors = postDeleters Set.\\ diff -- Same as just pre deleters, right?!
        modify (\m -> m {memStateDeleters = survivors})
        --trace ("LET Pre: " ++ show preDeleters ++ "\nPost: " ++ show postDeleters ++ "\nDiff: " ++ show diff ++ "\nSurvivors: " ++ show survivors)
        manage typeEnv globalEnv xobj
        pure $ do
          okBody <- visitedBody
          let finalBody = searchForInnerBreak diff okBody
          okBindings <- fmap (concatMap (\(n, x) -> [n, x])) (sequence visitedBindings)
          pure (XObj (Lst [letExpr, XObj (Arr okBindings) bindi bindt, finalBody]) newInfo t)
```

Read closely: `preDeleters` is the set of live deleters *before* entering the
`let`. The whole body is visited (walking every binding and every expression
in it, wherever last-use actually happens). Only *after* the entire body has
been visited is `postDeleters` sampled, and `diff = postDeleters \\
preDeleters` is computed — i.e., every variable that became owned somewhere
inside this `let` and was never transferred/unmanaged by the time the whole
body finished. That `diff` (not a per-variable, per-last-use set) is attached
via `newInfo = setDeletersOnInfo i diff` to `i`, which is the `Info` of the
**`let` xobj itself** (the enclosing scope form), and the resulting `newInfo`
is placed on the outer `Lst [letExpr, ..., finalBody]` node returned for the
whole `let`.

The `Emit.hs` side confirms where that attached info actually surfaces as
code — at the closing brace of the `let`'s C block, after the body's value
has already been computed and stored:

```haskell
-- Let
[XObj Let _ _, XObj (Arr bindings) _ _, body] ->
  ...
       appendToSrc (addIndent indent ++ "/* let */ {\n")
       ...
       ret <- visit indent' body
       when isNotVoid $
         appendToSrc (addIndent indent' ++ letBodyRet ++ " = " ++ ret ++ ";\n")
       delete indent' (infoDelete info)
       appendToSrc (addIndent indent ++ "}\n")
       pure letBodyRet
```

`delete indent' (infoDelete info)` — where `info` is the `let` form's own
`Info` (the one `manageMemory` attached the `diff` to) — runs after the
body's result has been captured into `letBodyRet` and immediately before the
closing `}` of the `let` block. This is "end of lexical scope," not "right
after the variable's last use" (which happened earlier, inside `visit
indent' body`).

### The `defn` (function body) case — same pattern at function scope

```haskell
[defn@(XObj (Defn maybeCaptures) _ _), nameSymbol@(XObj (Sym defPath _) _ _), args@(XObj (Arr argList) _ _), body] ->
  ...
        visitedBody <- visit body
        result <- unmanage typeEnv globalEnv body
        ...
        whenRightReturn result $
          do
            okBody <- visitedBody
            Right (XObj (Lst [defn, nameSymbol, args, okBody]) i t)
```

and at the top of `manageMemory`:

```haskell
manageMemory typeEnv globalEnv root =
  let (finalObj, finalState) = runState (visit root) (MemState Set.empty Set.empty Map.empty Set.empty Map.empty)
      deleteThese = memStateDeleters finalState
      ...
   in ...
        Right ok ->
          let newInfo = fmap (\i -> i {infoDelete = deleteThese}) (xobjInfo ok)
```

`deleteThese` is whatever is still in `memStateDeleters` after the *entire*
function body has been visited, attached to the function's own top-level
`Info`. `Emit.hs`'s `Defn` case then emits it right before the function's
`return`, at the end of the function body:

```haskell
else do
  emitLineDir body
  ret <- visit innerIndent body
  delete innerIndent (infoDelete info)
  case retTy of
    UnitTy -> when isMain $ appendToSrc (addIndent innerIndent ++ "return 0;\n")
    _ -> appendToSrc (addIndent innerIndent ++ "return " ++ ret ++ ";\n")
```

### The `while` and `if` cases also attach to the *construct's* info, not per-use

`while`:
```haskell
WhilePat whileExpr expr body ->
  do
    preDeleters <- gets memStateDeleters
    ...
    postDeleters <- gets memStateDeleters
    ...
    let diff = postDeleters \\ preDeleters
    modify (\m -> m {memStateDeleters = postDeleters \\ diff})
    pure $ do
      ...
      let newInfo = setDeletersOnInfo i diff
      ...
      pure (XObj (Lst [whileExpr, newExpr, finalBody]) newInfo t)
```

`if` computes `deletedInTrue`/`deletedInFalse` (`preDeleters \\
memStateDeleters stillAliveTrue`, etc.) and attaches the resulting sets to
each branch's own info via `setDeletersOnXObj okTrue delsTrue` /
`setDeletersOnXObj okFalse delsFalse` — i.e. deletion happens at the end of
each *branch* (a lexical scope), not pinned to the specific last-using
sub-expression within the branch.

### Conclusion for Claim B

Confirmed directly from `Memory.hs` (the `diff = postDeleters \\ preDeleters`
pattern computed after visiting an entire scope body, attached to that
scope-form's own `Info`) and cross-checked in `Emit.hs` (the `delete
indent (infoDelete info)` call sites are placed at the closing of each scope
block — end of `let`, end of function body, end of `if`/`while` iteration —
after the scope's result value has already been produced). This is
lexical-scope-end insertion, not last-use insertion. [primary]

---

## OPTIONAL: `Function_delete` / `if (f.delete)` runtime branch

**Not located in `Emit.hs`; reporting as unverified within the scope of this
task.**

`Emit.hs` does construct the `Lambda` struct literal with a `.delete` field
(function pointer, possibly `NULL`) at two sites:

```haskell
appendToSrc (addIndent indent ++ "Lambda " ++ var ++ " = { .callback = (void*)" ++ pathToC path ++ ", .env = NULL, .delete = NULL, .copy = NULL }; //" ++ show sym ++ "\n")
```

and, for a lambda that captures variables:

```haskell
appendToSrc (addIndent indent ++ "  .delete = (void*)" ++ (if needEnv then "" ++ show lambdaEnvTypeName ++ "_delete" else "NULL") ++ ",\n")
```

But `Emit.hs` never itself emits a *call* to that `.delete` field — I found
no `if (f.delete)` or `if (<x>.delete)` conditional-call code being generated
anywhere in the 1499-line file (the `deleterToC`/`delete` function shown
above only ever calls fixed, statically-known delete functions by path, never
a Lambda struct's runtime `.delete` field). The runtime code that actually
invokes a `Lambda`'s `.delete` pointer at teardown (if it exists) would live
in the Carp runtime's C headers/templates (e.g. `core/`, `Types.hs`
templates, or a `shared.h`-style runtime file), which were out of scope for
this task (only `Memory.hs` and `Emit.hs` were to be checked). **Unverified —
not found in the two files checked; the calling site, if any, is elsewhere in
the repository.**
