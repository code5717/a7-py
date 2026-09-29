"""Static recursion scanner for a Python package.

Used by ``test/test_no_recursion.py`` to enforce the rule that no function in
``a7/`` calls itself directly or through other functions. The scanner is
iterative itself: every traversal uses an explicit stack.

What it builds:

* A call graph over every function, method and nested function in the package
  (qualified names ``module:Class.method.inner``).
* Strongly connected components of that graph (iterative Tarjan). Each
  component with more than one member, and each self-loop, is a recursive group.
* ``copy.deepcopy`` call sites (the standard library implementation recurses).
* Dataclasses whose generated ``__eq__``, ``__repr__`` or ``__hash__`` recurses:
  a field can hold an instance of the same dataclass (or of a base of it), or
  an instance of another dataclass whose generated method of the same kind is
  already flagged (this covers dataclasses that hold AST nodes).

Call resolution rules (receiver-aware, so delegation to another class is not a
cycle):

* ``self.m`` / ``cls.m`` inside class C: ``m`` looked up in C's in-package MRO,
  plus every override of ``m`` in an in-package subclass of C (virtual dispatch).
  No in-package definition means no edge.
* ``super().m``: ``m`` of the next in-package class in C's MRO.
* ``ClassName.m`` and ``module.f``: that exact definition.
* A bare name: a nested function of an enclosing function, then a module-level
  function or class of the same module, then a name imported from another
  package module. Calling a class adds edges to its ``__new__``, ``__init__``
  and ``__post_init__``. Loading a function or method without calling it also
  adds an edge (the reference can be stored and called later).
* ``x.m`` where the class of ``x`` is inferred: ``m`` of that class plus
  subclass overrides. Inference uses parameter, variable, return and attribute
  annotations (including dataclass fields, ``@property`` return types and
  container element types), constructor calls, and assignments from other
  inferred expressions (``self.a = self.b``, ``x = self.items[-1]``,
  ``for x in self.items``, ``zip``/``enumerate``/``.items()`` loops). A call
  to a capitalised name from outside the package is taken to build a
  non-package object.
* ``x.m`` where inference fails: edges to methods named ``m`` in the caller's
  class, its in-package bases, and every subclass of those; any other
  in-package method named ``m`` is recorded as an unresolved call, not an edge.
  An untyped ``self.attribute`` receiver has no assumed relationship to its
  owner's class; all matching methods are recorded as unresolved candidates.
* Callable dictionaries assigned at module, class or instance scope are followed
  through subscript and ``get`` calls. Dynamic keys conservatively reach every
  stored value. Local callable assignments and list/queue insertion and removal
  are followed too.
* Lambdas have separate call-graph nodes. Creating or queuing a lambda does not
  execute its body; invoking it, including through a callback parameter, does.
* ``getattr(recv, <constant prefix> ...)`` (f-string, ``+``, ``%`` or
  ``.format`` with a constant prefix): edges to every method of the receiver's
  class hierarchy whose name starts with the prefix. ``getattr(recv, "name")``
  resolves like ``recv.name``.
* Callbacks: when a function calls one of its parameters, every call to it
  adds edges from it to the functions and methods passed as arguments.
* Implicit dunder calls: f-string interpolation, ``str``, ``print``, ``format``
  and ``"%s" %`` call ``__str__`` (falling back to ``__repr__``); ``repr`` and
  ``!r`` call ``__repr__``; ``hash`` calls ``__hash__``; ``len`` calls
  ``__len__``; ``==``/``!=`` call ``__eq__``/``__ne__``; calling an instance of
  an inferred class calls ``__call__``. Tuple and list operands, and container
  types, apply the call to their elements (sets excepted for ``hash``).

Limits (not modelled): calls made from class bodies and module-level code
(they cannot be part of a cycle), operators other than ``==``/``!=``, iteration
protocols, descriptors other than ``@property``, ``exec``/``eval``, and
dictionary mutation through item assignment, arbitrary container protocols,
``singledispatch`` registrations, and callable factories with inferred returns. The MRO is a depth-first left-to-right walk of in-package bases, not
C3.
"""

from __future__ import annotations

import argparse
import ast
import builtins
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# A type is a pair (instance classes, element classes). Each component is a
# frozenset of in-package class keys, or None when unknown. An empty set means
# "known, and not an in-package class" (for example ``str``).
EMPTY: frozenset = frozenset()
BOTTOM = (EMPTY, EMPTY)
TOP = (None, None)


class _BotSet(frozenset):
    """Marker for "no information yet" during fixpoint iteration."""


BOT = _BotSet()
UNSET = (BOT, BOT)

_MAX_ROUNDS = 25

_BUILTIN_NAMES = frozenset(dir(builtins))
_ANY_NAMES = frozenset({"Any", "object"})
_SEQ_CONTAINERS = frozenset({
    "List", "list", "Set", "set", "FrozenSet", "frozenset", "Sequence",
    "MutableSequence", "Iterable", "Iterator", "Deque", "deque", "AbstractSet",
    "Collection", "Generator", "Reversible", "KeysView", "ValuesView",
})
_TUPLE_CONTAINERS = frozenset({"Tuple", "tuple"})
_MAP_CONTAINERS = frozenset({
    "Dict", "dict", "Mapping", "MutableMapping", "DefaultDict", "defaultdict",
    "OrderedDict", "ChainMap", "Counter",
})
_UNWRAP_FIRST = frozenset({"Annotated", "ClassVar", "Final", "InitVar", "Required", "NotRequired"})
_BUILTIN_ITER_CTORS = frozenset({"list", "tuple", "set", "frozenset", "sorted", "reversed"})
_STR_DUNDER_BUILTINS = frozenset({"str", "format", "print"})


def _join(a, b):
    if a is BOT:
        return b
    if b is BOT:
        return a
    if a is None or b is None:
        return None
    return frozenset(a | b)


def _tag(x):
    return "unset" if x is BOT else x


def _frozen(env: dict) -> dict:
    return {k: (_tag(v[0]), _tag(v[1])) for k, v in env.items()}


def _unset_to_top(p):
    return (None if p[0] is BOT else p[0], None if p[1] is BOT else p[1])


def _join_pair(p, q):
    return (_join(p[0], q[0]), _join(p[1], q[1]))


@dataclass(eq=False)
class _Class:
    key: str
    module: str
    name: str
    node: ast.ClassDef
    path: str
    base_exprs: list
    bases: list = field(default_factory=list)
    ext_bases: list = field(default_factory=list)
    methods: dict = field(default_factory=dict)
    properties: set = field(default_factory=set)
    own_names: set = field(default_factory=set)
    ann: dict = field(default_factory=dict)  # attr -> (module, annotation expr)
    dataclass_opts: Optional[dict] = None
    fields: list = field(default_factory=list)  # (name, annotation, compare, repr, hash)


@dataclass(eq=False)
class _Func:
    qual: str
    module: str
    node: object
    path: str
    line: int
    cls: Optional[str]
    self_name: Optional[str]
    self_is_class: bool
    parent: Optional["_Func"] = field(repr=False)
    is_module: bool = False
    is_method: bool = False
    calls_params: bool = False
    params: set = field(default_factory=set)
    local_defs: dict = field(default_factory=dict)
    local_classes: dict = field(default_factory=dict)
    declared: dict = field(default_factory=dict)
    assigns: list = field(default_factory=list)  # (name, kind, expr)
    env: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Unresolved:
    caller: str
    name: str
    path: str
    line: int
    candidates: tuple


@dataclass(frozen=True)
class DataclassFinding:
    cls: str
    kind: str  # "eq", "repr" or "hash"
    path: str
    line: int
    fields: tuple  # fields whose values reach the recursion
    holds: tuple  # the classes those fields can hold that make it recursive


