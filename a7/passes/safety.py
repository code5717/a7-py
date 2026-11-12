"""Internal safety proof and backend-plan analysis for A7.

This pass owns value facts and risky-operation approval. The type checker
answers base type questions; this analysis turns those typed expressions into
obligations, discharges the obligations from local facts, and records the exact
operations the backend is allowed to lower.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum, auto
import math
from pathlib import Path
from typing import Optional

from a7.ast_nodes import ASTNode, AssignOp, BinaryOp, LiteralKind, NodeKind, UnaryOp
from a7.cast_classifier import CastClass, CastDecision, classify_cast
from a7.errors import SourceSpan, TypeCheckError, TypeErrorType
from a7.symbol_table import SymbolTable
from a7.passes.readonly_requirements import ReadonlyRequirements
from a7.proof_discharge import (
    OBLIGATION_MESSAGES,
    BackendPlan,
    DischargeLedger,
    Obligation,
    ObligationKind,
    ProofResult,
    SafetyError,
    record_safety_result,
)
from a7.types import (
    ArrayType,
    EnumType,
    FunctionType,
    INTEGER_RANGES,
    PrimitiveType,
    ReferenceType,
    SIGNED_INTEGER_WIDTHS,
    SliceType,
    StructType,
    Type,
    TypeKind,
    UnionType,
    UNSIGNED_INTEGER_WIDTHS,
)

# Compatibility re-exports for callers that imported these from safety.
__all__ = [
    "AllocationGraph",
    "BackendPlan",
    "Obligation",
    "ObligationKind",
    "ProofResult",
    "SafetyError",
    "SafetyProofPass",
]


class TypeCategory(Enum):
    SIGNED_INTEGER = auto()
    UNSIGNED_INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    REF = auto()
    POINTER = auto()
    ARRAY = auto()
    SLICE = auto()
    STRUCT = auto()
    ENUM = auto()
    UNION = auto()
    FUNCTION = auto()
    GENERIC = auto()
    OTHER = auto()


# Aliases onto the canonical a7.types.INTEGER_RANGES table. Values flow from
# the single source; the old names stay so the many uses below are untouched.
SIGNED_RANGES = {name: INTEGER_RANGES[name] for name in SIGNED_INTEGER_WIDTHS}
UNSIGNED_RANGES = {name: INTEGER_RANGES[name] for name in UNSIGNED_INTEGER_WIDTHS}

# Aggregate elements without a tracked field path retain the older conservative
# loop invalidation of their base. Field paths invalidate only that field.
DEL_TARGET_BASE_ATTRS = {
    NodeKind.FIELD_ACCESS: "object",
    NodeKind.INDEX: "object",
    NodeKind.SLICE: "object",
    NodeKind.DEREF: "pointer",
}

EXIT_KINDS = {NodeKind.RETURN, NodeKind.BREAK, NodeKind.CONTINUE}
LOOP_KINDS = {NodeKind.WHILE, NodeKind.FOR, NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}

def categorize_type(type_: Type) -> TypeCategory:
    if isinstance(type_, PrimitiveType):
        if type_.name in SIGNED_RANGES:
            return TypeCategory.SIGNED_INTEGER
        if type_.name in UNSIGNED_RANGES:
            return TypeCategory.UNSIGNED_INTEGER
        if type_.name in {"f32", "f64"}:
            return TypeCategory.FLOAT
        if type_.name == "bool":
            return TypeCategory.BOOLEAN
    if isinstance(type_, ReferenceType):
        return TypeCategory.REF
    if type_.kind is TypeKind.POINTER:
        return TypeCategory.POINTER
    if isinstance(type_, ArrayType):
        return TypeCategory.ARRAY
    if isinstance(type_, SliceType):
        return TypeCategory.SLICE
    if type_.kind is TypeKind.STRUCT:
        return TypeCategory.STRUCT
    if type_.kind is TypeKind.ENUM:
        return TypeCategory.ENUM
    if isinstance(type_, UnionType):
        return TypeCategory.UNION
    if isinstance(type_, FunctionType):
        return TypeCategory.FUNCTION
    if type_.kind in {TypeKind.GENERIC_PARAM, TypeKind.GENERIC_INSTANCE, TypeKind.TYPE_SET}:
        return TypeCategory.GENERIC
    return TypeCategory.OTHER


@dataclass(frozen=True)
class IntegerInterval:
    lower: Optional[int] = None
    upper: Optional[int] = None

    @classmethod
    def exact(cls, value: int) -> "IntegerInterval":
        return cls(value, value)

    def contains(self, low: int, high: int) -> bool:
        return self.lower is not None and self.upper is not None and low <= self.lower and self.upper <= high

    def is_nonzero(self) -> bool:
        return (self.upper is not None and self.upper < 0) or (self.lower is not None and self.lower > 0)

    def is_nonnegative(self) -> bool:
        return self.lower is not None and self.lower >= 0

    def add(self, other: "IntegerInterval") -> "IntegerInterval":
        lo = None if self.lower is None or other.lower is None else self.lower + other.lower
        hi = None if self.upper is None or other.upper is None else self.upper + other.upper
        return IntegerInterval(lo, hi)

    def sub(self, other: "IntegerInterval") -> "IntegerInterval":
        lo = None if self.lower is None or other.upper is None else self.lower - other.upper
        hi = None if self.upper is None or other.lower is None else self.upper - other.lower
        return IntegerInterval(lo, hi)

    def mul(self, other: "IntegerInterval") -> "IntegerInterval":
        if None in {self.lower, self.upper, other.lower, other.upper}:
            return IntegerInterval()
        values = [
            self.lower * other.lower,
            self.lower * other.upper,
            self.upper * other.lower,
            self.upper * other.upper,
        ]
        return IntegerInterval(min(values), max(values))


class AllocationGraph:
    def __init__(self):
        self.nodes = [(False, ()), (True, ())]
        self.intern = {node: index for index, node in enumerate(self.nodes)}
        self.cardinality = [0, 1]
        self.combinations = {}

    def _node(self, terminal, edges):
        node = (terminal, tuple(sorted(((label, child) for label, child in edges if child), key=lambda pair: repr(pair[0]))))
        found = self.intern.get(node)
        if found is not None:
            return found
        result = len(self.nodes)
        self.nodes.append(node)
        self.intern[node] = result
        self.cardinality.append(min(2, int(terminal) + sum(self.cardinality[child] for _, child in node[1])))
        return result

    def prefix(self, label, child):
        return self._node(False, ((label, child),)) if child else 0

    def atom(self, label):
        return self.prefix(label, 1)

    def union(self, roots):
        result = 0
        for root in roots:
            result = self.combine('union', result, root)
        return result

    def combine(self, operation, left, right):
        # Children always predate parents. Pair memoization also shares the
        # repeated suffixes reached through different invocation alternatives.
        pending = [(left, right, False)]
        while pending:
            a, b, finish = pending.pop()
            key = (operation, a, b)
            if key in self.combinations:
                continue
            if operation == 'union' and (a == b or not a or not b):
                self.combinations[key] = a or b
                continue
            if operation == 'intersection' and (a == b or not a or not b):
                self.combinations[key] = a if a == b else 0
                continue
            if operation == 'difference' and (a == b or not a or not b):
                self.combinations[key] = 0 if a == b else a
                continue
            a_terminal, a_edges = self.nodes[a]
            b_terminal, b_edges = self.nodes[b]
            a_edges, b_edges = dict(a_edges), dict(b_edges)
            shared = a_edges.keys() & b_edges.keys()
            if not finish:
                pending.append((a, b, True))
                pending.extend((a_edges[label], b_edges[label], False) for label in shared)
                continue
            edges = {label: self.combinations[(operation, a_edges[label], b_edges[label])] for label in shared}
            if operation == 'union':
                terminal = a_terminal or b_terminal
                edges.update((label, child) for label, child in a_edges.items() if label not in shared)
                edges.update((label, child) for label, child in b_edges.items() if label not in shared)
            elif operation == 'intersection':
                terminal = a_terminal and b_terminal
            else:
                terminal = a_terminal and not b_terminal
                edges.update((label, child) for label, child in a_edges.items() if label not in shared)
            self.combinations[key] = self._node(terminal, edges.items())
        return self.combinations[(operation, left, right)]


class AllocationConditions:
    """Shared Boolean conditions; allocation identity stays in AllocationGraph."""

    def __init__(self):
        self.nodes = [(None, 0, 0), (None, 1, 1)]
        self.intern = {}
        self.cache = {}
        self.next_variable = 0

    def node(self, variable, low, high):
        if low == high:
            return low
        key = (variable, low, high)
        if key not in self.intern:
            self.intern[key] = len(self.nodes)
            self.nodes.append(key)
        return self.intern[key]

    def combine(self, operation, left, right):
        work = [(left, right, False)]
        while work:
            a, b, finish = work.pop()
            key = (operation, a, b)
            if key in self.cache:
                continue
            if a == b:
                self.cache[key] = 0 if operation == 'xor' else a
                continue
            if operation == 'and' and (a in (0, 1) or b in (0, 1)):
                self.cache[key] = 0 if not a or not b else b if a == 1 else a
                continue
            if operation == 'or' and (a in (0, 1) or b in (0, 1)):
                self.cache[key] = 1 if a == 1 or b == 1 else b if a == 0 else a
                continue
            if operation == 'xor' and (not a or not b):
                self.cache[key] = a or b
                continue
            av, al, ah = self.nodes[a]
            bv, bl, bh = self.nodes[b]
            variable = bv if av is None else av if bv is None else min(av, bv)
            low = (al if av == variable else a, bl if bv == variable else b)
            high = (ah if av == variable else a, bh if bv == variable else b)
            if not finish:
                work.append((a, b, True))
                work.extend((x, y, False) for x, y in (low, high))
                continue
            self.cache[key] = self.node(variable, self.cache[(operation, *low)], self.cache[(operation, *high)])
        return self.cache[(operation, left, right)]


@dataclass(frozen=True)
class AllocationRef:
    root: int
    condition: int = 1

@dataclass(frozen=True)
class SlotDeath:
    key: str
    condition: int = 1



@dataclass(frozen=True)
class ValueFact:
    interval: Optional[IntegerInterval] = None
    nonzero: bool = False
    known_length: Optional[int] = None
    upper_length_of: Optional[str] = None
    non_nil: bool = False
    maybe_nil: bool = False
    initialized: bool = True
    moved: bool = False
    enum_discriminant: Optional[str] = None
    allocations: frozenset[str | AllocationRef] = frozenset()
    # Possible children of a selected holder constrain reads, but deleting a
    # selected child must not mark every possible concrete child as freed.
    selected_allocations: frozenset[str | AllocationRef] = frozenset()
    # Exact slot provenance is local to straight-line control flow.
    exact_array_alias: bool = False
    boolean: Optional[bool] = None
    boolean_condition: Optional[int] = None


@dataclass
class FactMap:
    """Facts per expression node, variable and reference field path.

    `by_symbol` is keyed by declaration key (see `SafetyProofPass._bind_names`),
    so two variables with the same name never share a fact.
    """

    by_node: dict[int, ValueFact] = field(default_factory=dict)
    by_symbol: dict[str, ValueFact] = field(default_factory=dict)

    def node(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        return self.by_node.get(id(node), ValueFact())

    def symbol(self, name: Optional[str]) -> ValueFact:
        if not name:
            return ValueFact()
        return self.by_symbol.get(name, ValueFact())

    def set_node(self, node: ASTNode, fact: ValueFact) -> None:
        self.by_node[id(node)] = fact

    def set_symbol(self, name: str, fact: ValueFact) -> None:
        self.by_symbol[name] = fact

    def copy_symbols(self) -> dict[str, ValueFact]:
        return dict(self.by_symbol)

    def restore_symbols(self, saved: dict[str, ValueFact]) -> None:
        self.by_symbol = saved


class ExitFrame:
    """One block or loop between a statement and its function.

    A block frame holds the block's pending `defer` statements. A loop frame
    carries the loop node, and the states at each `continue` when the loop has
    an update statement to prove against them.
    """

    __slots__ = ("loop", "defers", "continues")

    def __init__(self, loop: Optional[ASTNode] = None):
        self.loop = loop
        self.defers: list[ASTNode] = []
        self.continues: list[tuple[dict[str, ValueFact], set[str]]] = []


@dataclass
class ParameterEffectState:
    aliases: dict[str | tuple[int, str], frozenset[tuple[int | AllocationRef, bool]]]
    deleted: set[int | AllocationRef] = field(default_factory=set)
    written: set[str] = field(default_factory=set)
    places: dict[str, Optional[frozenset[int | AllocationRef]]] = field(default_factory=dict)
    counter_delta: Optional[tuple[int, int]] = (0, 0)
    current_aliases: dict[str, frozenset[tuple[int | AllocationRef, bool]]] = field(default_factory=dict)
    current_live: set[str] = field(default_factory=set)
    current_dead: set[str] = field(default_factory=set)
    replaced: set[str] = field(default_factory=set)
    replacement_escaped: bool = False
    current_nil: set[str] = field(default_factory=set)
    paths: frozenset[int] = frozenset({1})
    scalar_values: dict[str, int] = field(default_factory=dict)
    scalar_cases: dict[str, dict[int, int]] = field(default_factory=dict)

    def copy(self) -> ParameterEffectState:
        return ParameterEffectState(dict(self.aliases), set(self.deleted), set(self.written), dict(self.places), self.counter_delta, dict(self.current_aliases), set(self.current_live), set(self.current_dead), set(self.replaced), self.replacement_escaped, set(self.current_nil), self.paths, dict(self.scalar_values), {key: dict(values) for key, values in self.scalar_cases.items()})

    @staticmethod
    def join(states: list[ParameterEffectState], conditions: AllocationConditions) -> ParameterEffectState:
        aliases = {key: frozenset().union(*(state.aliases.get(key, frozenset({(-3, True)}) if isinstance(key, tuple) else frozenset())
                                           for state in states))
                   for key in set().union(*(state.aliases.keys() for state in states))}
        result = ParameterEffectState(aliases)
        result.current_aliases = {key: frozenset().union(*(state.current_aliases.get(key, frozenset()) for state in states))
                                  for key in set().union(*(state.current_aliases.keys() for state in states))}
        result.current_nil = set().union(*(state.current_nil for state in states))
        # Unequal backedge values widen to unknown instead of counting trips.
        result.scalar_values = {key: value for key, value in states[0].scalar_values.items()
                                if all(state.scalar_values.get(key) == value for state in states[1:])} if states else {}
        result.paths = frozenset().union(*(state.paths for state in states))
        reachable = []
        for state in states:
            region = 0
            for path in state.paths:
                region = conditions.combine('or', region, path)
            reachable.append(region)
        for key in set().union(*(state.scalar_cases.keys() for state in states)):
            possible, unknown = {}, 0
            for state, region in zip(states, reachable):
                covered = 0
                for value, guard in state.scalar_cases.get(key, {}).items():
                    guard = conditions.combine('and', guard, region)
                    covered = conditions.combine('or', covered, guard)
                    possible[value] = conditions.combine('or', possible.get(value, 0), guard)
                missing = conditions.combine('and', region, conditions.combine('xor', covered, 1))
                unknown = conditions.combine('or', unknown, missing)
            covered, conflict = 0, 0
            for guard in possible.values():
                conflict = conditions.combine('or', conflict, conditions.combine('and', covered, guard))
                covered = conditions.combine('or', covered, guard)
            valid = conditions.combine('xor', conditions.combine('or', unknown, conflict), 1)
            values = {value: region for value, guard in possible.items()
                      if (region := conditions.combine('and', guard, valid))}
            if values:
                result.scalar_cases[key] = values
        result.current_live = set.intersection(*(state.current_live for state in states)) if states else set()
        result.current_dead = set().union(*(state.current_dead for state in states))
        result.replaced = set().union(*(state.replaced for state in states))
        result.replacement_escaped = any(state.replacement_escaped for state in states)
        if any(state.counter_delta is None for state in states):
            result.counter_delta = None
        elif states:
            result.counter_delta = (min(state.counter_delta[0] for state in states),
                                    max(state.counter_delta[1] for state in states))
        for state in states:
            result.deleted.update(state.deleted)
            result.written.update(state.written)
            for key, origins in state.places.items():
                previous = result.places.get(key, frozenset())
                result.places[key] = None if origins is None or previous is None else origins | previous
        return result


class SafetyProofPass:
    """Collect and prove risky-operation obligations from typed AST facts."""

    def __init__(
        self,
        symbols: SymbolTable,
        node_types: dict[int, Type],
        *,
        discharge_ledger: Optional[DischargeLedger] = None,
    ):
        self.symbols = symbols
        self.node_types = node_types
        self._owns_discharge_ledger = discharge_ledger is None
        self.discharge_ledger = discharge_ledger if discharge_ledger is not None else DischargeLedger()
        self.facts = FactMap()
        self.obligations: list[Obligation] = []
        self.results: list[ProofResult] = []
        self.backend_plan = BackendPlan()
        self.errors: list[TypeCheckError] = []
        self.moved_symbols: set[str | AllocationRef | SlotDeath] = set()
        self.const_facts: dict[str, ValueFact] = {}
        self.current_stmt_span: Optional[SourceSpan] = None
        self.current_file = "<unknown>"
        self.source_lines: list[str] = []
        self.exact_effect_bodies: dict[str, ASTNode] = {}
        self.exact_effect_reasons: dict[str, set[str]] = {}
        self.function_deletes: dict[str, bool] = {}
        self.function_field_writes: dict[str, dict[int, set[str]]] = {}
        self.function_parameter_deletes: dict[str, set[int]] = {}
        self.capture_call_effects: dict[int, set[str]] = {}
        self.mutable_boolean_captures: set[str] = set()
        self.borrowed_keys: set[str] = set()
        self.repeated_boolean_keys: set[str] = set()
        self.escaped_arrays: set[str] = set()
        self.allocation_graph = AllocationGraph()
        self.allocation_conditions = AllocationConditions()
        self.allocation_places = {}
        self.allocation_place_names = {}
        self.global_origins: dict[int, str] = {}
        self.function_returns = {}
        self.literal_return_bodies = {}
        self.readonly_requirements = ReadonlyRequirements(self._key, self._type, set())
        self.function_global_effects = {}
        # True only when ordered origins describe every deletion in the body.
        self.function_direct_deletes = {}
        self.reference_globals = set()
        self.function_written_globals: dict[str, set[str]] = {}
        self.function_field_stores: dict[str, dict[tuple[int, str], frozenset[tuple[int | AllocationRef, bool]]]] = {}
        self.function_deleted_globals: dict[str, set[str]] = {}
        self.symbol_types: dict[str, Type] = {}
        self.file_variables: set[str] = set()
        self.allocation_graph = AllocationGraph()
        self.allocation_conditions = AllocationConditions()
        self.allocation_places = {}
        self.allocation_place_names = {}
        self._reset_bindings()

    def _reset_bindings(self) -> None:
        # (id(node), name) -> declaration key, for identifiers and declarations.
        self.keys: dict[tuple[int, str], str] = {}
        # id(scope owner node) -> keys declared in that scope.
        self.scope_keys: dict[int, list[str]] = {}
        # `defer` nodes that are direct statements of a block.
        self.block_defers: set[int] = set()
        self.frames: list[ExitFrame] = []
        # Frames below this index belong to the scope whose defers are running.
        self.defer_floor = 0
        # Keys that some fact names in `upper_length_of`. Grows only.
        self.length_targets: set[str] = set()
        # (node id, operation) pairs already reported or refused. A deferred
        # statement is proven once per scope exit.
        self.reported: set[tuple[int, str]] = set()
        self.refused_nonwrap: set[tuple[int, str]] = set()

    def analyze(self, program: ASTNode, filename: str = "<unknown>", *,
                executable_entry: Optional[ASTNode] = None) -> BackendPlan:
        self.current_file = filename
        self.errors = []
        self.obligations = []
        self.results = []
        self.backend_plan = BackendPlan()
        if self._owns_discharge_ledger:
            self.discharge_ledger = DischargeLedger()
        self.facts = FactMap()
        self.moved_symbols = set()
        self.const_facts = {}
        self.current_stmt_span = None
        self.function_deletes = {}
        self.symbol_types = {}
        self.allocation_graph = AllocationGraph()
        self.allocation_conditions = AllocationConditions()
        self.allocation_places = {}
        self.allocation_place_names = {}
        self._reset_bindings()
        self._bind_names(program)
        self._visit_program(program)
        # Entry identity comes from the original file before module merging.
        # Existing diagnostics retain priority; incomplete summaries stay unknown.
        if executable_entry is not None and not self.errors:
            name = self._key(executable_entry)
            violation, origin, disposition = self.readonly_requirements.evaluate(name, [])
            self.readonly_requirements.dispositions.append((id(executable_entry), name, disposition))
            if violation is True:
                origin_span = getattr(origin, "span", None)
                required = "readonly executable entry field access must remain non-nil"
                if origin_span is not None:
                    origin_file = getattr(origin_span, "origin_file", None) or self.current_file
                    origin_name = Path(origin_file).name if origin_file else "<unknown>"
                    required += (
                        f" (callee use in {origin_name} at line {origin_span.start_line}, "
                        f"column {origin_span.start_column})"
                    )
                obligation = self._obligation(ObligationKind.REF_NON_NIL, executable_entry,
                    "readonly_entry_precondition", None, required, TypeErrorType.CANNOT_DEREFERENCE)
                self._error(obligation, "reachable readonly callee read receives nil",
                    "Guard the reference or avoid the entry path that reads it")
        return self.backend_plan

    def _origin_set(self, values):
        ordinary = set()
        fresh = {}
        for origin, exact in values:
            if isinstance(origin, AllocationRef):
                key = (origin.root, exact)
                fresh[key] = self.allocation_conditions.combine('or', fresh.get(key, 0), origin.condition)
            else:
                ordinary.add((origin, exact))
        grouped = {}
        for (root, exact), condition in fresh.items():
            if root and condition:
                grouped.setdefault((exact, condition), []).append(root)
        ordinary.update((AllocationRef(self.allocation_graph.union(roots), condition), exact)
                        for (exact, condition), roots in grouped.items())
        return frozenset(ordinary)

    def _origin_intersection(self, values, deleted):
        result = {value for value in set(values) & set(deleted) if not isinstance(value, AllocationRef)}
        for left in values:
            if not isinstance(left, AllocationRef):
                continue
            for right in deleted:
                if isinstance(right, AllocationRef):
                    condition = self.allocation_conditions.combine('and', left.condition, right.condition)
                    root = self.allocation_graph.combine('intersection', left.root, right.root)
                    if root and condition:
                        result.add(AllocationRef(root, condition))
        return frozenset(result)

    def _condition_allocations(self, allocations, condition=1):
        result = {}
        for value in allocations:
            root = self._allocation_root((value,))
            active = self.allocation_conditions.combine('and', value.condition if isinstance(value, AllocationRef) else 1, condition)
            if root and active:
                result[root] = self.allocation_conditions.combine('or', result.get(root, 0), active)
        grouped = {}
        for root, active in result.items():
            grouped.setdefault(active, []).append(root)
        return frozenset(AllocationRef(self.allocation_graph.union(roots), active)
                         for active, roots in grouped.items())

    def _allocation_root(self, allocations):
        roots = []
        for identity in allocations:
            if isinstance(identity, AllocationRef):
                roots.append(identity.root)
                continue
            label = ('new', int(identity[4:])) if identity.startswith('new:') else ('identity', identity)
            root = self.allocation_graph.atom(label)
            roots.append(root)
            prefix = '@allocation:' + identity
            self.allocation_places[prefix] = root
            self.allocation_place_names[root] = prefix
        return self.allocation_graph.union(roots)

    def _allocation_count(self, allocations):
        return self.allocation_graph.cardinality[self._allocation_root(allocations)]

    def _allocation_place(self, allocations):
        root = self._allocation_root(allocations)
        if self.allocation_graph.cardinality[root] != 1:
            return None
        name = self.allocation_place_names.get(root)
        if name is None:
            name = f'@allocation:graph:{root}'
            self.allocation_place_names[root] = name
            self.allocation_places[name] = root
        return name

    def _allocation_prefixes(self, allocations):
        root = self._allocation_root(allocations)
        if not root:
            return []
        if self.allocation_graph.cardinality[root] == 1:
            return [self._allocation_place(allocations)]
        return [prefix for prefix, singleton in self.allocation_places.items()
                if self.allocation_graph.combine('intersection', root, singleton)]

    def _field_allocations(self, key):
        position = key.rfind('.')
        while position >= 0:
            prefix = key[:position]
            if prefix in self.allocation_places:
                parent = self.allocation_places[prefix]
                return frozenset({AllocationRef(self.allocation_graph.prefix(('field', key[position + 1:]), parent))})
            position = key.rfind('.', 0, position)
        return frozenset({f'field:{key}'})

    def _move_allocations(self, allocations, moved=None):
        moved = self.moved_symbols if moved is None else moved
        moved.update(self._condition_allocations(allocations))

    def _allocations_moved(self, allocations, moved=None):
        moved = self.moved_symbols if moved is None else moved
        return bool(self._origin_intersection(self._condition_allocations(allocations), moved))

    def _type(self, node: Optional[ASTNode]) -> Optional[Type]:
        return self.node_types.get(id(node)) if node is not None else None

    def _error(self, obligation: Obligation, reason: str, hint: Optional[str] = None) -> None:
        result = ProofResult(False, obligation, reason)
        self.results.append(result)
        record_safety_result(self.discharge_ledger, result)
        key = (obligation.node_id, obligation.backend_operation)
        if key in self.reported:
            return
        self.reported.add(key)
        context = f"{obligation.required_proof}: {reason}"
        headline = OBLIGATION_MESSAGES.get(obligation.kind.name)
        if obligation.diagnostic_code is not None:
            error = SafetyError.from_type(
                obligation.diagnostic_code,
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
                custom_message=headline,
                context=context,
            )
        else:
            error = SafetyError(
                f"{headline} ({context})",
                span=obligation.span,
                filename=self.current_file,
                source_lines=self.source_lines,
            )
        error.hint = hint
        self.errors.append(error)

    @staticmethod
    def _guard_subject(operand: Optional[ASTNode], placeholder: str, *, fields: bool = False) -> tuple[str, str]:
        """A guard can refine a binding or a field path rooted in a binding."""
        names = []
        while fields and operand is not None and operand.kind == NodeKind.FIELD_ACCESS:
            names.append(operand.field)
            operand = operand.object
        if operand is not None and operand.kind == NodeKind.IDENTIFIER and operand.name:
            return ".".join([operand.name, *reversed(names)]), ""
        return placeholder, f"Copy the value to a local '{placeholder}' first; proofs track local variables only. "

    def _prove(self, obligation: Obligation, reason: str) -> None:
        result = ProofResult(True, obligation, reason)
        self.results.append(result)
        self.backend_plan.approve(result)
        record_safety_result(self.discharge_ledger, result)

    def _obligation(
        self,
        kind: ObligationKind,
        node: ASTNode,
        operation: str,
        operand_type: Optional[Type],
        required: str,
        code: Optional[TypeErrorType],
    ) -> Obligation:
        obligation = Obligation(kind, id(node), operation, self._obligation_span(node), operand_type, required, code)
        self.obligations.append(obligation)
        return obligation

    def _obligation_span(self, node: ASTNode) -> Optional[SourceSpan]:
        """Span of the operation, else of its right operand, else of the statement.

        BINARY nodes have no span (PAR-04), so a division reports the divisor.
        """
        if node.span is not None:
            return node.span
        for attr in ("right", "index", "end", "operand", "expression"):
            child = getattr(node, attr, None)
            if isinstance(child, ASTNode) and child.span is not None:
                return child.span
        return self.current_stmt_span

    def _key(self, node: ASTNode, name: Optional[str] = None) -> str:
        """Declaration key of an identifier or declaration. A file-scope name is its own key."""
        name = node.name if name is None else name
        return self.keys.get((id(node), name), name)

    def _bind_names(self, program: ASTNode) -> None:
        """Give each local declaration its own key and resolve identifiers to it.

        A parameter, local, loop variable, match capture or nested function
        gets the key `name#n`. An identifier resolves to the innermost such
        declaration in scope where it is written, and keeps its bare name when
        only a file-scope declaration matches. Scopes follow
        `NameResolutionPass`. An initializer is resolved before its name is
        bound, so `x := x + 1` reads the outer `x`.
        """
        bound: dict[str, list[str]] = {}
        function_stack: list[int] = []
        declaration_owners: dict[str, int] = {}
        captured: set[str] = set()
        uses: list[tuple[ASTNode, int]] = []
        self.local_boolean_keys: set[str] = set()
        self.local_index_keys: set[str] = set()
        repeated_scopes: set[int] = set()
        open_scopes: list[tuple[int, list[str]]] = []
        count = 0
        work: list[tuple[str, object]] = [("visit", decl) for decl in reversed(program.declarations or [])]
        while work:
            action, item = work.pop()
            if action == "repeat_enter":
                repeated_scopes.add(id(item))
                continue
            if action == "repeat_exit":
                repeated_scopes.discard(id(item))
                continue
            if action == "open":
                open_scopes.append((id(item), []))
                if item.kind in LOOP_KINDS:
                    repeated_scopes.add(id(item))
                if item.kind == NodeKind.FUNCTION:
                    function_stack.append(id(item))
                continue
            if action == "close":
                owner, names = open_scopes.pop()
                repeated_scopes.discard(owner)
                if function_stack and owner == function_stack[-1]:
                    function_stack.pop()
                for name in names:
                    bound[name].pop()
                continue
            if action == "declare":
                node, name = item
                count += 1
                key = f"{name}#{count}"
                owner, names = open_scopes[-1]
                names.append(name)
                bound.setdefault(name, []).append(key)
                self.keys[(id(node), name)] = key
                self.scope_keys.setdefault(owner, []).append(key)
                if function_stack:
                    declaration_owners[key] = function_stack[-1]
                    typ = self._type(node)
                    if node.kind in {NodeKind.VAR, NodeKind.CONST} and isinstance(typ, PrimitiveType) and typ.name == "usize":
                        self.local_index_keys.add(key)
                    if (isinstance(typ, PrimitiveType) and typ.name == "bool") or (
                            node.param_type is not None and node.param_type.kind == NodeKind.TYPE_PRIMITIVE
                            and node.param_type.type_name == "bool"):
                        self.local_boolean_keys.add(key)
                        if repeated_scopes:
                            self.repeated_boolean_keys.add(key)
                continue
            node = item
            kind = node.kind
            if kind == NodeKind.IDENTIFIER:
                if function_stack:
                    uses.append((node, function_stack[-1]))
                if bound.get(node.name):
                    key = bound[node.name][-1]
                    self.keys[(id(node), node.name)] = key
                continue
            children = []
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    children.append(("visit", value))
                elif isinstance(value, list):
                    children.extend(("visit", child) for child in value if isinstance(child, ASTNode))
            steps: list[tuple[str, object]]
            if kind == NodeKind.FUNCTION:
                steps = [("declare", (node, node.name))] if open_scopes and node.name and (id(node), node.name) not in self.keys else []
                steps.append(("open", node))
                steps.extend(("declare", (param, param.name)) for param in node.parameters or [] if param.name)
                if node.body:
                    steps.append(("visit", node.body))
                steps.append(("close", None))
            elif kind == NodeKind.BLOCK:
                statements = node.statements or []
                self.block_defers.update(id(stmt) for stmt in statements if stmt.kind == NodeKind.DEFER)
                steps = [("open", node)]
                steps.extend(("declare", (stmt, stmt.name)) for stmt in statements if stmt.kind == NodeKind.FUNCTION and stmt.name)
                steps.extend(("visit", stmt) for stmt in statements)
                steps.append(("close", None))
            elif kind in {NodeKind.VAR, NodeKind.CONST}:
                steps = children
                if open_scopes and node.name:
                    steps.append(("declare", (node, node.name)))
            elif kind in {NodeKind.IF_STMT, NodeKind.WHILE}:
                steps = [("visit", node.condition)] if node.condition else []
                for branch in (node.then_stmt, node.else_stmt, node.body):
                    if branch is None:
                        continue
                    if branch.kind == NodeKind.BLOCK:
                        steps.append(("visit", branch))
                    else:
                        steps.extend([("open", branch), ("visit", branch), ("close", None)])
            elif kind == NodeKind.FOR:
                steps = [("open", node)]
                steps.extend(("visit", part) for part in (node.init, node.condition, node.update, node.body) if part)
                steps.append(("close", None))
            elif kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
                steps = [("visit", node.iterable)] if node.iterable else []
                steps.append(("open", node))
                steps.extend(("declare", (node, name)) for name in (node.index_var, node.iterator) if name)
                if node.body:
                    steps.append(("visit", node.body))
                steps.append(("close", None))
            elif kind in {NodeKind.MATCH, NodeKind.MATCH_EXPR}:
                steps = [("visit", node.expression)] if node.expression else []
                for case in node.cases or []:
                    steps.append(("open", case))
                    for pattern in case.patterns or []:
                        captures = pattern.kind == NodeKind.PATTERN_ENUM or (
                            pattern.kind == NodeKind.PATTERN_IDENTIFIER and pattern.is_capture_pattern
                        )
                        if captures and pattern.name:
                            steps.append(("declare", (pattern, pattern.name)))
                        else:
                            steps.append(("visit", pattern))
                    body = [case.statement, case.expression, *(case.statements or [])]
                    steps.extend(("visit", part) for part in body if part)
                    steps.append(("close", None))
                if isinstance(node.else_case, ASTNode):
                    steps.append(("visit", node.else_case))
                elif node.else_case:
                    steps = [*steps, ("open", node), *(("visit", stmt) for stmt in node.else_case), ("close", None)]
            else:
                steps = children
            if kind == NodeKind.WHILE:
                steps = [("repeat_enter", node), *steps, ("repeat_exit", node)]
            work.extend(reversed(steps))

        # Nested bodies resolve after their enclosing declarations. A forward
        # capture may therefore have no lexical key during the walk above.
        unresolved_captures = set()
        for use, owner in uses:
            symbol = self.symbols.resolved_uses.get(id(use))
            if symbol is not None and symbol.node is not None:
                key = self.keys.get((id(symbol.node), symbol.name))
            else:
                key = self.keys.get((id(use), use.name))
            if key is not None and declaration_owners.get(key) != owner:
                captured.add(key)
                if self._key(use) != key:
                    unresolved_captures.add(key)
        self.readonly_capture_candidates = self.local_boolean_keys & (captured - unresolved_captures)
        self.local_boolean_keys.difference_update(captured)
        self.local_index_keys.difference_update(captured)

    def _visit_program(self, node: ASTNode) -> None:
        # File-scope `::` constants cannot change, so their facts are computed
        # once and seeded into every function. File-scope `:=` variables are
        # never seeded.
        for decl in node.declarations or []:
            if decl.kind == NodeKind.CONST and decl.value:
                self.current_stmt_span = decl.span
                fact = self._visit_expr(decl.value)
                if decl.name:
                    self.const_facts[decl.name] = fact
                    self.facts.set_symbol(decl.name, fact)
        # Unknown function values may release their reference arguments. Known
        # bodies without deletion retain pointer identity across field writes.
        # Function keys include nested declarations and lexical shadowing.
        self.file_variables = {d.name for d in node.declarations or [] if d.kind == NodeKind.VAR and d.name}
        self.global_origins = {-5 - 2 * id(declaration): self._key(declaration)
                               for declaration in node.declarations or []
                               if declaration.kind == NodeKind.VAR and declaration.name}
        self.reference_globals = {self._key(d) for d in node.declarations or []
                                  if d.kind == NodeKind.VAR and isinstance(self._type(d), ReferenceType)}
        bodies = {}
        declarations = list(node.declarations or [])
        while declarations:
            declaration = declarations.pop()
            if declaration.kind == NodeKind.FUNCTION:
                bodies[self._key(declaration)] = declaration
            for value in vars(declaration).values():
                if isinstance(value, ASTNode):
                    declarations.append(value)
                elif isinstance(value, list):
                    declarations.extend(item for item in value if isinstance(item, ASTNode))
        self.function_field_writes = {name: {} for name in bodies}
        self.function_parameter_deletes = {name: set() for name in bodies}
        self.function_field_stores = {name: {} for name in bodies}
        self.function_returns = {name: (frozenset(), frozenset()) for name in bodies}
        self.function_global_effects = {name: ({}, frozenset(), frozenset()) for name in bodies}
        self.function_direct_deletes = {name: True for name in bodies}
        self.function_written_globals = {name: set() for name in bodies}
        calls: dict[str, set[str]] = {}
        self.borrowed_keys = set()
        assigned_keys = set()
        capture_own_effects = {}
        capture_calls = {}
        callable_copies = {}
        for name, decl in bodies.items():
            capture_own_effects[name] = set()
            capture_calls[name] = []
            deletes = False
            deleted_globals: set[str] = set()
            callees: set[str] = set()
            stack = [decl.body] if decl.body else []
            while stack:
                item = stack.pop()
                if item.kind == NodeKind.FUNCTION:
                    continue
                deletes |= item.kind == NodeKind.DEL
                if item.kind == NodeKind.ASSIGNMENT and item.target and item.target.kind == NodeKind.IDENTIFIER:
                    key = self._key(item.target)
                    assigned_keys.add(key)
                    capture_own_effects[name].add(key)
                    if key in self.file_variables:
                        self.function_written_globals[name].add(key)
                if item.kind == NodeKind.DEL:
                    if item.expression is None or item.expression.kind != NodeKind.IDENTIFIER:
                        self.function_direct_deletes[name] = False
                    deleted_key = self._place_key(item.expression)
                    if deleted_key and deleted_key.split(".")[0] in self.file_variables:
                        deleted_globals.add(deleted_key)
                if (item.kind in {NodeKind.VAR, NodeKind.CONST} and item.value is not None
                        and item.value.kind == NodeKind.IDENTIFIER and isinstance(self._type(item), FunctionType)):
                    callable_copies[self._key(item)] = self._key(item.value)
                if item.kind == NodeKind.CALL and item.function:
                    capture_calls[name].append(item)
                    capture_own_effects[name].update(self._key(arg) for index, arg in enumerate(item.arguments or [])
                                                    if arg.kind == NodeKind.IDENTIFIER and index in getattr(item, "implicit_ref_args", set()))
                    self.borrowed_keys.update(self._key(arg) for index, arg in enumerate(item.arguments or [])
                                              if arg.kind == NodeKind.IDENTIFIER and index in getattr(item, "implicit_ref_args", set()))
                    callee = item.function
                    if getattr(item, "stdlib_canonical", None):
                        pass
                    elif callee.kind == NodeKind.IDENTIFIER:
                        callees.add(self._key(callee))
                    else:
                        deletes = True
                        self.function_direct_deletes[name] = False
                for value in vars(item).values():
                    if isinstance(value, ASTNode):
                        stack.append(value)
                    elif isinstance(value, list):
                        stack.extend(v for v in value if isinstance(v, ASTNode))
            self.function_deleted_globals[name] = deleted_globals
            self.function_deletes[name] = deletes
            calls[name] = callees
        # Captured Boolean versions change at calls, not at declarations.
        # Unknown calls may invoke any mutable capture through an escaped value.
        self.mutable_boolean_captures = self.readonly_capture_candidates & (assigned_keys | self.borrowed_keys)
        targets = {name: name for name in bodies}
        pending_copies = {key: source for key, source in callable_copies.items()
                          if key not in assigned_keys and key not in self.borrowed_keys}
        changed = True
        while changed:
            changed = False
            for key, source in list(pending_copies.items()):
                if source in targets:
                    targets[key] = targets[source]
                    del pending_copies[key]
                    changed = True
        call_values = self._captured_callable_targets(bodies, targets)
        self._build_scalar_borrow_effects(bodies, call_values)
        capture_effects = {name: keys & self.mutable_boolean_captures for name, keys in capture_own_effects.items()}
        changed = True
        while changed:
            changed = False
            for name, calls_in_body in capture_calls.items():
                effects = set(capture_effects[name])
                for call in calls_in_body:
                    possible = call_values.get(id(call))
                    if possible is None:
                        effects.update(self.mutable_boolean_captures)
                    else:
                        for target in possible:
                            effects.update(capture_effects[target])
                if effects != capture_effects[name]:
                    capture_effects[name] = effects
                    changed = True
        self.capture_call_effects = {}
        for calls_in_body in capture_calls.values():
            for call in calls_in_body:
                possible = call_values.get(id(call))
                self.capture_call_effects[id(call)] = (set(self.mutable_boolean_captures) if possible is None
                    else set().union(*(capture_effects[target] for target in possible)))
        self.local_boolean_keys.update(self.readonly_capture_candidates)
        own_direct_deletes = dict(self.function_direct_deletes)
        changed = True
        while changed:
            changed = False
            for name, callees in calls.items():
                direct_before = self.function_direct_deletes[name]
                self.function_direct_deletes[name] = own_direct_deletes[name] and all(
                    self.function_direct_deletes.get(c, False) for c in callees)
                writes, parameter_deletes, stores, returns, global_effects = self._parameter_effect_summary(bodies[name])
                changed |= direct_before != self.function_direct_deletes[name]
                if global_effects != self.function_global_effects[name]:
                    self.function_global_effects[name] = global_effects
                    changed = True
                if returns != self.function_returns[name]:
                    self.function_returns[name] = returns
                    changed = True
                inherited_writes = set().union(*(self.function_written_globals.get(c, self.file_variables) for c in callees))
                if not inherited_writes.issubset(self.function_written_globals[name]):
                    self.function_written_globals[name].update(inherited_writes)
                    changed = True
                if stores != self.function_field_stores[name]:
                    self.function_field_stores[name] = stores
                    changed = True
                if parameter_deletes != self.function_parameter_deletes[name]:
                    self.function_parameter_deletes[name] = parameter_deletes
                    changed = True
                if writes != self.function_field_writes[name]:
                    self.function_field_writes[name] = writes
                    changed = True
                inherited = set().union(*(self.function_deleted_globals.get(c, set()) for c in callees))
                if not inherited.issubset(self.function_deleted_globals[name]):
                    self.function_deleted_globals[name].update(inherited)
                    changed = True
                if not self.function_deletes[name] and any(self.function_deletes.get(c, True) for c in callees):
                    self.function_deletes[name] = True
                    changed = True
        # These bodies only select a captured reference or nil. Validate all
        # branches, including unselected ones, before using the selector.
        self.literal_return_bodies = {}
        for name, function in bodies.items():
            parameters = function.parameters or []
            refs = {self._key(param): index for index, param in enumerate(parameters)
                    if param.param_type is not None and param.param_type.kind == NodeKind.TYPE_POINTER}
            bools = {self._key(param): index for index, param in enumerate(parameters)
                     if param.param_type is not None and param.param_type.kind == NodeKind.TYPE_PRIMITIVE
                     and param.param_type.type_name == "bool"}
            if len(refs) + len(bools) != len(parameters) or function.body is None:
                continue
            complete = True
            pending = [function.body]
            while pending:
                current = pending.pop()
                if current is None:
                    continue
                if current.kind == NodeKind.BLOCK:
                    pending.extend(current.statements or [])
                elif current.kind == NodeKind.IF_STMT:
                    condition = current.condition
                    if not ((condition.kind == NodeKind.IDENTIFIER and self._key(condition) in bools)
                            or (condition.kind == NodeKind.LITERAL and condition.literal_kind == LiteralKind.BOOLEAN)):
                        complete = False
                        break
                    pending.extend([current.then_stmt, current.else_stmt])
                elif current.kind == NodeKind.RETURN:
                    value = current.value
                    if value is None or not ((value.kind == NodeKind.IDENTIFIER and self._key(value) in refs)
                            or (value.kind == NodeKind.LITERAL and value.literal_kind == LiteralKind.NIL)):
                        complete = False
                        break
                else:
                    complete = False
                    break
            if complete:
                self.literal_return_bodies[name] = (function.body, refs, bools)
        self.readonly_requirements = ReadonlyRequirements(self._key, self._type, self.file_variables)
        self.readonly_requirements.build(bodies)
        # Unknown callable origins must not bypass the requirements of newly
        # admitted reference-array accesses. Existing field rules are unchanged.
        self.escaped_index_functions = set()
        declarations = {id(body): name for name, body in bodies.items()}
        pending = [(node, False)]
        while pending:
            item, direct_callee = pending.pop()
            symbol = self.symbols.resolved_uses.get(id(item))
            target = declarations.get(id(symbol.node)) if symbol is not None else None
            if item.kind == NodeKind.IDENTIFIER:
                target = self.readonly_requirements.alias_targets.get(self._key(item), target)
            if target in self.readonly_requirements.index_functions:
                copied = id(item) in self.readonly_requirements.alias_initializers
                if not copied and (not direct_callee or item.kind != NodeKind.IDENTIFIER):
                    self.escaped_index_functions.add(target)
            for field, value in vars(item).items():
                if isinstance(value, ASTNode):
                    pending.append((value, item.kind == NodeKind.CALL and field == 'function'))
                elif isinstance(value, list):
                    pending.extend((child, False) for child in value if isinstance(child, ASTNode))
        self._classify_exact_effects(bodies)
        for decl in node.declarations or []:
            self._visit_decl(decl)

    def _captured_callable_targets(self, bodies, immutable_targets):
        # This domain tracks callable values, not closure environments. None is
        # unknown; an absent incoming graph state is unreachable.
        owners = {}
        uses = []
        unsupported = set()
        ordered_initializers = {}
        supported = {NodeKind.BLOCK, NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT,
                     NodeKind.EXPRESSION_STMT, NodeKind.IF_STMT, NodeKind.IF_EXPR,
                     NodeKind.WHILE, NodeKind.FOR, NodeKind.RETURN, NodeKind.BREAK,
                     NodeKind.CONTINUE, NodeKind.DEFER, NodeKind.DEL, NodeKind.CALL,
                     NodeKind.IDENTIFIER, NodeKind.LITERAL, NodeKind.UNARY,
                     NodeKind.ADDRESS_OF, NodeKind.BINARY, NodeKind.CAST,
                     NodeKind.INDEX, NodeKind.SLICE, NodeKind.FIELD_ACCESS,
                     NodeKind.DEREF, NodeKind.ARRAY_INIT, NodeKind.STRUCT_INIT,
                     NodeKind.FIELD_INIT, NodeKind.NEW_EXPR}
        for owner, function in bodies.items():
            pending = [function.body]
            while pending:
                node = pending.pop()
                if node is None or node.kind == NodeKind.FUNCTION:
                    continue
                if node.kind.name.startswith("TYPE_"):
                    continue
                if node.kind not in supported:
                    unsupported.add(owner)
                if node.kind == NodeKind.STRUCT_INIT:
                    fields = getattr(self._type(node), "fields", None)
                    initializers = node.field_inits or []
                    names = [field.name for field in fields] if fields is not None else []
                    supplied = [field.name if field.name is not None else names[index] if index < len(names) else None
                                for index, field in enumerate(initializers)]
                    if len(set(supplied)) != len(supplied) or any(name not in names for name in supplied):
                        unsupported.add(owner)
                    else:
                        # Safety precedes AST normalization. Named fields still
                        # appear in source order here; execution uses declaration order.
                        ordered_initializers[id(node)] = [field.value for _, field in
                            sorted(zip(supplied, initializers), key=lambda pair: names.index(pair[0]))]
                if node.kind in {NodeKind.VAR, NodeKind.CONST} and isinstance(self._type(node), FunctionType):
                    owners[self._key(node)] = owner
                if node.kind == NodeKind.IDENTIFIER:
                    uses.append((self._key(node), owner))
                for value in vars(node).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(child for child in value if isinstance(child, ASTNode))
        captured = {key for key, owner in uses if key in owners and owners[key] != owner}
        results = {}
        for owner, function in bodies.items():
            if owner in unsupported:
                pending = [function.body]
                while pending:
                    node = pending.pop()
                    if node is None or node.kind == NodeKind.FUNCTION:
                        continue
                    if node.kind == NodeKind.CALL:
                        target = immutable_targets.get(self._key(node.function)) if node.function and node.function.kind == NodeKind.IDENTIFIER else None
                        results[id(node)] = frozenset({target}) if target is not None else None
                    for value in vars(node).values():
                        if isinstance(value, ASTNode):
                            pending.append(value)
                        elif isinstance(value, list):
                            pending.extend(child for child in value if isinstance(child, ASTNode))
                continue
            eligible = {key for key, declared in owners.items() if declared == owner
                        and key not in captured and key not in self.borrowed_keys}
            graph = []

            def add(action="jump", node=None, extra=None, successors=()):
                graph.append((action, node, extra, list(successors)))
                return len(graph) - 1

            entry, end = add(), add()
            tasks = [(function.body, entry, end, (), ())]
            while tasks:
                node, begin, finish, deferred, loops = tasks.pop()
                if node is None or node.kind == NodeKind.FUNCTION:
                    graph[begin][3].append(finish)
                    continue
                kind = node.kind
                if kind == NodeKind.BLOCK:
                    registered = []
                    cursor = begin
                    for statement in node.statements or []:
                        if statement.kind == NodeKind.DEFER:
                            registered.append(statement.statement)
                        else:
                            after = add()
                            tasks.append((statement, cursor, after, deferred + tuple(registered), loops))
                            cursor = after
                    for statement in reversed(registered):
                        after = add()
                        tasks.append((statement, cursor, after, deferred, loops))
                        cursor = after
                    graph[cursor][3].append(finish)
                    continue
                if kind == NodeKind.DEFER:
                    tasks.append((node.statement, begin, finish, deferred, loops))
                    continue
                if kind in EXIT_KINDS:
                    target = next((loop for loop in reversed(loops) if node.label in {None, loop[0]}), None) if kind != NodeKind.RETURN else None
                    destination = end if kind == NodeKind.RETURN else (target[1] if kind == NodeKind.BREAK else target[2])
                    depth = 0 if target is None else target[3]
                    cursor = begin
                    if kind == NodeKind.RETURN and node.value:
                        after = add()
                        tasks.append((node.value, cursor, after, deferred, loops))
                        cursor = after
                    for statement in reversed(deferred[depth:]):
                        after = add()
                        tasks.append((statement, cursor, after, deferred[:depth], loops))
                        cursor = after
                    graph[cursor][3].append(destination)
                    continue
                if kind in {NodeKind.WHILE, NodeKind.FOR}:
                    condition, split, body, update = add(), add(), add(), add()
                    tasks.append((node.init, begin, condition, deferred, loops))
                    tasks.append((node.condition, condition, split, deferred, loops))
                    context = (*loops, (node.label, finish, update, len(deferred)))
                    tasks.append((node.body, body, update, deferred, context))
                    tasks.append((node.update, update, condition, deferred, loops))
                    literal = node.condition.literal_value if node.condition and node.condition.kind == NodeKind.LITERAL and node.condition.literal_kind == LiteralKind.BOOLEAN else None
                    if literal is not False:
                        graph[split][3].append(body)
                    if literal is not True:
                        graph[split][3].append(finish)
                    continue
                if kind in {NodeKind.IF_STMT, NodeKind.IF_EXPR} or kind == NodeKind.BINARY and node.operator in {BinaryOp.AND, BinaryOp.OR}:
                    short = kind == NodeKind.BINARY
                    condition = node.left if short else node.condition
                    left = node.right if short else node.then_stmt if kind == NodeKind.IF_STMT else node.then_expr
                    right = None if short else node.else_stmt if kind == NodeKind.IF_STMT else node.else_expr
                    split, left_entry, right_entry = add(), add(), add()
                    tasks.append((condition, begin, split, deferred, loops))
                    tasks.append((left, left_entry, finish, deferred, loops))
                    tasks.append((right, right_entry, finish, deferred, loops))
                    literal = condition.literal_value if condition and condition.kind == NodeKind.LITERAL and condition.literal_kind == LiteralKind.BOOLEAN else None
                    if short and node.operator == BinaryOp.OR:
                        left_entry, right_entry = right_entry, left_entry
                    if literal is not False:
                        graph[split][3].append(left_entry)
                    if literal is not True:
                        graph[split][3].append(right_entry)
                    continue
                if kind == NodeKind.CALL:
                    capture = add("capture", node)
                    tasks.append((node.function, begin, capture, deferred, loops))
                    cursor = capture
                    for argument in node.arguments or []:
                        after = add()
                        tasks.append((argument, cursor, after, deferred, loops))
                        cursor = after
                    invoke = add("call", node, successors=(finish,))
                    graph[cursor][3].append(invoke)
                    continue
                if kind in {NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT}:
                    target = node.target if kind == NodeKind.ASSIGNMENT else node
                    key = self._key(target) if target.kind in {NodeKind.IDENTIFIER, NodeKind.VAR, NodeKind.CONST} else None
                    store = add("store", node, key, (finish,))
                    if kind == NodeKind.ASSIGNMENT and target.kind != NodeKind.IDENTIFIER:
                        base = add()
                        tasks.append((node.value, begin, base, deferred, loops))
                        tasks.append((target, base, store, deferred, loops))
                    else:
                        tasks.append((node.value, begin, store, deferred, loops))
                    continue
                finish_value = add("value", node, successors=(finish,))
                children = []
                if kind in {NodeKind.UNARY, NodeKind.ADDRESS_OF}:
                    children = [node.operand]
                elif kind == NodeKind.BINARY:
                    children = [node.left, node.right]
                elif kind in {NodeKind.CAST, NodeKind.EXPRESSION_STMT, NodeKind.DEL}:
                    children = [node.expression]
                elif kind == NodeKind.INDEX:
                    children = [node.object, node.index]
                elif kind == NodeKind.SLICE:
                    children = [node.object, node.start, node.end]
                elif kind == NodeKind.FIELD_ACCESS:
                    children = [node.object]
                elif kind == NodeKind.DEREF:
                    children = [node.pointer]
                elif kind == NodeKind.ARRAY_INIT:
                    children = node.elements or []
                elif kind == NodeKind.STRUCT_INIT:
                    children = ordered_initializers[id(node)]
                cursor = begin
                for child in children:
                    after = add()
                    tasks.append((child, cursor, after, deferred, loops))
                    cursor = after
                graph[cursor][3].append(finish_value)
            incoming = {entry: {}}
            pending = [entry]
            while pending:
                index = pending.pop()
                state = dict(incoming[index])
                action, node, extra, successors = graph[index]
                if action == "value" and node.kind == NodeKind.IDENTIFIER and isinstance(self._type(node), FunctionType):
                    key = self._key(node)
                    target = immutable_targets.get(key)
                    state[("value", id(node))] = state.get(key, frozenset({target}) if target is not None else None)
                elif action == "store":
                    value = state.pop(("value", id(node.value)), None)
                    if extra in eligible:
                        state[extra] = value
                elif action == "capture":
                    state[("call", id(node))] = state.pop(("value", id(node.function)), None)
                elif action == "call":
                    value = state.pop(("call", id(node)), None)
                    for argument in node.arguments or []:
                        state.pop(("value", id(argument)), None)
                    previous = results.get(id(node), frozenset())
                    results[id(node)] = None if previous is None or value is None else previous | value
                for successor in successors:
                    previous = incoming.get(successor)
                    if previous is None:
                        joined = dict(state)
                    else:
                        joined = {}
                        for key in previous.keys() | state.keys():
                            left, right = previous.get(key), state.get(key)
                            joined[key] = None if left is None or right is None else left | right
                    if previous != joined:
                        incoming[successor] = joined
                        pending.append(successor)
        return results

    def _build_scalar_borrow_effects(self, bodies, call_values):
        # Origin sets contain resolved storage keys. Union every binding version,
        # so later argument/rebinding effects cannot erase an earlier actual.
        nodes, owners, parameters, aliases, roots, captures = {}, {}, {}, {}, {}, {}
        reference_slots, captured_slots = {}, set()
        storage_tokens, captured_storage = {}, set()
        for name, function in bodies.items():
            parameters[name] = {index: self._key(param) for index, param in enumerate(function.parameters or [])
                                if isinstance(self._type(param), ReferenceType)
                                or param.param_type is not None and param.param_type.kind == NodeKind.TYPE_POINTER}
            aliases[name] = {key: {key} for key in parameters[name].values()}
            roots[name] = set(parameters[name].values())
            captures[name] = set()
            reference_slots[name] = set()
            for param in function.parameters or []:
                key = self._key(param)
                owners[key] = name
                type_node = param.param_type
                if (type_node is not None and type_node.kind == NodeKind.TYPE_POINTER
                        and type_node.target_type is not None
                        and type_node.target_type.kind == NodeKind.TYPE_PRIMITIVE
                        and type_node.target_type.type_name == "usize"):
                    reference_slots[name].add(key)
            storage_tokens[name] = {}
            nodes[name] = []
            pending = [function.body]
            while pending:
                node = pending.pop()
                if node is None or node.kind == NodeKind.FUNCTION or node.kind.name.startswith("TYPE_"):
                    continue
                nodes[name].append(node)
                if node.kind in {NodeKind.VAR, NodeKind.CONST}:
                    key = self._key(node)
                    owners[key] = name
                    if key in self.local_index_keys:
                        roots[name].add(key)
                    if isinstance(self._type(node), ReferenceType):
                        aliases[name][key] = set()
                    slot_type = self._type(node) or self._type(node.value)
                    if (isinstance(slot_type, ReferenceType)
                            and isinstance(slot_type.referent_type, PrimitiveType)
                            and slot_type.referent_type.name == "usize"):
                        reference_slots[name].add(key)
                for value in vars(node).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(child for child in value if isinstance(child, ASTNode))
        for name, statements in nodes.items():
            for node in statements:
                if node.kind != NodeKind.IDENTIFIER:
                    continue
                symbol = self.symbols.resolved_uses.get(id(node))
                key = (self.keys.get((id(symbol.node), symbol.name), self._key(node))
                       if symbol is not None and symbol.node is not None else self._key(node))
                owner = owners.get(key)
                checked = self._type(node) or (symbol.type if symbol is not None else None)
                if owner is not None and (isinstance(checked, (ArrayType, StructType, EnumType, SliceType, FunctionType))
                        or isinstance(checked, PrimitiveType)
                        and (checked.is_numeric() or checked.name in {"bool", "char", "string"})
                        and key not in roots[owner]):
                    # NUL cannot occur in an A7 declaration key. The owner
                    # length makes this private namespace unambiguous.
                    storage_tokens[owner][key] = f"\0storage:{len(owner)}:{owner}:{key}"
                    if owner != name:
                        captured_storage.add(key)
                if owner is not None and owner != name and key in aliases[owner]:
                    captures[owner].add(key)
                if owner is not None and isinstance(symbol.type if symbol is not None else None, ReferenceType):
                    slot_type = symbol.type
                    if (isinstance(slot_type.referent_type, PrimitiveType)
                            and slot_type.referent_type.name == "usize"):
                        reference_slots[owner].add(key)
                    if owner != name:
                        captured_slots.add(key)

        all_storage_tokens = {token for values in storage_tokens.values() for token in values.values()}
        for name in bodies:
            roots[name].update(storage_tokens[name].values())

        def origins(node, name):
            result = set()
            pending = [node]
            while pending:
                current = pending.pop()
                if current is None:
                    continue
                if current.kind == NodeKind.IDENTIFIER:
                    key = self._key(current)
                    if key in aliases[name]:
                        result.update(aliases[name][key])
                    elif key in roots[name]:
                        result.add(key)
                    elif isinstance(self._type(current), ReferenceType):
                        result.update(roots[name])
                elif current.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX, NodeKind.SLICE}:
                    pending.append(current.object)
                elif current.kind == NodeKind.NEW_EXPR:
                    # Fresh storage cannot alias an existing caller scalar.
                    continue
                elif current.kind == NodeKind.LITERAL and current.literal_kind == LiteralKind.NIL:
                    continue
                elif isinstance(self._type(current), ReferenceType):
                    # Returned/unsupported reference values may denote any root.
                    result.update(roots[name])
            return result

        # No summary is consumed by scalar eligibility until this union fixed
        # point includes every alias version, callee effect and captured origin.
        writes = {name: set() for name in bodies}
        escapes = {name: set() for name in bodies}
        call_writes, direct_writes = {}, {}
        # Parameter effects alone cannot see a no-argument callee deleting a
        # global that aliases a parameter. This whole-body veto includes those
        # effects, condition expressions, and deferred statements.
        reference_veto = {name for name, function in bodies.items() if function.body is None}
        reference_rebinds = {name: set() for name in bodies}
        changed = True
        while changed:
            changed = False
            for name, function in bodies.items():
                new_writes, new_escapes = set(), set()
                veto = name in reference_veto
                rebinds = set()
                if function.body is None:
                    new_writes.update(parameters[name].values())
                    new_escapes.update(parameters[name].values())
                for key in captures[name]:
                    new_escapes.update(aliases[name][key])
                for node in nodes[name]:
                    kind = node.kind
                    if kind == NodeKind.DEL:
                        veto = True
                    if kind == NodeKind.ASSIGNMENT:
                        target = node.target
                        if (target.kind == NodeKind.IDENTIFIER
                                and isinstance(self._type(target), ReferenceType)
                                and not getattr(node, "implicit_deref_target", False)):
                            symbol = self.symbols.resolved_uses.get(id(target))
                            key = (self.keys.get((id(symbol.node), symbol.name), self._key(target))
                                   if symbol is not None and symbol.node is not None else self._key(target))
                            rebinds.add(key)
                        else:
                            veto |= (getattr(node, "implicit_deref_target", False)
                                     or target.kind != NodeKind.IDENTIFIER
                                     or self._key(target) in self.file_variables)
                    if kind in {NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT}:
                        target = node.target if kind == NodeKind.ASSIGNMENT else node
                        key = self._key(target) if target and target.kind in {NodeKind.IDENTIFIER, NodeKind.VAR, NodeKind.CONST} else None
                        if kind == NodeKind.ASSIGNMENT and (getattr(node, "implicit_deref_target", False)
                                or target.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}):
                            affected = origins(target, name)
                            direct_writes.setdefault(id(node), set()).update(affected)
                            new_writes.update(affected)
                        elif kind == NodeKind.ASSIGNMENT and target.kind != NodeKind.IDENTIFIER:
                            direct_writes.setdefault(id(node), set()).update(roots[name])
                            new_writes.update(roots[name])
                        if node.value is not None and isinstance(self._type(node.value), ReferenceType):
                            value = origins(node.value, name)
                            if key in aliases[name] and not getattr(node, "implicit_deref_target", False):
                                before = len(aliases[name][key])
                                aliases[name][key].update(value)
                                changed |= len(aliases[name][key]) != before
                            elif self._has_reference_storage(self._type(target)):
                                new_escapes.update(value)
                    elif kind == NodeKind.DEL:
                        affected = origins(node.expression, name)
                        new_writes.update(affected)
                        new_escapes.update(affected)
                    elif kind == NodeKind.RETURN and node.value is not None:
                        value_type = self._type(node.value)
                        if node.value.kind == NodeKind.LITERAL and node.value.literal_kind == LiteralKind.NIL:
                            continue
                        if isinstance(value_type, ReferenceType):
                            new_escapes.update(origins(node.value, name))
                        elif self._has_reference_storage(value_type):
                            # Unsupported aggregate/callable/unknown results
                            # cannot establish that a caller origin stays local.
                            new_escapes.update(roots[name])
                    elif kind in {NodeKind.ARRAY_INIT, NodeKind.STRUCT_INIT}:
                        values = node.elements if kind == NodeKind.ARRAY_INIT else [item.value for item in node.field_inits or []]
                        for value in values or []:
                            if isinstance(self._type(value), ReferenceType):
                                new_escapes.update(origins(value, name))
                    elif kind == NodeKind.CALL:
                        affected, escaped = set(), set()
                        possible = call_values.get(id(node))
                        veto |= (not possible or any(target not in bodies or target in reference_veto
                                                      for target in possible))
                        for target in possible or ():
                            if target in reference_rebinds:
                                rebinds.update(reference_rebinds[target])
                        for index, argument in enumerate(node.arguments or []):
                            if index not in getattr(node, "implicit_ref_args", set()) and not isinstance(self._type(argument), ReferenceType):
                                continue
                            actual = origins(argument, name)
                            if not possible or any(target not in bodies for target in possible):
                                affected.update(actual)
                                escaped.update(actual)
                            else:
                                for target in possible:
                                    parameter = parameters[target].get(index)
                                    if parameter is None:
                                        # A reference converted to a primitive is a value copy.
                                        continue
                                    if parameter in writes[target]:
                                        affected.update(actual)
                                    if parameter in escapes[target]:
                                        escaped.update(actual)
                        call_writes.setdefault(id(node), set()).update(affected)
                        new_writes.update(affected)
                        new_escapes.update(escaped)
                if veto and name not in reference_veto:
                    reference_veto.add(name)
                    changed = True
                previous_rebinds = len(reference_rebinds[name])
                reference_rebinds[name].update(rebinds)
                changed |= previous_rebinds != len(reference_rebinds[name])
                before = (len(writes[name]), len(escapes[name]))
                writes[name].update(new_writes)
                escapes[name].update(new_escapes)
                changed |= before != (len(writes[name]), len(escapes[name]))
        # Binding versions are graph states. A missing incoming state is
        # unreachable; None is an unknown origin value, including a missing
        # binding on a reachable predecessor. Temporaries identify graph
        # occurrences, so separate cleanup expansions never share snapshots.
        supported = {NodeKind.BLOCK, NodeKind.VAR, NodeKind.CONST,
                     NodeKind.ASSIGNMENT, NodeKind.EXPRESSION_STMT,
                     NodeKind.IF_STMT, NodeKind.IF_EXPR, NodeKind.WHILE,
                     NodeKind.FOR, NodeKind.RETURN, NodeKind.BREAK,
                     NodeKind.CONTINUE, NodeKind.DEFER, NodeKind.DEL,
                     NodeKind.CALL, NodeKind.IDENTIFIER, NodeKind.LITERAL,
                     NodeKind.UNARY, NodeKind.BINARY, NodeKind.FIELD_ACCESS,
                     NodeKind.INDEX, NodeKind.SLICE, NodeKind.NEW_EXPR}
        graphs, fallback = {}, set()
        for name, function in bodies.items():
            if function.body is None:
                fallback.add(name)
            for node in nodes[name]:
                if node.kind not in supported:
                    fallback.add(name)
                if node.kind == NodeKind.ASSIGNMENT:
                    if node.target.kind != NodeKind.IDENTIFIER:
                        target_type = self._type(node.target)
                        if (node.target.kind not in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}
                                or node.operator != AssignOp.ASSIGN
                                or getattr(node, "implicit_deref_target", False)
                                or not isinstance(target_type, PrimitiveType)
                                or not (target_type.is_numeric() or target_type.name == "bool")):
                            fallback.add(name)
                    elif getattr(node, "implicit_deref_target", False):
                        pending = [node.value]
                        while pending:
                            item = pending.pop()
                            if item is None:
                                continue
                            if item.kind == NodeKind.CALL:
                                # Target/RHS sequencing for an effectful scalar
                                # store is not represented by this graph.
                                fallback.add(name)
                            for value in vars(item).values():
                                if isinstance(value, ASTNode):
                                    pending.append(value)
                                elif isinstance(value, list):
                                    pending.extend(child for child in value if isinstance(child, ASTNode))
                if (node.kind == NodeKind.RETURN and node.value is not None
                        and self._has_reference_storage(self._type(node.value))
                        and not isinstance(self._type(node.value), ReferenceType)
                        and not (node.value.kind == NodeKind.LITERAL
                                 and node.value.literal_kind == LiteralKind.NIL)):
                    fallback.add(name)
            if name in fallback:
                continue
            graph = []

            def add(action="jump", node=None, extra=None, successors=()):
                graph.append((action, node, extra, list(successors)))
                return len(graph) - 1

            entry, end = add(), add()
            tasks = [(function.body, entry, end, (), (), None)]
            while tasks:
                node, begin, finish, deferred, loops, output = tasks.pop()
                if node is None or node.kind == NodeKind.FUNCTION:
                    graph[begin][3].append(finish)
                    continue
                kind = node.kind
                if kind == NodeKind.BLOCK:
                    registered, cursor = [], begin
                    for statement in node.statements or []:
                        if statement.kind == NodeKind.DEFER:
                            registered.append(statement.statement)
                        else:
                            after = add()
                            tasks.append((statement, cursor, after, deferred + tuple(registered), loops, None))
                            cursor = after
                    for statement in reversed(registered):
                        after = add()
                        tasks.append((statement, cursor, after, deferred, loops, None))
                        cursor = after
                    graph[cursor][3].append(finish)
                    continue
                if kind == NodeKind.DEFER:
                    tasks.append((node.statement, begin, finish, deferred, loops, output))
                    continue
                if kind in EXIT_KINDS:
                    target = next((loop for loop in reversed(loops) if node.label in {None, loop[0]}), None) if kind != NodeKind.RETURN else None
                    destination = end if kind == NodeKind.RETURN else (target[1] if kind == NodeKind.BREAK else target[2])
                    depth, cursor, saved = (0 if target is None else target[3]), begin, None
                    if kind == NodeKind.RETURN and node.value is not None:
                        after = add()
                        saved = ("origin", after)
                        tasks.append((node.value, cursor, after, deferred, loops, saved))
                        cursor = after
                    for statement in reversed(deferred[depth:]):
                        after = add()
                        tasks.append((statement, cursor, after, deferred[:depth], loops, None))
                        cursor = after
                    if kind == NodeKind.RETURN:
                        publish = add("return", node, saved, (destination,))
                        graph[cursor][3].append(publish)
                    else:
                        graph[cursor][3].append(destination)
                    continue
                if kind in {NodeKind.WHILE, NodeKind.FOR}:
                    condition, split, body, update = add(), add(), add(), add()
                    tasks.append((node.init, begin, condition, deferred, loops, None))
                    tasks.append((node.condition, condition, split, deferred, loops, None))
                    context = (*loops, (node.label, finish, update, len(deferred)))
                    tasks.append((node.body, body, update, deferred, context, None))
                    tasks.append((node.update, update, condition, deferred, loops, None))
                    literal = node.condition.literal_value if node.condition and node.condition.kind == NodeKind.LITERAL and node.condition.literal_kind == LiteralKind.BOOLEAN else None
                    if literal is not False:
                        graph[split][3].append(body)
                    if literal is not True:
                        graph[split][3].append(finish)
                    continue
                if kind in {NodeKind.IF_STMT, NodeKind.IF_EXPR} or kind == NodeKind.BINARY and node.operator in {BinaryOp.AND, BinaryOp.OR}:
                    short = kind == NodeKind.BINARY
                    condition = node.left if short else node.condition
                    left = node.right if short else node.then_stmt if kind == NodeKind.IF_STMT else node.then_expr
                    right = None if short else node.else_stmt if kind == NodeKind.IF_STMT else node.else_expr
                    split, left_entry, right_entry = add(), add(), add()
                    tasks.append((condition, begin, split, deferred, loops, None))
                    tasks.append((left, left_entry, finish, deferred, loops, output))
                    tasks.append((right, right_entry, finish, deferred, loops, output))
                    literal = condition.literal_value if condition and condition.kind == NodeKind.LITERAL and condition.literal_kind == LiteralKind.BOOLEAN else None
                    if short and node.operator == BinaryOp.OR:
                        left_entry, right_entry = right_entry, left_entry
                    if literal is not False:
                        graph[split][3].append(left_entry)
                    if literal is not True:
                        graph[split][3].append(right_entry)
                    continue
                if kind == NodeKind.CALL:
                    cursor = add()
                    tasks.append((node.function, begin, cursor, deferred, loops, None))
                    actuals, exposed_slots = [], []
                    for argument in node.arguments or []:
                        after = add()
                        saved = ("origin", after)
                        index = len(actuals)
                        actuals.append(("location", saved) if index in getattr(node, "implicit_ref_args", set()) else saved)
                        exposed_slots.append(self._key(argument) if (
                            index in getattr(node, "implicit_ref_args", set())
                            and argument.kind == NodeKind.IDENTIFIER
                            and isinstance(self._type(argument), ReferenceType)) else None)
                        tasks.append((argument, cursor, after, deferred, loops, saved))
                        cursor = after
                    invoke = add("call", node, (output, tuple(actuals), tuple(exposed_slots), call_values.get(id(node))), (finish,))
                    graph[cursor][3].append(invoke)
                    continue
                if (kind == NodeKind.ASSIGNMENT
                        and node.target.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}):
                    # Capture the selected receiver after RHS effects and before
                    # index effects. An index call may rebind its source slot.
                    after_rhs, after_base = add(), add()
                    receiver = ("origin", after_base)
                    tasks.append((node.value, begin, after_rhs, deferred, loops, None))
                    tasks.append((node.target.object, after_rhs, after_base,
                                  deferred, loops, receiver))
                    store = add("place_store", node, receiver, (finish,))
                    if node.target.kind == NodeKind.INDEX:
                        tasks.append((node.target.index, after_base, store,
                                      deferred, loops, None))
                    else:
                        graph[after_base][3].append(store)
                    continue
                if kind in {NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT}:
                    target = node.target if kind == NodeKind.ASSIGNMENT else node
                    store = add("store", node, None, (finish,))
                    saved = ("origin", store)
                    graph[store] = ("store", node, (self._key(target), saved), [finish])
                    tasks.append((node.value, begin, store, deferred, loops, saved))
                    continue
                children = []
                if kind == NodeKind.UNARY:
                    children = [node.operand]
                elif kind == NodeKind.BINARY:
                    children = [node.left, node.right]
                elif kind in {NodeKind.EXPRESSION_STMT, NodeKind.DEL}:
                    children = [node.expression]
                elif kind == NodeKind.INDEX:
                    children = [node.object, node.index]
                elif kind == NodeKind.SLICE:
                    children = [node.object, node.start, node.end]
                elif kind == NodeKind.FIELD_ACCESS:
                    children = [node.object]
                cursor, child_values = begin, []
                for child in children:
                    after = add()
                    saved = ("origin", after)
                    child_values.append(saved)
                    tasks.append((child, cursor, after, deferred, loops, saved))
                    cursor = after
                value = add("value", node, (output, tuple(child_values)), (finish,))
                graph[cursor][3].append(value)
            graphs[name] = (graph, entry)

        # Slot addresses do not identify backing storage. Certify complete
        # bodies before monotone effect collection, so provisional uncertainty
        # cannot permanently pollute a subsequently certified slot replacement.
        slot_uncertified = set(fallback)
        slot_dependencies = {name: set() for name in bodies}
        handle_arguments = set()
        for name, statements in nodes.items():
            for node in statements:
                if node.kind in {NodeKind.DEL, NodeKind.SLICE}:
                    slot_uncertified.add(name)
                elif node.kind == NodeKind.IDENTIFIER:
                    key = self._key(node)
                    if (key in self.file_variables or key in captured_slots
                            or key in captured_storage
                            or key in owners and owners[key] != name):
                        slot_uncertified.add(name)
                elif node.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}:
                    receiver = self._type(node.object)
                    if isinstance(receiver, ReferenceType):
                        receiver = receiver.referent_type
                    if (not isinstance(receiver, (ArrayType, StructType))
                            or isinstance(self._type(node), ReferenceType)):
                        slot_uncertified.add(name)
                elif node.kind == NodeKind.CALL:
                    possible = call_values.get(id(node))
                    if not possible or any(target not in bodies for target in possible):
                        slot_uncertified.add(name)
                    slot_dependencies[name].update(target for target in possible or () if target in bodies)
                    for index, argument in enumerate(node.arguments or []):
                        addressed = self._type(argument)
                        if index not in getattr(node, "implicit_ref_args", set()):
                            if not isinstance(addressed, ReferenceType):
                                continue
                            addressed = addressed.referent_type
                        # Inspect inline payloads iteratively. A reference leaf
                        # or handle inside an aggregate can reach other roots.
                        pending_types, seen_types = [addressed], set()
                        while pending_types:
                            item = pending_types.pop()
                            if id(item) in seen_types:
                                continue
                            seen_types.add(id(item))
                            if isinstance(item, ArrayType):
                                pending_types.append(item.element_type)
                            elif isinstance(item, (StructType, UnionType)):
                                pending_types.extend(field.field_type for field in item.fields)
                            elif (isinstance(item, PrimitiveType)
                                  and item.name != "string") or isinstance(item, EnumType):
                                continue
                            else:
                                handle_arguments.add((id(node), index))
                                break
        changed = True
        while changed:
            changed = False
            for name, targets in slot_dependencies.items():
                if name not in slot_uncertified and targets & slot_uncertified:
                    slot_uncertified.add(name)
                    changed = True

        # Unknown return values are distinct from an analyzable function's
        # provisional empty summary. All channels converge before publication.
        returned = {name: None if name in fallback else frozenset() for name in bodies}
        for name in graphs:
            writes[name] = set()
            escapes[name] = set().union(*(aliases[name][key] for key in captures[name]))
            for node in nodes[name]:
                call_writes.pop(id(node), None)
                direct_writes.pop(id(node), None)
        changed = True
        while changed:
            changed = False
            for name, (graph, entry) in graphs.items():
                incoming = {entry: {key: frozenset({key}) for key in parameters[name].values()}}
                pending = [entry]
                new_writes, new_escapes, new_return = set(), set(), frozenset()
                while pending:
                    point = pending.pop()
                    state = dict(incoming[point])
                    action, node, extra, successors = graph[point]
                    if action == "value":
                        output, children = extra
                        value, location = frozenset(), None
                        if node.kind == NodeKind.IDENTIFIER:
                            key = self._key(node)
                            if isinstance(self._type(node), ReferenceType):
                                value = state.get(key)
                            elif key in roots[name] or key in self.file_variables:
                                value = frozenset({key})
                            if (key in storage_tokens[name] and key not in captured_storage
                                    and key not in self.file_variables and owners.get(key) == name):
                                location = frozenset({storage_tokens[name][key]})
                            elif key in roots[name] and not isinstance(self._type(node), ReferenceType):
                                location = frozenset({key})
                        elif isinstance(self._type(node), ReferenceType) and node.kind != NodeKind.NEW_EXPR:
                            value = None
                        if node.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}:
                            receiver_type = self._type(node.object)
                            if isinstance(receiver_type, ReferenceType) and isinstance(receiver_type.referent_type, (ArrayType, StructType)):
                                location = state.get(children[0])
                            elif isinstance(receiver_type, (ArrayType, StructType)):
                                location = state.get(("location", children[0]))
                        if node.kind == NodeKind.DEL:
                            affected = state.get(children[0])
                            affected = roots[name] if affected is None else affected
                            new_writes.update(affected)
                            new_escapes.update(affected)
                        if output is not None:
                            state[output] = value
                            state[("location", output)] = location
                    elif action == "place_store":
                        receiver_type = self._type(node.target.object)
                        affected = None
                        if isinstance(receiver_type, ReferenceType) and isinstance(receiver_type.referent_type, (ArrayType, StructType)):
                            affected = state.get(extra)
                        elif isinstance(receiver_type, (ArrayType, StructType)):
                            affected = state.get(("location", extra))
                        affected = roots[name] if affected is None else affected
                        direct_writes.setdefault(id(node), set()).update(affected)
                        new_writes.update(affected)
                    elif action == "store":
                        key, saved = extra
                        target = node.target if node.kind == NodeKind.ASSIGNMENT else node
                        value = state.get(saved)
                        if getattr(node, "implicit_deref_target", False):
                            affected = state.get(key)
                            affected = roots[name] if affected is None else affected
                            direct_writes.setdefault(id(node), set()).update(affected)
                            new_writes.update(affected)
                        elif (isinstance(self._type(target), ReferenceType)
                              or isinstance(self._type(node.value), ReferenceType)
                              or key in reference_slots[name]):
                            state[key] = value
                            if key in self.file_variables or owners.get(key) != name or key in captured_slots:
                                new_escapes.update(roots[name] if value is None else value)
                    elif action == "return" and node.value is not None:
                        if isinstance(self._type(node.value), ReferenceType):
                            value = state.get(extra)
                            # Returning an origin owned by this frame is not a
                            # fresh allocation or a caller formal forwarding.
                            if value is not None and not value <= set(parameters[name].values()):
                                value = None
                            new_return = None if new_return is None or value is None else new_return | value
                    elif action == "call":
                        output, saved, exposed_slots, possible = extra
                        # A borrowed reference slot can be rebound by a later
                        # argument before the callee reads it. Its referent is
                        # unknown; ordinary reference value snapshots stay fixed.
                        actuals = [None if exposed is not None else state.get(slot)
                                   for slot, exposed in zip(saved, exposed_slots)]
                        affected, escaped, result = set(), set(), frozenset()
                        unknown = not possible or any(target not in bodies for target in possible)
                        for index, argument in enumerate(node.arguments or []):
                            if index not in getattr(node, "implicit_ref_args", set()) and not isinstance(self._type(argument), ReferenceType):
                                continue
                            actual = actuals[index]
                            actual = roots[name] if actual is None else actual
                            if ((id(node), index) in handle_arguments
                                    and (unknown or any(target in slot_uncertified for target in possible))):
                                # Retain raw actuals for return substitution.
                                # Uncertified backing effects can reach any
                                # caller root, even through a returned alias.
                                actual = roots[name]
                            if unknown:
                                affected.update(actual)
                                escaped.update(actual)
                            else:
                                for target in possible:
                                    parameter = parameters[target].get(index)
                                    if parameter in writes[target]:
                                        affected.update(actual)
                                    if parameter in escapes[target]:
                                        escaped.update(actual)
                        if unknown:
                            result = None
                        else:
                            for target in possible:
                                if returned[target] is None:
                                    result = None
                                    break
                                for index, parameter in parameters[target].items():
                                    if parameter in returned[target]:
                                        actual = actuals[index] if index < len(actuals) else None
                                        result = None if result is None or actual is None else result | actual
                        call_writes.setdefault(id(node), set()).update(affected)
                        new_writes.update(affected)
                        new_escapes.update(escaped)
                        # Calls can change externally accessible slots. Earlier
                        # actual snapshots remain separate immutable values.
                        exposed = {key for key in exposed_slots if key is not None}
                        for key in state.keys() & (self.file_variables | captured_slots | exposed):
                            state[key] = None
                        if output is not None:
                            state[output] = result
                            # A call result is a value, not an addressable local
                            # aggregate. Reference projection uses result above.
                            state[("location", output)] = None
                    for successor in successors:
                        previous = incoming.get(successor)
                        if previous is None:
                            joined = dict(state)
                        else:
                            joined = {}
                            for key in previous.keys() | state.keys():
                                left, right = previous.get(key), state.get(key)
                                joined[key] = None if left is None or right is None else left | right
                        if previous != joined:
                            incoming[successor] = joined
                            pending.append(successor)
                before = (len(writes[name]), len(escapes[name]), returned[name])
                writes[name].update(new_writes)
                escapes[name].update(new_escapes)
                returned[name] = None if returned[name] is None or new_return is None else returned[name] | new_return
                changed |= before != (len(writes[name]), len(escapes[name]), returned[name])
        self.scalar_returned_origins = returned
        self.scalar_origin_graph_fallback = fallback
        # Keep owner-local provenance through calls, returns and escapes.
        # Only the scalar invalidation clients discard disjoint storage tokens.
        self.scalar_call_writes = {node: values - all_storage_tokens for node, values in call_writes.items()}
        self.scalar_direct_writes = {node: values - all_storage_tokens for node, values in direct_writes.items()}
        self.scalar_escaped_keys = set().union(*escapes.values())
        self.scalar_eligible_keys = self.local_index_keys - self.scalar_escaped_keys
        self.scalar_parameter_writes = {name: {index for index, key in parameters[name].items() if key in writes[name]}
                                        for name in bodies}
        self.scalar_parameter_escapes = {name: {index for index, key in parameters[name].items() if key in escapes[name]}
                                         for name in bodies}

        self.readonly_scalar_reference_keys = set()
        for name, function in bodies.items():
            if (name in reference_veto or self.scalar_parameter_writes[name]
                    or self.scalar_parameter_escapes[name]):
                continue
            # Binding identity proves only slot stability. Referent aliasing
            # remains covered by the collective write/escape and risk vetoes.
            self.readonly_scalar_reference_keys.update(
                reference_slots[name] - self.file_variables - self.borrowed_keys
                - captured_slots - reference_rebinds[name])

    def _classify_exact_effects(self, bodies: dict[str, ASTNode]) -> None:
        # Completeness covers the whole body, including every nested known call.
        self.exact_effect_bodies = bodies
        self.exact_effect_reasons = {}
        dependencies = {}
        branch_counts = {}
        own_work = {}
        supported = {NodeKind.BLOCK, NodeKind.VAR, NodeKind.CONST,
                     NodeKind.ASSIGNMENT, NodeKind.EXPRESSION_STMT, NodeKind.RETURN,
                     NodeKind.IF_STMT, NodeKind.DEFER, NodeKind.DEL,
                     NodeKind.IDENTIFIER, NodeKind.LITERAL, NodeKind.FIELD_ACCESS,
                     NodeKind.BINARY, NodeKind.UNARY, NodeKind.CAST, NodeKind.CALL}
        for name, function in bodies.items():
            reasons = set()
            callees = []
            branches = 0
            work_nodes = 0
            for param in function.parameters or []:
                if not isinstance(self._type(param), (ReferenceType, PrimitiveType)) and (param.param_type is None or param.param_type.kind not in {NodeKind.TYPE_POINTER, NodeKind.TYPE_PRIMITIVE}):
                    reasons.add("by-value aggregate parameter")
            pending = [function.body]
            while pending:
                node = pending.pop()
                if node is None:
                    continue
                if node.kind.name.startswith("TYPE_"):
                    continue
                work_nodes += 1
                if node.kind not in supported:
                    reasons.add(node.kind.name.lower())
                    continue
                branches += node.kind == NodeKind.IF_STMT
                if isinstance(self._type(node), ReferenceType) and node.kind not in {NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS, NodeKind.LITERAL, NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT}:
                    reasons.add("unrepresented reference expression")
                if node.kind == NodeKind.BINARY and node.operator in {BinaryOp.AND, BinaryOp.OR}:
                    reasons.add("short-circuit expression")
                if node.kind == NodeKind.IDENTIFIER and self._key(node) in self.file_variables:
                    reasons.add("global storage")
                if node.kind == NodeKind.RETURN and isinstance(self._type(node.value), ReferenceType):
                    reasons.add("returned reference")
                if node.kind in {NodeKind.VAR, NodeKind.CONST, NodeKind.ASSIGNMENT} and node.value is not None and not isinstance(self._type(node.value), (ReferenceType, PrimitiveType)) and not (node.value.kind == NodeKind.LITERAL and node.value.literal_kind == LiteralKind.NIL):
                    reasons.add("aggregate value copy")
                if node.kind == NodeKind.ASSIGNMENT and getattr(node, "implicit_deref_target", False):
                    reasons.add("scalar borrow write")
                if node.kind == NodeKind.CALL:
                    canonical = getattr(node, "stdlib_canonical", None)
                    if canonical and canonical not in {"std.io.print", "std.io.println"}:
                        reasons.add("unrepresented stdlib effects")
                    if not canonical:
                        target = self._key(node.function) if node.function and node.function.kind == NodeKind.IDENTIFIER else None
                        if target not in bodies:
                            reasons.add("unknown callee")
                        else:
                            callees.append(target)
                    pending.extend(node.arguments or [])
                    continue
                for value in vars(node).values():
                    if isinstance(value, ASTNode):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(item for item in value if isinstance(item, ASTNode))
            self.exact_effect_reasons[name] = reasons
            dependencies[name] = callees
            branch_counts[name] = min(branches, 2)
            own_work[name] = work_nodes
        work_budget = max(1, sum(own_work.values()))
        expanded_work = dict(own_work)
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                count = own_work[name]
                for callee in callees:
                    count += expanded_work[callee]
                    if count > work_budget:
                        count = work_budget + 1
                        break
                if count != expanded_work[name]:
                    expanded_work[name] = count
                    changed = True
        self.exact_effect_work_budget = work_budget
        self.exact_effect_work = expanded_work
        for name, count in expanded_work.items():
            if count > work_budget:
                self.exact_effect_reasons[name].add("transitive effect expansion exceeds source-sized work budget")
        own_branches = dict(branch_counts)
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                count = min(2, own_branches[name] + sum(branch_counts[c] for c in callees))
                if count != branch_counts[name]:
                    branch_counts[name] = count
                    changed = True
        self.exact_effect_branch_counts = branch_counts
        for name, count in branch_counts.items():
            if count > 1:
                self.exact_effect_reasons[name].add("more than one transitive conditional occurrence")
        changed = True
        while changed:
            changed = False
            for name, callees in dependencies.items():
                if not self.exact_effect_reasons[name] and any(self.exact_effect_reasons[c] for c in callees):
                    self.exact_effect_reasons[name].add("incomplete known callee")
                    changed = True

    def _exact_call_name(self, call: ASTNode, captured: Optional[list[tuple[ValueFact, Optional[str]]]] = None) -> Optional[str]:
        callee = call.function
        name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
        if name not in self.exact_effect_reasons or self.exact_effect_reasons[name]:
            return None
        for index, arg in enumerate(call.arguments or []):
            key = captured[index][1] if captured and captured[index][1] is not None else self._place_key(arg)
            fact = captured[index][0] if captured else self.facts.symbol(key)
            prefixes = [key + "."] if key else []
            prefixes.extend(prefix + "." for prefix in self._allocation_prefixes(fact.allocations))
            if any(self._allocation_count(fact.allocations) > 1 and any(place.startswith(prefix) for prefix in prefixes)
                   for place, fact in self.facts.by_symbol.items()):
                return None
            if index not in getattr(call, "implicit_ref_args", set()) and isinstance(self._type(arg), ReferenceType):
                if arg.kind not in {NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS} or self._allocation_count(fact.allocations) != 1:
                    return None
        return name

    def _apply_legacy_reference_effects(self, node: ASTNode, index: int, arg: ASTNode, fact: ValueFact) -> None:
        key = self._place_key(arg)
        callee = node.function
        writes = self.function_field_writes.get(self._key(callee)) if callee and callee.kind == NodeKind.IDENTIFIER else None
        if key and not getattr(node, "stdlib_canonical", None):
            prefixes = [key]
            prefixes.extend(self._allocation_prefixes(fact.allocations))
            for path in (writes.get(index, set()) if writes is not None else {""}):
                for prefix in prefixes:
                    target = prefix + ("." + path if path else "")
                    self._forget_names({name for name in self.facts.by_symbol
                                        if (path and name == target) or name.startswith(target + ".")})
        function_type = self._type(node.function)
        reference_parameter = isinstance(function_type, FunctionType) and index < len(function_type.param_types) and isinstance(function_type.param_types[index], ReferenceType)
        direct = callee and callee.kind == NodeKind.IDENTIFIER and self.function_direct_deletes.get(self._key(callee), False)
        if isinstance(self._type(arg), ReferenceType) and reference_parameter and self._calls_deleting_function(node) and not direct:
            self._move_allocations(fact.allocations)
            if key and self.facts.symbol(key).allocations == fact.allocations:
                self._mark_moved_slot(key, self.facts.symbol(key).allocations)

    def _replay_exact_effects(self, call: ASTNode, name: str, arguments: list[tuple[ValueFact, Optional[str]]]) -> None:
        # Actions capture values separately from storage. Each branch owns its
        # state; deletion never becomes a write to the parameter's caller slot.
        initial = ([("enter", self.exact_effect_bodies[name], arguments)],
                   dict(self.facts.by_symbol), set(self.moved_symbols), {}, {}, [], [])
        paths = [initial]
        exits = []
        serial = 0
        while paths:
            work, storage, moved, values, places, bindings, scopes = paths.pop()
            while work:
                action, node, extra = work.pop()
                if action == "enter":
                    serial += 1
                    mapping = {}
                    for index, param in enumerate(node.parameters or []):
                        fact, place = extra[index]
                        key = f"effect:{serial}:{self._key(param)}"
                        mapping[self._key(param)] = key
                        storage[key] = fact
                        if place is not None and not fact.allocations:
                            # An implicit aggregate borrow is a storage alias.
                            storage[key] = replace(fact, non_nil=True, allocations=frozenset({f"storage:{place}"}))
                    bindings.append(mapping)
                    scopes.append([])
                    work.extend([("leave", node, None), ("stmt", node.body, None)])
                    continue
                if action == "leave":
                    bindings.pop()
                    scopes.pop()
                    continue
                if action == "scope_end":
                    deferred = scopes.pop()
                    work.extend(("stmt", item, None) for item in deferred)
                    continue
                if action == "return":
                    deferred = []
                    while work and work[-1][0] != "leave":
                        popped, _, _ = work.pop()
                        if popped == "scope_end":
                            deferred.extend(reversed(scopes.pop()))
                    deferred.extend(reversed(scopes[-1]))
                    scopes[-1] = []
                    work.extend(("stmt", item, None) for item in reversed(deferred))
                    continue
                if action == "stmt":
                    if node is None:
                        continue
                    kind = node.kind
                    if kind == NodeKind.BLOCK:
                        scopes.append([])
                        work.append(("scope_end", node, None))
                        work.extend(("stmt", item, None) for item in reversed(node.statements or []))
                    elif kind == NodeKind.DEFER:
                        scopes[-1].append(node.statement)
                    elif kind == NodeKind.RETURN:
                        work.append(("return", node, None))
                        if node.value:
                            work.append(("expr", node.value, None))
                    elif kind == NodeKind.IF_STMT:
                        work.extend([("branch", node, None), ("expr", node.condition, None)])
                    elif kind in {NodeKind.VAR, NodeKind.CONST}:
                        key = f"effect:{serial}:{self._key(node)}"
                        bindings[-1][self._key(node)] = key
                        work.extend([("store", node, key), ("expr", node.value, None)])
                    elif kind == NodeKind.ASSIGNMENT:
                        work.append(("store", node, None))
                        # Assignment evaluates its RHS before its target base.
                        if node.target.kind == NodeKind.FIELD_ACCESS:
                            work.append(("target", node.target, None))
                        work.append(("expr", node.value, None))
                    elif kind == NodeKind.DEL:
                        work.extend([("delete", node, None), ("expr", node.expression, None)])
                    elif kind == NodeKind.EXPRESSION_STMT:
                        work.append(("expr", node.expression, None))
                    continue
                if action == "branch":
                    condition = node.condition
                    refinement = None
                    if condition.kind == NodeKind.BINARY and condition.operator in {BinaryOp.EQ, BinaryOp.NE}:
                        left, right = condition.left, condition.right
                        if right and right.kind == NodeKind.LITERAL and right.literal_kind == LiteralKind.NIL:
                            refinement = (places.get(id(left)), condition.operator == BinaryOp.NE)
                        elif left and left.kind == NodeKind.LITERAL and left.literal_kind == LiteralKind.NIL:
                            refinement = (places.get(id(right)), condition.operator == BinaryOp.NE)
                    for positive, body in [(False, node.else_stmt), (True, node.then_stmt)]:
                        branch_storage = dict(storage)
                        if refinement and refinement[0]:
                            key, non_nil_when_true = refinement
                            fact = branch_storage.get(key, ValueFact())
                            non_nil = positive == non_nil_when_true
                            if not non_nil and fact.non_nil:
                                continue
                            branch_storage[key] = replace(fact, non_nil=non_nil, maybe_nil=not non_nil)
                        paths.append((work + [("stmt", body, None)], branch_storage, set(moved),
                                      dict(values), dict(places), [dict(b) for b in bindings],
                                      [list(s) for s in scopes]))
                    break
                if action == "target":
                    work.extend([("field", node, True), ("expr", node.object, None)])
                    continue
                if action == "store":
                    target = node.target if node.kind == NodeKind.ASSIGNMENT else None
                    key = extra or (places.get(id(target)) if target.kind == NodeKind.FIELD_ACCESS else
                                    bindings[-1].get(self._key(target), self._key(target)))
                    fact = values.get(id(node.value), ValueFact())
                    fact = fact if isinstance(self._type(node.value), ReferenceType) or fact.maybe_nil else ValueFact()
                    previous = storage.get(key, ValueFact())
                    previous_ids = previous.allocations | previous.selected_allocations
                    storage[key] = fact
                    self._clear_moved_slot(key, moved)
                    field = key.rsplit(".", 1)[-1] if isinstance(key, str) and "." in key else None
                    if (isinstance(key, str) and key.startswith("@allocation:") and field and previous_ids
                            and previous_ids != (fact.allocations | fact.selected_allocations)):
                        suffix = "." + field
                        for name, existing in list(storage.items()):
                            if not isinstance(name, str) or name == key or not name.endswith(suffix):
                                continue
                            if name.startswith("@allocation:"):
                                continue
                            held = existing.allocations | existing.selected_allocations
                            if not (held & previous_ids):
                                continue
                            storage[name] = replace(
                                existing,
                                non_nil=fact.non_nil,
                                maybe_nil=fact.maybe_nil or not fact.non_nil,
                                allocations=fact.allocations,
                                selected_allocations=fact.selected_allocations,
                            )
                    continue
                if action == "delete":
                    fact = values.get(id(node.expression), ValueFact())
                    self._move_allocations(fact.allocations, moved)
                    key = places.get(id(node.expression))
                    if key:
                        self._mark_moved_slot(key, fact.allocations, moved)
                    continue
                if action == "expr":
                    if node is None:
                        continue
                    if node.kind == NodeKind.IDENTIFIER:
                        key = bindings[-1].get(self._key(node), self._key(node))
                        places[id(node)] = key
                        fact = storage.get(key, ValueFact())
                        values[id(node)] = fact
                        if self._slot_moved(key, moved) or self._allocations_moved(fact.allocations | fact.selected_allocations, moved):
                            obligation = self._obligation(ObligationKind.MOVE_VALID, node, f"callee_live:{id(call)}", self._type(node), "callee value must still be live", TypeErrorType.USE_AFTER_MOVE)
                            self._error(obligation, f"'{node.name}' was moved or deleted earlier")
                    elif node.kind == NodeKind.LITERAL:
                        values[id(node)] = self._literal_fact(node)
                    elif node.kind == NodeKind.FIELD_ACCESS:
                        work.extend([("field", node, False), ("expr", node.object, None)])
                    elif node.kind == NodeKind.CALL:
                        work.append(("invoke", node, None))
                        work.extend(("expr", arg, None) for arg in reversed(node.arguments or []))
                    else:
                        values[id(node)] = ValueFact()
                        children = [value for value in vars(node).values() if isinstance(value, ASTNode) and not value.kind.name.startswith("TYPE_")]
                        work.extend(("expr", child, None) for child in reversed(children))
                    continue
                if action == "field":
                    base = values.get(id(node.object), ValueFact())
                    root = places.get(id(node.object))
                    if isinstance(self._type(node.object), ReferenceType):
                        if not base.non_nil:
                            obligation = self._obligation(ObligationKind.REF_NON_NIL, node, f"callee_non_nil:{id(call)}", self._type(node.object), "callee field access must remain non-nil", TypeErrorType.CANNOT_DEREFERENCE)
                            self._error(obligation, "reference may be nil after caller aliases are substituted")
                        if self._allocation_count(base.allocations) == 1:
                            root = self._allocation_place(base.allocations)
                            if root.startswith("@allocation:storage:"):
                                root = root.removeprefix("@allocation:storage:")
                    key = (root or "") + "." + node.field
                    places[id(node)] = key
                    if not extra:
                        fact = storage.get(key)
                        if fact is None:
                            fact = ValueFact(maybe_nil=True, allocations=self._field_allocations(key)) if isinstance(self._type(node), ReferenceType) else ValueFact()
                            storage[key] = fact
                        values[id(node)] = fact
                        if self._slot_moved(key, moved) or self._allocations_moved(fact.allocations | fact.selected_allocations, moved):
                            obligation = self._obligation(ObligationKind.MOVE_VALID, node, f"callee_live:{id(call)}", self._type(node), "callee field value must still be live", TypeErrorType.USE_AFTER_MOVE)
                            self._error(obligation, f"'{node.field}' was moved or deleted earlier")
                    continue
                if action == "invoke":
                    values[id(node)] = ValueFact()
                    if not getattr(node, "stdlib_canonical", None):
                        callee = self.exact_effect_bodies[self._key(node.function)]
                        args = []
                        borrowed = getattr(node, "implicit_ref_args", set())
                        for index, arg in enumerate(node.arguments or []):
                            fact = values.get(id(arg), ValueFact())
                            if isinstance(self._type(arg), ReferenceType) and index not in borrowed and not fact.non_nil:
                                obligation = self._obligation(ObligationKind.REF_NON_NIL, arg, f"callee_argument:{id(call)}", self._type(arg), "callee reference argument must remain non-nil", TypeErrorType.CANNOT_DEREFERENCE)
                                self._error(obligation, "reference may be nil after caller aliases are substituted")
                            args.append((fact, places.get(id(arg)) if index in borrowed else None))
                        work.append(("enter", callee, args))
                    continue
            else:
                exits.append((storage, moved))
        if exits:
            joined, dead = exits[0]
            for storage, moved in exits[1:]:
                joined, dead = self._join_lifetime_states(joined, dead, storage, moved)
            self.facts.by_symbol = {key: fact for key, fact in joined.items() if not isinstance(key, str) or not key.startswith("effect:")}
            self.moved_symbols = {key for key in dead
                                  if not (isinstance(key, str) and key.startswith("effect:"))
                                  and not (isinstance(key, SlotDeath) and key.key.startswith("effect:"))}

    def _parameter_origins(self, node: Optional[ASTNode], aliases: dict[str | tuple[int, str], frozenset[tuple[int | AllocationRef, bool]]], *, field_places: bool = False, unknown_origins: frozenset[tuple[int | AllocationRef, bool]] = frozenset()) -> frozenset[tuple[int | AllocationRef, bool]]:
        origins: set[tuple[int, bool]] = set()
        pending = [(node, True)]
        while pending:
            current, exact = pending.pop()
            if current is None:
                continue
            if current.kind == NodeKind.IDENTIFIER:
                origins.update((index, exact and direct) for index, direct in aliases.get(self._key(current), unknown_origins))
            elif current.kind == NodeKind.FIELD_ACCESS:
                if field_places:
                    origins.update((index, exact and direct) for index, direct in aliases.get(self._place_key(current), unknown_origins))
                else:
                    pending.append((current.object, False))
            elif current.kind == NodeKind.NEW_EXPR and not field_places:
                origin = AllocationRef(self.allocation_graph.atom(("new", id(current))))
                origins.add((origin, True))
            elif current.kind == NodeKind.CALL:
                origins.update(aliases.get(f"@call:{id(current)}", unknown_origins))
            elif current.kind == NodeKind.IF_EXPR:
                pending.extend([(current.then_expr, exact), (current.else_expr, exact)])
            elif current.kind == NodeKind.MATCH_EXPR:
                pending.extend((getattr(case, "expression", None), exact) for case in current.cases or [])
                if isinstance(current.else_case, ASTNode):
                    pending.append((current.else_case, exact))
        return self._origin_set(origins)

    def _has_reference_storage(self, type_: Optional[Type]) -> bool:
        """Whether storing this value can expose reference aliases."""
        pending = [type_]
        seen = set()
        while pending:
            current = pending.pop()
            if current is None or current.kind in {TypeKind.UNKNOWN, TypeKind.GENERIC_PARAM, TypeKind.GENERIC_INSTANCE}:
                return True
            if id(current) in seen:
                continue
            seen.add(id(current))
            if isinstance(current, (ReferenceType, FunctionType)):
                return True
            if isinstance(current, (ArrayType, SliceType)):
                pending.append(current.element_type)
            elif current.kind in {TypeKind.STRUCT, TypeKind.UNION}:
                pending.extend(member.field_type for member in current.fields)
        return False

    def _effect_scalar_value(self, node, values):
        if node is not None and node.kind == NodeKind.IDENTIFIER:
            return values.get(self._key(node))
        if node is not None and node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER:
            return node.literal_value
        return None

    def _effect_scalar_condition(self, node, values):
        if node is not None and node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.BOOLEAN:
            return node.literal_value
        if node is not None and node.kind == NodeKind.BINARY:
            left = self._effect_scalar_value(node.left, values)
            right = self._effect_scalar_value(node.right, values)
            if left is not None and right is not None:
                return {BinaryOp.EQ: left == right, BinaryOp.NE: left != right,
                        BinaryOp.LT: left < right, BinaryOp.LE: left <= right,
                        BinaryOp.GT: left > right, BinaryOp.GE: left >= right}.get(node.operator)
        return None

    def _effect_scalar_cases(self, node, cases, reachable):
        if node is not None and node.kind == NodeKind.IDENTIFIER:
            return {value: active for value, guard in cases.get(self._key(node), {}).items()
                    if (active := self.allocation_conditions.combine('and', reachable, guard))}
        if node is not None and node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER:
            return {node.literal_value: reachable} if reachable else {}
        return {}

    def _parameter_effect_summary(self, function: ASTNode, aliases: Optional[dict[str | tuple[int, str], frozenset[tuple[int | AllocationRef, bool]]]] = None, *, loop_results=None):
        # Local rebinding changes which parameter a field write or direct
        # deletion reaches. Branches join origins; loops iterate a finite set
        # of parameter indices, not increasingly long access paths.
        field_places = aliases is not None
        condition = function.condition if field_places else None
        counter = (self._key(condition.left) if condition and condition.kind == NodeKind.BINARY
                   and condition.operator in {BinaryOp.LT, BinaryOp.LE}
                   and condition.left.kind == NodeKind.IDENTIFIER else None)
        if aliases is None:
            aliases = {self._key(param): frozenset({(index, True)})
                       for index, param in enumerate(function.parameters or [])}
            aliases.update({key: frozenset({(origin, True)}) for origin, key in self.global_origins.items()})
        predicate_writes = set()
        predicate_nodes = []
        stable_conditions = {}
        predicate_conditions = {}
        entry_condition = None
        if field_places:
            pending_predicates = [function]
            while pending_predicates:
                statement = pending_predicates.pop()
                if statement.kind == NodeKind.FUNCTION:
                    continue
                if statement.kind in {NodeKind.IF_STMT, NodeKind.IF_EXPR, NodeKind.WHILE, NodeKind.FOR}:
                    predicate_nodes.append(statement.condition)
                elif statement.kind == NodeKind.BINARY and statement.operator in {BinaryOp.AND, BinaryOp.OR}:
                    predicate_nodes.append(statement.left)
                if statement.kind == NodeKind.ASSIGNMENT and statement.target is not None and statement.target.kind == NodeKind.IDENTIFIER:
                    predicate_writes.add(self._key(statement.target))
                elif statement.kind == NodeKind.CALL:
                    predicate_writes.update(self.capture_call_effects.get(id(statement), self.mutable_boolean_captures))
                    predicate_writes.update(self._key(argument) for index, argument in enumerate(statement.arguments or [])
                        if argument.kind == NodeKind.IDENTIFIER and index in getattr(statement, 'implicit_ref_args', set()))
                for value in vars(statement).values():
                    if isinstance(value, ASTNode):
                        pending_predicates.append(value)
                    elif isinstance(value, list):
                        pending_predicates.extend(child for child in value if isinstance(child, ASTNode))
            if function.kind == NodeKind.WHILE:
                entry_condition = self._stable_boolean_condition(function.condition)
            for predicate_node in predicate_nodes:
                predicate = self._stable_boolean_condition(predicate_node, predicate_writes)
                predicate_conditions[id(predicate_node)] = predicate
                binding = predicate_node
                while binding is not None and binding.kind == NodeKind.UNARY and binding.operator == UnaryOp.NOT:
                    binding = binding.operand
                key = self._key(binding) if binding is not None and binding.kind == NodeKind.IDENTIFIER else None
                type_ = self._type(binding) if binding is not None else None
                if (key in self.local_boolean_keys and key not in self.borrowed_keys
                        and key not in self.file_variables and key not in self.repeated_boolean_keys
                        and key not in predicate_writes and key in self.facts.by_symbol
                        and self.facts.symbol(key).initialized
                        and isinstance(type_, PrimitiveType) and type_.name == "bool"):
                    stable_conditions[id(predicate_node)] = predicate
            if loop_results is not None:
                loop_results["stable_conditions"] = dict(stable_conditions)
        unknown_origins = frozenset().union(*aliases.values()) if field_places else frozenset({(-1, True)})
        # Negative integers distinguish unknown (-1), unchanged fields (-3),
        # and global declarations. Fresh alternatives share allocation graphs.
        unchanged = frozenset({(-3, True)})
        exits = []
        returned = []
        live = True
        writes: dict[int, set[str]] = {}
        flow = ParameterEffectState(aliases)
        if field_places:
            flow.scalar_values = {key: fact.interval.lower for key, fact in self.facts.by_symbol.items()
                                  if key in self.scalar_eligible_keys
                                  and fact.interval is not None and fact.interval.lower is not None
                                  and fact.interval.lower == fact.interval.upper}
            flow.scalar_cases = {key: {value: 1} for key, value in flow.scalar_values.items()}
        if field_places:
            # Current slot validity is separate from historical allocation death.
            # Rebinding a slot cannot revive another alias to the old object.
            flow.current_aliases = dict(aliases)
            flow.current_live = {key for key, fact in self.facts.by_symbol.items()
                                 if isinstance(key, str) and "." not in key
                                 and isinstance(self.symbol_types.get(key), ReferenceType)
                                 and not self._slot_moved(key)
                                 and not self._allocations_moved(fact.allocations | fact.selected_allocations)}
        loops = []
        frames: list[tuple[ASTNode, list[ASTNode]]] = []
        work = [("visit", function if field_places else function.body, None)]
        while work:
            action, node, state = work.pop()
            if action == "scalar_invalidate":
                if live:
                    for key in self.scalar_direct_writes.get(id(node), ()):
                        flow.scalar_values.pop(key, None)
                        flow.scalar_cases.pop(key, None)
                continue
            if action == "scalar_clear":
                if live:
                    flow.scalar_values = {key: value for key, value in flow.scalar_values.items()
                                          if key in self.scalar_eligible_keys}
                    flow.scalar_cases = {key: values for key, values in flow.scalar_cases.items()
                                         if key in self.scalar_eligible_keys}
                    if field_places:
                        flow.written.update(self.capture_call_effects.get(id(node), self.mutable_boolean_captures))
                continue
            if action == "scalar_store":
                if live:
                    key, operator = state
                    reachable = 0
                    for path in flow.paths:
                        reachable = self.allocation_conditions.combine('or', reachable, path)
                    values = self._effect_scalar_cases(node.value, flow.scalar_cases, reachable)
                    if operator != AssignOp.ASSIGN:
                        combined = {}
                        if operator in {AssignOp.ADD_ASSIGN, AssignOp.SUB_ASSIGN}:
                            for previous, left in flow.scalar_cases.get(key, {}).items():
                                for amount, right in values.items():
                                    guard = self.allocation_conditions.combine('and', left, right)
                                    result = previous + amount if operator == AssignOp.ADD_ASSIGN else previous - amount
                                    if guard:
                                        combined[result] = self.allocation_conditions.combine('or', combined.get(result, 0), guard)
                        values = combined
                    scalar_type = self._type(node.target if node.kind == NodeKind.ASSIGNMENT else node)
                    values = {value: guard for value, guard in values.items()
                              if self._range_fits(IntegerInterval.exact(value), scalar_type)}
                    if values:
                        flow.scalar_cases[key] = values
                    else:
                        flow.scalar_cases.pop(key, None)
                    value = self._effect_scalar_value(node.value, flow.scalar_values)
                    if operator != AssignOp.ASSIGN:
                        previous = flow.scalar_values.get(key)
                        if value is not None and previous is not None and operator in {AssignOp.ADD_ASSIGN, AssignOp.SUB_ASSIGN}:
                            value = previous + value if operator == AssignOp.ADD_ASSIGN else previous - value
                        else:
                            value = None
                    if value is not None and self._range_fits(IntegerInterval.exact(value), self._type(node.target if node.kind == NodeKind.ASSIGNMENT else node)):
                        flow.scalar_values[key] = value
                    else:
                        flow.scalar_values.pop(key, None)
                continue
            if action == "capture_return":
                state.extend(self._parameter_origins(node.value, flow.aliases, field_places=field_places, unknown_origins=unknown_origins))
                continue
            if action == "terminal":
                kind, target, value_origins = state
                if live:
                    if kind == NodeKind.RETURN:
                        if not field_places:
                            exits.append(flow.copy())
                            returned.append((self._origin_set(value_origins), self._origin_intersection(
                                [origin for origin, exact in value_origins if exact], flow.deleted)))
                    elif target is not None:
                        target["breaks" if kind == NodeKind.BREAK else "continues"].append(flow.copy())
                live = False
                continue
            if action == "block_end":
                _, deferred = frames.pop()
                if live:
                    work.extend(("visit", stmt, None) for stmt in deferred)
                continue
            if action == "loop_start":
                context = {"node": node, "entry": flow.copy(), "head": flow.copy(),
                           "back": [], "breaks": [], "continues": [], "false": []}
                loops.append(context)
                frames.append((node, []))
                work.extend([("loop_end", node, context), ("loop_condition", node, context),
                             ("visit", node.condition, None)])
                continue
            if action == "loop_condition":
                context = state
                if live:
                    if field_places and node is function:
                        # Measure one body-to-backedge path, not accumulated trips.
                        flow.counter_delta = (0, 0)
                    condition = node.condition
                    literal = condition.literal_value if condition and condition.kind == NodeKind.LITERAL and condition.literal_kind == LiteralKind.BOOLEAN else None
                    # This is only the root WHILE's first condition. A body
                    # write cannot make a known-false first entry reachable.
                    # FOR initializers and nested tests need their own state.
                    if (field_places and node is function and node.kind == NodeKind.WHILE
                            and not context["back"] and entry_condition == 0):
                        literal = False
                    predicate = predicate_conditions.get(id(condition)) if field_places else None
                    if literal is not True:
                        false_flow = flow.copy()
                        if predicate is None or self._condition_effect_state(false_flow, self.allocation_conditions.combine('xor', predicate, 1)):
                            context["false"].append(false_flow)
                    if literal is not False and (predicate is None or self._condition_effect_state(flow, predicate)):
                        work.extend([("loop_update", node, context), ("visit", node.body, None)])
                    else:
                        live = False
                continue
            if action == "loop_update":
                context = state
                incoming = context["continues"]
                if live:
                    incoming.append(flow.copy())
                live = bool(incoming)
                if live:
                    flow = ParameterEffectState.join(incoming, self.allocation_conditions)
                    context["continues"] = []
                    work.extend([("loop_back", node, context), ("visit", node.update, None)])
                continue
            if action == "loop_back":
                context = state
                if live:
                    if field_places and node is not function and flow.counter_delta != context["entry"].counter_delta:
                        # Repeated inner writes cannot bound this outer trip.
                        # An outer defer on a labeled exit never reaches here.
                        flow.counter_delta = None
                    context["back"].append(flow.copy())
                    if field_places and node is function and loop_results is not None and "first_back" not in loop_results:
                        loop_results["first_back"] = flow.copy()
                head = ParameterEffectState.join([context["entry"], *context["back"]], self.allocation_conditions)
                if head != context["head"]:
                    context["head"] = head.copy()
                    flow, live = head, True
                    work.extend([("loop_condition", node, context), ("visit", node.condition, None)])
                continue
            if action == "loop_end":
                context = state
                frames.pop()
                loops.pop()
                normal_exits = [*context["false"], *context["breaks"]]
                if field_places and node is function and loop_results is not None:
                    loop_results.update(back=ParameterEffectState.join(context["back"], self.allocation_conditions),
                                        exit=ParameterEffectState.join(normal_exits, self.allocation_conditions),
                                        has_break=bool(context["breaks"]))
                live = bool(normal_exits)
                if live:
                    flow = ParameterEffectState.join(normal_exits, self.allocation_conditions)
                continue
            if action == "restrict":
                if live:
                    live = self._condition_effect_state(flow, state)
                continue
            if action == "bind":
                if live:
                    key, value = state
                    flow.aliases[key] = self._parameter_origins(value, flow.aliases, field_places=field_places, unknown_origins=unknown_origins)
                    if field_places:
                        source_live = value is not None and value.kind == NodeKind.IDENTIFIER and self._key(value) in flow.current_live
                        source_dead = value is not None and value.kind == NodeKind.IDENTIFIER and self._key(value) in flow.current_dead
                        source_nil = value is not None and value.kind == NodeKind.IDENTIFIER and self._key(value) in flow.current_nil
                        if value is not None and value.kind == NodeKind.NEW_EXPR:
                            # Another execution of one allocation site creates a
                            # distinct object. Preserve older aliases, never revive them.
                            fresh = self.allocation_graph.atom(("new", id(value)))
                            prior = self.allocation_graph.prefix(("prior_iteration", id(value)), fresh)
                            for place, origins in list(flow.current_aliases.items()):
                                aged = set()
                                for origin, exact in origins:
                                    if isinstance(origin, AllocationRef):
                                        overlap = self.allocation_graph.combine('intersection', origin.root, fresh)
                                        if overlap:
                                            remainder = self.allocation_graph.combine('difference', origin.root, fresh)
                                            origin = AllocationRef(self.allocation_graph.union((remainder, prior)), origin.condition)
                                    aged.add((origin, exact))
                                flow.current_aliases[place] = self._origin_set(aged)
                        flow.current_aliases[key] = self._parameter_origins(value, flow.current_aliases, unknown_origins=unknown_origins)
                        flow.current_live.discard(key)
                        flow.current_dead.discard(key)
                        flow.current_nil.discard(key)
                        if value is not None and value.kind == NodeKind.LITERAL and value.literal_kind == LiteralKind.NIL:
                            flow.current_nil.add(key)
                            flow.current_live.add(key)
                            flow.replaced.add(key)
                        elif value is not None and value.kind == NodeKind.NEW_EXPR:
                            flow.current_live.add(key)
                            flow.replaced.add(key)
                        elif source_live:
                            flow.current_live.add(key)
                            if source_nil:
                                flow.current_nil.add(key)
                        elif source_dead:
                            flow.current_dead.add(key)
                        elif isinstance(self._type(value), ReferenceType):
                            flow.replacement_escaped = True
                        if "." in key and self._has_reference_storage(self._type(value)):
                            # Aggregate-held aliases keep the existing aggregate
                            # analysis; do not project their owners separately.
                            flow.current_live.clear()
                            flow.replacement_escaped = True
                continue
            if action == "store":
                if live:
                    targets, value = state
                    origins = self._parameter_origins(value, flow.aliases, unknown_origins=unknown_origins)
                    for target in targets:
                        flow.aliases[target] = origins if len(targets) == 1 else flow.aliases.get(target, unchanged) | origins
                continue
            if action == "call_argument":
                if live:
                    argument, captured = state
                    origins = self._parameter_origins(argument, flow.aliases, field_places=field_places,
                                                      unknown_origins=unknown_origins)
                    if field_places and len(captured) in getattr(node, "implicit_ref_args", set()):
                        origins = frozenset()
                    captured.append((origins, self._place_key(argument)))
                continue
            if action == "call_effects":
                if not live:
                    continue
                for key in self.scalar_call_writes.get(id(node), ()):
                    flow.scalar_values.pop(key, None)
                    flow.scalar_cases.pop(key, None)
                # Escaped storage cannot regain a scalar proof after a call.
                flow.scalar_values = {key: value for key, value in flow.scalar_values.items()
                                      if key in self.scalar_eligible_keys}
                flow.scalar_cases = {key: values for key, values in flow.scalar_cases.items()
                                     if key in self.scalar_eligible_keys}
                name, captured = state
                summary = self.function_field_writes.get(name)
                stores = self.function_field_stores.get(name, {})
                if field_places:
                    # Unknown or summarized calls retain their existing effects;
                    # this additional replacement proof does not infer effects.
                    flow.current_live.clear()
                    flow.replacement_escaped = True
                    flow.written.update(self.file_variables)
                    flow.written.update(self.capture_call_effects.get(id(node), self.mutable_boolean_captures))
                    signature = self._type(node.function)
                    parameters = signature.param_types if isinstance(signature, FunctionType) else []
                    may_delete = self._calls_deleting_function(node)
                    parameter_deletes = self.function_parameter_deletes.get(name, set())
                    for index, argument in enumerate(node.arguments or []):
                        origins, key = captured[index]
                        if key is None:
                            continue
                        is_ref = isinstance(self._type(argument), ReferenceType)
                        reference_parameter = index < len(parameters) and isinstance(parameters[index], ReferenceType)
                        if argument.kind == NodeKind.FIELD_ACCESS and index in parameter_deletes and is_ref and reference_parameter:
                            flow.written.add(key)
                            previous = flow.places.get(key, frozenset())
                            affected = frozenset(origin for origin, exact in origins if exact)
                            flow.places[key] = None if previous is None else previous | affected
                        elif argument.kind == NodeKind.IDENTIFIER:
                            if is_ref or index in getattr(node, "implicit_ref_args", set()):
                                flow.written.add(key)
                            if may_delete and is_ref and reference_parameter:
                                flow.places[key] = None
                # Actuals have already run. Global tokens denote these entry
                # values even when the callee later replaces their slots.
                entry_globals = dict(flow.aliases)
                global_stores, global_deleted, _ = self.function_global_effects.get(name, ({}, frozenset(), frozenset()))
                for key in self.function_written_globals.get(name, self.file_variables):
                    if key in flow.aliases:
                        flow.aliases[key] = unknown_origins
                return_origins, dead_returns = self.function_returns.get(name, (frozenset({(-1, True)}), frozenset()))
                translated_returns = set()
                translated_globals = {}
                groups = [(None, return_origins), (False, ((origin, True) for origin in dead_returns | global_deleted))]
                groups.extend((key, origins) for key, origins in global_stores.items())
                for destination, group in groups:
                    translated = set()
                    for origin, exact in group:
                        if not exact or origin == -1:
                            values = unknown_origins
                        elif isinstance(origin, int) and origin >= 0 and origin < len(captured):
                            values = captured[origin][0]
                        elif origin in self.global_origins:
                            values = entry_globals.get(self.global_origins[origin], unknown_origins)
                        elif isinstance(origin, AllocationRef):
                            if field_places:
                                values = frozenset()
                            else:
                                invocation = AllocationRef(self.allocation_graph.prefix(("call", id(node)), origin.root), origin.condition)
                                values = frozenset({(invocation, True)})
                        else:
                            values = unknown_origins
                        if destination is False:
                            flow.deleted.update(value for value, direct in values if direct)
                        else:
                            translated.update(values)
                    if destination is None:
                        translated_returns.update(translated)
                    elif destination is not False:
                        translated_globals[destination] = self._origin_set(translated)
                flow.aliases.update(translated_globals)
                flow.aliases[f"@call:{id(node)}"] = self._origin_set(translated_returns)
                for index in self.function_parameter_deletes.get(name, set()):
                    if index < len(captured):
                        flow.deleted.update(origin for origin, exact in captured[index][0] if exact)
                for index, (origins, key) in enumerate(captured):
                    for path in summary.get(index, set()) if summary is not None else {""}:
                        value = stores.get((index, path), frozenset({(-1, True)}))
                        translated = set()
                        for origin, exact in value:
                            if isinstance(origin, int) and origin >= 0 and origin < len(captured):
                                translated.update((item, direct and exact) for item, direct in captured[origin][0])
                            elif origin == -1:
                                translated.update(unknown_origins)
                            elif isinstance(origin, AllocationRef) and not field_places:
                                invocation = AllocationRef(self.allocation_graph.prefix(("call", id(node)), origin.root), origin.condition)
                                translated.add((invocation, exact))
                            elif origin in self.global_origins:
                                translated.update(entry_globals.get(self.global_origins[origin], unknown_origins))
                        targets = []
                        if field_places and key:
                            prefixes = [key]
                            prefixes.extend(self._allocation_prefixes(self.facts.symbol(key).allocations))
                            for prefix in prefixes:
                                target = prefix + ("." + path if path else "")
                                if path and (index, path) in stores:
                                    targets.append(target)
                                targets.extend(place for place in flow.aliases if place != target and place.startswith(target + ".")
                                               or place == target and target not in targets)
                        elif not field_places:
                            for origin, exact in origins:
                                if isinstance(origin, int) and origin >= 0:
                                    target_path = path if exact else ""
                                    writes.setdefault(origin, set()).add(target_path)
                                    targets.append((origin, target_path))
                        ordinary_count = sum(not isinstance(origin, AllocationRef) for origin, _ in origins)
                        fresh_count = sum(self.allocation_graph.cardinality[self.allocation_graph.union(
                            origin.root for origin, direct in origins if isinstance(origin, AllocationRef) and direct == exact)]
                            for exact in (False, True))
                        multiple_origins = ordinary_count + fresh_count > 1
                        for target in targets:
                            previous = flow.aliases.get(target, unchanged if not field_places else unknown_origins)
                            result = self._origin_set(translated)
                            if (-3, True) in value or multiple_origins:
                                result |= previous
                            flow.aliases[target] = result
                continue
            if action in {"other", "fall_other"}:
                before, branches, before_live = state
                if live and action != "fall_other":
                    branches.append(flow.copy())
                flow = ParameterEffectState.join([before, flow], self.allocation_conditions) if action == "fall_other" and live else before.copy()
                live = before_live
                continue
            if action == "join":
                before, branches, before_live = state
                if live:
                    branches.append(flow.copy())
                live = bool(branches) and before_live
                flow = ParameterEffectState.join(branches, self.allocation_conditions)
                continue
            if action == "split":
                if not live:
                    continue
                # Conditions and scrutinees run before every branch. Retain
                # their stores on skipped short-circuit paths as well.
                if node.kind in {NodeKind.MATCH, NodeKind.MATCH_EXPR}:
                    frame = (flow.copy(), [flow.copy()] if not node.else_case else [], live)
                    actions = []
                    for case in node.cases or []:
                        statements = case.statements or ([] if case.statement is None else [case.statement])
                        last = statements[-1] if statements else None
                        while last is not None and last.kind == NodeKind.BLOCK and last.statements:
                            last = last.statements[-1]
                        branch_action = "fall_other" if last is not None and last.kind == NodeKind.FALL else "other"
                        actions.extend([("visit", case, None), (branch_action, node, frame)])
                    if isinstance(node.else_case, ASTNode):
                        actions.append(("visit", node.else_case, None))
                    else:
                        actions.extend(("visit", stmt, None) for stmt in node.else_case or [])
                    actions.append(("join", node, frame))
                    work.extend(reversed(actions))
                else:
                    condition = node.left if node.kind == NodeKind.BINARY else node.condition
                    if node.kind == NodeKind.BINARY:
                        then_branch, else_branch = ((node.right, None) if node.operator == BinaryOp.AND
                                                    else (None, node.right))
                    elif node.kind == NodeKind.IF_EXPR:
                        then_branch, else_branch = node.then_expr, node.else_expr
                    else:
                        then_branch, else_branch = node.then_stmt, node.else_stmt
                    scalar_condition = self._effect_scalar_condition(condition, flow.scalar_values) if field_places else None
                    if scalar_condition is not None:
                        work.append(("visit", then_branch if scalar_condition else else_branch, None))
                    elif (condition.kind == NodeKind.LITERAL
                            and condition.literal_kind == LiteralKind.BOOLEAN):
                        work.append(("visit", then_branch if condition.literal_value else else_branch, None))
                    else:
                        frame = (flow.copy(), [], live)
                        predicate = predicate_conditions.get(id(condition)) if field_places else None
                        if predicate is None:
                            work.extend([("join", node, frame), ("visit", else_branch, None),
                                         ("other", node, frame), ("visit", then_branch, None)])
                        else:
                            work.extend([("join", node, frame), ("visit", else_branch, None),
                                         ("restrict", node, self.allocation_conditions.combine('xor', predicate, 1)),
                                         ("other", node, frame), ("visit", then_branch, None),
                                         ("restrict", node, predicate)])
                continue
            if not live or node is None or node.kind == NodeKind.FUNCTION:
                continue
            if node.kind == NodeKind.BLOCK:
                frames.append((node, []))
                work.append(("block_end", node, None))
                work.extend(("visit", stmt, None) for stmt in reversed(node.statements or []))
                continue
            if node.kind == NodeKind.DEFER:
                frames[-1][1].append(node.statement)
                continue
            if node.kind in EXIT_KINDS:
                deferred = []
                target = None
                if node.kind != NodeKind.RETURN:
                    target = next((context for context in reversed(loops) if node.label in {None, context["node"].label}), None)
                for owner, registered in reversed(frames):
                    if target is not None and owner is target["node"]:
                        break
                    deferred.extend(reversed(registered))
                value_origins = []
                work.append(("terminal", node, (node.kind, target, value_origins)))
                work.extend(("visit", stmt, None) for stmt in reversed(deferred))
                if node.kind == NodeKind.RETURN:
                    work.extend([("capture_return", node, value_origins), ("visit", node.value, None)])
                continue
            if (node.kind in {NodeKind.IF_STMT, NodeKind.IF_EXPR, NodeKind.MATCH, NodeKind.MATCH_EXPR}
                    or node.kind == NodeKind.BINARY and node.operator in {BinaryOp.AND, BinaryOp.OR}):
                condition = (node.left if node.kind == NodeKind.BINARY else
                             node.expression if node.kind in {NodeKind.MATCH, NodeKind.MATCH_EXPR}
                             else node.condition)
                work.extend([("split", node, None), ("visit", condition, None)])
                continue
            if node.kind in LOOP_KINDS:
                work.append(("loop_start", node, None))
                if not (field_places and node is function):
                    work.extend([("visit", node.init, None), ("visit", node.iterable, None)])
                continue
            if field_places and node.kind == NodeKind.ASSIGNMENT:
                work.append(("scalar_invalidate", node, None))
            if field_places and node.kind in {NodeKind.ASSIGNMENT, NodeKind.VAR, NodeKind.CONST}:
                target = node.target if node.kind == NodeKind.ASSIGNMENT else node
                key = self._key(target) if target is not None and target.kind in {NodeKind.IDENTIFIER, NodeKind.VAR, NodeKind.CONST} else None
                if key in self.scalar_eligible_keys:
                    work.append(("scalar_store", node, (key, node.operator if node.kind == NodeKind.ASSIGNMENT else AssignOp.ASSIGN)))
            if node.kind == NodeKind.CALL and getattr(node, "stdlib_canonical", None):
                work.append(("scalar_clear", node, None))
            if node.kind == NodeKind.CALL and not getattr(node, "stdlib_canonical", None):
                callee = node.function
                name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
                captured = []
                actions = [("visit", callee, None)]
                for argument in node.arguments or []:
                    actions.extend([("visit", argument, None), ("call_argument", node, (argument, captured))])
                actions.append(("call_effects", node, (name, captured)))
                work.extend(reversed(actions))
                continue
            if field_places and node.kind in {NodeKind.STRUCT_INIT, NodeKind.ARRAY_INIT} and self._has_reference_storage(self._type(node)):
                flow.current_live.clear()
                flow.replacement_escaped = True
            targets = []
            deletion_targets = []
            if node.kind == NodeKind.DEL:
                deletion_targets.append(node.expression)
                if field_places:
                    current = self._parameter_origins(node.expression, flow.current_aliases, unknown_origins=unknown_origins)
                    if node.expression.kind != NodeKind.IDENTIFIER or any(not exact for _, exact in current):
                        flow.current_live.clear()
                        flow.replacement_escaped = True
                    else:
                        dead = {origin for origin, exact in current if exact}
                        for place, origins in flow.current_aliases.items():
                            if self._origin_intersection(tuple(origin for origin, exact in origins if exact), dead):
                                flow.current_live.discard(place)
                                flow.current_dead.add(place)
                        flow.current_live.discard(self._key(node.expression))
                        flow.current_dead.add(self._key(node.expression))
                    target = node.expression
                    key = self._place_key(target)
                    while key is None and target is not None:
                        attr = DEL_TARGET_BASE_ATTRS.get(target.kind)
                        target = getattr(target, attr, None) if attr else None
                        key = self._place_key(target)
                    if key:
                        flow.written.add(key)
                        affected = frozenset(origin for origin, exact in self._parameter_origins(
                            node.expression, flow.aliases, field_places=True, unknown_origins=unknown_origins) if exact)
                        previous = flow.places.get(key, frozenset())
                        flow.places[key] = (None if previous is None or target is not node.expression
                                            else previous | affected)
            elif node.kind == NodeKind.ASSIGNMENT:
                targets.append((node.target, ""))
                if field_places:
                    if (node.target.kind == NodeKind.INDEX or getattr(node, "implicit_deref_target", False)) and self._has_reference_storage(self._type(node.value)):
                        flow.current_live.clear()
                        flow.replacement_escaped = True
                    key = self._place_key(node.target)
                    if key:
                        flow.written.add(key)
                    if counter is not None and key == counter:
                        if (flow.counter_delta is not None
                                and node.operator == AssignOp.ADD_ASSIGN
                                and node.target.kind == NodeKind.IDENTIFIER
                                and node.value.kind == NodeKind.LITERAL
                                and node.value.literal_kind == LiteralKind.INTEGER
                                and node.value.literal_value > 0):
                            step = node.value.literal_value
                            flow.counter_delta = (flow.counter_delta[0] + step, flow.counter_delta[1] + step)
                        else:
                            flow.counter_delta = None
                if node.target and node.target.kind == NodeKind.IDENTIFIER and not getattr(node, "implicit_deref_target", False):
                    work.append(("bind", node, (self._key(node.target), node.value)))
                elif field_places and node.target and node.target.kind == NodeKind.FIELD_ACCESS:
                    key = self._place_key(node.target)
                    if key:
                        work.append(("bind", node, (key, node.value)))
            elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
                if isinstance(self._type(node.value), ReferenceType):
                    work.append(("bind", node, (self._key(node), node.value)))
            for target in deletion_targets:
                # A descendant origin does not mean the parameter itself dies.
                origins = self._parameter_origins(target, flow.aliases, field_places=field_places, unknown_origins=unknown_origins)
                if not field_places and any(not exact or origin == -1 for origin, exact in origins):
                    self.function_direct_deletes[self._key(function)] = False
                flow.deleted.update(index for index, exact in origins if exact)
            for target, suffix in targets:
                stored_value = node.value if node.kind == NodeKind.ASSIGNMENT else None
                fields = []
                while target is not None and target.kind == NodeKind.FIELD_ACCESS:
                    fields.append(target.field)
                    target = target.object
                store_targets = []
                for index, exact in self._parameter_origins(target, flow.aliases):
                    if not isinstance(index, int) or index < 0:
                        continue
                    if fields or node.kind == NodeKind.CALL:
                        path = ".".join([*reversed(fields), *([suffix] if suffix else [])]) if exact else ""
                        writes.setdefault(index, set()).add(path)
                        if fields and exact and not field_places and node.kind == NodeKind.ASSIGNMENT and isinstance(self._type(node.target), ReferenceType):
                            store_targets.append((index, path))
                if store_targets:
                    work.append(("store", node, (store_targets, stored_value)))
            children = []
            for value in vars(node).values():
                if isinstance(value, ASTNode):
                    children.append(value)
                elif isinstance(value, list):
                    children.extend(child for child in value if isinstance(child, ASTNode))
            work.extend(("visit", child, None) for child in reversed(children))
        if live:
            exits.append(flow.copy())
        stores = {key: self._origin_set(frozenset().union(*(branch.aliases.get(key, unchanged) for branch in exits)))
                  for key in set().union(*(branch.aliases.keys() for branch in exits)) if isinstance(key, tuple)}
        deleted = set().union(*(branch.deleted for branch in exits))
        return_origins = self._origin_set(frozenset().union(*(origins for origins, _ in returned)))
        if not field_places and function.body is None:
            return_origins = frozenset({(-1, True)})
        dead_returns = frozenset().union(*(dead for _, dead in returned))
        dead_returns = self._origin_intersection(dead_returns, dead_returns)
        global_stores = {key: self._origin_set(frozenset().union(*(branch.aliases.get(key, frozenset()) for branch in exits)))
                         for key in self.reference_globals if key in self.function_written_globals.get(self._key(function), set())}
        deleted_origins = frozenset(origin for origin, _ in self._origin_set((origin, True) for origin in deleted))
        if not field_places and -1 in deleted_origins:
            self.function_direct_deletes[self._key(function)] = False
        dead_globals = frozenset(key for key in self.reference_globals if any(
            self._origin_intersection((origin for origin, exact in branch.aliases.get(key, ()) if exact), branch.deleted)
            for branch in exits))
        return writes, {index for index in deleted if isinstance(index, int) and index >= 0}, stores, (return_origins, dead_returns), (global_stores, deleted_origins, dead_globals)

    def _visit_decl(self, node: ASTNode) -> None:
        if node.kind == NodeKind.FUNCTION and node.body:
            self.escaped_arrays = set()
            self.moved_symbols = set()
            self.symbol_types = {}
            self.frames = []
            self.defer_floor = 0
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    key = self._key(param)
                    fact = self._fact_from_type_node(param.param_type)
                    if isinstance(self._type(param), ReferenceType) or param.param_type and param.param_type.kind == NodeKind.TYPE_POINTER:
                        fact = replace(fact, allocations=frozenset({f"parameter:{key}"}))
                    self.facts.set_symbol(key, fact)
                    if param.param_type and param.param_type.type_name in INTEGER_RANGES:
                        self.symbol_types[key] = PrimitiveType(param.param_type.type_name)
            self._visit_stmt(node.body)
        elif node.kind == NodeKind.VAR and node.value:
            self.current_stmt_span = node.span
            fact = self._visit_expr(node.value)
            if node.name:
                self.facts.set_symbol(node.name, fact)

    def _calls_deleting_function(self, call: ASTNode) -> bool:
        """True unless the declaration-bound callee is known not to delete."""
        callee = call.function
        if callee is None or callee.kind != NodeKind.IDENTIFIER:
            return True
        return self.function_deletes.get(self._key(callee), True)

    def _stable_boolean_condition(self, node, invalidated=()):
        positive = True
        while node is not None and node.kind == NodeKind.UNARY and node.operator == UnaryOp.NOT:
            positive = not positive
            node = node.operand
        if node is None or node.kind != NodeKind.IDENTIFIER:
            return None
        key = self._key(node)
        # Facts carry value versions through copies and branch snapshots.
        # Repeated declarations and captures do not have a stable local version.
        if key not in self.local_boolean_keys or key in self.repeated_boolean_keys or key in invalidated:
            return None
        fact = self.facts.symbol(key)
        if fact.boolean is not None:
            condition = int(fact.boolean)
        elif fact.boolean_condition is not None:
            condition = fact.boolean_condition
        else:
            variable = self.allocation_conditions.next_variable
            self.allocation_conditions.next_variable += 1
            condition = self.allocation_conditions.node(variable, 0, 1)
            self.facts.set_symbol(key, replace(fact, boolean_condition=condition))
        return condition if positive else self.allocation_conditions.combine('xor', condition, 1)

    def _condition_effect_state(self, flow, condition):
        # Collapse alternative paths in the shared condition graph before the
        # next split; do not enumerate combinations of sequential predicates.
        reachable = 0
        for path in flow.paths:
            reachable = self.allocation_conditions.combine('or', reachable, path)
        active = self.allocation_conditions.combine('and', reachable, condition)
        flow.paths = frozenset({active}) if active else frozenset()
        flow.scalar_cases = {key: restricted for key, values in flow.scalar_cases.items()
                             if (restricted := {value: guard for value, prior in values.items()
                                                if (guard := self.allocation_conditions.combine('and', prior, active))})}
        for mapping in (flow.aliases, flow.current_aliases):
            for key, values in list(mapping.items()):
                mapping[key] = self._origin_set(
                    (origin, exact) for value, exact in values
                    for origin in (self._condition_allocations((value,), condition)
                                   if isinstance(value, AllocationRef) else (value,)))
        flow.deleted = {origin for value in flow.deleted
                        for origin in (self._condition_allocations((value,), condition)
                                       if isinstance(value, AllocationRef) else (value,))}
        for key, values in list(flow.places.items()):
            if values is not None:
                flow.places[key] = frozenset(origin for value in values
                    for origin in (self._condition_allocations((value,), condition)
                                   if isinstance(value, AllocationRef) else (value,)))
        return bool(flow.paths)

    def _loop_effects(self, loop: ASTNode):
        """Separate effects reaching a body backedge from matching loop exits."""
        origins = {key: frozenset((origin, True) for origin in self._condition_allocations(fact.allocations))
                   for key, fact in self.facts.by_symbol.items()}
        results = {}
        self._parameter_effect_summary(loop, origins, loop_results=results)
        back, exit_state = results["back"], results["exit"]
        deletions = []
        for state in (back, exit_state):
            deleted = dict(state.places)
            for origin in state.deleted:
                if isinstance(origin, AllocationRef):
                    deleted[origin] = frozenset({origin})
            deletions.append(deleted)
        current = []
        initial = self.allocation_graph.union(origin.root for values in origins.values()
                                              for origin, exact in values if isinstance(origin, AllocationRef))
        for state in (back, exit_state):
            projected = {}
            for key in state.current_live & state.written if state.replaced and not state.replacement_escaped else ():
                if (key not in self.facts.by_symbol or "." in key or key in self.file_variables
                        or key in self.borrowed_keys or self._slot_moved(key)
                        or not self.facts.symbol(key).allocations or self.facts.symbol(key).selected_allocations
                        or self._allocations_moved(self.facts.symbol(key).allocations | self.facts.symbol(key).selected_allocations)):
                    continue
                values = state.current_aliases.get(key, ())
                if (not values and key not in state.current_nil) or any(not exact or not isinstance(origin, AllocationRef) for origin, exact in values):
                    continue
                projected_values = set()
                for origin, exact in values:
                    active_dead = self.allocation_graph.union(
                        item.root for item in state.deleted if isinstance(item, AllocationRef)
                        and self.allocation_conditions.combine('and', origin.condition, item.condition))
                    unchanged = self.allocation_graph.combine('difference', initial, active_dead)
                    retained = self.allocation_graph.combine('intersection', origin.root, unchanged)
                    changed = self.allocation_graph.combine('difference', origin.root, unchanged)
                    projected_root = self.allocation_graph.union((retained, self.allocation_graph.prefix(("loop_current", id(loop)), changed)))
                    projected_values.add(AllocationRef(projected_root, origin.condition))
                projected[key] = self._condition_allocations(projected_values)
            # A dead current slot must not fall back to its unrelated entry
            # allocation. Other aliases to that entry allocation remain live.
            dead_places = set()
            for key in state.current_dead & state.written if not state.replacement_escaped else ():
                values = state.current_aliases.get(key, ())
                deaths = self._origin_intersection(
                    tuple(origin for origin, exact in values if exact), state.deleted)
                condition = 0
                if values and all(exact and isinstance(origin, AllocationRef) for origin, exact in values):
                    for death in deaths:
                        if isinstance(death, AllocationRef):
                            condition = self.allocation_conditions.combine('or', condition, death.condition)
                dead_places.add(SlotDeath(key, condition) if condition else key)
            current.append((projected, dead_places))
        terminal_reentry = False
        first_back = results.get("first_back")
        if first_back is not None and loop.kind in {NodeKind.WHILE, NodeKind.FOR}:
            condition = loop.condition
            truth = (condition.literal_value if condition is not None and condition.kind == NodeKind.LITERAL
                     and condition.literal_kind == LiteralKind.BOOLEAN else None)
            key = self._key(condition) if condition is not None and condition.kind == NodeKind.IDENTIFIER else None
            type_ = self._type(condition) if condition is not None else None
            boolean_header = (key in self.local_boolean_keys and key not in self.borrowed_keys
                              and key not in self.file_variables and key in self.facts.by_symbol
                              and self.facts.symbol(key).initialized
                              and isinstance(type_, PrimitiveType) and type_.name == "bool")
            if truth is False:
                terminal_reentry = True
            elif truth is True or boolean_header:
                # This prefix cannot register cleanup or reuse a first-trip
                # dereference, bounds or arithmetic approval on a changed state.
                conditions = self.allocation_conditions
                reachable = 0
                for path in first_back.paths:
                    reachable = conditions.combine('or', reachable, path)
                stable_conditions = results.get("stable_conditions", {})
                outcomes = {id(None): (0, reachable, 0)}
                pending = [("visit", loop.body, None)]
                while pending:
                    action, statement, context = pending.pop()
                    if action == "sequence":
                        statements, result = context
                        if not result[1]:
                            outcomes[id(statement)] = result
                            continue
                        child = next(statements, None)
                        if child is None:
                            outcomes[id(statement)] = result
                        else:
                            pending.extend([("sequence_after", statement, (statements, result, child)),
                                            ("visit", child, None)])
                        continue
                    if action == "sequence_after":
                        statements, result, child = context
                        following = outcomes[id(child)]
                        result = (conditions.combine('or', result[0], conditions.combine('and', result[1], following[0])),
                                  conditions.combine('and', result[1], following[1]),
                                  conditions.combine('or', result[2], conditions.combine('and', result[1], following[2])))
                        pending.append(("sequence", statement, (statements, result)))
                        continue
                    if action == "branches":
                        children, unknown = context
                        result = [0, 0, unknown]
                        for child, mask in children:
                            for index, region in enumerate(outcomes[id(child)]):
                                result[index] = conditions.combine('or', result[index], conditions.combine('and', mask, region))
                        outcomes[id(statement)] = tuple(result)
                        continue
                    if id(statement) in outcomes:
                        continue
                    if statement.kind == NodeKind.BLOCK:
                        pending.append(("sequence", statement, (iter(statement.statements or []), (0, reachable, 0))))
                    elif statement.kind == NodeKind.IF_STMT:
                        condition = statement.condition
                        branch = self._effect_scalar_condition(condition, first_back.scalar_values)
                        unknown = 0
                        if branch is not None:
                            masks = (reachable, 0) if branch else (0, reachable)
                        elif (condition.kind == NodeKind.BINARY and condition.operator in
                              {BinaryOp.EQ, BinaryOp.NE, BinaryOp.LT, BinaryOp.LE, BinaryOp.GT, BinaryOp.GE}):
                            left = self._effect_scalar_cases(condition.left, first_back.scalar_cases, reachable)
                            right = self._effect_scalar_cases(condition.right, first_back.scalar_cases, reachable)
                            yes, no = 0, 0
                            for first, left_guard in left.items():
                                for second, right_guard in right.items():
                                    region = conditions.combine('and', left_guard, right_guard)
                                    truth = {BinaryOp.EQ: first == second, BinaryOp.NE: first != second,
                                             BinaryOp.LT: first < second, BinaryOp.LE: first <= second,
                                             BinaryOp.GT: first > second, BinaryOp.GE: first >= second}[condition.operator]
                                    if truth:
                                        yes = conditions.combine('or', yes, region)
                                    else:
                                        no = conditions.combine('or', no, region)
                            masks = (yes, no)
                            unknown = conditions.combine('and', reachable, conditions.combine('xor', conditions.combine('or', yes, no), 1))
                        else:
                            key = self._key(condition) if condition.kind == NodeKind.IDENTIFIER else None
                            type_ = self._type(condition)
                            pure_boolean = (key in self.local_boolean_keys and key not in self.borrowed_keys
                                            and key not in self.file_variables and key in self.facts.by_symbol
                                            and self.facts.symbol(key).initialized
                                            and isinstance(type_, PrimitiveType) and type_.name == "bool")
                            if not pure_boolean:
                                outcomes[id(statement)] = (0, 0, reachable)
                                continue
                            predicate = stable_conditions.get(id(condition))
                            masks = ((reachable, reachable) if predicate is None else
                                     (conditions.combine('and', reachable, predicate),
                                      conditions.combine('and', reachable, conditions.combine('xor', predicate, 1))))
                        children = ((statement.then_stmt, masks[0]), (statement.else_stmt, masks[1]))
                        pending.append(("branches", statement, (children, unknown)))
                        pending.extend(("visit", child, None) for child, mask in reversed(children))
                    elif statement.kind == NodeKind.BREAK and statement.label in {None, loop.label}:
                        outcomes[id(statement)] = (reachable, 0, 0)
                    else:
                        outcomes[id(statement)] = (0, 0, reachable)
                terminal, continuing, unsupported = outcomes[id(loop.body)]
                terminal_reentry = (bool(reachable)
                                    and not conditions.combine('and', reachable, conditions.combine('xor', terminal, 1))
                                    and not conditions.combine('and', reachable, conditions.combine('or', continuing, unsupported)))
        return (back.written, deletions[0], exit_state.written, deletions[1], results["has_break"], back.counter_delta,
                current[0], current[1], terminal_reentry)

    def _apply_loop_deletions(self, deleted: dict[str | AllocationRef, Optional[frozenset[str | AllocationRef]]]) -> None:
        for key, allocations in deleted.items():
            if allocations is None:
                self._delete_place(key)
            else:
                self._mark_moved_slot(key, allocations)
                self._move_allocations(allocations)

        # Nil facts describe the slot, not an exemption from allocation death.
        for key in self.readonly_scalar_reference_keys:
            fact = self.facts.symbol(key)
            if (self._slot_moved(key)
                    or self._allocations_moved(fact.allocations | fact.selected_allocations)):
                self.facts.set_symbol(key, replace(fact, non_nil=False, maybe_nil=True))

    def _invalidate_length_relations(self, key: str) -> None:
        if key not in self.length_targets:
            return
        for other, fact in list(self.facts.by_symbol.items()):
            if fact.upper_length_of == key:
                self.facts.set_symbol(other, replace(fact, upper_length_of=None))

    def _forget_names(self, keys: set[str], preserve_non_nil: bool = False) -> None:
        affected = set(keys)
        for name in self.facts.by_symbol:
            if any(name.startswith(key + ".") for key in keys):
                affected.add(name)
        for key in affected:
            self._invalidate_length_relations(key)
            # A key with no entry is already unknown: a local the loop
            # declares later, or a file-scope variable.
            if ".[" in key:
                self.facts.by_symbol.pop(key, None)
                self._clear_moved_slot(key)
            elif key in self.facts.by_symbol:
                fact = self.facts.symbol(key)
                retained = (preserve_non_nil and key in self.readonly_scalar_reference_keys
                            and fact.initialized and fact.non_nil and not fact.maybe_nil
                            and not self._slot_moved(key)
                            and not self._allocations_moved(fact.allocations | fact.selected_allocations))
                forgotten = replace(self._default_fact_for_type(self.symbol_types.get(key)),
                                    allocations=fact.allocations, selected_allocations=fact.selected_allocations)
                if retained:
                    forgotten = replace(forgotten, non_nil=True, maybe_nil=False)
                self.facts.set_symbol(key, forgotten)

    def _forget_array_aliases(self) -> None:
        # A loop can replace cells without rebinding scalar references copied
        # from them. Keep those scalar origins for the ordinary loop effects.
        for key, fact in list(self.facts.by_symbol.items()):
            if ".[" in key:
                self.facts.by_symbol.pop(key)
                self._clear_moved_slot(key)

    def _join_lifetime_states(self, left, left_moved, right, right_moved, condition=None):
        if condition is None:
            variable = self.allocation_conditions.next_variable
            self.allocation_conditions.next_variable += 1
            condition = self.allocation_conditions.node(variable, 0, 1)
        branches = (condition, self.allocation_conditions.combine('xor', condition, 1))
        states = []
        moved = set()
        for facts, deaths, condition in zip((left, right), (left_moved, right_moved), branches):
            states.append({key: replace(fact,
                allocations=self._condition_allocations(fact.allocations, condition),
                selected_allocations=self._condition_allocations(fact.selected_allocations, condition))
                for key, fact in facts.items()})
            moved.update(item for item in deaths if not isinstance(item, (AllocationRef, SlotDeath)))
            for item in deaths:
                if isinstance(item, SlotDeath):
                    active = self.allocation_conditions.combine('and', item.condition, condition)
                    if active:
                        moved.add(SlotDeath(item.key, active))
            moved.update(self._condition_allocations((item for item in deaths if isinstance(item, AllocationRef)), condition))
        return self._join_facts(*states, retain_exact=True), self._normalize_slot_deaths(moved)

    def _join_facts(self, left: dict[str, ValueFact], right: dict[str, ValueFact], *, retain_exact: bool = False) -> dict[str, ValueFact]:
        joined = {}
        for name in left.keys() | right.keys():
            a, b = left.get(name, ValueFact()), right.get(name, ValueFact())
            # Only paired states with represented identities on both paths
            # retain literal slots. Missing facts can mean prior invalidation.
            represented = (retain_exact and name in left and name in right
                           and bool(a.allocations or a.selected_allocations)
                           and bool(b.allocations or b.selected_allocations))
            if ".[" in name and not represented:
                continue
            if a.exact_array_alias and not represented:
                a = replace(a, allocations=frozenset(), selected_allocations=frozenset(), exact_array_alias=False)
            if b.exact_array_alias and not represented:
                b = replace(b, allocations=frozenset(), selected_allocations=frozenset(), exact_array_alias=False)
            if a is b:
                joined[name] = a
                continue
            interval = None
            if a.interval and b.interval:
                lo = min(a.interval.lower, b.interval.lower) if a.interval.lower is not None and b.interval.lower is not None else None
                hi = max(a.interval.upper, b.interval.upper) if a.interval.upper is not None and b.interval.upper is not None else None
                interval = IntegerInterval(lo, hi)
            joined[name] = ValueFact(boolean=a.boolean if a.boolean == b.boolean else None,
                                     boolean_condition=a.boolean_condition if a.boolean_condition == b.boolean_condition else None,
                                     interval=interval, nonzero=a.nonzero and b.nonzero,
                                     known_length=a.known_length if a.known_length == b.known_length else None,
                                     upper_length_of=a.upper_length_of if a.upper_length_of == b.upper_length_of else None,
                                     non_nil=a.non_nil and b.non_nil, maybe_nil=a.maybe_nil or b.maybe_nil,
                                     initialized=a.initialized and b.initialized, moved=a.moved or b.moved,
                                     exact_array_alias=represented and (a.exact_array_alias or b.exact_array_alias),
                                     allocations=self._condition_allocations(a.allocations | b.allocations),
                                     selected_allocations=self._condition_allocations(a.selected_allocations | b.selected_allocations))
        return joined

    def _place_key(self, node: Optional[ASTNode], *, exact_indices: bool = False,
                   current_indices: bool = False) -> Optional[str]:
        fields = []
        while node is not None and node.kind in {NodeKind.FIELD_ACCESS, NodeKind.INDEX}:
            index = None
            if node.kind == NodeKind.INDEX:
                array_type = self._type(node.object)
                if not exact_indices or not isinstance(array_type, ArrayType):
                    return None
                index = self._int_literal(node.index)
                if index is None and current_indices and node.index.kind == NodeKind.IDENTIFIER:
                    index_key = self._key(node.index)
                    interval = self.facts.symbol(index_key).interval
                    if (index_key in self.local_index_keys and index_key not in self.borrowed_keys
                            and interval is not None and interval.lower is not None
                            and interval.lower == interval.upper and array_type.size is not None
                            and 0 <= interval.lower < array_type.size):
                        index = interval.lower
                if index is None:
                    return None
            fields.append((node, index))
            node = node.object
        if node is None or node.kind != NodeKind.IDENTIFIER:
            return None
        key = self._key(node)
        for access, index in reversed(fields):
            if access.kind == NodeKind.INDEX and key in self.escaped_arrays:
                return None
            if isinstance(self._type(access.object), ReferenceType):
                allocations = self.facts.symbol(key).allocations
                if self._allocation_count(allocations) == 1:
                    key = self._allocation_place(allocations)
            key += (".[" + str(index) + "]"
                    if access.kind == NodeKind.INDEX else "." + access.field)
        return key

    def _store_value(self, key: str, value: Optional[ASTNode], fact: ValueFact) -> None:
        # Aggregate copies retain referent identities, with independent slot cells.
        children = {}
        pending = [(key, value)]
        while pending:
            prefix, current = pending.pop()
            source_key = self._place_key(current, exact_indices=True, current_indices=True)
            if source_key:
                children.update({prefix + name[len(source_key):]: item
                                 for name, item in self.facts.by_symbol.items()
                                 if name.startswith(source_key + ".") and prefix not in self.escaped_arrays})
            if current is not None and current.kind == NodeKind.ARRAY_INIT and prefix not in self.escaped_arrays:
                for index, element in enumerate(current.elements or []):
                    child = prefix + ".[" + str(index) + "]"
                    element_fact = self.facts.node(element)
                    if isinstance(self._type(element), ReferenceType):
                        children[child] = element_fact
                    else:
                        pending.append((child, element))
            if current is not None and current.kind == NodeKind.STRUCT_INIT:
                for member in current.field_inits or []:
                    if member.name is None:
                        continue
                    child = prefix + "." + member.name
                    member_fact = self.facts.node(member.value)
                    children[child] = member_fact if isinstance(self._type(member.value), ReferenceType) or member_fact.maybe_nil else ValueFact()
                    pending.append((child, member.value))
        for name in list(self.facts.by_symbol):
            if name.startswith(key + "."):
                del self.facts.by_symbol[name]
                self._clear_moved_slot(name)
        if "." in key and not isinstance(self._type(value), ReferenceType) and not fact.maybe_nil:
            fact = ValueFact()
        previous = self.facts.symbol(key)
        previous_ids = previous.allocations | previous.selected_allocations
        self.facts.set_symbol(key, fact)
        self.facts.by_symbol.update(children)
        self._clear_moved_slot(key)
        # Only heap-field stores share storage with selected binding paths.
        # Independent by-value struct copies that hold the same reference keep
        # separate field slots and must not be rewritten.
        field = key.rsplit(".", 1)[-1] if "." in key else None
        if (key.startswith("@allocation:") and field and previous_ids
                and previous_ids != (fact.allocations | fact.selected_allocations)):
            suffix = "." + field
            for name, existing in list(self.facts.by_symbol.items()):
                if name == key or not name.endswith(suffix) or name.startswith("@allocation:"):
                    continue
                held = existing.allocations | existing.selected_allocations
                if not (held & previous_ids):
                    continue
                self.facts.set_symbol(
                    name,
                    replace(
                        existing,
                        non_nil=fact.non_nil,
                        maybe_nil=fact.maybe_nil or not fact.non_nil,
                        allocations=fact.allocations,
                        selected_allocations=fact.selected_allocations,
                    ),
                )

    def _slot_moved(self, key, moved=None):
        moved = self.moved_symbols if moved is None else moved
        return key in moved or any(
            isinstance(item, SlotDeath) and item.key == key and item.condition
            for item in moved)

    def _clear_moved_slot(self, key, moved=None):
        moved = self.moved_symbols if moved is None else moved
        moved.difference_update(item for item in tuple(moved)
                                if item == key or isinstance(item, SlotDeath) and item.key == key)

    def _normalize_slot_deaths(self, moved):
        conditions = {}
        result = set()
        for item in moved:
            if isinstance(item, SlotDeath):
                conditions[item.key] = self.allocation_conditions.combine(
                    'or', conditions.get(item.key, 0), item.condition)
            else:
                result.add(item)
        result.update(SlotDeath(key, condition) for key, condition in conditions.items() if condition)
        return result

    def _mark_moved_slot(self, key, allocations, moved=None):
        moved = self.moved_symbols if moved is None else moved
        if not isinstance(key, str):
            moved.add(key)
            return
        condition = 0
        for origin in self._condition_allocations(allocations):
            condition = self.allocation_conditions.combine('or', condition, origin.condition)
        moved.add(SlotDeath(key, condition if allocations else 1))
        normalized = self._normalize_slot_deaths(moved)
        moved.clear()
        moved.update(normalized)

    def _restrict_lifetime_state(self, condition):
        self.facts.by_symbol = {key: replace(fact,
            allocations=self._condition_allocations(fact.allocations, condition),
            selected_allocations=self._condition_allocations(fact.selected_allocations, condition))
            for key, fact in self.facts.by_symbol.items()}
        moved = {item for item in self.moved_symbols if not isinstance(item, (AllocationRef, SlotDeath))}
        moved.update(self._condition_allocations(
            (item for item in self.moved_symbols if isinstance(item, AllocationRef)), condition))
        for item in self.moved_symbols:
            if isinstance(item, SlotDeath):
                active = self.allocation_conditions.combine('and', item.condition, condition)
                if active:
                    moved.add(SlotDeath(item.key, active))
        self.moved_symbols = self._normalize_slot_deaths(moved)

    def _delete_place(self, key: str) -> None:
        fact = self.facts.symbol(key)
        self._move_allocations(fact.allocations)
        self._mark_moved_slot(key, self.facts.symbol(key).allocations)

    def _check_reference_alive(self, node: ASTNode, fact: ValueFact, key: Optional[str]) -> None:
        if self._slot_moved(key) or self._allocations_moved(fact.allocations | fact.selected_allocations):
            name = node.name if node.kind == NodeKind.IDENTIFIER else node.field if node.kind == NodeKind.FIELD_ACCESS else "array element"
            self._error_moved_symbol(node, name, "moved/deleted values cannot be read")

    def _check_function_initialized(self, node: ASTNode, fact: ValueFact, key: Optional[str]) -> None:
        if not isinstance(self._type(node), FunctionType):
            return
        if fact.initialized is not False:
            return
        name = node.name if node.kind == NodeKind.IDENTIFIER else key or "<function>"
        obligation = self._obligation(
            ObligationKind.INITIALIZED,
            node,
            "initialized",
            self._type(node),
            "function value must be assigned before use",
            None,
        )
        self._error(obligation, f"Function value '{name}' may be used before assignment",
                    "Assign a function value before calling or copying it")

    def _visit_stmt(self, node: ASTNode) -> None:
        work = [self._statement_steps(node)]
        error = None
        while work:
            try:
                if error is None:
                    child = next(work[-1])
                else:
                    pending_error = error
                    error = None
                    child = work[-1].throw(pending_error)
            except StopIteration:
                work.pop()
            except BaseException as raised:
                work.pop()
                if not work:
                    raise
                error = raised
            else:
                work.append(self._statement_steps(child))

    def _statement_steps(self, node: ASTNode):
        if node.kind != NodeKind.BLOCK and node.span is not None:
            self.current_stmt_span = node.span
        if node.kind == NodeKind.BLOCK:
            statements = node.statements or []
            self.frames.append(ExitFrame())
            for stmt in statements:
                yield stmt
            frame = self.frames.pop()
            # A deferred statement runs when the block ends, so it is proven
            # against the state there and its writes and deletes reach the
            # statements after the block. A block that ends in `ret`, `break`
            # or `continue` proved its defers at that exit.
            if frame.defers and statements[-1].kind not in EXIT_KINDS:
                floor = self.defer_floor
                self.defer_floor = len(self.frames)
                for deferred in reversed(frame.defers):
                    yield deferred
                self.defer_floor = floor
            for key in self.scope_keys.get(id(node), ()):
                self.facts.by_symbol.pop(key, None)
                self._clear_moved_slot(key)
        elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
            if node.value:
                fact = self._visit_expr(node.value)
            else:
                fact = self._default_fact_for_type(self._type(node))
                if isinstance(self._type(node), FunctionType):
                    # No callable zero value: proved-uninitialized until assigned.
                    fact = replace(fact, initialized=False)
            if node.name:
                key = self._key(node)
                self._invalidate_length_relations(key)
                declared_type = self._type(node)
                value_type = self._type(node.value)
                if ((id(node), node.name) in self.keys and node.value is not None
                        and isinstance(declared_type, PrimitiveType)
                        and (declared_type.is_numeric() or declared_type.name in {"bool", "char"})
                        and isinstance(value_type, PrimitiveType)
                        and (value_type.is_numeric() or value_type.name in {"bool", "char"})):
                    # A typed scalar local has no field or element descendants,
                    # even when its declaration is revisited by loop analysis.
                    self.facts.set_symbol(key, fact)
                else:
                    self._store_value(key, node.value, fact)
                self.symbol_types[key] = self._type(node) or self._type(node.value)
                self._clear_moved_slot(key)
        elif node.kind == NodeKind.ASSIGNMENT:
            rhs = self._visit_expr(node.value) if node.value else ValueFact()
            if node.target:
                # Plain indexed assignment overwrites the slot; do not prove the
                # old element alive. Compound forms still read the old value.
                if node.target.kind == NodeKind.IDENTIFIER and not getattr(node, "implicit_deref_target", False):
                    target_fact = self.facts.symbol(self._key(node.target))
                elif node.target.kind == NodeKind.FIELD_ACCESS:
                    target_fact = self._visit_expr(node.target.object)
                elif node.target.kind == NodeKind.INDEX and node.operator == AssignOp.ASSIGN:
                    # Prove bounds without reading the old element identity.
                    target_fact = self._visit_expr(node.target.object)
                    idx_fact = self._visit_expr(node.target.index)
                    self._prove_index(node.target, target_fact, idx_fact)
                else:
                    target_fact = self._visit_expr(node.target)
                if getattr(node, "implicit_deref_target", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        target_fact,
                        self._type(node.target),
                        "reference must be proven non-nil before assignment through it",
                        node.target,
                    )
                if node.target.kind == NodeKind.IDENTIFIER and node.target.name:
                    if node.operator != AssignOp.ASSIGN:
                        result = self._default_fact_for_type(self._type(node.target))
                        operations = {AssignOp.ADD_ASSIGN: IntegerInterval.add, AssignOp.SUB_ASSIGN: IntegerInterval.sub, AssignOp.MUL_ASSIGN: IntegerInterval.mul}
                        operation = operations.get(node.operator)
                        if operation:
                            nonwrap = node.operator.name.lower() + "_nonwrap"
                            interval = operation(target_fact.interval, rhs.interval) if target_fact.interval and rhs.interval else None
                            if self._range_fits(interval, self._type(node.target)):
                                if (id(node), nonwrap) not in self.refused_nonwrap:
                                    obligation = self._obligation(
                                        ObligationKind.INTEGER_OVERFLOW,
                                        node,
                                        nonwrap,
                                        self._type(node.target),
                                        "compound assignment result must fit the target type range",
                                        None,
                                    )
                                    self._prove(obligation, "result interval fits the target type range")
                                result = ValueFact(interval=interval, nonzero=interval.is_nonzero())
                            else:
                                self._refuse_nonwrap(node, nonwrap)
                        rhs = result
                    if not getattr(node, "implicit_deref_target", False):
                        key = self._key(node.target)
                        self._invalidate_length_relations(key)
                        self._store_value(key, node.value, rhs)
                elif node.target.kind == NodeKind.FIELD_ACCESS:
                    if node.operator != AssignOp.ASSIGN:
                        self._visit_expr(node.target)
                    if getattr(node.target, "implicit_deref_object", False):
                        self._prove_ref_non_nil_for_node(
                            node.target, target_fact, self._type(node.target.object),
                            "reference must be proven non-nil before field assignment", node.target.object)
                    key = self._place_key(node.target, exact_indices=True, current_indices=True)
                    if key:
                        self._store_value(key, node.value, rhs)
                    # Uncertain holders: each concrete candidate may keep its old
                    # field value or receive the store. Join; do not overwrite all.
                    object_fact = self.facts.node(node.target.object)
                    if (isinstance(self._type(node.target.object), ReferenceType)
                            and self._allocation_count(object_fact.allocations) > 1
                            and node.target.field):
                        for prefix in self._allocation_prefixes(object_fact.allocations):
                            place = prefix + "." + node.target.field
                            old = self.facts.symbol(place)
                            joined = self._join_facts({"value": old}, {"value": rhs})["value"]
                            if isinstance(self._type(node.value), ReferenceType) or joined.maybe_nil:
                                self.facts.set_symbol(place, joined)
                            else:
                                self.facts.set_symbol(place, ValueFact())
                            self._clear_moved_slot(place)
                elif node.target.kind == NodeKind.INDEX and node.operator == AssignOp.ASSIGN:
                    # Plain ASSIGN already visited object/index above.
                    key = self._place_key(node.target, exact_indices=True, current_indices=True)
                    if key:
                        self._store_value(key, node.value, rhs)
                    else:
                        # Dynamic index: every tracked element may be the target.
                        # Join; do not overwrite-all or drop exact element facts.
                        accesses = [node.target]
                        container = node.target.object
                        base = self._place_key(container, exact_indices=True, current_indices=True)
                        while base is None and container.kind in {NodeKind.INDEX, NodeKind.FIELD_ACCESS}:
                            accesses.append(container)
                            container = container.object
                            base = self._place_key(container, exact_indices=True, current_indices=True)
                        prefixes = {base} if base else set()
                        for access in reversed(accesses):
                            next_prefixes = set()
                            for prefix in prefixes:
                                if isinstance(self._type(access.object), ReferenceType):
                                    allocations = self.facts.symbol(prefix).allocations
                                    if self._allocation_count(allocations) == 1:
                                        prefix = self._allocation_place(allocations)
                                if access.kind == NodeKind.FIELD_ACCESS:
                                    next_prefixes.add(prefix + "." + access.field)
                                elif self._int_literal(access.index) is not None:
                                    next_prefixes.add(prefix + ".[" + str(self._int_literal(access.index)) + "]")
                                else:
                                    for name in self.facts.by_symbol:
                                        if name.startswith(prefix + ".["):
                                            cell = name[len(prefix) + 1:].split(".", 1)[0]
                                            next_prefixes.add(prefix + "." + cell)
                            prefixes = next_prefixes
                        for name in list(self.facts.by_symbol):
                            if not any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes):
                                continue
                            self._invalidate_length_relations(name)
                            old = self.facts.symbol(name)
                            joined = self._join_facts({"value": old}, {"value": rhs})["value"]
                            if isinstance(self._type(node.value), ReferenceType) or rhs.maybe_nil:
                                self.facts.set_symbol(name, joined)
                            else:
                                self.facts.set_symbol(name, ValueFact(maybe_nil=True))
                            self._clear_moved_slot(name)
                elif node.target.kind == NodeKind.INDEX:
                    if node.operator != AssignOp.ASSIGN:
                        self._visit_expr(node.target)
            if node.operator in {AssignOp.DIV_ASSIGN, AssignOp.MOD_ASSIGN} and node.value:
                self._prove_nonzero_divisor(node, node.value, node.operator.name.lower())
        elif node.kind == NodeKind.EXPRESSION_STMT and node.expression:
            self._visit_expr(node.expression)
        elif node.kind in EXIT_KINDS:
            if node.kind == NodeKind.RETURN and node.value:
                self._visit_expr(node.value)
            # Frames this exit leaves, innermost first: every frame for `ret`,
            # the frames above the target loop for `break` and `continue`.
            pending: list[ASTNode] = []
            target: Optional[ExitFrame] = None
            for index in range(len(self.frames) - 1, self.defer_floor - 1, -1):
                frame = self.frames[index]
                if node.kind != NodeKind.RETURN and frame.loop is not None and node.label in {None, frame.loop.label}:
                    target = frame
                    break
                pending.extend(reversed(frame.defers))
            feeds_update = node.kind == NodeKind.CONTINUE and target is not None and target.loop.update is not None
            if pending or feeds_update:
                # The defers of those frames run here, last registered first.
                # Statements after the exit keep the state
                # from before it, so a `ret` in one match arm does not apply
                # its defers to the state after the match.
                saved = self.facts.copy_symbols()
                moved = set(self.moved_symbols)
                floor = self.defer_floor
                self.defer_floor = len(self.frames)
                for deferred in pending:
                    yield deferred
                self.defer_floor = floor
                if feeds_update:
                    target.continues.append((self.facts.by_symbol, self.moved_symbols))
                self.facts.restore_symbols(saved)
                self.moved_symbols = moved
        elif node.kind == NodeKind.IF_STMT:
            self._visit_expr(node.condition)
            predicate = self._stable_boolean_condition(node.condition)
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if predicate is not None:
                self._restrict_lifetime_state(predicate)
            if node.then_stmt:
                yield node.then_stmt
            then_state = self.facts.copy_symbols()
            then_moved = set(self.moved_symbols)
            self.facts.restore_symbols(dict(saved))
            self.moved_symbols = set(moved)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            if predicate is not None:
                self._restrict_lifetime_state(self.allocation_conditions.combine('xor', predicate, 1))
            if node.else_stmt:
                yield node.else_stmt
            if node.then_stmt and self._always_returns(node.then_stmt):
                pass  # Only the else path reaches the following statement.
            elif node.else_stmt and self._always_returns(node.else_stmt):
                self.facts.restore_symbols(then_state)
                self.moved_symbols = then_moved
            else:
                self.facts.by_symbol, self.moved_symbols = self._join_lifetime_states(then_state, then_moved, self.facts.by_symbol, self.moved_symbols, predicate)
        elif node.kind in {NodeKind.WHILE, NodeKind.FOR}:
            self._forget_array_aliases()
            self.frames.append(ExitFrame(node))
            if node.init:
                yield node.init
            written, deleted, exit_written, exit_deleted, has_break, back_delta, back_live, exit_live, terminal_reentry = self._loop_effects(node)
            # A counter increment on every backedge can establish at most one
            # active iteration. Integer wrapping must not re-enable the guard.
            single_iteration = False
            condition = node.condition
            if (condition and condition.kind == NodeKind.BINARY and condition.operator in {BinaryOp.LT, BinaryOp.LE}
                    and condition.left.kind == NodeKind.IDENTIFIER
                    and condition.right.kind == NodeKind.LITERAL
                    and condition.right.literal_kind == LiteralKind.INTEGER):
                counter = self._key(condition.left)
                interval = self.facts.symbol(counter).interval
                pending = [(node.body, False), (node.update, False)]
                inspected_callees = set()
                updates = []
                safe_counter = counter not in self.file_variables and counter not in self.borrowed_keys
                while pending and safe_counter:
                    statement, nested = pending.pop()
                    if statement is None or statement.kind == NodeKind.FUNCTION:
                        continue
                    if statement.kind == NodeKind.ASSIGNMENT and self._place_key(statement.target) == counter:
                        updates.append((statement, nested))
                    elif statement.kind == NodeKind.CALL and not getattr(statement, "stdlib_canonical", None):
                        callee = statement.function
                        name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
                        declaration = self.exact_effect_bodies.get(name)
                        if declaration is None or declaration.body is None:
                            safe_counter = False
                        elif name not in inspected_callees:
                            inspected_callees.add(name)
                            pending.append((declaration.body, True))
                    for value in vars(statement).values():
                        if isinstance(value, ASTNode):
                            pending.append((value, nested or statement.kind in LOOP_KINDS))
                        elif isinstance(value, list):
                            pending.extend((child, nested or statement.kind in LOOP_KINDS) for child in value if isinstance(child, ASTNode))
                if (safe_counter and back_delta is not None and updates
                        and all(not nested and update.operator == AssignOp.ADD_ASSIGN
                                and update.target.kind == NodeKind.IDENTIFIER
                                and update.value.kind == NodeKind.LITERAL
                                and update.value.literal_kind == LiteralKind.INTEGER
                                and update.value.literal_value > 0 for update, nested in updates)
                        and interval is not None and interval.lower is not None and interval.upper is not None):
                    bound = condition.right.literal_value + (condition.operator == BinaryOp.LE)
                    minimum_step, maximum_step = back_delta
                    active_upper = min(interval.upper, bound - 1)
                    single_iteration = (minimum_step > 0 and interval.lower < bound <= interval.lower + minimum_step
                                        and self._range_fits(IntegerInterval(interval.lower, active_upper + maximum_step), self._type(condition.left)))
            if not single_iteration and not terminal_reentry:
                self._apply_loop_deletions(deleted)
                self._forget_names(written, preserve_non_nil=True)
                for key, allocations in back_live[0].items():
                    self.facts.set_symbol(key, ValueFact(maybe_nil=True, allocations=allocations))
                    self._clear_moved_slot(key)
                self.moved_symbols.update(back_live[1])
            head = self.facts.copy_symbols()
            head_moved = set(self.moved_symbols)
            if node.condition:
                self._visit_expr(node.condition)
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if node.body:
                yield node.body
            frame = self.frames.pop()
            if node.update:
                for facts, continue_moved in frame.continues:
                    self.facts.by_symbol, self.moved_symbols = self._join_lifetime_states(self.facts.by_symbol, self.moved_symbols, facts, continue_moved)
                yield node.update
            # The loop may run zero times, and a `break` leaves from a state
            # the head state covers, so nothing the body established survives.
            # The false condition holds after the loop only when no `break`
            # can leave with it still true.
            self.facts.restore_symbols(head)
            self.moved_symbols = head_moved
            self._forget_names(exit_written, preserve_non_nil=True)
            self._apply_loop_deletions(exit_deleted)
            for key, allocations in exit_live[0].items():
                self.facts.set_symbol(key, ValueFact(maybe_nil=True, allocations=allocations))
                self._clear_moved_slot(key)
            self.moved_symbols.update(exit_live[1])
            if node.condition and not has_break:
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            for key in self.scope_keys.get(id(node), ()):
                self.facts.by_symbol.pop(key, None)
                self._clear_moved_slot(key)
        elif node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
            self._forget_array_aliases()
            iterable_fact = self._visit_expr(node.iterable)
            self.frames.append(ExitFrame(node))
            written, deleted, exit_written, exit_deleted, _, _, back_live, exit_live, _ = self._loop_effects(node)
            if self._object_length(node.iterable, iterable_fact) != 1:
                self._apply_loop_deletions(deleted)
                self._forget_names(written, preserve_non_nil=True)
                for key, allocations in back_live[0].items():
                    self.facts.set_symbol(key, ValueFact(maybe_nil=True, allocations=allocations))
                    self._clear_moved_slot(key)
                self.moved_symbols.update(back_live[1])
            head = self.facts.copy_symbols()
            head_moved = set(self.moved_symbols)
            if node.index_var:
                length = self._object_length(node.iterable, iterable_fact)
                self.facts.set_symbol(self._key(node, node.index_var), ValueFact(interval=IntegerInterval(0, length - 1 if length is not None else None), nonzero=False))
            if node.iterator:
                iterable_type = self._type(node.iterable)
                element_type = iterable_type.element_type if isinstance(iterable_type, (ArrayType, SliceType)) else None
                self.facts.set_symbol(self._key(node, node.iterator), self._default_fact_for_type(element_type))
            if node.body:
                yield node.body
            self.frames.pop()
            # Same exit rule as `while`: zero iterations are possible.
            self.facts.restore_symbols(head)
            self.moved_symbols = head_moved
            self._forget_names(exit_written, preserve_non_nil=True)
            self._apply_loop_deletions(exit_deleted)
            for key, allocations in exit_live[0].items():
                self.facts.set_symbol(key, ValueFact(maybe_nil=True, allocations=allocations))
                self._clear_moved_slot(key)
            self.moved_symbols.update(exit_live[1])
        elif node.kind == NodeKind.MATCH:
            self._visit_expr(node.expression)
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            joined = dict(saved)  # A non-exhaustive match can execute no arm.
            all_moved = set(moved)
            # A payload capture has its own key and no entry, so it starts
            # unknown whatever an outer variable of the same name holds.
            branches = [case.statements or ([] if case.statement is None else [case.statement]) for case in node.cases or []]
            branches.append(node.else_case or [])
            fallen: Optional[tuple[dict[str, ValueFact], set[str]]] = None
            for statements in branches:
                self.facts.restore_symbols(dict(saved))
                self.moved_symbols = set(moved)
                if fallen is not None:
                    # The arm above ends in `fall`, so this arm also starts
                    # from that arm's end state.
                    self.facts.by_symbol, self.moved_symbols = self._join_lifetime_states(self.facts.by_symbol, self.moved_symbols, *fallen)
                for stmt in statements:
                    yield stmt
                last = statements[-1] if statements else None
                if last is not None and last.kind == NodeKind.BLOCK and last.statements:
                    last = last.statements[-1]
                falls = last is not None and last.kind == NodeKind.FALL
                fallen = (self.facts.by_symbol, self.moved_symbols) if falls else None
                # Falling arms continue in the next arm; terminal arms leave
                # this statement. Neither is an ordinary fallthrough state.
                if not falls and not (last is not None and self._always_returns(last)):
                    joined, all_moved = self._join_lifetime_states(joined, all_moved, self.facts.by_symbol, self.moved_symbols)
            self.facts.restore_symbols(joined)
            self.moved_symbols = all_moved
        elif node.kind == NodeKind.DEFER and node.statement:
            if id(node) in self.block_defers:
                self.frames[-1].defers.append(node.statement)
            else:
                # The only statement of a branch or match arm: that scope ends
                # here, so the deferred statement runs now.
                yield node.statement
        elif node.kind == NodeKind.DEL and node.expression:
            target = node.expression
            if target.kind == NodeKind.IDENTIFIER and self._slot_moved(self._key(target)):
                self._error_moved_symbol(target, target.name, "a value can be deleted only once")
            else:
                self._visit_expr(target)
            self._mark_deleted(target)
        elif node.kind == NodeKind.FUNCTION and node.body:
            # A nested function starts from the file-scope constant facts, like
            # a top-level one, and leaves the enclosing function's state intact.
            saved = self.facts.copy_symbols()
            saved_moved = self.moved_symbols
            saved_frames = self.frames
            saved_floor = self.defer_floor
            saved_escaped_arrays = self.escaped_arrays
            self.escaped_arrays = set()
            self.moved_symbols = set()
            self.frames = []
            self.defer_floor = 0
            self.facts.by_symbol = dict(self.const_facts)
            for param in node.parameters or []:
                if param.name:
                    key = self._key(param)
                    fact = self._fact_from_type_node(param.param_type)
                    if param.param_type and param.param_type.kind == NodeKind.TYPE_POINTER:
                        fact = replace(fact, allocations=frozenset({f"parameter:{key}"}))
                    self.facts.set_symbol(key, fact)
            yield node.body
            self.facts.restore_symbols(saved)
            self.moved_symbols = saved_moved
            self.frames = saved_frames
            self.defer_floor = saved_floor
            self.escaped_arrays = saved_escaped_arrays
        if node.kind in LOOP_KINDS:
            self._forget_array_aliases()

    def _call_origin_fact(self, node: ASTNode, captured, origins, global_values=None) -> ValueFact:
        values = []
        for origin, exact in origins:
            if not exact or origin == -1:
                values.append(ValueFact(maybe_nil=True))
            elif isinstance(origin, AllocationRef):
                root = self.allocation_graph.prefix(("call", id(node)), origin.root)
                for item in list(self.moved_symbols):
                    if isinstance(item, AllocationRef):
                        remaining = self.allocation_graph.combine('difference', item.root, root)
                        if remaining != item.root:
                            self.moved_symbols.remove(item)
                            if remaining:
                                self.moved_symbols.add(AllocationRef(remaining, item.condition))
                values.append(ValueFact(maybe_nil=True, allocations=frozenset({AllocationRef(root, origin.condition)})))
            elif origin in self.global_origins:
                key = self.global_origins[origin]
                values.append(global_values[key] if global_values is not None else self.facts.symbol(key))
            elif isinstance(origin, int) and origin >= 0 and origin < len(captured):
                values.append(captured[origin][0])
        fact = values[0] if values else ValueFact(maybe_nil=True)
        for value in values[1:]:
            fact = self._join_facts({"value": fact}, {"value": value})["value"]
        return fact

    def _visit_expr(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        root = node
        pending = [("visit", node, None)]
        while pending:
            action, node, context = pending.pop()
            if action == "exact_finish":
                name, captured, global_values = context
                if self._exact_call_name(node, captured) == name:
                    self._replay_exact_effects(node, name, captured)
                else:
                    # Argument evaluation can introduce selected identities.
                    # This call gets legacy effects once, with no partial replay.
                    for index, arg in enumerate(node.arguments or []):
                        self._apply_legacy_reference_effects(node, index, arg, captured[index][0])
                    pending.append(("global_effects", node, (name, captured, global_values)))
                continue
            if action == "store_effects":
                name, captured, global_values = context
                # Only deletion-free summaries restore a stored value here.
                # Deleting callees still require the ordered exact replay.
                if not self.function_deletes.get(name, True):
                    for (index, path), origins in self.function_field_stores.get(name, {}).items():
                        if not path or any(origin in {-1, -3} or not exact for origin, exact in origins):
                            continue
                        if index >= len(captured):
                            continue
                        holder, key = captured[index]
                        prefixes = [key] if key else []
                        prefixes.extend(self._allocation_prefixes(holder.allocations))
                        if self._allocation_count(holder.allocations) > 1:
                            continue
                        fact = self._call_origin_fact(node, captured, origins, global_values)
                        for prefix in prefixes:
                            self._store_value(prefix + "." + path, None, replace(fact, maybe_nil=True, non_nil=False))
                continue
            if action == "return_effects":
                name, captured, global_values = context
                if isinstance(self._type(node), ReferenceType):
                    origins, dead = self.function_returns.get(name, (frozenset({(-1, True)}), frozenset()))
                    fact = self._call_origin_fact(node, captured, origins, global_values)
                    selection = self.literal_return_bodies.get(name)
                    if selection is not None:
                        body, refs, bools = selection
                        arguments = node.arguments or []
                        # Syntactic literals cannot change during later actuals.
                        # Reference facts still come from ordered call_arg capture.
                        if all(index < len(arguments) and arguments[index].kind == NodeKind.LITERAL
                               and arguments[index].literal_kind == LiteralKind.BOOLEAN
                               for index in bools.values()):
                            pending_returns = [body]
                            while pending_returns:
                                current = pending_returns.pop()
                                if current is None:
                                    continue
                                if current.kind == NodeKind.BLOCK:
                                    pending_returns.extend(reversed(current.statements or []))
                                elif current.kind == NodeKind.IF_STMT:
                                    condition = current.condition
                                    truth = (condition.literal_value if condition.kind == NodeKind.LITERAL
                                             else arguments[bools[self._key(condition)]].literal_value)
                                    pending_returns.append(current.then_stmt if truth else current.else_stmt)
                                else:
                                    value = current.value
                                    if value.kind == NodeKind.LITERAL:
                                        fact = self._literal_fact(value)
                                    else:
                                        fact = self._call_origin_fact(node, captured,
                                            {(refs[self._key(value)], True)}, global_values)
                                    break
                    for origin in dead:
                        affected = self._call_origin_fact(node, captured, {(origin, True)}, global_values)
                        self._move_allocations(affected.allocations)
                    self.facts.set_node(node, fact)
                continue
            if action == "readonly_requirements":
                name, scalar_captures, captured = context
                engine = self.readonly_requirements
                name = engine.call_targets.get(id(node), name)
                if self._exact_call_name(node, captured) is not None:
                    engine.dispositions.append((id(node), name, "existing exact replay owns requirement"))
                    continue
                if name in engine.index_functions:
                    scalar_captures = list(scalar_captures)
                    for index, arg in enumerate(node.arguments or []):
                        if isinstance(self._type(arg), ReferenceType):
                            fact = captured[index][0]
                            if fact.non_nil:
                                scalar_captures[index] = False
                violation, origin, disposition = engine.evaluate(name, scalar_captures)
                engine.dispositions.append((id(node), name, disposition))
                if violation is None and name in engine.index_functions:
                    obligation = self._obligation(ObligationKind.REF_NON_NIL, node,
                        "index_call_precondition", None,
                        "reference-array access requires a complete caller nil proof", TypeErrorType.CANNOT_DEREFERENCE)
                    self._error(obligation, "reference-array caller requirement is unresolved")
                if violation is True:
                    origin_span = getattr(origin, "span", None)
                    required = ("readonly callee indexed access must remain non-nil"
                                if origin is not None and origin.kind == NodeKind.INDEX
                                else "readonly callee field access must remain non-nil")
                    if origin_span is not None:
                        origin_file = getattr(origin_span, "origin_file", None) or self.current_file
                        origin_name = Path(origin_file).name if origin_file else "<unknown>"
                        required += (
                            f" (callee use in {origin_name} at line {origin_span.start_line}, "
                            f"column {origin_span.start_column})"
                        )
                    obligation = self._obligation(ObligationKind.REF_NON_NIL, node,
                        "readonly_call_precondition", None, required, TypeErrorType.CANNOT_DEREFERENCE)
                    self._error(obligation, "reachable readonly callee read receives nil",
                        "Guard the reference or avoid the callee path that reads it")
                continue
            if action == "captured_boolean_effects":
                for key in self.capture_call_effects.get(id(node), self.mutable_boolean_captures):
                    if key in self.facts.by_symbol:
                        self.facts.set_symbol(key, replace(self.facts.symbol(key), boolean=None, boolean_condition=None))
                continue
            if action == "capture_globals":
                context.update({key: self.facts.symbol(key) for key in self.global_origins.values()})
                continue
            if action == "global_effects":
                name, captured, global_values = context
                stores, deleted, dead_globals = self.function_global_effects.get(name, ({}, frozenset(), frozenset()))
                final_values = {key: self._call_origin_fact(node, captured, origins, global_values)
                                for key, origins in stores.items()}
                affected = [self._call_origin_fact(node, captured, {(origin, True)}, global_values)
                            for origin in deleted]
                fallback = self.function_deleted_globals.get(name, set()) if name is not None else self.file_variables
                for key in fallback:
                    if not self.function_direct_deletes.get(name, False) or key not in self.reference_globals:
                        self._delete_place(key)
                self._forget_names(self.file_variables)
                for key, fact in final_values.items():
                    self._store_value(key, None, replace(fact, non_nil=False, maybe_nil=True))
                for fact in affected:
                    self._move_allocations(fact.allocations)
                for key in self.reference_globals:
                    if key in dead_globals or self._allocations_moved(self.facts.symbol(key).allocations):
                        self._mark_moved_slot(key, self.facts.symbol(key).allocations)
                continue
            if action == "call_start":
                exact_name = self._exact_call_name(node)
                captured = []
                scalar_captures = []
                global_values = {}
                callee = node.function
                name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
                pending.append(("captured_boolean_effects", node, None))
                pending.append(("return_effects", node, (name, captured, global_values)))
                if exact_name:
                    pending.append(("exact_finish", node, (exact_name, captured, global_values)))
                elif node.function and node.function.kind == NodeKind.IDENTIFIER:
                    pending.append(("store_effects", node, (self._key(node.function), captured, global_values)))
                borrowed = getattr(node, "implicit_ref_args", set())
                function_type = self._type(node.function)
                if not exact_name and not getattr(node, "stdlib_canonical", None):
                    pending.append(("global_effects", node, (name, captured, global_values)))
                pending.append(("readonly_requirements", node, (name, scalar_captures, captured)))
                pending.append(("capture_globals", node, global_values))
                for i, arg in reversed(list(enumerate(node.arguments or []))):
                    pending.append(("call_arg", node, (i, arg, borrowed, function_type, exact_name, captured, scalar_captures)))
                    pending.append(("visit", arg, None))
                continue
            if action == "call_arg":
                i, arg, borrowed, function_type, exact_name, captured, scalar_captures = context
                scalar = None
                if arg.kind == NodeKind.LITERAL:
                    if arg.literal_kind == LiteralKind.NIL:
                        scalar = True
                    elif arg.literal_kind in {LiteralKind.BOOLEAN, LiteralKind.INTEGER}:
                        scalar = arg.literal_value
                elif i in borrowed:
                    scalar = False
                elif arg.kind == NodeKind.CALL:
                    engine = self.readonly_requirements
                    if engine.call_targets.get(id(node)) in engine.index_functions:
                        scalar = engine.boolean_results.get(engine.call_targets.get(id(arg)))
                if scalar is None and self.readonly_requirements.call_targets.get(id(node)) in self.readonly_requirements.index_functions:
                    scalar = self.facts.node(arg).boolean
                scalar_captures.append(scalar)
                fact = self.facts.node(arg)
                captured.append((replace(fact, non_nil=True) if i in borrowed else fact, self._place_key(arg) if i in borrowed else None))
                if i in borrowed and isinstance(self._type(arg), ArrayType):
                    container = arg
                    key = self._place_key(container, exact_indices=True, current_indices=True)
                    while key is None and container.kind in {NodeKind.INDEX, NodeKind.FIELD_ACCESS}:
                        container = container.object
                        key = self._place_key(container, exact_indices=True, current_indices=True)
                    if key:
                        self.escaped_arrays.add(key)
                        self._forget_names({name for name in self.facts.by_symbol if name.startswith(key + ".[")})
                if not exact_name:
                    self._apply_legacy_reference_effects(node, i, arg, self.facts.node(arg))
                arg_fact = self.facts.node(arg)
                is_ref_parameter = isinstance(function_type, FunctionType) and i < len(function_type.param_types) and isinstance(function_type.param_types[i], ReferenceType)
                if isinstance(self._type(arg), ReferenceType) and is_ref_parameter:
                    self._prove_ref_non_nil_for_node(node, arg_fact, self._type(arg), "reference argument must be proven non-nil", arg)
                elif i in borrowed and arg.kind == NodeKind.IDENTIFIER:
                    self._invalidate_length_relations(self._key(arg))
                    key = self._key(arg)
                    refreshed = self._default_fact_for_type(self._type(arg))
                    # Ref arguments can overwrite storage, but a function local
                    # that was already assigned does not become unassigned.
                    if isinstance(self._type(arg), FunctionType):
                        refreshed = replace(refreshed, initialized=True)
                    self.facts.set_symbol(key, replace(refreshed,
                                                       allocations=self.facts.symbol(key).allocations,
                                                   selected_allocations=self.facts.symbol(key).selected_allocations))
                continue
            if action == "visit":
                pending.append(("finish", node, None))
                if node.kind == NodeKind.CALL:
                    # Borrow invalidation remains ordered between arguments.
                    # Global and exact body effects follow argument evaluation.
                    pending.append(("call_start", node, None))
                    children = [node.function]
                elif node.kind in {NodeKind.UNARY, NodeKind.ADDRESS_OF}:
                    children = [node.operand]
                elif node.kind == NodeKind.BINARY:
                    children = [node.left, node.right]
                elif node.kind == NodeKind.CAST:
                    children = [node.expression]
                elif node.kind == NodeKind.INDEX:
                    children = [node.object, node.index]
                elif node.kind == NodeKind.SLICE:
                    children = [node.object, node.start, node.end]
                elif node.kind == NodeKind.FIELD_ACCESS:
                    children = [node.object]
                elif node.kind == NodeKind.DEREF:
                    children = [node.pointer]
                elif node.kind == NodeKind.ARRAY_INIT:
                    children = node.elements or []
                elif node.kind == NodeKind.STRUCT_INIT:
                    children = [init.value for init in node.field_inits or []]
                elif node.kind == NodeKind.IF_EXPR:
                    children = [node.condition, node.then_expr, node.else_expr]
                elif node.kind == NodeKind.MATCH_EXPR:
                    children = [node.expression]
                    children.extend(getattr(case, "expression", None) for case in node.cases or [])
                    if isinstance(node.else_case, ASTNode):
                        children.append(node.else_case)
                else:
                    children = []
                pending.extend(("visit", child, None) for child in reversed(children) if child is not None)
                continue
            fact = ValueFact()
            if node.kind == NodeKind.CALL:
                fact = self.facts.node(node)
            elif node.kind == NodeKind.LITERAL:
                fact = self._literal_fact(node)
            elif node.kind == NodeKind.IDENTIFIER:
                key = self._key(node)
                # A value copied before its first condition still shares that
                # version; later assignments and borrows replace the slot fact.
                predicate = self._stable_boolean_condition(node)
                fact = self.facts.symbol(key)
                if key in self.mutable_boolean_captures:
                    # Preserve lifetime correlation without widening readonly
                    # caller literal-value proofs for writable captures.
                    fact = replace(fact, boolean=None, boolean_condition=predicate)
                elif key not in self.local_boolean_keys or key in self.borrowed_keys:
                    fact = replace(fact, boolean=None)
                self._check_reference_alive(node, fact, key)
                self._check_function_initialized(node, fact, key)
            elif node.kind == NodeKind.UNARY:
                operand = self.facts.node(node.operand)
                fact = self._unary_fact(node, operand)
            elif node.kind == NodeKind.BINARY:
                left = self.facts.node(node.left)
                right = self.facts.node(node.right)
                fact = self._binary_fact(node, left, right)
                if node.operator in {BinaryOp.DIV, BinaryOp.MOD} and node.right:
                    self._prove_nonzero_divisor(node, node.right, node.operator.name.lower())
                if node.operator in {BinaryOp.ADD, BinaryOp.SUB, BinaryOp.MUL}:
                    self._prove_integer_overflow(node, fact)
            elif node.kind == NodeKind.CAST:
                source = self.facts.node(node.expression)
                fact = self._cast_fact(node, source)
            elif node.kind == NodeKind.INDEX:
                obj_fact = self.facts.node(node.object)
                idx_fact = self.facts.node(node.index)
                self._prove_index(node, obj_fact, idx_fact)
                key = self._place_key(node, exact_indices=True, current_indices=True)
                if key and isinstance(self._type(node), ReferenceType):
                    saved = self.facts.symbol(key)
                    fact = ValueFact(allocations=saved.allocations, exact_array_alias=bool(saved.allocations))
                    self._check_reference_alive(node, fact, key if key in self.facts.by_symbol else None)
            elif node.kind == NodeKind.SLICE:
                obj_fact = self.facts.node(node.object)
                start_fact = self.facts.node(node.start) if node.start else ValueFact(interval=IntegerInterval.exact(0))
                end_fact = self.facts.node(node.end) if node.end else ValueFact(interval=IntegerInterval.exact(obj_fact.known_length), known_length=obj_fact.known_length) if obj_fact.known_length is not None else ValueFact()
                self._prove_slice(node, obj_fact, start_fact, end_fact)
                fact = self._slice_fact(node, obj_fact, start_fact, end_fact)
                # A mutable view can write backing slots outside this model.
                container = node.object
                key = self._place_key(container, exact_indices=True, current_indices=True)
                while key is None and container.kind in {NodeKind.INDEX, NodeKind.FIELD_ACCESS}:
                    container = container.object
                    key = self._place_key(container, exact_indices=True, current_indices=True)
                if key:
                    self.escaped_arrays.add(key)
                    self._forget_names({name for name in self.facts.by_symbol if name.startswith(key + ".[")})
            elif node.kind == NodeKind.FIELD_ACCESS:
                obj = self.facts.node(node.object)
                if getattr(node, "implicit_deref_object", False):
                    self._prove_ref_non_nil_for_node(
                        node,
                        obj,
                        self._type(node.object),
                        "reference must be proven non-nil before field access through it",
                        node.object,
                    )
                key = self._place_key(node, exact_indices=True, current_indices=True)
                fact = self.facts.symbol(key)
                if key and key not in self.facts.by_symbol and isinstance(self._type(node), ReferenceType):
                    fact = ValueFact(maybe_nil=True, allocations=self._field_allocations(key))
                    self.facts.set_symbol(key, fact)
                alive_key = key
                if (key and isinstance(self._type(node.object), ReferenceType)
                        and isinstance(self._type(node), ReferenceType) and self._allocation_count(obj.allocations) > 1
                        and fact.allocations == self._field_allocations(key)):
                    # Only synthetic selected-field facts follow the candidates.
                    # Explicit stores retain their own identity. Saved aliases
                    # keep these dependencies as they were when captured.
                    holder_root = self._allocation_root(obj.allocations)
                    missing = holder_root
                    identities = set()
                    for prefix in self._allocation_prefixes(obj.allocations):
                        parent = self.allocation_places[prefix]
                        child_key = prefix + "." + node.field
                        child = self.facts.symbol(child_key)
                        if child.allocations or child.selected_allocations:
                            active = 0
                            for owner in self._condition_allocations(obj.allocations):
                                if self.allocation_graph.combine('intersection', owner.root, parent):
                                    active = self.allocation_conditions.combine('or', active, owner.condition)
                            identities.update(self._condition_allocations(child.allocations | child.selected_allocations, active))
                            missing = self.allocation_graph.combine('difference', missing, parent)
                        if self._slot_moved(child_key):
                            alive_key = child_key
                    if missing:
                        for owner in self._condition_allocations(obj.allocations):
                            unknown = self.allocation_graph.combine('intersection', missing, owner.root)
                            if unknown:
                                identities.add(AllocationRef(self.allocation_graph.prefix(('field', node.field), unknown), owner.condition))
                    fact = replace(fact, selected_allocations=frozenset(identities))
                    self.facts.set_symbol(key, fact)
                self._check_reference_alive(node, fact, alive_key)
                object_type = self._type(node.object)
                if node.field == "ptr" and (isinstance(object_type, (ArrayType, SliceType))
                                             or isinstance(object_type, PrimitiveType) and object_type.name == "string"):
                    fact = ValueFact(non_nil=True)
                if node.field == "len" and obj.known_length is not None:
                    fact = ValueFact(interval=IntegerInterval.exact(obj.known_length), known_length=None, nonzero=obj.known_length != 0)
            elif node.kind == NodeKind.ADDRESS_OF:
                fact = ValueFact(non_nil=True, maybe_nil=False)
            elif node.kind == NodeKind.DEREF:
                ptr_fact = self.facts.node(node.pointer)
                self._prove_ref_non_nil(node, ptr_fact)
            elif node.kind == NodeKind.ARRAY_INIT:
                fact = ValueFact(known_length=len(node.elements or []), non_nil=True)
            elif node.kind == NodeKind.MATCH_EXPR:
                branches = [getattr(case, "expression", None) for case in node.cases or []]
                if isinstance(node.else_case, ASTNode):
                    branches.append(node.else_case)
                branch_facts = [self.facts.node(branch) for branch in branches if branch is not None]
                if branch_facts:
                    fact = branch_facts[0]
                    for branch_fact in branch_facts[1:]:
                        fact = self._join_facts({"value": fact}, {"value": branch_fact})["value"]
            elif node.kind == NodeKind.IF_EXPR:
                fact = self._join_facts({"value": self.facts.node(node.then_expr)},
                                        {"value": self.facts.node(node.else_expr)})["value"]
            elif node.kind == NodeKind.NEW_EXPR:
                fact = ValueFact(maybe_nil=True, allocations=frozenset({f"new:{id(node)}"}))
            self.facts.set_node(node, fact)
        return self.facts.node(root)

    def _default_fact_for_type(self, type_: Optional[Type]) -> ValueFact:
        # FunctionType stays initialized=True here: loop forget/for-in/borrow
        # refresh use this helper. Uninitialized locals are marked only at
        # declarations without an initializer.
        if isinstance(type_, PrimitiveType) and type_.name in INTEGER_RANGES:
            lo, hi = INTEGER_RANGES[type_.name]
            return ValueFact(interval=IntegerInterval(lo, hi), nonzero=False)
        if isinstance(type_, ArrayType):
            return ValueFact(known_length=type_.size)
        return ValueFact(maybe_nil=isinstance(type_, ReferenceType))

    def _fact_from_type_node(self, node: Optional[ASTNode]) -> ValueFact:
        if node is None:
            return ValueFact()
        if node.kind == NodeKind.TYPE_POINTER:
            return ValueFact(non_nil=True)
        name = getattr(node, "type_name", None)
        if name in INTEGER_RANGES:
            return ValueFact(interval=IntegerInterval(*INTEGER_RANGES[name]))
        return ValueFact()

    def _literal_fact(self, node: ASTNode) -> ValueFact:
        if node.literal_kind == LiteralKind.BOOLEAN:
            return ValueFact(boolean=node.literal_value)
        if node.literal_kind == LiteralKind.INTEGER and isinstance(node.literal_value, int):
            return ValueFact(interval=IntegerInterval.exact(node.literal_value), nonzero=node.literal_value != 0)
        if node.literal_kind == LiteralKind.FLOAT and isinstance(node.literal_value, (int, float)):
            return ValueFact(nonzero=node.literal_value != 0.0)
        if node.literal_kind == LiteralKind.STRING and isinstance(node.literal_value, str):
            return ValueFact(known_length=len(node.literal_value), non_nil=True)
        if node.literal_kind == LiteralKind.NIL:
            return ValueFact(maybe_nil=True)
        return ValueFact()

    def _unary_fact(self, node: ASTNode, operand: ValueFact) -> ValueFact:
        if node.operator == UnaryOp.NOT and operand.boolean is not None:
            return ValueFact(boolean=not operand.boolean)
        if node.operator == UnaryOp.NEG and operand.interval and operand.interval.lower is not None and operand.interval.upper is not None:
            interval = IntegerInterval(-operand.interval.upper, -operand.interval.lower)
            # `-MIN` wraps to `MIN`, so an interval past the type's maximum
            # says nothing about the result.
            result_type = self._type(node)
            if isinstance(result_type, PrimitiveType) and result_type.name in INTEGER_RANGES and not self._range_fits(interval, result_type):
                return self._default_fact_for_type(result_type)
            return ValueFact(interval=interval, nonzero=interval.is_nonzero())
        return ValueFact()

    def _binary_fact(self, node: ASTNode, left: ValueFact, right: ValueFact) -> ValueFact:
        if not left.interval or not right.interval:
            return ValueFact()
        if node.operator == BinaryOp.ADD:
            interval = left.interval.add(right.interval)
        elif node.operator == BinaryOp.SUB:
            interval = left.interval.sub(right.interval)
        elif node.operator == BinaryOp.MUL:
            interval = left.interval.mul(right.interval)
        elif node.operator in {BinaryOp.DIV, BinaryOp.MOD} and right.interval and right.interval.is_nonzero():
            interval = IntegerInterval()
        else:
            return ValueFact()
        result_type = self._type(node)
        if isinstance(result_type, PrimitiveType) and result_type.name in INTEGER_RANGES and not self._range_fits(interval, result_type):
            return self._default_fact_for_type(result_type)
        return ValueFact(interval=interval, nonzero=interval.is_nonzero())

    def _cast_fact(self, node: ASTNode, source_fact: ValueFact) -> ValueFact:
        source_type = self._type(node.expression)
        target_type = self._type(node) or self._type_from_cast_target(node)
        decision = classify_cast(
            source_type,
            target_type,
            source_nonnegative=bool(source_fact.interval and source_fact.interval.is_nonnegative()),
        ) if source_type is not None and target_type is not None else None
        if (
            decision is not None
            and not decision.allowed
            and isinstance(source_type, PrimitiveType)
            and isinstance(target_type, PrimitiveType)
            and source_type.name in INTEGER_RANGES
            and target_type.name in INTEGER_RANGES
            and self._range_fits(source_fact.interval, target_type)
        ):
            decision = CastDecision(CastClass.PROVABLE_NARROWING, "integer value range is proven to fit target")
        obligation = self._obligation(ObligationKind.CAST, node, "cast", source_type, "cast must be classified and range-proven", TypeErrorType.UNSAFE_CAST)
        if decision is None or not decision.allowed:
            self._error(obligation, decision.reason if decision else "unknown source or target type")
        elif decision.kind is CastClass.PROVABLE_NARROWING and not self._range_fits(source_fact.interval, target_type):
            self._error(obligation, "cast target range is not proven")
        elif isinstance(source_type, PrimitiveType) and source_type.name in {"f32", "f64"} and isinstance(target_type, PrimitiveType) and target_type.name in INTEGER_RANGES and not self._float_to_int_is_proven(node.expression, target_type):
            self._error(obligation, "float-to-int cast requires finite integral range proof")
        else:
            node.cast_decision = decision
            node.cast_source_type = source_type
            node.cast_target_type = target_type
            self._prove(obligation, decision.reason)
        if isinstance(target_type, PrimitiveType) and target_type.name in INTEGER_RANGES and self._range_fits(source_fact.interval, target_type):
            return ValueFact(interval=source_fact.interval, nonzero=source_fact.nonzero)
        if decision is not None and decision.allowed and source_type == target_type:
            return source_fact
        return ValueFact()

    def _type_from_cast_target(self, node: ASTNode) -> Optional[Type]:
        return getattr(node, "cast_target_type", None)

    def _prove_nonzero_divisor(self, node: ASTNode, divisor: ASTNode, operation: str) -> None:
        fact = self.facts.node(divisor)
        obligation = self._obligation(ObligationKind.DIVISOR_NONZERO, node, operation, self._type(divisor), "division/modulo divisor must be non-zero", None)
        if fact.nonzero or (fact.interval and fact.interval.is_nonzero()):
            self._prove(obligation, "divisor is proven non-zero")
        else:
            if divisor.kind == NodeKind.LITERAL:
                hint = "The divisor is the constant 0; divide by a non-zero value"
            else:
                name, copy_first = self._guard_subject(divisor, "d")
                hint = (
                    f"{copy_first}Guard the divisor: 'if {name} != 0 {{ ... }}' around the division, "
                    f"or an early 'if {name} == 0 {{ ret ... }}' before it"
                )
            self._error(obligation, "divisor may be zero", hint)

    def _prove_index(self, node: ASTNode, obj: ValueFact, idx: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.INDEX_IN_BOUNDS, node, "index", self._type(node.index), "index must satisfy 0 <= index < len", None)
        length = self._object_length(node.object, obj)
        typ = self._type(node.object)
        unavailable_requirement = None
        if isinstance(typ, ReferenceType) and isinstance(typ.referent_type, ArrayType):
            self._prove_ref_non_nil_for_node(
                node, obj, typ, "reference must be proven non-nil before indexing through it", node.object,
            )
            owner = self.readonly_requirements.index_owners.get(id(node))
            if (owner in self.escaped_index_functions
                    or owner not in self.readonly_requirements.summaries):
                length = None
                unavailable_requirement = ("callable origin is not trackable"
                                           if owner in self.escaped_index_functions
                                           else "function access requirements are unresolved")
        interval = idx.interval
        relative_bound = (idx.upper_length_of is not None and node.object is not None
                          and node.object.kind == NodeKind.IDENTIFIER
                          and idx.upper_length_of == self._key(node.object)
                          and interval is not None and interval.is_nonnegative())
        if relative_bound or (length is not None and interval is not None and interval.contains(0, length - 1)):
            self._prove(obligation, "index is in bounds")
        else:
            detail = "index bounds are not proven"
            if unavailable_requirement is not None:
                detail = "reference-array access requires a complete caller proof: " + unavailable_requirement
                if owner in self.escaped_index_functions:
                    hint = "Use direct calls or unwritten, uncaptured local callable aliases; an index guard alone cannot establish the required caller proof."
                else:
                    hint = "The current analysis cannot resolve this function's access requirements; an index guard alone cannot establish the required caller proof."
            elif node.index is not None and node.index.kind == NodeKind.LITERAL and length is not None:
                hint = f"This array has {length} elements; valid indexes are 0 to {length - 1}"
            else:
                name, copy_first = self._guard_subject(node.index, "i")
                if length is not None:
                    bound = str(length)
                else:
                    # `i < xs.len` is tracked only for a slice held in a variable.
                    slice_name, copy_slice = self._guard_subject(node.object, "xs")
                    bound = f"{slice_name}.len"
                    copy_first = copy_slice or copy_first
                hint = f"{copy_first}Guard the index: 'if {name} < {bound} {{ ... }}' around the access"
            self._error(obligation, detail, hint)

    def _prove_slice(self, node: ASTNode, obj: ValueFact, start: ValueFact, end: ValueFact) -> None:
        obligation = self._obligation(ObligationKind.SLICE_IN_BOUNDS, node, "slice", self._type(node.object), "slice must satisfy 0 <= start <= end <= len", None)
        length = self._object_length(node.object, obj)
        si = start.interval
        ei = end.interval
        if (
            length is not None
            and si is not None
            and ei is not None
            and si.lower is not None
            and ei.upper is not None
            and si.lower >= 0
            and ei.upper <= length
            and si.upper is not None
            and ei.lower is not None
            and si.upper <= ei.lower
        ):
            self._prove(obligation, "slice range is in bounds")
        else:
            if length is None:
                hint = (
                    "Slice bounds are proven only against a known length: slice the fixed-size array "
                    "itself, for example 'if end <= 5 { ... xs[0..end] ... }' for a '[5]T' array"
                )
            else:
                name, _ = self._guard_subject(node.end, "end")
                hint = (
                    f"Guard each variable bound against a constant, one comparison per 'if': "
                    f"'if {name} <= {length} {{ ... xs[0..{name}] ... }}'; a variable start needs "
                    f"its own 'if start <= K', with K no greater than the smallest end"
                )
            self._error(obligation, "slice bounds are not proven", hint)

    def _slice_fact(self, node: ASTNode, obj: ValueFact, start: ValueFact, end: ValueFact) -> ValueFact:
        if start.interval and end.interval and start.interval.lower is not None and end.interval.upper is not None and start.interval.lower == start.interval.upper and end.interval.lower == end.interval.upper:
            return ValueFact(known_length=end.interval.upper - start.interval.lower, non_nil=True)
        return ValueFact(non_nil=True)

    def _object_length(self, node: Optional[ASTNode], fact: ValueFact) -> Optional[int]:
        type_ = self._type(node)
        if isinstance(type_, ReferenceType) and isinstance(type_.referent_type, ArrayType):
            type_ = type_.referent_type
        if isinstance(type_, ArrayType):
            return type_.size
        if fact.known_length is not None:
            return fact.known_length
        return None

    def _prove_ref_non_nil(self, node: ASTNode, fact: ValueFact) -> None:
        self._prove_ref_non_nil_for_node(
            node,
            fact,
            self._type(node.pointer),
            "reference must be proven non-nil before dereference",
            node.pointer,
        )

    def _prove_ref_non_nil_for_node(
        self,
        node: ASTNode,
        fact: ValueFact,
        operand_type: Optional[Type],
        required: str,
        reference: Optional[ASTNode],
    ) -> None:
        obligation = self._obligation(ObligationKind.REF_NON_NIL, node, "deref", operand_type, required, TypeErrorType.CANNOT_DEREFERENCE)
        if fact.non_nil:
            self._prove(obligation, "reference is non-nil")
        else:
            name, copy_first = self._guard_subject(reference, "p", fields=True)
            self._error(
                obligation,
                "reference may be nil",
                f"{copy_first}Check the reference first: 'if {name} != nil {{ ... }}' around the use, "
                f"or an early 'if {name} == nil {{ ret ... }}' before it",
            )

    def _prove_integer_overflow(self, node: ASTNode, fact: ValueFact) -> None:
        # Wrapping stays the default lowering. When both operand intervals are
        # known and the raw result fits the result type, approve a non-wrapping
        # lowering for the release backend. `fact` cannot be used here:
        # _binary_fact clamps overflowing results to the full type range, so
        # the raw interval is recomputed from the operand node facts.
        result_type = self._type(node)
        if not isinstance(result_type, PrimitiveType) or result_type.name not in INTEGER_RANGES:
            return
        if node.left is None or node.right is None:
            return
        operations = {
            BinaryOp.ADD: IntegerInterval.add,
            BinaryOp.SUB: IntegerInterval.sub,
            BinaryOp.MUL: IntegerInterval.mul,
        }
        nonwrap = node.operator.name.lower() + "_nonwrap"
        left = self.facts.node(node.left)
        right = self.facts.node(node.right)
        if not left.interval or not right.interval:
            self._refuse_nonwrap(node, nonwrap)
            return
        interval = operations[node.operator](left.interval, right.interval)
        obligation = self._obligation(
            ObligationKind.INTEGER_OVERFLOW,
            node,
            nonwrap,
            result_type,
            "arithmetic result must fit the result type range",
            None,
        )
        if not self._range_fits(interval, result_type):
            self._refuse_nonwrap(node, nonwrap)
        elif (id(node), nonwrap) not in self.refused_nonwrap:
            self._prove(obligation, "result interval fits the result type range")

    def _refuse_nonwrap(self, node: ASTNode, operation: str) -> None:
        """Keep the wrapping lowering for `node`, whatever another proof of it found.

        A deferred statement is proven once per scope exit. One exit where the
        result may overflow withdraws the approval for all of them.
        """
        self.refused_nonwrap.add((id(node), operation))
        self.backend_plan.approved.pop((id(node), operation), None)

    def _range_fits(self, interval: Optional[IntegerInterval], target_type: Optional[Type]) -> bool:
        if not isinstance(target_type, PrimitiveType) or target_type.name not in INTEGER_RANGES or interval is None:
            return False
        low, high = INTEGER_RANGES[target_type.name]
        return interval.contains(low, high)

    def _float_to_int_is_proven(self, node: Optional[ASTNode], target_type: Type) -> bool:
        if node is None or node.kind != NodeKind.LITERAL or node.literal_kind != LiteralKind.FLOAT:
            return False
        value = node.literal_value
        if not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
            return False
        low, high = INTEGER_RANGES[getattr(target_type, "name", "")]
        return low <= int(value) <= high

    def _always_returns(self, node: ASTNode) -> bool:
        """Whether every branch leaves this statement via ret, break or continue."""
        results = {}
        pending = [(node, False)]
        while pending:
            current, finish = pending.pop()
            children = []
            if current is not None and current.kind == NodeKind.BLOCK and current.statements:
                children = [current.statements[-1]]
            elif current is not None and current.kind == NodeKind.IF_STMT:
                children = [current.then_stmt, current.else_stmt]
            if children and not finish:
                pending.append((current, True))
                pending.extend((child, False) for child in reversed(children))
                continue
            results[id(current)] = (all(results[id(child)] for child in children) if children
                                    else current is not None and current.kind in EXIT_KINDS)
        return results[id(node)]

    def _facts_from_condition(self, condition: Optional[ASTNode], *, positive: bool) -> dict[str, ValueFact]:
        original_positive = positive
        predicate = condition
        while predicate is not None and predicate.kind == NodeKind.UNARY and predicate.operator == UnaryOp.NOT:
            positive = not positive
            predicate = predicate.operand
        subject = predicate
        value = positive
        if predicate is not None and predicate.kind == NodeKind.BINARY and predicate.operator in {BinaryOp.EQ, BinaryOp.NE}:
            for subject, literal in ((predicate.left, predicate.right), (predicate.right, predicate.left)):
                if literal.kind == NodeKind.LITERAL and literal.literal_kind == LiteralKind.BOOLEAN:
                    value = literal.literal_value if positive == (predicate.operator == BinaryOp.EQ) else not literal.literal_value
                    break
            else:
                subject = None
        if subject is not None and subject.kind == NodeKind.IDENTIFIER:
            key = self._key(subject)
            if key in self.local_boolean_keys and key not in self.borrowed_keys:
                return {key: replace(self.facts.symbol(key), boolean=value)}
        positive = original_positive
        if condition is None or condition.kind != NodeKind.BINARY:
            return {}
        field_guard = condition.left is not None and condition.left.kind == NodeKind.FIELD_ACCESS
        if field_guard and not (condition.right and condition.right.kind == NodeKind.LITERAL
                                and condition.right.literal_kind == LiteralKind.NIL):
            return {}
        name = self._place_key(condition.left)
        if not name:
            return {}
        literal = self._int_literal(condition.right)
        current = self.facts.symbol(name)
        interval = current.interval
        facts: dict[str, ValueFact] = {}
        rhs = self.facts.node(condition.right).interval
        if literal is not None:
            rhs = IntegerInterval.exact(literal)
        op = condition.operator
        if not positive:
            op = {BinaryOp.GE: BinaryOp.LT, BinaryOp.GT: BinaryOp.LE, BinaryOp.LE: BinaryOp.GT, BinaryOp.LT: BinaryOp.GE, BinaryOp.EQ: BinaryOp.NE, BinaryOp.NE: BinaryOp.EQ}.get(op, op)
        if rhs:
            lo, hi = (interval.lower, interval.upper) if interval else (None, None)
            if op in {BinaryOp.GE, BinaryOp.GT, BinaryOp.EQ} and rhs.lower is not None:
                lower = rhs.lower + (1 if op == BinaryOp.GT else 0)
                lo = max(lo, lower) if lo is not None else lower
            if op in {BinaryOp.LE, BinaryOp.LT, BinaryOp.EQ} and rhs.upper is not None:
                upper = rhs.upper - (1 if op == BinaryOp.LT else 0)
                hi = min(hi, upper) if hi is not None else upper
            narrowed = IntegerInterval(lo, hi)
            facts[name] = replace(current, interval=narrowed, nonzero=current.nonzero or narrowed.is_nonzero())
        if (op == BinaryOp.LT and condition.right and condition.right.kind == NodeKind.FIELD_ACCESS
                and condition.right.field == "len" and condition.right.object
                and condition.right.object.kind == NodeKind.IDENTIFIER
                and isinstance(self._type(condition.right.object), (ArrayType, SliceType))):
            target = self._key(condition.right.object)
            self.length_targets.add(target)
            facts[name] = replace(facts.get(name, current), upper_length_of=target)
        if self._zero_literal(condition.right):
            if (positive and condition.operator == BinaryOp.NE) or (not positive and condition.operator == BinaryOp.EQ):
                facts[name] = ValueFact(interval=interval, nonzero=True, non_nil=current.non_nil, maybe_nil=current.maybe_nil)
        if condition.right and condition.right.kind == NodeKind.LITERAL and condition.right.literal_kind == LiteralKind.NIL:
            if positive and condition.operator == BinaryOp.NE:
                facts[name] = replace(current, non_nil=True, maybe_nil=False)
            elif not positive and condition.operator == BinaryOp.EQ:
                facts[name] = replace(current, non_nil=True, maybe_nil=False)
        return facts

    def _zero_literal(self, node: Optional[ASTNode]) -> bool:
        if node is None or node.kind != NodeKind.LITERAL:
            return False
        if node.literal_kind == LiteralKind.INTEGER:
            return node.literal_value == 0
        if node.literal_kind == LiteralKind.FLOAT:
            return node.literal_value == 0.0
        return False

    def _int_literal(self, node: Optional[ASTNode]) -> Optional[int]:
        sign = 1
        while node is not None and node.kind == NodeKind.UNARY and node.operator == UnaryOp.NEG:
            sign = -sign
            node = node.operand
        if node is not None and node.kind == NodeKind.LITERAL and node.literal_kind == LiteralKind.INTEGER and isinstance(node.literal_value, int):
            return -node.literal_value if sign < 0 else node.literal_value
        return None

    def _mark_deleted(self, node: ASTNode) -> None:
        key = self._place_key(node, exact_indices=True, current_indices=True)
        if key:
            self._delete_place(key)

    def _error_moved_symbol(self, node: ASTNode, name: str, required: str) -> None:
        obligation = self._obligation(
            ObligationKind.MOVE_VALID,
            node,
            "move",
            self._type(node),
            required,
            TypeErrorType.USE_AFTER_MOVE,
        )
        self._error(obligation, f"'{name}' was moved or deleted earlier")
