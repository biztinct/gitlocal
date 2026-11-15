# -*- coding: utf-8 -*-
"""WDGAP S8-B — Change job (`pb_job_change`). Numbered as in the S8-B report.

JC1  C-1: `pb_start_for_employee` returns the guided-flow action, prefilled,
     unknown keys dropped, nothing created.
JC2  one route: their manager (only with a login) → HR lead → Finance only
     above the guidance.
JC3  approved today: person AND contract written together, wage with a
     `pb.pay.apply` row, pay lines with DATED change rows, wage change row when
     the scheme reads the wage, one letter, one trail event.
JC4  future date: approved → Scheduled, NOTHING written; the job writes it on
     the day (company time) and a second run writes nothing.
JC5  changed underneath: nothing written, named; a scheduled one is sent back.
JC6  past date in a paid month: allowed; paid months listed; the re-work door
     opens a DRAFT re-work for that person and months; no back-pay input,
     no payslip touched. Without the re-work: a calm sentence.
JC7  take it back: within 24 h everything returns; after that, refused.
JC8  rights: HR officer refused; HR manager without pay rights never sees or
     sends a figure; a manager asked to decide reads only their seat; another
     company sees nothing.
JC9  checks before sending: nothing changes, own manager, cycle, a year
     ahead, reason, a second live change.
JC10 letters: promotion/transfer/job change types by selection_add; one letter.
JC11 silent install: quiet idempotent job on an empty set; process row; seed.
JC12 "Paid by" what-if: the roster override is read-only and per person.
JC13 golden: a finished payslip's lines are byte-identical after a job change.
JC14 timeline shows the change as ONE event.
"""
import json
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wdgap_s8b')
class TestJobChange(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.company = cls.env['res.company'].create(
            {'name': 'S8B Co', 'currency_id': cls.vnd.id})
        cls.other = cls.env['res.company'].create(
            {'name': 'S8B Other Co', 'currency_id': cls.vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.other.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        cls.JC = cls.env['pb.job.change']
        cls.Board = cls.env['pb.job.change.board']
        cls.calendar = cls.company.resource_calendar_id or \
            cls.env['resource.calendar'].create(
                {'name': 'S8B Hours', 'company_id': cls.company.id})
        cls.calendar2 = cls.env['resource.calendar'].create(
            {'name': 'S8B Part time', 'company_id': cls.company.id})
        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'S8B Finance', 'company_id': cls.company.id})
        cls.dept_b = Dept.create({'name': 'S8B Tax', 'company_id': cls.company.id})
        Job = cls.env['hr.job']
        cls.job_a = Job.create({'name': 'S8B Accountant', 'company_id': cls.company.id})
        cls.job_b = Job.create({'name': 'S8B Senior Accountant',
                                'company_id': cls.company.id})
        cls.loc = cls.env['hr.work.location'].create({
            'name': 'S8B Hanoi office', 'company_id': cls.company.id,
            'address_id': cls.company.partner_id.id, 'location_type': 'office'})
        cls.mgr_user = cls.env['res.users'].create({
            'name': 'S8B Boss', 'login': 's8b_boss',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})
        cls.boss = cls.env['hr.employee'].create({
            'name': 'S8B Boss', 'company_id': cls.company.id,
            'user_id': cls.mgr_user.id})
        cls.boss2 = cls.env['hr.employee'].create({
            'name': 'S8B New Boss', 'company_id': cls.company.id})
        cls.template = cls.env['hr.contract.advantage.template'].search(
            [('code', '=', 'SBMEAL')], limit=1) or \
            cls.env['hr.contract.advantage.template'].create(
                {'name': 'Meal allowance', 'code': 'SBMEAL'})
        settings = cls.env['pb.pay.settings'].sudo().for_company(cls.company)
        settings.change_finance_pct = 10.0
        cls._seq = 0

    # ------------------------------------------------------------ fixtures
    def _person(self, wage=10_000_000.0, meal=500_000.0, manager=None):
        type(self)._seq += 1
        emp = self.env['hr.employee'].create({
            'name': 'S8B Person %s' % self._seq, 'company_id': self.company.id,
            'department_id': self.dept_a.id, 'job_id': self.job_a.id,
            'parent_id': (manager or self.boss).id,
            'resource_calendar_id': self.calendar.id})
        contract = self.env['hr.contract'].create({
            'name': 'S8B contract %s' % self._seq, 'employee_id': emp.id,
            'wage': wage, 'state': 'open', 'date_start': '2026-01-01',
            'company_id': self.company.id,
            'resource_calendar_id': self.calendar.id,
            'department_id': self.dept_a.id, 'job_id': self.job_a.id})
        if meal:
            self.env['hr.contract.advantage'].create({
                'contract_id': contract.id,
                'advantage_template_id': self.template.id, 'amount': meal})
        return emp, contract

    def _vals(self, emp, **kw):
        vals = {
            'employee_id': emp.id, 'reason_kind': 'promotion',
            'reason': 'Took over the tax desk', 'effective_date':
                fields.Date.to_string(self._today()),
            'new_job_id': self.job_b.id, 'new_job_title': 'Senior Accountant',
            'new_department_id': self.dept_b.id, 'new_parent_id': self.boss2.id,
            'new_work_location_id': self.loc.id,
            'new_resource_calendar_id': self.calendar2.id,
            'change_pay': True, 'new_wage': 10_500_000.0,
            'lines': [{'code': 'SBMEAL', 'name': 'Meal allowance',
                       'old': 500_000.0, 'new': 700_000.0}],
        }
        vals.update(kw)
        return vals

    def _today(self):
        return self.JC._today_for(self.company)

    def _fast(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(
            self.company, 'jobchange')

    def _send(self, emp, **kw):
        return self.Board.send(self._vals(emp, **kw))

    def _rec(self, answer):
        return self.JC.browse(answer['id'])

    # ================================================================ JC1
    def test_jc01_start_for_employee(self):
        emp, _c = self._person()
        before = self.JC.search_count([])
        action = self.JC.pb_start_for_employee(emp.id, {
            'job_id': self.job_b.id, 'department_id': self.dept_b.id,
            'wage': 12_000_000, 'reason': 'Internal hire', 'source':
                'internal_hire', 'unknown_key': 'dropped',
            'lines': [{'code': 'SBMEAL', 'amount': 800000}, {'x': 1}]})
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'pb_job_change')
        params = action['params']
        self.assertEqual(params['employee_id'], emp.id)
        self.assertEqual(params['vals']['job_id'], self.job_b.id)
        self.assertEqual(params['vals']['wage'], 12_000_000.0)
        self.assertNotIn('unknown_key', params['vals'])
        self.assertEqual(params['vals']['lines'], [{'code': 'SBMEAL', 'amount': 800000.0}])
        self.assertEqual(self.JC.search_count([]), before, "C-1 creates nothing")
        # the screen's prefill reads those vals
        flow = self.Board.get_flow(emp.id, 0, params['vals'])
        self.assertEqual(flow['draft']['new_job_id'], self.job_b.id)
        self.assertTrue(flow['draft']['change_pay'])
        self.assertEqual(flow['draft']['source'], 'internal_hire')
        with self.assertRaises(UserError):
            self.JC.pb_start_for_employee(999999999)

    # ================================================================ JC2
    def test_jc02_one_route(self):
        emp, _c = self._person()
        small = self._rec(self._send(emp, new_wage=10_500_000.0))   # +5 %
        request = small.sudo().approval_request_id
        self.assertTrue(request, "sent in on the job change route")
        self.assertEqual(request.process_id.key, 'jobchange')
        included = {s.key: s.included for s in request.step_ids}
        self.assertTrue(included.get('mgr'), "their manager has a login")
        self.assertIn('hr', included)
        self.assertFalse(included.get('fin'), "Finance only above guidance")
        self.assertIn(self.mgr_user, small.sudo().seat_user_ids)
        small.action_cancel()
        big = self._rec(self._send(emp, new_wage=13_000_000.0))    # +30 %
        steps = {s.key: s.included for s in big.sudo().approval_request_id.step_ids}
        self.assertTrue(steps.get('fin'), "above the guidance: Finance signs")
        self.assertTrue(big.facts()['above_guidance']['value'])
        big.action_cancel()
        # no manager login: the manager step is left out, not blocked on
        emp2, _c2 = self._person(manager=self.boss2)
        rec = self._rec(self._send(emp2))
        steps = {s.key: s.included for s in rec.sudo().approval_request_id.step_ids}
        self.assertFalse(steps.get('mgr'))

    # ================================================================ JC3
    def test_jc03_apply_today_writes_everything_together(self):
        self._fast()
        emp, contract = self._person()
        with patch.object(type(self.JC), '_wage_code', lambda s, c: 'BASIC'):
            answer = self._send(emp)
        rec = self._rec(answer)
        self.assertEqual(rec.state, 'applied', answer)
        emp.invalidate_recordset()
        contract.invalidate_recordset()
        self.assertEqual(emp.job_id, self.job_b)
        self.assertEqual(emp.job_title, 'Senior Accountant')
        self.assertEqual(emp.department_id, self.dept_b)
        self.assertEqual(emp.parent_id, self.boss2)
        self.assertEqual(emp.work_location_id, self.loc)
        self.assertEqual(emp.resource_calendar_id, self.calendar2)
        self.assertEqual(contract.job_id, self.job_b, "contract job too (facts §1.1)")
        self.assertEqual(contract.department_id, self.dept_b)
        self.assertEqual(contract.resource_calendar_id, self.calendar2)
        self.assertEqual(contract.wage, 10_500_000.0)
        line = contract.advantages_ids.filtered(
            lambda l: l.advantage_template_code == 'SBMEAL')
        self.assertEqual(line.amount, 700_000.0)
        changes = self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', contract.id)])
        meal = changes.filtered(lambda c: c.advantage_template_code == 'SBMEAL')
        self.assertEqual(len(meal), 1)
        self.assertEqual(meal.effective_date, rec.effective_date, "dated")
        self.assertEqual((meal.old_amount, meal.new_amount), (500_000.0, 700_000.0))
        wage = changes.filtered(lambda c: c.advantage_template_code == 'BASIC')
        self.assertEqual((wage.old_amount, wage.new_amount),
                         (10_000_000.0, 10_500_000.0))
        apply_rows = rec.apply_ids
        self.assertEqual(len(apply_rows), 1)
        self.assertEqual(apply_rows.old_wage, 10_000_000.0)
        self.assertEqual(apply_rows.letter_state, 'none',
                         "the Pay job never prints a pay-review letter for it")
        self.assertTrue(rec.letter_id, "one letter")
        self.assertEqual(rec.letter_id.letter_type, 'promotion')
        summary = self.env['biz.audit.entry'].sudo().search([
            ('model_name', '=', 'hr.employee'), ('res_id', '=', emp.id),
            ('field_name', '=', 'pb_job_change')])
        self.assertEqual(len(summary), 1, "one event on the trail")

    # ================================================================ JC4
    def test_jc04_future_date_writes_nothing_until_the_day(self):
        self._fast()
        emp, contract = self._person()
        start = self._today() + timedelta(days=10)
        changes_before = self.env['hr.contract.advantage.change'].sudo().search_count([])
        rec = self._rec(self._send(emp, effective_date=fields.Date.to_string(start)))
        self.assertEqual(rec.state, 'scheduled')
        emp.invalidate_recordset()
        contract.invalidate_recordset()
        self.assertEqual(emp.job_id, self.job_a)
        self.assertEqual(emp.department_id, self.dept_a)
        self.assertEqual(contract.wage, 10_000_000.0)
        self.assertEqual(contract.advantages_ids.amount, 500_000.0)
        self.assertEqual(self.env['hr.contract.advantage.change'].sudo().search_count([]),
                         changes_before, "no dated row before the day")
        self.assertFalse(rec.apply_ids)
        # the job before the day: nothing
        tally = self.JC._cron_start_due()
        self.assertFalse(tally.get('started'))
        self.assertEqual(rec.state, 'scheduled')
        # on the day
        with patch.object(type(self.JC), '_today_for', lambda s, company=None: start):
            tally = self.JC._cron_start_due()
            self.assertEqual(tally.get('started'), 1)
            self.assertEqual(rec.state, 'applied')
            self.assertTrue(rec.started_by_job)
            emp.invalidate_recordset()
            contract.invalidate_recordset()
            self.assertEqual(emp.job_id, self.job_b)
            self.assertEqual(contract.wage, 10_500_000.0)
            # idempotent
            self.assertEqual(self.JC._cron_start_due(), {})
            self.assertEqual(len(rec.apply_ids), 1)

    # ================================================================ JC5
    def test_jc05_changed_underneath(self):
        emp, contract = self._person()
        rec = self._rec(self._send(emp))
        self.assertEqual(rec.state, 'pending')
        contract.sudo().write({'wage': 11_000_000.0})
        with self.assertRaises(UserError) as caught:
            rec.sudo()._approval_apply(rec.sudo().approval_request_id)
        self.assertIn('monthly pay', str(caught.exception))
        emp.invalidate_recordset()
        self.assertEqual(emp.job_id, self.job_a, "nothing written")
        # a scheduled one is sent back on its day
        self._fast()
        emp2, c2 = self._person()
        start = self._today() + timedelta(days=3)
        rec2 = self._rec(self._send(emp2, effective_date=fields.Date.to_string(start)))
        self.assertEqual(rec2.state, 'scheduled')
        dept_c = self.env['hr.department'].create(
            {'name': 'S8B Audit', 'company_id': self.company.id})
        emp2.sudo().write({'department_id': dept_c.id})
        with patch.object(type(self.JC), '_today_for', lambda s, company=None: start):
            tally = self.JC._cron_start_due()
        self.assertEqual(tally.get('returned'), 1)
        self.assertEqual(rec2.state, 'returned')
        self.assertIn('team', rec2.block_note)
        c2.invalidate_recordset()
        self.assertEqual(c2.wage, 10_000_000.0)

    # ================================================================ JC6
    def _done_slip(self, emp, contract, month_start, cfg=None):
        last = (month_start.replace(day=28) + timedelta(days=4))
        last = last - timedelta(days=last.day)
        vals = {'name': 'S8B slip', 'employee_id': emp.id,
                'contract_id': contract.id, 'date_from': month_start,
                'date_to': last, 'company_id': self.company.id}
        if cfg is not None:
            vals['formula_config_id'] = cfg.id
        slip = self.env['hr.payslip'].create(vals)
        slip.write({'state': 'done'})
        return slip

    def _scheme(self):
        type(self)._seq += 1
        return self.env['hr.formula.config'].create({
            'name': 'S8B Scheme %s' % self._seq, 'code': 'SBSCH%s' % self._seq,
            'country_code': 'VN', 'state': 'active', 'company_id': self.company.id,
            'cycle_type': 'end_cycle'})

    def test_jc06_past_date_in_a_paid_month(self):
        self._fast()
        emp, contract = self._person()
        today = self._today()
        month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        cfg = self._scheme()
        slip = self._done_slip(emp, contract, month, cfg)
        lines_before = json.dumps(slip.line_ids.read(['code', 'amount', 'total']),
                                  sort_keys=True, default=str)
        retro_before = self.env['hr.payroll.retro.adjustment'].sudo().search_count([]) \
            if 'hr.payroll.retro.adjustment' in self.env else 0
        start = month.replace(day=15)
        preview = self.Board.preview(self._vals(emp, effective_date=fields.Date.to_string(start)))
        self.assertTrue(preview['ok'], preview['problems'])
        self.assertEqual(preview['timing'], 'past')
        self.assertEqual(len(preview['paid']), 1)
        rec = self._rec(self._send(emp, effective_date=fields.Date.to_string(start)))
        self.assertEqual(rec.state, 'applied')
        self.assertEqual(len(rec.paid_months()), 1)
        self.assertEqual(rec.paid_months()[0]['config_id'], cfg.id)
        detail = self.Board.get_change(rec.id)
        self.assertTrue(detail['paid'])
        self.assertTrue(detail['retro'])
        meal = self.env['hr.contract.advantage.change'].sudo().search([
            ('contract_id', '=', contract.id), ('advantage_template_code', '=', 'SBMEAL')])
        self.assertEqual(meal.effective_date, start, "dated in the past month")
        # the door: a DRAFT re-work for this person and that month
        answer = self.Board.act(rec.id, 'rework')
        review = self.env['pb.retro.review'].browse(answer['review_id'])
        self.assertTrue(review.exists())
        self.assertEqual(review.state, 'draft')
        self.assertEqual(review.employee_ids, emp)
        self.assertEqual(review.month_from, month)
        self.assertEqual(review.config_id, cfg)
        # pressing again opens the same one
        self.assertEqual(self.Board.act(rec.id, 'rework')['review_id'], review.id)
        # C-6: no back-pay input, the paid payslip untouched
        if 'hr.payroll.retro.adjustment' in self.env:
            self.assertEqual(self.env['hr.payroll.retro.adjustment'].sudo().search_count([]),
                             retro_before)
        slip.invalidate_recordset()
        self.assertEqual(slip.state, 'done')
        self.assertEqual(json.dumps(slip.line_ids.read(['code', 'amount', 'total']),
                                    sort_keys=True, default=str), lines_before)
        # without the re-work module: a calm sentence, never an error page
        with patch.object(type(self.JC), '_retro_installed', lambda s: False):
            detail = self.Board.get_change(rec.id)
            self.assertFalse(detail['retro'])
            rec.sudo().rework_id = 0
            with self.assertRaises(UserError) as caught:
                rec.action_open_rework()
            self.assertIn('next pay run', str(caught.exception))

    # ================================================================ JC7
    def test_jc07_take_it_back(self):
        self._fast()
        emp, contract = self._person()
        rec = self._rec(self._send(emp))
        self.assertEqual(rec.state, 'applied')
        self.assertTrue(self.Board.get_change(rec.id)['undo'])
        self.Board.act(rec.id, 'undo')
        self.assertEqual(rec.state, 'undone')
        emp.invalidate_recordset()
        contract.invalidate_recordset()
        self.assertEqual(emp.job_id, self.job_a)
        self.assertEqual(emp.department_id, self.dept_a)
        self.assertEqual(emp.parent_id, self.boss)
        self.assertEqual(contract.job_id, self.job_a)
        self.assertEqual(contract.wage, 10_000_000.0)
        self.assertEqual(contract.advantages_ids.amount, 500_000.0)
        self.assertEqual(rec.apply_ids.state, 'undone')
        self.assertEqual(rec.letter_id.state, 'draft', "letter voided")
        # after the window: refused
        emp2, _c2 = self._person()
        rec2 = self._rec(self._send(emp2))
        rec2.sudo().undo_until = fields.Datetime.now() - timedelta(hours=1)
        with self.assertRaises(UserError):
            rec2.action_undo()
        # moved since: refused
        emp3, _c3 = self._person()
        rec3 = self._rec(self._send(emp3))
        emp3.sudo().write({'department_id': self.dept_a.id})
        with self.assertRaises(UserError):
            rec3.action_undo()

    # ================================================================ JC8
    def _user(self, login, groups, company=None):
        company = company or self.company
        return self.env['res.users'].create({
            'name': login, 'login': login, 'company_id': company.id,
            'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def test_jc08_rights(self):
        emp, _c = self._person()
        officer = self._user('s8b_officer', ['base.group_user', 'hr.group_hr_user'])
        board = self.Board.with_user(officer).with_context(allowed_company_ids=[self.company.id])
        self.assertFalse(board.get_board()['allowed'])
        with self.assertRaises(AccessError):
            board.send(self._vals(emp))
        hr_only = self._user('s8b_hrmgr', ['base.group_user', 'hr.group_hr_manager'])
        hr_board = self.Board.with_user(hr_only).with_context(
            allowed_company_ids=[self.company.id])
        flow = hr_board.get_flow(emp.id)
        self.assertFalse(flow['can_pay'])
        self.assertEqual(flow['now']['wage'], 0.0, "no figure for HR without pay rights")
        self.assertFalse(flow['lines'])
        with self.assertRaises(AccessError):
            hr_board.save(self._vals(emp))
        answer = hr_board.send(self._vals(emp, change_pay=False, lines=[]))
        rec = self.JC.browse(answer['id'])
        self.assertFalse(rec.change_pay)
        # the manager asked to decide reads their seat, nothing else
        self.env.flush_all()
        self.env.invalidate_all()
        mine = self.JC.with_user(self.mgr_user).with_context(
            allowed_company_ids=[self.company.id]).search([])
        self.assertEqual(mine, rec)
        self.assertTrue(rec.with_user(self.mgr_user).sudo(False)._approval_detail(
            rec.sudo().approval_request_id)['rows'])
        # another company's HR manager sees nothing
        stranger = self._user('s8b_stranger', ['base.group_user', 'hr.group_hr_manager',
                                               'pb_pay.group_pay_manager'], self.other)
        self.env.flush_all()
        self.env.invalidate_all()
        theirs = self.JC.with_user(stranger).with_context(
            allowed_company_ids=[self.other.id]).search([])
        self.assertFalse(theirs)
        with self.assertRaises(UserError):
            self.Board.with_user(stranger).with_context(
                allowed_company_ids=[self.other.id]).get_change(rec.id)

    # ================================================================ JC9
    def test_jc09_checks_before_sending(self):
        emp, _c = self._person()
        nothing = self.Board.preview({'employee_id': emp.id, 'reason': 'x',
                                      'effective_date': fields.Date.to_string(self._today())})
        self.assertFalse(nothing['ok'])
        self.assertTrue(any('Nothing changes' in p for p in nothing['problems']))
        own = self.Board.preview(self._vals(emp, new_parent_id=emp.id))
        self.assertTrue(any('own manager' in p for p in own['problems']))
        report, _rc = self._person(manager=emp)
        cycle = self.Board.preview(self._vals(emp, new_parent_id=report.id))
        self.assertTrue(any('reports to' in p for p in cycle['problems']))
        far = self.Board.preview(self._vals(emp, effective_date=fields.Date.to_string(
            self._today() + timedelta(days=400))))
        self.assertTrue(any('a year ahead' in p for p in far['problems']))
        why = self.Board.preview(self._vals(emp, reason=''))
        self.assertTrue(any('Say why' in p for p in why['problems']))
        with self.assertRaises(UserError):
            self.Board.send(self._vals(emp, reason=''))
        self._send(emp)
        again = self.Board.preview(self._vals(emp))
        self.assertTrue(any('already has a job change waiting' in p
                            for p in again['problems']))

    # ================================================================ JC10
    def test_jc10_letter_types(self):
        known = dict(self.env['pb.letter.template']._fields['letter_type'].selection)
        for key in ('promotion', 'transfer', 'job_change', 'pay_change', 'custom'):
            self.assertIn(key, known)
        known_letter = dict(self.env['pb.hr.letter']._fields['letter_type']
                            ._description_selection(self.env))
        self.assertIn('transfer', known_letter)
        self._fast()
        emp, _c = self._person()
        rec = self._rec(self._send(emp, reason_kind='transfer', change_pay=False, lines=[]))
        self.assertEqual(rec.letter_id.letter_type, 'transfer')

    # ================================================================ JC11
    def test_jc11_silent_install(self):
        cron = self.env.ref('pb_job_change.ir_cron_job_change_start_due')
        self.assertTrue(cron.active)
        process = self.env['biz.approval.process']._by_key('jobchange')
        self.assertTrue(process)
        self.assertEqual(process.model_name, 'pb.job.change')
        self.JC.sudo().search([]).unlink()
        self.assertEqual(self.JC._cron_start_due(), {}, "quiet on an empty set")
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id), ('process_id', '=', process.id),
            ('active', '=', True)])
        self.assertTrue(binding, "a new company gets the route")
        board = self.Board.get_board()
        self.assertTrue(board['allowed'])
        self.assertEqual(board['total'], 0)

    # ================================================================ JC12
    def test_jc12_paid_by_what_if_is_read_only(self):
        emp, _c = self._person()
        Map = self.env['pb.scheme.map']
        plain = Map._departments_for(employee_ids=[emp.id])
        self.assertEqual(plain[emp.id][0], self.dept_a.id)
        moved = Map.with_context(pb_jc_department_override={
            emp.id: (self.dept_b.id, self.company.id)})._departments_for(
                employee_ids=[emp.id])
        self.assertEqual(moved[emp.id][0], self.dept_b.id)
        emp.invalidate_recordset()
        self.assertEqual(emp.department_id, self.dept_a, "nothing written")
        # a scheme change is shown and is a route fact
        now = {'config_id': 1, 'config_name': 'Office'}
        after = {'config_id': 2, 'config_name': 'Shop floor'}
        calls = []

        def fake(self_map, employee, cycle_type='any', on_date=None):
            calls.append(self_map.env.context.get('pb_jc_department_override'))
            return after if self_map.env.context.get('pb_jc_department_override') else now
        with patch.object(type(Map), 'resolve', fake):
            preview = self.Board.preview(self._vals(emp))
        self.assertTrue(preview['changes_scheme'])
        self.assertEqual((preview['scheme_now'], preview['scheme_after']),
                         ('Office', 'Shop floor'))

    # ================================================================ JC13
    def test_jc13_golden_finished_payslip_untouched(self):
        self._fast()
        emp, contract = self._person()
        month = self._today().replace(day=1)
        slip = self._done_slip(emp, contract, (month - timedelta(days=1)).replace(day=1))
        rule = self.env['hr.salary.rule'].search([], limit=1)
        if not rule:
            self.skipTest('no salary rule on this database')
        self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'name': 'Basic', 'code': 'BASIC',
            'salary_rule_id': rule.id,
            'category_id': self.env.ref('om_hr_payroll.BASIC').id,
            'contract_id': contract.id, 'employee_id': emp.id,
            'amount': 10_000_000.0, 'quantity': 1, 'rate': 100})
        self.env.flush_all()
        snap = json.dumps(slip.line_ids.read(['code', 'amount', 'total', 'quantity']),
                          sort_keys=True, default=str)
        self._send(emp)
        self.env.flush_all()
        slip.invalidate_recordset()
        self.assertEqual(json.dumps(slip.line_ids.read(['code', 'amount', 'total', 'quantity']),
                                    sort_keys=True, default=str), snap)
        self.assertEqual(slip.state, 'done')

    # ================================================================ JC14
    def test_jc14_timeline_one_event(self):
        self._fast()
        emp, _c = self._person()
        self._send(emp)
        items = self.env['pb.employee.timeline']._collect(emp, True)
        titles = [it['title'] for it in items]
        self.assertEqual(sum(1 for t in titles if t.startswith('Job changed')), 1)
        self.assertFalse(any(t.startswith('Job change updated') for t in titles),
                         "the summary trail line is folded into the event")
        self.assertFalse(any(t in ('Department updated', 'Manager updated')
                             for t in titles), "field lines folded away")
        job_item = [it for it in items if it['title'].startswith('Job changed')][0]
        self.assertIn('S8B Tax', job_item['detail'])

    # ================================================================ JC15
    def _seat(self, role_key, user):
        role = self.env['biz.approval.role'].sudo().search([('key', '=', role_key)], limit=1)
        Resp = self.env['biz.approval.responsibility'].sudo()
        Resp.with_context(active_test=False).search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'active': False})
        Resp.create({'company_id': self.company.id, 'role_id': role.id,
                     'scope_key': '', 'user_id': user.id})

    def test_jc15_signed_off_by_people_without_hr_rights(self):
        """The real route, decided seat by seat: their line manager (a plain
        login, ledger W2B-2), the HR lead, then Finance because the rise is
        above the guidance. The last decider writes it."""
        hr_lead = self._user('s8b_hrlead', ['base.group_user', 'hr.group_hr_manager'])
        finance = self._user('s8b_fin', ['base.group_user'])    # no HR, no payroll
        self._seat('hr_lead', hr_lead)
        self._seat('finance', finance)
        emp, contract = self._person()
        rec = self._rec(self._send(emp, new_wage=13_000_000.0))
        Engine = self.env['biz.approval.engine']
        order = []
        for _guard in range(5):
            request = rec.sudo().approval_request_id
            if request.state not in ('pending', 'blocked'):
                break
            self.assertEqual(request.state, 'pending', request.block_reason)
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            order.append(step.key)
            self.env.flush_all()
            self.env.invalidate_all()
            Engine.with_user(seat.acting_user_id).with_context(
                allowed_company_ids=[self.company.id]).decide(
                    request.id, step.key, 'approve', 'ok')
            rec.invalidate_recordset()
        self.assertEqual(order, ['mgr', 'hr', 'fin'])
        self.assertEqual(rec.state, 'applied', rec.block_note)
        self.assertEqual(rec.applied_by, finance)
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 13_000_000.0)
        self.assertEqual(contract.job_id, self.job_b)
