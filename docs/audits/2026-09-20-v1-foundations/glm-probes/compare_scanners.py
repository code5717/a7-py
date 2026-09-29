"""Compare baseline and candidate scanners on the real a7/ tree."""
import importlib.util
import sys
from pathlib import Path

REPO = Path("/home/cx89/Projects/pl-dev/a7-py")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


base = load("base_scan", REPO / "tmp/norec0b/baseline/norec_scan.py")
cand = load("cand_scan", REPO / "tmp/norec0b/candidate/test/norec_scan.py")

rb = base.scan(REPO / "a7")
rc = cand.scan(REPO / "a7")
rbc = base.scan(REPO / "a7", include_unresolved=True)
rcc = cand.scan(REPO / "a7", include_unresolved=True)

gb = {tuple(g) for g in rb.groups}
gc = {tuple(g) for g in rc.groups}
print("baseline groups:", len(gb), " candidate groups:", len(gc))
print("only in baseline:", sorted(gb - gc))
print("only in candidate:", sorted(gc - gb))

gbc = {tuple(g) for g in rbc.groups}
gcc = {tuple(g) for g in rcc.groups}
print("baseline conservative:", len(gbc), " candidate conservative:", len(gcc))
print("conservative only in baseline:", sorted(gbc - gcc))
print("conservative only in candidate:", sorted(gcc - gbc))
print("candidate: groups == conservative groups:", gc == gcc)

eb = {k: set(v) for k, v in rb.edges.items()}
ec = {k: set(v) for k, v in rc.edges.items()}
keys = set(eb) | set(ec)
diffs = [(k, eb.get(k, set()), ec.get(k, set())) for k in keys if eb.get(k, set()) != ec.get(k, set())]
print("edge-count baseline:", sum(len(v) for v in eb.values()),
      " candidate:", sum(len(v) for v in ec.values()),
      " differing nodes:", len(diffs))
for k, b, c in diffs[:25]:
    print("  ", k, "\n     base-only:", sorted(b - c), "\n     cand-only:", sorted(c - b))
print("baseline unresolved:", len(rb.unresolved), " candidate unresolved:", len(rc.unresolved))
print("baseline deepcopy:", len(rb.deepcopy_calls), " candidate deepcopy:", len(rc.deepcopy_calls))
print("baseline dataclass findings:", len(rb.dataclass_findings),
      " candidate dataclass findings:", len(rc.dataclass_findings))