@dataclass
class ScanResult:
    functions: dict  # qual -> (path, line)
    edges: dict  # qual -> set of qual
    edge_lines: dict  # (caller, callee) -> first line of the call in caller
    groups: list  # sorted tuples of qualified names
    deepcopy_calls: list  # (caller qual, path, line)
    dataclass_findings: list  # DataclassFinding
    unchecked_dataclass_fields: list  # (class key, field name, path, line)
    unresolved: list  # Unresolved

    def location(self, qual: str) -> str:
        path, line = self.functions[qual]
        return f"{path}:{line}"

    def describe_group(self, group: Iterable[str]) -> str:
        return ", ".join(f"{q} ({self.location(q)})" for q in group)


class _Scanner:
    def __init__(self, root: Path, package: str):
        self.root = root
        self.package = package
        self.modules: dict = {}  # module name -> (path str, tree, is_package)
        self.defs: dict = {}  # module -> name -> ("func", q) | ("class", k) | ("var", module, name)
        self.imports: dict = {}  # module -> name -> ("import", module) | ("from", module, name)
        self.classes: dict = {}
        self.funcs: dict = {}
        self.func_list: list = []
        self.module_funcs: dict = {}  # module -> pseudo _Func for module-level code
        self.methods_by_name: dict = {}
        self.property_names: set = set()
        self.attr_assigns: list = []  # (class key, attr, fn, kind, expr)
        self.attr_values: dict = {}
        self._mro_cache: dict = {}
        self._children: dict = {}
        self._sub_cache: dict = {}
        self._ann_cache: dict = {}
        self.edges: dict = {}
        self.edge_lines: dict = {}
        self._line = 0
        self.unresolved: list = []
        self.deepcopy_calls: list = []
        self.include_unresolved = False
        self.lambda_funcs: dict = {}
        self.class_values: dict = {}
        self.container_values: dict = {}

    # ------------------------------------------------------------------ loading
    def load(self) -> None:
        for path in sorted(self.root.rglob("*.py")):
            rel = path.relative_to(self.root)
            parts = list(rel.with_suffix("").parts)
            is_pkg = parts[-1] == "__init__"
            if is_pkg:
                parts = parts[:-1]
            mod = ".".join([self.package] + parts)
            display = str(Path(self.package) / rel)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            self.modules[mod] = (display, tree, is_pkg)
            self.defs[mod] = {}
            self.imports[mod] = {}
        for mod, (display, tree, is_pkg) in self.modules.items():
            self._collect_imports(mod, tree, is_pkg)
            self._collect_defs(mod, display, tree)
        self._collect_lambdas()
        for cls in self.classes.values():
            context = _Func(f"{cls.key}.<body>", cls.module, cls.node, cls.path,
                            cls.node.lineno, cls.key, None, False, None)
            context.local_defs.update(cls.methods)
            for node in cls.node.body:
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                    for name in _assigned_names(node):
                        self.class_values.setdefault((cls.key, name), []).append((context, node.value))
            for expr in cls.base_exprs:
                r = self._static_module(cls.module, expr)
                if r and r[0] == "class":
                    cls.bases.append(r[1])
                elif r and r[0] == "ext":
                    cls.ext_bases.append(r[1])
        self._children = {}
        for cls in self.classes.values():
            for b in cls.bases:
                self._children.setdefault(b, []).append(cls.key)
        for cls in self.classes.values():
            self._collect_dataclass(cls)
        for fn in self.func_list:
            self._collect_locals(fn)

    def _collect_lambdas(self) -> None:
        pending = list(self.module_funcs.values()) + self.func_list
        index = 0
        while index < len(pending):
            owner = pending[index]
            index += 1
            for node in self._body_nodes(owner):
                if not isinstance(node, ast.Lambda) or id(node) in self.lambda_funcs:
                    continue
                qual = f"{owner.qual}.<lambda@{node.lineno}:{node.col_offset}>"
                fn = _Func(qual, owner.module, node, owner.path, node.lineno,
                           owner.cls, owner.self_name, owner.self_is_class, owner)
                self.lambda_funcs[id(node)] = qual
                self.funcs[qual] = fn
                self.func_list.append(fn)
                pending.append(fn)

    def _abs_module(self, mod: str, is_pkg: bool, node: ast.ImportFrom) -> str:
        if not node.level:
            return node.module or ""
        parts = mod.split(".")
        drop = node.level - 1 if is_pkg else node.level
        base = parts[: len(parts) - drop] if drop else parts
        if node.module:
            base = base + node.module.split(".")
        return ".".join(base)

    def _collect_imports(self, mod: str, tree: ast.Module, is_pkg: bool) -> None:
        table = self.imports[mod]
        local = {}
        top_ids = {id(n) for n in tree.body}
        for node in ast.walk(tree):
            target = table if id(node) in top_ids else local
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        target.setdefault(alias.asname, ("import", alias.name))
                    else:
                        head = alias.name.split(".")[0]
                        target.setdefault(head, ("import", head))
            elif isinstance(node, ast.ImportFrom):
                src = self._abs_module(mod, is_pkg, node)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    target.setdefault(alias.asname or alias.name, ("from", src, alias.name))
        for name, value in local.items():
            table.setdefault(name, value)

    def _collect_defs(self, mod: str, display: str, tree: ast.Module) -> None:
        modfn = _Func(f"{mod}:<module>", mod, tree, display, 1, None, None, False, None, is_module=True)
        self.module_funcs[mod] = modfn
        stack = [(n, "", None, None) for n in reversed(tree.body)]
        while stack:
            node, prefix, ckey, pfunc = stack.pop()
            if isinstance(node, ast.ClassDef):
                key = f"{mod}:{prefix}{node.name}"
                cls = self.classes.get(key)
                if cls is None:
                    cls = _Class(key, mod, node.name, node, display, list(node.bases))
                    self.classes[key] = cls
                if pfunc is not None:
                    pfunc.local_classes[node.name] = key
                elif ckey is None:
                    self.defs[mod].setdefault(node.name, ("class", key))
                if ckey is not None:
                    self.classes[ckey].own_names.add(node.name)
                for child in reversed(node.body):
                    stack.append((child, f"{prefix}{node.name}.", key, pfunc))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{mod}:{prefix}{node.name}"
                decos = {self._deco_name(d) for d in node.decorator_list}
                if ckey is not None:
                    cls = self.classes[ckey]
                    cls.own_names.add(node.name)
                    cls.methods.setdefault(node.name, qual)
                    if "property" in decos or "cached_property" in decos:
                        cls.properties.add(node.name)
                        self.property_names.add(node.name)
                    positional = node.args.posonlyargs + node.args.args
                    if "staticmethod" in decos or not positional:
                        owner, self_name, is_cls = ckey, None, False
                    else:
                        owner, self_name = ckey, positional[0].arg
                        is_cls = "classmethod" in decos
                elif pfunc is not None:
                    owner, self_name, is_cls = pfunc.cls, pfunc.self_name, pfunc.self_is_class
                    pfunc.local_defs.setdefault(node.name, qual)
                else:
                    owner, self_name, is_cls = None, None, False
                    self.defs[mod].setdefault(node.name, ("func", qual))
                fn = self.funcs.get(qual)
                if fn is None:
                    fn = _Func(qual, mod, node, display, node.lineno, owner, self_name, is_cls, pfunc)
                    fn.is_method = ckey is not None and self_name is not None
                    self.funcs[qual] = fn
                    self.func_list.append(fn)
                    if ckey is not None:
                        self.methods_by_name.setdefault(node.name, []).append(qual)
                else:
                    # Conditional redefinition or property setter: same node in the graph.
                    fn.node = _MergedBody(fn.node, node)
                for child in reversed(node.body):
                    stack.append((child, f"{prefix}{node.name}.", None, fn))
            else:
                if pfunc is None and ckey is None:
                    for name in _assigned_names(node):
                        self.defs[mod].setdefault(name, ("var", mod, name))
                if ckey is not None and pfunc is None:
                    cls = self.classes[ckey]
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                        cls.ann.setdefault(node.target.id, (mod, node.annotation))
                        cls.own_names.add(node.target.id)
                    for name in _assigned_names(node):
                        cls.own_names.add(name)
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.stmt, ast.excepthandler, ast.match_case)):
                        stack.append((child, prefix, ckey, pfunc))

    @staticmethod
    def _deco_name(expr) -> str:
        if isinstance(expr, ast.Call):
            expr = expr.func
        if isinstance(expr, ast.Attribute):
            return expr.attr
        if isinstance(expr, ast.Name):
            return expr.id
        return ""

    # --------------------------------------------------------- name resolution
    def _resolve_global(self, mod: str, name: str):
        seen = set()
        while (mod, name) not in seen:
            seen.add((mod, name))
            if mod not in self.defs:
                return ("ext", f"{mod}.{name}")
            if name in self.defs[mod]:
                return self.defs[mod][name]
            imp = self.imports[mod].get(name)
            if imp is None:
                if f"{mod}.{name}" in self.modules:
                    return ("module", f"{mod}.{name}")
                return None
            if imp[0] == "import":
                return ("module", imp[1]) if imp[1] in self.modules else ("ext", imp[1])
            src, src_name = imp[1], imp[2]
            if f"{src}.{src_name}" in self.modules:
                return ("module", f"{src}.{src_name}")
            if src not in self.modules:
                return ("ext", f"{src}.{src_name}")
            mod, name = src, src_name
        return None

    def _step_attr(self, resolved, attr: str):
        if resolved is None:
            return None
        kind = resolved[0]
        if kind == "module":
            r = self._resolve_global(resolved[1], attr)
            if r is None and f"{resolved[1]}.{attr}" in self.modules:
                return ("module", f"{resolved[1]}.{attr}")
            return r
        if kind == "ext":
            return ("ext", f"{resolved[1]}.{attr}")
        if kind == "builtin":
            return ("ext", f"builtins.{resolved[1]}.{attr}")
        if kind == "class":
            nested = f"{resolved[1]}.{attr}"
            if nested in self.classes:
                return ("class", nested)
            q = self._lookup_mro(resolved[1], attr)
            if q is not None:
                return ("method", q)
            return None
        return None

    @staticmethod
    def _attr_chain(expr):
        names = []
        while isinstance(expr, ast.Attribute):
            names.append(expr.attr)
            expr = expr.value
        if not isinstance(expr, ast.Name):
            return None, None
        names.reverse()
        return expr.id, names

    def _static_module(self, mod: str, expr):
        """Resolve a Name/Attribute chain at module scope."""
        base, names = self._attr_chain(expr)
        if base is None:
            return None
        r = self._resolve_global(mod, base)
        if r is None and base in _BUILTIN_NAMES:
            r = ("builtin", base)
        for attr in names:
            r = self._step_attr(r, attr)
        return r

    def _resolve_name(self, fn: _Func, name: str):
        f = fn
        while f is not None and not f.is_module:
            if name in f.local_defs:
                return ("func", f.local_defs[name])
            if name in f.local_classes:
                return ("class", f.local_classes[name])
            if name in f.env or name in f.declared:
                return ("local", f)
            f = f.parent
        r = self._resolve_global(fn.module, name)
        if r is None and name in _BUILTIN_NAMES:
            return ("builtin", name)
        return r

    def _static(self, fn: _Func, expr):
        base, names = self._attr_chain(expr)
        if base is None:
            return None
        r = self._resolve_name(fn, base)
        if r is None or r[0] in ("local", "var"):
            return None if not names else ("dynamic",)
        for attr in names:
            r = self._step_attr(r, attr)
        return r

    # ---------------------------------------------------------------- classes
    def _mro(self, key: str) -> list:
        cached = self._mro_cache.get(key)
        if cached is not None:
            return cached
        order, seen, stack = [], set(), [key]
        while stack:
            k = stack.pop()
            if k in seen or k not in self.classes:
                continue
            seen.add(k)
            order.append(k)
            stack.extend(reversed(self.classes[k].bases))
        self._mro_cache[key] = order
        return order

    def _subclasses(self, key: str) -> list:
        cached = self._sub_cache.get(key)
        if cached is not None:
            return cached
        out, seen, stack = [], {key}, list(self._children.get(key, []))
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
            stack.extend(self._children.get(k, []))
        self._sub_cache[key] = sorted(out)
        return self._sub_cache[key]

    def _lookup_mro(self, key: str, name: str) -> Optional[str]:
        for k in self._mro(key):
            q = self.classes[k].methods.get(name)
            if q is not None:
                return q
        return None

    def _virtual(self, key: str, name: str) -> set:
        out = set()
        q = self._lookup_mro(key, name)
        if q is not None:
            out.add(q)
        for s in self._subclasses(key):
            q = self.classes[s].methods.get(name)
            if q is not None:
                out.add(q)
        return out

    def _ctor_targets(self, key: str, virtual: bool = False) -> set:
        out = set()
        for name in ("__new__", "__init__", "__post_init__"):
            if virtual:
                out |= self._virtual(key, name)
            else:
                q = self._lookup_mro(key, name)
                if q is not None:
                    out.add(q)
        return out

    # ------------------------------------------------------------ annotations
    def _ann_pair(self, mod: str, expr):
        cache_key = (mod, id(expr))
        if cache_key in self._ann_cache:
            return self._ann_cache[cache_key]
        results, parsed = {}, {}
        stack = [(expr, False)]
        while stack:
            node, ready = stack.pop()
            if not ready:
                stack.append((node, True))
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    try:
                        p = ast.parse(node.value.strip(), mode="eval").body
                    except SyntaxError:
                        p = None
                    if p is not None:
                        parsed[id(node)] = p
                        stack.append((p, False))
                elif isinstance(node, ast.Subscript):
                    stack.append((node.slice, False))
                elif isinstance(node, ast.Tuple):
                    stack.extend((e, False) for e in node.elts)
                elif isinstance(node, ast.BinOp):
                    stack.append((node.left, False))
                    stack.append((node.right, False))
                continue
            results[id(node)] = self._ann_node(mod, node, results, parsed)
        pair = results[id(expr)]
        self._ann_cache[cache_key] = pair
        return pair

    def _head_name(self, mod: str, expr):
        r = self._static_module(mod, expr)
        if r is None:
            return None, None
        if r[0] == "class":
            return "class", r[1]
        if r[0] in ("ext", "builtin"):
            return "ext", r[1].split(".")[-1]
        return None, None

    def _ann_node(self, mod, node, results, parsed):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                p = parsed.get(id(node))
                return results.get(id(p), TOP) if p is not None else TOP
            return BOTTOM
        if isinstance(node, (ast.Name, ast.Attribute)):
            kind, name = self._head_name(mod, node)
            if kind == "class":
                return (frozenset({name}), EMPTY)
            if kind == "ext":
                if name in _ANY_NAMES:
                    return TOP
                if name in _SEQ_CONTAINERS or name in _TUPLE_CONTAINERS or name in _MAP_CONTAINERS:
                    return (EMPTY, None)
                if name in ("Type", "type"):
                    return TOP
                return BOTTOM
            return TOP
        if isinstance(node, ast.Tuple):
            out = BOTTOM
            for e in node.elts:
                out = _join_pair(out, results[id(e)])
            return out
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return _join_pair(results[id(node.left)], results[id(node.right)])
        if isinstance(node, ast.Subscript):
            kind, name = self._head_name(mod, node.value)
            args = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if kind == "class":
                return (frozenset({name}), EMPTY)
            if kind != "ext":
                return TOP
            if name == "Optional":
                return results[id(node.slice)]
            if name == "Union":
                return results[id(node.slice)]
            if name in _UNWRAP_FIRST:
                return results[id(args[0])]
            if name in _SEQ_CONTAINERS:
                return (EMPTY, results[id(args[0])][0])
            if name in _TUPLE_CONTAINERS:
                elem = EMPTY
                for a in args:
                    if isinstance(a, ast.Constant) and a.value is Ellipsis:
                        continue
                    elem = _join(elem, results[id(a)][0])
                return (EMPTY, elem)
            if name in _MAP_CONTAINERS:
                return (EMPTY, results[id(args[-1])][0])
            if name in ("Type", "type"):
                return TOP
            return BOTTOM
        return TOP

    def _ann_classes(self, mod: str, expr):
        """Class keys named anywhere in an annotation, and whether Any/object appears."""
        found, has_any = set(), False
        stack = [expr]
        while stack:
            node = stack.pop()
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                try:
                    stack.append(ast.parse(node.value.strip(), mode="eval").body)
                except SyntaxError:
                    has_any = True
            elif isinstance(node, (ast.Name, ast.Attribute)):
                r = self._static_module(mod, node)
                if r is None:
                    has_any = True
                elif r[0] == "class":
                    found.add(r[1])
                elif r[0] in ("ext", "builtin") and r[1].split(".")[-1] in _ANY_NAMES:
                    has_any = True
            elif isinstance(node, ast.Subscript):
                stack.append(node.value)
                stack.append(node.slice)
            elif isinstance(node, (ast.Tuple, ast.List)):
                stack.extend(node.elts)
            elif isinstance(node, ast.BinOp):
                stack.append(node.left)
                stack.append(node.right)
        return found, has_any

    # -------------------------------------------------------------- dataclass
    def _collect_dataclass(self, cls: _Class) -> None:
        for deco in cls.node.decorator_list:
            target = deco.func if isinstance(deco, ast.Call) else deco
            r = self._static_module(cls.module, target)
            if r != ("ext", "dataclasses.dataclass"):
                continue
            opts = {"eq": True, "repr": True, "frozen": False, "unsafe_hash": False}
            if isinstance(deco, ast.Call):
                for kw in deco.keywords:
                    if kw.arg in opts:
                        v = kw.value
                        opts[kw.arg] = v.value if isinstance(v, ast.Constant) else True
            cls.dataclass_opts = opts
            for stmt in cls.node.body:
                if not (isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)):
                    continue
                head = stmt.annotation.value if isinstance(stmt.annotation, ast.Subscript) else stmt.annotation
                kind, name = self._head_name(cls.module, head)
                if kind == "ext" and name in ("ClassVar", "InitVar"):
                    continue
                if isinstance(stmt.annotation, ast.Constant) and "ClassVar" in str(stmt.annotation.value):
                    continue
                flags = {"compare": True, "repr": True, "hash": None}
                v = stmt.value
                if isinstance(v, ast.Call) and self._static_module(cls.module, v.func) == ("ext", "dataclasses.field"):
                    for kw in v.keywords:
                        if kw.arg in flags and isinstance(kw.value, ast.Constant):
                            flags[kw.arg] = kw.value.value
                cls.fields.append((stmt.target.id, stmt.annotation, flags, stmt.lineno))

    def dataclass_findings(self):
        generated = {}
        for cls in self.classes.values():
            o = cls.dataclass_opts
            if o is None:
                continue
            kinds = set()
            if o["eq"] and "__eq__" not in cls.own_names:
                kinds.add("eq")
            if o["repr"] and "__repr__" not in cls.own_names:
                kinds.add("repr")
            if "__hash__" not in cls.own_names and (o["unsafe_hash"] or (o["eq"] and o["frozen"])):
                kinds.add("hash")
            if kinds:
                generated[cls.key] = kinds
        field_info = {}
        unchecked = []
        for key in generated:
            entries = []
            for k in reversed(self._mro(key)):
                c = self.classes[k]
                if c.dataclass_opts is None:
                    continue
                for name, ann, flags, line in c.fields:
                    found, has_any = self._ann_classes(c.module, ann)
                    held = set(found)
                    for f in found:
                        held.update(self._subclasses(f))
                    entries.append((name, held, flags))
                    if has_any:
                        unchecked.append((key, name, c.path, line))
            field_info[key] = entries

        def included(flags, kind):
            if kind == "eq":
                return flags["compare"]
            if kind == "repr":
                return flags["repr"]
            h = flags["hash"]
            return flags["compare"] if h is None else h

        flagged = {}
        changed = True
        while changed:
            changed = False
            for key, kinds in generated.items():
                for kind in kinds:
                    reasons = set()
                    for name, held, flags in field_info[key]:
                        if not included(flags, kind):
                            continue
                        for h in held:
                            if h == key or (h, kind) in flagged:
                                reasons.add((name, h))
                    if reasons and flagged.get((key, kind)) != reasons:
                        flagged[(key, kind)] = reasons
                        changed = True
        out = []
        for (key, kind), reasons in sorted(flagged.items()):
            c = self.classes[key]
            out.append(DataclassFinding(
                key, kind, c.path, c.node.lineno,
                tuple(sorted({n for n, _ in reasons})), tuple(sorted({h for _, h in reasons})),
            ))
        unchecked = sorted(set(unchecked))
        return out, unchecked

    # ----------------------------------------------------------- local facts
    def _body_nodes(self, fn: _Func):
        """Nodes executed as part of fn's own frame (nested def bodies excluded)."""
        node = fn.node
        if fn.is_module:
            roots = [n for n in node.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        elif isinstance(node, ast.Lambda):
            roots = [node.body]
        elif isinstance(node, _MergedBody):
            roots = node.bodies()
        else:
            roots = list(node.body)
        stack = list(reversed(roots))
        while stack:
            n = stack.pop()
            yield n
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                kids = list(getattr(n, "decorator_list", ())) + list(n.args.defaults) + [d for d in n.args.kw_defaults if d]
            elif isinstance(n, ast.ClassDef):
                kids = list(n.decorator_list) + list(n.bases) + [k.value for k in n.keywords]
            else:
                kids = list(ast.iter_child_nodes(n))
            stack.extend(reversed(kids))

    def _collect_locals(self, fn: _Func) -> None:
        if not fn.is_module:
            nodes = [fn.node] if not isinstance(fn.node, _MergedBody) else fn.node.nodes
            for fnode in nodes:
                a = fnode.args
                params = a.posonlyargs + a.args + a.kwonlyargs
                for i, p in enumerate(params):
                    if i == 0 and fn.is_method and p.arg == fn.self_name:
                        fn.declared[p.arg] = (frozenset({fn.cls}), EMPTY)
                    elif p.annotation is not None:
                        fn.declared[p.arg] = self._ann_pair(fn.module, p.annotation)
                    else:
                        fn.declared[p.arg] = TOP
                fn.params.update(p.arg for p in params)
                if a.vararg:
                    fn.declared[a.vararg.arg] = (EMPTY, None)
                if a.kwarg:
                    fn.declared[a.kwarg.arg] = (EMPTY, None)
        for n in self._body_nodes(fn):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    self._record_target(fn, t, "value", n.value)
            elif isinstance(n, ast.AnnAssign):
                t = n.target
                if isinstance(t, ast.Name):
                    fn.declared[t.id] = self._ann_pair(fn.module, n.annotation)
                elif self._is_self_attr(fn, t):
                    self.classes[fn.cls].ann.setdefault(t.attr, (fn.module, n.annotation))
            elif isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
                self._record_target(fn, n.target, "elem", n.iter)
            elif isinstance(n, ast.withitem) and n.optional_vars is not None:
                self._record_target(fn, n.optional_vars, "unknown", None)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                fn.assigns.append((n.name, "unknown", None))
            elif isinstance(n, ast.NamedExpr):
                self._record_target(fn, n.target, "value", n.value)
            elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
                fn.assigns.append((n.name, "unknown", None))
            elif isinstance(n, ast.MatchMapping) and n.rest:
                fn.assigns.append((n.rest, "unknown", None))
        fn.env.update(fn.declared)

    def _is_self_attr(self, fn: _Func, t) -> bool:
        return (
            isinstance(t, ast.Attribute)
            and isinstance(t.value, ast.Name)
            and fn.cls is not None
            and fn.self_name is not None
            and not fn.self_is_class
            and t.value.id == fn.self_name
        )

    def _record_target(self, fn: _Func, target, kind: str, expr) -> None:
        work = [(target, kind, expr)]
        while work:
            t, k, e = work.pop()
            if isinstance(t, ast.Name):
                fn.assigns.append((t.id, k, e))
                continue
            if self._is_self_attr(fn, t):
                self.attr_assigns.append((fn.cls, t.attr, fn, k, e))
                continue
            if isinstance(t, ast.Starred):
                work.append((t.value, "unknown", None))
                continue
            if not isinstance(t, (ast.Tuple, ast.List)):
                continue
            parts = None
            # Tuple targets over zip(...), enumerate(...) and d.items().
            if k == "elem" and isinstance(e, ast.Call):
                f = e.func
                if isinstance(f, ast.Name) and f.id == "zip" and not e.keywords:
                    parts = [("elem", a) for a in e.args]
                elif isinstance(f, ast.Name) and f.id == "enumerate" and len(e.args) == 1:
                    parts = [("known", None), ("elem", e.args[0])]
                elif isinstance(f, ast.Attribute) and f.attr == "items" and not e.args:
                    parts = [("unknown", None), ("elem", f.value)]
            if parts is None or len(parts) != len(t.elts):
                parts = [("unknown", None)] * len(t.elts)
            for elt, (pk, pe) in zip(t.elts, parts):
                work.append((elt, pk, pe))

    # ----------------------------------------------------------- type eval
    def _is_enum(self, key: str) -> bool:
        for k in self._mro(key):
            for r in self.classes[k].ext_bases:
                if r.startswith("enum."):
                    return True
        return False

    def _return_pair(self, quals) -> tuple:
        if not quals:
            return TOP
        out = UNSET
        for q in quals:
            fn = self.funcs[q]
            nodes = fn.node.nodes if isinstance(fn.node, _MergedBody) else [fn.node]
            ann = getattr(nodes[0], "returns", None)
            if ann is None:
                return TOP
            out = _join_pair(out, self._ann_pair(fn.module, ann))
        return out

    def _attr_type(self, key: str, attr: str):
        for k in self._mro(key):
            ann = self.classes[k].ann.get(attr)
            if ann is not None:
                return self._ann_pair(ann[0], ann[1])
        q = self._lookup_mro(key, attr)
        if q is not None:
            name = q.rsplit(".", 1)[-1]
            if any(name in self.classes[k].properties for k in self._mro(key)):
                return self._return_pair(self._virtual(key, attr))
            return TOP
        if attr == "name" and self._is_enum(key):
            return BOTTOM
        found = False
        out = UNSET
        for k in self._mro(key) + self._subclasses(key):
            v = self.attr_values.get((k, attr))
            if v is not None:
                out = _join_pair(out, v)
                found = True
        return out if found else TOP

    def _eval(self, fn: _Func, expr):
        if expr is None:
            return TOP
        results = {}
        stack = [(expr, False)]
        while stack:
            node, ready = stack.pop()
            if not ready:
                stack.append((node, True))
                if isinstance(node, (ast.Attribute, ast.Subscript, ast.NamedExpr, ast.Starred)):
                    stack.append((node.value, False))
                elif isinstance(node, ast.IfExp):
                    stack.append((node.body, False))
                    stack.append((node.orelse, False))
                elif isinstance(node, ast.BoolOp):
                    stack.extend((v, False) for v in node.values)
                elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                    stack.extend((e, False) for e in node.elts)
                elif isinstance(node, ast.Dict):
                    stack.extend((v, False) for v in node.values)
                elif isinstance(node, ast.Call):
                    if node.args:
                        stack.append((node.args[0], False))
                    if isinstance(node.func, ast.Attribute):
                        stack.append((node.func.value, False))
                elif isinstance(node, ast.BinOp):
                    stack.append((node.left, False))
                    stack.append((node.right, False))
                continue
            results[id(node)] = self._type_of(fn, node, results)
        return results[id(expr)]

    def _type_of(self, fn: _Func, node, results):
        if isinstance(node, ast.Name):
            r = self._resolve_name(fn, node.id)
            if r is None:
                return TOP
            if r[0] == "local":
                return r[1].env.get(node.id, TOP)
            if r[0] == "var":
                return self.module_funcs[r[1]].env.get(r[2], TOP)
            return TOP
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.Compare, ast.UnaryOp)):
            return BOTTOM
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and fn.self_is_class and f.id == fn.self_name and fn.cls:
                return (frozenset({fn.cls}), EMPTY)
            if isinstance(f, ast.Attribute):
                inst = results[id(f.value)][0]
                if inst is BOT:
                    return UNSET
                return self._return_pair(self._resolve_attr(fn, f.value, f.attr, inst, True))
            r = self._static(fn, f)
            if r is None:
                return TOP
            if r[0] == "class":
                return (frozenset({r[1]}), EMPTY)
            if r[0] == "func":
                return self._return_pair({r[1]})
            if r[0] == "ext" and r[1].split(".")[-1][:1].isupper():
                # Constructing a class from outside the package.
                return BOTTOM
            if r[0] == "builtin":
                if r[1] in _BUILTIN_ITER_CTORS:
                    if node.args:
                        return (EMPTY, results[id(node.args[0])][1])
                    return (EMPTY, EMPTY)
                if r[1] in ("dict", "iter", "enumerate", "zip", "map", "filter", "getattr", "next", "min", "max"):
                    return TOP
                return BOTTOM
            return TOP
        if isinstance(node, ast.Attribute):
            if node.attr in ("__name__", "__qualname__", "__module__", "__doc__"):
                return BOTTOM
            r = self._static(fn, node.value)
            if r is not None and r[0] != "dynamic":
                if r[0] == "module":
                    rr = self._resolve_global(r[1], node.attr)
                    if rr is not None and rr[0] == "var":
                        return self.module_funcs[rr[1]].env.get(rr[2], TOP)
                return TOP
            inst = results[id(node.value)][0]
            if inst is BOT:
                return UNSET
            if not inst:
                return TOP
            out = UNSET
            for k in inst:
                out = _join_pair(out, self._attr_type(k, node.attr))
            return out
        if isinstance(node, ast.Subscript):
            v = results[id(node.value)]
            if isinstance(node.slice, ast.Slice):
                return v
            if v[1] is BOT:
                return UNSET
            if v[1] is None:
                return TOP
            return (v[1], None)
        if isinstance(node, ast.IfExp):
            return _join_pair(results[id(node.body)], results[id(node.orelse)])
        if isinstance(node, ast.BoolOp):
            out = UNSET
            for v in node.values:
                out = _join_pair(out, results[id(v)])
            return out
        if isinstance(node, ast.NamedExpr):
            return results[id(node.value)]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            elem = BOT if node.elts else EMPTY
            for e in node.elts:
                elem = None if isinstance(e, ast.Starred) else _join(elem, results[id(e)][0])
                if elem is None:
                    break
            return (EMPTY, elem)
        if isinstance(node, ast.Dict):
            elem = BOT if node.values else EMPTY
            for k, v in zip(node.keys, node.values):
                elem = None if k is None else _join(elem, results[id(v)][0])
                if elem is None:
                    break
            return (EMPTY, elem)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return (EMPTY, None)
        if isinstance(node, ast.BinOp):
            left, right = results[id(node.left)], results[id(node.right)]
            if left[0] == EMPTY and right[0] == EMPTY and left[0] is not BOT and right[0] is not BOT:
                return (EMPTY, None)
            return TOP
        return TOP

    def infer(self) -> None:
        order = list(self.module_funcs.values()) + self.func_list
        for fn in self.module_funcs.values():
            self._collect_locals(fn)
        for key, attr, _, _, _ in self.attr_assigns:
            self.attr_values[(key, attr)] = UNSET
        for fn in order:
            for name, _, _ in fn.assigns:
                if name not in fn.declared:
                    fn.env[name] = UNSET
        converged = False
        for _ in range(_MAX_ROUNDS):
            for fn in order:
                self._local_fixpoint(fn)
            new = {}
            for key, attr, fn, kind, expr in self.attr_assigns:
                p = self._assigned_pair(fn, kind, expr)
                new[(key, attr)] = _join_pair(new.get((key, attr), UNSET), p)
            if _frozen(new) == _frozen(self.attr_values):
                converged = True
                break
            self.attr_values = new
        if not converged:
            for k in self.attr_values:
                self.attr_values[k] = TOP
        # Anything still unset has no information: treat it as unknown.
        self.attr_values = {k: _unset_to_top(v) for k, v in self.attr_values.items()}
        for fn in order:
            fn.env = {k: _unset_to_top(v) for k, v in fn.env.items()}

    def _assigned_pair(self, fn: _Func, kind: str, expr):
        if kind == "unknown":
            return TOP
        if kind == "known":
            return BOTTOM
        p = self._eval(fn, expr)
        if kind == "elem":
            if p[1] is BOT:
                return UNSET
            return (p[1], None) if p[1] is not None else TOP
        return p

    def _local_fixpoint(self, fn: _Func) -> None:
        for _ in range(_MAX_ROUNDS):
            new = dict(fn.declared)
            for name, kind, expr in fn.assigns:
                if name in fn.declared:
                    continue
                new[name] = _join_pair(new.get(name, UNSET), self._assigned_pair(fn, kind, expr))
            if _frozen(new) == _frozen(fn.env):
                return
            fn.env = new
        for name, _, _ in fn.assigns:
            if name not in fn.declared:
                fn.env[name] = TOP

    # -------------------------------------------------------------- edges
    def build_edges(self) -> None:
        for fn in list(self.module_funcs.values()) + self.func_list:
            for node in self._body_nodes(fn):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                method = node.func.attr
                if method not in ("append", "appendleft", "extend", "extendleft", "insert") or not node.args:
                    continue
                value = node.args[-1] if method == "insert" else node.args[0]
                for key in self._container_keys(fn, node.func.value):
                    self.container_values.setdefault(key, []).append((fn, value))
        for fn in self.func_list:
            fn.calls_params = self._calls_params(fn)
        for fn in list(self.module_funcs.values()) + self.func_list:
            self._edges_for(fn)

    def _calls_params(self, fn: _Func) -> bool:
        """Whether fn calls one of its own or an enclosing function's parameters."""
        for n in self._body_nodes(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                r = self._resolve_name(fn, n.func.id)
                if r is not None and r[0] == "local" and n.func.id in r[1].params:
                    return True
        return False

    def _function_refs(self, fn: _Func, expr) -> set:
        """Functions an argument expression refers to without calling them."""
        if isinstance(expr, ast.Name):
            r = self._resolve_name(fn, expr.id)
            return {r[1]} if r is not None and r[0] == "func" else set()
        if isinstance(expr, ast.Attribute):
            inst = self._receiver_classes(fn, expr.value)
            return self._resolve_attr(fn, expr.value, expr.attr, inst, False)
        return set()

    def _container_keys(self, fn: _Func, expr) -> list:
        if isinstance(expr, ast.Name):
            resolved = self._resolve_name(fn, expr.id)
            if resolved is not None and resolved[0] == "local":
                return [(resolved[1].qual, expr.id)]
            if resolved is not None and resolved[0] == "var":
                return [(resolved[1], resolved[2])]
        if isinstance(expr, ast.Attribute):
            classes = self._receiver_classes(fn, expr.value)
            return [(key, expr.attr) for cls in classes or () for key in self._mro(cls)]
        return []

    def _callable_targets(self, fn: _Func, expr) -> set:
        """Follow callable assignments and container values with an explicit worklist."""
        out, seen = set(), set()
        unknown_key = object()
        pending = [(fn, expr, unknown_key)]
        while pending:
            context, node, selected = pending.pop()
            key = (context.qual, id(node), selected)
            if node is None or key in seen:
                continue
            seen.add(key)
            for storage in self._container_keys(context, node):
                pending.extend((owner, value, selected) for owner, value in self.container_values.get(storage, ()))
            if isinstance(node, ast.Lambda):
                qual = self.lambda_funcs.get(id(node))
                if qual:
                    out.add(qual)
            elif isinstance(node, ast.Name):
                resolved = self._resolve_name(context, node.id)
                if resolved is not None and resolved[0] == "func":
                    out.add(resolved[1])
                elif resolved is not None and resolved[0] in ("local", "var"):
                    owner = resolved[1] if resolved[0] == "local" else self.module_funcs[resolved[1]]
                    name = node.id if resolved[0] == "local" else resolved[2]
                    pending.extend((owner, value, selected) for target, _, value in owner.assigns if target == name)
            elif isinstance(node, ast.Attribute):
                out |= self._function_refs(context, node)
                classes = self._receiver_classes(context, node.value)
                static = self._static(context, node.value)
                if static is not None and static[0] == "class":
                    classes = {static[1]}
                elif static is not None and static[0] == "module":
                    owner = self.module_funcs[static[1]]
                    pending.extend((owner, value, selected) for target, _, value in owner.assigns if target == node.attr)
                for cls in classes or ():
                    for base in self._mro(cls) + self._subclasses(cls):
                        pending.extend((owner, value, selected) for owner, value in self.class_values.get((base, node.attr), ()))
                        pending.extend((owner, value, selected) for key, attr, owner, _, value in self.attr_assigns
                                       if key == base and attr == node.attr)
            elif isinstance(node, ast.Subscript):
                index = node.slice.value if isinstance(node.slice, ast.Constant) else unknown_key
                pending.append((context, node.value, index))
            elif isinstance(node, ast.Dict):
                for key_node, value in zip(node.keys, node.values):
                    if (selected is unknown_key or key_node is None
                            or not isinstance(key_node, ast.Constant) or key_node.value == selected):
                        pending.append((context, value, unknown_key if key_node is not None else selected))
            elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                pending.extend((context, value, unknown_key) for value in node.elts)
            elif isinstance(node, ast.IfExp):
                pending.extend(((context, node.body, selected), (context, node.orelse, selected)))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("pop", "popleft", "get"):
                    index = unknown_key
                    if node.func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant):
                        index = node.args[0].value
                    pending.append((context, node.func.value, index))
        return out

    def _callback_edges(self, fn: _Func, call: ast.Call) -> None:
        """A function that calls its parameters may call any function passed to it."""
        f = call.func
        if isinstance(f, ast.Name):
            r = self._resolve_name(fn, f.id)
            callees = {r[1]} if r is not None and r[0] == "func" else set()
        elif isinstance(f, ast.Attribute):
            callees = self._resolve_attr(fn, f.value, f.attr, self._receiver_classes(fn, f.value), True)
        else:
            return
        callees = {q for q in callees if self.funcs[q].calls_params}
        if not callees:
            return
        refs = set()
        for arg in list(call.args) + [k.value for k in call.keywords]:
            refs |= self._callable_targets(fn, arg.value if isinstance(arg, ast.Starred) else arg)
        saved = self._line
        for callee in callees:
            # The call happens inside the callee; cite its definition line.
            self._line = self.funcs[callee].line
            self._add(self.funcs[callee], refs)
        self._line = saved

    def _add(self, fn: _Func, targets) -> None:
        if fn.is_module:
            return
        self.edges.setdefault(fn.qual, set()).update(targets)
        for t in targets:
            key = (fn.qual, t)
            if key not in self.edge_lines or self._line < self.edge_lines[key]:
                self.edge_lines[key] = self._line

    def _family(self, key: Optional[str]) -> list:
        """The class, its in-package bases, and every subclass of any of them."""
        if key is None:
            return []
        out = []
        seen = set()
        for k in self._mro(key):
            for c in [k] + self._subclasses(k):
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out

    def _fallback_candidates(self, fn: _Func, name: str) -> set:
        cands = set()
        for k in self._family(fn.cls):
            q = self.classes[k].methods.get(name)
            if q is not None:
                cands.add(q)
        return cands

    def _fallback(self, fn: _Func, name: str, line: int, record: bool) -> set:
        cands = self._fallback_candidates(fn, name)
        others = [q for q in self.methods_by_name.get(name, ()) if q not in cands]
        if others and record and not fn.is_module:
            self.unresolved.append(Unresolved(fn.qual, name, fn.path, line, tuple(sorted(others))))
            if self.include_unresolved:
                cands.update(others)
        return cands

    def _receiver_classes(self, fn: _Func, recv):
        inst = self._eval(fn, recv)[0]
        return None if inst is BOT else inst

    def _resolve_attr(self, fn: _Func, recv, name: str, inst, is_call: bool) -> set:
        """Targets of ``recv.name`` without side effects; ``inst`` is the receiver's classes."""
        if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) and recv.func.id == "super" \
                and self._resolve_name(fn, "super") == ("builtin", "super"):
            if fn.cls is None:
                return set()
            mro = self._mro(fn.cls)
            start = 1
            if len(recv.args) >= 1:
                r = self._static(fn, recv.args[0])
                if r is not None and r[0] == "class" and r[1] in mro:
                    start = mro.index(r[1]) + 1
            for k in mro[start:]:
                q = self.classes[k].methods.get(name)
                if q is not None:
                    return {q}
            return set()
        r = self._static(fn, recv)
        if r is not None and r[0] != "dynamic":
            kind = r[0]
            if kind == "class":
                q = self._lookup_mro(r[1], name)
                nested = f"{r[1]}.{name}"
                out = {q} if q else set()
                if is_call and nested in self.classes:
                    out |= self._ctor_targets(nested)
                return out
            if kind == "module":
                rr = self._resolve_global(r[1], name)
                if rr is None:
                    return set()
                if rr[0] == "func":
                    return {rr[1]}
                if rr[0] == "class" and is_call:
                    return self._ctor_targets(rr[1])
            return set()
        if inst is None or inst is BOT:
            if name not in self.methods_by_name:
                return set()
            return set() if self._is_self_attr(fn, recv) else self._fallback_candidates(fn, name)
        out = set()
        for k in inst:
            out |= self._virtual(k, name)
        return out

    def _attr_targets(self, fn: _Func, recv, name: str, is_call: bool, line: int) -> set:
        r = self._static(fn, recv)
        if r is not None and r[0] == "ext" and is_call and f"{r[1]}.{name}" == "copy.deepcopy":
            self.deepcopy_calls.append((fn.qual, fn.path, line))
            return set()
        if r is not None and r[0] != "dynamic":
            return self._resolve_attr(fn, recv, name, None, is_call)
        if isinstance(recv, ast.Call) and isinstance(recv.func, ast.Name) and recv.func.id == "super":
            return self._resolve_attr(fn, recv, name, None, is_call)
        inst = self._receiver_classes(fn, recv)
        if inst is None:
            if name not in self.methods_by_name:
                return set()
            if self._is_self_attr(fn, recv):
                candidates = tuple(sorted(self.methods_by_name[name]))
                if (is_call or name in self.property_names) and not fn.is_module:
                    self.unresolved.append(Unresolved(fn.qual, name, fn.path, line, candidates))
                return set(candidates) if self.include_unresolved else set()
            return self._fallback(fn, name, line, record=is_call or name in self.property_names)
        return self._resolve_attr(fn, recv, name, inst, is_call)

    def _dunder_targets(self, fn: _Func, recv, name: str) -> set:
        """Methods run by an implicit ``name`` call on ``recv``.

        Tuple, list and set literals apply the call to each element; an
        expression of container type also applies it to its element classes
        (tuple hashing, container equality and ``str`` of a container reach the
        elements).
        """
        out = set()
        stack = [recv]
        while stack:
            e = stack.pop()
            if isinstance(e, (ast.Tuple, ast.List, ast.Set)):
                stack.extend(e.elts)
                continue
            if isinstance(e, ast.Starred):
                stack.append(e.value)
                continue
            if isinstance(e, ast.Constant):
                continue
            inst, elem = self._eval(fn, e)
            if name == "__hash__" and self._is_set_attr(fn, e):
                # A set's hash uses the element hashes stored at insertion.
                elem = EMPTY
            groups = [inst, elem]
            if inst is None or inst is BOT:
                for n in [name] + (["__repr__"] if name == "__str__" else []):
                    out |= self._fallback_candidates(fn, n)
                groups = [elem]
            for classes in groups:
                if classes is None or classes is BOT:
                    continue
                for k in classes:
                    for sub in [k] + self._subclasses(k):
                        q = self._lookup_mro(sub, name)
                        if q is None and name == "__str__":
                            q = self._lookup_mro(sub, "__repr__")
                        if q is not None:
                            out.add(q)
        return out

    def _is_set_attr(self, fn: _Func, e) -> bool:
        if not isinstance(e, ast.Attribute):
            return False
        inst = self._receiver_classes(fn, e.value)
        if not inst:
            return False
        for k in inst:
            ann = None
            for c in self._mro(k):
                ann = self.classes[c].ann.get(e.attr)
                if ann is not None:
                    break
            if ann is None:
                return False
            head = ann[1].value if isinstance(ann[1], ast.Subscript) else ann[1]
            kind, name = self._head_name(ann[0], head)
            if kind != "ext" or name not in ("set", "frozenset", "Set", "FrozenSet", "AbstractSet"):
                return False
        return True

    @staticmethod
    def _const_prefix(expr) -> Optional[str]:
        if isinstance(expr, ast.JoinedStr):
            if expr.values and isinstance(expr.values[0], ast.Constant) and isinstance(expr.values[0].value, str):
                return expr.values[0].value
            return None
        if isinstance(expr, ast.BinOp):
            left = expr.left
            while isinstance(left, ast.BinOp) and isinstance(left.op, ast.Add):
                left = left.left
            if isinstance(expr.op, ast.Add) and isinstance(left, ast.Constant) and isinstance(left.value, str):
                return left.value
            if isinstance(expr.op, ast.Mod) and isinstance(expr.left, ast.Constant) and isinstance(expr.left.value, str):
                return expr.left.value.split("%")[0]
            return None
        if (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Attribute)
            and expr.func.attr == "format"
            and isinstance(expr.func.value, ast.Constant)
            and isinstance(expr.func.value.value, str)
        ):
            return expr.func.value.value.split("{")[0]
        return None

    def _getattr_targets(self, fn: _Func, call: ast.Call) -> set:
        recv, name_expr = call.args[0], call.args[1]
        line = call.lineno
        if isinstance(name_expr, ast.Constant) and isinstance(name_expr.value, str):
            return self._attr_targets(fn, recv, name_expr.value, False, line)
        prefix = self._const_prefix(name_expr)
        inst = self._receiver_classes(fn, recv)
        if inst is None:
            if prefix is None:
                return set()
            keys = self._family(fn.cls)
        else:
            keys = []
            for k in inst:
                keys.extend(self._mro(k) + self._subclasses(k))
        out = set()
        for k in keys:
            for mname, q in self.classes[k].methods.items():
                if prefix is None or mname.startswith(prefix):
                    out.add(q)
        return out

    def _edges_for(self, fn: _Func) -> None:
        call_funcs = set()
        stored_refs = set()
        for node in self._body_nodes(fn):
            if isinstance(node, ast.Dict):
                values = list(node.values)
                while values:
                    value = values.pop()
                    if isinstance(value, (ast.Name, ast.Attribute)):
                        stored_refs.add(id(value))
                    elif isinstance(value, ast.IfExp):
                        values.extend((value.body, value.orelse))
                    elif isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                        values.extend(value.elts)
        for n in self._body_nodes(fn):
            self._line = getattr(n, "lineno", fn.line)
            if isinstance(n, ast.Call):
                call_funcs.add(id(n.func))
                self._callback_edges(fn, n)
                f = n.func
                self._add(fn, self._callable_targets(fn, f))
                if isinstance(f, ast.Name):
                    r = self._resolve_name(fn, f.id)
                    if r == ("builtin", "getattr") and len(n.args) >= 2:
                        self._add(fn, self._getattr_targets(fn, n))
                    elif r is not None and r[0] == "builtin":
                        if f.id in _STR_DUNDER_BUILTINS:
                            for a in n.args:
                                self._add(fn, self._dunder_targets(fn, a, "__str__"))
                        elif f.id in ("repr", "ascii") and n.args:
                            self._add(fn, self._dunder_targets(fn, n.args[0], "__repr__"))
                        elif f.id == "hash" and n.args:
                            self._add(fn, self._dunder_targets(fn, n.args[0], "__hash__"))
                        elif f.id == "len" and n.args:
                            self._add(fn, self._dunder_targets(fn, n.args[0], "__len__"))
                    elif r is not None and r[0] == "class":
                        self._add(fn, self._ctor_targets(r[1]))
                    elif r is not None and r[0] == "ext" and r[1] == "copy.deepcopy":
                        self.deepcopy_calls.append((fn.qual, fn.path, n.lineno))
                    elif r is not None and r[0] == "local":
                        if fn.self_is_class and f.id == fn.self_name and fn.cls:
                            self._add(fn, self._ctor_targets(fn.cls, virtual=True))
                        else:
                            inst = self._receiver_classes(fn, f)
                            for k in inst or ():
                                self._add(fn, self._virtual(k, "__call__"))
            elif isinstance(n, ast.FormattedValue):
                dunder = "__repr__" if n.conversion in (ord("r"), ord("a")) else "__str__"
                self._add(fn, self._dunder_targets(fn, n.value, dunder))
            elif isinstance(n, ast.Compare):
                operands = [n.left] + list(n.comparators)
                for i, op in enumerate(n.ops):
                    if isinstance(op, (ast.Eq, ast.NotEq)):
                        dunder = "__eq__" if isinstance(op, ast.Eq) else "__ne__"
                        for side in (operands[i], operands[i + 1]):
                            self._add(fn, self._dunder_targets(fn, side, dunder))
            elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) \
                    and isinstance(n.left.value, str):
                items = n.right.elts if isinstance(n.right, ast.Tuple) else [n.right]
                for item in items:
                    self._add(fn, self._dunder_targets(fn, item, "__str__"))
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in stored_refs:
                r = self._resolve_name(fn, n.id)
                if r is not None and r[0] == "func":
                    self._add(fn, {r[1]})
            elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and id(n) not in stored_refs:
                self._add(fn, self._attr_targets(fn, n.value, n.attr, id(n) in call_funcs, n.lineno))

    # ---------------------------------------------------------------- SCCs
    def groups(self) -> list:
        nodes = sorted(self.funcs)
        index, low, on_stack = {}, {}, set()
        stack, out = [], []
        counter = 0
        for start in nodes:
            if start in index:
                continue
            index[start] = low[start] = counter
            counter += 1
            stack.append(start)
            on_stack.add(start)
            work = [(start, iter(sorted(self.edges.get(start, ()))))]
            while work:
                v, it = work[-1]
                pushed = False
                for w in it:
                    if w not in self.funcs:
                        continue
                    if w not in index:
                        index[w] = low[w] = counter
                        counter += 1
                        stack.append(w)
                        on_stack.add(w)
                        work.append((w, iter(sorted(self.edges.get(w, ())))))
                        pushed = True
                        break
                    if w in on_stack:
                        low[v] = min(low[v], index[w])
                if pushed:
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1 or v in self.edges.get(v, ()):
                        out.append(tuple(sorted(comp)))
        return sorted(out)


