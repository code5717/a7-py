"""Large cast-safety matrix for the first compiler safety vertical slice."""

import pytest

from a7.ast_nodes import NodeKind
from a7.backends.zig import ZigCodeGenerator
from a7.cast_classifier import CastClass, classify_cast
from a7.errors import CodegenError, CompilerError
from a7.parser import Parser
from a7.passes.name_resolution import NameResolutionPass
from a7.passes.semantic_validator import SemanticValidationPass
from a7.passes import SafetyProofPass
from a7.passes.type_checker import TypeCheckingPass
from a7.tokens import Tokenizer
from a7.types import FunctionType, I32, ReferenceType, get_primitive_type


SIGNED = ["i8", "i16", "i32", "i64", "isize"]
UNSIGNED = ["u8", "u16", "u32", "u64", "usize"]
FLOATS = ["f32", "f64"]
NUMERIC = SIGNED + UNSIGNED + FLOATS
NON_NUMERIC = ["bool", "char", "string"]
PRIMITIVES = NUMERIC + NON_NUMERIC


def parse_program(source: str):
    tokenizer = Tokenizer(source)
    tokens = tokenizer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def run_semantic_analysis(source: str):
    program = parse_program(source)
    resolver = NameResolutionPass()
    symbols = resolver.analyze(program, "<test>")
    if resolver.errors:
        raise resolver.errors[0]

    checker = TypeCheckingPass(symbols)
    node_types = checker.analyze(program, "<test>")
    if checker.errors:
        raise checker.errors[0]

    validator = SemanticValidationPass(symbols, node_types)
    validator.analyze(program, "<test>")
    if validator.errors:
        raise validator.errors[0]

    safety = SafetyProofPass(symbols, node_types)
    safety.analyze(program, "<test>")
    if safety.errors:
        raise safety.errors[0]

    return program, symbols, node_types


def expect_success(source: str) -> bool:
    try:
        run_semantic_analysis(source)
        return True
    except CompilerError:
        return False


def expect_error(source: str, fragment: str) -> bool:
    try:
        run_semantic_analysis(source)
        return False
    except CompilerError as exc:
        return fragment.lower() in str(exc).lower()


def primitive(name: str):
    result = get_primitive_type(name)
    assert result is not None
    return result


def expected_without_proof(source: str, target: str) -> CastClass:
    source_type = primitive(source)
    target_type = primitive(target)
    return classify_cast(source_type, target_type, source_nonnegative=False).kind


def source_literal(type_name: str) -> str:
    if type_name in FLOATS:
        return "1.5"
    if type_name in {"bool"}:
        return "true"
    if type_name == "char":
        return "'a'"
    if type_name == "string":
        return '"a"'
    return "1"


def cast_program(source_type: str, target_type: str, *, guard: str = "") -> str:
    return f"""
    main :: fn() {{
        x: {source_type} = {source_literal(source_type)}
        {guard}
        y := cast({target_type}, x)
    }}
    """


@pytest.mark.parametrize("source_type", PRIMITIVES)
@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_all_primitive_pairs_without_nonnegative_proof(source_type: str, target_type: str):
    """Every primitive pair has a deterministic no-proof classification."""
    decision = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=False)
    expected = expected_without_proof(source_type, target_type)
    assert decision.kind is expected
    assert decision.reason


@pytest.mark.parametrize("source_type", PRIMITIVES)
@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_all_primitive_pairs_with_nonnegative_proof(source_type: str, target_type: str):
    """The non-negative proof flag only widens the signed-to-unsigned surface."""
    without_proof = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=False)
    with_proof = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=True)

    if source_type in SIGNED and target_type in UNSIGNED:
        assert with_proof.kind in {CastClass.LOSSLESS, CastClass.PROVABLE_NARROWING}
    else:
        assert with_proof.kind is without_proof.kind


@pytest.mark.parametrize("source_type", PRIMITIVES)
@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_reasons_are_stable_and_nonempty(source_type: str, target_type: str):
    """Repeated classification should not depend on mutable compiler state."""
    first = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=False)
    second = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=False)
    assert first == second
    assert first.reason.strip()


@pytest.mark.parametrize("source_type", PRIMITIVES)
@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_forbidden_pairs_are_not_allowed(source_type: str, target_type: str):
    """FORBIDDEN and allowed stay in sync across the whole primitive matrix."""
    decision = classify_cast(primitive(source_type), primitive(target_type), source_nonnegative=False)
    assert decision.allowed is (decision.kind is not CastClass.FORBIDDEN)


@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_rejects_reference_sources_for_every_primitive_target(target_type: str):
    decision = classify_cast(ReferenceType(I32), primitive(target_type))
    assert decision.kind is CastClass.FORBIDDEN
    assert not decision.allowed


@pytest.mark.parametrize("source_type", PRIMITIVES)
def test_classifier_rejects_reference_targets_for_every_primitive_source(source_type: str):
    decision = classify_cast(primitive(source_type), ReferenceType(I32))
    assert decision.kind is CastClass.FORBIDDEN
    assert not decision.allowed


