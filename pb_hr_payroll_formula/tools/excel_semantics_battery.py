#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Excel-semantics regression battery for the formula conversion engine.

Runs the REAL `_convert_excel_to_python` + `_run_formula` code (and the
FormulaEvaluator secondary path) against a battery of Excel formulas with
hand-computed Excel-expected results — no Odoo server or database needed
(odoo is shimmed out, the module files are imported from this repo).

Usage:
    python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py

Exit code 0 = all green. Run this after ANY change to
models/formula_rule.py (converter/helpers) or formula_engine/evaluator.py /
excel_semantics.py — it is the regression gate for Excel-vs-engine
correctness (see docs/FORMULA_ENGINE_CONVENTIONS.md, C12).
"""
import logging
import os
import sys
import types

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODULE_DIR = os.path.join(REPO_ROOT, 'pb_hr_payroll_formula')


# ---------------------------------------------------------------------------
# Odoo shim — lets the real formula_rule.py import untouched
# ---------------------------------------------------------------------------

def _passthrough_decorator(*a, **kw):
    if len(a) == 1 and callable(a[0]) and not kw:
        return a[0]

    def deco(fn):
        return fn
    return deco


def install_odoo_shim():
    odoo = types.ModuleType('odoo')
    api = types.ModuleType('odoo.api')
    for name in ('depends', 'depends_context', 'model', 'model_create_multi',
                 'onchange', 'constrains', 'autovacuum', 'ondelete', 'returns'):
        setattr(api, name, _passthrough_decorator)

    class _Field:
        def __init__(self, *a, **kw):
            pass

    class _DatetimeField(_Field):
        @staticmethod
        def now():
            import datetime
            return datetime.datetime(2026, 1, 1)

        @staticmethod
        def today():
            import datetime
            return datetime.date(2026, 1, 1)

    fields = types.ModuleType('odoo.fields')
    for name in ('Char', 'Text', 'Html', 'Boolean', 'Integer', 'Float',
                 'Monetary', 'Selection', 'Many2one', 'One2many', 'Many2many',
                 'Binary', 'Date', 'Json', 'Reference'):
        setattr(fields, name, _Field)
    fields.Datetime = _DatetimeField

    models = types.ModuleType('odoo.models')
    models.Model = type('Model', (), {})
    models.TransientModel = type('TransientModel', (), {})
    models.AbstractModel = type('AbstractModel', (), {})
    # Odoo 19 constraints are class attributes (`models.Constraint(...)`, C9);
    # formula_rule.py carries several — the shim must accept them as no-ops.
    models.Constraint = lambda *a, **k: None

    exceptions = types.ModuleType('odoo.exceptions')
    exceptions.UserError = type('UserError', (Exception,), {})
    exceptions.ValidationError = type('ValidationError', (Exception,), {})

    odoo.api, odoo.fields, odoo.models, odoo.exceptions = api, fields, models, exceptions
    odoo._ = lambda s, *a: s % a if a else s
    for key, mod in (('odoo', odoo), ('odoo.api', api), ('odoo.fields', fields),
                     ('odoo.models', models), ('odoo.exceptions', exceptions)):
        sys.modules[key] = mod


def install_fake_package():
    """Synthetic `pbf` package pointing at the real module dirs, so the
    relative imports inside formula_rule.py resolve WITHOUT running the
    formula_engine package __init__ (which pulls openpyxl-heavy modules)."""
    pbf = types.ModuleType('pbf')
    pbf.__path__ = []
    fe = types.ModuleType('pbf.formula_engine')
    fe.__path__ = [os.path.join(MODULE_DIR, 'formula_engine')]
    mdl = types.ModuleType('pbf.models')
    mdl.__path__ = [os.path.join(MODULE_DIR, 'models')]
    sys.modules['pbf'] = pbf
    sys.modules['pbf.formula_engine'] = fe
    sys.modules['pbf.models'] = mdl


install_odoo_shim()
install_fake_package()
logging.disable(logging.CRITICAL)

import importlib  # noqa: E402
fr_mod = importlib.import_module('pbf.models.formula_rule')
evaluator_mod = importlib.import_module('pbf.formula_engine.evaluator')
FormulaEvaluator = evaluator_mod.FormulaEvaluator

RuleCls = None
for _name in dir(fr_mod):
    _obj = getattr(fr_mod, _name)
    if isinstance(_obj, type) and hasattr(_obj, '_convert_excel_to_python'):
        RuleCls = _obj
        break
assert RuleCls, "formula rule class not found"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeCol:
    def __init__(self, letter, code):
        self.column_letter = letter
        self.code = code


class FakeConfig:
    def __init__(self, cols):
        self.rule_ids = cols


COLS = [
    FakeCol('A', 'BASE'), FakeCol('B', 'DAYS'), FakeCol('C', 'OT'),
    FakeCol('D', 'GRADE'), FakeCol('E', 'ALW'), FakeCol('F', 'REGION'),
    FakeCol('G', 'BONUS'), FakeCol('H', 'RATE'),
]
CONFIG = FakeConfig(COLS)
COLUMN_MAP = {c.column_letter: c.code for c in COLS}
BASE_VALUES = {
    'BASE': 100, 'DAYS': 2, 'OT': 3, 'GRADE': 'HN',
    'ALW': 50, 'REGION': 1, 'BONUS': 0, 'RATE': 1.5,
}
REMOVE = object()


def make_rule(formula, code='TEST'):
    r = object.__new__(RuleCls)
    r.code = code
    r.column_type = 'formula'
    r.excel_formula = formula
    r.config_id = CONFIG
    r.has_evaluation_error = False
    r.ensure_one = lambda: None
    return r


def build_values(override=None):
    v = dict(BASE_VALUES)
    if override:
        for k, val in override.items():
            if val is REMOVE:
                v.pop(k, None)
            else:
                v[k] = val
    for col in COLS:  # production mirrors values under column letters too
        if col.code in v:
            v[col.column_letter] = v[col.code]
    return v


# (id, excel formula, value overrides, excel-expected, note)
# "<CONVERT-FAIL>" = the converter must REFUSE loudly (ValueError), never
# emit silently-wrong code.
CASES = [
    ("arith",        "=A1*B1+C1", None, 203, "baseline"),
    ("paren",        "=(A1+B1)*2", None, 204, ""),
    ("unary-minus",  "=-A1+5", None, -95, ""),
    ("pct-int",      "=A1*8%", None, 8.0, ""),
    ("pct-dec",      "=A1*8.5%", None, 8.5, ""),
    ("if-eq",        "=IF(B1=2,10,20)", None, 10, ""),
    ("if-neq<>",     "=IF(B1<>2,10,20)", None, 20, "Excel <> operator"),
    ("neq-str<>",    '=IF(D1<>"",1,0)', None, 1, "<> vs empty string"),
    ("if-ge",        "=IF(B1>=2,1,0)", None, 1, ""),
    ("if-nested",    "=IF(A1>50,IF(B1>1,5,6),7)", None, 5, ""),
    ("if-divguard0", "=IF(B1=0,0,A1/B1)", {'DAYS': 0}, 0, "guard, zero branch"),
    ("if-divguardX", "=IF(B1=0,999,A1/B1)", {'DAYS': 0}, 999, "lazy IF branch"),
    ("iferror-div",  "=IFERROR(A1/B1,999)", {'DAYS': 0}, 999, "IFERROR catches #DIV/0!"),
    ("round-half",   "=ROUND(2.5,0)", None, 3, "half away from zero"),
    ("round-half2",  "=ROUND(100.5,0)", None, 101, ""),
    ("round-neg",    "=ROUND(12500,-3)", None, 13000, "negative digits"),
    ("roundup-neg",  "=ROUNDUP(-1.2,0)", None, -2, "away from zero"),
    ("rounddn-neg",  "=ROUNDDOWN(-1.8,0)", None, -1, "toward zero"),
    ("roundup-pos",  "=ROUNDUP(1.2,0)", None, 2, ""),
    ("ceiling-sig",  "=CEILING(A1+47,100)", None, 200, "significance arg"),
    ("floor-sig",    "=FLOOR(147,100)", None, 100, "significance arg"),
    ("caret-pow",    "=A1^2", None, 10000, "Excel ^ (Python ^ is XOR!)"),
    ("power-fn",     "=POWER(A1,2)", None, 10000, ""),
    ("sqrt-abs",     "=SQRT(ABS(-4))", None, 2, ""),
    ("concat-amp",   '="VN"&"1"', None, "<CONVERT-FAIL>", "& unsupported -> loud"),
    ("true-lit",     "=IF(A1>50,TRUE,FALSE)", None, 1, "TRUE literal"),
    ("and-fn",       "=IF(AND(A1>50,B1>1),1,0)", None, 1, ""),
    ("or-fn",        "=IF(OR(A1>500,B1>1),1,0)", None, 1, ""),
    ("not-fn",       "=NOT(A1>50)", None, 0, ""),
    ("not-mult",     "=NOT(A1>500)*5", None, 5, "NOT call precedence"),
    ("isblank",      "=IF(ISBLANK(G1),1,0)", {'BONUS': ''}, 1, "raw-value ISBLANK"),
    ("str-eq",       '=IF(D1="HN",1,0)', None, 1, ""),
    ("str-eq-case",  '=IF(D1="HN",1,0)', {'GRADE': 'hn'}, 1, "case-insensitive"),
    ("str-empty",    '=IF(D1="",1,0)', {'GRADE': REMOVE}, 1, ""),
    ("sum-range",    "=SUM(A1:C1)", None, 105, ""),
    ("sum-cols",     "=SUM(A:C)", None, 105, ""),
    ("sum-coderange", "=SUM(BASE:OT)", None, 105, ""),
    ("sum-two",      "=SUM(A1:C1)+SUM(A1:B1)", None, 207, "double bracket fix"),
    ("max-2arg",     "=MAX(A1,B1)", None, 100, ""),
    ("min-3arg",     "=MIN(A1,B1,C1)", None, 2, ""),
    ("max-nested-if", "=MAX(A1,IF(B1>1,500,0))", None, 500, "nested fn in list arg"),
    ("code-mixed",   "=BASE*0.1+B1", None, 12, "code + letter refs"),
    ("abs-ref",      "=$A$1*2", None, 200, ""),
    ("redundant-par", "=(B1)", None, 2, ""),
    ("div-prec",     "=A1/B1*C1", None, 150, ""),
    ("if-pct",       "=IF(B1>1.5,A1*75%,A1*50%)", None, 75, ""),
    ("bool-mult",    "=(A1>50)*10", None, 10, ""),
    ("round-div",    "=ROUND(A1/3,2)", None, 33.33, ""),
    ("average",      "=AVERAGE(A1:C1)", {'OT': 0}, 34, "AVERAGE includes zeros"),
    ("str-then",     '=IF(D1="HN","Hanoi","Other")', None, "Hanoi", "string result"),
    ("vlookup-ss",   "=VLOOKUP(D1,$A$1:$C$1,3,0)", None, 3, "same-sheet heuristic"),
    ("mod",          "=MOD(A1,30)", None, 10, ""),
    ("sign-neg",     "=SIGN(B1-10)", None, -1, ""),
    ("abs-cellref",  "=ABS(A1)", None, 100, "one-arg fn paren-mangle fix"),
    ("sum-onecell",  "=SUM(A1)", None, 100, "one-arg fn paren-mangle fix"),
    ("isblank-ref",  "=IF(ISBLANK(D1),1,0)", {'GRADE': REMOVE}, 1, "paren-mangle fix"),
    ("iferror-fb",   "=IFERROR(SUM(A1:C1)/B1,7)", {'DAYS': 0}, 7, "lazy IFERROR"),
    ("iferror-ok",   "=IFERROR(A1/B1,7)", None, 50, "IFERROR passthrough"),
    ("if-2arg",      "=IF(A1>50,7)", None, 7, "IF without else"),
    ("if-monster",   "=IF(F1=1,IF(B1>1,A1/B1,0),MAX(A1*0.5,B1))", None, 50, "nested lazy IF"),
    ("if-strcomma",  '=IF(D1="HN","Ha Noi, VN","Other")', None, "Ha Noi, VN", "comma in literal"),
    ("caret-b3",     "=B1^3", None, 8, "^ to **"),
    ("true-mult",    "=IF(A1>50,TRUE,FALSE)*5", None, 5, "TRUE arithmetic"),
    ("streq-trim",   '=IF(D1="CT",1,0)', {'GRADE': ' ct '}, 1, "trim + case-insensitive"),
    ("roundup-dec",  "=ROUNDUP(1.2,1)", None, 1.2, "no float-artifact bump"),
    ("round-prod",   "=ROUND(A1*0.105,0)", None, 11, "10.5 away from zero"),
    ("guard-env",    "=self.env['res.users']", None, 0, "forbidden token blocked"),
    ("amp-loud",     '="A"&B1', None, "<CONVERT-FAIL>", "& must fail loudly"),
    ("live-shape",   '=ROUND(IF(D1="x",(A1+E1)*H1,0),0)', {'GRADE': 'x'}, 225, "live BHXH shape"),
    ("live-advrate", "=ROUND(A1*IF(A1+E1>=120,H1/10,H1/15))", None, 15, "demo ADVPAY shape"),
]

SEC_CASES = [
    ("ev-arith", "=A1*B1+C1", None, 203, ""),
    ("ev-average-zero", "=AVERAGE(A1:C1)", {'OT': 0}, 34, "shared avg includes zeros"),
    ("ev-numstr", "=A1*2", {'BASE': '100'}, 200, "shared numeric-string coercion"),
    ("ev-if-divguardX", "=IF(B1=0,999,A1/B1)", {'DAYS': 0}, 999, "lazy ternary"),
    ("ev-str-eq", '=IF(D1="HN",1,0)', None, 1, "self._streq resolves"),
    ("ev-iferror", "=IFERROR(A1/B1,7)", {'DAYS': 0}, 7, "lambda IFERROR"),
    ("ev-round", "=ROUND(2.5,0)", None, 3, "shared excel_round"),
    ("ev-live", '=ROUND(IF(D1="x",(A1+E1)*H1,0),0)', {'GRADE': 'x'}, 225, "live shape"),
]


def close(a, b):
    if isinstance(b, str):
        return a == b
    try:
        return abs(float(a) - float(b)) < 1e-9
    except Exception:
        return False


def main():
    fails = []
    print(f"Primary path battery over {fr_mod.__file__}")
    for cid, formula, over, expected, note in CASES:
        rule = make_rule(formula)
        values = build_values(over)
        try:
            converted = rule._convert_excel_to_python(
                formula[1:] if formula.startswith('=') else formula, COLUMN_MAP)
        except Exception as e:
            converted = f"<CONVERT ERROR: {e}>"
        try:
            got = rule._run_formula(values, formula, write_diagnostics=False)
        except Exception as e:
            got = f"<RAISED {type(e).__name__}: {e}>"
        if expected == "<CONVERT-FAIL>":
            ok = isinstance(converted, str) and converted.startswith("<CONVERT ERROR")
        else:
            ok = close(got, expected)
        if not ok:
            fails.append((cid, formula, expected, got, converted, note))
        print(f"[{'PASS' if ok else 'FAIL'}] {cid:15s} {formula!r:45s} "
              f"expected={expected!r} got={got!r}")
    print(f"\n{len(CASES) - len(fails)}/{len(CASES)} passed on primary path")
    for cid, formula, expected, got, converted, note in fails:
        print(f"\n* {cid} ({note})\n  excel   : {formula}\n  python  : {converted}"
              f"\n  expected: {expected!r}\n  got     : {got!r}")

    print("\nSecondary path: FormulaEvaluator.evaluate_single")
    ev = FormulaEvaluator()
    sec_fails = 0
    for cid, formula, over, expected, note in SEC_CASES:
        rule = make_rule(formula)
        values = build_values(over)
        try:
            converted = rule._convert_excel_to_python(formula[1:], COLUMN_MAP)
            got = ev.evaluate_single(converted, values)
        except Exception as e:
            got = f"<RAISED {type(e).__name__}: {e}>"
        ok = close(got, expected)
        sec_fails += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {cid:18s} {formula!r:38s} "
              f"expected={expected!r} got={got!r}  {note}")

    total_fail = len(fails) + sec_fails
    print(f"\nRESULT: {'ALL GREEN' if not total_fail else f'{total_fail} FAILURES'}")
    return 1 if total_fail else 0


if __name__ == '__main__':
    sys.exit(main())
