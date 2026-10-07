"""Deep statement emission preserves Zig text without Python call-stack growth."""
import subprocess
import sys
import textwrap

import pytest

from a7.backends.zig import ZigCodeGenerator
from a7.errors import CodegenError
from a7.parser import Parser
from a7.tokens import Tokenizer


@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
@pytest.mark.parametrize("shape", ["block", "if", "while", "for", "match"])
def test_deep_source_emits_same_zig_at_limit_100(shape, profile, tmp_path):
    code = textwrap.dedent('''
        import pathlib, sys
        from a7.compile import A7Compiler
        shape, profile, directory = sys.argv[1:]
        opening, closing, depth = {
            "block": ("{", "}", 60),
            "if": ("if true {", "}", 35),
            "while": ("while false {", "}", 35),
            "for": ("for {", "}", 35),
            "match": ("match 1 {case 1: {", "}}", 35),
        }[shape]
        path = pathlib.Path(directory) / "deep.a7"
        path.write_text("main :: fn(){" + opening * depth + "x:=1" + closing * depth + "}")
        emitted = []
        for limit in (1000, 100):
            sys.setrecursionlimit(limit)
            result = A7Compiler(build_profile=profile).compile_file_detailed(str(path), str(path.with_suffix(".zig")))
            assert result.ok, result.failure
            emitted.append(result.codegen_result["output_code"])
        assert emitted[0] == emitted[1]
        assert "pub fn main() void" in emitted[1]
    ''')
    result = subprocess.run([sys.executable, "-c", code, shape, profile, str(tmp_path)], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("profile", ["debug", "release", "fast"])
def test_nested_function_backend_at_limit_100(profile):
    # This isolates emission. The safety pass still limits this deep source.
    code = textwrap.dedent('''
        import sys
        from a7.backends.zig import ZigCodeGenerator
        from a7.parser import Parser
        from a7.tokens import Tokenizer
        source = "main :: fn(){" + "".join(f"localfn{i} :: fn() {{" for i in range(60)) + "ret" + "}" * 61
        root = Parser(Tokenizer(source).tokenize()).parse()
        reference = ZigCodeGenerator().generate(root, profile=sys.argv[1])
        sys.setrecursionlimit(100)
        actual = ZigCodeGenerator().generate(root, profile=sys.argv[1])
        assert actual == reference
        assert actual.count("fn __a7_fn_localfn") == 60
        assert "pub fn main() void" in actual
    ''')
    result = subprocess.run([sys.executable, "-c", code, profile], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fall_context_unwinds_on_child_codegen_error_and_generator_reuses():
    # A hand-built backend boundary: semantic analysis rejects this defer.
    root = Parser(Tokenizer("main :: fn(){match 1 {case 1: {defer ret; fall}}}").tokenize()).parse()
    generator = ZigCodeGenerator()
    with pytest.raises(CodegenError, match="'RETURN' cannot be deferred"):
        generator.generate(root)
    assert generator._fall_context_stack == []
    valid = Parser(Tokenizer("main :: fn() {ret}").tokenize()).parse()
    assert generator.generate(valid) == ZigCodeGenerator().generate(valid)
