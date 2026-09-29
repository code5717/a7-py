from pathlib import Path
import json, subprocess, hashlib
from concurrent.futures import ThreadPoolExecutor
E=Path(__file__).resolve().parent
scope={ '__file__':str(E/'run_cases.py') }
exec((E/'run_cases.py').read_text().split('results={')[0],scope)
old={c['name']:c for c in json.loads((E/'pre-diagnostic-final-results.json').read_text())['cases']}
run=scope['run'];C=scope['C'];PY=scope['PY'];ZIG=scope['ZIG']
def check(spec):
 d=E/'final-cases'/spec['name'];d.mkdir(parents=True,exist_ok=True)
 src=d/'main.a7';src.write_text(spec['source']);out=d/'main.zig';out.unlink(missing_ok=True)
 c=run([PY,str(C/'main.py'),str(src),'-o',str(out)],C)
 r=dict(spec,compile=c,artifact_exists=out.exists(),profiles={})
 previous=old.get(spec['name'],{})
 if c['exit_code']==0 and out.exists():
  r['emitted_zig']=out.read_text()
  for profile in ('Debug','ReleaseFast'):
   existing=previous.get('profiles',{}).get(profile,{})
   if r['emitted_zig']==previous.get('emitted_zig') and existing.get('build',{}).get('exit_code')==0:
    b=existing['build'];binary=Path(existing['run']['command'][0])
    entry={'build':b,'build_revalidated_by_identical_zig':True,'original_build_evidence':'pre-diagnostic-final-results.json'}
   else:
    binary=d/profile
    b=run([ZIG,'build-exe',str(out),'-O',profile,'-femit-bin='+str(binary),'--cache-dir',str(E/'zig-cache'),'--global-cache-dir',str(E/'zig-global-cache')],C)
    entry={'build':b}
   if b['exit_code']==0:entry['run']=run([str(binary)],C)
   r['profiles'][profile]=entry
 if spec['expected_stdout'] is not None:
  r['passes_expectation']=c['exit_code']==0 and all(r['profiles'].get(p,{}).get('run',{}).get('stdout')==spec['expected_stdout'] and r['profiles'][p]['run']['exit_code']==0 for p in ('Debug','ReleaseFast'))
 elif spec['expected_diagnostic']:
  r['passes_expectation']=c['exit_code']!=0 and not out.exists() and spec['expected_diagnostic'].lower() in (c['stdout']+c['stderr']).lower()
 else:r['passes_expectation']=None
 print(spec['name'],r['passes_expectation'],flush=True)
 return r
sources={str(p.relative_to(C)):hashlib.sha256(p.read_bytes()).hexdigest() for p in C.rglob('*.py') if '__pycache__' not in p.parts}
results={'python':run([PY,'--version'],C),'zig':run([ZIG,'version'],C),'source_hashes_at_start':sources,'cases':[]}
with ThreadPoolExecutor(max_workers=3) as pool:
 for r in pool.map(check,scope['cases']):
  results['cases'].append(r)
  (E/'final-results.json').write_text(json.dumps(results,indent=2))
results['source_hashes_unchanged']=all(hashlib.sha256((C/p).read_bytes()).hexdigest()==v for p,v in sources.items())
(E/'final-results.json').write_text(json.dumps(results,indent=2))
