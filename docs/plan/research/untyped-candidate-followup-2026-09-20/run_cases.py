from pathlib import Path
import json, subprocess, os, shutil
from concurrent.futures import ThreadPoolExecutor
E=Path(__file__).resolve().parent
ROOT=E.parents[2]
C=E.parent/'candidate'
PY=str(ROOT/'.venv/bin/python'); ZIG=shutil.which('zig')
os.environ['PYTHONDONTWRITEBYTECODE']='1'
cases=[]
def add(name,source,output=None,diagnostic=None):
 cases.append(dict(name=name,source=source,expected_stdout=output,expected_diagnostic=diagnostic))
def prog(body,before=''):
 return 'io :: import "std/io"\n'+before+'\nmain :: fn() {\n'+body+'\n}\n'
old=json.loads((E.parent/'candidate-evidence/final-results.json').read_text())
for c in old['cases']: cases.append({k:c.get(k) for k in ['name','source','expected_stdout','expected_diagnostic','note']})
review=json.loads((E.parent/'review-candidate-contexts/results.json').read_text())
outputs={'exact_decimal_comparison':'true\n','negative_integer_division':'-2\n','negative_float_remainder':'-1.5\n','integer_division_float_destination':'2\n','float32_midpoint':'false\n','float32_above_midpoint':'true\n','float32_below_midpoint':'false\n','exact_division_comparison':'false\n'}
for c in review['cases']:
 name=c['case']
 if name in outputs: add('controller_'+name,c['source'],outputs[name])
 if name in ['float32_overflow','float64_overflow']: add('controller_'+name,c['source'],diagnostic='overflows')
 if name=='fractional_division_integer_destination': add('controller_'+name,c['source'],diagnostic='fractional')
for width in (32,64):
 for sign in ('','-'):
  add(f'overflow_{width}_{sign or "positive"}',prog(f'x: f{width} = {sign}1e400\nio.println("{{}}",x)'),diagnostic=f'overflows f{width}')
add('short_witness',prog('x: f32 = 1.0000000596046448\nio.println("{}", x > 1.0)'),'true\n')
add('odd_tie_f32',prog('x: f32 = 1.000000178813934326171875\nio.println("{}", x == 1.0000002384185791015625)'),'true\n')
add('tie_f64',prog('x: f64 = 1.00000000000000011102230246251565404236316680908203125\nio.println("{}", x == 1.0)'),'true\n')
add('above_tie_f64',prog('x: f64 = 1.000000000000000111022302462515654042363166809082031250000000000000001\nio.println("{}", x > 1.0)'),'true\n')
add('carry_f32',prog('x: f32 = 1.999999940395355224609375\nio.println("{}", x == 2.0)'),'true\n')
add('max_f32',prog('x: f32 = 340282346638528859811704183484516925440.0\nio.println("{}", x > 3e38)'),'true\n')
add('threshold_f32',prog('x: f32 = 340282356779733661637539395458142568448.0'),diagnostic='overflows f32')
add('underflow_zero',prog('x: f32 = -1e-100\ny: f64 = -1e-1000\nio.println("{} {}", x,y)'),'-0 -0\n')
add('min_subnormal',prog('x: f32 = 1.0 / 713623846352979940529142984724747568191373312.0\nio.println("{}", x > 0.0)'),'true\n')
add('default_overflow',prog('x := 1e400\nio.println("{}",x)'),diagnostic='overflows f64')
add('format_overflow',prog('io.println("{}",1e400)'),diagnostic='overflows f64')
add('exact_huge_comparison',prog('io.println("{}", 1e400 == 1e400)'),'true\n')
add('rational_third',prog('x: f64 = 1.0 / 3.0\nio.println("{} {}",x == 0.3333333333333333, (1.0/3.0)*3.0 == 1.0)'),'true true\n')
add('division_categories',prog('a: i32 = 5/2\nb: f64 = 5.0/2\nc: i32 = -5/2\nd: i32 = 5/-2\nio.println("{} {} {} {}",a,b,c,d)'),'2 2.5 -2 -2\n')
add('remainders',prog('a: i32 = -5%2\nb: i32 = 5%-2\nc: f64 = -5.5%2.0\nd: f64 = 5.5%-2.0\nio.println("{} {} {} {}",a,b,c,d)'),'-1 1 -1.5 1.5\n')
add('remainder_exact',prog('io.println("{}", (9007199254740993.0 % 2.0) == 1.0)'),'true\n')
add('signed_zero_ops',prog('a: f64 = -0.0/2.0\nb: f64 = 0.0/-2.0\nc: f64 = -4.0%2.0\nio.println("{} {} {}", a,b,c)'),'-0 -0 -0\n')
for expr in ('1.0/0.0','1%0'):
 add('zero_'+str(len(cases)),prog('x := '+expr),diagnostic='zero')
