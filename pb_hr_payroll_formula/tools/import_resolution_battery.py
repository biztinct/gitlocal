#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP-E import-resolution regression battery.

Runs the REAL import-wizard resolution, code-generation and preview-diagnosis
functions (odoo shimmed) against crafted inputs — no server or DB needed.
Guards the WP-E fixes: anchored cross-sheet regex (no formula shredding),
#REF! markers instead of silent 0, C5-safe code generation, and the
positional-lookup / cross-row warnings. Run after any change to
wizards/multisheet_import_wizard.py or multisheet_import_preview.py.

    python3 pb_hr_payroll_formula/tools/import_resolution_battery.py

Exit 0 = green. Provides its own minimal odoo shim (no odoo install needed).
"""
import sys, os, types, logging, re, html as _html

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODULE = os.path.join(REPO, 'pb_hr_payroll_formula')
WIZ = os.path.join(MODULE, 'wizards', 'multisheet_import_wizard.py')
PREV = os.path.join(MODULE, 'wizards', 'multisheet_import_preview.py')
sys.path.insert(0, os.path.join(MODULE, 'formula_engine'))


def _passthrough(*a, **k):
    if len(a) == 1 and callable(a[0]) and not k:
        return a[0]
    return lambda fn: fn


def install_odoo_shim():
    odoo = types.ModuleType('odoo')
    odoo.__path__ = []
    api = types.ModuleType('odoo.api')
    for n in ('depends', 'depends_context', 'model', 'model_create_multi',
              'onchange', 'constrains', 'autovacuum', 'ondelete', 'returns'):
        setattr(api, n, _passthrough)

    class _F:
        def __init__(self, *a, **k):
            pass

    class _DT(_F):
        @staticmethod
        def now():
            import datetime; return datetime.datetime(2026, 1, 1)

    fields = types.ModuleType('odoo.fields')
    for n in ('Char', 'Text', 'Html', 'Boolean', 'Integer', 'Float', 'Monetary',
              'Selection', 'Many2one', 'One2many', 'Many2many', 'Binary', 'Date',
              'Json', 'Reference'):
        setattr(fields, n, _F)
    fields.Datetime = _DT
    models = types.ModuleType('odoo.models')
    models.Model = type('Model', (), {})
    models.TransientModel = type('TransientModel', (), {})
    models.AbstractModel = type('AbstractModel', (), {})
    exceptions = types.ModuleType('odoo.exceptions')
    exceptions.UserError = type('UserError', (Exception,), {})
    exceptions.ValidationError = type('ValidationError', (Exception,), {})
    tools = types.ModuleType('odoo.tools')
    tools.html_escape = lambda s: _html.escape(str(s))
    odoo.api, odoo.fields, odoo.models = api, fields, models
    odoo.exceptions, odoo.tools = exceptions, tools
    odoo._ = lambda s, *a: s % a if a else s
    for k, m in (('odoo', odoo), ('odoo.api', api), ('odoo.fields', fields),
                 ('odoo.models', models), ('odoo.exceptions', exceptions),
                 ('odoo.tools', tools)):
        sys.modules[k] = m


def install_markupsafe_shim():
    """The wizard imports `markupsafe` for its preview HTML. It ships with Odoo but
    not with a bare interpreter, and without it this battery cannot import the file
    it exists to test — so a faithful-enough stand-in is provided rather than making
    the gate depend on the developer's site-packages."""
    try:
        import markupsafe  # noqa: F401
        return
    except ImportError:
        pass
    ms = types.ModuleType('markupsafe')

    class Markup(str):
        def __add__(self, other):
            return Markup(str.__add__(self, other))

        def __mod__(self, other):
            return Markup(str.__mod__(self, other))

        def join(self, seq):
            return Markup(str.join(self, seq))

        def format(self, *a, **k):
            return Markup(str.format(self, *a, **k))

    ms.Markup = Markup
    ms.escape = lambda s: Markup(_html.escape(str(s)))
    ms.escape_silent = ms.escape
    sys.modules['markupsafe'] = ms


install_odoo_shim()
install_markupsafe_shim()
logging.disable(logging.CRITICAL)