class _MergedBody:
    """Several definitions sharing one qualified name (property setters, redefinitions)."""

    def __init__(self, first, second):
        firsts = first.nodes if isinstance(first, _MergedBody) else [first]
        self.nodes = firsts + [second]

    def bodies(self):
        out = []
        for n in self.nodes:
            out.extend(n.body)
        return out


def _assigned_names(node) -> list:
    targets = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    names = []
    while targets:
        t = targets.pop()
        if isinstance(t, ast.Name):
            names.append(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            targets.extend(t.elts)
        elif isinstance(t, ast.Starred):
            targets.append(t.value)
    return names


def scan(root, package: Optional[str] = None, include_unresolved: bool = False) -> ScanResult:
    """Scan the package directory ``root`` (for example ``<repo>/a7``)."""
    root = Path(root)
    scanner = _Scanner(root, package or root.name)
    scanner.include_unresolved = include_unresolved
    scanner.load()
    scanner.infer()
    scanner.build_edges()
    findings, unchecked = scanner.dataclass_findings()
    functions = {q: (f.path, f.line) for q, f in scanner.funcs.items()}
    return ScanResult(
        functions=functions,
        edges=scanner.edges,
        edge_lines=scanner.edge_lines,
        groups=scanner.groups(),
        deepcopy_calls=sorted(set(scanner.deepcopy_calls)),
        dataclass_findings=findings,
        unchecked_dataclass_fields=unchecked,
        unresolved=sorted(set(scanner.unresolved), key=lambda u: (u.path, u.line, u.name)),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1] / "a7"))
    parser.add_argument("--unresolved", action="store_true", help="list unresolved calls")
    parser.add_argument(
        "--with-unresolved-edges",
        action="store_true",
        help="also report groups that appear only when unresolved calls become edges",
    )
    args = parser.parse_args(argv)
    result = scan(args.root)
    print(f"functions scanned: {len(result.functions)}")
    print(f"recursive groups: {len(result.groups)}")
    for group in result.groups:
        kind = "self-loop" if len(group) == 1 else f"cycle of {len(group)}"
        print(f"- {kind}:")
        for q in group:
            calls = sorted(
                (result.edge_lines[(q, t)], t) for t in group if t in result.edges.get(q, ())
            )
            via = "; ".join(f"line {line} -> {t.split(':')[1]}" for line, t in calls)
            print(f"    {q}  {result.location(q)}  [{via}]")
    print(f"\ncopy.deepcopy calls: {len(result.deepcopy_calls)}")
    for caller, path, line in result.deepcopy_calls:
        print(f"- {caller}  {path}:{line}")
    print(f"\ndataclasses with recursive generated methods: {len(result.dataclass_findings)}")
    for f in result.dataclass_findings:
        print(f"- {f.cls} __{f.kind}__  {f.path}:{f.line}  fields: {', '.join(f.fields)}  holds: {', '.join(f.holds)}")
    print(f"\ndataclass fields annotated Any/object (not checked): {len(result.unchecked_dataclass_fields)}")
    for key, name, path, line in result.unchecked_dataclass_fields:
        print(f"- {key}.{name}  {path}:{line}")
    print(f"\nunresolved calls: {len(result.unresolved)}")
    if args.unresolved:
        for u in result.unresolved:
            print(f"- {u.caller} .{u.name}  {u.path}:{u.line}  candidates: {', '.join(u.candidates)}")
    if args.with_unresolved_edges:
        wide = scan(args.root, include_unresolved=True)
        extra = [g for g in wide.groups if g not in set(result.groups)]
        print(f"\ngroups only with unresolved edges: {len(extra)}")
        for group in extra:
            print(f"- {wide.describe_group(group)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
