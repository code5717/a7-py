"""B2 uses canonical prelude types through checked I/O and ordinary modules."""

import pytest

from conftest import build_and_run, expect_exit, expect_ok

IO = 'io :: import "std/io"\n'


@pytest.mark.parametrize('hook', ['print', 'println', 'eprintln'])
@pytest.mark.parametrize('context', ['return', 'initializer'])
def test_void_io_results_reject_value_contexts(tmp_path, hook, context):
    call = f'io.{hook}("x")'
    source = (f'f :: fn() i32 {{ ret {call} }}\nmain :: fn() {{}}'
              if context == 'return' else f'main :: fn() {{ value: i32 = {call} }}')
    expect_exit(IO + source, tmp_path, 6,
                'Return type mismatch' if context == 'return' else 'Type mismatch')


def test_void_io_calls_remain_valid_statements(tmp_path):
    expect_ok(IO + 'main :: fn() { io.print("x"); io.println("x"); io.eprintln("x") }', tmp_path)


@pytest.mark.parametrize('argument, declaration, message', [
    ('', '', 'expects 1 arguments, got 0'),
    ('"buffer"', '', "expected '[]u8', got 'string'"),
    ('buf[0..], buf[0..]', 'buf: [8]u8', 'expects 1 arguments, got 2'),
    ('buf[0..]', 'buf: [8]u16', "expected '[]u8', got '[]u16'"),
    ('buf', 'buf: [8]u8', "expected '[]u8', got '[8]u8'"),
])
def test_read_line_checks_fixed_signature(tmp_path, argument, declaration, message):
    expect_exit(IO + f'main :: fn() {{ {declaration}; io.read_line({argument}) }}',
                tmp_path, 6, message)


def test_nested_prelude_type_is_emitted_without_a_direct_constructor(tmp_path):
    result = expect_ok('f :: fn(r: Result(Option(i32), i32)) {}\nmain :: fn() {}', tmp_path)
    from pathlib import Path
    emitted = Path(result.output_path).read_text()
    assert 'fn user__a7_Option_1(' in emitted
    assert 'fn user__a7_Result_1(' in emitted


@pytest.mark.parametrize('declaration', [
    'S :: struct { r: Option(Result(i32, io.IoErr)) }',
    'S :: struct { r: [2]Option(Result(i32, io.IoErr)) }',
    'S :: struct { r: []Option(Result(i32, io.IoErr)) }',
    'S :: struct { r: ref Option(Result(i32, io.IoErr)) }',
    'S :: struct { r: fn(Option(i32)) Result(i32, io.IoErr) }',
    'S :: union(tag) { r: Option(Result(i32, io.IoErr)), other: i32 }',
    'S :: [2]Option(Result(i32, io.IoErr))',
])
def test_declaration_only_prelude_dependencies(tmp_path, declaration):
    # No value constructor or local variable can independently mark these types.
    from pathlib import Path
    result = expect_ok(IO + declaration + '\nf :: fn(s: S) {}\nmain :: fn() {}', tmp_path)
    emitted = Path(result.output_path).read_text()
    assert 'fn user__a7_Option_1(' in emitted
    assert 'fn user__a7_Result_1(' in emitted
    assert 'const user__a7_IoErr_1 = enum' in emitted


def test_saved_wrapped_result_and_imported_error_type(tmp_path):
    expect_ok(IO + '''
read :: fn(buf: []u8) Result(usize, io.IoErr) { ret io.read_line(buf) }
main :: fn() {
    buf: [8]u8
    result := read(buf[0..])
    count: usize = match result { case .ok(n): n; case .err(e): 0 }
    io.println("{}", count)
}
''', tmp_path)


def test_result_identity_is_shared_across_files_and_import_spellings(tmp_path):
    (tmp_path / 'producer.a7').write_text('''io :: import "io"
make :: fn() Result(usize, io.IoErr) { ret io.println_ok("a") }
''')
    (tmp_path / 'consumer.a7').write_text('''console :: import "std/io"
count :: fn(r: Result(usize, console.IoErr)) usize {
    ret match r { case .ok(n): n; case .err(e): 0 }
}
''')
    expect_ok(IO + '''producer :: import "producer"
consumer :: import "consumer"
main :: fn() { io.println("{}", consumer.count(producer.make())) }
''', tmp_path)


