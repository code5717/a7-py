from pathlib import Path
import json, os
E=Path(__file__).resolve().parent
os.environ['PYTHONDONTWRITEBYTECODE']='1'
exec((E/'run_cases.py').read_text().split("results={'python'")[0])
source=prog('x: i32 = LATER\nLATER :: 2.0\nio.println("{}", x)')
result={'source':source,'note':'Observable local forward-reference control. This is a compatibility probe, not a proposed new local rule.'}
for flavor in ('candidate','baseline'):
 cwd=E.parent/flavor
 folder=E/'local-visibility'/flavor; folder.mkdir(parents=True,exist_ok=True)
 src=folder/'main.a7'; src.write_text(source); out=folder/'main.zig'
 record={'compile':run([PYTHON,str(cwd/'main.py'),str(src),'-o',str(out)],cwd)}
 if record['compile']['exit_code']==0:
  record['emitted_zig']=out.read_text(); record['profiles']={}
  for profile in ('Debug','ReleaseFast'):
   binary=folder/('main-'+profile)
   build=run([ZIG,'build-exe',str(out),'-O',profile,'-femit-bin='+str(binary),'--cache-dir',str(E/'zig-cache'),'--global-cache-dir',str(E/'zig-global-cache')],cwd)
   entry={'build':build}
   if build['exit_code']==0: entry['run']=run([str(binary)],cwd)
   record['profiles'][profile]=entry
 result[flavor]=record
(E/'local-visibility.json').write_text(json.dumps(result,indent=2))
print({flavor:{p:e['build']['exit_code'] for p,e in result[flavor].get('profiles',{}).items()} for flavor in ('candidate','baseline')})
