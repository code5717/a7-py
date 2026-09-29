exec(open('tmp/untyped-constants-next/candidate-evidence/reviewer/probe.py').read().split('results=[]')[0])
cases={'comparison_distinct':'X :: 9007199254740993.0\nio.println("{}", X == 9007199254740992.0)', 'comparison_same':'X :: 9007199254740993.0\nio.println("{}", X == 9007199254740993.0)'}
script=open('tmp/untyped-constants-next/candidate-evidence/reviewer/probe.py').read().split('results=[]')[1].replace("out/'results.json'", "out/'comparison-results.json'")
exec('results=[]'+script)
