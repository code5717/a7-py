"""Selected-child replacement and independent deletion retain runtime values."""

from conftest import run_all_profiles


def test_selected_children_preserve_replacement_and_complementary_values(tmp_path, zig):
    source = '''
io :: import "std/io"
Box :: struct { value: i32 }
Holder :: struct { child: ref Box }
trial :: fn(flag: bool) {
    x := new Box; if x == nil { ret }
    y := new Box; if y == nil { del x; ret }
    z := new Box; if z == nil { del x; del y; ret }
    a := new Holder; if a == nil { del x; del y; del z; ret }
    b := new Holder; if b == nil { del a; del x; del y; del z; ret }
    x.value = 11; y.value = 22; z.value = 33
    a.child = x; b.child = y
    p := a; q := b
    if flag { p = b; q = a }
    if p.child != nil { del p.child }
    p.child = z
    if p.child != nil { io.println("{}", p.child.value) }
    if q.child != nil { io.println("{}", q.child.value); del q.child }
    del z; del a; del b
}
main :: fn() { trial(false); trial(true) }
'''
    assert run_all_profiles(source, tmp_path, zig) == "33\n22\n33\n11\n"
