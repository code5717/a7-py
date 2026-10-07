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
from typing import Optional

from a7.ast_nodes import ASTNode, AssignOp, BinaryOp, LiteralKind, NodeKind, UnaryOp
from a7.cast_classifier import CastClass, CastDecision, classify_cast
from a7.errors import SourceSpan, TypeCheckError, TypeErrorType
from a7.symbol_table import SymbolTable
from a7.passes.readonly_requirements import ReadonlyRequirements
from a7.types import (
    ArrayType,
    FunctionType,
    INTEGER_RANGES,
    PrimitiveType,
    ReferenceType,
    SIGNED_INTEGER_WIDTHS,
    SliceType,
    Type,
    TypeKind,
    UnionType,
    UNSIGNED_INTEGER_WIDTHS,
)


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

# Headline message for each safety obligation kind. Kinds not listed use the
# message of their diagnostic code. Division, index and slice obligations carry
# no diagnostic code: no existing TypeErrorType describes them. Their hint
# comes from the `_error` call site, which knows the operand.
OBLIGATION_MESSAGES = {
    "DIVISOR_NONZERO": "Divisor not proven non-zero",
    "INDEX_IN_BOUNDS": "Index not proven in bounds",
    "SLICE_IN_BOUNDS": "Slice bounds not proven",
    "REF_NON_NIL": "Reference not proven non-nil",
}


class SafetyError(TypeCheckError):
    """A safety obligation the proof pass could not discharge.

    `hint` names the guard shape the pass accepts for this obligation and
    takes the place of the advice text of the diagnostic code.
    """

    hint: Optional[str] = None


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


@dataclass(frozen=True)
class AllocationRef:
    root: int


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


class ObligationKind(Enum):
    CAST = auto()
    DIVISOR_NONZERO = auto()
    INDEX_IN_BOUNDS = auto()
    SLICE_IN_BOUNDS = auto()
    REF_NON_NIL = auto()
    INTEGER_OVERFLOW = auto()
    UNION_FIELD = auto()
    MOVE_VALID = auto()


@dataclass(frozen=True)
class Obligation:
    kind: ObligationKind
    node_id: int
    backend_operation: str
    span: Optional[SourceSpan]
    operand_type: Optional[Type]
    required_proof: str
    diagnostic_code: Optional[TypeErrorType]


@dataclass(frozen=True)
class ProofResult:
    proven: bool
    obligation: Obligation
    reason: str


