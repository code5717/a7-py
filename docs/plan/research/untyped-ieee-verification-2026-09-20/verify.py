#!/usr/bin/env python3
"""Independent fixed IEEE expectations; run only against a frozen compiler tree."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


# Fixed from docs/plan/research/untyped-ieee-acceptance-2026-09-20.md.
# Never compute expected bits by parsing the decimal input as a host float.
CASES = [
    ('f32_mid_below', 'f32', '1.000000059604644775390624', '3f800000'),
    ('f32_mid_tie', 'f32', '1.000000059604644775390625', '3f800000'),
    ('f32_mid_above', 'f32', '1.0000000596046447753906250000000000000000000000000000000000000000000000001', '3f800001'),
    ('f64_mid_below', 'f64', '1.00000000000000011102230246251565404236316680908203124', '3ff0000000000000'),
    ('f64_mid_tie', 'f64', '1.00000000000000011102230246251565404236316680908203125', '3ff0000000000000'),
    ('f64_mid_above', 'f64', '1.00000000000000011102230246251565404236316680908203126', '3ff0000000000001'),
    ('f32_under_below', 'f32', '7.006492321624085e-46', '00000000'),
    ('f32_under_above', 'f32', '7.006492321624086e-46', '00000001'),
    ('f32_min_subnormal', 'f32', '1.401298464324817e-45', '00000001'),
    ('f64_under_below', 'f64', '2.4703282292062327e-324', '0000000000000000'),
    ('f64_under_above', 'f64', '2.4703282292062328e-324', '0000000000000001'),
    ('f64_min_subnormal', 'f64', '4.9406564584124654e-324', '0000000000000001'),
    ('f32_max', 'f32', '340282346638528859811704183484516925440.0', '7f7fffff'),
    ('f32_overflow_below', 'f32', '340282356779733661637539395458142568447.0', '7f7fffff'),
    ('f32_overflow_tie', 'f32', '340282356779733661637539395458142568448.0', None),
    ('f64_max', 'f64', '1.7976931348623157e308', '7fefffffffffffff'),
    ('f64_overflow', 'f64', '1.7976931348623159e308', None),
    ('f32_negative_zero', 'f32', '-0.0', '80000000'),
    ('f64_negative_underflow', 'f64', '-1e-400', '8000000000000000'),
]


def execute(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return dict(command=command, cwd=str(cwd), exit=result.returncode,
                stdout=result.stdout, stderr=result.stderr)


def hashes(root):
    files = sorted((root / 'a7').rglob('*.py')) + [root / 'main.py']
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files}


def located_overflow_diagnostic(stdout):
    try:
        stack = [json.loads(stdout)]
    except json.JSONDecodeError:
        return False
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            message = str(value.get('message', '')).lower()
            span = value.get('span')
            if ('overflow' in message or 'fit' in message or 'out of range' in message):
                if isinstance(span, dict) and span.get('start_line', 0) > 0:
                    return True
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return False


def check(case, args):
    name, destination, literal, expected = case
    directory = args.output / name
    directory.mkdir()
    source = ('io :: import "std/io"\nmain :: fn() {\n'
              f'    observed_value: {destination} = {literal}\n'
              '    io.println("{}", observed_value)\n}\n')
    src, zig_source = directory / 'main.a7', directory / 'original.zig'
    src.write_text(source)
    compilation = execute([str(args.python), str(args.compiler_root / 'main.py'),
                           str(src), '--format', 'json', '--output', str(zig_source)],
                          args.compiler_root)
    result = dict(name=name, destination=destination, literal=literal, source=source,
                  expected_bits=expected, expected_rejection=expected is None,
                  compile=compilation, artifact_exists=zig_source.exists(), passed=False)
    if expected is None:
        result['passed'] = (compilation['exit'] == 6 and not zig_source.exists()
                            and located_overflow_diagnostic(compilation['stdout']))
    elif compilation['exit'] == 0 and zig_source.exists():
        original = zig_source.read_text()
        integer = 'u32' if destination == 'f32' else 'u64'
        # Match the whole known generated print call. Change only its argument.
        pattern = r'(__a7_stdout_print\("\{\}\\n", \.\{)observed_value(\}\);)'
        replacement = r'\g<1>@as(' + integer + r', @bitCast(observed_value))\g<2>'
        instrumented, count = re.subn(pattern, replacement, original)
        result.update(original_zig=original, observer_substitutions=count)
        if count == 1:
            observed_path = directory / 'observer.zig'
            observed_path.write_text(instrumented)
            result['observer_zig'] = instrumented
            native = []
            for profile in ('Debug', 'ReleaseFast'):
                binary = directory / ('program-' + profile)
                build = execute([args.zig, 'build-exe', str(observed_path), '-O', profile,
                                 '-femit-bin=' + str(binary)], directory)
                entry = dict(profile=profile, build=build, passed=False)
                if build['exit'] == 0:
                    run = execute([str(binary)], directory)
                    entry['run'] = run
                    entry['passed'] = (run['exit'] == 0 and run['stderr'] == ''
                                       and run['stdout'] == str(int(expected, 16)) + '\n')
                native.append(entry)
            result['native'] = native
            result['passed'] = all(entry['passed'] for entry in native)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler_root', type=Path)
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--zig', default=shutil.which('zig'))
    args = parser.parse_args()
    args.compiler_root = args.compiler_root.resolve()
    # Preserve the venv entrypoint symlink: resolving it bypasses its packages.
    args.python = args.python.absolute()
    args.output = args.output.resolve()
    if not args.zig:
        parser.error('Zig executable required')
    args.zig = str(Path(args.zig).resolve())
    assert all(len(case[2]) <= 100 for case in CASES)
    args.output.mkdir(parents=True, exist_ok=False)
    before = hashes(args.compiler_root)
    version = execute([args.zig, 'version'], args.compiler_root)
    if version['exit'] != 0 or version['stdout'].strip() != '0.16.0':
        raise SystemExit('Expected Zig 0.16.0, got ' + repr(version))
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda case: check(case, args), CASES))
    after = hashes(args.compiler_root)
    report = dict(compiler_root=str(args.compiler_root), zig_version=version,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  source_hashes_before=before, source_hashes_after=after,
                  source_unchanged=before == after, parallel_workers=3,
                  observation_boundary='Only final generated print argument is changed to expose stored IEEE bits. Ordinary A7 float formatting remains unverified.',
                  cases=results, passed=before == after and all(r['passed'] for r in results))
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'failed': [r['name'] for r in results if not r['passed']],
                      'report': str(args.output / 'report.json')}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
