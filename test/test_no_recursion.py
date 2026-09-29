"""No recursion anywhere in the compiler (`a7/`).

The scanner in `test/norec_scan.py` builds a receiver-aware call graph of the
package and reports recursive groups (strongly connected components and
self-loops), `copy.deepcopy` calls, and dataclasses whose generated
`__eq__`/`__repr__`/`__hash__` recurse.

The synthetic cases below are the scanner's specification: they state what
must be reported and what must not be. The ratchet tests at the end hold the
recursion that still exists in `a7/`; see "No recursion anywhere in the
compiler" in docs/plan/execution.md.
"""

import shutil
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import norec_scan  # noqa: E402

A7_ROOT = Path(__file__).resolve().parents[1] / "a7"


def scan_sources(tmp_path, files):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "__init__.py").write_text("")
    for rel, source in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source))
    return norec_scan.scan(root)


# --------------------------------------------------------------------------
# Scanner specification: recursion that must be reported
# --------------------------------------------------------------------------

def test_direct_self_recursion_is_reported(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        def fact(n):
            return 1 if n <= 1 else n * fact(n - 1)

        class Walker:
            def depth(self, node):
                return 1 + max((self.depth(c) for c in node.children), default=0)
    """})
    assert set(result.groups) == {("pkg.m:fact",), ("pkg.m:Walker.depth",)}


def test_mutual_recursion_across_methods_is_one_group(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Parser:
            def parse_expr(self):
                return self.parse_primary()

            def parse_primary(self):
                if self.peek() == "(":
                    return self.parse_expr()
                return None

            def peek(self):
                return "x"
    """})
    assert result.groups == [("pkg.m:Parser.parse_expr", "pkg.m:Parser.parse_primary")]


def test_recursion_through_nested_functions_is_reported(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        def collect(node):
            names = []

            def visit(n):
                names.append(n.name)
                for child in n.children:
                    visit(child)

            visit(node)
            return names

        def outer(x):
            def inner(y):
                return outer(y)
            return inner(x)
    """})
    assert set(result.groups) == {
        ("pkg.m:collect.visit",),
        ("pkg.m:outer", "pkg.m:outer.inner"),
    }


def test_getattr_visitor_dispatch_is_reported(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Visitor:
            def visit(self, node):
                method = getattr(self, f"visit_{node.kind}")
                return method(node)

            def visit_block(self, node):
                for stmt in node.statements:
                    self.visit(stmt)

            def visit_literal(self, node):
                return node.value

            def helper(self):
                return 0

        class Emitter:
            def emit(self, node):
                return getattr(self, "emit_" + node.kind.lower())(node)

            def emit_call(self, node):
                return [self.emit(arg) for arg in node.arguments]
    """})
    assert set(result.groups) == {
        ("pkg.m:Visitor.visit", "pkg.m:Visitor.visit_block"),
        ("pkg.m:Emitter.emit", "pkg.m:Emitter.emit_call"),
    }


def test_callback_passed_to_a_walker_is_reported(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Generator:
            def _walk(self, root, visitor):
                stack = [root]
                while stack:
                    node = stack.pop()
                    visitor(node)
                    stack.extend(node.children)

            def emit(self, root):
                def visit(node):
                    if node.kind == "fn":
                        self.emit(node.body)
                self._walk(root, visit)
    """})
    assert result.groups == [
        ("pkg.m:Generator._walk", "pkg.m:Generator.emit", "pkg.m:Generator.emit.visit"),
    ]


def test_virtual_dispatch_and_implicit_str_through_a_base_type_are_reported(tmp_path):
    result = scan_sources(tmp_path, {"types.py": """
        class Type:
            def equals(self, other: "Type") -> bool:
                raise NotImplementedError

            def __str__(self) -> str:
                raise NotImplementedError(f"{self.__class__.__name__}")

        class IntType(Type):
            def equals(self, other):
                return isinstance(other, IntType)

            def __str__(self):
                return "int"

        class ArrayType(Type):
            def __init__(self, element_type: Type):
                self.element_type = element_type

            def equals(self, other):
                return isinstance(other, ArrayType) and self.element_type.equals(other.element_type)

        class PointerType(Type):
            def __init__(self, pointee: Type):
                self.pointee = pointee

            def equals(self, other):
                return isinstance(other, PointerType) and self.pointee.equals(other.pointee)

            def __str__(self):
                return f"ptr {self.pointee}"
    """})
    assert set(result.groups) == {
        ("pkg.types:ArrayType.equals", "pkg.types:PointerType.equals"),
        ("pkg.types:PointerType.__str__",),
    }


def test_unknown_receiver_inside_the_same_class_family_counts(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Node:
            def size(self, other):
                return 1 + other.size(self)
    """})
    assert result.groups == [("pkg.m:Node.size",)]


