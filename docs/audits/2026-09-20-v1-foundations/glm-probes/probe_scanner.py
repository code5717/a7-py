"""Adversarial probes for the NOREC-0b candidate scanner.

Each case states the ground truth (is there a real runtime call cycle?) and
prints what the candidate scanner reports, in normal and conservative
(include_unresolved) modes. Run with the candidate scanner on sys.path.
"""
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import norec_scan  # noqa: E402

ROOT = Path(__file__).resolve().parent


def scan_sources(tag, source):
    root = ROOT / f"pkg_{tag}"
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir()
    (root / "__init__.py").write_text("")
    (root / "m.py").write_text(textwrap.dedent(source))
    return norec_scan.scan(root), norec_scan.scan(root, include_unresolved=True)


CASES = {}


def case(tag, truth):
    def deco(fn):
        CASES[tag] = (truth, fn)
        return fn
    return deco


# --- TRUE cycles the scanner should catch ---------------------------------

@case("queued_append_pop_cycle", "TRUE cycle run->lambda->run")
def _(tag):
    return scan_sources(tag, """
        class D:
            def __init__(self):
                self.work = []
            def run(self):
                cb = self.work.pop()
                cb()
            def step(self):
                self.work.append(lambda: self.run())
    """)


@case("augassign_queue_cycle", "TRUE cycle run->lambda->run via += list")
def _(tag):
    return scan_sources(tag, """
        class D:
            def __init__(self):
                self.work = []
            def run(self):
                cb = self.work.pop()
                cb()
            def step(self):
                self.work += [lambda: self.run()]
    """)


@case("partial_queue_cycle", "TRUE cycle run->partial(run)->run")
def _(tag):
    return scan_sources(tag, """
        from functools import partial
        class D:
            def __init__(self):
                self.work = []
            def run(self):
                cb = self.work.pop()
                cb()
            def step(self):
                self.work.append(partial(self.run))
    """)


@case("dict_item_assignment_cycle", "TRUE cycle run->run via d['k']=self.run")
def _(tag):
    return scan_sources(tag, """
        class W:
            def build(self):
                self.d = {}
                self.d["run"] = self.run
                self.d["leaf"] = self.leaf
            def run(self, k):
                return self.d[k](k)
            def leaf(self, k):
                return 1
    """)


@case("dict_call_constructor_cycle", "TRUE cycle run->run via dict(run=self.run)")
def _(tag):
    return scan_sources(tag, """
        class W:
            def __init__(self):
                self.d = dict(run=self.run, leaf=self.leaf)
            def run(self, k):
                return self.d[k](k)
            def leaf(self, k):
                return 1
    """)


@case("factory_returned_table_cycle", "TRUE cycle run->run via make()['run']()")
def _(tag):
    return scan_sources(tag, """
        class W:
            def make(self):
                return {"run": self.run, "leaf": self.leaf}
            def run(self, k):
                return self.make()["run"](k)
            def leaf(self, k):
                return 1
    """)


@case("self_lambda_recursion", "TRUE cycle f->lambda->f")
def _(tag):
    return scan_sources(tag, """
        f = lambda n: f(n - 1) if n > 0 else 0
    """)


@case("getattr_constant_cycle", "TRUE cycle run->run via getattr(self,'run')")
def _(tag):
    return scan_sources(tag, """
        class W:
            def run(self, k):
                return getattr(self, "run")(k)
    """)


@case("dynamic_get_cycle", "TRUE cycle run->run via d.get(k)")
def _(tag):
    return scan_sources(tag, """
        class W:
            def __init__(self):
                self.d = {"run": self.run, "leaf": self.leaf}
            def run(self, k):
                return self.d.get(k)(k)
            def leaf(self, k):
                return 1
    """)


# --- NO cycle: false-positive checks --------------------------------------

@case("queued_only_no_cycle", "NO cycle: step queues lambda; nothing pops in step")
def _(tag):
    return scan_sources(tag, """
        class D:
            def __init__(self):
                self.work = []
            def drive(self):
                while self.work:
                    cb = self.work.pop()
                    cb()
            def step(self):
                self.work.append(lambda: self.step())
    """)


@case("sibling_classes_same_attr", "NO cycle: A and B each queue their own leaf")
def _(tag):
    return scan_sources(tag, """
        class A:
            def __init__(self):
                self.work = []
                self.work.append(lambda: self.leaf_a())
            def drive(self):
                cb = self.work.pop()
                cb()
            def leaf_a(self):
                return 1
        class B:
            def __init__(self):
                self.work = []
                self.work.append(lambda: self.leaf_b())
            def drive(self):
                cb = self.work.pop()
                cb()
            def leaf_b(self):
                return 1
    """)


@case("stored_never_called", "NO cycle: helper stored in dict, only leaf called")
def _(tag):
    return scan_sources(tag, """
        class W:
            def run(self, k):
                d = {"helper": self.helper, "leaf": self.leaf}
                return d["leaf"](k)
            def helper(self, k):
                return self.run(k)
            def leaf(self, k):
                return 1
    """)


def main():
    for tag, (truth, fn) in CASES.items():
        result, conservative = fn(tag)
        print(f"== {tag}")
        print(f"   ground truth: {truth}")
        print(f"   normal groups:      {[tuple(g) for g in result.groups]}")
        print(f"   conservative groups:{[tuple(g) for g in conservative.groups]}")
        unresolved = [(u.caller, u.name, u.candidates) for u in result.unresolved]
        if unresolved:
            print(f"   unresolved: {unresolved}")
        print()


if __name__ == "__main__":
    main()
