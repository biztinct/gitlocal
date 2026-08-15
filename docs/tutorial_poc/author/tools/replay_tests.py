#!/usr/bin/env python3
"""Run the SOURCE-LEVEL pb_learn tests without a database.

    python3 docs/tutorial_poc/author/tools/replay_tests.py

WHY THIS IS A COMMITTED TOOL
----------------------------
There is no odoo-bin on the authoring machine, and the Phase C review turned on
exactly that: four assertions across three files were broken in ways that made
them unfalsifiable, and every one had shipped under a "suite green" claim that
had never been run. **A test written and never executed is not a test.** The
harness that found those was built ad hoc and thrown away, which is why the
same class of bug could come back — so this time it is committed beside the
other offline mirrors (`simulate_resolver.py`, `parity_check.py`,
`test_scenario_rules.py`).

WHAT IT DOES
------------
Stubs the four Odoo symbols these files import, runs `setUpClass` for real, and
executes each `test_*` method against the resulting instance. A method that
touches `self.env` raises out of a deliberately hostile stub and is reported as
SKIP — never as a pass, because a database-bound assertion that silently
succeeds offline is worse than one that does not run at all.

WHAT IT CANNOT SEE, and the list is the point: anything with a record in it.
Access rules, the ORM constraints, the record rules on learn.progress, the
event log's append-only guard. Those run at deploy time, on a staging clone,
and the ledger's F5 note says so.
"""
import os
import re
import sys
import types
import unittest
import json

# FOUR dirnames: tools -> author -> tutorial_poc -> docs -> repo. The
# generator's own comment records getting this wrong by one and writing the
# whole module into docs/ without complaining; the assert below is the same
# lesson, one tool later.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
assert os.path.isdir(os.path.join(REPO, "pb_learn")), (
    "pb_learn not found from %s — check the depth of this path" % REPO)
sys.path.insert(0, REPO)


# ---------------------------------------------------------------- odoo stubs
def _mk(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m


odoo = _mk("odoo")
odoo_modules = _mk("odoo.modules")
odoo_modules_module = _mk("odoo.modules.module")
odoo_tests = _mk("odoo.tests")
odoo_tests_common = _mk("odoo.tests.common")
odoo.modules = odoo_modules
odoo_modules.module = odoo_modules_module
odoo.tests = odoo_tests
odoo_tests.common = odoo_tests_common


def get_module_path(module, downloaded=False, display_warning=True):
    p = os.path.join(REPO, module)
    return p if os.path.isdir(p) else None


odoo_modules_module.get_module_path = get_module_path
odoo_tests_common.TransactionCase = unittest.TestCase


def tagged(*a, **k):
    def deco(cls):
        return cls
    return deco


odoo_tests_common.tagged = tagged
odoo.api = types.SimpleNamespace()
odoo.fields = types.SimpleNamespace()
odoo.models = types.SimpleNamespace()

# make `from .common import ...` work: load the tests package for real
pkg = types.ModuleType("pb_learn_tests")
pkg.__path__ = [os.path.join(REPO, "pb_learn", "tests")]
sys.modules["pb_learn_tests"] = pkg


def load(name):
    import importlib.util
    path = os.path.join(REPO, "pb_learn", "tests", name + ".py")
    spec = importlib.util.spec_from_file_location("pb_learn_tests." + name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pb_learn_tests." + name] = mod
    spec.loader.exec_module(mod)
    return mod


common = load("common")
sys.modules["pb_learn_tests.common"] = common


class NeedsDB(Exception):
    pass


class NoEnv:
    def __getattr__(self, item):
        raise NeedsDB(item)

    def __getitem__(self, item):
        raise NeedsDB(item)


def run(modname, clsname):
    mod = load(modname)
    cls = getattr(mod, clsname)

    class Case(cls):
        def runTest(self):
            pass

    inst = Case()
    inst.env = NoEnv()
    # call setUpClass on the CLASS with TransactionCase.setUpClass neutered
    orig = unittest.TestCase.setUpClass
    unittest.TestCase.setUpClass = classmethod(lambda c: None)
    try:
        Case.setUpClass()
    finally:
        unittest.TestCase.setUpClass = orig

    names = sorted(n for n in dir(cls) if n.startswith("test_"))
    ok = skipped = failed = 0
    for n in names:
        try:
            getattr(inst, n)()
            print("    PASS  %s" % n)
            ok += 1
        except NeedsDB as e:
            print("    SKIP  %s (needs a database: %s)" % (n, e))
            skipped += 1
        except unittest.SkipTest as e:
            print("    SKIP  %s (%s)" % (n, e))
            skipped += 1
        except AssertionError as e:
            print("    FAIL  %s\n          %s" % (n, str(e)[:600]))
            failed += 1
        except Exception as e:  # noqa: BLE001
            print("    ERROR %s: %r" % (n, e))
            failed += 1
    print("  %s.%s -> %d pass, %d skip, %d fail" % (modname, clsname, ok, skipped, failed))
    return ok, skipped, failed


TOTAL = [0, 0, 0]
for modname, clsname in (
    ("test_scenario", "TestScenarioEngine"),
    ("test_retirement", "TestRetirementSeams"),
    ("test_anchor_registry", "TestAnchorRegistry"),
    ("test_assets", "TestAssets"),
):
    print("== %s" % modname)
    r = run(modname, clsname)
    for i in range(3):
        TOTAL[i] += r[i]
print("\nTOTAL: %d pass, %d skip, %d fail" % tuple(TOTAL))
sys.exit(1 if TOTAL[2] else 0)
