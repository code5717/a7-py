from pathlib import Path
import subprocess,tempfile,json
repo=Path(__file__).resolve().parents[2]
programs={
'callbacks': '''io :: import "std/io"

BinaryOp :: fn(i32, i32) i32

add :: fn(a: i32, b: i32) i32 {
    ret a + b
}

apply :: fn(op: BinaryOp, a: i32, b: i32) i32 {
    ret op(a, b)
}

main :: fn() {
    raw: fn(i32, i32) i32 = add
    callback: BinaryOp = add
    io.println("{} {}", raw(8, 3), apply(callback, 8, 3))
}
''',
'match_fall': '''io :: import "std/io"

main :: fn() {
    value := 1
    match value {
        case 1: {
            io.println("one")
            fall
        }
        case 2: {
            io.println("two")
        }
        else: {
            io.println("other")
        }
    }
}
''',
'array_operations': '''io :: import "std/io"

main :: fn() {
    numbers: [4]i32 = [10, 20, 30, 40]
    middle := numbers[1..3]
    index: usize = 0
    io.println("{} {}", middle[index], middle.len)

    left: [2]f64 = [1.0, 2.0]
    right: [2]f64 = [3.0, 4.0]
    sum: [2]f64 = left + right
    io.println("{} {}", sum[0], sum[1])

    text: string = "A7"
    prefix := text[0..1]
    for ch in prefix {
        io.print("{}", ch)
    }
    io.println(" {}", text.len)
}
''',
'capture_match': '''io :: import "std/io"
score :: fn(x: i32) i32 {
    ret match x {
        case value: value + 1
    }
}
main :: fn() { io.println("{}", score(4)) }
''',
'array_initialization': '''io :: import "std/io"
main :: fn() {
    zeroes: [3]i32
    filled: [3]i32 = 7
    matrix: [2][2]i32 = [[1, 2], [3, 4]]
    io.println("{} {} {}", zeroes[0], filled[2], matrix[1][0])
}
''',
'match_patterns': '''io :: import "std/io"
main :: fn() {
    value := 5
    match value {
        case 0: io.println("zero")
        case 1, 2, 3: io.println("small")
        case 4..10: io.println("range")
        else: io.println("other")
    }
}
'''
}
programs['array_operations_valid']=programs['array_operations'].replace('io.println(" {}", text.len)', 'io.println(" {}", prefix.len)')
programs['array_zero_initialization']=programs['array_initialization'].replace('    filled: [3]i32 = 7\n', '').replace('"{} {} {}", zeroes[0], filled[2], matrix[1][0]', '"{} {}", zeroes[0], matrix[1][0]')
programs['constrained_generic']='''io :: import "std/io"
IntOnly :: @type_set(i32, i64)
identity($T: IntOnly) :: fn(value: $T) $T {
    ret value
}
main :: fn() { io.println("{}", identity(42)) }
'''
programs['builtin_constraint']=programs['constrained_generic'].replace('IntOnly :: @type_set(i32, i64)\n','').replace('$T: IntOnly','$T: Numeric')
programs['inline_constraint']=programs['constrained_generic'].replace('IntOnly :: @type_set(i32, i64)\n','').replace('$T: IntOnly','$T: @type_set(i32, i64)')
results=[]
with tempfile.TemporaryDirectory(prefix='a7-reference-') as td:
 for name,source in programs.items():
  src=Path(td)/(name+'.a7');src.write_text(source); zig=src.with_suffix('.zig')
  cp=subprocess.run(['uv','run','a7',str(src),'-o',str(zig),'--format','json'],cwd=repo,capture_output=True,text=True)
  payload=json.loads(cp.stdout)
  result={'name':name,'source':source,'compile_exit':cp.returncode,'diagnostic':payload.get('error')}
  if cp.returncode==0:
   native=subprocess.run(['zig','run',str(zig)],cwd=repo,capture_output=True,text=True)
   result.update(native_exit=native.returncode,stdout=native.stdout,stderr=native.stderr)
  results.append(result)
  print(name,cp.returncode,result.get('native_exit'),result.get('stdout'),result.get('stderr','')[:200])
(repo/'site/docs/reference-probes.json').write_text(json.dumps(results,indent=2)+'\n')

expected_output = {'callbacks': '11 11\n', 'match_fall': 'one\ntwo\n',
 'capture_match': '5\n', 'match_patterns': 'range\n',
 'array_operations_valid': '20 2\n4 6\nA 1\n',
 'array_zero_initialization': '0 3\n', 'builtin_constraint': '42\n',
 'inline_constraint': '42\n'}
for result in results:
 name = result['name']
 if name in expected_output:
  assert result['compile_exit'] == 0 and result['native_exit'] == 0, result
  assert result['stdout'] == expected_output[name], result
 elif name in {'array_operations', 'array_initialization'}:
  assert result['compile_exit'] == 6, result
 elif name == 'constrained_generic':
  assert result['compile_exit'] == 7, result
