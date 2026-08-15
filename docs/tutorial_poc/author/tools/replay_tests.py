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


# ============================================================================
# THE ENGINE'S PURE FUNCTIONS, EXECUTED  (LEARNOS Phase 2)
# ============================================================================
# `glossify` and `tx` are the two pieces of Phase 2 that are pure string in,
# string out — deliberately, because that is what makes them testable without
# a browser. Everything above this line reads SOURCE; this section RUNS it.
#
# The files are copied to `.mjs` and imported by Node. No JSDOM: neither
# function touches the DOM, and if one ever starts to, this section stops
# working, which is the correct alarm.
import shutil
import subprocess
import tempfile

JS_ENGINE = os.path.join(REPO, "pb_learn", "static", "src", "engine")

JS_SUITE = r"""
import { RT, tx, txHtml, esc } from "./runtime.mjs";
import { glossify, setGlossary, glossCardHTML, gtx } from "./glossary.mjs";

let ok = 0, bad = 0;
function check(name, cond, detail) {
    if (cond) { console.log("    PASS  " + name); ok++; }
    else { console.log("    FAIL  " + name + "\n          " + (detail || "")); bad++; }
}

/* A SYNTHETIC table, so the algorithm is tested rather than today's content.
   The shipped table is exercised at the bottom. */
setGlossary([
    { key: "insuranceBase", term: { en: "Insurance base", vi: "Mức lương đóng bảo hiểm" },
      definition: { en: "The salary insurance is charged on.", vi: "Mức lương dùng tính bảo hiểm." },
      match: { en: ["insurance base", "base"], vi: ["mức lương đóng bảo hiểm"] } },
    { key: "bhxh", term: { en: "BHXH", vi: "BHXH" },
      definition: { en: "Social insurance.", vi: "Bảo hiểm xã hội." },
      match: { en: ["bhxh", "social insurance"], vi: ["bhxh", "bảo hiểm xã hội"] } },
    { key: "net", term: { en: "Net", vi: "Thực nhận" },
      definition: { en: "What reaches the bank.", vi: "Tiền về tài khoản." },
      match: { en: ["net"], vi: ["thực nhận"] } },
    { key: "payslip", term: { en: "Payslip", vi: "Phiếu lương" },
      definition: { en: "One person's pay for one month.", vi: "Lương một người một tháng." },
      match: { en: ["payslip", "payslips"], vi: ["phiếu lương"] } },
]);

/* 1. LONGEST MATCH FIRST. "insurance base" must win over "base", and
      "social insurance" must win over the "insurance base" prefix trap. */
let r = glossify("charged on the insurance base", "en");
check("longest-match: 'insurance base' beats 'base'",
      r.includes('data-gloss="insuranceBase"') && !r.includes('>base<'), r);
r = glossify("social insurance is BHXH", "en");
check("longest-match: 'social insurance' resolves to bhxh",
      (r.match(/data-gloss="bhxh"/g) || []).length === 1, r);

/* 2. ONCE PER BLOCK. Six payslips is noise; one is a definition. */
r = glossify("A payslip, another payslip, a third payslip.", "en");
check("once-per-block: one wrapper for three occurrences",
      (r.match(/data-gloss="payslip"/g) || []).length === 1, r);

/* 3. NEVER INSIDE <code>. A code sample that says net means the component
      named NET, and defining take-home pay over it teaches the wrong thing. */
r = glossify("<code>net</code> and then net", "en");
check("no wrap inside <code>",
      r.startsWith("<code>net</code>") && (r.match(/data-gloss/g) || []).length === 1, r);

/* 4. NEVER INSIDE AN ANCHOR. */
r = glossify('<a href="#x">net</a> and net', "en");
check("no wrap inside <a>",
      r.includes('<a href="#x">net</a>') && (r.match(/data-gloss/g) || []).length === 1, r);

/* 5. NEVER IN ATTRIBUTE TEXT. A title= that becomes markup is a tooltip that
      becomes a tag. */
r = glossify('<span title="the net amount">net</span>', "en");
check("no wrap inside an attribute",
      r.includes('title="the net amount"') && (r.match(/data-gloss/g) || []).length === 1, r);

/* 6. LANGUAGE-AWARE, both directions. */
r = glossify("Đây là phiếu lương của bạn", "vi");
check("VI render matches a VI term", r.includes('data-gloss="payslip"'), r);
r = glossify("This is your phiếu lương", "en");
check("EN render does NOT match a VI-only term", !r.includes("data-gloss"), r);
r = glossify("Bảng này là payslip", "vi");
check("VI render does NOT match an EN-only term", !r.includes("data-gloss"), r);

/* 7. WORD BOUNDARIES. "net" must not fire inside "network", and a hyphenated
      phrase must still match across the hyphen. */
r = glossify("the network is fine", "en");
check("no match inside a longer word", !r.includes("data-gloss"), r);

/* 8. AUTHORED MARKUP SURVIVES. The body is trusted and inserted raw; the pass
      adds spans and changes nothing else. */
r = glossify("Your <b>net</b> pay", "en");
check("authored <b> is preserved", r.includes("<b>") && r.includes("data-gloss"), r);

/* 9. IDEMPOTENT. */
const once = glossify("one payslip", "en");
check("running twice changes nothing", glossify(once, "en") === once, once);

/* 10. THE CARD renders term and definition, escaped. */
RT.lang = "en";
const card = glossCardHTML("bhxh");
check("card carries the term and the definition",
      card.includes("BHXH") && card.includes("Social insurance."), card);
check("an unknown key renders nothing", glossCardHTML("nope") === "", "!");

/* ====================================================== token escaping
   THE PHASE 2 HARDENING, at the seam it actually belongs on.

   A tenant administrator types the value of a `learn.tenant.override` slot.
   It is interpolated into lesson bodies — and eight of those positions insert
   the result as RAW HTML. Unescaped, that was a tenant-admin -> learner XSS
   surface.

   The escape lives in `txHtml`/`gtx` (the raw positions) and NOT in `tx`,
   because ~400 sites are `esc(tx(...))` and escaping in `tx` double-escapes
   every one of them. Both halves are asserted: the raw path must be inert,
   and the escaped path must not be escaped twice. */
RT.tokens = {
    companyDisplayName: { en: "<script>alert(1)</script>", vi: "<script>alert(1)</script>" },
    gmTierName: { en: 'Finance " onmouseover=x', vi: "Tài chính" },
    payrollSupportContact: { en: "Trần & Sons", vi: "Trần & Sons" },
};
RT.lang = "en";

/* --- the RAW positions: inert, always ------------------------------------ */
let out = txHtml("Welcome to {{companyDisplayName}}.");
check("txHtml: a <script> in a token value renders inert",
      !out.includes("<script") && out.includes("&lt;script&gt;"), out);
check("txHtml: the escaped value keeps its text", out.includes("alert(1)"), out);
out = txHtml("Approved at {{gmTierName}}.");
check("txHtml: a quote in a token value is escaped",
      !out.includes('" onmouseover') && out.includes("&quot;"), out);

/* The body itself is STILL trusted — escaping the token must not escape the
   authored markup around it, or every <b> in the module would print as text. */
out = txHtml("<b>Bold</b> at {{gmTierName}}.");
check("txHtml: the authored body is not escaped", out.startsWith("<b>Bold</b>"), out);

/* gtx is the wrapper the eight raw sites actually call. Same guarantee. */
out = gtx({ en: "The net at {{companyDisplayName}}.", vi: "x" });
check("gtx: no live tag survives the token",
      !out.includes("<script") && out.includes("&lt;script&gt;"), out);
check("gtx: the glossary pass still runs", out.includes('data-gloss="net"'), out);

/* --- the ESCAPED positions: single-escaped, never double ----------------- */
/* THE REGRESSION THIS PAIR EXISTS FOR. Phase 2 first escaped inside `tx`,
   which made "Trần & Sons" render as "Trần &amp;amp; Sons" at every one of
   the ~400 esc(tx(...)) call sites. `tx` is raw; `esc` escapes once. */
check("tx: a token value is returned RAW",
      tx("Ask {{payrollSupportContact}}.") === "Ask Trần & Sons.",
      tx("Ask {{payrollSupportContact}}."));
check("esc(tx(...)): an ampersand in a token is escaped exactly once",
      esc(tx("Ask {{payrollSupportContact}}.")) === "Ask Trần &amp; Sons.",
      esc(tx("Ask {{payrollSupportContact}}.")));
check("esc(tx(...)): no &amp;amp; anywhere",
      !esc(tx("Ask {{payrollSupportContact}}.")).includes("&amp;amp;"),
      esc(tx("Ask {{payrollSupportContact}}.")));
check("txHtml: an ampersand in a RAW position is escaped exactly once",
      txHtml("Ask {{payrollSupportContact}}.") === "Ask Trần &amp; Sons.",
      txHtml("Ask {{payrollSupportContact}}."));

/* An unknown slot still renders its own name, visibly, and is not injectable
   through the key (the token regex only admits [A-Za-z][A-Za-z0-9_]*). */
check("tx: an unknown slot renders the key",
      tx("x {{nosuchslot}} y") === "x {{nosuchslot}} y", tx("x {{nosuchslot}} y"));
check("esc: the primitive itself",
      esc('<a href="x">&</a>') === "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;", esc("<"));

console.log("  glossify/tx -> " + ok + " pass, 0 skip, " + bad + " fail");
process.exit(bad ? 1 : 0);
"""


