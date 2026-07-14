#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WP-J / W42 offline check — exercises the REAL preview-mixin promotion logic
(_build_rate_proposals + _apply_rate_table_promotions) on a stubbed wizard, with
odoo shimmed. call_kw cannot reach these private methods over JSON-RPC, so this
is the deterministic gate for the accept / decline paths and the staged-text
rewrite. The shared detector + BRACKET compile path are separately proven live
(W54 apply) and by if_chain_battery.

    python3 pb_hr_payroll_formula/tools/w42_promotion_check.py

Exit 0 = green.
"""
import os, sys, types

MODULE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PREV = os.path.join(MODULE, 'wizards', 'multisheet_import_preview.py')
sys.path.insert(0, os.path.join(MODULE, 'formula_engine'))

PIT = ("=-MAX(0,IF(AP2<=0,0,IF(AP2<=5000000,AP2*0.05,"
       "IF(AP2<=10000000,AP2*0.1-250000,IF(AP2<=18000000,AP2*0.15-750000,"
       "IF(AP2<=32000000,AP2*0.2-1650000,IF(AP2<=52000000,AP2*0.25-3250000,"
       "IF(AP2<=80000000,AP2*0.3-5850000,AP2*0.35-9850000))))))))")
PLAIN = "=BASIC*0.1+ALLOW"   # not a chain — must NOT be proposed


def _passthrough(*a, **k):
    if len(a) == 1 and callable(a[0]) and not k:
        return a[0]
    return lambda fn: fn


def install_shim():
    odoo = types.ModuleType('odoo'); odoo.__path__ = []
    api = types.ModuleType('odoo.api')
    for n in ('model', 'depends', 'onchange', 'constrains', 'model_create_multi'):
        setattr(api, n, _passthrough)
    fields = types.ModuleType('odoo.fields')
    for n in ('Char', 'Text', 'Integer', 'Float', 'Boolean', 'Many2one',
              'One2many', 'Html', 'Selection'):
        setattr(fields, n, lambda *a, **k: None)
    models = types.ModuleType('odoo.models')
    models.TransientModel = type('TransientModel', (), {})
    models.Model = type('Model', (), {})
    exceptions = types.ModuleType('odoo.exceptions')
    exceptions.UserError = type('UserError', (Exception,), {})
    tools = types.ModuleType('odoo.tools'); tools.html_escape = lambda s: str(s)
    odoo.api, odoo.fields, odoo.models = api, fields, models
    odoo.exceptions, odoo.tools = exceptions, tools
    odoo._ = lambda s, *a: (s % a if a else s)
    for k, m in (('odoo', odoo), ('odoo.api', api), ('odoo.fields', fields),
                 ('odoo.models', models), ('odoo.exceptions', exceptions),
                 ('odoo.tools', tools)):
        sys.modules[k] = m


install_shim()

# fake package so `from ..formula_engine import if_chain` resolves
pkg = types.ModuleType('fakepkg'); pkg.__path__ = []
fe = types.ModuleType('fakepkg.formula_engine')
import if_chain as _ic
fe.if_chain = _ic
sys.modules['fakepkg'] = pkg
sys.modules['fakepkg.formula_engine'] = fe
src = open(PREV, encoding='utf-8').read().replace(
    'from ..formula_engine import if_chain', 'from fakepkg.formula_engine import if_chain')
g = {'__name__': 'prev', '__package__': 'fakepkg'}
exec(compile(src, PREV, 'exec'), g)
Mixin = next(v for v in g.values()
             if isinstance(v, type) and hasattr(v, '_apply_rate_table_promotions'))


# ---- minimal fakes -----------------------------------------------------------
class Rec(list):
    """A list that also filters like a recordset and unlink()s in place."""
    def filtered(self, fn):
        if isinstance(fn, str):
            return Rec(x for x in self if getattr(x, fn))
        return Rec(x for x in self if fn(x))
    def unlink(self):
        self[:] = []
    def __getitem__(self, i):
        r = super().__getitem__(i)
        return Rec(r) if isinstance(i, slice) else r
    def __getattr__(self, name):
        # a length-1 Rec behaves like an Odoo singleton recordset
        if len(self) == 1:
            return getattr(self[0], name)
        raise AttributeError(name)


class Comp:
    def __init__(self, code, formula, letter=None):
        self.generated_code = code
        self.generated_name = code.title()
        self.column_type = 'formula'
        self.excel_formula = formula
        self.resolved_formula = formula
        self.column_letter = letter
    def write(self, vals):
        for k, v in vals.items():
            setattr(self, k, v)


class Prop:
    _store = None
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class Table:
    made = []
    def __init__(self, vals):
        self.vals = vals
        self.code = vals['code']
        Table.made.append(self)


class Env:
    def __init__(self):
        self._t = types.SimpleNamespace(create=lambda vals: Table(vals))
        self._p = types.SimpleNamespace(create=self._prop_create)
        self.props = Rec()
    def _prop_create(self, vals_list):
        for v in vals_list:
            self.props.append(Prop(**v))
        return self.props
    def __getitem__(self, name):
        return {'hr.formula.rate.table': self._t,
                'hr.formula.import.rate.proposal': self._p}[name]


class Config:
    def __init__(self):
        self.id = 1
        self.rate_table_ids = Rec()
        self.rule_ids = Rec()


class FakeWizard(Mixin):
    def __init__(self, comps):
        self.id = 1
        self.env = Env()
        self.config_id = Config()
        self.component_preview_ids = Rec(comps)
        self.rate_proposal_ids = self.env.props
    # real staticmethod from the base wizard would live on the MRO; supply the
    # genuine C5 deduper behaviour (letters-only, unique) inline for the stub.
    @staticmethod
    def _dedupe_code_c5(base, existing):
        import string
        if base not in existing:
            return base
        for s in [''] + list(string.ascii_uppercase):
            if base + s not in existing:
                return base + s
        return base + 'X'


def main():
    fails = []

    # 1) build proposals: PIT chain proposed, plain formula not
    w = FakeWizard([Comp('PIT', PIT, 'AP'), Comp('NETSAL', PLAIN, 'BC')])
    Table.made = []
    w._build_rate_proposals()
    props = list(w.rate_proposal_ids)
    got = {p.component_code for p in props}
    if got != {'PIT'}:
        fails.append('build: expected only PIT proposed, got %s' % got)
    else:
        p = props[0]
        print("  ok   proposal built: %s driver=%s %s (table %s)" % (
            p.component_code, p.driver, p.edges, p.table_code))
        if p.n_brackets != 7:
            fails.append('build: PIT proposal should carry 7 brackets, got %s' % p.n_brackets)

    # 2) DECLINE (accept stays False) → staged formula imports verbatim, no table
    w._apply_rate_table_promotions()
    pit = w.component_preview_ids[0]
    if pit.excel_formula != PIT or Table.made:
        fails.append('decline: formula must be verbatim and no table (%s tables)' % len(Table.made))
    else:
        print("  ok   decline → formula verbatim, 0 tables created")

    # 3) ACCEPT → table created + staged text becomes BRACKET(code, driver)
    props[0].accept = True
    w._apply_rate_table_promotions()
    pit = w.component_preview_ids[0]
    ok_shape = (pit.excel_formula.startswith('=-MAX(0,BRACKET(')
                and pit.excel_formula.endswith(',AP2))')
                and pit.resolved_formula == pit.excel_formula)
    if not (Table.made and ok_shape):
        fails.append('accept: expected 1 table + BRACKET rewrite, got formula=%r tables=%s'
                     % (pit.excel_formula, len(Table.made)))
    else:
        t = Table.made[0]
        nbr = len(t.vals['line_ids'])
        print("  ok   accept → table %s (%s brackets), staged: %s" % (t.code, nbr, pit.excel_formula))
        if nbr != 7:
            fails.append('accept: table must have 7 brackets, got %s' % nbr)

    # 4) a chain that no longer parses is skipped (defensive) — corrupt then accept
    w2 = FakeWizard([Comp('PIT', PIT, 'AP')])
    w2._build_rate_proposals()
    list(w2.rate_proposal_ids)[0].accept = True
    w2.component_preview_ids[0].excel_formula = "=BASIC+1"   # no longer a chain
    Table.made = []
    w2._apply_rate_table_promotions()
    if w2.component_preview_ids[0].excel_formula != "=BASIC+1" or Table.made:
        fails.append('defensive: a no-longer-chain must import verbatim, no table')
    else:
        print("  ok   defensive re-detect → verbatim, no table when chain gone")

    print("\n%s" % ("ALL GREEN" if not fails else "FAILURES:\n  " + "\n  ".join(fails)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
