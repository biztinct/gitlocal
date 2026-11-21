# -*- coding: utf-8 -*-
"""FS-16 — People › Add employee sends bank details through the bank change
path (one waiting change a second person approves), never to the old boxes.

Numbers match FS16_REPORT.md: 1 direct new hire, 2 through the new-hire
approval, 3 a bad account number, 4 no bank details, 8 silent (only the
bank change itself, no other approval or job).
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE

FIELDS = ('vietnam_bank_account_number', 'vietnam_bank_name',
          'vietnam_bank_account_name', 'vietnam_bank_branch')


@tagged('post_install', '-at_install')
class TestFs16NewHireBank(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.ready = ('pb.bank.change.request' in env and 'pb.records.apply' in env
                     and 'vietnam_bank_account_number' in env['hr.employee']._fields)
        if not cls.ready:
            return
        from odoo.addons.pb_records.tests.bank_second import ensure_second_person
        cls.company = env.company
        cls.second = ensure_second_person(env, cls.company)
        Users = env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        cls.typist = Users.create(dict(common, name='DEMO FS16 Typist', login='fs16_typist',
                                       group_ids=[(6, 0, [env.ref('base.group_user').id,
                                                          env.ref('hr.group_hr_user').id,
                                                          env.ref('om_hr_payroll.group_hr_payroll_user').id])]))
        cls.Wizard = env['pb.people.onboard.wizard']
        cls.Req = env['pb.bank.change.request'].sudo()
        # the Records Desk twin (test 1's field-by-field compare)
        env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'records')
        cls.cfg = env['hr.formula.config'].create({
            'name': 'DEMO FS16 Scheme', 'code': 'FS16SCHEME', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id})
        for code, role in (('FSXACCNO', 'acc_number'), ('FSXBANK', 'bank_name'),
                           ('FSXHOLDER', 'acc_holder_name')):
            rule = env['hr.formula.rule'].create({
                'config_id': cls.cfg.id, 'name': code, 'code': code,
                'column_type': 'input', 'sequence': 1, 'default_value': 0.0})
            env['hr.payslip.import.mapping'].create({
                'salary_structure_id': cls.cfg.id, 'component_id': rule.id,
                'destination_type': 'bank_account', 'bank_role': role})

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('the bank change path is not installed here')

    # ------------------------------------------------------------ helpers
    def vals(self, name, number='0123 4567 8901', bank='Vietcombank', holder='DEMO FS16 HOLDER'):
        return {'name': name, 'with_contract': False, 'bank_name': bank,
                'account_number': number, 'account_holder': holder}

    def wizard(self, user=None):
        return self.Wizard.with_user(user or self.typist).with_context(
            allowed_company_ids=[self.company.id])

    def changes(self, emp):
        return self.Req.search([('employee_id', '=', emp.id)])

    def seat_of(self, req):
        request = req.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        return request, step, step.seat_ids.filtered(lambda s: s.status == 'open')

    def approve(self, req):
        request, step, seats = self.seat_of(req)
        seat = seats.filtered(lambda s: s.acting_user_id != req.proposed_by_id)[:1]
        self.assertTrue(seat, 'nobody but the typist holds a seat')
        self.env['biz.approval.engine'].with_user(seat.acting_user_id).decide(
            request.id, step.key, 'approve')
        self.env.invalidate_all()
        return seat.acting_user_id

    def stores(self, emp):
        """Both bank stores, field by field (numbers and holders compared to
        what was typed by the caller)."""
        self.env.invalidate_all()
        emp = emp.sudo()
        acc = emp.bank_account_ids[:1]
        return {
            'file': {f: emp[f] or False for f in FIELDS},
            'acc_number': acc.acc_number or False,
            'acc_bank': acc.bank_id.name or False,
            'acc_holder': acc.acc_holder_name or False,
            'acc_on_work_contact': bool(acc) and acc.partner_id == emp.work_contact_id,
            'acc_company': acc.company_id.id if acc and 'company_id' in acc._fields else False,
            'acc_active': bool(acc.active) if acc else False,
            'accounts': len(emp.bank_account_ids),
        }

    def old_boxes(self, emp):
        emp = emp.sudo()
        return tuple(emp[f] or False for f in ('account_number', 'bank_name') if f in emp._fields)

    # ------------------------------------------------------------ test 1
    def test_01_new_hire_bank_waits_for_a_second_person(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'newhire')
        res = self.wizard().create_employee(self.vals('DEMO FS16 One'))
        emp = self.env['hr.employee'].browse(res['employee_id'])
        self.assertTrue(emp.exists())
        self.assertTrue(res.get('applied'), 'the screen says "Employee added"')
        self.assertEqual(res['bank']['state'], 'sent', res.get('bank'))
        self.assertEqual(res['bank']['message'], 'Bank details sent for approval')
        req = self.changes(emp)
        self.assertEqual(len(req), 1, 'exactly ONE waiting bank change')
        self.assertEqual(req.state, 'hr_review')
        self.assertEqual(req.pb_origin, 'import')
        self.assertTrue(req.pb_import_key.startswith('pb.newhire,'))
        self.assertEqual(req.proposed_by_id, self.typist)
        self.assertEqual(req.x_account_number, '012345678901')
        self.assertEqual(req.x_bank_name, 'Vietcombank')
        self.assertEqual(req.x_account_name, 'DEMO FS16 HOLDER')
        self.assertEqual(req.approval_request_id.process_id.key, 'records_bank')
        # the approver sees it in the Approvals inbox; the typist is never seated
        _request, _step, seats = self.seat_of(req)
        self.assertTrue(seats)
        self.assertNotIn(self.typist, seats.acting_user_id)
        approver = seats[:1].acting_user_id
        page = self.env['pb.approval.inbox'].with_user(approver).with_context(
            pbf_ctx={'scope': 'me'}).get_inbox_page(filters={'my_turn': ['yes']})
        self.assertIn(req.approval_request_id.id, [c.get('id') for c in page['cards']])
        # nothing payable until approved; the old boxes stay empty
        before = self.stores(emp)
        self.assertFalse(before['file']['vietnam_bank_account_number'])
        self.assertEqual(before['accounts'], 0)
        self.assertFalse(any(self.old_boxes(emp)))
        # approve → both stores, as a Records Desk bank change writes them
        self.approve(req)
        after = self.stores(emp)
        twin = self.env['hr.employee'].create({'name': 'DEMO FS16 Twin',
                                               'company_id': self.company.id})
        self.env['hr.contract'].create({'name': 'DEMO FS16 twin contract',
                                        'employee_id': twin.id, 'wage': 1000.0,
                                        'state': 'open', 'date_start': '2026-01-01'})
        from odoo.addons.pb_records.tests.bank_second import approve_bank
        out = self.env['pb.records.desk'].apply_changes(self.cfg.id, [
            {'emp_id': twin.id, 'field_id': 'b:acc_number', 'value': '0987 6543 2109'},
            {'emp_id': twin.id, 'field_id': 'b:bank_name', 'value': 'Vietcombank'},
            {'emp_id': twin.id, 'field_id': 'b:acc_holder_name', 'value': 'DEMO FS16 HOLDER'}])
        self.assertEqual(approve_bank(self.env, out), 1)
        desk = self.stores(twin)
        self.assertEqual(after['acc_number'], '012345678901')
        self.assertEqual(after['file']['vietnam_bank_account_number'], '012345678901')
        self.assertEqual(desk['acc_number'], '098765432109')
        for side in (after, desk):
            side['acc_number'] = bool(side['acc_number'])
            side['file']['vietnam_bank_account_number'] = bool(
                side['file']['vietnam_bank_account_number'])
        self.assertEqual(after, desk, 'new hire and Records Desk write the same fields')
        self.assertFalse(any(self.old_boxes(emp)))

    # ------------------------------------------------------------ test 2
    def test_02_through_the_new_hire_approval(self):
        res = self.wizard().create_employee(self.vals('DEMO FS16 Two', number='555666777888'))
        self.assertFalse(res.get('employee_id'), 'the hire waits for its route')
        self.assertEqual(res['bank']['state'], 'later')
        prop = self.env['pb.newhire.proposal'].sudo().browse(res['proposal_id'])
        rows = [str(r[2]) for r in prop._proposal_rows()]
        self.assertIn('•••• 7888', rows)
        self.assertNotIn('555666777888', ' '.join(rows), 'the number is never shown whole')
        self.assertTrue(prop.facts()['has_bank']['value'])
        request = prop.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open'
                                      and s.acting_user_id != self.typist)[:1]
        self.assertTrue(seat)
        self.env['biz.approval.engine'].with_user(seat.acting_user_id).decide(
            request.id, step.key, 'approve')
        self.env.invalidate_all()
        self.assertTrue(prop.applied, prop.block_note)
        emp = self.env['hr.employee'].search([('name', '=', 'DEMO FS16 Two')])
        self.assertEqual(len(emp), 1)
        req = self.changes(emp)
        self.assertEqual(len(req), 1)
        self.assertEqual(req.state, 'hr_review')
        # proposed by the person who typed it, not by the hire's approver
        self.assertEqual(req.proposed_by_id, self.typist)
        self.assertFalse(self.stores(emp)['file']['vietnam_bank_account_number'])
        self.approve(req)
        self.assertEqual(self.stores(emp)['acc_number'], '555666777888')
        self.assertEqual(self.stores(emp)['file']['vietnam_bank_account_number'], '555666777888')
        self.assertFalse(any(self.old_boxes(emp)))

    # ------------------------------------------------------------ test 3
    def test_03_bad_number_person_created_clear_message_no_change(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'newhire')
        for number, words in (('12-34', '6 to 19 digits'), ('12AB345678', 'only have digits')):
            name = 'DEMO FS16 Bad %s' % number
            res = self.wizard().create_employee(self.vals(name, number=number))
            emp = self.env['hr.employee'].browse(res['employee_id'])
            self.assertTrue(emp.exists(), 'the person is still created')
            self.assertEqual(res['bank']['state'], 'not_sent')
            self.assertIn(words, res['bank']['message'])
            self.assertIn('side panel', res['bank']['message'])
            self.assertFalse(self.changes(emp))
            self.assertFalse(any(self.old_boxes(emp)))
            self.assertIn(words, ' '.join(emp.message_ids.mapped('body')))
        # a bank name with no number is a problem too, never dropped in silence
        res = self.wizard().create_employee({'name': 'DEMO FS16 No number',
                                             'bank_name': 'Vietcombank', 'with_contract': False})
        self.assertEqual(res['bank']['state'], 'not_sent')
        self.assertIn('account number too', res['bank']['message'])

    def test_03b_bad_number_on_the_approval_route_is_said_at_once(self):
        res = self.wizard().create_employee(self.vals('DEMO FS16 Bad route', number='123'))
        self.assertEqual(res['bank']['state'], 'not_sent')
        prop = self.env['pb.newhire.proposal'].sudo().browse(res['proposal_id'])
        values = prop.payload()['values']
        self.assertFalse(values.get('account_number'))
        self.assertFalse(prop.facts()['has_bank']['value'])

    # ------------------------------------------------------------ test 4
    def test_04_no_bank_details_no_change(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'newhire')
        res = self.wizard().create_employee({'name': 'DEMO FS16 Four', 'with_contract': False,
                                             'bank_name': '', 'account_number': ' ',
                                             'account_holder': ''})
        emp = self.env['hr.employee'].browse(res['employee_id'])
        self.assertTrue(emp.exists())
        self.assertNotIn('bank', res)
        self.assertFalse(self.changes(emp))

    # ------------------------------------------------- the contract fact
    def test_05_contract_fact_reads_the_approved_account(self):
        emp = self.env['hr.employee'].create({'name': 'DEMO FS16 Fact',
                                              'company_id': self.company.id})
        if 'account_number' in emp._fields:
            emp.sudo().write({'account_number': '999999999'})   # the old box: never counts
        self.assertFalse(self.env['pb.people.contract.wizard']._pb_has_approved_bank(emp))
        emp.sudo().write({'vietnam_bank_account_number': '123456789'})
        self.assertTrue(self.env['pb.people.contract.wizard']._pb_has_approved_bank(emp))

    # ------------------------------------------------------------ test 8
    def test_08_only_the_bank_change_is_made(self):
        """Silent: a new hire with bank details makes the person and ONE bank
        change; no other approval, no scheduled job."""
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'newhire')
        Request = self.env['biz.approval.request'].sudo()
        crons = self.env['ir.cron'].sudo().search_count([])
        res = self.wizard().create_employee(self.vals('DEMO FS16 Eight', number='112233445566'))
        emp = self.env['hr.employee'].browse(res['employee_id'])
        req = self.changes(emp)
        bank_requests = Request.search([('res_model', '=', 'pb.bank.change.request'),
                                        ('res_id', '=', req.id)])
        self.assertEqual(len(bank_requests), 1)
        self.assertEqual(self.env['ir.cron'].sudo().search_count([]), crons)

    # ------------------------------------------------ the screen's lists
    def test_09_defaults_offer_the_bank_list(self):
        d = self.wizard().get_defaults()
        self.assertTrue(d['bank_check'])
        values = [b['value'] for b in d['banks']]
        self.assertTrue(values, 'the bank check knows some banks')
        self.assertEqual(len(values), len({v.lower() for v in values}))
