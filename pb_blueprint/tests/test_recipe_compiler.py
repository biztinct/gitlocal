# -*- coding: utf-8 -*-
"""The compiler, on its own — no database, no records, no engine.

`compile_recipe` is a pure function, and these are the assertions that make it
safe to change: give it a sentence and a picture of a configuration, and it
must produce exactly one formula, written in column letters, using only what
the engine can read.

Every expectation here is a STRING, deliberately. "It produces something that
evaluates the same" is the kind of promise that quietly drifts; "it produces
this formula" is one a person can check against the rule pack by eye.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_blueprint.models import recipe_compiler as rc
from odoo.addons.pb_blueprint.models.recipe_schema import (
    RecipeError, helper_code, validate_recipe,
)
from odoo.addons.pb_blueprint.models.essentials_recipes import ESSENTIALS_RECIPES
from odoo.addons.pb_blueprint.models.workbook_vocabulary import (
    WORKBOOK_CODES, WORKBOOK_COMPONENTS,
)

#: The Vietnam rule pack, as the compiler sees it: letter, code, kind.
PACK = [
    ('A', 'BASIC', 'input'), ('B', 'DEPS', 'input'), ('C', 'STDDAYS', 'input'),
    ('D', 'OTHRS15', 'input'), ('E', 'OTHRS20', 'input'),
    ('F', 'OTHRS30', 'input'), ('G', 'BONUS', 'input'),
    ('H', 'ALLOWIN', 'input'), ('I', 'DEDUCTSELF', 'constant'),
    ('J', 'DEDUCTDEP', 'constant'), ('K', 'SIRATE', 'constant'),
    ('L', 'HIRATE', 'constant'), ('M', 'UIRATE', 'constant'),
    ('N', 'SIEMPR', 'constant'), ('O', 'HIEMPR', 'constant'),
    ('P', 'UIEMPR', 'constant'), ('Q', 'CAPLO', 'constant'),
    ('R', 'CAPHI', 'constant'), ('S', 'MULT15', 'constant'),
    ('T', 'MULT20', 'constant'), ('U', 'MULT30', 'constant'),
    ('V', 'HOURRATE', 'formula'), ('W', 'OTPAY', 'formula'),
    ('X', 'GROSS', 'formula'), ('Y', 'SIBASE', 'formula'),
    ('Z', 'UIBASE', 'formula'), ('AA', 'SIDED', 'formula'),
    ('AB', 'HIDED', 'formula'), ('AC', 'UIDED', 'formula'),
    ('AD', 'EEDED', 'formula'), ('AE', 'TAXABLE', 'formula'),
    ('AF', 'PIT', 'formula'), ('AG', 'NET', 'formula'),
    ('AH', 'SICOMP', 'formula'), ('AI', 'HICOMP', 'formula'),
    ('AJ', 'UICOMP', 'formula'), ('AK', 'ERCOST', 'formula'),
]


def _letter(index):
    """0 -> A, 25 -> Z, 26 -> AA. The same walk the engine uses."""
    out = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        out = chr(65 + rest) + out
    return out


class Picture(object):
    """A configuration, faked well enough for a pure compiler."""

    def __init__(self, rows=PACK):
        self.letters, self.order, self.types = {}, [], {}
        for letter, code, kind in rows:
            self.letters[code] = letter
            self.order.append(code)
            self.types[code] = kind
        self.recipes, self.groups = {}, {}
        self.next = len(rows)

    def add(self, code, kind='input', letter=None):
        if code in self.letters:
            return self.letters[code]
        self.letters[code] = letter or _letter(self.next)
        self.next += 1
        self.order.append(code)
        self.types[code] = kind
        # setdefault, never assignment: a sentence may be taught before the
        # component gets its letter, and clobbering it here was worth an hour.
        self.groups.setdefault(code, 'helper')
        self.recipes.setdefault(code, None)
        return self.letters[code]

    def teach(self, code, recipe):
        clean = validate_recipe(recipe, {
            'codes': set(self.order), 'rate_tables': {'VNTAX'},
            'self_code': code})
        self.recipes[code] = clean
        self.groups[code] = clean['group']
        return clean

    def ctx(self, self_code=''):
        return rc.Ctx({
            'letters': dict(self.letters), 'recipes': dict(self.recipes),
            'groups': dict(self.groups), 'types': dict(self.types),
            'order': list(self.order), 'rate_tables': {'VNTAX'},
            'self_code': self_code, 'contract_code': 'BASIC',
        })

    def compile(self, code):
        return rc.compile_recipe(self.recipes[code], self.ctx(code))

    def provision(self, rounds=5):
        """Create every helper the sentences ask for, as the server would."""
        made = []
        for _round in range(rounds):
            wanted = []
            for code in list(self.order):
                recipe = self.recipes.get(code)
                if not recipe:
                    continue
                for formula, needs in (rc.compile_recipe(recipe, self.ctx(code)),
                                       rc.taxable_helper_formula(recipe, self.ctx(code))):
                    for need in needs:
                        if need not in self.letters and need not in wanted:
                            wanted.append(need)
            if not wanted:
                break
            for code in wanted:
                self.add(code, 'input')
                made.append(code)
        return made


@tagged('post_install', '-at_install')
class TestRecipeCompiler(TransactionCase):

    def setUp(self):
        super().setUp()
        self.p = Picture()

    def _base(self, **over):
        recipe = {'v': 1, 'group': 'earning', 'audience': 'all',
                  'amount': {'kind': 'contract'}, 'proration': 'none',
                  'frequency': 'monthly', 'sign': 1, 'round': '0',
                  'treatment': {'cash': 'cash', 'tax': 'taxable',
                                'insurance': 'excluded'}}
        recipe.update(over)
        return recipe

    # ---- 1 ----------------------------------------------------------
    def test_contract_prorated_by_working_days(self):
        """The simplest real rule, letter for letter."""
        self.p.add('PAIDDAYS')          # takes the letter after the pack
        self.p.teach('SALARYPAID', self._base(proration='working_days'))
        self.p.add('SALARYPAID', 'formula')
        formula, needs = self.p.compile('SALARYPAID')
        paid = self.p.letters['PAIDDAYS']
        self.assertEqual(formula, '=ROUND((A*(%s/C)),0)' % paid)
        self.assertEqual(needs, [])

    # ---- 2 ----------------------------------------------------------
    def test_hourly_names_its_helpers_before_they_exist(self):
        self.p.teach('OTWE', self._base(
            amount={'kind': 'hourly', 'rate_pct': 200}))
        self.p.add('OTWE', 'formula')
        formula, needs = self.p.compile('OTWE')
        # Nothing exists yet, so the sentence SAYS what it needs rather than
        # refusing: the caller creates them and compiles again.
        self.assertIn('OTWEHRS', needs)
        self.assertIn('HOURSDAY', needs)
        self.assertNotIn('BASIC', needs)
        self.assertNotIn('STDDAYS', needs)

        self.p.add('OTWEHRS')
        self.p.add('HOURSDAY')
        formula, needs = self.p.compile('OTWE')
        self.assertEqual(needs, [])
        hrs, hpd = self.p.letters['OTWEHRS'], self.p.letters['HOURSDAY']
        self.assertEqual(formula, '=ROUND((%s*(A/(C*%s))*200/100),0)' % (hrs, hpd))

    # ---- 3 ----------------------------------------------------------
    def test_audience_local_wraps_and_shares_one_helper(self):
        self.p.add('ISLOCAL')
        self.p.teach('ALLOWA', self._base(audience='local',
                                          amount={'kind': 'fixed', 'value': 500000}))
        self.p.add('ALLOWA', 'formula')
        self.p.teach('ALLOWB', self._base(audience='local',
                                          amount={'kind': 'fixed', 'value': 200000}))
        self.p.add('ALLOWB', 'formula')
        local = self.p.letters['ISLOCAL']
        a, _needs = self.p.compile('ALLOWA')
        b, _needs2 = self.p.compile('ALLOWB')
        self.assertEqual(a, '=ROUND(IF(%s=1,500000,0),0)' % local)
        self.assertEqual(b, '=ROUND(IF(%s=1,200000,0),0)' % local)
        # One helper, not one per rule.
        self.assertEqual(len([c for c in self.p.order if c == 'ISLOCAL']), 1)

    # ---- 4 ----------------------------------------------------------
    def test_annual_service_ratio(self):
        for code in ('PAYMONTH', 'SERVDAYS', 'ANNUALDAYS'):
            self.p.add(code)
        self.p.teach('MONTH13', self._base(
            frequency='annual',
            amount={'kind': 'annual_ratio', 'payout_month': 1}))
        self.p.add('MONTH13', 'formula')
        formula, needs = self.p.compile('MONTH13')
        month = self.p.letters['PAYMONTH']
        serv = self.p.letters['SERVDAYS']
        year = self.p.letters['ANNUALDAYS']
        self.assertEqual(needs, [])
        self.assertEqual(
            formula, '=ROUND(IF(%s=1,MIN(A,A*%s/%s),0),0)' % (month, serv, year))

    # ---- 5 ----------------------------------------------------------
    def test_group_sum_respects_cash_and_membership(self):
        self.p.teach('GROSS', ESSENTIALS_RECIPES['GROSS'])
        for code in ('BASIC', 'BONUS', 'ALLOWIN', 'OTPAY'):
            self.p.teach(code, ESSENTIALS_RECIPES[code])
        formula, _needs = self.p.compile('GROSS')
        self.assertEqual(formula, '=(A+G+H+W)')

        # A non-cash earning is not cash, and is left out.
        self.p.teach('BONUS', dict(
            ESSENTIALS_RECIPES['BONUS'],
            treatment={'cash': 'noncash', 'tax': 'taxable',
                       'insurance': 'excluded'}))
        formula, _needs = self.p.compile('GROSS')
        self.assertEqual(formula, '=(A+H+W)')

        # Nothing in the group at all is a zero, never an empty expression.
        empty = Picture([('A', 'BASIC', 'input')])
        empty.teach('TOTAL', {'v': 1, 'group': 'total',
                              'amount': {'kind': 'sum_group',
                                         'of': {'group': 'deduction'}},
                              'round': 'none',
                              'treatment': {'tax': 'exempt'}})
        empty.add('TOTAL', 'formula')
        formula, _needs = empty.compile('TOTAL')
        self.assertEqual(formula, '=0')

    # ---- 6 ----------------------------------------------------------
    def test_bracket_and_an_unknown_band_table(self):
        self.p.teach('PIT', ESSENTIALS_RECIPES['PIT'])
        formula, _needs = self.p.compile('PIT')
        self.assertEqual(formula, '=BRACKET(VNTAX,AE)')

        with self.assertRaises(RecipeError) as caught:
            self.p.teach('PIT', dict(
                ESSENTIALS_RECIPES['PIT'],
                amount={'kind': 'bracket', 'table': 'NOSUCH', 'base': 'TAXABLE'}))
        self.assertIn('NOSUCH', str(caught.exception))

    # ---- 7 ----------------------------------------------------------
    def test_percentage_of_uses_the_rate_constant_not_a_literal(self):
        self.p.teach('SIDED', ESSENTIALS_RECIPES['SIDED'])
        formula, _needs = self.p.compile('SIDED')
        self.assertEqual(formula, '=(Y*K)', "the stored rate constant must be "
                                            "referenced, so changing it changes the rule")
        # And a plain percentage still works.
        self.p.teach('UNIONDUES', {
            'v': 1, 'group': 'deduction', 'round': 'none',
            'amount': {'kind': 'percent_of', 'base': 'SIBASE', 'percent': 0.5},
            'treatment': {'tax': 'exempt'}})
        self.p.add('UNIONDUES', 'formula')
        formula, _needs = self.p.compile('UNIONDUES')
        self.assertEqual(formula, '=(Y*0.5/100)')

    # ---- extra: the Essentials pack, reproduced ----------------------
    def test_essentials_reproduce_the_packs_arithmetic(self):
        """Every generated total must be the pack's own total, by construction."""
        for code, recipe in ESSENTIALS_RECIPES.items():
            self.p.teach(code, recipe)
        expected = {
            'GROSS': '=(A+G+H+W)',
            'SIBASE': '=MIN(A,Q)',
            'UIBASE': '=MIN(A,R)',
            'SIDED': '=(Y*K)', 'HIDED': '=(Y*L)', 'UIDED': '=(Z*M)',
            'EEDED': '=(AA+AB+AC)',
            'TAXABLE': '=MAX(0,(A+G+H+W)-(AA+AB+AC)-I-(B*J))',
            'PIT': '=BRACKET(VNTAX,AE)',
            'NET': '=(A+G+H+W)-(AA+AB+AC+AF)',
            'SICOMP': '=(Y*N)', 'HICOMP': '=(Y*O)', 'UICOMP': '=(Z*P)',
            'ERCOST': '=(A+G+H+W)+(AH+AI+AJ)',
        }
        for code, want in expected.items():
            formula, needs = self.p.compile(code)
            self.assertEqual(needs, [], "%s should need nothing new" % code)
            self.assertEqual(formula, want, "%s changed shape" % code)
        # The inputs and the constants keep no formula of their own.
        for code in ('BASIC', 'DEPS', 'CAPLO', 'HOURRATE', 'OTPAY'):
            formula, _needs = self.p.compile(code)
            self.assertIsNone(formula, "%s must keep its own value" % code)

    def test_dependency_order_refuses_a_loop_by_name(self):
        self.p.teach('GROSS', ESSENTIALS_RECIPES['GROSS'])
        self.p.teach('TAXABLE', ESSENTIALS_RECIPES['TAXABLE'])
        self.p.teach('PIT', ESSENTIALS_RECIPES['PIT'])
        codes = [c for c in self.p.order if self.p.recipes.get(c)]
        order = rc.dependency_order(codes, self.p.ctx())
        self.assertLess(order.index('TAXABLE'), order.index('PIT'))

        # Now make the tax feed the taxable income, and it has to refuse.
        self.p.teach('TAXABLE', {
            'v': 1, 'group': 'total', 'round': 'none',
            'amount': {'kind': 'percent_of', 'base': 'PIT', 'percent': 100},
            'treatment': {'tax': 'exempt'}})
        with self.assertRaises(RecipeError) as caught:
            rc.dependency_order([c for c in self.p.order if self.p.recipes.get(c)],
                                self.p.ctx())
        self.assertIn('PIT', str(caught.exception))
        self.assertIn('TAXABLE', str(caught.exception))

    def test_a_component_cannot_be_worked_out_from_itself(self):
        self.p.teach('SIBASE', {
            'v': 1, 'group': 'total', 'round': 'none',
            'amount': {'kind': 'percent_of', 'base': 'CAPLO', 'percent': 50},
            'treatment': {'tax': 'exempt'}})
        with self.assertRaises(RecipeError):
            validate_recipe({'v': 1, 'group': 'total',
                             'amount': {'kind': 'percent_of', 'base': 'SIBASE',
                                        'percent': 50},
                             'treatment': {'tax': 'exempt'}},
                            {'codes': set(self.p.order), 'self_code': 'SIBASE'})

    def test_helper_codes_fit_twelve_characters(self):
        self.assertEqual(helper_code('UNIFORM', 'YTD'), 'UNIFORMYTD')
        self.assertEqual(helper_code('OTHEREXMP', 'QUAL'), 'OTHEREXMQUAL')
        self.assertEqual(len(helper_code('PRIVHLTHDEP', 'ENR')), 12)
        for base in ('A', 'AB', 'VERYLONGCODE'):
            for suffix in ('IN', 'HRS', 'ENR', 'QUAL', 'YTD', 'ENT', 'TX'):
                code = helper_code(base, suffix)
                self.assertLessEqual(len(code), 12)
                self.assertTrue(code.isalnum())
                self.assertTrue(code[0].isalpha())

    # ---- 14 ---------------------------------------------------------
    def test_the_whole_workbook_vocabulary_compiles(self):
        """All 38 workbook components, said as sentences and compiled.

        This is the proof that the next phase is content and not engineering:
        every exemption, proration, audience and employer share the real
        Vietnamese workbook carries can be expressed without a new kind.
        """
        self.assertEqual(len(WORKBOOK_COMPONENTS), 38)
        self.assertEqual(len(set(WORKBOOK_CODES)), 38)
        for code in WORKBOOK_CODES:
            self.assertLessEqual(len(code), 12)
            self.assertTrue(code.isalnum() and code[0].isalpha(), code)

        # No code may contain another, Essentials included: the template
        # registry refuses such a set at authoring time.
        every = sorted(set(WORKBOOK_CODES) | {c for _l, c, _t in PACK})
        for one in every:
            for other in every:
                if one != other:
                    self.assertNotIn(one, other,
                                     "%s sits inside %s" % (one, other))

        for code, recipe in ESSENTIALS_RECIPES.items():
            self.p.teach(code, recipe)
        # Every code first, THEN every sentence: one component links to
        # another, and a forward reference is a real thing a starter contains.
        for comp in WORKBOOK_COMPONENTS:
            self.p.add(comp['code'], 'formula')
        for comp in WORKBOOK_COMPONENTS:
            self.p.teach(comp['code'], comp['recipe'])
        made = self.p.provision()
        self.assertTrue(made, "the sentences ask for helper inputs")

        for comp in WORKBOOK_COMPONENTS:
            formula, needs = self.p.compile(comp['code'])
            self.assertEqual(needs, [], "%s still needs %s" % (comp['code'], needs))
            self.assertTrue(formula and formula.startswith('='),
                            "%s produced nothing" % comp['code'])
            # Letters only: no component CODE may survive into a formula.
            for other in WORKBOOK_CODES:
                self.assertNotIn(other, formula,
                                 "%s refers to %s by code, not by letter"
                                 % (comp['code'], other))

        # And the four conditional exemptions each grow their own helper rule.
        for code in ('UNIFORM', 'SEVERSTAT', 'OTHEREXMP', 'OTWD'):
            formula, needs = rc.taxable_helper_formula(
                self.p.recipes[code], self.p.ctx(code))
            self.assertTrue(formula, "%s should have a taxable part" % code)
            self.assertEqual(needs, [])
