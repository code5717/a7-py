import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;C=E.parent/'candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((E/'source-manifest.json').read_text())
for entry in m['files']:
 assert sha(C/entry['path'])==entry['candidate_sha256']==sha(E/'final-sources'/entry['path'])
assert sha(E/'source.diff')==m['diff_sha256']
d=json.loads((E/'final-results.json').read_text());assert d['source_hashes_unchanged']
assert all(sha(C/path)==digest for path,digest in d['source_hashes_at_start'].items())
extra=json.loads((E/'supplemental-results.json').read_text())
rows=d['cases']+extra
for c in rows:
 assert c['passes_expectation'] is not False,c['name']
 if c['expected_stdout'] is not None:
  for profile in ['Debug','ReleaseFast']:
   p=c['profiles'][profile]
   assert p['build']['exit_code']==0 and p['run']['exit_code']==0 and p['run']['stdout']==c['expected_stdout']
 elif c['expected_diagnostic']:
  assert c['compile']['exit_code']!=0 and not c['artifact_exists']
 assert Path(c['compile']['command'][2]).read_text()==c['source']
selected=json.loads((E/'selected-tests.json').read_text())
assert '1 failed, 52 passed' in selected['stdout']
assert 'test_listed_recursive_groups_still_exist' in selected['stdout']
base=json.loads((E/'baseline-selected-failure.json').read_text());assert base['exit_code']==1 and '1 failed' in base['stdout']
assert not json.loads((E/'recursion.json').read_text())['new_groups']
oracle=json.loads((E/'reviewer/rounding-final-results.json').read_text());assert oracle['candidate_exact_constants_sha256']==sha(C/'a7/exact_constants.py')
result={'source_manifest_verified':True,'source_hashes_match_final_compiles':True,'cases':len(rows),'passing_expectations':sum(x['passes_expectation'] is True for x in rows),'inherited_probes':sum(x['passes_expectation'] is None for x in rows),'accepted_cases':sum(x['expected_stdout'] is not None for x in rows),'rejected_cases':sum(x['expected_diagnostic'] is not None for x in rows),'selected_tests':'52 passed, 1 unchanged baseline failure','new_recursive_groups':[],'candidate_tree_sha256':m['candidate_tree_sha256']}
(E/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
paths=[p for p in E.rglob('*') if p.is_file() and p.suffix in {'.json','.md','.py','.diff'} and not any(x in p.parts for x in ['final-sources','zig-cache','zig-global-cache','pytest-temp','baseline-pytest-temp']) and p.name!='evidence-manifest.json']
(E/'evidence-manifest.json').write_text(json.dumps({str(p.relative_to(E)):sha(p) for p in sorted(paths)},indent=2))