# --------------------------------------------------------------------------
# Scanner specification: code that must not be reported
# --------------------------------------------------------------------------

DELEGATION_SOURCES = {
    "scope.py": """
        from typing import List, Optional

        class Scope:
            def __init__(self, name: str, parent: Optional["Scope"] = None):
                self.name = name
                self.parent = parent
                self.symbols = {}
                self.children: List["Scope"] = []

            def define(self, name, value):
                self.symbols[name] = value

            def lookup(self, name):
                scope = self
                while scope is not None:
                    if name in scope.symbols:
                        return scope.symbols[name]
                    scope = scope.parent
                return None

        class SymbolTable:
            def __init__(self):
                self.global_scope = Scope("global")
                self.current_scope = self.global_scope
                self.scope_stack: List[Scope] = [self.global_scope]

            def enter_scope(self, name):
                for child in self.current_scope.children:
                    if child.name == name:
                        self.current_scope = child
                        return child
                new_scope = Scope(name, parent=self.current_scope)
                self.current_scope = new_scope
                self.scope_stack.append(new_scope)
                return new_scope

            def exit_scope(self):
                self.scope_stack.pop()
                self.current_scope = self.scope_stack[-1]

            def define(self, name, value):
                return self.current_scope.define(name, value)

            def lookup(self, name):
                return self.current_scope.lookup(name)
    """,
    "checker.py": """
        from .scope import SymbolTable

        class Checker:
            def __init__(self):
                self.symbols = SymbolTable()

            def lookup(self, name):
                return self.symbols.lookup(name)

        class Proxy:
            def find(self, table, name):
                return table.lookup(name)
    """,
}


def test_delegation_to_a_method_of_the_same_name_on_another_class_is_not_a_cycle(tmp_path):
    result = scan_sources(tmp_path, DELEGATION_SOURCES)
    assert result.groups == []
    # The delegating calls are resolved to their real targets, not dropped.
    assert result.edges["pkg.scope:SymbolTable.lookup"] == {"pkg.scope:Scope.lookup"}
    assert result.edges["pkg.scope:SymbolTable.define"] == {"pkg.scope:Scope.define"}
    assert result.edges["pkg.checker:Checker.lookup"] == {"pkg.scope:SymbolTable.lookup"}


def test_unknown_receiver_outside_the_class_family_is_recorded_not_linked(tmp_path):
    result = scan_sources(tmp_path, DELEGATION_SOURCES)
    assert result.edges.get("pkg.checker:Proxy.find", set()) == set()
    recorded = [u for u in result.unresolved if u.caller == "pkg.checker:Proxy.find"]
    assert [(u.name, u.candidates) for u in recorded] == [
        ("lookup", ("pkg.checker:Checker.lookup", "pkg.scope:Scope.lookup", "pkg.scope:SymbolTable.lookup")),
    ]


