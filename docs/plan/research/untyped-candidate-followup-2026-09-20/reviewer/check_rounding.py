from pathlib import Path
import sys, random, json, hashlib
from fractions import Fraction
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'candidate'))
from a7.exact_constants import ieee_bits, ExactArithmeticError

def decode(bits,width):
 p,e,bias=(23,8,127) if width==32 else (52,11,1023)
 field=bits>>p
 mant=bits & ((1<<p)-1)
 if field: mant+=1<<p
 exp=(field if field else 1)-bias-p
 return Fraction(mant*(1<<exp)) if exp>=0 else Fraction(mant,1<<-exp)

results=[]
for width in [32,64]:
 p,e=(23,8) if width==32 else (52,11)
 maxfinite=(((1<<e)-1)<<p)-1
 special=[0,1,2,3,(1<<p)-2,(1<<p)-1,1<<p,(1<<p)+1,((127 if width==32 else 1023)<<p)-1,((127 if width==32 else 1023)<<p),maxfinite-2,maxfinite-1]
 rng=random.Random(20260920+width)
 lows=special+[rng.randrange(0,maxfinite) for _ in range(200)]
 count=0
 for lo in lows:
  a,b=decode(lo,width),decode(lo+1,width)
  midpoint=(a+b)/2
  epsilon=(b-a)/10**90
  for val,expect in [(a,lo),(b,lo+1),(midpoint-epsilon,lo),(midpoint,lo+(lo%2)),(midpoint+epsilon,lo+1)]:
   for sign in [1,-1]:
    expected=expect|((1<<(width-1)) if sign<0 else 0)
    actual=ieee_bits((val*sign,'negative_zero' if not val and sign<0 else True),width)
    assert actual==expected,(width,lo,str(val),actual,expected)
    count+=1
 largest=decode(maxfinite,width)
 ulp=largest-decode(maxfinite-1,width)
 for sign in [1,-1]:
  assert ieee_bits(((largest+ulp/4)*sign,True),width)==maxfinite|((1<<(width-1)) if sign<0 else 0)
  for val in [largest+ulp/2,largest+ulp,largest*2]:
   try: ieee_bits((val*sign,True),width)
   except ExactArithmeticError: pass
   else: raise AssertionError(('overflow accepted',width,val))
 results.append({'width':width,'neighbor_checks':count,'overflow_checks':6,'above_maxfinite_rounds_to_maxfinite_checks':2,'status':'pass'})
output={'method':'Decode chosen IEEE integer encodings into exact rationals, inspect midpoint and values on either side; expected tie follows lower encoding parity. Includes subnormal, normal-boundary, exponent-carry, max-finite and signed-zero controls. Seeded random neighbor sampling augments named boundaries.','candidate_exact_constants_sha256':hashlib.sha256((root/'candidate/a7/exact_constants.py').read_bytes()).hexdigest(),'results':results}
Path(__file__).with_name('rounding-results.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
