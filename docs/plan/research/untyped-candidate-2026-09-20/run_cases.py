from pathlib import Path
import json, subprocess, sys, shutil, os
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parents[3]
E = Path(__file__).resolve().parent
PYTHON = str(ROOT / '.venv/bin/python')
ZIG = shutil.which('zig')
CASES = []
def case(name, source, output=None, diagnostic=None, note=None):
    CASES.append(dict(name=name, source=source, expected_stdout=output, expected_diagnostic=diagnostic, note=note))
def prog(body, before='', after=''):
    return 'io :: import "std/io"\n' + before + '\nmain :: fn() {\n' + body + '\n}\n' + after
for order in ('forward','backward'):
    for label, value, typ, output, diagnostic in [
        ('whole','2.0','i32','2\n',None),
        ('fraction','2.5','i32',None,'fractional'),
        ('range','256.0','u8',None,'out of range'),
        ('range_control','255.0','u8','255\n',None),
        ('exact_large','9007199254740993.0','i64','9007199254740993\n',None),
        ('negative','-1.0','usize',None,'out of range'),
        ('negative_control','0.0','usize','0\n',None),
    ]:
        binding = f'VALUE :: {value}\n'
        case(order+'_'+label, prog(f'x: {typ} = VALUE\nio.println("{{}}", x)', before=binding if order=='backward' else '', after=binding if order=='forward' else ''), output, diagnostic)
    binding='MESSAGE :: "hello"\n'
    case(order+'_string', prog('io.println("{}", MESSAGE)', before=binding if order=='backward' else '', after=binding if order=='forward' else ''), 'hello\n')
case('alias_chain',prog('x: i64 = FIRST\nio.println("{}", x)', after='FIRST :: SECOND\nSECOND :: THIRD\nTHIRD :: 9007199254740993.0\n'),'9007199254740993\n')
case('multi_use',prog('a: u8 = VALUE\nb: i64 = VALUE\nio.println("{} {}", a,b)',after='VALUE :: 200.0\n'),'200 200\n')
case('multi_use_reverse',prog('b: i64 = VALUE\na: u8 = VALUE\nio.println("{} {}", a,b)',after='VALUE :: 200.0\n'),'200 200\n')
case('multi_use_bad',prog('a: u8 = VALUE\nb: i8 = VALUE',after='VALUE :: 200.0\n'),diagnostic='out of range')
case('local_exact',prog('VALUE :: 9007199254740993.0\nALIAS :: VALUE\nx: i64 = ALIAS\nio.println("{}", x)'),'9007199254740993\n')
case('local_fraction',prog('VALUE :: 2.5\nx: i32 = VALUE'),diagnostic='fractional')
case('local_shadow',prog('x: i32 = VALUE\n{ VALUE :: 3.0\ny: i32 = VALUE\nio.println("{}", y) }\nz: i64 = VALUE\nio.println("{} {}", x,z)',before='VALUE :: 2.0\n'),'3\n2 2\n')
case('exact_arithmetic',prog('x: i64 = BIG\ny: u16 = SUM\nz: i32 = DECIMAL\nio.println("{} {} {}", x,y,z)',after='BIG :: 9007199254740993.0 + 2.0 - 1.0\nSUM :: 255 + 1\nDECIMAL :: (0.1 + 0.2) * 10\n'),'9007199254740994 256 3\n')
case('arithmetic_range',prog('x: u8 = SUM',after='SUM :: 255 + 1\n'),diagnostic='out of range')
case('typed_runtime_reject',prog('r := RATE\nx: i32 = r',after='RATE :: 2.0\n'),diagnostic='Type mismatch')
case('typed_runtime_control',prog('r := RATE\nx: f64 = r\nio.println("{}", x)',after='RATE :: 2.0\n'),'2\n')
case('typed_call_reject',prog('x: i32 = VALUE',after='VALUE :: get()\nget :: fn() f64 { ret 2.0 }\n'),diagnostic='Type mismatch')
case('typed_call_control',prog('x: f64 = VALUE\nio.println("{}", x)',after='VALUE :: get()\nget :: fn() f64 { ret 2.0 }\n'),'2\n')
case('default_range_reject',prog('x := BIG',after='BIG :: 2147483648\n'),diagnostic='default i32')
case('default_range_control',prog('x := BIG\nio.println("{}",x)',after='BIG :: 2147483647\n'),'2147483647\n')
case('mixed_range_reject',prog('x: i8 = 1\ny := x + VALUE',after='VALUE :: 200\n'),diagnostic='out of range')
case('mixed_range_control',prog('x: i8 = 1\ny := x + VALUE\nio.println("{}", y)',after='VALUE :: 2.0\n'),'3\n')
case('typed_wrapping',prog('x: u8 = 255\ny := x + 1\nio.println("{}",y)'),'0\n')
case('global_cycle',prog('x: i32 = A',after='A :: B\nB :: A\n'),diagnostic='Unresolved global value dependency')
case('missing_name',prog('x: i32 = MISSING'),diagnostic='MISSING')
case('local_forward_probe',prog('x: i32 = LATER\nLATER :: 2.0'),note='Preserve baseline local visibility; unresolved local forward use is outside this slice.')
case('local_runtime_order',prog('first :: mark(1)\nsecond :: mark(2)\nx: i32 = VALUE\nio.println("{} {} {}",first,second,x)',after='VALUE :: 2.0\nmark :: fn(x: i32) i32 { io.println("{}",x) ret x }\n'),'1\n2\n1 2 2\n')
case('global_runtime_order_probe',prog('io.println("{} {}", FIRST, SECOND)',after='FIRST :: mark(1)\nSECOND :: mark(2)\nmark :: fn(x: i32) i32 { io.println("{}",x) ret x }\n'),note='Probe inherited global runtime initializer support; no success claim if Zig rejects.')
case('explicit_cast_fraction',prog('x := cast(i32, 2.5)'),diagnostic='cast')
case('explicit_cast_range',prog('x := cast(u8, 256)'),diagnostic='cast')