def test_super_init_chains_are_not_cycles(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Base:
            def __init__(self, name):
                self.name = name

        class Middle(Base):
            def __init__(self, name):
                super().__init__(name)

        class Leaf(Middle):
            def __init__(self):
                super().__init__("leaf")

        class Holder:
            def __init__(self):
                self.leaf = Leaf()

        class Error(Exception):
            def __init__(self, message):
                super().__init__(message)
    """})
    assert result.groups == []
    assert result.edges["pkg.m:Leaf.__init__"] == {"pkg.m:Middle.__init__"}
    assert result.edges["pkg.m:Middle.__init__"] == {"pkg.m:Base.__init__"}


def test_explicit_stack_traversal_is_not_a_cycle(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Walker:
            def walk(self, root):
                stack = [root]
                count = 0
                while stack:
                    node = stack.pop()
                    count += self.visit_one(node)
                    stack.extend(reversed(node.children))
                return count

            def visit_one(self, node):
                return 1
    """})
    assert result.groups == []


def test_the_scanner_itself_has_no_recursion(tmp_path):
    root = tmp_path / "scanner"
    root.mkdir()
    shutil.copy(Path(norec_scan.__file__), root / "norec_scan.py")
    result = norec_scan.scan(root)
    assert result.groups == [], "\n".join(result.describe_group(g) for g in result.groups)
    assert result.deepcopy_calls == []
    assert result.dataclass_findings == []


# --------------------------------------------------------------------------
# Scanner specification: deepcopy and dataclass-generated methods
# --------------------------------------------------------------------------

