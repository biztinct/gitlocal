# -*- coding: utf-8 -*-
"""UPDATES P2c — start dates, the scheduled job, Start now, Cancel and the
employee look-ups (handover cases C1-C12, C16, C17 and the Records half of
C18). The Updates half (C13-C15, C19) is in `pb_updates`.

Everything runs in a company of its own whose address is in Ho Chi Minh City
(UTC+7), with a FROZEN clock (`pb.records.apply._records_now`): "today" for
the company is 11 Nov 2026 unless a test moves the clock. No payslip is
touched.
"""
from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

JOB = 'f:hr.employee:job_title'
MANAGER = 'f:hr.employee:parent_id'
COACH = 'f:hr.employee:coach_id'
WAGE = 'f:hr.contract:wage'
X = 'c:P2CX'

NOW = datetime(2026, 11, 11, 3, 0)          # 10:00 in Ho Chi Minh City
TODAY = date(2026, 11, 11)
FUTURE = '2026-12-01'
PAST = '2026-10-01'


class _P2cBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        cls.company = cls.env['res.company'].create(
            {'name': 'P2C Fixture Co', 'currency_id': vnd.id})
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id]))
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.company, 'records')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.proposer = Users.create({
            'name': 'P2C Proposer', 'login': 'p2c_proposer', 'tz': 'Asia/Ho_Chi_Minh',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('hr.group_hr_user').id,
                                  cls.env.ref('pb_records.group_records_editor').id])]})
        cls.calendar = cls.company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'P2C Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P2C Kind'})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P2C Boss', 'barcode': 'P2CB01',
                               'work_email': 'boss.p2c@example.com',
                               'company_id': cls.company.id})
        cls.ann = Emp.create({'name': 'P2C Ann', 'barcode': 'P2C0001',
                              'company_id': cls.company.id, 'job_title': 'Operator'})
        cls.bob = Emp.create({'name': 'P2C Bob', 'barcode': 'P2C0002',
                              'company_id': cls.company.id, 'job_title': 'Operator'})
        cls.contracts = {}
        for person in (cls.ann, cls.bob, cls.boss):
            cls.contracts[person.id] = cls.env['hr.contract'].create({
                'name': 'P2C contract %s' % person.name, 'employee_id': person.id,
                'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
                'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
                'type_id': cls.kind.id})
        cls.template = cls.env['hr.contract.advantage.template'].create({
            'name': 'P2C Site allowance', 'code': 'P2CX', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0, 'value_type': 'amount'})
        for person in (cls.ann, cls.bob):
            cls.env['hr.contract.advantage'].create({
                'contract_id': cls.contracts[person.id].id,
                'advantage_template_id': cls.template.id, 'amount': 100.0})
        cls.Apply = cls.env['pb.records.apply']

    def setUp(self):
        super().setUp()
        self.clock = NOW
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    @property
    def D(self):
        """The desk as the proposer, in the fixture company."""
        return self.env['pb.records.desk'].with_user(self.proposer).with_context(
            allowed_company_ids=[self.company.id])

    def changes(self, person, job='Lead', wage='1500', x='200'):
        out = []
        if job is not None:
            out.append({'emp_id': person.id, 'field_id': JOB, 'value': job})
        if wage is not None:
            out.append({'emp_id': person.id, 'field_id': WAGE, 'value': wage})
        if x is not None:
            out.append({'emp_id': person.id, 'field_id': X, 'value': x})
        return out

    def line(self, person):
        return self.contracts[person.id].advantages_ids.filtered(
            lambda l: l.advantage_template_id.code == 'P2CX')

    def snapshot(self, person):
        person.invalidate_recordset()
        contract = self.contracts[person.id]
        contract.invalidate_recordset()
        return (person.job_title, contract.wage, self.line(person).amount)

    def component_rows(self, apply_rec):
        return self.env['hr.contract.advantage.change'].sudo().search(
            [('notes', '=', 'Records Desk apply #%s' % apply_rec.id)])

    def run_job(self):
        return self.Apply._cron_start_scheduled()


