# -*- coding: utf-8 -*-
"""WDGAP S8-D — "Raise the scale" in one request (owner rulings SC1, SC2).

Numbered as in the S8-D report (§3, SC1 rows):

R1  preview maths: by a percentage on an amounts scale — On-scale people move
    to their new step, a drifted person below it moves up too (marked), a
    person paid above the new step keeps their pay ("above step", SC2), a
    Pinned person is untouched, a contract ending before the date cannot move
    (plain reason); a flat amount; a typed table may not lower a step.
R2  the real cost, per currency: worked out through the person's own pay
    rules (basic + the employer's contribution on it), a month and twelve
    months; a person paid in another currency cannot move and adds nothing.
R3  route: the process row and the seeded route (HR lead → Finance, no
    manager step); the preparer is the maker (independence); decided seat by
    seat, Finance holding no pay role — the last decision writes it.
R4  GOLDEN: preparing, previewing, leaving people out, sending and a refusal
    write NO contract, pay line, amount-change row, payslip or pay record.
R5  approved for today: wages written, one DATED amount-change row per person
    ("From the pay scale"), one pay record each, the new version in force,
    the people On scale; above-step and pinned people untouched; one letter
    per moved person.
R6  future date: approved → "starts later", nothing on any contract, the new
    version waits (a joiner from that day starts on it); the hourly job does
    nothing before the day, writes it on the day, and a second run (and a
    second write) changes nothing.
R7  take it back before the day: the version goes, nobody's pay changed;
    once started it can no longer be taken back.
R8  a person whose pay changed after sending is skipped with the reason; the
    others move.
R9  a past date: the months already paid are listed; the Past-month re-work
    opened from the rise finds the difference (C-6: no back-pay input
    written here).
R10 rights: a plain user reads nothing and prepares nothing; a pay viewer
    reads and cannot prepare.
R11 silent install: the hourly job on an empty set does nothing; a new
    company gets the route.
R12 SC2 on the chip: paid above their step reads "Above step" and is never
    offered "Bring to step"; paid exactly another step gets "Mark on step N".
"""
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged


@contextmanager
def spy_writes(tables):
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lower()
        if text.lstrip()[:7].startswith(('insert', 'update', 'delete')):
            for table in tables:
                if re.search(r'\b%s\b' % re.escape(table), text):
                    seen.append(text[:120])
        return real(self, query, params, log_exceptions)

    with patch.object(Cursor, 'execute', execute):
        yield seen


PAY_TABLES = ('hr_contract', 'hr_contract_advantage', 'hr_contract_advantage_change',
              'hr_payslip', 'hr_payslip_line', 'pb_pay_apply', 'pb_hr_letter')


