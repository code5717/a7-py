from pathlib import Path
import json
E=Path(__file__).resolve().parent
exec((E/'run_cases.py').read_text().split("results={'python'")[0])
rows=[]
for spec in CASES:
    folder=E/'preflight'/spec['name']; folder.mkdir(parents=True,exist_ok=True)
    src=folder/'main.a7'; src.write_text(spec['source']); out=folder/'main.zig'; out.unlink(missing_ok=True)
    record=run([PYTHON,str(E.parent/'candidate/main.py'),str(src),'-o',str(out)],E.parent/'candidate')
    text=record['stdout']+record['stderr']
    ok=(record['exit_code']==0) if spec['expected_stdout'] is not None else (record['exit_code']!=0 and spec['expected_diagnostic'].lower() in text.lower()) if spec['expected_diagnostic'] is not None else None
    rows.append(dict(name=spec['name'],command=record,compile_expectation=ok))
    if ok is False: print(spec['name'],text)
(E/'preflight.json').write_text(json.dumps(rows,indent=2))