@tagged('post_install', '-at_install', 'pb_records', 'pb_records_p2c')
class TestRecordsP2cDates(_P2cBase):

    # ================================================================ C1
    def test_C1_no_date_and_today_take_todays_path(self):
        before = self.snapshot(self.ann)
        plain = self.D.apply_changes(0, self.changes(self.ann), note='C1 plain')
        today = self.D.apply_changes(0, self.changes(self.bob), note='C1 today',
                                     start_date=fields.Date.to_string(TODAY))
        for answer in (plain, today):
            self.assertTrue(answer['ok'])
            self.assertFalse(answer['pending'])
            self.assertFalse(answer['scheduled'])
            self.assertEqual(answer['written'], 3)
        a, b = self.Apply.browse(plain['apply_id']), self.Apply.browse(today['apply_id'])
        self.assertFalse(a.start_date, "no date stays no date")
        self.assertFalse(b.start_date, "today is stored as 'no date': today's path")
        self.assertEqual((a.state, a.applied), ('applied', True))
        self.assertEqual((b.state, b.applied), ('applied', True))
        self.assertNotEqual(self.snapshot(self.ann), before)
        self.assertEqual(self.snapshot(self.ann), ('Lead', 1500.0, 200.0))
        shape = lambda rec: sorted((c.field_key, c.old_json, c.new_json, c.model)
                                   for c in rec.change_ids)
        self.assertEqual(shape(a), shape(b))
        real_today = fields.Date.context_today(self.D)
        self.assertEqual(set(a.change_ids.mapped('effective_date')), {real_today})
        self.assertEqual(self.component_rows(a).effective_date, real_today)
        self.assertEqual(self.component_rows(b).effective_date, real_today)

    # ================================================================ C2
    def test_C2_a_past_date_is_written_now_and_recorded_with_it(self):
        before = self.snapshot(self.ann)
        answer = self.D.apply_changes(0, self.changes(self.ann, job=None),
                                      note='C2', start_date=PAST)
        self.assertTrue(answer['ok'])
        self.assertFalse(answer['scheduled'])
        self.assertEqual(answer['written'], 2)
        rec = self.Apply.browse(answer['apply_id'])
        self.assertEqual(rec.start_date, date(2026, 10, 1))
        self.assertEqual(self.snapshot(self.ann), ('Operator', 1500.0, 200.0))
        self.assertEqual(set(rec.change_ids.mapped('effective_date')), {date(2026, 10, 1)})
        self.assertEqual(self.component_rows(rec).effective_date, date(2026, 10, 1))
        undo = self.D.undo_apply(rec.id)
        self.assertTrue(undo['ok'])
        self.assertEqual(undo['restored'], 2)
        self.assertEqual(self.snapshot(self.ann), before)
        undo_rec = self.Apply.browse(undo['apply_id'])
        real_today = fields.Date.context_today(self.D)
        self.assertEqual(set(undo_rec.change_ids.mapped('effective_date')), {real_today},
                         "an undo is stamped today")
        self.assertEqual(self.component_rows(undo_rec).effective_date, real_today)

    # ================================================================ C3
    def test_C3_a_future_date_is_held(self):
        before = self.snapshot(self.ann)
        answer = self.D.apply_changes(0, self.changes(self.ann), note='C3',
                                      start_date=FUTURE)
        self.assertTrue(answer['ok'])
        self.assertTrue(answer['scheduled'])
        self.assertFalse(answer['pending'])
        self.assertEqual(answer['written'], 0)
        self.assertEqual(answer['start_date'], FUTURE)
        rec = self.Apply.browse(answer['apply_id'])
        self.assertEqual(rec.state, 'scheduled')
        self.assertFalse(rec.applied)
        self.assertFalse(rec.change_ids)
        self.assertEqual(rec.hold_scope, 'pay')
        self.assertEqual(self.snapshot(self.ann), before)

    def test_C3b_bounds(self):
        count = self.Apply.search_count([])
        far = self.D.apply_changes(0, self.changes(self.ann), start_date='2028-01-01')
        self.assertFalse(far['ok'])
        self.assertIn('up to a year back or a year ahead', far['msg'])
        self.assertEqual(self.Apply.search_count([]), count, "nothing proposed")
        edge = self.D.apply_changes(0, self.changes(self.ann), start_date='2027-11-12')
        self.assertTrue(edge['ok'] and edge['scheduled'], "366 days ahead is allowed")
        bad = self.D.apply_changes(0, self.changes(self.ann), start_date='soon')
        self.assertFalse(bad['ok'])
        self.assertIn('is not a date', bad['msg'])

    # ================================================================ C5 / C6
    def test_C5_the_job_writes_it_on_the_day(self):
        answer = self.D.apply_changes(0, self.changes(self.ann), note='C5',
                                      start_date=FUTURE)
        rec = self.Apply.browse(answer['apply_id'])
        self.assertEqual(self.run_job(), {}, "before the day the job does nothing")
        self.clock = datetime(2026, 12, 1, 3, 0)
        tally = self.run_job()
        self.assertEqual(tally, {'started': 1})
        rec.invalidate_recordset()
        self.assertTrue(rec.applied)
        self.assertEqual(rec.state, 'applied')
        self.assertTrue(rec.started_by_job)
        self.assertEqual(rec.started_by_id, self.proposer, "the audit names the proposer")
        self.assertEqual(rec.count_values, 3)
        self.assertEqual(self.snapshot(self.ann), ('Lead', 1500.0, 200.0))
        self.assertEqual(set(rec.change_ids.mapped('effective_date')), {date(2026, 12, 1)})
        self.assertEqual(self.component_rows(rec).effective_date, date(2026, 12, 1))
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.write_uid, self.proposer, "written as the proposer")
        self.assertEqual(self.run_job(), {}, "never twice")

    def test_C6_company_time_zone_ahead_of_utc(self):
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        self.clock = datetime(2026, 11, 30, 16, 0)     # 23:00 on 30 Nov in HCMC
        self.assertEqual(self.run_job(), {})
        self.assertFalse(rec.applied)
        self.clock = datetime(2026, 11, 30, 17, 30)    # 00:30 on 1 Dec in HCMC
        self.assertEqual(self.run_job(), {'started': 1})
        rec.invalidate_recordset()
        self.assertTrue(rec.applied)

    def test_C6b_company_time_zone_behind_utc(self):
        self.company.partner_id.tz = 'America/New_York'
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        self.assertEqual(rec.state, 'scheduled')
        self.clock = datetime(2026, 12, 1, 3, 0)       # 22:00 on 30 Nov in New York
        self.assertEqual(self.run_job(), {}, "still 30 Nov for the company")
        self.assertFalse(rec.applied)
        self.clock = datetime(2026, 12, 1, 5, 30)      # 00:30 on 1 Dec in New York
        self.assertEqual(self.run_job(), {'started': 1})

    # ================================================================ C7
    def test_C7_moved_since_sends_it_back_and_tells_the_proposer(self):
        before_wage = self.contracts[self.ann.id].wage
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), note='C7', start_date=FUTURE)['apply_id'])
        self.ann.sudo().job_title = 'Somebody else'
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {'returned': 1})
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'returned')
        self.assertFalse(rec.applied)
        self.assertIn('changed by somebody else', rec.block_note)
        self.assertEqual(self.snapshot(self.ann), ('Somebody else', before_wage, 100.0),
                         "nothing at all was written")
        activity = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'biz.approval.request'),
            ('res_id', '=', rec.approval_request_id.id)])
        self.assertEqual(activity.user_id, self.proposer)
        self.assertIn(rec.name, activity.summary)
        self.assertEqual(self.run_job(), {}, "never retried silently")

    # ================================================================ C8
    def test_C8_one_failure_never_stops_the_rest(self):
        bad = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), note='C8 bad', start_date=FUTURE)['apply_id'])
        good = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.bob), note='C8 good', start_date=FUTURE)['apply_id'])
        Desk = type(self.env['pb.records.desk'])
        original = Desk._write_plan

        def flaky(desk, apply_rec):
            if apply_rec.id == bad.id:
                raise RuntimeError('boom')
            return original(desk, apply_rec)

        with patch.object(Desk, '_write_plan', flaky), \
                patch('odoo.addons.pb_records.models.records_approval._logger.exception'):
            self.clock = datetime(2026, 12, 1, 3, 0)
            self.assertEqual(self.run_job(), {'failed': 1, 'started': 1})
            good.invalidate_recordset()
            bad.invalidate_recordset()
            self.assertTrue(good.applied)
            self.assertEqual(self.snapshot(self.bob), ('Lead', 1500.0, 200.0))
            self.assertEqual(bad.state, 'scheduled')
            self.assertFalse(bad.applied)
            self.assertIn('it will be tried again', bad.block_note)
            self.assertEqual(self.snapshot(self.ann), ('Operator', 1000.0, 100.0))
            self.assertEqual(bad.start_fail_days, 1)
            self.clock = datetime(2026, 12, 1, 4, 0)      # same day: still one day
            self.run_job()
            bad.invalidate_recordset()
            self.assertEqual(bad.start_fail_days, 1)
            self.clock = datetime(2026, 12, 2, 3, 0)
            self.run_job()
            self.clock = datetime(2026, 12, 3, 3, 0)
            self.run_job()
            bad.invalidate_recordset()
            self.assertEqual(bad.start_fail_days, 3)
            self.assertEqual(bad.state, 'returned', "third bad day: sent back")
            self.assertIn('three different days', bad.block_note)
        self.assertTrue(self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'biz.approval.request'),
            ('res_id', '=', bad.approval_request_id.id)]))

    # ================================================================ C9
    def test_C9_start_now(self):
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), note='C9', start_date=FUTURE)['apply_id'])
        answer = self.D.start_now(rec.id)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(answer['written'], 3)
        rec.invalidate_recordset()
        self.assertTrue(rec.applied)
        self.assertFalse(rec.started_by_job)
        self.assertEqual(rec.start_date, date(2026, 12, 1), "the start date is kept")
        self.assertEqual(set(rec.change_ids.mapped('effective_date')), {TODAY},
                         "it really started today")
        self.assertEqual(self.snapshot(self.ann), ('Lead', 1500.0, 200.0))
        rows = len(rec.change_ids)
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {})
        rec.invalidate_recordset()
        self.assertEqual(len(rec.change_ids), rows, "the job later does nothing")
        again = self.D.start_now(rec.id)
        self.assertFalse(again['ok'])

    def test_C9b_start_now_on_a_conflict_leaves_it_scheduled(self):
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        self.ann.sudo().job_title = 'Moved'
        answer = self.D.start_now(rec.id)
        self.assertFalse(answer['ok'])
        self.assertIn('changed by somebody else', answer['msg'])
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'scheduled', "a person pressing never sends it back")

    # ================================================================ C10
    def test_C10_locked_by_somebody_else_writes_nothing(self):
        """The in-transaction half of C10: when the row lock is held by
        another transaction (`_lock_row` False), neither the job nor Start
        now writes. The real two-connection race runs outside the suite
        (it must COMMIT): `UPDATES_P2C_REPORT.md` R1, script `c10_race.py`."""
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        Apply = type(rec)
        with patch.object(Apply, '_lock_row', lambda _self, wait=False: False):
            self.assertEqual(self.D.start_now(rec.id)['outcome'], 'busy')
            self.clock = datetime(2026, 12, 1, 3, 0)
            self.assertEqual(self.run_job(), {'busy': 1})
        rec.invalidate_recordset()
        self.assertFalse(rec.applied)
        self.assertFalse(rec.change_ids)

    # ================================================================ C11 / C12
    def test_C11_cancel_a_scheduled_change(self):
        before = self.snapshot(self.ann)
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        answer = self.D.cancel_apply(rec.id)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(answer['msg'], 'Cancelled before anything was changed.')
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'cancelled')
        self.assertEqual(rec.cancelled_by_id, self.proposer)
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.run_job(), {})
        with self.assertRaises(UserError):
            rec._approval_apply(rec.approval_request_id)
        self.assertFalse(self.D.start_now(rec.id)['ok'])
        self.assertEqual(self.snapshot(self.ann), before)
        self.assertFalse(self.D.cancel_apply(rec.id)['ok'], "only once")

    def test_C11c_who_may_cancel(self):
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        stranger = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P2C Stranger', 'login': 'p2c_stranger',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id])]})
        answer = self.env['pb.records.desk'].with_user(stranger).with_context(
            allowed_company_ids=[self.company.id]).cancel_apply(rec.id)
        self.assertFalse(answer['ok'])
        self.assertIn('Only the person who proposed', answer['msg'])
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'scheduled')

    def test_C12_undo_on_an_unwritten_change_cancels_it(self):
        before = self.snapshot(self.ann)
        rec = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), start_date=FUTURE)['apply_id'])
        undo = self.D.undo_apply(rec.id)
        self.assertTrue(undo['ok'])
        self.assertTrue(undo['cancelled'])
        self.assertEqual(undo['restored'], 0)
        self.assertEqual(undo['msg'], 'Cancelled before anything was changed.')
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'cancelled')
        self.assertFalse(rec.undone, "no empty 'undone' mark any more")
        self.assertFalse(self.Apply.search([('source', '=', 'undo'),
                                            ('note', '=', 'Undo of %s' % rec.name)]),
                         "no empty undo row")
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.run_job()
        self.assertEqual(self.snapshot(self.ann), before, "never written afterwards")

    # ================================================================ C17
    def test_C17_manager_by_code_email_and_name(self):
        twin1 = self.env['hr.employee'].create({'name': 'P2C Twin', 'barcode': 'P2CT1',
                                                'work_email': 'twin1.p2c@example.com',
                                                'company_id': self.company.id})
        self.env['hr.employee'].create({'name': 'P2C Twin', 'barcode': 'P2CT2',
                                        'company_id': self.company.id})
        count = self.env['hr.employee'].search_count([])

        def judge(value, field=MANAGER, desk=None):
            # (an AbstractModel recordset is empty, so never `desk or …`)
            desk = self.D if desk is None else desk
            return desk.preview_changes(0, [{'emp_id': self.ann.id, 'field_id': field,
                                             'value': value}])['items'][0]

        for text in ('P2CB01', 'p2cb01', ' P2CB01 '):
            item = judge(text)
            self.assertEqual((item['status'], item['new_label']), ('ok', 'P2C Boss'), text)
        item = judge('BOSS.P2C@example.com')
        self.assertEqual((item['status'], item['new_label']), ('ok', 'P2C Boss'))
        self.assertEqual(judge('p2c boss')['new_label'], 'P2C Boss')
        self.assertEqual(judge('P2CT1', COACH)['new_label'], 'P2C Twin', "coach too")
        self.assertEqual(judge('twin1.p2c@example.com')['status'], 'ok')
        # Namesakes: the Records screen keeps its sentence; a file is told
        # what to type instead.
        screen = judge('P2C Twin')
        self.assertEqual(screen['status'], 'refused')
        self.assertIn('Pick the right one on the Records screen', screen['why'])
        from_file = judge('P2C Twin', desk=self.D.with_context(records_from_file=True))
        self.assertEqual(from_file['why'], "2 people are called 'P2C Twin'. Type the "
                         "employee code or work email of the right one instead.")
        nobody = judge('Nobody P2C')
        self.assertEqual(nobody['status'], 'refused')
        self.assertEqual(nobody['why'], "Nobody is called 'Nobody P2C'. Check the "
                         "spelling, or use their employee code or work email.")
        self.assertNotIn('(new)', nobody['new_label'])
        res = self.D.apply_changes(0, [{'emp_id': self.ann.id, 'field_id': MANAGER,
                                        'value': 'Nobody P2C'}], source='import')
        self.assertFalse(res['apply_id'])
        self.assertEqual(self.env['hr.employee'].search_count([]), count,
                         "an employee is never created")
        # The import door says the file sentence.
        self.assertIn('Type the employee code', [
            r for r in self.D.apply_changes(0, [{'emp_id': self.ann.id, 'field_id': MANAGER,
                                                 'value': 'P2C Twin'}], source='import')['refused']
        ][0]['why'])

    # ================================================================ C18
    def test_C18_history_shows_scheduled_and_cancelled(self):
        kept = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.ann), note='C18 kept', start_date=FUTURE)['apply_id'])
        gone = self.Apply.browse(self.D.apply_changes(
            0, self.changes(self.bob), note='C18 gone', start_date=FUTURE)['apply_id'])
        self.D.cancel_apply(gone.id)
        rows = {r['id']: r for r in self.D.get_history(50)['applies']}
        self.assertTrue(rows[kept.id]['scheduled'])
        self.assertTrue(rows[kept.id]['can_cancel'])
        self.assertEqual(rows[kept.id]['start_date'], FUTURE)
        self.assertEqual(rows[kept.id]['state_label'], 'Scheduled')
        self.assertTrue(rows[gone.id]['cancelled'])
        self.assertFalse(rows[gone.id]['can_cancel'])
        self.assertEqual(rows[gone.id]['state_label'], 'Cancelled')


