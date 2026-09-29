from pathlib import Path
import json
E=Path(__file__).resolve().parent
scope={'__file__':str(E/'run_cases.py')}
exec((E/'run_cases.py').read_text().split('results={')[0],scope)
scope['cases'].clear()
add=scope['add'];prog=scope['prog']
add('max_f64',prog('x: f64 = 1.7976931348623157e308\nio.println("{}",x>1e308)'),'true\n')
add('boundary_overflow_f64',prog('x: f64 = 1.7976931348623159e308'),diagnostic='overflows f64')
add('below_overflow_f32',prog('x: f32 = 340282356779733661637539395458142568447.0\ny: f32 = 340282346638528859811704183484516925440.0\nio.println("{}",x==y)'),'true\n')
results=[scope['check'](s) for s in scope['cases']]
(E/'supplemental-results.json').write_text(json.dumps(results,indent=2))
