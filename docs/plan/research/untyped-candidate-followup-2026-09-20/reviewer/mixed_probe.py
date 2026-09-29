from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[2]
repo=root.parents[1]
base=Path(__file__).parent
cases={
'mixed_f32_midpoint':'main :: fn() { x: f32 = 0.0; y := x + 1.0000000596046448; io.println("{}", y == 1.0) }',
'mixed_f32_overflow':'main :: fn() { x: f32 = 0.0; y := x + 1e40; io.println("{}", y) }',
'mixed_f32_compare':'main :: fn() { x: f32 = 1.0; io.println("{}", x == 1.000000059604644775390625) }'}
res=[]
def run(cmd):
 p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
 return {'command':list(map(str,cmd)),'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
for name,src in cases.items():
 d=base/name;d.mkdir(exist_ok=True)
 f=d/'input.a7';f.write_text('io :: import "std/io"\n'+src+'\n')
 c=run([repo/'.venv/bin/python',root/'candidate/main.py',f,'--format','json','--output',d/'out.zig'])
 row={'case':name,'source':f.read_text(),'compile':c,'profiles':{}}
 if c['exit']==0:
  row['zig']=(d/'out.zig').read_text()
  for profile in ['Debug','ReleaseFast']:
   b=run(['zig','build-exe',d/'out.zig','-O',profile,f'-femit-bin={d/profile}'])
   row['profiles'][profile]={'build':b}
   if b['exit']==0: row['profiles'][profile]['run']=run([d/profile])
 res.append(row)
 print(name,c['exit'],[(p,v.get('build',{}).get('exit'),v.get('run',{}).get('stdout')) for p,v in row['profiles'].items()])
(base/'mixed-results.json').write_text(json.dumps(res,indent=2)+'\n')
