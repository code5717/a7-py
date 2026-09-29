from pathlib import Path
import concurrent.futures,subprocess,json,hashlib,sys
root=Path.cwd()
phase=sys.argv[1]
compiler=root/'tmp/untyped-constants-next'/phase/'main.py'
outdir=root/'tmp/untyped-constants-next'/f'{phase}-corpus'
outdir.mkdir(exist_ok=True)
inventory=json.loads((root/'tmp/untyped-constants-next/frozen-corpus-inventory.json').read_text())
files=list(inventory)
for name, digest in inventory.items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, ('Source changed since baseline',name)
def run(name):
 source=root/name
 out=outdir/(hashlib.sha256(name.encode()).hexdigest()[:16]+'.zig')
 command=[str(root/'.venv/bin/python'),str(compiler),str(source),'--format','json','--output',str(out)]
 p=subprocess.run(command,text=True,capture_output=True)
 try:
  data=json.loads(p.stdout)
 except ValueError:
  data={}
 stages=data.get('stages',{})
 errors={k:v.get('errors') for k,v in stages.items() if isinstance(v,dict) and v.get('errors')}
 code=out.read_text() if out.exists() else None
 return dict(source=name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),command=command,exit=p.returncode,status=data.get('status'),errors=errors,stderr=p.stderr,unparsed_stdout=p.stdout if not data else None,zig_sha256=hashlib.sha256(code.encode()).hexdigest() if code is not None else None,zig=code)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 records=list(pool.map(run,sorted(files)))
compiler_hashes={str(p.relative_to(compiler.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((compiler.parent/'a7').rglob('*.py'))}
result=dict(phase=phase,scope='Repository .a7 files listed by rg; excludes tmp and node_modules; compile only',compiler_hashes=compiler_hashes,records=records)
target=outdir/'results.json';target.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(phase=phase,total=len(records),accepted=sum(r['exit']==0 for r in records),output=str(target))))
