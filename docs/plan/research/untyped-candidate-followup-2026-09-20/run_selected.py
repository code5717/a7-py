import json, subprocess, os
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=E.parents[2]
cwd=E.parent/'candidate'
args=[str(ROOT/'.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','test/test_no_recursion.py','test/test_constant_folding_exact.py::test_large_integer_quotient_and_remainder_match_run_time','test/test_constant_folding_exact.py::test_boundary_values_match_the_run_time_result','test/test_float_nonfinite_folding.py::test_float_remainder_constants_match_native_values','test/test_compound_assignment_types.py','test/test_constant_folding_exact.py::test_exact_quotient_formatting_requires_fitting_default','--basetemp='+str(E/'pytest-temp')]
p=subprocess.run(args,cwd=cwd,capture_output=True,text=True)
(E/'selected-tests.json').write_text(json.dumps(dict(command=args,cwd=str(cwd),exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2))
print(p.stdout,p.stderr,flush=True)
