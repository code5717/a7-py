"""Canonical prelude unions and checked recoverable I/O through the full pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from a7.stdlib import StdlibRegistry
from conftest import shared_zig_cache

UV = shutil.which("uv")

IO_IMPORT = 'io :: import "std/io"\n'

OPTION_UNION = ""

RESULT_UNION = ""


def run_a7(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    assert UV is not None, "uv is required to run the a7 CLI"
    env = dict(os.environ, PYTHONPATH=str(PROJECT_ROOT))
    return subprocess.run(
        [UV, "run", "a7", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def compile_source(tmp_path: Path, name: str, source: str) -> tuple[int, str]:
    src = tmp_path / name
    src.write_text(source, encoding="utf-8")
    proc = run_a7([str(src), "-o", str(tmp_path / (name + ".zig"))], PROJECT_ROOT)
    return proc.returncode, proc.stdout + proc.stderr


def codegen_to_zig(source: str) -> str:
    """Use the supported pipeline; any frontend failure fails the native fixture."""
    from tempfile import TemporaryDirectory
    from a7.compile import A7Compiler

    with TemporaryDirectory(prefix="a7-typed-io-") as directory:
        root = Path(directory)
        src = root / "main.a7"
        src.write_text(source, encoding="utf-8")
        output = root / "main.zig"
        result = A7Compiler().compile_file_detailed(str(src), str(output))
        assert result.ok, result.failure
        return output.read_text(encoding="utf-8")


def build_zig(zig_code: str, tmp_path: Path, zig: str, name: str) -> Path:
    """Build emitted Zig into a binary. `zig ast-check` is not a build check."""
    cache = shared_zig_cache()
    src = tmp_path / (name + ".zig")
    src.write_text(zig_code, encoding="utf-8")
    binary = tmp_path / name
    build = subprocess.run(
        [zig, "build-exe", str(src),
         "--cache-dir", str(cache / "local"),
         "--global-cache-dir", str(cache / "global"),
         "-femit-bin=" + str(binary)],
        capture_output=True, text=True, timeout=120,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    return binary


class TestRegistry:
    def test_println_ok_resolves(self):
        registry = StdlibRegistry()
        assert registry.resolve_call("io", "println_ok") == "std.io.println_ok"
        assert registry.resolve_call("std/io", "println_ok") == "std.io.println_ok"

    def test_read_line_resolves(self):
        registry = StdlibRegistry()
        assert registry.resolve_call("io", "read_line") == "std.io.read_line"
        assert registry.resolve_call("std/io", "read_line") == "std.io.read_line"

    def test_panicking_helpers_unchanged(self):
        registry = StdlibRegistry()
        assert registry.resolve_call("io", "println") == "std.io.println"
        assert registry.resolve_call("io", "print") == "std.io.print"
        assert registry.resolve_call("io", "eprintln") == "std.io.eprintln"


class TestShadowing:
    """Tag spellings remain identifiers; user unions retain collision checks."""

    def test_some_none_ok_err_are_ordinary_names(self, tmp_path: Path):
        code, out = compile_source(tmp_path, "shadowok.a7", IO_IMPORT + """
        main :: fn() {
            ok := 1
            err := 2
            some := 3
            none := 4
            option_value := 5
            result_value := 6
            io.println("{}", ok + err + some + none + option_value + result_value)
        }
        """)
        assert code == 0, out

    def test_shadow_names_run(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "shadowrun.a7", IO_IMPORT + """
        main :: fn() {
            ok := 1
            err := 2
            some := 3
            none := 4
            option_value := 5
            result_value := 6
            io.println("{}", ok + err + some + none + option_value + result_value)
        }
        """)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "shadowrun.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "21"

    def test_duplicate_local_is_already_defined(self, tmp_path: Path):
        code, out = compile_source(tmp_path, "shadowdup.a7", IO_IMPORT + """
        main :: fn() {
            ok := 1
            ok := 2
            io.println("{}", ok)
        }
        """)
        assert code == 6, out
        assert "Already defined" in out
        assert "'ok'" in out

    def test_duplicate_union_is_already_defined(self, tmp_path: Path):
        code, out = compile_source(tmp_path, "shadowunion.a7", IO_IMPORT + """
        Maybe :: union(tag) {
            some: i32,
            none: bool,
        }

        Maybe :: union(tag) {
            some: i32,
            none: bool,
        }

        main :: fn() {
            io.println("hi")
        }
        """)
        assert code == 6, out
        assert "Already defined" in out
        assert "Union 'Maybe'" in out

    def test_tag_and_local_share_spelling(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "shadowtag.a7", IO_IMPORT + """
        Outcome :: union(tag) {
            ok: i32,
            err: i32,
        }

        main :: fn() {
            ok := 10
            r := Outcome{ok: 1}
            out := match r {
                case .ok(v): v + ok
                case .err(e): e
            }
            io.println("{}", out)
        }
        """)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "shadowtag.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "11"


class TestOptionResultMatch:
    """Packet sections 3a/3b: ordinary generic unions, explicit match only."""

    PROGRAM = IO_IMPORT + OPTION_UNION + RESULT_UNION + """
    lookup :: fn(id: i32) Option(i32) {
        match id {
            case 1: {
                ret Option(i32){some: 100}
            }
            else: {
                ret Option(i32){none: true}
            }
        }
    }

    parse_port :: fn(ok: bool) Result(i32, i32) {
        match ok {
            case true: {
                ret Result(i32, i32){ok: 8080}
            }
            else: {
                ret Result(i32, i32){err: -1}
            }
        }
    }

    main :: fn() {
        name := match lookup(1) {
            case .some(v): v
            case .none: 0
        }
        io.println("{}", name)
        missing := match lookup(9) {
            case .some(v): v
            case .none: 0
        }
        io.println("{}", missing)
        port := match parse_port(true) {
            case .ok(v): v
            case .err(e): e
        }
        io.println("{}", port)
        bad := match parse_port(false) {
            case .ok(v): v
            case .err(e): e
        }
        io.println("{}", bad)
    }
    """

    def test_compiles(self, tmp_path: Path):
        code, out = compile_source(tmp_path, "optmatch.a7", self.PROGRAM)
        assert code == 0, out

    def test_runs(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "optrun.a7", self.PROGRAM)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "optrun.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.split() == ["100", "0", "8080", "-1"]

    def test_explicit_match_propagates_err(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "propagate.a7", IO_IMPORT + RESULT_UNION + """
        parse_port :: fn(ok: bool) Result(i32, i32) {
            match ok {
                case true: {
                    ret Result(i32, i32){ok: 8080}
                }
                else: {
                    ret Result(i32, i32){err: -1}
                }
            }
        }

        wrap :: fn(ok: bool) Result(i32, i32) {
            ret match parse_port(ok) {
                case .ok(v): Result(i32, i32){ok: v}
                case .err(e): Result(i32, i32){err: e}
            }
        }

        main :: fn() {
            out := match wrap(false) {
                case .ok(v): v
                case .err(e): e
            }
            io.println("{}", out)
        }
        """)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "propagate.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == "-1"

    def test_cross_kind_mixing_is_a_type_error(self, tmp_path: Path):
        code, out = compile_source(tmp_path, "crosskind.a7", IO_IMPORT + """
        f :: fn() Result(i32, i32) {
            ret Option(i32){none: true}
        }

        main :: fn() {
            io.println("hi")
        }
        """)
        assert code == 6, out
        assert "Return type mismatch" in out


class TestPrintlnOk:
    def test_statement_compiles_and_runs(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "pok.a7", IO_IMPORT + """
        main :: fn() {
            io.println_ok("hello")
            io.println_ok("n={}", 42)
        }
        """)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "pok.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == ["hello", "n=42"]

    def test_no_arg_form_and_mixed_with_println(self, tmp_path: Path, zig: str):
        code, out = compile_source(tmp_path, "pokmix.a7", IO_IMPORT + """
        main :: fn() {
            io.println("plain")
            io.println_ok("ok")
            io.println_ok()
        }
        """)
        assert code == 0, out
        proc = subprocess.run(
            [zig, "run", str(tmp_path / "pokmix.a7.zig")],
            cwd=tmp_path, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == ["plain", "ok", ""]

    def test_emission_constructs_result_union(self, tmp_path: Path):
        zig_code = codegen_to_zig(IO_IMPORT + """
        main :: fn() {
            io.println_ok("hello")
        }
        """)
        assert "EndOfStream," in zig_code
        assert "const __a7_IoResult = user__a7_Result_1(usize, user__a7_IoErr_1);" in zig_code
        assert "__a7_stdout_print_ok(\"hello\\n\", .{})" in zig_code
        assert "catch return .{ .err = .WriteFailed }" in zig_code
        assert "catch return .{ .err = .FlushFailed }" in zig_code
        assert "return .{ .ok = std.fmt.count(fmt, args) };" in zig_code
        assert "_ = __a7_stdout_print_ok(" in zig_code

    def test_match_on_call_has_result_payloads(self, tmp_path: Path):
        """The success arm has a usize payload and joins the literal fallback."""
        code, out = compile_source(tmp_path, "pokseam.a7", IO_IMPORT + """
        main :: fn() {
            n := match io.println_ok("hi") {
                case .ok(wrote): wrote
                case .err(e): 0
            }
            io.println("{}", n)
        }
        """)
        assert code == 0, out


class TestReadLine:
    """Checked byte slices reach the persistent native reader."""

    SHOW = IO_IMPORT + """
    show :: fn(buf: []u8) {
        match io.read_line(buf) {
            case .ok(n): { io.println("ok {}", n) }
            case .err(e): { io.println("err {}", e) }
        }
    }
    """

    def test_two_reads_return_two_lines(self, tmp_path: Path, zig: str):
        """A reader created inside the helper drops the bytes it buffered past
        the first newline, so a later read misses them. `line_len` is 8 for a
        buffer that never received a newline."""
        binary = build_zig(codegen_to_zig(IO_IMPORT + """
        line_len :: fn(buf: [8]u8) usize {
            i: usize = 0
            while i < 8 {
                if buf[i] == 10 {
                    ret i
                }
                i += 1
            }
            ret 8
        }
        main :: fn() {
            a: [8]u8
            b: [8]u8
            io.read_line(a[0..])
            io.read_line(b[0..])
            io.println("{} {}", line_len(a), line_len(b))
        }
        """), tmp_path, zig, "rltwo")
        proc = subprocess.run([str(binary)], input="hi\nyo\n", capture_output=True, text=True, timeout=30)
        assert (proc.returncode, proc.stdout) == (0, "2 2\n"), proc.stderr

    def test_ok_counts_bytes_and_end_of_input_is_its_own_error(self, tmp_path: Path, zig: str):
        """`ok` counts the newline. A last line without a newline is still a
        line; only a read that gets no byte reports EndOfStream."""
        binary = build_zig(codegen_to_zig(self.SHOW + """
        main :: fn() {
            buf: [8]u8
            show(buf[0..])
            show(buf[0..])
            show(buf[0..])
        }
        """), tmp_path, zig, "rleof")
        proc = subprocess.run([str(binary)], input="hi\nyo", capture_output=True, text=True, timeout=30)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.splitlines() == ["ok 3", "ok 2", "err .EndOfStream"]

    def test_read_error_is_not_reported_as_end_of_input(self, tmp_path: Path, zig: str):
        """stdin is a directory, so `read` fails with EISDIR."""
        binary = build_zig(codegen_to_zig(self.SHOW + """
        main :: fn() {
            buf: [8]u8
            show(buf[0..])
        }
        """), tmp_path, zig, "rlerr")
        directory = os.open(tmp_path, os.O_RDONLY)
        try:
            proc = subprocess.run([str(binary)], stdin=directory, capture_output=True, text=True, timeout=30)
        finally:
            os.close(directory)
        assert (proc.returncode, proc.stdout) == (0, "err .ReadFailed\n"), proc.stderr

    def test_prompt_is_flushed_before_the_read_blocks(self, tmp_path: Path, zig: str):
        """stdout is buffered. Without a flush before the read, the prompt
        stays in the buffer while the program waits for input."""
        import select

        binary = build_zig(codegen_to_zig(IO_IMPORT + """
        main :: fn() {
            buf: [8]u8
            io.print("name> ")
            io.read_line(buf[0..])
        }
        """), tmp_path, zig, "rlprompt")
        proc = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            readable, _, _ = select.select([proc.stdout], [], [], 10)
            assert readable, "no prompt on stdout while the program waits on stdin"
            assert os.read(proc.stdout.fileno(), 64) == b"name> "
            proc.stdin.write(b"x\n")
            proc.stdin.close()
            assert proc.wait(timeout=10) == 0
        finally:
            proc.kill()
            proc.stdout.close()

    def test_cli_accepts_mutable_byte_slice(self, tmp_path: Path):
        """A byte buffer is a typed argument, not a format string."""
        code, out = compile_source(tmp_path, "rlseam.a7", IO_IMPORT + """
        main :: fn() {
            buf: [16]u8
            io.read_line(buf[0..])
        }
        """)
        assert code == 0, out


    def test_full_buffer_then_remaining_line(self, tmp_path: Path, zig: str):
        binary = build_zig(codegen_to_zig(self.SHOW + """
        main :: fn() {
            buf: [4]u8
            show(buf[0..])
            io.println("bytes {} {}", buf[0], buf[3])
            show(buf[0..])
            io.println("bytes {} {}", buf[0], buf[2])
            show(buf[0..])
        }
        """), tmp_path, zig, "rlfull")
        proc = subprocess.run([str(binary)], input="abcdef\n", capture_output=True, text=True, timeout=30)
        assert (proc.returncode, proc.stdout, proc.stderr) == (
            0, "ok 4\nbytes 97 100\nok 3\nbytes 101 10\nerr .EndOfStream\n", "",
        )