def js_checks():
    """node --check on every engine file, then run the pure-function suite."""
    print("== engine JS")
    ok = failed = 0
    tmp = tempfile.mkdtemp(prefix="pblearn-js-")
    try:
        # `node --check` needs module syntax it recognises; the sources are ESM
        # with Odoo's banner comment, so a `.mjs` copy checks cleanly.
        for name in sorted(os.listdir(JS_ENGINE)):
            if not name.endswith(".js"):
                continue
            dst = os.path.join(tmp, name[:-3] + ".mjs")
            src = open(os.path.join(JS_ENGINE, name), encoding="utf-8").read()
            # Relative imports between engine files have to find the copies.
            src = re.sub(r'(from\s+")(\./[A-Za-z0-9_./-]+?)(")',
                         lambda m: m.group(1) + m.group(2) + ".mjs" + m.group(3), src)
            open(dst, "w", encoding="utf-8").write(src)
        for name in sorted(os.listdir(tmp)):
            r = subprocess.run(["node", "--check", os.path.join(tmp, name)],
                               capture_output=True, text=True)
            if r.returncode:
                print("    FAIL  node --check %s\n          %s"
                      % (name, r.stderr.strip()[:300]))
                failed += 1
            else:
                print("    PASS  node --check %s" % name)
                ok += 1
        suite = os.path.join(tmp, "_suite.mjs")
        open(suite, "w", encoding="utf-8").write(JS_SUITE)
        r = subprocess.run(["node", suite], capture_output=True, text=True, cwd=tmp)
        sys.stdout.write(r.stdout)
        if r.stderr.strip():
            sys.stdout.write("          " + r.stderr.strip()[:600] + "\n")
        for line in r.stdout.splitlines():
            if line.strip().startswith("PASS"):
                ok += 1
            elif line.strip().startswith("FAIL"):
                failed += 1
        if r.returncode and not failed:
            failed += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("  engine JS -> %d pass, 0 skip, %d fail" % (ok, failed))
    return ok, 0, failed


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

r = js_checks()
for i in range(3):
    TOTAL[i] += r[i]

print("\nTOTAL: %d pass, %d skip, %d fail" % tuple(TOTAL))
sys.exit(1 if TOTAL[2] else 0)
