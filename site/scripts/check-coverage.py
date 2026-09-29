#!/usr/bin/env python3
"""Check documentation dispositions against source inventories without importing A7.

This checks inventory completeness and evidence paths. It does not establish
whether a documented language feature executes correctly.
"""
from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

SITE = Path(__file__).resolve().parent.parent
ROOT = SITE.parent
STATUSES = {'supported', 'limited', 'unavailable', 'planned', 'unverified'}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def same_inventory(label: str, source: list[str], documented: list[str]) -> None:
    missing = Counter(source) - Counter(documented)
    extra = Counter(documented) - Counter(source)
    require(not missing and not extra,
            f'{label}: missing={dict(missing)}, extra={dict(extra)}')


def headings(markdown: str) -> list[str]:
    """Read ATX headings while excluding fenced examples, including tilde fences."""
    result = []
    fence = None
    for line in markdown.splitlines():
        if fence:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) +
                            '{' + str(fence[1]) + r',}\s*', line):
                fence = None
            continue
        opening = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if opening:
            marker, info = opening.groups()
            if marker[0] != '`' or '`' not in info:
                fence = (marker[0], len(marker))
            continue
        match = re.match(r'^ {0,3}#{2,4}\s+(.+?)\s*$', line)
        if match:
            title = re.sub(r'\s+#+\s*$', '', match.group(1))
            if title != 'Table of Contents':
                result.append(title)
    return result


def named_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name]
    require(len(matches) == 1, f'Expected one function {name}, found {len(matches)}')
    return matches[0]


def dictionary_keys(node: ast.AST, label: str) -> list[str]:
    require(isinstance(node, ast.Dict), f'{label}: expected literal dictionary')
    values = []
    for key in node.keys:
        require(isinstance(key, ast.Constant) and isinstance(key.value, str),
                f'{label}: nonliteral dictionary key needs checker support')
        values.append(key.value)
    return values


def assigned_dictionary(tree: ast.AST, name: str) -> list[str]:
    matches = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    require(len(matches) == 1, f'Expected one dictionary assignment to {name}')
    return dictionary_keys(matches[0], name)


def operators(tree: ast.AST) -> list[str]:
    function = named_function(tree, '_try_operator')
    spellings = set(assigned_dictionary(function, 'operators'))
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == '_add_token' and len(node.args) > 1):
            value = node.args[1]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                spellings.add(value.value)
            elif not isinstance(value, ast.Name) or value.id != 'char':
                raise ValueError('Operator token emission changed; update inventory extraction')
    return sorted(spellings)


def stdlib_operations() -> list[str]:
    """Follow default registrar calls and inspect their function assignments.

    Handle literal function registration and the current dictionary-driven loop.
    Fail if a registration uses an unknown shape instead of silently skipping it.
    """
    tree = ast.parse((ROOT / 'a7/stdlib/__init__.py').read_text())
    defaults = named_function(tree, '_register_defaults')
    imports = {}
    for node in defaults.body:
        if isinstance(node, ast.ImportFrom):
            require(node.level == 1 and node.module is not None,
                    'Stdlib registrar import shape changed')
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module, alias.name)
    calls = [n for n in defaults.body if isinstance(n, ast.Expr)
             and isinstance(n.value, ast.Call)]
    require(bool(calls), 'No default stdlib registrar calls found')
    result = []
    for statement in calls:
        call = statement.value
        require(isinstance(call.func, ast.Name) and call.func.id in imports,
                'Unknown stdlib registrar call; update checker')
        file, name = imports[call.func.id]
        function = named_function(ast.parse((ROOT / f'a7/stdlib/{file}.py').read_text()), name)
        modules = [n for n in ast.walk(function) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == 'StdlibModule']
        require(len(modules) == 1, f'{file}: expected one module registration')
        names = [k.value for k in modules[0].keywords if k.arg == 'name']
        require(len(names) == 1 and isinstance(names[0], ast.Constant)
                and isinstance(names[0].value, str), f'{file}: nonliteral module name')
        module = names[0].value
        loop_values = {}
        for node in ast.walk(function):
            if not isinstance(node, ast.For):
                continue
            iterator = node.iter
            require(isinstance(iterator, ast.Call)
                    and isinstance(iterator.func, ast.Attribute)
                    and iterator.func.attr == 'items'
                    and isinstance(iterator.func.value, ast.Name)
                    and isinstance(node.target, ast.Tuple)
                    and isinstance(node.target.elts[0], ast.Name),
                    f'{file}: unknown registration loop')
            loop_values[node.target.elts[0].id] = assigned_dictionary(
                function, iterator.func.value.id)
        assignments = 0
        for node in ast.walk(function):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Attribute)
                        and target.value.attr == 'functions'):
                    continue
                assignments += 1
                key = target.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    names = [key.value]
                elif isinstance(key, ast.Name) and key.id in loop_values:
                    names = loop_values[key.id]
                else:
                    raise ValueError(f'{file}: unknown function registration key')
                result.extend(f'std.{module}.{value}' for value in names)
        require(assignments > 0, f'{file}: no function registrations found')
    return result