# We only want the two methods' logic, not Odoo model machinery. Extract the
# source of the functions we need and exec them onto a bare host object.
wiz_src = open(WIZ, encoding='utf-8').read()
prev_src = open(PREV, encoding='utf-8').read()

# Provide excel_semantics for the wizard's import (already shimmed path).
sys.path.insert(0, REPO + '/pb_hr_payroll_formula/formula_engine')

def load_module(path, name, inject=None):
    # Build a throwaway module exposing the class methods by exec'ing the file
    # with odoo shimmed. The file imports `from ..formula_engine import
    # excel_semantics` — provide a fake package.
    pkg = types.ModuleType('fakepkg')
    pkg.__path__ = []
    fe = types.ModuleType('fakepkg.formula_engine')
    import excel_semantics as _es
    import if_chain as _ic
    fe.excel_semantics = _es
    fe.if_chain = _ic
    sys.modules['fakepkg'] = pkg
    sys.modules['fakepkg.formula_engine'] = fe
    # The wizard also reaches sideways into `..models` for the plain-Python
    # classifier and the shared code generator. Both are stdlib-only, so they are
    # loaded from source rather than stubbed — the code generator in particular is
    # exactly what the code-generation cases below are testing.
    models_pkg = types.ModuleType('fakepkg.models')
    models_pkg.__path__ = []
    models_dir = os.path.join(MODULE, 'models')
    import importlib.util as _ilu
    for mod_name in ('column_role_classifier', 'component_code'):
        mod_path = os.path.join(models_dir, mod_name + '.py')
        mod_src = open(mod_path, encoding='utf-8').read().replace(
            'from .column_role_classifier import', 'from column_role_classifier import')
        mod = types.ModuleType(mod_name)
        mod.__dict__['__name__'] = mod_name
        sys.modules[mod_name] = mod
        exec(compile(mod_src, mod_path, 'exec'), mod.__dict__)
        setattr(models_pkg, mod_name, mod)
        sys.modules['fakepkg.models.' + mod_name] = mod
    sys.modules['fakepkg.models'] = models_pkg
    src = open(path, encoding='utf-8').read()
    src = src.replace('from ..formula_engine import excel_semantics',
                      'from fakepkg.formula_engine import excel_semantics')
    src = src.replace('from ..formula_engine import if_chain',
                      'from fakepkg.formula_engine import if_chain')
    src = src.replace('from ..models import', 'from fakepkg.models import')
    g = {'__name__': name, '__package__': 'fakepkg'}
    exec(compile(src, path, 'exec'), g)
    return g

wiz_g = load_module(WIZ, 'wiz')
prev_g = load_module(PREV, 'prev')

WizCls = wiz_g['MultiSheetImportWizard'] if 'MultiSheetImportWizard' in wiz_g else None
if WizCls is None:
    # find the class defining _resolve_cross_sheet_formula
    for k, v in wiz_g.items():
        if isinstance(v, type) and hasattr(v, '_resolve_cross_sheet_formula'):
            WizCls = v; break
PrevCls = None
for k, v in prev_g.items():
    if isinstance(v, type) and hasattr(v, '_diagnose'):
        PrevCls = v; break

print("WizCls:", WizCls.__name__, "PrevCls:", PrevCls.__name__)

# Build a bare instance (bypass Odoo __init__) with just what the methods touch.
wiz = object.__new__(WizCls)
prev = object.__new__(PrevCls)

fails = []
def check(name, got, expected):
    ok = got == expected
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got!r} exp={expected!r}")
    if not ok:
        fails.append(name)

# ---- D-E2: direct-ref anchoring + D-E1: #REF! preservation ----
# column_mapping keyed by (normalized_sheet, col_letter or index)
cm = {
    ('sheet2', 'B'): 'BONUS',
    ('sheet2', 1): 'BONUS',
    ('rates', 'C'): 'TAXRATE',
    ('lương', 'A'): 'LUONG',
}
def resolve(formula):
    return wiz._resolve_cross_sheet_formula(formula, cm)

