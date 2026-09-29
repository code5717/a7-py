from pathlib import Path
import json, os
E=Path(__file__).resolve().parent
os.environ['PYTHONDONTWRITEBYTECODE']='1'
exec((E/'run_cases.py').read_text().split("results={'python'")[0])
# The first pass is retained as exploratory evidence, including invalid probe spellings.
old=json.loads((E/'exploratory-results.json').read_text())
prior={c['name']:c for c in old['cases']}
case('global_annotated',prog('io.println("{}", x)',before='x: i64 = BIG\n',after='BIG :: 9007199254740993.0\n'),'9007199254740993\n')
case('concrete_parameter',prog('show(BIG)',after='BIG :: 9007199254740993.0\nshow :: fn(x: i64) { io.println("{}", x) }\n'),'9007199254740993\n')
case('concrete_return',prog('x := get()\nio.println("{}",x)',after='BIG :: 9007199254740993.0\nget :: fn() i64 { ret BIG }\n'),'9007199254740993\n')
case('typed_float_arithmetic',prog('x: f64 = 0.1\ny := x + 0.2\nio.println("{}", y == 0.3)'),'false\n')
case('exact_comparison',prog('io.println("{} {}", BIG == 9007199254740992.0, (0.1+0.2)==0.3)',after='BIG :: 9007199254740993.0\n'),'false true\n')
case('signed_zero',prog('x: f64 = -0.0\nio.println("{}", x)'),'-0\n')
case('format_default_reject',prog('io.println("{}", BIG)',after='BIG :: 2147483648\n'),diagnostic='formatting default i32')
case('format_default_control',prog('io.println("{}", BIG)',after='BIG :: 2147483647\n'),'2147483647\n')
results={'python':run([PYTHON,'--version'],ROOT),'zig':run([ZIG,'version'],ROOT),'environment':{'PYTHONDONTWRITEBYTECODE':'1'},'cases':[]}
for spec in CASES:
    result=dict(spec)
    for flavor in ('candidate','baseline'):
        cwd=E.parent/flavor
        folder=E/'cases'/spec['name']/flavor
        folder.mkdir(parents=True,exist_ok=True)
        src=folder/'main.a7'; src.write_text(spec['source'])
        out=folder/'main.zig'; out.unlink(missing_ok=True)
        compile=run([PYTHON,str(cwd/'main.py'),str(src),'-o',str(out)],cwd)
        record={'compile':compile,'artifact_exists':out.exists()}
        previous=prior.get(spec['name'],{}).get(flavor,{})
        if out.exists() and compile['exit_code']==0:
            record['emitted_zig']=out.read_text()
            record['profiles']={}
            for profile in ('Debug','ReleaseFast'):
                binary=folder/('main-'+profile)
                previous_profile=previous.get('profiles',{}).get(profile,{})
                if previous.get('emitted_zig')==record['emitted_zig'] and previous_profile and (binary.exists() or previous_profile['build']['exit_code']!=0):
                    entry={'build':previous_profile['build'],'build_revalidated_by_identical_zig':True,'original_build_evidence':'exploratory-results.json'}
                else:
                    build=run([ZIG,'build-exe',str(out),'-O',profile,'-femit-bin='+str(binary),'--cache-dir',str(E/'zig-cache'),'--global-cache-dir',str(E/'zig-global-cache')],cwd)
                    entry={'build':build}
                if entry['build']['exit_code']==0:
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
    (E/'final-results.json').write_text(json.dumps(results,indent=2))
    print(spec['name'],result['passes_expectation'],flush=True)
