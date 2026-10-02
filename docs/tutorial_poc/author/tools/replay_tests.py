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


def load(name, addon="pb_learn", pkgname="pb_learn_tests"):
    import importlib.util
    if pkgname not in sys.modules:
        p = types.ModuleType(pkgname)
        p.__path__ = [os.path.join(REPO, addon, "tests")]
        sys.modules[pkgname] = p
        # A DOTTED package name has to be reachable as an attribute of its
        # parent, or a `from ..x import y` inside it resolves to nothing. That
        # is exactly why pb_tenants' tests are loaded as `pb_tenants.tests`
        # and pb_learn's are not: the pb_learn suite imports only siblings, so
        # it can stay out of the real package and away from its __init__.
        if "." in pkgname:
            parent, _sep, leaf = pkgname.rpartition(".")
            if parent in sys.modules:
                setattr(sys.modules[parent], leaf, p)
    path = os.path.join(REPO, addon, "tests", name + ".py")
    spec = importlib.util.spec_from_file_location(pkgname + "." + name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[pkgname + "." + name] = mod
    spec.loader.exec_module(mod)
    return mod


common = load("common")
sys.modules["pb_learn_tests.common"] = common


# ---------------------------------------------------------------------------
# LEARNOS Phase 3 — two neighbouring modules, replayed the same way.
#
# `pb_dashboard`'s source assertions need nothing but the stubs above.
# `pb_tenants`'s need ONE symbol out of a file that imports half of Odoo's
# service layer, so rather than stub that layer the harness lifts the shipped
# function out of the real source by AST and executes THAT. The distinction
# matters: this is the code that ships, compiled from the file it ships in —
# not a copy of it living in a test.
# ---------------------------------------------------------------------------
def lift(addon, relpath, *names):
    """Compile named top-level functions (and constants) out of a source file.

    LEARNOS Phase 6 added the constants. `payroll_ai_report`'s two prompt
    builders interpolate a module-level note that tells the model what a
    placeholder is — lifting the functions alone gave them a NameError at call
    time, which would have made the offline replay of the report prompt
    impossible for the sake of one string. Names are matched against function
    definitions AND simple top-level assignments, so the caller asks for what
    it needs by name and nothing else comes across.
    """
    import ast
    path = os.path.join(REPO, addon, relpath)
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    wanted = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            wanted.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(t in names for t in targets):
                wanted.append(node)
                found |= {t for t in targets if t in names}
    missing = set(names) - found
    assert not missing, "%s does not define %s" % (relpath, sorted(missing))
    ns = {}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), path, "exec"), ns)
    return ns