# resolvable ref inside a function must NOT be shredded (the headline bug)
check('direct-in-IF-resolves', resolve('=IF(Sheet2!B2>0,1,0)'), '=IF(BONUS>0,1,0)')
# unresolvable sheet → #REF!, formula NOT shredded into 0>0,1,0)
check('direct-unresolved-REF', resolve('=IF(Nope!B2>0,1,0)'), '=IF(#REF!>0,1,0)')
# unicode unquoted sheet resolves
check('unicode-sheet', resolve('=Lương!A2+1'), '=LUONG+1')
# quoted sheet with space resolves (rates)
check('quoted-space', resolve("='Rates'!C2*2"), '=TAXRATE*2')
# plain arithmetic untouched
check('no-xref', resolve('=A2*B2+3'), '=A2*B2+3')
# two refs, one resolves one doesn't
check('mixed', resolve('=Sheet2!B2+Zzz!C9'), '=BONUS+#REF!')

# ---- D-E3: code generation (C5: underscore-free, non-substring) ----
def gen(header, existing):
    s = set(existing)
    return wiz._generate_code(header, s)

check('code-basic', gen('Basic Salary', []), 'BASICSALARY')
check('code-numeric-header', gen('2024', []), 'COL2024')
check('code-formula-header', gen('=A1+B1', []), 'FORMULACOL')
# HARD guarantee: a duplicate of an existing code is underscore-free AND unique.
c = gen('Amount', {'AMOUNT'})
check('code-dup-nounderscore', '_' not in c, True)
check('code-dup-unique', c != 'AMOUNT' and c not in {'AMOUNT'}, True)
# COSMETIC preference: when a short suffix CAN escape substring collision it is
# taken (Tax vs TAXRATE — base != existing, so achievable).
c2 = gen('Tax', {'TAXRATE'})
check('code-substring-avoided-when-possible', (c2 not in 'TAXRATE' and 'TAXRATE' not in c2), True)
check('code-substring-nounderscore', '_' not in c2, True)
# When it's IMPOSSIBLE (base == existing), we still return underscore-free +
# unique (substring is tolerated — the greedy converter resolves it correctly).
c3 = gen('Amount', {'AMOUNT'})
check('code-impossible-substring-still-unique', ('_' not in c3 and c3 != 'AMOUNT'), True)

# ---- diagnose (D-E1/D-E6/D-E7) ----
def diag(o, r):
    return prev._diagnose(o, r)[0:2]

check('diag-ref-broken', diag('=Sheet2!B2', '=#REF!'), ('broken', 'becomes_zero'))
check('diag-clean-ok', diag('=A2+B2', '=BONUS+3'), ('ok', False))
check('diag-vlookup-warn', diag("=VLOOKUP(B2,'R'!A:C,3,0)", '=TAXRATE')[0], 'warning')
check('diag-rowoffset-warn', diag('=B5+B4', '=BONUS+BONUS')[0], 'warning')
check('diag-surviving-xref', diag("=X", "='Sheet'!A1")[0], 'broken')

# ---- W40 diff re-import: constant-value change detection (review fix M1) ----
# A changed statutory constant (8% -> 9%) carries its value in constant_value,
# not excel_formula, so a formula-only diff would call it "unchanged" while the
# commit still writes it — a payroll change bypassing officer review.
rd_g = load_module(os.path.join(MODULE, 'wizards', 'multisheet_reimport_diff.py'), 'rd')
RdCls = next(v for v in rd_g.values()
             if isinstance(v, type) and hasattr(v, '_rd_constant_change'))
rd = object.__new__(RdCls)


class _P:
    def __init__(self, sv):
        self.sample_value = sv


class _R:
    def __init__(self, cv):
        self.constant_value = cv


check('reimport-const-8to9-changed', rd._rd_constant_change(_P('9%'), _R(0.08))[0], True)
check('reimport-const-8to9-newval', rd._rd_constant_change(_P('9%'), _R(0.08))[2], '0.09')
check('reimport-const-same-unchanged', rd._rd_constant_change(_P('0.08'), _R(0.08))[0], False)
check('reimport-const-cap-intfmt', rd._rd_constant_change(_P('46800000'), _R(46800000.0))[2], '46800000')

print(f"\nRESULT: {'ALL GREEN' if not fails else str(len(fails)) + ' FAILURES: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
