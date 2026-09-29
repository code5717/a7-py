from pathlib import Path
import subprocess,tempfile,json
repo=Path(__file__).resolve().parents[2]
results=[]
def run(args):
 p=subprocess.run(args,cwd=repo,text=True,capture_output=True)
 return {'command':args,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
with tempfile.TemporaryDirectory(prefix='a7-docs-') as td:
 d=Path(td)
 cases={
 'math': '''io :: import "std/io"
math :: import "std/math"
main :: fn() {
 x: f64 = 4.0
 io.println("{} {} {} {} {} {} {} {} {} {} {}", math.sqrt(x), math.abs(-4.0), math.floor(1.5), math.ceil(1.5), math.sin(0.0), math.cos(0.0), math.tan(0.0), math.log(1.0), math.exp(0.0), math.min(2, 3), math.max(2, 3))
}
''',
 'io': '''io :: import "std/io"
main :: fn() {
 io.print("Hello, ")
 io.println("{}!", "A7")
 io.eprintln("diagnostic {}", 42)
 io.print()
 io.println()
 io.eprintln()
}
''',
 'math_integer_rejected': '''math :: import "std/math"
main :: fn() { x := math.sqrt(4) }
''',
 'format_variable_rejected': '''io :: import "std/io"
main :: fn() { fmt := "hello"; io.println(fmt) }
''',
 'format_arity_rejected': '''io :: import "std/io"
main :: fn() { io.println("{}") }
''',
 'typed_math_rejected': '''math :: import "std/math"
main :: fn() { x := math.sqrt_f64(4.0) }
''',
 'escaped_braces': '''io :: import "std/io"
main :: fn() { io.println("{{}}") }
''',
 'signed_abs': '''io :: import "std/io"
math :: import "std/math"
absolute :: fn(x: i32) i32 { ret math.abs(x) }
main :: fn() { io.println("{}", absolute(-4)) }
'''
 }
 for name,code in cases.items():
  src=d/f'{name}.a7'; zig=d/f'{name}.zig'; src.write_text(code)
  compiled=run(['uv','run','a7',str(src),'--format','json','-o',str(zig)])
  payload=json.loads(compiled.pop('stdout'))
  compiled['payload']={k:v for k,v in payload.items() if k not in ['timing_ms','stages']}
  compiled['reached_stages']=list(payload['stages'])
  if 'codegen' in payload['stages']: compiled['generated_zig']=payload['stages']['codegen']['output_code']
  record={'name':name,'source':code,'compile':compiled}
  if compiled['exit']==0: record['native']=run(['zig','run',str(zig)])
  results.append(record)
 for mode in ['tokens','ast','semantic','pipeline','doc','compile']:
  args=['uv','run','a7','examples/001_hello.a7','--mode',mode,'--format','json']
  if mode=='doc': args+=['--doc-out',str(d/'hello.md')]
  if mode=='compile': args+=['-o',str(d/'hello.zig')]
  r=run(args); payload=json.loads(r['stdout']); results.append({'name':'mode_'+mode,'exit':r['exit'],'status':payload['status'],'schema':payload['schema_version'],'stages':list(payload['stages']),'artifacts':payload['artifacts']})
 (repo/'site/docs/content-probes.json').write_text(json.dumps(results,indent=2)+'\n')
 for r in results:
  print(r['name'],r.get('exit',r.get('compile',{}).get('exit')),r.get('native',{}).get('exit'),r.get('native',{}).get('stdout',''),r.get('native',{}).get('stderr','')[:150])

# Expectations name observable output and rejection stages, including repaired cases.
expected_output = {'math': '2 4 1 2 0 1 0 0 1 2 3\n', 'io': 'Hello, A7!\n\n',
                   'escaped_braces': '{}\n', 'signed_abs': '4\n'}
for result in results:
 name = result['name']
 if name in expected_output:
  assert result['compile']['exit'] == 0, result
  assert result['native']['exit'] == 0, result
  assert result['native']['stdout'] == expected_output[name], result
  expected_stderr = 'diagnostic 42\n\n' if name == 'io' else ''
  assert result['native']['stderr'] == expected_stderr, result
 elif name.endswith('_rejected'):
  assert result['compile']['exit'] == 6, result
 elif name.startswith('mode_'):
  assert result['exit'] == 0, result