def run(args, cwd):
    p = subprocess.run(args,cwd=cwd,text=True,capture_output=True)
    return dict(command=args,cwd=str(cwd),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
results={'python':run([PYTHON,'--version'],ROOT),'zig':run([ZIG,'version'],ROOT),'cases':[]}
for spec in CASES:
    result=dict(spec)
    for flavor in ('candidate','baseline'):
        cwd=E.parent/flavor
        folder=E/'cases'/spec['name']/flavor
        folder.mkdir(parents=True,exist_ok=True)
        src=folder/'main.a7'; src.write_text(spec['source'])
        out=folder/'main.zig'
        out.unlink(missing_ok=True)
        compile=run([PYTHON,str(cwd/'main.py'),str(src),'-o',str(out)],cwd)
        record={'compile':compile,'artifact_exists':out.exists()}
        if out.exists() and compile['exit_code']==0:
            record['emitted_zig']=out.read_text()
            record['profiles']={}
            for profile in ('Debug','ReleaseFast'):
                binary=folder/('main-'+profile)
                build=run([ZIG,'build-exe',str(out),'-O',profile,'-femit-bin='+str(binary),'--cache-dir',str(E/'zig-cache'),'--global-cache-dir',str(E/'zig-global-cache')],cwd)
                entry={'build':build}
                if build['exit_code']==0:
                    entry['run']=run([str(binary)],cwd)
                record['profiles'][profile]=entry
        result[flavor]=record
    candidate=result['candidate']
    if spec['expected_stdout'] is not None:
        result['passes_expectation']=candidate['compile']['exit_code']==0 and all(candidate.get('profiles',{}).get(p,{}).get('run',{}).get('stdout')==spec['expected_stdout'] and candidate['profiles'][p]['run']['exit_code']==0 for p in ('Debug','ReleaseFast'))
    elif spec['expected_diagnostic'] is not None:
        result['passes_expectation']=candidate['compile']['exit_code']!=0 and not candidate['artifact_exists'] and spec['expected_diagnostic'].lower() in (candidate['compile']['stdout']+candidate['compile']['stderr']).lower()
    else: result['passes_expectation']=None
    results['cases'].append(result)
    (E/'results.json').write_text(json.dumps(results,indent=2))
    print(spec['name'],result['passes_expectation'],flush=True)
