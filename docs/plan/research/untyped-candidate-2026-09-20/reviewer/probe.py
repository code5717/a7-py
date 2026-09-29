from pathlib import Path
import subprocess,json
root=Path.cwd(); out=root/'tmp/untyped-constants-next/candidate-evidence/reviewer'; candidate=root/'tmp/untyped-constants-next/candidate'
cases={
'mixed_overflow':'x: i8 = 1\ny := x + 200\nio.println("{}", y)',
'mixed_valid':'x: i8 = 1\ny := x + 2\nio.println("{}", y)',
'negative_zero':'x: f64 = -0.0\nio.println("{}", x)',
'positive_zero':'x: f64 = 0.0\nio.println("{}", x)',
'format_big':'BIG :: 2147483648\nio.println("{}", BIG)',
'format_valid':'BIG :: 2147483647\nio.println("{}", BIG)',
'fraction_comparison':'X :: 0.1 + 0.2\nio.println("{}", X == 0.3)',
'local_shadow':'X :: 2.0\n{\ny: i32 = X\nX :: 3.0\nio.println("{}", y)\n}\nz: i32 = X\nio.println("{}", z)',
}
results=[]
for name,body in cases.items():
 source='io :: import "std/io"\nmain :: fn() {\n'+body+'\n}\n'; path=out/(name+'.a7'); path.write_text(source)
 command=[str(root/'.venv/bin/python'),str(candidate/'main.py'),'build',str(path),'--profile','debug','-o',str(out/(name+'-bin'))]
 p=subprocess.run(command,capture_output=True,text=True); item=dict(case=name,source=source,command=command,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
 if p.returncode==0:
  r=subprocess.run([str(out/(name+'-bin'))],capture_output=True,text=True);item['run']=dict(exit=r.returncode,stdout=r.stdout,stderr=r.stderr)
 results.append(item)
(out/'results.json').write_text(json.dumps(results,indent=2))
for r in results:print(r['case'],r['exit'],r.get('run',r['stdout'][-650:]))