def test_deepcopy_and_recursive_dataclass_methods_are_reported(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        import copy
        from copy import deepcopy as clone
        from dataclasses import dataclass, field
        from typing import List, Optional

        @dataclass
        class Node:
            kind: str
            children: List["Node"] = field(default_factory=list)

        @dataclass(eq=False, repr=False)
        class SafeNode:
            kind: str
            children: List["SafeNode"] = field(default_factory=list)

        @dataclass
        class Symbol:
            name: str
            node: Optional[Node] = None

        @dataclass(frozen=True)
        class Span:
            line: int
            column: int

        def duplicate(node):
            return copy.deepcopy(node)

        def duplicate_again(node):
            return clone(node)

        def shallow(node):
            return copy.copy(node)
    """})
    assert {caller for caller, _, _ in result.deepcopy_calls} == {"pkg.m:duplicate", "pkg.m:duplicate_again"}
    assert {(f.cls, f.kind) for f in result.dataclass_findings} == {
        ("pkg.m:Node", "eq"),
        ("pkg.m:Node", "repr"),
        ("pkg.m:Symbol", "eq"),
        ("pkg.m:Symbol", "repr"),
    }


# --------------------------------------------------------------------------
# Ratchet over a7/
# --------------------------------------------------------------------------

# This list must only shrink. Each entry is a recursive group that still exists
# in a7/, identified by the sorted qualified names of its members. Do not add
# to it: convert the new recursion to an explicit stack instead. See the
# "No recursion anywhere in the compiler" section of docs/plan/execution.md.
KNOWN_RECURSIVE_GROUPS = {
    (
        "a7.backends.zig:ZigCodeGenerator._emit_address_of",
        "a7.backends.zig:ZigCodeGenerator._emit_array_init",
        "a7.backends.zig:ZigCodeGenerator._emit_binary_iterative",
        "a7.backends.zig:ZigCodeGenerator._emit_call",
        "a7.backends.zig:ZigCodeGenerator._emit_cast",
        "a7.backends.zig:ZigCodeGenerator._emit_deref",
        "a7.backends.zig:ZigCodeGenerator._emit_expr",
        "a7.backends.zig:ZigCodeGenerator._emit_field_access",
        "a7.backends.zig:ZigCodeGenerator._emit_if_expr",
        "a7.backends.zig:ZigCodeGenerator._emit_implicit_ref_field_base",
        "a7.backends.zig:ZigCodeGenerator._emit_index",
        "a7.backends.zig:ZigCodeGenerator._emit_match_condition_zig",
        "a7.backends.zig:ZigCodeGenerator._emit_match_expr",
        "a7.backends.zig:ZigCodeGenerator._emit_match_expr_with_captures",
        "a7.backends.zig:ZigCodeGenerator._emit_match_pattern_condition_zig",
        "a7.backends.zig:ZigCodeGenerator._emit_new_expr",
        "a7.backends.zig:ZigCodeGenerator._emit_pattern",
        "a7.backends.zig:ZigCodeGenerator._emit_slice",
        "a7.backends.zig:ZigCodeGenerator._emit_slice_bound",
        "a7.backends.zig:ZigCodeGenerator._emit_struct_init",
        "a7.backends.zig:ZigCodeGenerator._emit_type_leaf",
        "a7.backends.zig:ZigCodeGenerator._emit_type_node",
        "a7.backends.zig:ZigCodeGenerator._emit_unary",
    ),
    (
        "a7.backends.zig:ZigCodeGenerator._emit_fall_case_body",
        "a7.backends.zig:ZigCodeGenerator._emit_fall_else_body",
        "a7.backends.zig:ZigCodeGenerator._visit_block",
        "a7.backends.zig:ZigCodeGenerator._visit_block_inline",
        "a7.backends.zig:ZigCodeGenerator._visit_defer",
        "a7.backends.zig:ZigCodeGenerator._visit_else_chain",
        "a7.backends.zig:ZigCodeGenerator._visit_for",
        "a7.backends.zig:ZigCodeGenerator._visit_for_in",
        "a7.backends.zig:ZigCodeGenerator._visit_for_in_indexed",
        "a7.backends.zig:ZigCodeGenerator._visit_function",
        "a7.backends.zig:ZigCodeGenerator._visit_if_stmt",
        "a7.backends.zig:ZigCodeGenerator._visit_match",
        "a7.backends.zig:ZigCodeGenerator._visit_match_as_if_chain",
        "a7.backends.zig:ZigCodeGenerator._visit_match_with_fall",
        "a7.backends.zig:ZigCodeGenerator._visit_program",
        "a7.backends.zig:ZigCodeGenerator._visit_switch_block",
        "a7.backends.zig:ZigCodeGenerator._visit_while",
        "a7.backends.zig:ZigCodeGenerator.visit",
    ),
    (
        "a7.backends.zig:ZigCodeGenerator._emit_semantic_type",
    ),
    (
        "a7.parser:Parser._parse_call_argument",
        "a7.parser:Parser._parse_inline_struct_init",
        "a7.parser:Parser.parse_array_literal",
        "a7.parser:Parser.parse_binary_expression",
        "a7.parser:Parser.parse_builtin_intrinsic",
        "a7.parser:Parser.parse_call_expression",
        "a7.parser:Parser.parse_cast_expression",
        "a7.parser:Parser.parse_expression",
        "a7.parser:Parser.parse_if_expression",
        "a7.parser:Parser.parse_index_expression",
        "a7.parser:Parser.parse_match_expression",
        "a7.parser:Parser.parse_new_expression",
        "a7.parser:Parser.parse_pattern",
        "a7.parser:Parser.parse_postfix_expression",
        "a7.parser:Parser.parse_primary_expression",
        "a7.parser:Parser.parse_primary_pattern",
        "a7.parser:Parser.parse_struct_literal",
        "a7.parser:Parser.parse_type",
        "a7.parser:Parser.parse_type_set",
        "a7.parser:Parser.parse_unary_expression",
    ),
    (
        "a7.parser:Parser.parse_block",
        "a7.parser:Parser.parse_defer_statement",
        "a7.parser:Parser.parse_for_statement",
        "a7.parser:Parser.parse_function_decl_with_name",
        "a7.parser:Parser.parse_if_statement",
        "a7.parser:Parser.parse_match_statement",
        "a7.parser:Parser.parse_statement",
        "a7.parser:Parser.parse_while_statement",
    ),
    (
        "a7.passes.semantic_validator:SemanticValidationPass._schedule_parameter_call_positions",
    ),
    (
        "a7.passes.semantic_validator:SemanticValidationPass._schedule_statement_calls",
    ),
    (
        "a7.passes.semantic_validator:SemanticValidationPass.visit_defer_stmt",
        "a7.passes.semantic_validator:SemanticValidationPass.visit_statement",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._check_array_initializer_assignable",
        "a7.passes.type_checker:TypeCheckingPass._is_initializer_assignable_to",
        "a7.passes.type_checker:TypeCheckingPass._resolve_pattern_type",
        "a7.passes.type_checker:TypeCheckingPass._validate_match_pattern",
        "a7.passes.type_checker:TypeCheckingPass._visit_expression_impl",
        "a7.passes.type_checker:TypeCheckingPass._visit_stdlib_module_call",
        "a7.passes.type_checker:TypeCheckingPass._visit_union_init",
        "a7.passes.type_checker:TypeCheckingPass.visit_address_of",
        "a7.passes.type_checker:TypeCheckingPass.visit_array_init",
        "a7.passes.type_checker:TypeCheckingPass.visit_binary_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_call_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_cast",
        "a7.passes.type_checker:TypeCheckingPass.visit_deref",
        "a7.passes.type_checker:TypeCheckingPass.visit_expression",
        "a7.passes.type_checker:TypeCheckingPass.visit_field_access",
        "a7.passes.type_checker:TypeCheckingPass.visit_if_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_index_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_match_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_slice_expr",
        "a7.passes.type_checker:TypeCheckingPass.visit_struct_init",
        "a7.passes.type_checker:TypeCheckingPass.visit_unary_expr",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._common_array_literal_element_type",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._format_match_pattern",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._range_const_expr_value",
        "a7.passes.type_checker:TypeCheckingPass._range_pattern_value",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._resolve_type_leaf",
        "a7.passes.type_checker:TypeCheckingPass.register_type_alias",
        "a7.passes.type_checker:TypeCheckingPass.resolve_type_node",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._statement_always_returns",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass._substitute_generic",
    ),
    (
        "a7.passes.type_checker:TypeCheckingPass.visit_for_in_stmt",
        "a7.passes.type_checker:TypeCheckingPass.visit_for_stmt",
        "a7.passes.type_checker:TypeCheckingPass.visit_if_stmt",
        "a7.passes.type_checker:TypeCheckingPass.visit_match_stmt",
        "a7.passes.type_checker:TypeCheckingPass.visit_statement",
        "a7.passes.type_checker:TypeCheckingPass.visit_while_stmt",
    ),
    (
        "a7.safety:SafetyProofPass._always_returns",
    ),
    (
        "a7.safety:SafetyProofPass._visit_expr",
    ),
    (
        "a7.safety:SafetyProofPass._visit_stmt",
    ),
}

# This list must only shrink (same rule and plan section as above).
KNOWN_DEEPCOPY_CALLERS = set()

# This list must only shrink (same rule and plan section as above). Each entry
# is (dataclass, generated method) where the generated method recurses.
KNOWN_RECURSIVE_DATACLASS_METHODS = {
    ("a7.ast_nodes:ASTNode", "eq"),
    ("a7.ast_nodes:ASTNode", "repr"),
    ("a7.module_resolver:ModuleInfo", "eq"),
    ("a7.module_resolver:ModuleInfo", "repr"),
    ("a7.safety:BackendPlan", "repr"),
    ("a7.safety:Obligation", "repr"),
    ("a7.safety:ProofResult", "repr"),
    ("a7.semantic_context:DeferContext", "eq"),
    ("a7.semantic_context:DeferContext", "repr"),
    ("a7.semantic_context:FunctionContext", "eq"),
    ("a7.semantic_context:FunctionContext", "repr"),
    ("a7.symbol_table:Symbol", "eq"),
    ("a7.symbol_table:Symbol", "repr"),
    ("a7.types:ArrayType", "repr"),
    ("a7.types:FunctionType", "repr"),
    ("a7.types:GenericInstanceType", "repr"),
    ("a7.types:GenericParamType", "repr"),
    ("a7.types:PointerType", "repr"),
    ("a7.types:ReferenceType", "repr"),
    ("a7.types:SliceType", "repr"),
    ("a7.types:StructField", "repr"),
    ("a7.types:StructType", "repr"),
    ("a7.types:TypeSet", "repr"),
    ("a7.types:UnionField", "repr"),
    ("a7.types:UnionType", "repr"),
}


@pytest.fixture(scope="module")
def a7_scan():
    return norec_scan.scan(A7_ROOT)


def test_no_new_recursion_in_a7(a7_scan):
    new = [g for g in a7_scan.groups if g not in KNOWN_RECURSIVE_GROUPS]
    assert not new, (
        "Recursion in a7/ that is not in KNOWN_RECURSIVE_GROUPS (convert it to an explicit stack; "
        "if a listed group lost members or split, replace its entry with the smaller groups; "
        "never add a member):\n"
        + "\n".join(f"- {a7_scan.describe_group(g)}" for g in new)
    )


def test_listed_recursive_groups_still_exist(a7_scan):
    gone = sorted(KNOWN_RECURSIVE_GROUPS - set(a7_scan.groups))
    assert not gone, (
        "These groups are no longer found in a7/; delete them from KNOWN_RECURSIVE_GROUPS:\n"
        + "\n".join(f"- {', '.join(g)}" for g in gone)
    )


def test_no_new_deepcopy_calls_in_a7(a7_scan):
    new = sorted({(c, p, line) for c, p, line in a7_scan.deepcopy_calls if c not in KNOWN_DEEPCOPY_CALLERS})
    assert not new, "copy.deepcopy calls in a7/ not in KNOWN_DEEPCOPY_CALLERS:\n" + "\n".join(
        f"- {c} ({p}:{line})" for c, p, line in new
    )


def test_listed_deepcopy_callers_still_call_deepcopy(a7_scan):
    gone = sorted(KNOWN_DEEPCOPY_CALLERS - {c for c, _, _ in a7_scan.deepcopy_calls})
    assert not gone, "No longer calling copy.deepcopy; delete from KNOWN_DEEPCOPY_CALLERS:\n" + "\n".join(
        f"- {c}" for c in gone
    )


def test_no_new_recursive_dataclass_methods_in_a7(a7_scan):
    new = [f for f in a7_scan.dataclass_findings if (f.cls, f.kind) not in KNOWN_RECURSIVE_DATACLASS_METHODS]
    assert not new, (
        "Dataclasses in a7/ whose generated method recurses (pass eq=False/repr=False or exclude the field), "
        "not in KNOWN_RECURSIVE_DATACLASS_METHODS:\n"
        + "\n".join(
            f"- {f.cls} __{f.kind}__ ({f.path}:{f.line}) via fields {', '.join(f.fields)}" for f in new
        )
    )


def test_listed_recursive_dataclass_methods_still_exist(a7_scan):
    found = {(f.cls, f.kind) for f in a7_scan.dataclass_findings}
    gone = sorted(KNOWN_RECURSIVE_DATACLASS_METHODS - found)
    assert not gone, "No longer recursive; delete from KNOWN_RECURSIVE_DATACLASS_METHODS:\n" + "\n".join(
        f"- {c} __{k}__" for c, k in gone
    )

@pytest.mark.parametrize("source, expected", [
    ("""
        class Walker:
            def walk(self, kind):
                return self.handlers[kind](self, kind)
            def block(self, kind):
                return self.walk(kind)
            handlers = {"block": block}
    """, ("pkg.m:Walker.block", "pkg.m:Walker.walk")),
    ("""
        class Walker:
            def __init__(self):
                self.handlers = {"block": self.block}
            def walk(self, kind):
                return self.handlers[kind](kind)
            def block(self, kind):
                return self.walk(kind)
    """, ("pkg.m:Walker.block", "pkg.m:Walker.walk")),
    ("""
        def walk(kind):
            return handlers[kind](kind)
        def block(kind):
            return walk(kind)
        handlers = {"block": block}
    """, ("pkg.m:block", "pkg.m:walk")),
])
def test_stored_dispatch_tables_preserve_recursive_call_edges(tmp_path, source, expected):
    result = scan_sources(tmp_path, {"m.py": source})
    assert result.groups == [expected]
    assert expected[1] in result.edges[expected[0]]
    assert expected[0] in result.edges[expected[1]]


def test_nonrecursive_dispatch_table_stays_nonrecursive(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Walker:
            def __init__(self):
                self.handlers = {"leaf": self.leaf}
            def walk(self, kind):
                return self.handlers[kind]()
            def leaf(self):
                return 1
    """})
    assert result.groups == []
    assert "pkg.m:Walker.leaf" in result.edges["pkg.m:Walker.walk"]


