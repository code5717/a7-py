from pathlib import Path
import json,sys
root=Path.cwd(); base=root/'tmp/untyped-constants-next';sys.path.insert(0,str(base/'candidate/test'))
import norec_scan
rows={}
for label in ('baseline','candidate'):
 r=norec_scan.scan(base/label/'a7');rows[label]=[list(x) for x in r.groups]
new=[x for x in rows['candidate'] if x not in rows['baseline']];rows['new_groups']=new
(base/'candidate-evidence/reviewer/recursion.json').write_text(json.dumps(rows,indent=2));print('new recursive groups:',new)
