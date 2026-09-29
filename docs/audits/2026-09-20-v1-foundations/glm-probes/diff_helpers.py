"""Differential oracle: run the three helpers on identical random inputs.

Usage: python diff_helpers.py <main|cand>
Run from the directory containing the a7 package to test. Prints JSON.
"""
import json
import random
import sys

from a7.ast_nodes import ASTNode, NodeKind, LiteralKind, UnaryOp
from a7.safety import SafetyProofPass
from a7.symbol_table import SymbolTable, Scope, Symbol, SymbolKind
from a7.types import I32
from a7.backends.zig import ZigCodeGenerator

rng = random.Random(1234)
out = {}

# --- _int_literal ----------------------------------------------------------
UNARY_OPS = [o for o in UnaryOp]
LIT_KINDS = [LiteralKind.INTEGER, LiteralKind.FLOAT, LiteralKind.STRING]


def rand_leaf():
    r = rng.random()
    if r < 0.2:
        return None
    if r < 0.35:
        return ASTNode(kind=NodeKind.IDENTIFIER, name="x")
    k = rng.choice(LIT_KINDS)
    v = rng.choice([0, 1, 17, -5, 2.5, "s"]) if k != LiteralKind.STRING else "s"
    return ASTNode(kind=NodeKind.LITERAL, literal_kind=k, literal_value=v)


def rand_unary_chain(depth):
    node = rand_leaf()
    for _ in range(depth):
        node = ASTNode(kind=NodeKind.UNARY, operator=rng.choice(UNARY_OPS), operand=node)
    return node


proof = SafetyProofPass(SymbolTable(), {})
cases = [None]
for _ in range(300):
    cases.append(rand_unary_chain(rng.randint(0, 12)))
cases.append(ASTNode(kind=NodeKind.UNARY, operator=UnaryOp.NEG, operand=None))
out["int_literal"] = [proof._int_literal(c) for c in cases]

# --- base_identifier via _collect_mutations --------------------------------
TARGET_KINDS = [NodeKind.IDENTIFIER, NodeKind.FIELD_ACCESS, NodeKind.INDEX, NodeKind.DEREF,
                NodeKind.CALL]


def rand_target(depth):
    if depth == 0 or rng.random() < 0.1:
        return ASTNode(kind=NodeKind.IDENTIFIER, name=rng.choice(["a", "b", "ptr"]))
    k = rng.choice(TARGET_KINDS)
    obj = rand_target(depth - 1) if rng.random() > 0.05 else None
    if k == NodeKind.CALL:
        return ASTNode(kind=k, object=obj, arguments=[])
    return ASTNode(kind=k, object=obj)


gen = ZigCodeGenerator()
mut = []
for _ in range(300):
    t = rand_target(rng.randint(1, 8))
    mut.append(sorted(gen._collect_mutations(
        ASTNode(kind=NodeKind.BLOCK, statements=[ASTNode(kind=NodeKind.ASSIGNMENT, target=t)]))))
# deref-rooted and address-of forms
for _ in range(100):
    t = ASTNode(kind=NodeKind.DEREF, operand=rand_target(rng.randint(0, 5)))
    mut.append(sorted(gen._collect_mutations(
        ASTNode(kind=NodeKind.BLOCK, statements=[
            ASTNode(kind=NodeKind.ASSIGNMENT, target=t),
            ASTNode(kind=NodeKind.ADDRESS_OF, operand=rand_target(rng.randint(0, 5))),
        ]))))
out["mutations"] = mut

# --- SymbolTable.dump -------------------------------------------------------
NAMES = ["global", "f", "block", "loop", "lambda", "z"]


def rand_scope_tree():
    root = Scope("root", None)
    count = [0]

    def add(parent, depth):
        for _ in range(rng.randint(0, 3)):
            count[0] += 1
            child = Scope(f"s{count[0]}", parent)
            parent.children.append(child)
            for _ in range(rng.randint(0, 3)):
                child.symbols[f"v{rng.randint(0, 40)}"] = Symbol(
                    f"v{rng.randint(0, 40)}", SymbolKind.VARIABLE, I32,
                    is_used=rng.random() < 0.5)
            if depth < 4:
                add(child, depth + 1)

    add(root, 0)
    return root


dumps = []
for _ in range(120):
    r = rand_scope_tree()
    table = SymbolTable()
    table.global_scope.children.append(r)
    dumps.append(table.dump())
out["dumps"] = dumps

print(json.dumps(out))
