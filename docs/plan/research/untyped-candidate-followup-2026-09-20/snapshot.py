from pathlib import Path
import hashlib, difflib, json, shutil
E=Path(__file__).resolve().parent
C=E.parent/'candidate';B=E.parent/'baseline';F=E/'final-sources'
def files(root):
 return {str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c,b=files(C),files(B)
entries=[];diff=[]
for name in sorted(c):
 target=F/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(c[name],target)
 entries.append({'path':name,'candidate_sha256':digest(c[name]),'snapshot_sha256':digest(target),'baseline_sha256':digest(b[name]) if name in b else None})
for name in sorted(set(c)|set(b)):
 before=b[name].read_text() if name in b else ''
 after=c[name].read_text() if name in c else ''
 if before!=after:diff.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='baseline/'+name,tofile='candidate/'+name))
(E/'source.diff').write_text(''.join(diff))
canonical=''.join(x['path']+' '+x['candidate_sha256']+'\n' for x in entries)
manifest={'algorithm':'sha256','candidate_tree_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'tree_hash_input':'Sorted relative path, space, SHA256, newline for each file; excludes __pycache__ and .pytest_cache.','files':entries,'diff_sha256':digest(E/'source.diff'),'changed_paths':[x['path'] for x in entries if x['candidate_sha256']!=x['baseline_sha256']]}
(E/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({k:v for k,v in manifest.items() if k!='files'},indent=2))
