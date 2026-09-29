from pathlib import Path
import subprocess,json,os
E=Path(__file__).resolve().parent
args=[str(E.parents[2]/'.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','test/test_no_recursion.py::test_listed_recursive_groups_still_exist','--basetemp='+str(E/'baseline-pytest-evidence')]
cwd=E.parent/'baseline'
p=subprocess.run(args,cwd=cwd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True)
(E/'baseline-selected-failure.json').write_text(json.dumps(dict(command=args,cwd=str(cwd),environment={'PYTHONDONTWRITEBYTECODE':'1'},exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