@dataclass
class BackendPlan:
    approved: dict[tuple[int, str], ProofResult] = field(default_factory=dict)

    def approve(self, result: ProofResult) -> None:
        key = (result.obligation.node_id, result.obligation.backend_operation)
        self.approved[key] = result

    def require(self, node: ASTNode, operation: str) -> ProofResult:
        result = self.approved.get((id(node), operation))
        if result is None or not result.proven:
            raise KeyError(f"backend operation '{operation}' is not approved")
        return result

    def is_approved(self, node: ASTNode, operation: str) -> bool:
        result = self.approved.get((id(node), operation))
        return bool(result and result.proven)


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

    def copy(self) -> ParameterEffectState:
        return ParameterEffectState(dict(self.aliases), set(self.deleted), set(self.written), dict(self.places), self.counter_delta)

    @staticmethod
    def join(states: list[ParameterEffectState]) -> ParameterEffectState:
        aliases = {key: frozenset().union(*(state.aliases.get(key, frozenset({(-3, True)}) if isinstance(key, tuple) else frozenset())
                                           for state in states))
                   for key in set().union(*(state.aliases.keys() for state in states))}
        result = ParameterEffectState(aliases)
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

    def __init__(self, symbols: SymbolTable, node_types: dict[int, Type]):
        self.symbols = symbols
        self.node_types = node_types
        self.facts = FactMap()
        self.obligations: list[Obligation] = []
        self.results: list[ProofResult] = []
        self.backend_plan = BackendPlan()
        self.errors: list[TypeCheckError] = []
        self.moved_symbols: set[str | AllocationRef] = set()
        self.const_facts: dict[str, ValueFact] = {}
        self.current_stmt_span: Optional[SourceSpan] = None
        self.current_file = "<unknown>"
        self.source_lines: list[str] = []
        self.exact_effect_bodies: dict[str, ASTNode] = {}
        self.exact_effect_reasons: dict[str, set[str]] = {}
        self.function_deletes: dict[str, bool] = {}
        self.function_field_writes: dict[str, dict[int, set[str]]] = {}
        self.function_parameter_deletes: dict[str, set[int]] = {}
        self.borrowed_keys: set[str] = set()
        self.allocation_graph = AllocationGraph()
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

    def analyze(self, program: ASTNode, filename: str = "<unknown>") -> BackendPlan:
        self.current_file = filename
        self.errors = []
        self.obligations = []
        self.results = []
        self.backend_plan = BackendPlan()
        self.facts = FactMap()
        self.moved_symbols = set()
        self.const_facts = {}
        self.current_stmt_span = None
        self.function_deletes = {}
        self.symbol_types = {}
        self.allocation_graph = AllocationGraph()
        self.allocation_places = {}
        self.allocation_place_names = {}
        self._reset_bindings()
        self._bind_names(program)
        self._visit_program(program)
        return self.backend_plan

    def _origin_set(self, values):
        ordinary = set()
        fresh = {False: [], True: []}
        for origin, exact in values:
            if isinstance(origin, AllocationRef):
                fresh[exact].append(origin.root)
            else:
                ordinary.add((origin, exact))
        for exact, roots in fresh.items():
            root = self.allocation_graph.union(roots)
            if root:
                ordinary.add((AllocationRef(root), exact))
        return frozenset(ordinary)

    def _origin_intersection(self, values, deleted):
        result = set(values) & set(deleted)
        left = self.allocation_graph.union(value.root for value in values if isinstance(value, AllocationRef))
        right = self.allocation_graph.union(value.root for value in deleted if isinstance(value, AllocationRef))
        root = self.allocation_graph.combine('intersection', left, right)
        result = {value for value in result if not isinstance(value, AllocationRef)}
        if root:
            result.add(AllocationRef(root))
        return frozenset(result)

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
        for prefix in sorted(self.allocation_places, key=len, reverse=True):
            parent = self.allocation_places[prefix]
            if key.startswith(prefix + '.'):
                return frozenset({AllocationRef(self.allocation_graph.prefix(('field', key[len(prefix) + 1:]), parent))})
        return frozenset({f'field:{key}'})

    def _move_allocations(self, allocations, moved=None):
        moved = self.moved_symbols if moved is None else moved
        root = self._allocation_root(allocations)
        if root:
            moved.add(AllocationRef(root))

    def _allocations_moved(self, allocations, moved=None):
        moved = self.moved_symbols if moved is None else moved
        root = self._allocation_root(allocations)
        return any(self.allocation_graph.combine('intersection', root, item.root)
                   for item in moved if isinstance(item, AllocationRef))

    def _type(self, node: Optional[ASTNode]) -> Optional[Type]:
        return self.node_types.get(id(node)) if node is not None else None

    def _error(self, obligation: Obligation, reason: str, hint: Optional[str] = None) -> None:
        self.results.append(ProofResult(False, obligation, reason))
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
        open_scopes: list[tuple[int, list[str]]] = []
        count = 0
        work: list[tuple[str, object]] = [("visit", decl) for decl in reversed(program.declarations or [])]
        while work:
            action, item = work.pop()
            if action == "open":
                open_scopes.append((id(item), []))
                continue
            if action == "close":
                for name in open_scopes.pop()[1]:
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
                continue
            node = item
            kind = node.kind
            if kind == NodeKind.IDENTIFIER:
                if bound.get(node.name):
                    self.keys[(id(node), node.name)] = bound[node.name][-1]
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
            work.extend(reversed(steps))

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
        for name, decl in bodies.items():
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
                    if key in self.file_variables:
                        self.function_written_globals[name].add(key)
                if item.kind == NodeKind.DEL:
                    if item.expression is None or item.expression.kind != NodeKind.IDENTIFIER:
                        self.function_direct_deletes[name] = False
                    deleted_key = self._place_key(item.expression)
                    if deleted_key and deleted_key.split(".")[0] in self.file_variables:
                        deleted_globals.add(deleted_key)
                if item.kind == NodeKind.CALL and item.function:
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
        self._classify_exact_effects(bodies)
        for decl in node.declarations or []:
            self._visit_decl(decl)

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
                self.moved_symbols.add(key)

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
                    storage[key] = fact if isinstance(self._type(node.value), ReferenceType) or fact.maybe_nil else ValueFact()
                    moved.discard(key)
                    continue
                if action == "delete":
                    fact = values.get(id(node.expression), ValueFact())
                    self._move_allocations(fact.allocations, moved)
                    key = places.get(id(node.expression))
                    if key:
                        moved.add(key)
                    continue
                if action == "expr":
                    if node is None:
                        continue
                    if node.kind == NodeKind.IDENTIFIER:
                        key = bindings[-1].get(self._key(node), self._key(node))
                        places[id(node)] = key
                        fact = storage.get(key, ValueFact())
                        values[id(node)] = fact
                        if key in moved or self._allocations_moved(fact.allocations | fact.selected_allocations, moved):
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
                        if key in moved or self._allocations_moved(fact.allocations | fact.selected_allocations, moved):
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
                joined = self._join_facts(joined, storage)
                dead |= moved
            self.facts.by_symbol = {key: fact for key, fact in joined.items() if not isinstance(key, str) or not key.startswith("effect:")}
            self.moved_symbols = {key for key in dead if not isinstance(key, str) or not key.startswith("effect:")}

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
        unknown_origins = frozenset().union(*aliases.values()) if field_places else frozenset({(-1, True)})
        # Negative integers distinguish unknown (-1), unchanged fields (-3),
        # and global declarations. Fresh alternatives share allocation graphs.
        unchanged = frozenset({(-3, True)})
        exits = []
        returned = []
        live = True
        writes: dict[int, set[str]] = {}
        flow = ParameterEffectState(aliases)
        loops = []
        frames: list[tuple[ASTNode, list[ASTNode]]] = []
        work = [("visit", function if field_places else function.body, None)]
        while work:
            action, node, state = work.pop()
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
                    if literal is not True:
                        context["false"].append(flow.copy())
                    if literal is not False:
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
                    flow = ParameterEffectState.join(incoming)
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
                head = ParameterEffectState.join([context["entry"], *context["back"]])
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
                    loop_results.update(back=ParameterEffectState.join(context["back"]),
                                        exit=ParameterEffectState.join(normal_exits),
                                        has_break=bool(context["breaks"]))
                live = bool(normal_exits)
                if live:
                    flow = ParameterEffectState.join(normal_exits)
                continue
            if action == "bind":
                if live:
                    key, value = state
                    flow.aliases[key] = self._parameter_origins(value, flow.aliases, field_places=field_places, unknown_origins=unknown_origins)
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
                name, captured = state
                summary = self.function_field_writes.get(name)
                stores = self.function_field_stores.get(name, {})
                if field_places:
                    flow.written.update(self.file_variables)
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
                                invocation = AllocationRef(self.allocation_graph.prefix(("call", id(node)), origin.root))
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
                                invocation = AllocationRef(self.allocation_graph.prefix(("call", id(node)), origin.root))
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
                flow = ParameterEffectState.join([before, flow]) if action == "fall_other" and live else before.copy()
                live = before_live
                continue
            if action == "join":
                before, branches, before_live = state
                if live:
                    branches.append(flow.copy())
                live = bool(branches) and before_live
                flow = ParameterEffectState.join(branches)
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
                    if (condition.kind == NodeKind.LITERAL
                            and condition.literal_kind == LiteralKind.BOOLEAN):
                        work.append(("visit", then_branch if condition.literal_value else else_branch, None))
                    else:
                        frame = (flow.copy(), [], live)
                        work.extend([("join", node, frame), ("visit", else_branch, None),
                                     ("other", node, frame), ("visit", then_branch, None)])
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
            targets = []
            deletion_targets = []
            if node.kind == NodeKind.DEL:
                deletion_targets.append(node.expression)
                if field_places:
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

    def _loop_effects(self, loop: ASTNode):
        """Separate effects reaching a body backedge from matching loop exits."""
        origins = {key: frozenset({(AllocationRef(root), True)}) if root else frozenset()
                   for key, fact in self.facts.by_symbol.items()
                   for root in [self._allocation_root(fact.allocations)]}
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
        return back.written, deletions[0], exit_state.written, deletions[1], results["has_break"], back.counter_delta

    def _apply_loop_deletions(self, deleted: dict[str | AllocationRef, Optional[frozenset[str | AllocationRef]]]) -> None:
        for key, allocations in deleted.items():
            if allocations is None:
                self._delete_place(key)
            else:
                self.moved_symbols.add(key)
                self._move_allocations(allocations)

    def _invalidate_length_relations(self, key: str) -> None:
        if key not in self.length_targets:
            return
        for other, fact in list(self.facts.by_symbol.items()):
            if fact.upper_length_of == key:
                self.facts.set_symbol(other, replace(fact, upper_length_of=None))

    def _forget_names(self, keys: set[str]) -> None:
        affected = set(keys)
        for name in self.facts.by_symbol:
            if any(name.startswith(key + ".") for key in keys):
                affected.add(name)
        for key in affected:
            self._invalidate_length_relations(key)
            # A key with no entry is already unknown: a local the loop
            # declares later, or a file-scope variable.
            if key in self.facts.by_symbol:
                self.facts.set_symbol(key, replace(self._default_fact_for_type(self.symbol_types.get(key)),
                                                   allocations=self.facts.symbol(key).allocations,
                                                   selected_allocations=self.facts.symbol(key).selected_allocations))

    def _join_facts(self, left: dict[str, ValueFact], right: dict[str, ValueFact]) -> dict[str, ValueFact]:
        joined = {}
        for name in left.keys() | right.keys():
            a, b = left.get(name, ValueFact()), right.get(name, ValueFact())
            if a is b:
                joined[name] = a
                continue
            interval = None
            if a.interval and b.interval:
                lo = min(a.interval.lower, b.interval.lower) if a.interval.lower is not None and b.interval.lower is not None else None
                hi = max(a.interval.upper, b.interval.upper) if a.interval.upper is not None and b.interval.upper is not None else None
                interval = IntegerInterval(lo, hi)
            joined[name] = ValueFact(interval=interval, nonzero=a.nonzero and b.nonzero,
                                     known_length=a.known_length if a.known_length == b.known_length else None,
                                     upper_length_of=a.upper_length_of if a.upper_length_of == b.upper_length_of else None,
                                     non_nil=a.non_nil and b.non_nil, maybe_nil=a.maybe_nil or b.maybe_nil,
                                     initialized=a.initialized and b.initialized, moved=a.moved or b.moved,
                                     allocations=a.allocations | b.allocations,
                                     selected_allocations=a.selected_allocations | b.selected_allocations)
        return joined

    def _place_key(self, node: Optional[ASTNode]) -> Optional[str]:
        fields = []
        while node is not None and node.kind == NodeKind.FIELD_ACCESS:
            fields.append(node)
            node = node.object
        if node is None or node.kind != NodeKind.IDENTIFIER:
            return None
        key = self._key(node)
        for access in reversed(fields):
            if isinstance(self._type(access.object), ReferenceType):
                allocations = self.facts.symbol(key).allocations
                if self._allocation_count(allocations) == 1:
                    key = self._allocation_place(allocations)
            key += "." + access.field
        return key

    def _store_value(self, key: str, value: Optional[ASTNode], fact: ValueFact) -> None:
        # Struct copies retain the allocation identities of their reference fields.
        children = {}
        pending = [(key, value)]
        while pending:
            prefix, current = pending.pop()
            source_key = self._place_key(current)
            if source_key:
                children.update({prefix + name[len(source_key):]: item
                                 for name, item in self.facts.by_symbol.items()
                                 if name.startswith(source_key + ".")})
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
                self.moved_symbols.discard(name)
        if "." in key and not isinstance(self._type(value), ReferenceType) and not fact.maybe_nil:
            fact = ValueFact()
        self.facts.set_symbol(key, fact)
        self.facts.by_symbol.update(children)
        self.moved_symbols.discard(key)

    def _delete_place(self, key: str) -> None:
        fact = self.facts.symbol(key)
        self._move_allocations(fact.allocations)
        self.moved_symbols.add(key)

    def _check_reference_alive(self, node: ASTNode, fact: ValueFact, key: Optional[str]) -> None:
        if key in self.moved_symbols or self._allocations_moved(fact.allocations | fact.selected_allocations):
            name = node.name if node.kind == NodeKind.IDENTIFIER else node.field
            self._error_moved_symbol(node, name, "moved/deleted values cannot be read")

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
                self.moved_symbols.discard(key)
        elif node.kind in {NodeKind.VAR, NodeKind.CONST}:
            fact = self._visit_expr(node.value) if node.value else self._default_fact_for_type(self._type(node))
            if node.name:
                key = self._key(node)
                self._invalidate_length_relations(key)
                self._store_value(key, node.value, fact)
                self.symbol_types[key] = self._type(node) or self._type(node.value)
                self.moved_symbols.discard(key)
        elif node.kind == NodeKind.ASSIGNMENT:
            rhs = self._visit_expr(node.value) if node.value else ValueFact()
            if node.target:
                target_fact = (
                    self._visit_expr(node.target.object if node.target.kind == NodeKind.FIELD_ACCESS else node.target)
                    if getattr(node, "implicit_deref_target", False) or node.target.kind != NodeKind.IDENTIFIER
                    else self.facts.symbol(self._key(node.target))
                )
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
                    key = self._place_key(node.target)
                    if key:
                        self._store_value(key, node.value, rhs)
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
            saved = self.facts.copy_symbols()
            moved = set(self.moved_symbols)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=True))
            if node.then_stmt:
                yield node.then_stmt
            then_state = self.facts.copy_symbols()
            then_moved = set(self.moved_symbols)
            self.facts.restore_symbols(dict(saved))
            self.moved_symbols = set(moved)
            self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            if node.else_stmt:
                yield node.else_stmt
            if node.then_stmt and self._always_returns(node.then_stmt):
                pass  # Only the else path reaches the following statement.
            elif node.else_stmt and self._always_returns(node.else_stmt):
                self.facts.restore_symbols(then_state)
                self.moved_symbols = then_moved
            else:
                self.facts.by_symbol = self._join_facts(then_state, self.facts.by_symbol)
                self.moved_symbols.update(then_moved)
        elif node.kind in {NodeKind.WHILE, NodeKind.FOR}:
            self.frames.append(ExitFrame(node))
            if node.init:
                yield node.init
            written, deleted, exit_written, exit_deleted, has_break, back_delta = self._loop_effects(node)
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
            if not single_iteration:
                self._apply_loop_deletions(deleted)
                self._forget_names(written)
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
                    self.facts.by_symbol = self._join_facts(self.facts.by_symbol, facts)
                    self.moved_symbols.update(continue_moved)
                yield node.update
            # The loop may run zero times, and a `break` leaves from a state
            # the head state covers, so nothing the body established survives.
            # The false condition holds after the loop only when no `break`
            # can leave with it still true.
            self.facts.restore_symbols(head)
            self.moved_symbols = head_moved
            self._forget_names(exit_written)
            self._apply_loop_deletions(exit_deleted)
            if node.condition and not has_break:
                self.facts.by_symbol.update(self._facts_from_condition(node.condition, positive=False))
            for key in self.scope_keys.get(id(node), ()):
                self.facts.by_symbol.pop(key, None)
                self.moved_symbols.discard(key)
        elif node.kind in {NodeKind.FOR_IN, NodeKind.FOR_IN_INDEXED}:
            iterable_fact = self._visit_expr(node.iterable)
            self.frames.append(ExitFrame(node))
            written, deleted, exit_written, exit_deleted, _, _ = self._loop_effects(node)
            if self._object_length(node.iterable, iterable_fact) != 1:
                self._apply_loop_deletions(deleted)
                self._forget_names(written)
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
            self._forget_names(exit_written)
            self._apply_loop_deletions(exit_deleted)
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
                    self.facts.by_symbol = self._join_facts(self.facts.by_symbol, fallen[0])
                    self.moved_symbols.update(fallen[1])
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
                    joined = self._join_facts(joined, self.facts.by_symbol)
                    all_moved.update(self.moved_symbols)
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
            if target.kind == NodeKind.IDENTIFIER and self._key(target) in self.moved_symbols:
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
                                self.moved_symbols.add(AllocationRef(remaining))
                values.append(ValueFact(maybe_nil=True, allocations=frozenset({AllocationRef(root)})))
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
                if self._exact_call_name(node, captured) is not None:
                    engine.dispositions.append((id(node), name, "existing exact replay owns requirement"))
                    continue
                violation, origin, disposition = engine.evaluate(name, scalar_captures)
                engine.dispositions.append((id(node), name, disposition))
                if violation is True:
                    origin_span = getattr(origin, "span", None)
                    required = "readonly callee field access must remain non-nil"
                    if origin_span is not None:
                        required += f" (callee use at line {origin_span.start_line}, column {origin_span.start_column})"
                    obligation = self._obligation(ObligationKind.REF_NON_NIL, node,
                        "readonly_call_precondition", None, required, TypeErrorType.CANNOT_DEREFERENCE)
                    self._error(obligation, "reachable readonly callee read receives nil",
                        "Guard the reference or avoid the callee path that reads it")
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
                        self.moved_symbols.add(key)
                continue
            if action == "call_start":
                exact_name = self._exact_call_name(node)
                captured = []
                scalar_captures = []
                global_values = {}
                callee = node.function
                name = self._key(callee) if callee and callee.kind == NodeKind.IDENTIFIER else None
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
                scalar_captures.append(scalar)
                fact = self.facts.node(arg)
                captured.append((replace(fact, non_nil=True) if i in borrowed else fact, self._place_key(arg) if i in borrowed else None))
                if not exact_name:
                    self._apply_legacy_reference_effects(node, i, arg, self.facts.node(arg))
                arg_fact = self.facts.node(arg)
                is_ref_parameter = isinstance(function_type, FunctionType) and i < len(function_type.param_types) and isinstance(function_type.param_types[i], ReferenceType)
                if isinstance(self._type(arg), ReferenceType) and is_ref_parameter:
                    self._prove_ref_non_nil_for_node(node, arg_fact, self._type(arg), "reference argument must be proven non-nil", arg)
                elif i in borrowed and arg.kind == NodeKind.IDENTIFIER:
                    self._invalidate_length_relations(self._key(arg))
                    key = self._key(arg)
                    self.facts.set_symbol(key, replace(self._default_fact_for_type(self._type(arg)),
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
                fact = self.facts.symbol(key)
                self._check_reference_alive(node, fact, key)
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
            elif node.kind == NodeKind.SLICE:
                obj_fact = self.facts.node(node.object)
                start_fact = self.facts.node(node.start) if node.start else ValueFact(interval=IntegerInterval.exact(0))
                end_fact = self.facts.node(node.end) if node.end else ValueFact(interval=IntegerInterval.exact(obj_fact.known_length), known_length=obj_fact.known_length) if obj_fact.known_length is not None else ValueFact()
                self._prove_slice(node, obj_fact, start_fact, end_fact)
                fact = self._slice_fact(node, obj_fact, start_fact, end_fact)
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
                key = self._place_key(node)
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
                            identities.update(child.allocations | child.selected_allocations)
                            missing = self.allocation_graph.combine('difference', missing, parent)
                        if child_key in self.moved_symbols:
                            alive_key = child_key
                    if missing:
                        identities.add(AllocationRef(self.allocation_graph.prefix(('field', node.field), missing)))
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
        interval = idx.interval
        relative_bound = (idx.upper_length_of is not None and node.object is not None
                          and node.object.kind == NodeKind.IDENTIFIER
                          and idx.upper_length_of == self._key(node.object)
                          and interval is not None and interval.is_nonnegative())
        if relative_bound or (length is not None and interval is not None and interval.contains(0, length - 1)):
            self._prove(obligation, "index is in bounds")
        else:
            if node.index is not None and node.index.kind == NodeKind.LITERAL and length is not None:
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
            self._error(obligation, "index bounds are not proven", hint)

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
        key = self._place_key(node)
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
