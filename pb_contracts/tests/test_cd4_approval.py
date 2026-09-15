# -*- coding: utf-8 -*-
"""A contract's terms are money, so changing them is a decision.

The three suites beside this one publish "No approval needed" and test the
drawer's write body (ledger AM100). This one is the other half: what happens
when a route really is published.

WHAT IT PROVES, AND WHY EACH ONE MATTERS
  1. A change to somebody's PAY is written down and the contract is untouched.
  2. A change that moves no money — a reference, a note — writes straight
     through, because "Salary and contract changes" is the row, and a route in
     front of fixing a typo is a gate nobody asked for.
  3. A mixed press does both: the money waits, the note lands, and the answer
     says how many were saved so nobody reads "nothing happened" over
     something that did.
  4. Approving it writes exactly what was proposed, once.
  5. The drawer names the person and the values in words — never the payload.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCd4ContractApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Facade = cls.env['pb.contracts']
        cls.Proposal = cls.env['pb.contract.proposal']
        cls.engine = cls.env['biz.approval.engine']
        cls.company = cls.env['res.company'].create({'name': 'CD4 Co'})
        cls.admin = cls.env.ref('base.user_admin')
        cls.admin.write({'company_ids': [(4, cls.company.id)]})

        cls.hr = cls._user('cd4_hr', 'Hana HR',
                           ['base.group_user', 'hr.group_hr_manager',
                            'hr_contract.group_hr_contract_manager'])
        cls.lead = cls._user('cd4_lead', 'Lena Lead',
                             ['base.group_user', 'hr.group_hr_manager',
                              'hr_contract.group_hr_contract_manager'])
        cls.Proposal._approval_seed_default(cls.company)
        cls._seat('hr_lead', cls.lead)

        cls.calendar = cls.env['resource.calendar'].create(
            {'name': 'CD4 Hours', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'CD4 Staff'})
        cls.employee = cls.env['hr.employee'].create(
            {'name': 'CD4 Person', 'company_id': cls.company.id})
        cls.contract = cls.env['hr.contract'].create({
            'name': 'CD4 Contract',
            'employee_id': cls.employee.id,
            'company_id': cls.company.id,
            'date_start': '2026-01-01',
            'wage': 10000000.0,
            'state': 'open',
            'type_id': cls.ctype.id,
            'resource_calendar_id': cls.calendar.id,
        })

    @classmethod
    def _user(cls, login, name, groups):
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login,
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])],
            })

    @classmethod
    def _seat(cls, role_key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', role_key)], limit=1)
        if not role:
            return False
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'active': False})
        return cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.company.name,
            'user_id': user.id})

    def _save(self, terms, user=None):
        return self.Facade.with_user(user or self.hr).with_company(
            self.company).save_contract_360(self.contract.id, terms, [], '')

    # ------------------------------------------------------------------ 1
    def test_cd4_a_pay_change_is_written_down_and_nothing_is_touched(self):
        was = self.contract.wage
        answer = self._save({'wage': 15000000.0})

        self.assertTrue(answer['ok'])
        self.assertTrue(answer.get('pending'),
                        'a pay change must not write until somebody agrees')
        self.assertTrue(answer.get('reference', '').startswith('CTR'))
        self.assertIn('Lena Lead', answer.get('msg') or '',
                      'the answer says who is holding it')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.wage, was,
                         'the contract changed before anybody agreed')

    # ------------------------------------------------------------------ 2
    def test_cd4_a_change_that_moves_no_money_writes_straight_through(self):
        answer = self._save({'name': 'CD4 Contract (renamed)'})

        self.assertFalse(answer.get('pending'),
                         'a rename is not a salary change')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.name, 'CD4 Contract (renamed)')

    # ------------------------------------------------------------------ 3
    def test_cd4_a_mixed_press_waits_for_the_money_and_lands_the_rest(self):
        was = self.contract.wage
        answer = self._save({'wage': 16000000.0, 'name': 'CD4 both'})

        self.assertTrue(answer.get('pending'))
        self.assertEqual(answer['saved'], 1,
                         'the note was saved and the answer should say so')
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.name, 'CD4 both')
        self.assertEqual(self.contract.wage, was)

    # ------------------------------------------------------------------ 4
    def test_cd4_approving_writes_exactly_what_was_proposed(self):
        self._save({'wage': 17000000.0})
        proposal = self.Proposal.sudo().search([], order='id desc', limit=1)
        request = proposal.approval_request_id
        self.assertTrue(request)

        self.engine.with_user(self.lead).decide(
            request, request.current_step_key, 'approve', 'Agreed')
        self.contract.invalidate_recordset()
        proposal.invalidate_recordset()
        self.assertEqual(self.contract.wage, 17000000.0)
        self.assertEqual(proposal.state, 'applied')
        self.assertEqual(
            self.env['biz.approval.request'].sudo().search_count(
                [('res_model', '=', 'pb.contract.proposal'),
                 ('res_id', '=', proposal.id)]), 1,
            'exactly one request, and the write happened once')

    # ------------------------------------------------------------------ 5
    def test_cd4_the_drawer_says_it_in_words(self):
        self._save({'wage': 18000000.0})
        proposal = self.Proposal.sudo().search([], order='id desc', limit=1)
        detail = proposal._approval_detail(proposal.approval_request_id)

        labels = [row['head'] for row in detail['rows']]
        self.assertIn('Person', labels)
        self.assertIn('Monthly pay', labels)
        for bad in ('terms', 'components', 'contract_id', 'shown'):
            self.assertNotIn(bad, labels,
                             'the drawer is showing the payload again')
        pay = [r for r in detail['rows'] if r['head'] == 'Monthly pay'][0]
        self.assertIn('10', pay['cells'][0], 'the old wage should be beside it')