def test_continuation_stack_does_not_call_the_scheduling_frame(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Driver:
            def __init__(self):
                self.work = []
            def run(self):
                while self.work:
                    callback = self.work.pop()
                    callback()
            def step(self):
                self.work.append(lambda: self.step())
    """})
    assert result.groups == []
    callback = next(q for q in result.functions if "<lambda@" in q)
    assert callback in result.edges["pkg.m:Driver.run"]
    assert result.edges[callback] == {"pkg.m:Driver.step"}
    assert callback not in result.edges.get("pkg.m:Driver.step", ())


@pytest.mark.parametrize("body", [
    "(lambda: self.step())()",
    "callback = lambda: self.step(); callback()",
    "self.callback = lambda: self.step(); self.callback()",
    "work = [lambda: self.step()]; work.pop()()",
])
def test_synchronously_invoked_lambda_still_reports_recursion(tmp_path, body):
    result = scan_sources(tmp_path, {"m.py": f"""
        class Driver:
            def step(self):
                {body}
    """})
    callback = next(q for q in result.functions if "<lambda@" in q)
    assert result.groups == [tuple(sorted(("pkg.m:Driver.step", callback)))]


def test_callback_parameter_invoking_lambda_preserves_cycle(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        def invoke(callback):
            return callback()
        def repeat():
            return invoke(lambda: repeat())
    """})
    callback = next(q for q in result.functions if "<lambda@" in q)
    assert result.groups == [tuple(sorted(("pkg.m:invoke", "pkg.m:repeat", callback)))]


