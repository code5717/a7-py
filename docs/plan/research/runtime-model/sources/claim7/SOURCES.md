<!-- Preserved 2026-09-19 from tmp/research/runtime-model/sources/claim7/SOURCES.md. Repository home-path prefixes normalized; claims and verification statements below are historical. Saved files remain beside the original temporary manifest. -->

# Claim 7 sources — live dynamic schema evolution

All read 2026-09-18. Every quote grep-verified against the saved file with
`tr -s '[:space:]' ' ' < <file>.txt | grep -o -F '<quote>'`.

### Live++ documentation — "Structural changes"
URL: https://liveplusplus.tech/docs/documentation.html
Saved: livepp.html / livepp.txt
Kind: vendor doc (commercial C++ live-coding product; the state of the art)
Quote: "The following operations are considered "structural changes": Changing the memory layout of a class declaration, which includes: adding or removing base classes adding or removing non-static data members changing the order of non-static data members"
Quote: "When making structural changes to existing code and data, Live++ has to make sure that new code can correctly work with existing data allocated and stored in an old memory layout. In order to do so, existing objects must have their data migrated from the old into the new memory layout, which can be achieved by using pre-patch and post-patch hot-reload hooks."
Quote: "The basic idea is always the same: Serialize the data members of existing objects into memory. Delete the objects. Re-create the objects using the new class layout. Serialize the data members from memory to the new objects."
Quote: "Keep in mind that objects created on the stack cannot be migrated to a new class layout."
Note: The shipping product does exactly the opposite of claim 7's "in-place ... automatic": migration is serialize-delete-recreate-deserialize, written by hand by the user in hooks, and stack objects are excluded entirely.

### JVM Tool Interface — RedefineClasses
URL: https://docs.oracle.com/en/java/javase/21/docs/specs/jvmti.html
Saved: jvmti.html / jvmti.txt
Kind: spec
Quote: "Instances of the redefined class are not affected -- fields retain their previous values."
Quote: "The redefinition must not add, remove or rename fields or methods, change the signatures of methods, change modifiers, or change inheritance."
Note: A managed runtime with a precise moving collector and full reference knowledge still forbids the schema change outright. It swaps behavior only.

### Erlang/OTP — code loading
URL: https://www.erlang.org/doc/system/code_loading.html
Saved: erl_codeloading.html / erl_codeloading.txt
Kind: project doc
Quote: "If then a new instance of the module is loaded, the code of the previous instance becomes 'old' and the new instance becomes 'current'."
Quote: "Both old and current code are valid, and can be evaluated concurrently."
Quote: "If a third instance of the module is loaded, the code server removes (purges) the old code and any processes lingering in it are terminated."
Quote: "To change from old code to current code, a process must make a fully qualified function call."
Note: The mature model. Two versions coexist; the transition point is explicit and program-visible (a fully qualified call, and `code_change/3` for gen_server state). Not automatic and not in-place: the process rewrites its own state at a point it chooses.

### Linux kernel livepatch — shadow variables
URL: https://docs.kernel.org/livepatch/shadow-vars.html
Saved: shadow-vars.html / shadow-vars.txt
Kind: kernel doc
Quote: "Shadow variables are a simple way for livepatch modules to associate additional "shadow" data with existing data structures. Shadow data is allocated separately from parent data structures, which are left unmodified."
Note: The production live-patching system for a whole OS kernel cannot add a field to a live struct. Its answer is a side hashtable keyed by the parent pointer. Direct counter-evidence to "migrated into the new layout in-place".

### Linux kernel livepatch — consistency model and limitations
URL: https://docs.kernel.org/livepatch/livepatch.html
Saved: livepatch.html / livepatch.txt
Kind: kernel doc
Quote: "the affected unit (thread, whole kernel) need to start using all new versions of the functions at the same time. Also the switch must happen only when it is safe to do so, e.g. when the affected locks are released or no data are stored in the modified structures at the moment."
Quote: "The theory about how to apply functions a safe way is rather complex."
Quote: "Only functions that can be traced could be patched."
Note: Even behavior-only replacement needs a quiescence argument per task. Establishes the cost the claim does not mention.

### Unity Entities — structural changes
URL: https://docs.unity3d.com/Packages/com.unity.entities@1.3/manual/concepts-structural-changes.html
Saved: unity_structural.html / unity_structural.txt
Kind: vendor doc
Quote: "When you add or remove components from an entity, you change the entity's archetype. Unity stores each entity in a chunk that matches the entity's archetype. This means that if you change an entity's archetype, Unity must move the entity to another chunk."
Quote: "You can't make structural changes directly in a job because it might invalidate other jobs that are already scheduled, and creates a synchronization point (sync point)."
Quote: "Structural changes to the data in ECS are the primary cause of sync points."
Note: A shipping ECS designed around flat data still moves the instance when its shape changes, and the move is a concurrency sync point. Changing a type's shape is a relocation, not an in-place edit — and the language pays for it by handing out entity ids rather than pointers.

## Not obtained
- Unity "Enter Play mode without domain reload" manual page: fetched, but the body is JavaScript-rendered; the saved file contains navigation chrome only. No quote taken.
- Unreal Engine Live Coding documentation on dev.epicgames.com: not fetched; Live++ is the same technology and is documented statically, so it was used instead.
- Smalltalk `become:` primary documentation: not obtained.