def test_error_type_requires_import_and_preserves_nominal_identity(tmp_path):
    expect_exit('main :: fn() { e: IoErr }', tmp_path, 6, "Undefined type")
    expect_exit(IO + '''OtherErr :: enum { ReadFailed }
f :: fn() Result(usize, OtherErr) { ret io.println_ok("x") }
main :: fn() {}
''', tmp_path, 6, 'Return type mismatch')


@pytest.mark.parametrize('declaration', [
    'Option :: union(tag) { some: $T, none: bool }',
    'Result :: union(tag) { ok: $T, err: $E }',
    'f :: fn(Option: i32) {}',
    'f :: fn(x: $Result) $Result { ret x }',
    'f :: fn() { Result := 1 }',
    'f :: fn() { for Option in [1, 2] {} }',
    'f :: fn() { r := Result(i32,i32){ok:1}; match r { case .ok(Result): {}; case .err(e): {} } }',
])
def test_prelude_names_cannot_be_redeclared(tmp_path, declaration):
    expect_exit(declaration + '\nmain :: fn() {}', tmp_path, 6, 'Already defined')


def test_imported_prelude_collision_names_its_own_file(tmp_path):
    path = tmp_path / 'part.a7'
    path.write_text('Result :: struct { value: i32 }')
    result = expect_exit('part :: import "part"\nmain :: fn() {}', tmp_path, 6, "Struct 'Result'")
    assert any(detail['file'] == str(path) for detail in result.failure.details)


def test_prelude_reservation_does_not_ban_members_or_capture_internal_names(tmp_path):
    expect_ok(IO + '''S :: struct { Option: i32, Result: i32 }
E :: enum { Option, Result }
main :: fn() {
    __a7_Result := 7
    __a7_IoErr := 9
    s := S{Option: __a7_Result, Result: __a7_IoErr}
    e := E.Result
    r := Result(i32, i32){ok: s.Result}
    match r { case .ok(n): { io.println("{}", n) }; case .err(err): {} }
    io.println_ok("{}", e)
}
''', tmp_path)


@pytest.mark.parametrize('path', ['std/io', 'std/result'])
def test_project_cannot_supply_reserved_std_module(tmp_path, path):
    (tmp_path / 'std').mkdir()
    (tmp_path / (path.removeprefix('./') + '.a7')).write_text('value :: 7')
    expect_exit(f'lib :: import "{path}"\nmain :: fn() {{}}', tmp_path, 3, 'reserved')


def test_buffer_write_preserves_copied_byte_but_reloading_loses_nonzero_proof(tmp_path):
    prefix = IO + '''main :: fn() {
    buf: [8]u8
    value := buf[0]
    if value != 0 {
        io.read_line(buf[0..])
'''
    suffix = '''        quotient: u8 = 1 / value
        io.println("{}", quotient)
    }
}
'''
    expect_ok(prefix + suffix, tmp_path)
    expect_exit(prefix + 'value = buf[0]\n' + suffix, tmp_path, 6, 'Divisor not proven non-zero')


@pytest.mark.zig
@pytest.mark.parametrize('profile', ['debug', 'release', 'fast'])
def test_native_canonical_result_and_byte_buffer(profile, tmp_path, zig):
    source = IO + '''
read :: fn(buf: []u8) Result(usize, io.IoErr) { ret io.read_line(buf) }
id :: fn(value: $T) $T { ret value }
nested :: fn(result: Result(Option(i32), i32)) {
    match result {
        case .ok(option): {
            match option {
                case .some(n): { io.println("nested {}", n) }
                case .none(empty): { io.println("none") }
            }
        }
        case .err(e): { io.println("nested err") }
    }
}
show :: fn(result: Result(usize, io.IoErr)) {
    match result {
        case .ok(n): { io.println("count {}", n) }
        case .err(e): { io.println("err {}", e) }
    }
}
main :: fn() {
    buf: [4]u8
    show(id(read(buf[0..])))
    io.println("bytes {} {}", buf[0], buf[1])
    show(read(buf[0..]))
    show(read(buf[0..]))
    show(read(buf[0..0]))
    show(io.println_ok("hi"))
    show(Result(usize, io.IoErr){err: io.IoErr.ReadFailed})
    zero: Result(Option(i32), i32)
    nested(zero)
}
'''
    result = build_and_run(source, tmp_path, zig, profile=profile, stdin='A\nBC')
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'count 2\nbytes 65 10\ncount 2\nerr .EndOfStream\ncount 0\nhi\ncount 3\nerr .ReadFailed\nnested 0\n'
    assert result.stderr == ''


