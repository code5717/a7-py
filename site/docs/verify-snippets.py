from pathlib import Path
import re, subprocess, tempfile, json
repo=Path(__file__).resolve().parents[2]
records=[]
with tempfile.TemporaryDirectory(prefix='a7-site-snippets-') as td:
 for doc in (repo/'site/public/docs').rglob('*.md'):
  for i,source in enumerate(re.findall(r'```a7\n(.*?)\n```',doc.read_text(),re.S),1):
   if 'main :: fn' not in source: continue
   name=str(doc.relative_to(repo/'site/public/docs')).replace('/','-').replace('.md','')+f'-{i}'
   src=Path(td)/(name+'.a7'); zig=src.with_suffix('.zig'); src.write_text(source+'\n')
   c=subprocess.run(['uv','run','a7',str(src),'-o',str(zig)],cwd=repo,text=True,capture_output=True)
   r={'document':str(doc.relative_to(repo)),'block':i,'source':source,'compile_exit':c.returncode,'compile_output':c.stdout+c.stderr}
   if c.returncode==0:
    n=subprocess.run(['zig','run',str(zig)],cwd=repo,text=True,capture_output=True)
    r.update(native_exit=n.returncode,stdout=n.stdout,stderr=n.stderr)
   records.append(r)
(repo/'site/docs/evidence/standalone-snippets.json').write_text(json.dumps(records,indent=2)+'\n')
for r in records: print(r['document'],r['block'],r['compile_exit'],r.get('native_exit'),r.get('stdout'),r.get('stderr','')[:400])
assert all(r['compile_exit']==0 and r.get('native_exit')==0 for r in records)