def escape_cell(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def main() -> None:
    features = json.loads((SITE / 'content/features.json').read_text())
    require(isinstance(features, list) and bool(features), 'Feature list is empty or invalid')
    ids = []
    for feature in features:
        require(isinstance(feature, dict), 'Feature must be an object')
        for field in ('id', 'status', 'qualification', 'topic'):
            require(isinstance(feature.get(field), str) and bool(feature[field].strip()),
                    f'Invalid {field} in feature {feature}')
        ids.append(feature['id'])
        require(feature['status'] in STATUSES, f"Invalid status: {feature['id']}")
        topic = feature['topic']
        require(bool(re.fullmatch(r'[a-z0-9-]+(?:/[a-z0-9-]+)*', topic)),
                f'Invalid topic path: {topic}')
        require((SITE / 'public/docs' / f'{topic}.md').is_file(), f'Missing topic: {topic}')
        evidence = feature.get('evidence')
        require(isinstance(evidence, list) and bool(evidence), f'Missing evidence: {feature["id"]}')
        for link in evidence:
            require(isinstance(link, str), f'Non-string evidence: {feature["id"]}')
            parsed = urlparse(link)
            prefix = '/code5717/a7-py/blob/master/'
            require(parsed.scheme == 'https' and parsed.netloc == 'github.com'
                    and parsed.path.startswith(prefix), f'Unexpected evidence URL: {link}')
            path = (ROOT / unquote(parsed.path[len(prefix):])).resolve()
            require(path.is_relative_to(ROOT) and path.is_file(), f'Missing evidence file: {link}')
    require(len(ids) == len(set(ids)), 'Duplicate feature IDs')
    spec = (ROOT / 'docs/SPEC.md').read_text()
    spec_records = [f.get('title', '') for f in features
                    if f['id'].startswith('spec-') and not f['id'].startswith('spec-word-')]
    same_inventory('SPEC headings', headings(spec), spec_records)
    tokens = ast.parse((ROOT / 'a7/tokens.py').read_text())
    same_inventory('Keywords', assigned_dictionary(tokens, 'KEYWORDS'),
                   [f.get('title', '') for f in features if f['id'].startswith('keyword-')])
    same_inventory('Operators', operators(tokens),
                   [f.get('title', '') for f in features if f['id'].startswith('operator-')])
    same_inventory('Stdlib registrations', stdlib_operations(),
                   [f.get('title', '') for f in features if f['id'].startswith('stdlib-')])
    same_inventory('Examples', [p.name for p in (ROOT / 'examples').glob('*.a7')],
                   [f.get('title', '') for f in features if f['id'].startswith('example-')])
    tensor = spec.split('## 9. Planned Array Programming for AI', 1)[1].split('## 10.', 1)[0]
    same_inventory('Tensor names', sorted(set(re.findall(r'\btensor_[a-zA-Z_]\w*', tensor))),
                   [f.get('title', '') for f in features if f['id'].startswith('planned-tensor-')])
    planned = spec.split('### 11.2 Standard Library Functions', 1)[1].split('## 12.', 1)[0]
    same_inventory('Planned stdlib signatures',
                   sorted(set(re.findall(r'^([a-zA-Z_]\w*)\s*::\s*fn', planned, re.M))),
                   [f.get('title', '') for f in features if f['id'].startswith('planned-stdlib-')])
    coverage = (SITE / 'docs/coverage.md').read_text()
    matrix = coverage.split('## Coverage matrix', 1)[1].split('\n## ', 1)[0]
    actual = [line for line in matrix.splitlines() if line.startswith('| ')]
    expected = ['| ID or source item | Status | Topic | Disposition |',
                '| --- | --- | --- | --- |']
    for feature in features:
        topic = feature['topic']
        expected.append('| ' + escape_cell(feature.get('title', feature['id'])) +
                        ' | ' + feature['status'] + ' | [' + topic +
                        '](../public/docs/' + topic + '.md) | ' +
                        escape_cell(feature['qualification']) + ' |')
    same_inventory('Coverage matrix rows', expected, actual)
    print(f'Coverage check passed: {len(features)} records; SPEC headings, keywords, '
          'operators, stdlib, examples, proposed APIs, evidence paths, and matrix agree.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, IndexError, OSError, SyntaxError) as error:
        print(f'Coverage check failed: {error}', file=sys.stderr)
        sys.exit(1)