add('typed_math_globals',prog('io.println("{} {} {}",INF,NAN==NAN,NAN!=NAN)','math :: import "std/math"\nINF :: math.exp(1000.0)\nNAN :: math.sqrt(-1.0)\n'),'inf false true\n')
add('typed_math_runtime',prog('x := math.exp(1000.0)\ny := math.sqrt(-1.0)\na: f64 = 1e308\nb: f64 = 10.0\nc := a*b\nio.println("{} {} {} {}",x,y==y,y!=y,c)','math :: import "std/math"\n'),'inf false true inf\n')
add('half_min_subnormal',prog('x: f32 = 1.0 / 1427247692705959881058285969449495136382746624.0\ny: f32 = -1.0 / 1427247692705959881058285969449495136382746624.0\nio.println("{} {}",x,y)'),'0 -0\n')
add('normal_boundary',prog('x: f32 = 16777215.0 / 1427247692705959881058285969449495136382746624.0\ny: f32 = 1.1754943508222875e-38\nio.println("{}",x==y)'),'true\n')
add('f64_underflow_boundary',prog('x: f64 = 5e-324\ny: f64 = 2e-324\nio.println("{} {}",x>0.0,y==0.0)'),'true true\n')
add('mixed_f32_rounding',prog('x: f32 = 0.0\ny := x + 1.0000000596046448\nio.println("{}",y>1.0)'),'true\n')
add('mixed_f32_overflow',prog('x: f32 = 0.0\ny := x+1e40\nio.println("{}",y)'),diagnostic='overflows f32')
add('f32_return_argument',prog('x := get()\nshow(1.0000000596046448)\nio.println("{}",x>1.0)','get :: fn() f32 { ret 1.0000000596046448 }\nshow :: fn(x: f32) { io.println("{}",x>1.0) }\n'),'true\ntrue\n')
add('wide_quotient',prog('x: i64 = 9007199254740993 / 1\ny: u64 = 18446744073709551615 / 1\nio.println("{} {}",x,y)'),'9007199254740993 18446744073709551615\n')
add('wide_quotient_default_reject',prog('io.println("{}",9007199254740993 / 1)'),diagnostic='formatting default i32')
add('same_binding_float_widths',prog('a: f32 = VALUE\nb: f64 = VALUE\nio.println("{} {}",a>1.0,b==1.0000000596046448)','VALUE :: 1.0000000596046448\n'),'true true\n')
def run(args,cwd):
 p=subprocess.run(args,cwd=cwd,capture_output=True,text=True)
 return dict(command=args,cwd=str(cwd),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
def check(spec):
 d=E/'cases'/spec['name'];d.mkdir(parents=True,exist_ok=True)
 src=d/'main.a7';src.write_text(spec['source']);out=d/'main.zig';out.unlink(missing_ok=True)
 c=run([PY,str(C/'main.py'),str(src),'-o',str(out)],C)
 r=dict(spec,compile=c,artifact_exists=out.exists(),profiles={})
 if c['exit_code']==0 and out.exists():
  r['emitted_zig']=out.read_text()
  for profile in ('Debug','ReleaseFast'):
   binary=d/profile
   b=run([ZIG,'build-exe',str(out),'-O',profile,'-femit-bin='+str(binary),'--cache-dir',str(E/'zig-cache'),'--global-cache-dir',str(E/'zig-global-cache')],C)
   r['profiles'][profile]={'build':b}
   if b['exit_code']==0:r['profiles'][profile]['run']=run([str(binary)],C)
 if spec['expected_stdout'] is not None:
  r['passes_expectation']=c['exit_code']==0 and all(r['profiles'].get(p,{}).get('run',{}).get('stdout')==spec['expected_stdout'] and r['profiles'][p]['run']['exit_code']==0 for p in ('Debug','ReleaseFast'))
 elif spec['expected_diagnostic']:
  r['passes_expectation']=c['exit_code']!=0 and not out.exists() and spec['expected_diagnostic'].lower() in (c['stdout']+c['stderr']).lower()
 else:r['passes_expectation']=None
 print(spec['name'],r['passes_expectation'],flush=True)
 return r
results={'python':run([PY,'--version'],C),'zig':run([ZIG,'version'],C),'cases':[]}
with ThreadPoolExecutor(max_workers=3) as pool:
 for r in pool.map(check,cases):
  results['cases'].append(r)
  (E/'results.json').write_text(json.dumps(results,indent=2))