@tagged('post_install', '-at_install', 'pb_records', 'pb_records_p2c')
class TestRecordsP2cRoute(TransactionCase):
    """C4, C11 (pending) and C12 with a real approval route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('hr.group_hr_user').id]
        cls.hr_lead = Users.create({'name': 'P2C HR Lead', 'login': 'p2c_hr_lead',
                                    'group_ids': [(6, 0, groups)]})
        cls.finance = Users.create({'name': 'P2C Finance', 'login': 'p2c_finance',
                                    'group_ids': [(6, 0, groups)]})
        for key, user in (('hr_lead', cls.hr_lead), ('finance', cls.finance)):
            role = cls.env['biz.approval.role'].sudo().search([('key', '=', key)], limit=1)
            if not role:
                continue
            held = cls.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', cls.company.id), ('role_id', '=', role.id),
                ('scope_key', '=', '')], limit=1)
            if held:
                held.write({'user_id': user.id, 'active': True})
            else:
                cls.env['biz.approval.responsibility'].sudo().create({
                    'company_id': cls.company.id, 'role_id': role.id, 'scope_key': '',
                    'scope_label': cls.company.name, 'user_id': user.id,
                    'date_from': date(2020, 1, 1)})
        cls.env['pb.records.apply']._approval_seed_default(cls.company)
        cls.person = cls.env['hr.employee'].create({
            'name': 'P2C Routed', 'company_id': cls.company.id, 'job_title': 'Before'})
        cls.Desk = cls.env['pb.records.desk']
        cls.Engine = cls.env['biz.approval.engine']
        cls.Apply = cls.env['pb.records.apply']

    def setUp(self):
        super().setUp()
        self.clock = NOW
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def propose(self, value='After'):
        answer = self.Desk.apply_changes(0, [{'emp_id': self.person.id, 'field_id': JOB,
                                              'value': value}], note='P2C route',
                                         start_date=FUTURE)
        self.assertTrue(answer['pending'], answer)
        return self.Apply.browse(answer['apply_id'])

    def approve_all(self, rec):
        for _guard in range(6):
            request = rec.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.Engine.with_user(seat.acting_user_id).decide(request.id, step.key,
                                                              'approve', 'ok')
            rec.invalidate_recordset()
        self.fail('never finished')

    def test_C4_approved_then_scheduled(self):
        rec = self.propose()
        self.assertEqual(rec.state, 'pending')
        self.approve_all(rec)
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'scheduled')
        self.assertFalse(rec.applied)
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_title, 'Before', "nothing written on approval")
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(rec._cron_start_scheduled(), {'started': 1})
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_title, 'After')

    def test_C11b_cancel_a_pending_change_withdraws_the_request(self):
        rec = self.propose()
        request = rec.approval_request_id
        answer = self.Desk.cancel_apply(rec.id)
        self.assertTrue(answer['ok'], answer.get('msg'))
        rec.invalidate_recordset()
        request.invalidate_recordset()
        self.assertEqual(rec.state, 'cancelled')
        self.assertEqual(request.state, 'cancelled', "withdrawn through the engine")
        step = request.step_ids.filtered(lambda s: s.key == 's1')[:1]
        with self.assertRaises(Exception):
            self.Engine.with_user(self.hr_lead).decide(request.id, step.key, 'approve', 'late')
        with self.assertRaises(UserError):
            rec._approval_apply(request)
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(rec._cron_start_scheduled(), {})
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_title, 'Before')

    def test_C12b_undo_on_a_pending_change_cancels_it_for_real(self):
        rec = self.propose()
        undo = self.Desk.undo_apply(rec.id)
        self.assertTrue(undo['ok'])
        self.assertTrue(undo['cancelled'])
        rec.invalidate_recordset()
        self.assertEqual(rec.state, 'cancelled')
        self.assertEqual(rec.approval_request_id.state, 'cancelled')
        with self.assertRaises(UserError):
            rec._approval_apply(rec.approval_request_id)
        self.person.invalidate_recordset()
        self.assertEqual(self.person.job_title, 'Before', "the defect: never written later")


@tagged('post_install', '-at_install', 'pb_records', 'pb_records_p2c')
class TestRecordsP2cPayrun(_P2cBase):
    """C16 — what the pay run's preparation says."""

    def preparation(self):
        from odoo.addons.pb_hr_payroll_formula.models.payroll_preparation import _CTX, _TOKEN
        cfg = self.env['hr.formula.config'].create({
            'name': 'P2C Run scheme', 'code': 'P2CRUN', 'country_code': 'VN',
            'company_id': self.company.id, 'state': 'active'})
        return self.env['hr.payroll.preparation'].sudo().with_context(**{_CTX: _TOKEN}).create({
            'config_id': cfg.id, 'owner_id': self.env.uid,
            'date_from': '2026-12-01', 'date_to': '2026-12-31',
            'scope_key': 'p2c-test-scope',
            'employee_ids': [(6, 0, [self.ann.id, self.bob.id])]})

    def test_C16_scheduled_inside_after_cancelled_pending(self):
        prep = self.preparation()
        self.assertEqual(prep._records_scheduled(), [], "nothing scheduled, nothing said")
        inside = self.D.apply_changes(0, self.changes(self.ann), start_date='2026-12-10')
        self.D.apply_changes(0, self.changes(self.bob, job=None, x=None),
                             start_date='2026-12-10')
        after = self.D.apply_changes(0, self.changes(self.bob, job='After', wage=None, x=None),
                                     start_date='2027-01-05')
        cancelled = self.D.apply_changes(0, [{'emp_id': self.ann.id, 'field_id': JOB,
                                              'value': 'Gone'}], start_date='2026-12-15')
        self.D.cancel_apply(cancelled['apply_id'])
        lines = prep._records_scheduled()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(lines[0]['date'], '2026-12-10')
        self.assertEqual(lines[0]['count'], 4)
        self.assertEqual(lines[0]['people'], 2)
        self.assertIn('4 scheduled changes start on', lines[0]['message'])
        self.assertIn('inside this pay period', lines[0]['message'])
        self.assertIn('unless you start them now', lines[0]['message'])
        self.assertTrue(inside['scheduled'] and after['scheduled'])

    def test_C16b_pending_wording_unchanged_cancelled_worded(self):
        prep = self.preparation()
        pending = self.Apply.sudo().create({'name': 'P2C pending', 'state': 'pending',
                                            'company_id': self.company.id})
        gone = self.Apply.sudo().create({'name': 'P2C gone', 'state': 'cancelled',
                                         'company_id': self.company.id})
        waiting = 'Saved record change is waiting for approval.'

        def base(_self, row, edits, strict=False):
            for cell in row['inputs']:
                cell.update(status='conflict', reason=waiting)
            row['blockers'] = [{'code': c['code'], 'key': c['code'], 'reason': waiting}
                               for c in row['inputs']]
            return row

        from odoo.addons.pb_hr_payroll_formula.models import payroll_preparation as prep_mod
        row = {'employee_id': self.ann.id, 'blockers': [],
               'inputs': [{'code': 'A'}, {'code': 'B'}]}
        edits = {'%s:A' % self.ann.id: {'proposal_id': pending.id},
                 '%s:B' % self.ann.id: {'proposal_id': gone.id}}
        with patch.object(prep_mod.PayrollPreparation, '_apply_row', base):
            out = prep._apply_row(row, edits)
        reasons = {c['code']: c['reason'] for c in out['inputs']}
        self.assertEqual(reasons['A'], waiting, "waiting for approval: exactly as before")
        self.assertIn('was cancelled', reasons['B'])
        self.assertIn('was cancelled', [b for b in out['blockers'] if b['code'] == 'B'][0]['reason'])
