from pathlib import Path
import hashlib, json, difflib
E=Path(__file__).resolve().parent
candidate=E.parent/'candidate'; baseline=E.parent/'baseline'
manifest={}; diffs=[]
paths=sorted(set(p.relative_to(candidate) for p in (candidate/'a7').rglob('*.py')) | set(p.relative_to(baseline) for p in (baseline/'a7').rglob('*.py')))
for rel in paths:
    old=baseline/rel; new=candidate/rel
    a=old.read_bytes() if old.exists() else b''; b=new.read_bytes() if new.exists() else b''
    manifest[str(rel)]={'baseline_sha256':hashlib.sha256(a).hexdigest() if old.exists() else None,'candidate_sha256':hashlib.sha256(b).hexdigest() if new.exists() else None}
    if a!=b:
        diffs.extend(difflib.unified_diff(a.decode().splitlines(keepends=True),b.decode().splitlines(keepends=True),fromfile='baseline/'+str(rel),tofile='candidate/'+str(rel)))
(E/'source.diff').write_text(''.join(diffs))
(E/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
print('Changed files:',[k for k,v in manifest.items() if v['baseline_sha256']!=v['candidate_sha256']])