@pytest.mark.parametrize('path', ['./std/local', './std/../helper', './link', 'pkg/std/local'])
def test_explicit_relative_paths_are_not_std_namespace(tmp_path, path):
    (tmp_path / 'std').mkdir()
    (tmp_path / 'pkg/std').mkdir(parents=True)
    for relative in ('std/local.a7', 'pkg/std/local.a7', 'helper.a7'):
        (tmp_path / relative).write_text('value :: fn() i32 { ret 7 }')
    (tmp_path / 'link.a7').symlink_to('std/local.a7')
    expect_ok(f'local :: import "{path}"\nmain :: fn() {{ n := local.value() }}', tmp_path)


@pytest.mark.parametrize('path, expected', [
    ('../std/local', 0), ('./std/local', 0), ('../pkg/std/local', 0), ('std/local', 3),
])
def test_nested_relative_imports_keep_importer_base(tmp_path, path, expected):
    (tmp_path / 'nested/std').mkdir(parents=True)
    (tmp_path / 'std').mkdir()
    (tmp_path / 'pkg/std').mkdir(parents=True)
    for relative in ('std/local.a7', 'nested/std/local.a7', 'pkg/std/local.a7'):
        (tmp_path / relative).write_text('value :: fn() i32 { ret 7 }')
    (tmp_path / 'nested/part.a7').write_text(f'local :: import "{path}"\nvalue :: fn() i32 {{ ret local.value() }}')
    source = 'part :: import "nested/part"\nmain :: fn() { n := part.value() }'
    if expected == 0:
        expect_ok(source, tmp_path)
    else:
        expect_exit(source, tmp_path, 3, 'reserved')


def test_reserved_path_cannot_escape_to_project_file(tmp_path):
    (tmp_path / 'helper.a7').write_text('value :: 7')
    expect_exit('lib :: import "std/../helper"\nmain :: fn() {}', tmp_path, 3,
                'Invalid reserved module path')


@pytest.mark.zig
@pytest.mark.parametrize('profile', ['debug', 'release', 'fast'])
@pytest.mark.parametrize('a7_source, zig_argument', [
    ('accept :: fn(r: Result(Option(i32), i32)) i32 { ret 7 }', '.{ .err = 23 }'),
    (IO + 'S :: struct { r: Option(Result(i32, io.IoErr)) }\n'
     'accept :: fn(s: S) i32 { ret 7 }', '.{ .r = .{ .none = true } }'),
])
def test_native_signature_only_nested_prelude(tmp_path, zig, profile, a7_source, zig_argument):
    # The Zig harness makes the A7 library signature reachable without an A7
    # constructor or variable adding a second checked-type discovery route.
    import subprocess
    from pathlib import Path
    from conftest import ZIG_MODE, shared_zig_cache

    result = expect_ok(a7_source, tmp_path, is_library=True, profile=profile)
    source = Path(result.output_path)
    source.write_text(source.read_text() + '\npub fn main() u8 { return @intCast(accept(' + zig_argument + ') - 7); }\n')
    cache = shared_zig_cache()
    binary = tmp_path / 'signature-only'
    build = subprocess.run([zig, 'build-exe', str(source), '-O', ZIG_MODE[profile],
                            '--cache-dir', str(cache / 'local'),
                            '--global-cache-dir', str(cache / 'global'),
                            '-femit-bin=' + str(binary)], capture_output=True, text=True)
    assert build.returncode == 0, build.stdout + build.stderr
    run = subprocess.run([str(binary)], capture_output=True, text=True)
    assert (run.returncode, run.stdout, run.stderr) == (0, '', '')
