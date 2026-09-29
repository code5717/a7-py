from pathlib import Path
import subprocess,json,sys,concurrent.futures
root=Path.cwd();phase=sys.argv[1]
base=root/'tmp/untyped-constants-next';compiler=base/phase/'main.py';out=base/(phase+'-contexts');out.mkdir(exist_ok=True)
header='io :: import "std/io"\n'
cases={
'exact_decimal_comparison':header+'main :: fn() { io.println("{}", 0.1 + 0.2 == 0.3) }',
'negative_integer_division':header+'main :: fn() { x: i32 = -5 / 2; io.println("{}", x) }',
'negative_float_remainder':header+'main :: fn() { x: f64 = -5.5 % 2.0; io.println("{}", x) }',
'integer_division_float_destination':header+'R :: 5 / 2\nmain :: fn() { x: f64 = R; io.println("{}", x) }',
'fractional_division_integer_destination':header+'R :: 5.0 / 2\nmain :: fn() { x: i32 = R; io.println("{}", x) }',
'negative_shift_count':header+'main :: fn() { x := 1 << -1; io.println("{}", x) }',
'floating_bitwise':header+'main :: fn() { x := 2.0 & 3; io.println("{}", x) }',
'typed_wrap':header+'main :: fn() { x: u8 = 255; x += 1; io.println("{}", x) }',
'function_argument':header+'RATE :: 2.0\nshow :: fn(x: i32) { io.println("{}", x) }\nmain :: fn() { show(RATE) }',
'function_return':header+'RATE :: 2.0\nget :: fn() i32 { ret RATE }\nmain :: fn() { io.println("{}", get()) }',
'struct_field':header+'RATE :: 2.0\nBox :: struct { n: i32 }\nmain :: fn() { b := Box{n: RATE}; io.println("{}", b.n) }',
'array_element':header+'RATE :: 2.0\nmain :: fn() { a: [1]i32 = [RATE]; io.println("{}", a[0]) }',
'array_index':header+'INDEX :: 0.0\nmain :: fn() { a: [1]i32 = [7]; io.println("{}", a[INDEX]) }',
'array_length':header+'SIZE :: 2.0\nmain :: fn() { a: [SIZE]i32 = [3, 4]; io.println("{}", a[0]) }',
'match_pattern':header+'RATE :: 2.0\nmain :: fn() { n: i32 = 2; match n { case RATE: { io.println("yes") } else: { io.println("no") } } }',
'generic_default':header+'identity($T) :: fn(value: $T) $T { ret value }\nRATE :: 2.0\nmain :: fn() { x := identity(RATE); io.println("{}", x) }',
'inferred_default':header+'RATE :: 2.0\nmain :: fn() { x := RATE; n: i32 = x; io.println("{}", n) }',
'constant_multi_use':header+'N :: 200\nmain :: fn() { a: u8 = N; b: i64 = N; io.println("{} {}", a, b) }',
'constant_range_rejection':header+'N :: 200\nmain :: fn() { a: i8 = N; io.println("{}", a) }',
}
cases.update({
'exact_intermediate_overflow':header+'main :: fn() { x: f64 = 1e308 * 10.0 / 100.0; io.println("{}", x) }',
'exponent_resource_compat':header+'main :: fn() { x: f64 = 1e9999; io.println("{}", x) }',
'wide_format_default':header+'main :: fn() { io.println("{}", 9007199254740993 / 1) }',
'wide_format_explicit':header+'main :: fn() { value: i64 = 9007199254740993 / 1; io.println("{}", value) }',
'float32_overflow':header+'main :: fn() { x: f32 = 1e100; io.println("{}", x) }',
'float64_overflow':header+'main :: fn() { x: f64 = 1e400; io.println("{}", x) }',
'float32_midpoint':header+'main :: fn() { x: f32 = 1.000000059604644775390625; io.println("{}", x > 1.0) }',
'float32_above_midpoint':header+'main :: fn() { x: f32 = 1.0000000596046447753906250000000000000000000000000000000000000000000000001; io.println("{}", x > 1.0) }',
'float32_below_midpoint':header+'main :: fn() { x: f32 = 1.0000000596046447753906249999999999999999999999999999999999999999999999999; io.println("{}", x > 1.0) }',
'exact_division_comparison':header+'main :: fn() { same := (9007199254740993.0 / 1.0) == 9007199254740992.0; io.println("{}", same) }',
})
if len(sys.argv)>2:
 names=set(sys.argv[2].split(','))
 cases={k:v for k,v in cases.items() if k in names}
def command(args):
 p=subprocess.run(args,text=True,capture_output=True)
 return dict(command=args,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
def run(item):
 name,source=item;folder=out/name;folder.mkdir(exist_ok=True)
 path=folder/'input.a7';path.write_text(source);zig=folder/'out.zig'
 check=command([str(root/'.venv/bin/python'),str(compiler),str(path),'--format','json','--output',str(zig)])
 result=dict(case=name,source=source,compile=check,profiles={})
 if check['exit']==0:
  result['zig']=zig.read_text()
  for profile in ['Debug','ReleaseFast']:
   binary=folder/profile
   build=command(['zig','build-exe',str(zig),'-O',profile,'-femit-bin='+str(binary)])
   result['profiles'][profile]=dict(build=build)
   if build['exit']==0:result['profiles'][profile]['run']=command([str(binary)])
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(run,cases.items()))
(out/'results.json').write_text(json.dumps(dict(phase=phase,zig_version=command(['zig','version']),cases=results),indent=2)+'\n')
for r in results:
 print(r['case'],r['compile']['exit'],{k:(v['build']['exit'],v.get('run',{}).get('stdout')) for k,v in r['profiles'].items()})