@tagged('post_install', '-at_install', 'wdgap_s8d')
class TestS8dScaleRaise(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vnd = cls.env.ref('base.VND')
        cls.vnd.active = True
        cls.usd = cls.env.ref('base.INR')
        cls.usd.active = True
        cls.company = cls.env['res.company'].create({
            'name': 'S8D Co', 'currency_id': cls.vnd.id,
            'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        cls.Scales = cls.env['pb.pay.scales']
        cls.Raise = cls.env['pb.pay.scale.raise']
        Rule = cls.env['hr.formula.rule']
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'S8D scheme', 'code': 'SEIGHTD', 'country_code': 'VN',
            'state': 'active', 'company_id': cls.company.id, 'currency_id': cls.vnd.id})
        basic = Rule.create({'config_id': cls.cfg.id, 'code': 'BASIC', 'name': 'Basic',
                             'column_type': 'input', 'sequence': 10, 'net_role': 'earning'})
        b = basic.column_letter
        Rule.create({'config_id': cls.cfg.id, 'code': 'ERSI', 'name': 'Employer insurance',
                     'column_type': 'formula', 'sequence': 20, 'net_role': 'employer_cost',
                     'excel_formula': '=%s*0.17' % b})
        Rule.create({'config_id': cls.cfg.id, 'code': 'NETPAY', 'name': 'Take-home',
                     'column_type': 'formula', 'sequence': 30, 'net_role': 'net',
                     'excel_formula': '=%s' % b})
        cls.cfg_usd = cls.env['hr.formula.config'].create({
            'name': 'S8D rupee scheme', 'code': 'SEIGHTDINR', 'country_code': 'IN',
            'state': 'active', 'company_id': cls.company.id, 'currency_id': cls.usd.id})
        Rule.create({'config_id': cls.cfg_usd.id, 'code': 'BASIC', 'name': 'Basic',
                     'column_type': 'input', 'sequence': 10, 'net_role': 'earning'})
        cls.scale = cls.env['pb.pay.scale'].create({
            'name': 'S8D Retail scale', 'country_code': 'VN', 'currency_id': cls.vnd.id,
            'step_count': 3, 'company_ids': [(6, 0, [cls.company.id])]})
        cls.grade = cls.env['pb.pay.scale.grade'].create(
            {'scale_id': cls.scale.id, 'name': 'Store associate', 'sequence': 10})
        cls.version = cls.env['pb.pay.scale.version'].create(
            {'scale_id': cls.scale.id, 'date_from': '2025-01-01'})
        for step, amount in enumerate((5_500_000, 5_800_000, 6_100_000), start=1):
            cls.env['pb.pay.scale.cell'].create({
                'version_id': cls.version.id, 'grade_id': cls.grade.id,
                'step_no': step, 'amount': amount})
        cls._n = 0

    # ------------------------------------------------------------ fixtures
    def _today(self):
        return self.Raise._today_for(self.company)

    def _first_of_next_month(self):
        today = self._today()
        return (today.replace(day=28) + timedelta(days=4)).replace(day=1)

    def _person(self, wage, step=1, pinned=False, scheme=None, date_end=None):
        type(self)._n += 1
        emp = self.env['hr.employee'].create({
            'name': 'S8D Person %s' % self._n, 'company_id': self.company.id})
        vals = {'name': 'S8D contract %s' % self._n, 'employee_id': emp.id,
                'wage': wage, 'state': 'open', 'date_start': '2025-01-01',
                'company_id': self.company.id}
        if date_end:
            vals['date_end'] = date_end
        contract = self.env['hr.contract'].create(vals)
        # "Paid by" AFTER the contract: a new contract marks it stale.
        emp.sudo().write({'pb_paid_by_id': (scheme or self.cfg).id})
        if 'pb_paid_by_stale' in emp._fields:
            emp.sudo().write({'pb_paid_by_stale': False})
        place = {'contract_id': contract.id, 'grade_id': self.grade.id, 'step_no': step,
                 'source': 'hand'}
        if pinned:
            place.update(pinned=True, pin_reason='retention')
        self.env['pb.pay.scale.placement'].create(place)
        return emp, contract

    def _crowd(self, ending_on=None):
        on = self._person(5_500_000, 1)
        drift = self._person(5_700_000, 2)          # below step 2 (5.8 M)
        above = self._person(5_900_000, 1)          # above new step 1 (5.775 M)
        pinned = self._person(5_000_000, 1, pinned=True)
        ending = self._person(5_500_000, 1, date_end=fields.Date.to_string(
            ending_on or self._today()))            # ends before the rise starts
        return {'on': on, 'drift': drift, 'above': above, 'pinned': pinned,
                'ending': ending}

    def _draft(self, **vals):
        base = {'effective_date': fields.Date.to_string(self._first_of_next_month()),
                'method': 'percent', 'pct': 5, 'reason': 'Yearly rise agreed'}
        base.update(vals)
        return self.Scales.raise_save(self.scale.id, base, 0)

    def _fast(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'scaleraise')

    def _rec(self, read):
        return self.Raise.browse(read['id'])

    def _by_contract(self, read):
        out = {}
        for key, rows in read['groups'].items():
            for row in rows:
                out[row['contract_id']] = (key, row)
        return out

    # ================================================================ R1
    def test_r01_preview_maths(self):
        people = self._crowd()
        read = self._draft()
        table = {s['step']: s for s in read['table'][0]['steps']}
        self.assertEqual([table[i]['new'] for i in (1, 2, 3)],
                         [5_775_000.0, 6_090_000.0, 6_405_000.0])
        rows = self._by_contract(read)
        on_c, drift_c = people['on'][1], people['drift'][1]
        self.assertEqual(rows[on_c.id][0], 'move')
        self.assertEqual((rows[on_c.id][1]['old'], rows[on_c.id][1]['new']),
                         (5_500_000.0, 5_775_000.0))
        self.assertFalse(rows[on_c.id][1]['drifted'])
        self.assertEqual(rows[drift_c.id][0], 'move', "below their step: moves up to it")
        self.assertEqual(rows[drift_c.id][1]['new'], 6_090_000.0)
        self.assertTrue(rows[drift_c.id][1]['drifted'])
        self.assertEqual(rows[people['above'][1].id][0], 'above', "SC2: keeps their pay")
        self.assertIn('above', rows[people['above'][1].id][1]['why'])
        self.assertEqual(rows[people['pinned'][1].id][0], 'pinned')
        self.assertEqual(rows[people['ending'][1].id][0], 'cannot')
        self.assertIn('ends before', rows[people['ending'][1].id][1]['why'])
        self.assertEqual(read['counts']['move'], 2)
        self.assertTrue(read['can_send'], read['problems'])
        # leave one out, and put them back
        read = self.Scales.raise_toggle(read['id'], on_c.id, True)
        self.assertEqual(self._by_contract(read)[on_c.id][0], 'left_out')
        read = self.Scales.raise_toggle(read['id'], on_c.id, False)
        self.assertEqual(self._by_contract(read)[on_c.id][0], 'move')
        # a flat amount
        read = self.Scales.raise_save(self.scale.id, {'method': 'flat', 'flat': 300_000},
                                      read['id'])
        self.assertEqual(read['table'][0]['steps'][0]['new'], 5_800_000.0)
        self.assertEqual(self._by_contract(read)[people['above'][1].id][0], 'above',
                         "5.9 M is above the new 5.8 M step 1")
        # a typed table may not lower a step
        read = self.Scales.raise_save(self.scale.id, {'method': 'table', 'typed': [
            {'grade_id': self.grade.id, 'step': 1, 'amount': 5_000_000},
            {'grade_id': self.grade.id, 'step': 2, 'amount': 6_000_000}]}, read['id'])
        self.assertTrue(any('go down' in p for p in read['problems']), read['problems'])
        self.assertFalse(read['can_send'])
        # nothing above zero
        read = self.Scales.raise_save(self.scale.id, {'method': 'percent', 'pct': 0},
                                      read['id'])
        self.assertTrue(read['problems'])

    # ================================================================ R2
    def test_r02_real_cost_per_currency(self):
        self._person(5_500_000, 1)
        self._person(5_800_000, 2)
        dollar = self._person(5_500_000, 1, scheme=self.cfg_usd)
        read = self._draft()
        rows = self._by_contract(read)
        self.assertEqual(rows[dollar[1].id][0], 'cannot')
        self.assertIn('INR', rows[dollar[1].id][1]['why'])
        self.assertEqual(len(read['costs']), 1, "one line per currency, never added")
        cost = read['costs'][0]
        self.assertEqual(cost['currency'], 'VND')
        # (275,000 + 290,000) wage + 17% employer insurance on it
        self.assertAlmostEqual(cost['month'], 565_000 * 1.17, delta=1.0)
        self.assertAlmostEqual(cost['year'], 565_000 * 1.17 * 12, delta=12.0)
        self.assertEqual(cost['engine'], 2, "both worked out through the pay rules")

    # ================================================================ R3
    def _user(self, login, groups):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref(g).id for g in groups])]})

    def _seat(self, role_key, user):
        role = self.env['biz.approval.role'].sudo().search([('key', '=', role_key)], limit=1)
        Resp = self.env['biz.approval.responsibility'].sudo()
        Resp.with_context(active_test=False).search([
            ('company_id', '=', self.company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')]).write({'active': False})
        Resp.create({'company_id': self.company.id, 'role_id': role.id,
                     'scope_key': '', 'user_id': user.id})

    def test_r03_route_seed_and_one_sign_off(self):
        process = self.env['biz.approval.process'].sudo().search([('key', '=', 'scaleraise')])
        self.assertTrue(process, "the process row ships with the module")
        self.assertEqual(process.model_name, 'pb.pay.scale.raise')
        self.assertTrue(self.Raise._approval_seed_default(self.company))
        hr_lead = self._user('s8d_hrlead', ['base.group_user', 'pb_pay.group_pay_manager'])
        finance = self._user('s8d_fin', ['base.group_user'])    # no pay role at all
        self._seat('hr_lead', hr_lead)
        self._seat('finance', finance)
        _emp, contract = self._person(5_500_000, 1)
        read = self._draft(effective_date=fields.Date.to_string(self._today()))
        rec = self._rec(read)
        answer = self.Scales.raise_act(rec.id, 'send')
        self.assertEqual(answer['state'], 'pending', answer)
        ctx = rec._approval_context()
        self.assertEqual(ctx['maker_uids'], [self.env.uid], "the preparer is the maker")
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
            self.assertEqual(contract.wage, 5_500_000.0, "nothing moves before the end")
            self.env.flush_all()
            self.env.invalidate_all()
            Engine.with_user(seat.acting_user_id).with_context(
                allowed_company_ids=[self.company.id]).decide(
                    request.id, step.key, 'approve', 'ok')
            rec.invalidate_recordset()
        self.assertEqual(order, ['hr', 'fin'], "manager-free: HR lead, then Finance")
        self.assertEqual(rec.state, 'applied', rec.block_note)
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 5_775_000.0)
        # a seat reads its own request only
        self.assertTrue(rec.with_user(finance).read(['name']))

    # ================================================================ R4
    def test_r04_golden_nothing_moves_until_approved(self):
        self._seat('hr_lead', self._user('s8d_hr4', ['base.group_user',
                                                     'pb_pay.group_pay_manager']))
        self._seat('finance', self._user('s8d_fin4', ['base.group_user']))
        people = self._crowd()
        contracts = [c for _e, c in people.values()]
        before = [(c.wage, c.write_date) for c in contracts]
        self.env.flush_all()
        with spy_writes(PAY_TABLES) as seen:
            read = self._draft()
            read = self.Scales.raise_toggle(read['id'], people['on'][1].id, True)
            read = self.Scales.raise_toggle(read['id'], people['on'][1].id, False)
            self.Scales.raise_read(read['id'])
            answer = self.Scales.raise_act(read['id'], 'send')
            rec = self._rec(read)
            self.assertEqual(rec.state, 'pending', answer)
            # turned down
            request = rec.sudo().approval_request_id
            rec._approval_reject(request, 'no')
            self.env.flush_all()
        self.assertFalse(seen, "a rise not yet approved wrote pay tables: %s" % seen)
        self.env.invalidate_all()
        self.assertEqual([(c.wage, c.write_date) for c in contracts], before)
        self.assertEqual(len(self.scale.version_ids), 1, "no version until approved")

    # ================================================================ R5
    def test_r05_approved_today_writes_dated_rows_and_letters(self):
        self._fast()
        today = self._today()
        people = self._crowd(ending_on=today - timedelta(days=1))
        read = self._draft(effective_date=fields.Date.to_string(today))
        answer = self.Scales.raise_act(read['id'], 'send')
        rec = self._rec(read)
        self.assertEqual(rec.state, 'applied', answer)
        self.env.invalidate_all()
        on_c, drift_c = people['on'][1], people['drift'][1]
        self.assertEqual(on_c.wage, 5_775_000.0)
        self.assertEqual(drift_c.wage, 6_090_000.0)
        self.assertEqual(people['above'][1].wage, 5_900_000.0, "SC2: pay kept")
        self.assertEqual(people['pinned'][1].wage, 5_000_000.0, "pinned untouched")
        self.assertEqual(people['ending'][1].wage, 5_500_000.0)
        rows = self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', 'in', (on_c | drift_c).ids)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('effective_date')), {today})
        self.assertEqual(set(rows.mapped('change_source')), {'pay_scale'})
        self.assertEqual(set(rows.mapped('advantage_template_code')), {'BASIC'})
        applies = self.env['pb.pay.apply'].sudo().search([('pb_scale_raise_id', '=', rec.id)])
        self.assertEqual(len(applies), 2)
        self.assertEqual(rec.version_id.date_from, today)
        self.assertEqual(self.version.date_to, today - timedelta(days=1))
        self.assertEqual(on_c.pb_scale_state, 'on')
        self.assertEqual(drift_c.pb_scale_state, 'on')
        self.assertEqual(people['pinned'][1].pb_scale_state, 'pinned')
        letters = self.env['pb.hr.letter'].sudo().search(
            [('employee_id', 'in', (people['on'][0] | people['drift'][0]).ids)])
        self.assertEqual(len(letters), 2, "one letter per moved person")
        self.assertEqual(set(letters.mapped('template_id.letter_type')), {'pay_scale_raise'})
        self.assertIn('5,775,000', letters.filtered(
            lambda l: l.employee_id == people['on'][0]).rendered_html or '')
        self.assertFalse(self.env['pb.hr.letter'].sudo().search(
            [('employee_id', 'in', (people['above'][0] | people['pinned'][0]).ids)]))
        # applying twice changes nothing
        self.env.flush_all()
        with spy_writes(('hr_contract', 'hr_contract_advantage_change', 'pb_pay_apply')) as seen:
            rec._approval_apply(rec.sudo().approval_request_id)
            rec.sudo()._write_wages(self.env.user)
            self.env.flush_all()
        self.assertFalse(seen, seen)

    # ================================================================ R6
    def test_r06_future_date_waits_then_the_job_writes_it_once(self):
        self._fast()
        _emp, contract = self._person(5_500_000, 1)
        start = self._first_of_next_month()
        read = self._draft(effective_date=fields.Date.to_string(start))
        self.env.flush_all()
        with spy_writes(PAY_TABLES) as seen:
            self.Scales.raise_act(read['id'], 'send')
            self.env.flush_all()
        rec = self._rec(read)
        self.assertEqual(rec.state, 'scheduled')
        self.assertFalse(seen, "approved for later: nothing on any contract yet")
        self.assertEqual(rec.version_id.date_from, start)
        job = self.env['hr.job'].create({'name': 'S8D Associate'})
        band = self.env['pb.pay.band'].create({
            'family_id': self.env['pb.pay.family'].create({'name': 'S8D fam'}).id,
            'level': 2, 'country_code': 'VN', 'currency_id': self.vnd.id,
            'min_amount': 1, 'mid_amount': 2, 'max_amount': 99_000_000,
            'date_from': '2020-01-01'})
        self.env['pb.pay.band.job'].create({'band_id': band.id, 'job_id': job.id,
                                            'pb_scale_grade_id': self.grade.id})
        self.assertEqual(self.Scales.resolve(job, self.company, start)['amount'], 5_775_000.0,
                         "a joiner from that day starts on the new table")
        self.assertEqual(self.Scales.resolve(job, self.company, start - timedelta(days=1))
                         ['amount'], 5_500_000.0)
        Model = type(self.Raise)
        self.assertFalse(self.Raise._cron_apply_due().get('started'))
        self.assertEqual(contract.wage, 5_500_000.0)
        with patch.object(Model, '_today_for', lambda s, company=None: start):
            tally = self.Raise._cron_apply_due()
            # >= 1: another rise of the database due the same day starts too
            self.assertGreaterEqual(tally.get('started', 0), 1)
            rec.invalidate_recordset()
            self.assertEqual(rec.state, 'applied')
            self.assertTrue(rec.started_by_job)
            contract.invalidate_recordset()
            self.assertEqual(contract.wage, 5_775_000.0)
            change = self.env['hr.contract.advantage.change'].sudo().search(
                [('contract_id', '=', contract.id)])
            self.assertEqual(change.effective_date, start)
            self.env.flush_all()
            with spy_writes(('hr_contract', 'hr_contract_advantage_change', 'pb_pay_apply')) as seen:
                self.assertFalse(self.Raise._cron_apply_due())
                rec.sudo()._write_wages(self.env.user)
                self.env.flush_all()
            self.assertFalse(seen, "a second run writes nothing")

    # ================================================================ R7
    def test_r07_take_back_before_the_day(self):
        self._fast()
        _emp, contract = self._person(5_500_000, 1)
        start = self._first_of_next_month()
        read = self._draft(effective_date=fields.Date.to_string(start))
        self.Scales.raise_act(read['id'], 'send')
        rec = self._rec(read)
        self.assertEqual(len(self.scale.version_ids), 2)
        out = self.Scales.raise_act(rec.id, 'take_back')
        self.assertEqual(out['read']['state'], 'taken_back')
        self.scale.invalidate_recordset()
        self.assertEqual(len(self.scale.version_ids), 1, "the new version goes with it")
        self.assertFalse(self.version.date_to, "the table before it is in force again")
        self.assertEqual(contract.wage, 5_500_000.0)
        self.assertFalse(self.Raise._cron_apply_due())
        # once started: only a new request
        read2 = self._draft(effective_date=fields.Date.to_string(self._today()))
        self.Scales.raise_act(read2['id'], 'send')
        with self.assertRaises(UserError):
            self.Scales.raise_act(read2['id'], 'take_back')

    # ================================================================ R8
    def test_r08_pay_changed_since_sending_is_skipped(self):
        start = self._first_of_next_month()
        _e1, c1 = self._person(5_500_000, 1)
        _e2, c2 = self._person(5_500_000, 1)
        self._fast()
        read = self._draft(effective_date=fields.Date.to_string(start))
        self.Scales.raise_act(read['id'], 'send')
        rec = self._rec(read)
        c2.wage = 5_600_000.0        # somebody changed it meanwhile
        with patch.object(type(self.Raise), '_today_for', lambda s, company=None: start):
            self.Raise._cron_apply_due()
        self.env.invalidate_all()
        self.assertEqual(c1.wage, 5_775_000.0)
        self.assertEqual(c2.wage, 5_600_000.0, "never over a change made since")
        line = rec.line_ids.filtered(lambda l: l.contract_id == c2)
        self.assertEqual(line.state, 'skipped')
        self.assertIn('changed since', line.skip_reason)
        self.assertEqual(self.Scales.raise_read(rec.id)['skipped'], 1)

    # ================================================================ R9
    def test_r09_past_date_and_the_rework_finds_it(self):
        if 'pb.retro.review' not in self.env:
            self.skipTest('Past-month re-work not installed')
        from odoo.addons.pb_retro.tests import test_retro as base
        B = base.TestW2d1Retro
        holder = type('H', (), {'_seq': 300})()
        holder.env = self.env
        holder.company = self.company
        holder.calendar = self.company.resource_calendar_id or self.env['resource.calendar'].create(
            {'name': 'S8D Hours', 'company_id': self.company.id})
        holder.cat = {
            'earning': self.env.ref('om_hr_payroll.BASIC'),
            'deduction': self.env.ref('om_hr_payroll.DED'),
            'net': self.env.ref('om_hr_payroll.NET'),
            'employer_cost': self.env.ref('om_hr_payroll.COMP'),
        }
        for name in ('_scheme', '_rule', '_progressive', '_run', '_slip'):
            setattr(holder, name, getattr(B, name).__get__(holder))
        cfg = holder._progressive()
        scale = self.env['pb.pay.scale'].create({
            'name': 'S8D big scale', 'country_code': 'VN', 'currency_id': self.vnd.id,
            'step_count': 1, 'company_ids': [(6, 0, [self.company.id])]})
        grade = self.env['pb.pay.scale.grade'].create({'scale_id': scale.id, 'name': 'Lead'})
        version = self.env['pb.pay.scale.version'].create(
            {'scale_id': scale.id, 'date_from': '2025-01-01'})
        self.env['pb.pay.scale.cell'].create({'version_id': version.id, 'grade_id': grade.id,
                                              'step_no': 1, 'amount': 44_000_000})
        emp = self.env['hr.employee'].create({'name': 'S8D Past', 'company_id': self.company.id})
        emp.sudo().write({'pb_paid_by_id': cfg.id})
        contract = self.env['hr.contract'].create({
            'name': 'S8D past contract', 'employee_id': emp.id, 'wage': 44_000_000,
            'state': 'open', 'date_start': '2025-01-01', 'company_id': self.company.id})
        self.env['pb.pay.scale.placement'].create(
            {'contract_id': contract.id, 'grade_id': grade.id, 'step_no': 1})
        slips = [holder._slip(cfg, emp, contract, p, {'BASICPAY': 44_000_000, 'LOANINST': 0.0})
                 for p in (base.SEP, base.OCT)]
        stored = {s.id: sorted((l.code, l.total) for l in s.line_ids) for s in slips}
        self._fast()
        Model = type(self.Raise)
        with patch.object(Model, '_wage_code', lambda s, e: 'BASICPAY'), \
                patch.object(Model, '_today_for', lambda s, company=None: base.OCT[1]
                             + timedelta(days=5)):
            read = self.Scales.raise_save(scale.id, {
                'effective_date': fields.Date.to_string(base.SEP[0]), 'method': 'percent',
                'pct': 10, 'reason': 'Back-dated rise'}, 0)
            self.assertTrue(read['past'])
            self.assertEqual(len(read['paid_months']), 2, read['paid_months'])
            self.Scales.raise_act(read['id'], 'send')
            rec = self._rec(read)
            self.assertEqual(rec.state, 'applied')
        contract.invalidate_recordset()
        self.assertEqual(contract.wage, 48_400_000.0)
        self.assertFalse(self.env['hr.payroll.retro.adjustment'].sudo().search(
            [('original_payslip_id', 'in', [s.id for s in slips])]), "C-6: no back-pay input")
        self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', contract.id)]).write(
            {'changed_at': fields.Datetime.now() + timedelta(days=1)})
        answer = self.Scales.raise_act(rec.id, 'rework')
        review = self.env['pb.retro.review'].browse(answer['review_id'])
        self.assertEqual(review.state, 'draft')
        self.assertEqual(review.employee_ids, emp)
        review.action_work_out()
        diff = sum(line.diff for row in review.slip_ids for line in row.line_ids
                   if line.code == 'BASICPAY')
        self.assertAlmostEqual(diff, 8_800_000.0, delta=1.0,
                               msg="Sep + Oct at +4,400,000 each")
        for s in slips:
            s.invalidate_recordset()
            self.assertEqual(sorted((l.code, l.total) for l in s.line_ids), stored[s.id])
        # a second press finds the same re-work
        self.assertEqual(self.Scales.raise_act(rec.id, 'rework')['review_id'], review.id)

    # ================================================================ R10
    def test_r10_rights(self):
        self._person(5_500_000, 1)
        read = self._draft()
        plain = self._user('s8d_plain', ['base.group_user'])
        viewer = self._user('s8d_viewer', ['base.group_user', 'pb_pay.group_pay_viewer'])
        Plain = self.Scales.with_user(plain).with_context(allowed_company_ids=[self.company.id])
        with self.assertRaises(AccessError):
            Plain.raise_read(read['id'])
        with self.assertRaises(AccessError):
            Plain.raise_save(self.scale.id, {'pct': 3}, 0)
        View = self.Scales.with_user(viewer).with_context(allowed_company_ids=[self.company.id])
        self.assertEqual(View.raise_read(read['id'])['id'], read['id'])
        self.assertFalse(View.raise_read(read['id'])['editable'])
        with self.assertRaises(AccessError):
            View.raise_save(self.scale.id, {'pct': 3}, read['id'])
        with self.assertRaises(AccessError):
            View.raise_act(read['id'], 'send')

    # ================================================================ R11
    def test_r11_silent_install(self):
        self.assertFalse(self.Raise.search([('company_id', '=', self.company.id)]))
        due = self.Raise.sudo().search([('state', '=', 'scheduled'),
                                        ('effective_date', '<=', self._today())])
        if not due:
            self.assertEqual(self.Raise._cron_apply_due(), {})
        cron = self.env.ref('pb_pay_scales.ir_cron_scale_raise_apply_due')
        self.assertTrue(cron.active)
        company = self.env['res.company'].create({'name': 'S8D New Co'})
        workflow = self.env['biz.approval.workflow'].sudo().search([
            ('company_id', '=', company.id), ('process_id.key', '=', 'scaleraise')])
        self.assertTrue(workflow, "a new company gets the rise route")

    # ================================================================ R12
    def test_r12_above_step_chip(self):
        _emp, above = self._person(5_900_000, 1)     # paid above step 1
        _emp2, exact = self._person(5_800_000, 1)    # paid exactly step 2
        self.env.invalidate_all()
        chip = self.Scales.contract_chip(above.id)
        self.assertIn('Above step', chip['label'])
        self.assertNotIn('stage_wage', chip, "never offered a cut")
        self.assertEqual(chip['action']['method'], 'pin_from_drawer')
        chip = self.Scales.contract_chip(exact.id)
        self.assertEqual(chip['action']['method'], 'place')
        self.assertEqual(chip['action']['args'], [exact.id, self.grade.id, 2])