def _fake_pkg(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


# ---------------------------------------------------------------------------
# LEARNOS Phase 4 — PayAI's egress tests, executed here for the same reason
# everything else in this file is: there is no odoo-bin, and a test that has
# never run is not a test. This is the phase's PRIVACY suite, so "written and
# unexecuted" would have been the worst possible place for it.
#
# `ai_redaction.py` is imported FOR REAL: it has no Odoo import in it, by
# design, so the module under test is the module that ships. The two prompt
# builders cannot be imported whole — their files define Odoo models — so they
# are LIFTED by AST out of the shipped source, which is still the shipped code
# rather than a copy living in a test.
# ---------------------------------------------------------------------------
def load_pure(relpath, modname):
    """Import a dependency-free module straight off disk, under a given name."""
    import importlib.util
    path = os.path.join(REPO, relpath)
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


_addons = _fake_pkg("odoo.addons")
odoo.addons = _addons

# Enough of `odoo.models` / `odoo.api` for a MODEL FILE to import. Two class
# statements and a decorator are all `learn_intent.py` needs at import time —
# nothing here pretends to be an ORM, and any method that reaches for one dies
# on `NoEnv` and is reported as SKIP, which is the behaviour the harness is
# built around.
odoo.models.AbstractModel = type("AbstractModel", (), {})
odoo.models.Model = odoo.models.AbstractModel
odoo.models.TransientModel = odoo.models.AbstractModel
odoo.api.model = staticmethod(lambda fn: fn).__func__
odoo.api.constrains = lambda *a, **k: (lambda fn: fn)
odoo.api.depends = lambda *a, **k: (lambda fn: fn)

_learn = _fake_pkg("odoo.addons.pb_learn")
_addons.pb_learn = _learn
_learn_models = _fake_pkg("odoo.addons.pb_learn.models")
_learn.models = _learn_models
# The REAL module, imported whole. Its pure functions — explain_blocks,
# build_corpus and the two prompt builders — are what LEARNOS Phase 4's offline
# replay exercises, and they are exercised in the file that ships them.
_learn_models.learn_intent = load_pure(
    "pb_learn/models/learn_intent.py",
    "odoo.addons.pb_learn.models.learn_intent")
# LEARNOS Phase 6 — the "what next" decision table and the streak counter.
# LIFTED rather than imported: learn_runtime.py defines an Odoo model and
# imports pytz and a sibling model file, while the two rules under test are
# pure functions over lists and dates. `timedelta` is handed in the same way
# the pulse's `json` is — lift() compiles the functions alone and does not run
# the imports above them.
_runtime_ns = lift("pb_learn", "models/learn_runtime.py",
                   "choose_next", "reading_order", "streak_days")
_runtime_ns["timedelta"] = __import__("datetime").timedelta
# The one constant it borrows from its neighbour, rather than re-typing the
# prefix that decides whether a mission's progress row can be found at all.
_runtime_ns["MISSION_PREFIX"] = lift(
    "pb_learn", "models/learn_progress.py", "MISSION_PREFIX")["MISSION_PREFIX"]
_learn_models.learn_runtime = _fake_pkg(
    "odoo.addons.pb_learn.models.learn_runtime", **_runtime_ns)

_payai = _fake_pkg("odoo.addons.pb_payroll_ai_insights")
_addons.pb_payroll_ai_insights = _payai
_payai_models = _fake_pkg("odoo.addons.pb_payroll_ai_insights.models")
_payai.models = _payai_models
_payai_models.ai_redaction = load_pure(
    "pb_payroll_ai_insights/models/ai_redaction.py",
    "odoo.addons.pb_payroll_ai_insights.models.ai_redaction")
_payai_models.payroll_ai_engine = _fake_pkg(
    "odoo.addons.pb_payroll_ai_insights.models.payroll_ai_engine",
    **lift("pb_payroll_ai_insights", "models/payroll_ai_engine.py",
           "data_query_prompt"))
# The pulse's two module-level functions. `redacted_details` calls into
# ai_redaction, so the lifted namespace is given the real module's names —
# lift() compiles the functions alone and does not run the imports above them.
_pulse_ns = lift("pb_payroll_ai_insights", "models/payroll_ai_pulse.py",
                 "pulse_summary_prompt", "redacted_details")
_pulse_ns["json"] = json
_pulse_ns["redact_names"] = _payai_models.ai_redaction.redact_names
_pulse_ns["restore_names"] = _payai_models.ai_redaction.restore_names
_payai_models.payroll_ai_pulse = _fake_pkg(
    "odoo.addons.pb_payroll_ai_insights.models.payroll_ai_pulse", **_pulse_ns)
# LEARNOS Phase 6 — the PDF report's two prompt builders, lifted for the same
# reason as the others: the file defines an Odoo model, and the claim being
# tested is about a STRING. This path spent four phases dead, so the day it
# was switched on is the day its prompt has to be assertable offline.
_report_ns = lift("pb_payroll_ai_insights", "models/payroll_ai_report.py",
                  "report_section_prompt", "report_executive_prompt",
                  "redact_sections", "alert_rows", "alert_names",
                  "summary_is_traceable", "_PLACEHOLDER_NOTE",
                  "PERSON_NAMING_CATEGORIES", "SUMMARY_DATA_CHARS",
                  "SECTION_DATA_CHARS")
_report_ns["json"] = json
_report_ns["_logger"] = __import__("logging").getLogger("replay")
for _name in ("PERSON_KEYS", "collect_names", "extend_mapping", "redact_names",
              "redact_text", "restore_names"):
    _report_ns[_name] = getattr(_payai_models.ai_redaction, _name)
_payai_models.payroll_ai_report = _fake_pkg(
    "odoo.addons.pb_payroll_ai_insights.models.payroll_ai_report",
    **_report_ns)

_tenants = _fake_pkg("pb_tenants")
_tenants.__path__ = [os.path.join(REPO, "pb_tenants")]
_tenants_models = _fake_pkg("pb_tenants.models")
_tenants_models.__path__ = [os.path.join(REPO, "pb_tenants", "models")]
_tenants.models = _tenants_models
_tenants_models.service = _fake_pkg(
    "pb_tenants.models.service",
    **lift("pb_tenants", "models/service.py", "currency_change"))


class NeedsDB(Exception):
    pass


class NoEnv:
    def __getattr__(self, item):
        raise NeedsDB(item)

    def __getitem__(self, item):
        raise NeedsDB(item)


def run(modname, clsname, addon="pb_learn", pkgname="pb_learn_tests"):
    mod = load(modname, addon, pkgname)
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

    # A class whose setUp needs a database skips ENTIRELY rather than reporting
    # an AttributeError per method. Added in Phase 3, when the first class with
    # a database-bound setUp arrived: an ERROR that means "not run here" is
    # noise that eventually gets ignored, and this harness's whole value is
    # that its output is read.
    setup_failed = None
    setup_broken = None
    try:
        inst.setUp()
    except NeedsDB as e:
        setup_failed = "needs a database: %s" % e
    except Exception as e:                                      # noqa: BLE001
        # A setUp that dies for any reason OTHER than needing a database is a
        # broken suite, and a broken suite reported as SKIP is a green light
        # nobody meant to give. It fails, loudly, once per class.
        setup_broken = repr(e)

    names = sorted(n for n in dir(cls) if n.startswith("test_"))
    ok = skipped = failed = 0
    for n in names:
        if setup_broken:
            print("    FAIL  %s (setUp broke: %s)" % (n, setup_broken))
            failed += 1
            continue
        if setup_failed:
            print("    SKIP  %s (setUp %s)" % (n, setup_failed))
            skipped += 1
            continue
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
import { SCREENS, practiceShellHTML } from "./screens.mjs";
import { INPUT_ANCHORS } from "./fixture.mjs";
import { looseMatch, foldText, foldNumber } from "./input_match.mjs";

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
/* 9b. AND THE GUARD IS KEYED ON THE WRAPPER, NOT ON THE ATTRIBUTE NAME.
   A tenant slot's value reaches a body through gtx, escaped — so it can carry
   the literal `data-gloss=` as TEXT. Keying the guard on that substring let a
   value somebody typed switch the whole pass off for the body it landed in.
   (Ledger, Phase 2 accepted nit; closed in Phase 5.) */
RT.tokens = { companyDisplayName: { en: "data-gloss=x Ltd", vi: "data-gloss=x Ltd" } };
let guarded = gtx({ en: "The net at {{companyDisplayName}}.", vi: "x" });
check("a token value containing the attribute name does not disable glossing",
      guarded.includes('data-gloss="net"'), guarded);
check("...and the value itself is still inert text",
      guarded.includes("data-gloss=x Ltd"), guarded);

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

/* ================================================= practice mode (Phase 5)
   THE WATERMARK, EXECUTED. The source test in tests/test_practice.py asserts
   that the builder has no branch in it; this one runs the builder for every
   replica there is and looks at the output, which is the half that would
   notice the mark being deleted rather than merely made conditional.

   Both languages, because the mark is chrome and chrome follows the reader —
   and a mark that vanished in Vietnamese would vanish for most of the people
   this module is written for. */
const screenKeys = Object.keys(SCREENS);
check("the replica still has its twenty screens",
      screenKeys.length === 20, "found " + screenKeys.length);
let marked = 0;
for (const lang of ["en", "vi"]) {
    RT.lang = lang;
    for (const key of screenKeys) {
        const html = practiceShellHTML(key, new Set());
        if (html.includes('data-coach="rep-watermark"')) { marked++; }
    }
}
check("every practice screen carries the watermark, in both languages",
      marked === screenKeys.length * 2,
      marked + " of " + (screenKeys.length * 2));
/* An unknown screen key renders an empty body — and STILL carries the mark.
   That is the case a state flag would have got wrong: no body, no banner. */
check("even an unknown screen carries the watermark",
      practiceShellHTML("no_such_screen", new Set())
          .includes('data-coach="rep-watermark"'), "!");
/* FREE-ROAM. In practice mode every section is in scope, so no leaf is
   greyed out; a lesson's shell greys everything outside its own section, and
   that difference is what makes the sandbox a sandbox. */
const free = practiceShellHTML("dashboard", new Set());
check("practice mode leaves every menu leaf reachable",
      !free.includes('aria-disabled="true"'),
      "a practice screen has a disabled leaf");
/* NINETEEN, not twenty: the import wizard is a flow and has no sidebar leaf,
   which is why it is a SUB_SCREEN. So the sandbox can reach every replica the
   menu can name, and the one it cannot name is the one the product cannot
   either. */
check("every menu leaf is a nav target in the sandbox",
      (free.match(/data-nav="/g) || []).length === 19,
      (free.match(/data-nav="/g) || []).length + " nav targets");
/* NAV SWITCHING, executed. `pNav` writes one key and the view builder reads
   it, so what has to be true is that two keys really are two screens — a
   builder that ignored its argument would pass every check above it. */
const onDash = practiceShellHTML("dashboard", new Set());
const onStat = practiceShellHTML("statutory", new Set());
check("two nav targets render two different screens",
      onDash !== onStat && onDash.includes('data-coach="dash-kpis"')
      && onStat.includes('data-coach="st-kpis"'), "!");
check("the menu marks the screen you are on, and only that one",
      (onStat.match(/class="lrn-item on/g) || []).length === 1,
      (onStat.match(/class="lrn-item on/g) || []).length + " marked");
RT.lang = "en";

/* =============================================== the loose match (Phase 5)
   THE NEGATIVE CONTROL IS HALF OF THIS BLOCK, and deliberately so. A matcher
   is only worth having if it says NO — every "accepts" case below has a
   "refuses" case beside it, because a comparison that returned true would pass
   the first list on its own and would turn every input step into a keypress. */

/* Numbers: the thousands mark is the reader's, not the author's. The same step
   is played by somebody typing 1,200,000 and by somebody typing 1.200.000. */
for (const typed of ["1200000", "1,200,000", "1.200.000", "1 200 000",
                     "  1200000  ", "1200000 ₫"]) {
    check("number accepts " + JSON.stringify(typed),
          looseMatch(typed, "1.200.000", "number"), foldNumber(typed));
}
for (const typed of ["120000", "12000000", "1200001", "", "   ", "abc",
                     "1,200,00"]) {
    check("number REFUSES " + JSON.stringify(typed),
          !looseMatch(typed, "1.200.000", "number"), foldNumber(typed));
}
/* And the expected side is folded the same way, so an author who writes the
   English grouping does not change what a Vietnamese learner may type. */
check("number: both sides fold, either way round",
      looseMatch("1.200.000", "1,200,000", "number")
      && looseMatch("1,200,000", "1.200.000", "number"), "!");

/* Text: trimmed, casefolded, and tone marks optional — the keyboard somebody
   has is not part of the lesson. A DIFFERENT name is still a different name. */
for (const typed of ["Nguyễn Văn An", "nguyen van an", "  Nguyen  Van   An ",
                     "NGUYEN VAN AN"]) {
    check("text accepts " + JSON.stringify(typed),
          looseMatch(typed, "Nguyễn Văn An", "text"), foldText(typed));
}
for (const typed of ["Nguyen Van Anh", "Nguyen An", "Van An Nguyen", "",
                     "   ", "Nguyen Van"]) {
    check("text REFUSES " + JSON.stringify(typed),
          !looseMatch(typed, "Nguyễn Văn An", "text"), foldText(typed));
}
check("text: đ folds to d rather than disappearing",
      foldText("Đỗ Thị Lan") === "do thi lan", foldText("Đỗ Thị Lan"));
/* An empty EXPECTED can never be satisfied either. A step whose value went
   missing must not become a step that advances on anything typed at all. */
check("an empty expected value matches nothing",
      !looseMatch("anything", "", "text") && !looseMatch("", "", "text"), "!");
/* The kind is read off INPUT_ANCHORS, and an unknown kind must fall back to
   the STRICTER of the two — text, where 1.200.000 and 1,200,000 differ. */
check("an unknown kind is compared as text",
      !looseMatch("1,200,000", "1.200.000", "wat"), "!");

/* The table itself: both declared fields are drawn by the replica, in the one
   screen each belongs to. The generator checks this too; here it is checked
   against the RENDERED html rather than against the source. */
RT.lang = "en";
const anchorScreens = { "rep-impfix": "importwizard", "rep-newemp-name": "employees" };
for (const [anchor, screen] of Object.entries(anchorScreens)) {
    const html = SCREENS[screen]();
    check("the replica draws a real input at " + anchor,
          html.includes('<input') && html.includes('data-coach="' + anchor + '"'),
          screen);
}
check("every declared input anchor is one of those two",
      Object.keys(INPUT_ANCHORS).sort().join(",")
        === Object.keys(anchorScreens).sort().join(","),
      Object.keys(INPUT_ANCHORS).join(","));

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


# ============================================================================
# THE TRY BRIDGE, LIFTED AND DRIVEN  (LEARNOS Phase 5 review round)
# ============================================================================
# The click bridge and the input check are the two methods a learner's fingers
# reach, and every property this phase claims about them — a wrong value never
# advances, a click on a field never advances, a blur and the click that caused
# it are ONE advance, and a KEYBOARD activation after a blur is not swallowed —
# is a property of how they behave in sequence. Source-level assertions cannot
# see a sequence.
#
# So the real methods are lifted out of journey.js by name and executed against
# a stub `this` and a hand-rolled DOM of three objects. Lifted, not copied: a
# copy in this file would be a second bridge, and the second one is always the
# one that stays right.
BRIDGE_METHODS = ('_scenarioClick', '_scenarioInputCheck', 'onKeydown',
                  'onFocusOut', 'onMouseDown')


def _lift_js_methods(path, names):
    """Pull named ES class methods out of a file as source text."""
    with open(path, encoding='utf-8') as fh:
        lines = fh.read().split('\n')
    out, start, name = {}, None, None
    for i, line in enumerate(lines):
        m = re.match(r'^    (?:async )?([A-Za-z_$][\w$]*)\(', line)
        if m and start is None:
            name, start = m.group(1), i
            continue
        if start is not None and line == '    }':
            if name in names:
                out[name] = '\n'.join(lines[start:i + 1])
            start = None
    missing = set(names) - set(out)
    assert not missing, 'journey.js no longer defines %s' % sorted(missing)
    return out


BRIDGE_IMPORTS = r"""
import { RT } from "./runtime.mjs";
import { INPUT_ANCHORS } from "./fixture.mjs";
import { looseMatch } from "./input_match.mjs";
"""

BRIDGE_SUITE = r"""
let ok = 0, bad = 0;
function check(name, cond, detail) {
    if (cond) { console.log("    PASS  " + name); ok++; }
    else { console.log("    FAIL  " + name + "\n          " + (detail || "")); bad++; }
}
const tx = (v) => (v && (v[RT.lang] || v.en)) || "";

/* --- the three-object DOM. `closest` is the only thing the bridge uses. --- */
function el(anchor, tag, value) {
    const node = {
        tagName: tag || "BUTTON", value: value === undefined ? "" : value,
        getAttribute: (n) => (n === "data-coach" ? anchor : null),
        matches: (s) => s === "input" && tag === "INPUT",
    };
    node.closest = (sel) => {
        if (sel === "input") { return tag === "INPUT" ? node : null; }
        return anchor ? node : null;
    };
    return node;
}

/* --- the bridge, with a stub `this`. ------------------------------------ */
function bridge(steps) {
    const self = {
        state: { view: "scenario", sDone: false, sStep: 0, sNudge: false, sMiss: false },
        advances: 0,
        get sCurrent() { return steps[self.state.sStep] || null; },
        sNext() { self.advances++; self.state.sStep++; self.state.sNudge = false;
                  self.state.sMiss = false; },
    };
    Object.assign(self, METHODS);
    return self;
}
/* Gestures, in the order a browser dispatches them. */
const click = (b, node) => { b.onMouseDown(); b._scenarioClick({ target: node }); };
const blurTo = (b, node) => b.onFocusOut({ target: node });
const press = (b, node, key) =>
    b.onKeydown({ key, target: node, preventDefault() {} });

const FIELD = "rep-impfix";
const NEXT = "rep-impmatch";
const STEPS = [
    { key: "fixcell", anchor: FIELD, act: "input",
      value: { en: "1,200,000", vi: "1.200.000" } },
    { key: "matchrow", anchor: NEXT, act: "click" },
    { key: "landed", anchor: "iw-outcome", act: "observe" },
];
check("the lifted bridge knows the field it is driving",
      !!INPUT_ANCHORS[FIELD] && INPUT_ANCHORS[FIELD].kind === "number", FIELD);

/* 1. A CLICK ON THE FIELD NEVER ADVANCES. */
let b = bridge(STEPS);
click(b, el(FIELD, "INPUT", ""));
check("clicking an input step's own field does not advance",
      b.advances === 0 && b.state.sStep === 0, "advances=" + b.advances);

/* 2. A WRONG VALUE NEVER ADVANCES, and says so. */
b = bridge(STEPS);
press(b, el(FIELD, "INPUT", "12"), "Enter");
check("a wrong value does not advance and raises the hint",
      b.advances === 0 && b.state.sMiss === true, "advances=" + b.advances);

/* 3. THE RIGHT VALUE ADVANCES ONCE — in either reader's grouping. */
for (const [lang, typed] of [["en", "1,200,000"], ["vi", "1.200.000"],
                             ["en", "1200000"]]) {
    RT.lang = lang;
    b = bridge(STEPS);
    press(b, el(FIELD, "INPUT", typed), "Enter");
    check("Enter with " + JSON.stringify(typed) + " [" + lang + "] advances once",
          b.advances === 1 && b.state.sStep === 1, "advances=" + b.advances);
}
RT.lang = "en";

/* 4. THE MOUSE GESTURE. Type, then click the control the NEXT step wants:
      mousedown, focusout, click — and exactly ONE step of movement, because
      the card in between must not be skipped. */
b = bridge(STEPS);
b.onMouseDown();
blurTo(b, el(FIELD, "INPUT", "1.200.000"));
b._scenarioClick({ target: el(NEXT, "BUTTON") });
check("type then mouse-click the next control: exactly one advance",
      b.advances === 1 && b.state.sStep === 1, "advances=" + b.advances);

/* 5. THE KEYBOARD GESTURE, and this is the regression the review round found.
      Tab out (blur advances), then Enter or Space on the focused button —
      which dispatches a click. Without a keyboard disarm the one-shot from
      step 4 swallowed it and the learner pressed a control that did nothing. */
for (const key of ["Enter", " "]) {
    b = bridge(STEPS);
    blurTo(b, el(FIELD, "INPUT", "1.200.000"));      // Tab: no mousedown
    const btn = el(NEXT, "BUTTON");
    press(b, btn, key);                              // keyboard activation…
    b._scenarioClick({ target: btn });               // …dispatches a click
    check("type, Tab, then " + JSON.stringify(key) + " on the next control: two advances",
          b.advances === 2 && b.state.sStep === 2, "advances=" + b.advances);
}

/* 6. A WRONG CONTROL IS A NUDGE, never a silent no-op and never an advance. */
b = bridge(STEPS);
b.state.sStep = 1;                                   // the click step
click(b, el("iw-review", "BUTTON"));
check("clicking the wrong control nudges and does not advance",
      b.advances === 0 && b.state.sNudge === true, "advances=" + b.advances);
b = bridge(STEPS);
b.state.sStep = 1;
click(b, el(NEXT, "BUTTON"));
check("clicking the right control on a click step advances once",
      b.advances === 1 && b.state.sNudge === false, "advances=" + b.advances);

/* 7. AN EMPTY FIELD IS NOT A WRONG ANSWER. Blurring one nobody typed in must
      not put a correction on the screen for doing nothing. */
b = bridge(STEPS);
blurTo(b, el(FIELD, "INPUT", "   "));
check("blurring an untouched field says nothing",
      b.advances === 0 && b.state.sMiss === false, "miss=" + b.state.sMiss);

console.log("  try bridge -> " + ok + " pass, 0 skip, " + bad + " fail");
process.exit(bad ? 1 : 0);
"""


def bridge_checks():
    """Execute the LIFTED click bridge through whole gestures."""
    print("== try bridge (lifted from journey.js)")
    tmp = tempfile.mkdtemp(prefix="pblearn-bridge-")
    ok = failed = 0
    try:
        for name in sorted(os.listdir(JS_ENGINE)):
            if not name.endswith(".js"):
                continue
            src = open(os.path.join(JS_ENGINE, name), encoding="utf-8").read()
            src = re.sub(r'(from\s+")(\./[A-Za-z0-9_./-]+?)(")',
                         lambda m: m.group(1) + m.group(2) + ".mjs" + m.group(3), src)
            open(os.path.join(tmp, name[:-3] + ".mjs"), "w", encoding="utf-8").write(src)
        methods = _lift_js_methods(
            os.path.join(REPO, "pb_learn/static/src/journey/journey.js"),
            BRIDGE_METHODS)
        body = "const METHODS = {\n%s\n};\n" % ",\n".join(
            m.replace("    ", "", 1) for m in
            (methods[n] for n in BRIDGE_METHODS))
        suite = os.path.join(tmp, "_bridge.mjs")
        # METHODS is DECLARED FIRST. `const` is hoisted but not initialised, so
        # a suite that used it before its declaration threw a TDZ error and
        # reported one PASS and a crash — which is exactly the "found nothing
        # means broken, not passing" shape, one language over.
        open(suite, "w", encoding="utf-8").write(
            BRIDGE_IMPORTS + body + BRIDGE_SUITE)
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
            print("    FAIL  the bridge suite did not run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok, 0, failed


TOTAL = [0, 0, 0]
for addon, pkgname, modname, clsname in (
    ("pb_learn", "pb_learn_tests", "test_scenario", "TestScenarioEngine"),
    # LEARNOS Phase 5 — the sandbox's two structural promises. Both are source
    # facts, so both execute here; the watermark is ALSO executed for real
    # against all twenty replicas in the JS suite below.
    ("pb_learn", "pb_learn_tests", "test_practice", "TestPracticeMode"),
    ("pb_learn", "pb_learn_tests", "test_retirement", "TestRetirementSeams"),
    ("pb_learn", "pb_learn_tests", "test_anchor_registry", "TestAnchorRegistry"),
    ("pb_learn", "pb_learn_tests", "test_assets", "TestAssets"),
    # LEARNOS Phase 3.
    ("pb_learn", "pb_learn_tests", "test_welcome", "TestWelcomeCard"),
    # LEARNOS Phase 6. The decision table and the streak are pure functions
    # for exactly this: every rule, every tie and every time-zone edge runs
    # here, on a machine with no odoo-bin.
    ("pb_learn", "pb_learn_tests", "test_nextbest", "TestNextBest"),
    # LEARNOS Phase 4. `explain_blocks`, `build_corpus` and both prompt
    # builders are pure over the content tree, so the floor really is replayed
    # here for three screens in both languages rather than only described.
    ("pb_learn", "pb_learn_tests", "test_explain", "TestExplainScreen"),
    ("pb_dashboard", "pb_dashboard_tests", "test_activation", "TestActivationSource"),
    ("pb_dashboard", "pb_dashboard_tests", "test_activation", "TestActivationPayload"),
    ("pb_tenants", "pb_tenants.tests", "test_currency", "TestProvisioningCurrency"),
    # LEARNOS Phase 4 — the egress suite. `TestAiRedaction` is the one that
    # asserts on the exact prompt string, so it is the one that must never be
    # a test nobody has run.
    ("pb_payroll_ai_insights", "pb_payai_tests", "test_redaction",
     "TestAiRedaction"),
    ("pb_payroll_ai_insights", "pb_payai_tests", "test_egress",
     "TestEgressSeams"),
):
    print("== %s.%s" % (addon, modname))
    r = run(modname, clsname, addon, pkgname)
    for i in range(3):
        TOTAL[i] += r[i]

r = js_checks()
for i in range(3):
    TOTAL[i] += r[i]

r = bridge_checks()
for i in range(3):
    TOTAL[i] += r[i]

print("\nTOTAL: %d pass, %d skip, %d fail" % tuple(TOTAL))
sys.exit(1 if TOTAL[2] else 0)
