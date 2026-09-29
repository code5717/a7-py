import json,subprocess,os
from pathlib import Path
E=Path(__file__).resolve().parent
os.environ['PYTHONDONTWRITEBYTECODE']='1'
args=[str(E.parents[2]/'.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','test/test_no_recursion.py::test_listed_recursive_groups_still_exist','--basetemp='+str(E/'baseline-pytest-temp')]
cwd=E.parent/'baseline'
p=subprocess.run(args,cwd=cwd,capture_output=True,text=True)
(E/'baseline-selected-failure.json').write_text(json.dumps(dict(command=args,cwd=str(cwd),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
print(p.stdout)
