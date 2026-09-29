from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent
r=json.loads((E/'final-results.json').read_text())
assert len(r['cases'])==49
assert all(c['passes_expectation'] is not False for c in r['cases'])
manifest=json.loads((E/'source-manifest.json').read_text())
review=json.loads((E/'reviewer/followup/source-hashes.json').read_text())
checks={}
for flavor in ('candidate','baseline'):
    checks[flavor+'_source_hashes_match']=all((hashlib.sha256((E.parent/flavor/name).read_bytes()).hexdigest() if (E.parent/flavor/name).exists() else None)==hashes[flavor+'_sha256'] for name,hashes in manifest.items())
checks['reviewed_changed_source_hashes_match']=all(hashlib.sha256((E.parent/'candidate'/name).read_bytes()).hexdigest()==h for name,h in review.items())
checks['all_stated_case_expectations_pass']=all(c['passes_expectation'] is not False for c in r['cases'])
checks['case_count']=len(r['cases'])
checks['valid_cases']=sum(c['expected_stdout'] is not None for c in r['cases'])
checks['rejection_cases']=sum(c['expected_diagnostic'] is not None for c in r['cases'])
checks['unqualified_probes']=sum(c['passes_expectation'] is None for c in r['cases'])
checks['failure_artifacts_absent']=all(not c['candidate']['artifact_exists'] for c in r['cases'] if c['expected_diagnostic'] is not None)
assert all(checks[k] for k in ('candidate_source_hashes_match','baseline_source_hashes_match','reviewed_changed_source_hashes_match','all_stated_case_expectations_pass','failure_artifacts_absent'))
(E/'verification.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