def test_unannotated_attribute_delegation_is_unresolved_not_a_self_loop(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Worker:
            def run(self):
                return 1
        class Proxy:
            def __init__(self, worker):
                self.worker = worker
            def run(self):
                return self.worker.run()
    """})
    assert result.groups == []
    unresolved = [item for item in result.unresolved if item.caller == "pkg.m:Proxy.run"]
    assert len(unresolved) == 1
    assert unresolved[0].candidates == ("pkg.m:Proxy.run", "pkg.m:Worker.run")


def test_unresolved_edges_retain_possible_unannotated_back_reference(tmp_path):
    source = """
        class Owner:
            def __init__(self, worker):
                self.worker = worker
            def run(self):
                return self.worker.run()
    """
    result = scan_sources(tmp_path, {"m.py": source})
    assert result.groups == []
    conservative = norec_scan.scan(tmp_path / "pkg", include_unresolved=True)
    assert conservative.groups == [("pkg.m:Owner.run",)]


def test_unresolved_edges_do_not_change_a7_recursive_groups(a7_scan):
    conservative = norec_scan.scan(A7_ROOT, include_unresolved=True)
    assert conservative.groups == a7_scan.groups


@pytest.mark.parametrize("access", ["methods['leaf']()", "methods.get('leaf')()"])
def test_constant_dictionary_key_does_not_call_other_handlers(tmp_path, access):
    result = scan_sources(tmp_path, {"m.py": f"""
        class Worker:
            def run(self):
                methods = {{"recur": self.run, "leaf": self.leaf}}
                return {access}
            def leaf(self):
                return 1
    """})
    assert result.groups == []
    assert result.edges["pkg.m:Worker.run"] == {"pkg.m:Worker.leaf"}


def test_dynamic_dictionary_key_retains_all_possible_handlers(tmp_path):
    result = scan_sources(tmp_path, {"m.py": """
        class Worker:
            def run(self, key):
                methods = {"recur": self.run, "leaf": self.leaf}
                return methods[key](key)
            def leaf(self, key):
                return 1
    """})
    assert result.groups == [("pkg.m:Worker.run",)]
    assert result.edges["pkg.m:Worker.run"] == {"pkg.m:Worker.run", "pkg.m:Worker.leaf"}
