# -*- coding: utf-8 -*-
"""SCHEMECTX follow-up — the contract drawer writes the SCHEME's money.

The defect: a Vietnamese company running an Indian scheme showed an Indian
salary in dong, because the drawer took its sign from the company the contract
is filed under. It now takes it from the scheme that pays the person.

Four numbered cases, and the numbers are the handover's.

1  a person paid by an Indian scheme inside a dong company reads in rupees —
   the payload's sign, the wage sentence and a component's amount, all three;
2  a person nobody pays reads in the company's money, exactly as before;
3  a database with no scheme models reads in the company's money, exactly as
   before — the probe is the whole of the compatibility promise;
4  what a save says back — the fresh payload and a bounds refusal — is written
   in the same rupees.

Fixtures follow `test_schemectx_p2_components`: codes are underscore-free and
none is a substring of another (the converter contract binds fixtures too).
"""

from unittest.mock import patch

from odoo.api import Environment
from odoo.tests import TransactionCase, tagged

from .approval_lane import no_approval_needed
from .scheme_scope import paid_by


@tagged('post_install', '-at_install')
class TestSchemeCtxP3Currency(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        no_approval_needed(cls.env)
        cls.Facade = cls.env['pb.contracts']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Rule = cls.env.get('hr.formula.rule')
        cls.Config = cls.env.get('hr.formula.config')
        cls.company = cls.env.company
        cls.company_symbol = cls.company.currency_id.symbol or ''

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search(
                            [('company_id', 'in', (cls.company.id, False))],
                            limit=1))
        if not cls.calendar:
            cls.calendar = cls.env['resource.calendar'].create(
                {'name': 'SCP3 Schedule', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1)
        if not cls.ctype:
            cls.ctype = cls.env['hr.contract.type'].create(
                {'name': 'SCP3 Staff'})

        # One component per scheme. The Indian one carries a WINDOW, which is
        # what case 4 walks out of.
        cls.templates = {
            'SCP3INHRA': cls.Template.create({
                'name': 'SCP3 House rent allowance', 'code': 'SCP3INHRA',
                'lower_bound': 1000.0, 'upper_bound': 90000.0,
                'default_value': 0.0}),
            'SCP3VNMEAL': cls.Template.create({
                'name': 'SCP3 Meal allowance', 'code': 'SCP3VNMEAL',
                'lower_bound': 0.0, 'upper_bound': 0.0,
                'default_value': 0.0}),
        }

        cls.have_engine = bool(cls.Rule is not None and cls.Config is not None)
        cls.ind = cls.vn = None
        if cls.have_engine:
            cls.ind = cls.Config.create({
                'name': 'SCP3 India', 'code': 'SCP3IN',
                'country_code': 'IN', 'state': 'active',
                'company_id': cls.company.id})
            cls.vn = cls.Config.create({
                'name': 'SCP3 Vietnam', 'code': 'SCP3VN',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls._rule(cls.ind, 'SCP3INHRA')
            cls._rule(cls.vn, 'SCP3VNMEAL')

        # The person an Indian scheme pays, inside this (dong) company.
        cls.indian = cls.Employee.create(
            {'name': 'SCP3 Person India', 'company_id': cls.company.id})
        cls.in_contract = cls._contract(cls.indian, wage=75000.0)
        cls.in_line = cls._line(cls.in_contract, 'SCP3INHRA', 42000.0)
        cls.mapped = paid_by(cls.env, cls.indian, cls.ind)

        # The person nobody pays.
        cls.nobody = cls.Employee.create(
            {'name': 'SCP3 Person Unpaid', 'company_id': cls.company.id})
        cls.no_contract = cls._contract(cls.nobody, wage=12500000.0)
        cls._line(cls.no_contract, 'SCP3VNMEAL', 730000.0)
        if 'pb_paid_by_id' in cls.Employee._fields:
            cls.nobody.sudo().write({'pb_paid_by_id': False,
                                     'pb_paid_by_stale': False})
            if 'pb_paid_by_advance_id' in cls.Employee._fields:
                cls.nobody.sudo().write({'pb_paid_by_advance_id': False})

    # --------------------------------------------------------------- fixtures
    @classmethod
    def _rule(cls, config, code):
        return cls.Rule.create({
            'config_id': config.id, 'name': 'SCP3 %s' % code, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'is_contract_component': True})

    @classmethod
    def _contract(cls, employee, wage):
        return cls.Contract.create({
            'name': '%s - 2026-06-01' % employee.name,
            'employee_id': employee.id, 'wage': wage,
            'state': 'open', 'date_start': '2026-06-01',
            'resource_calendar_id': cls.calendar.id,
            'type_id': cls.ctype.id})

    @classmethod
    def _line(cls, contract, code, amount):
        return cls.Advantage.create({
            'contract_id': contract.id,
            'advantage_template_id': cls.templates[code].id,
            'amount': amount})

    # ---------------------------------------------------------------- helpers
    def _payload(self, contract):
        answer = self.Facade.get_contract_360(contract.id)
        self.assertTrue(answer.get('ok'), answer.get('error'))
        return answer

    def _term(self, payload, name):
        for group in payload['terms']:
            for field in (group.get('fields') or []):
                if field['name'] == name:
                    return field
        return None

    def _need_india(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        if not self.mapped:
            self.skipTest("this database cannot say who pays somebody")
        if not self.ind.currency_id:
            self.skipTest("this database has no currency for India")
        symbol = self.ind.currency_id.symbol or ''
        if symbol == self.company_symbol:
            self.skipTest("this company already pays in the scheme's money, "
                          "so there is nothing to tell apart")
        return symbol

    # ===================================================================== 1
    def test_01_an_indian_scheme_is_read_in_rupees(self):
        symbol = self._need_india()
        self.assertEqual(self.ind.currency_id.name, 'INR',
                         "the India scheme is not on rupees at all — that is "
                         "Phase 1's ground, not this one's")
        payload = self._payload(self.in_contract)

        # the payload's own sign
        self.assertEqual(payload['currency'], symbol)

        # the wage SENTENCE — the header reads it off this term (the drawer
        # never formats money a second time, client-side)
        wage = self._term(payload, 'wage')
        self.assertIsNotNone(wage, "the wage term is missing from the drawer")
        if payload['header'].get('wage_masked'):
            self.skipTest("this user may not see wages")
        self.assertTrue(
            wage['display'].startswith(symbol),
            "the wage reads %r, not rupees" % wage['display'])
        # SC3: the sign is always in FRONT, whatever `res.currency` stores
        self.assertNotIn(self.company_symbol, wage['display'])

        # and a component's amount
        rows = [r for r in payload['components']['rows']
                if r['code'] == 'SCP3INHRA']
        self.assertEqual(len(rows), 1,
                         "the scheme's own component is not on the list")
        self.assertTrue(
            rows[0]['display'].startswith(symbol),
            "the component reads %r, not rupees" % rows[0]['display'])
        # the window sentence under the cell quotes the same money
        hint = rows[0]['bounds_hint']
        self.assertTrue(hint, "the bounded component lost its window hint")
        self.assertIn(symbol, hint)
        self.assertNotIn(self.company_symbol, hint)

    # ===================================================================== 2
    def test_02_nobody_pays_this_person_so_it_is_the_company_money(self):
        if not self.have_engine:
            self.skipTest("no formula engine on this database")
        payload = self._payload(self.no_contract)
        if payload['components']['scope']['state'] == 'scoped':
            self.skipTest("this database resolves a scheme for anybody")
        self.assertEqual(payload['currency'], self.company_symbol)
        wage = self._term(payload, 'wage')
        if wage and not payload['header'].get('wage_masked'):
            self.assertTrue(wage['display'].startswith(self.company_symbol))

    # ===================================================================== 3
    def test_03_no_scheme_models_is_the_company_money(self):
        """The probe is the whole of the compatibility promise.

        `env.get` is what the drawer asks with, so the honest way to stage a
        database that has never heard of a payroll scheme is to make that one
        lookup answer nothing. Patched on `Environment` itself and only for
        the duration of the call.
        """
        symbol = self._need_india()
        original = Environment.get

        def blind(env_self, key, default=None):
            if key == 'hr.formula.config':
                return default
            return original(env_self, key, default)

        with patch.object(Environment, 'get', blind):
            payload = self._payload(self.in_contract)
        self.assertEqual(payload['currency'], self.company_symbol,
                         "a database with no schemes stopped using its own "
                         "company's money")
        self.assertNotEqual(payload['currency'], symbol)
        # and with the models back, the rupees return — the patch proved a
        # branch, not a broken fixture
        self.assertEqual(self._payload(self.in_contract)['currency'], symbol)

    # ===================================================================== 4
    def test_04_a_save_answers_in_the_schemes_money(self):
        symbol = self._need_india()
        answer = self.Facade.save_contract_360(
            self.in_contract.id, terms={},
            components={'edits': {str(self.in_line.id): {'amount': 999999.0}},
                        'removes': [], 'adds': []})
        self.assertTrue(answer.get('ok'), answer.get('msg'))
        refusals = [r for r in answer['refusals']
                    if r.get('key') == self.in_line.id]
        self.assertEqual(len(refusals), 1,
                         "999,999 is outside the window and was accepted")
        why = refusals[0]['why']
        self.assertIn(symbol, why,
                      "the refusal reads %r — it is quoting the wrong "
                      "money at the person" % why)
        self.assertNotIn(self.company_symbol, why)
        # the fresh payload the drawer repaints from
        self.assertEqual(answer['detail']['currency'], symbol)
        # nothing was written
        self.assertEqual(self.in_line.amount, 42000.0)

        # …and the same for the preview, which shares the one judgement
        preview = self.Facade.preview_contract_360(
            self.in_contract.id, terms={},
            components={'edits': {str(self.in_line.id): {'amount': 999999.0}},
                        'removes': [], 'adds': []})
        self.assertTrue(preview.get('ok'))
        self.assertIn(symbol, (preview['refusals'] or [{}])[0].get('why', ''))