@pytest.mark.parametrize("target_type", PRIMITIVES)
def test_classifier_rejects_function_sources_for_every_primitive_target(target_type: str):
    decision = classify_cast(FunctionType((I32,), I32), primitive(target_type))
    assert decision.kind is CastClass.FORBIDDEN
    assert not decision.allowed


@pytest.mark.parametrize("source_type", PRIMITIVES)
def test_classifier_rejects_function_targets_for_every_primitive_source(source_type: str):
    decision = classify_cast(primitive(source_type), FunctionType((I32,), I32))
    assert decision.kind is CastClass.FORBIDDEN
    assert not decision.allowed


@pytest.mark.parametrize("source_type", NUMERIC)
@pytest.mark.parametrize("target_type", NUMERIC)
def test_semantic_numeric_cast_matrix_without_guard(source_type: str, target_type: str):
    """Semantic behavior uses literal facts, not only no-proof classification."""
    source = cast_program(source_type, target_type)
    if source_type in FLOATS and target_type in SIGNED + UNSIGNED:
        assert expect_error(source, "cast")
    else:
        assert expect_success(source)


@pytest.mark.parametrize("source_type", SIGNED)
@pytest.mark.parametrize("target_type", UNSIGNED)
def test_semantic_signed_to_unsigned_guarded_by_early_return(source_type: str, target_type: str):
    source = cast_program(source_type, target_type, guard="if x < 0 { ret }")
    assert expect_success(source)


@pytest.mark.parametrize("source_type", SIGNED)
@pytest.mark.parametrize("target_type", UNSIGNED)
def test_semantic_signed_to_unsigned_guarded_inside_positive_branch(source_type: str, target_type: str):
    source = f"""
    main :: fn() {{
        x: {source_type} = {source_literal(source_type)}
        if x >= 0 {{
            y := cast({target_type}, x)
        }}
    }}
    """
    assert expect_success(source)


@pytest.mark.parametrize("target_type", NON_NUMERIC)
@pytest.mark.parametrize("source_type", PRIMITIVES)
def test_semantic_rejects_casts_to_non_numeric_primitives(source_type: str, target_type: str):
    assert expect_error(cast_program(source_type, target_type), "numeric")


@pytest.mark.parametrize("source_type", NON_NUMERIC)
@pytest.mark.parametrize("target_type", NUMERIC)
def test_semantic_rejects_casts_from_non_numeric_primitives(source_type: str, target_type: str):
    assert expect_error(cast_program(source_type, target_type), "numeric")


def test_codegen_refuses_cast_without_semantic_annotation():
    source = """
    main :: fn() {
        x: i32 = 1
        y := cast(i64, x)
    }
    """
    ast = parse_program(source)
    with pytest.raises(CodegenError, match="not approved"):
        ZigCodeGenerator().generate(ast)


def test_backend_plan_is_operation_specific_for_approved_nodes():
    source = """
    main :: fn() {
        arr := [1, 2, 3]
        x := arr[1]
    }
    """
    ast, symbols, node_types = run_semantic_analysis(source)
    safety = SafetyProofPass(symbols, node_types)
    backend_plan = safety.analyze(ast, "<test>")

    index_node = None
    stack = list(ast.declarations or [])
    while stack:
        node = stack.pop()
        if node.kind == NodeKind.INDEX:
            index_node = node
            break
        for attr in ("body", "statements", "value", "expression", "left", "right", "object", "index"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                stack.extend(item for item in child if hasattr(item, "kind"))
            elif hasattr(child, "kind"):
                stack.append(child)

    assert index_node is not None
    assert backend_plan.is_approved(index_node, "index")
    with pytest.raises(KeyError):
        backend_plan.require(index_node, "cast")


def test_direct_use_after_del_is_rejected():
    source = """
    Box :: struct {
        value: i32
    }

    main :: fn() {
        box := new Box
        if box == nil { ret }
        del box
        x := box.value
    }
    """
    assert expect_error(source, "moved or deleted")


def test_assignment_after_del_reinitializes_binding():
    source = """
    Box :: struct {
        value: i32
    }

    main :: fn() {
        box := new Box
        if box == nil { ret }
        del box
        box = new Box
        if box == nil { ret }
        box.value = 2
        del box
    }
    """
    assert expect_success(source)


def test_semantic_cast_annotation_survives_on_ast_node():
    source = """
    main :: fn() {
        x: i32 = 1
        y := cast(i64, x)
    }
    """
    ast, _, _ = run_semantic_analysis(source)
    stack = list(ast.declarations or [])
    cast_node = None
    while stack:
        node = stack.pop()
        if node.kind == NodeKind.CAST:
            cast_node = node
            break
        for attr in ("body", "statements", "value", "expression", "left", "right"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                stack.extend(item for item in child if hasattr(item, "kind"))
            elif hasattr(child, "kind"):
                stack.append(child)

    assert cast_node is not None
    assert getattr(cast_node, "cast_decision").allowed
