from pathlib import Path
import subprocess,json
root=Path.cwd();out=root/'tmp/untyped-constants-next/candidate-evidence/reviewer';candidate=root/'tmp/untyped-constants-next/candidate';dest=out/'followup';dest.mkdir(exist_ok=True)
prior=json.loads((out/'results.json').read_text())+json.loads((out/'comparison-results.json').read_text())
results=[]
for old in prior:
 name=old['case'];source=old['source'];path=dest/(name+'.a7');path.write_text(source)
 for profile in ('debug','release'):
  command=[str(root/'.venv/bin/python'),str(candidate/'main.py'),'build',str(path),'--profile',profile,'-o',str(dest/(name+'-'+profile))]
  p=subprocess.run(command,capture_output=True,text=True);item=dict(case=name,profile=profile,source=source,command=command,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
  if p.returncode==0:
   r=subprocess.run([str(dest/(name+'-'+profile))],capture_output=True,text=True);item['run']=dict(exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
  results.append(item)
  print(name,profile,p.returncode,item.get('run',{}),flush=True)
(dest/'results.json').write_text(json.dumps(results,indent=2))
