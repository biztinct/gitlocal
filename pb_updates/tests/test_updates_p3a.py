# -*- coding: utf-8 -*-
"""UPDATES P3a — lanes, the bank second check, portal-login managers (D12),
month-only pay data files (D1), the old employee import retired, the demo
shortcut's one-offs (F1-F19 in UPDATES_P3A_HANDOVER.md §5).

A company of its own. People:

    proposer   HR officer + payroll officer — sends every update
    second     HR manager — a "records manager", the second person
    lead       holds the HR lead responsibility (the records route's step)

and three employees (Ann, Bob, Cat). Cat has an employee self-service
(portal) login, for D12.
"""
import base64
import csv
import inspect
import io
from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged

from odoo.addons.biz_approval_workflow.models import definition as D
from odoo.addons.pb_records.models import records_approval as RA
from odoo.addons.pb_records.models.records_approval import lane_of
from odoo.addons.pb_records.models import records_engine
from odoo.addons.pb_updates.models import updates_managers, updates_monthonly

JOB = 'f:hr.employee:job_title'
PHONE = 'f:hr.employee:work_phone'
COUNTRY = 'f:hr.employee:payroll_country'
WAGE = 'f:hr.contract:wage'
ACC = 'b:acc_number'
BANK = 'b:bank_name'
MANAGER = 'f:hr.employee:parent_id'
NOW = datetime(2026, 11, 11, 3, 0)
FUTURE = '2026-12-01'


def csv_b64(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    return base64.b64encode(out.getvalue().encode('utf-8')).decode()


class P3aCommon(TransactionCase):

    @classmethod
    def _user(cls, login, groups, company):
        return cls.env['res.users'].with_context(
            no_reset_password=True, mail_create_nosubscribe=True).create({
                'name': login.replace('.', ' ').title(), 'login': login,
                'email': '%s@example.com' % login,
                'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})

    @classmethod
    def _hold(cls, company, role_key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', role_key)], limit=1)
        Resp = cls.env['biz.approval.responsibility'].sudo()
        held = Resp.with_context(active_test=False).search([
            ('company_id', '=', company.id), ('role_id', '=', role.id),
            ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': user.id, 'active': True,
                        'backup_user_id': False})
        else:
            Resp.create({'company_id': company.id, 'role_id': role.id,
                         'scope_key': '', 'scope_label': company.name,
                         'user_id': user.id, 'date_from': date(2020, 1, 1)})

    @classmethod
    def _company(cls, name):
        vnd = cls.env.ref('base.VND')
        company = cls.env['res.company'].create({'name': name, 'currency_id': vnd.id})
        company.partner_id.tz = 'Asia/Ho_Chi_Minh'
        return company

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls._company('P3A Updates Co')
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context,
                                       allowed_company_ids=[cls.company.id]))
        cls.proposer = cls._user('p3a.proposer', (
            'base.group_user', 'hr.group_hr_user',
            'pb_hr_payroll_base.group_payroll_base_officer',
            'pb_records.group_records_editor'), cls.company)
        cls.second = cls._user('p3a.second', (
            'base.group_user', 'hr.group_hr_manager'), cls.company)
        cls.lead = cls._user('p3a.lead', (
            'base.group_user', 'hr.group_hr_user'), cls.company)
        cls._hold(cls.company, 'hr_lead', cls.lead)
        # Finance: the bank lane's first choice of second person.
        cls._hold(cls.company, 'finance', cls.second)
        cls.Apply = cls.env['pb.records.apply']
        cls.Engine = cls.env['biz.approval.engine']
        cls.calendar = cls.company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'P3A Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'P3A Kind'})
        cls.ann = cls._person('P3A Ann', 'P3AU01')
        cls.bob = cls._person('P3A Bob', 'P3AU02')
        cls.cat = cls._person('P3A Cat', 'P3AU03')
        for p in (cls.ann, cls.bob, cls.cat):
            cls.env['hr.contract'].create({
                'name': 'P3A contract %s' % p.name, 'employee_id': p.id,
                'company_id': cls.company.id, 'wage': 1000.0, 'state': 'open',
                'date_start': '2026-01-01', 'date_end': '2027-12-31',
                'resource_calendar_id': cls.calendar.id, 'type_id': cls.kind.id})
        cls.uenv = cls.env(user=cls.proposer, context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id]))
        cls.Upd = cls.uenv['pb.updates.desk']
        cls.Desk = cls.uenv['pb.records.desk']

    @classmethod
    def _person(cls, name, code, company=None):
        return cls.env['hr.employee'].create({
            'name': name, 'barcode': code,
            'company_id': (company or cls.company).id, 'job_title': 'Operator'})

    def setUp(self):
        super().setUp()
        self.clock = NOW
        patcher = patch.object(type(self.env['pb.records.apply']), '_records_now',
                               lambda _self: self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------ helpers
    def cols(self, used, code=1):
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': code, 'name': 0, 'email': 0}, 'heads': {}}

    def send(self, rows, used, upd=None, **kw):
        upd = upd if upd is not None else self.Upd
        rev = upd.review(csv_b64(rows), 'p3a.csv', self.cols(used))
        self.assertTrue(rev['ok'], rev.get('msg'))
        answer = upd.apply(kw.pop('name', 'P3A update'), csv_b64(rows), 'p3a.csv',
                           self.cols(used), rev['changes'],
                           {'rows': len(rows) - 1}, **kw)
        self.assertTrue(answer.get('ok', True), answer.get('msg'))
        return answer

    def mixed(self, upd=None, **kw):
        """Ann: job title (details) + wage (pay) + account number (bank)."""
        return self.send([['Code', 'Job', 'Wage', 'Account', 'Bank'],
                          ['P3AU01', 'Lead Operator', '2000', '9988776655', 'P3A Bank']],
                         {2: JOB, 3: WAGE, 4: ACC, 5: BANK}, upd=upd, **kw)

    def parts(self, answer):
        recs = self.Apply.sudo().browse(answer.get('apply_ids') or [answer['apply_id']])
        return {r.lane: r for r in recs}

    def fresh(self, *recs):
        for rec in recs:
            rec.invalidate_recordset()

    def seat_users(self, rec):
        request = rec.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        return step.seat_ids.filtered(lambda s: s.status == 'open').mapped('acting_user_id')

    def approve(self, rec, user):
        request = rec.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        return self.Engine.with_user(user).decide(request.id, step.key, 'approve', 'ok')

    def publish_route(self, company, key, definition, name='P3A own route'):
        """Publish a route of the company's own for `key` and bind it to
        the whole company (ending the binding in force), the way the Matrix
        screen does."""
        process = self.env['biz.approval.process']._by_key(key)
        Workflow = self.env['biz.approval.workflow'].sudo()
        workflow = Workflow.create({'name': name, 'company_id': company.id,
                                    'process_id': process.id,
                                    'owner_user_id': self.env.user.id})
        version = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': workflow.id, 'revision': 1, 'status': 'draft',
            'definition': definition})
        engine = self.Engine.sudo().with_context(approval_skip_coverage=True)
        checks = engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'], checks['errors'])
        engine.publish(version.id, version.draft_revision, None, 'P3A test',
                       [w['code'] for w in checks['warnings']])
        Binding = self.env['biz.approval.binding'].sudo()
        Binding.search([('company_id', '=', company.id),
                        ('process_id', '=', process.id), ('scope_key', '=', ''),
                        ('active', '=', True)]).write({'active': False})
        Binding.create({'company_id': company.id, 'process_id': process.id,
                        'scope_key': '', 'scope_label': company.name,
                        'kind_key': 'any', 'workflow_id': workflow.id,
                        'mode': 'follow'})
        return version

    def no_approval(self, key='records', company=None):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(
            company or self.company, key)

    def account(self, person):
        person.invalidate_recordset()
        accounts = person.bank_account_ids if 'bank_account_ids' in person._fields \
            else person.bank_account_id
        return ','.join(accounts.mapped('acc_number'))


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aLanes(P3aCommon):

    # ------------------------------------------------------------ F1
    def test_F1_three_lanes_default_route(self):
        answer = self.mixed()
        parts = self.parts(answer)
        self.assertEqual(set(parts), {'details', 'pay', 'bank'})
        batch = parts['details'].updates_batch_id
        self.assertTrue(batch)
        self.assertEqual(set(batch.apply_ids.ids), {p.id for p in parts.values()})
        # personal details: changed now, nobody asked
        self.assertTrue(parts['details'].applied)
        self.assertTrue(parts['details'].details_now)
        self.assertFalse(parts['details'].approval_request_id)
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.job_title, 'Lead Operator')
        # pay: the records route, exactly as before (HR lead)
        self.assertEqual(parts['pay'].state, 'pending')
        self.assertEqual(parts['pay'].approval_request_id.process_id.key, 'records')
        self.assertIn(self.lead, self.seat_users(parts['pay']))
        # bank: its own route, a second person, never the proposer
        bank = parts['bank']
        self.assertEqual(bank.state, 'pending')
        self.assertEqual(bank.approval_request_id.process_id.key, 'records_bank')
        seats = self.seat_users(bank)
        self.assertTrue(seats)
        self.assertNotIn(self.proposer, seats)
        self.assertIn(self.second, seats)
        self.assertEqual(self.account(self.ann), '')
        # the answer lists every lane
        self.assertEqual([p['lane'] for p in answer['lanes']], ['details', 'pay', 'bank'])
        self.assertTrue(answer['pending'])
        # the request title the inbox reads first
        self.assertEqual(bank.approval_request_id.title, 'Bank details for 1 person')
        notes = bank.approval_request_id.seat_notes or []
        self.assertTrue(any(n.get('code') == 'second_person' for n in notes))

    # ------------------------------------------------------------ F2
    def test_F2_no_approval_needed_keeps_bank_waiting(self):
        self.no_approval('records')
        answer = self.mixed()
        parts = self.parts(answer)
        self.assertTrue(parts['details'].applied)
        self.assertTrue(parts['pay'].applied)
        self.assertEqual(parts['bank'].state, 'pending')
        self.assertEqual(self.account(self.ann), '')
        self.assertEqual(answer['written'], 2)

    # ------------------------------------------------------------ F3
    def test_F3_own_records_route_is_followed(self):
        own = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'HR lead only',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
             'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        self.publish_route(self.company, 'records', own)
        details = self.send([['Code', 'Job'], ['P3AU02', 'Fitter']], {2: JOB})
        rec = self.parts(details)['details']
        self.assertEqual(rec.state, 'pending', "an own route is never overridden")
        self.assertFalse(rec.details_now)

    def test_F3b_the_switch(self):
        self.assertTrue(self.company.pb_records_sheet_details_now)
        # only somebody who looks after approvals may turn it off
        self.assertFalse(self.Upd.set_details_now(False)['ok'])
        admin_upd = self.env['pb.updates.desk']
        self.assertTrue(admin_upd.set_details_now(False)['ok'])
        self.assertFalse(self.company.pb_records_sheet_details_now)
        off = self.send([['Code', 'Job'], ['P3AU02', 'Fitter']], {2: JOB})
        self.assertEqual(self.parts(off)['details'].state, 'pending')
        admin_upd.set_details_now(True)
        on = self.send([['Code', 'Job'], ['P3AU03', 'Welder']], {2: JOB})
        self.assertTrue(self.parts(on)['details'].applied)

    # ------------------------------------------------------------ F4 / F5
    def test_F4_proposer_can_never_approve_bank(self):
        bank = self.parts(self.mixed())['bank']
        request = bank.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        # no seat at all (UI: no Approve button): the sentence, before anything
        with self.assertRaisesRegex(UserError, 'Bank details need a second person'):
            self.Engine.with_user(self.proposer).decide(request.id, step.key, 'approve')
        # ... and moved onto the proposer by an approvals admin, still refused
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.sudo().reassign(request.id, seat.key, self.proposer.id, 'P3A test')
        with self.assertRaisesRegex(UserError, 'Bank details need a second person'):
            self.Engine.with_user(self.proposer).decide(request.id, step.key, 'approve')
        # the inbox's own button path is the same engine call
        inbox = self.env['pb.approval.inbox'].with_user(self.proposer) \
            if 'pb.approval.inbox' in self.env else None
        if inbox is not None:
            with self.assertRaisesRegex(UserError, 'Bank details need a second person'):
                inbox.act('pb.records.apply', bank.id, 'approve')
        # the write itself refuses too (a route set to "No approval needed")
        self.assertIn('second person', bank._bank_refusal(request))
        self.fresh(bank)
        self.assertFalse(bank.applied)
        self.assertEqual(self.account(self.ann), '')

    def test_F5_a_second_person_approves(self):
        bank = self.parts(self.mixed())['bank']
        self.approve(bank, self.second)
        self.fresh(bank)
        self.assertTrue(bank.applied)
        self.assertEqual(self.account(self.ann), '9988776655')
        decision = bank.approval_request_id.decision_ids
        self.assertEqual(decision.user_id, self.second)
        self.assertEqual(bank.user_id, self.proposer)
        self.assertTrue(bank.change_ids)
        # the approver sees the account number masked
        detail = bank._approval_detail(bank.approval_request_id)
        self.assertIn('•••• 6655', ' '.join(c for r in detail['rows'] for c in r['cells']))

    def test_F5b_bank_route_set_to_no_approval_still_fails_closed(self):
        self.no_approval('records_bank')
        bank = self.parts(self.mixed())['bank']
        self.fresh(bank)
        self.assertFalse(bank.applied)
        self.assertEqual(bank.approval_request_id.state, 'approved')
        self.assertIn('second person', bank.approval_request_id.block_reason)
        self.assertEqual(self.account(self.ann), '')

    # ------------------------------------------------------------ F6
    def test_F5c_finance_is_the_proposer_falls_back(self):
        self._hold(self.company, 'finance', self.proposer)
        bank = self.parts(self.mixed())['bank']
        seats = self.seat_users(bank)
        self.assertNotIn(self.proposer, seats)
        self.assertIn(self.second, seats, "a records manager stands in")

    def test_F6_nobody_else(self):
        lone_co = self._company('P3A Lone Co')
        # Nobody else is in this company: not even the administrator, and no
        # responsibility is held there (the set-up seeds them from whoever
        # created the company).
        self.env.user.company_ids = [(3, lone_co.id)]
        self.env['biz.approval.responsibility'].sudo().search(
            [('company_id', '=', lone_co.id)]).write({'active': False})
        lone = self._user('p3a.lone', (
            'base.group_user', 'hr.group_hr_user',
            'pb_hr_payroll_base.group_payroll_base_officer',
            'pb_records.group_records_editor'), lone_co)
        dee = self._person('P3A Dee', 'P3AU09', lone_co)
        upd = self.env(user=lone, context=dict(
            self.env.context, allowed_company_ids=[lone_co.id]))['pb.updates.desk']
        answer = self.send([['Code', 'Account'], ['P3AU09', '1112223334']],
                           {2: ACC}, upd=upd)
        bank = self.parts(answer)['bank']
        request = bank.approval_request_id
        self.assertEqual(request.state, 'blocked', [
            (s.acting_user_id.login, s.resolved_via) for s in request.seat_ids])
        self.assertIn('Nobody else in P3A Lone Co can approve bank details yet',
                      request.block_reason)
        self.assertEqual(bank.state, 'pending')
        self.assertEqual(self.account(dee), '')
        outlook = upd.lane_outlook([{'emp_id': dee.id, 'field_id': ACC,
                                     'value': '1112223334'}])['lanes']
        self.assertEqual(outlook[0]['outcome'], 'nobody')

    # ------------------------------------------------------------ F7
    def test_F7_dated_bank_needs_the_second_person_first(self):
        answer = self.mixed(start_date=FUTURE, hold_scope='all')
        parts = self.parts(answer)
        bank = parts['bank']
        self.assertEqual(bank.start_date, fields.Date.to_date(FUTURE))
        self.assertEqual(bank.state, 'pending', "a second person BEFORE it is scheduled")
        # Start now by the proposer: nothing to start (not approved)
        res = self.Upd.start_now(bank.id)
        self.assertFalse(res['ok'])
        # the job on the day writes nothing that is not approved (the
        # personal details, scheduled for the day, are written)
        self.clock = datetime(2026, 12, 1, 3, 0)
        self.assertEqual(self.Apply._cron_start_scheduled(), {'started': 1})
        self.assertEqual(self.account(self.ann), '')
        self.clock = NOW
        self.approve(bank, self.second)
        self.fresh(bank)
        self.assertEqual(bank.state, 'scheduled')
        self.assertEqual(self.account(self.ann), '')
        # a scheduled bank change whose approval is gone is refused (rail)
        with patch.object(type(bank), '_second_person_approved', lambda *a, **k: False):
            res = self.Upd.start_now(bank.id)
            self.assertFalse(res['ok'])
            self.assertIn('second person', res['msg'])
        self.clock = datetime(2026, 12, 1, 3, 0)
        tally = self.Apply._cron_start_scheduled()
        self.fresh(*parts.values())
        self.assertEqual(tally.get('started'), 1, (tally, [
            (p.lane, p.state, p.block_note) for p in parts.values()]))
        self.assertEqual(self.account(self.ann), '9988776655')

    # ------------------------------------------------------------ F8
    def test_F8_undo_and_cancel_per_lane(self):
        self.no_approval('records')
        answer = self.mixed()
        parts = self.parts(answer)
        batch = parts['details'].updates_batch_id
        row = self.Upd._batch_row(batch, True)
        self.assertEqual([l['lane'] for l in row['lanes']], ['details', 'pay', 'bank'])
        self.assertTrue(row['lanes'][2]['can_cancel'])
        # undo personal details only
        res = self.Upd.undo(batch.id, apply_id=parts['details'].id)
        self.assertTrue(res['ok'], res.get('msg'))
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.job_title, 'Operator')
        self.assertEqual(self.ann.contract_id.wage if 'contract_id' in self.ann._fields
                         else 2000.0, 2000.0)
        # cancel the bank lane only
        res = self.Upd.cancel(apply_id=parts['bank'].id)
        self.assertTrue(res['ok'], res.get('msg'))
        self.fresh(*parts.values())
        self.assertEqual(parts['bank'].state, 'cancelled')
        self.assertTrue(parts['pay'].applied)
        # the whole update: what is left (pay) is put back
        res = self.Upd.undo(batch.id)
        self.assertTrue(res['ok'], res.get('msg'))
        self.fresh(*parts.values())
        self.assertTrue(parts['pay'].undone)
        self.assertEqual(self.account(self.ann), '')

    # ------------------------------------------------------------ F9
    def test_F9_lane_field_list(self):
        cards = self.Upd._desk()._cards(0)
        lanes = {}
        for cid in cards:
            lanes.setdefault(lane_of(cid), []).append(cid)
        self.assertEqual(sum(len(v) for v in lanes.values()), len(cards))
        self.assertEqual(set(lanes), {'details', 'pay', 'bank'} & set(lanes))
        self.assertEqual(lane_of(COUNTRY), 'pay')
        self.assertEqual(lane_of(JOB), 'details')
        self.assertEqual(lane_of(MANAGER), 'details')
        self.assertEqual(lane_of(WAGE), 'pay')
        self.assertEqual(lane_of('c:ANY'), 'pay')
        self.assertEqual(lane_of(ACC), 'bank')
        for cid, card in cards.items():
            if card.get('group') == 'bank':
                self.assertEqual(lane_of(cid), 'bank', cid)
            elif card.get('group') in ('contract', 'component'):
                self.assertEqual(lane_of(cid), 'pay', cid)
        # "Payment method" (the old word match) is not a field on this build
        labels = {(c.get('label') or '').lower() for c in cards.values()}
        self.assertNotIn('payment method', labels)

    # ------------------------------------------------------------ F10 / F11
    def test_F10_records_screen_mixed_proposal(self):
        changes = [{'emp_id': self.bob.id, 'field_id': JOB, 'value': 'Fitter'},
                   {'emp_id': self.bob.id, 'field_id': WAGE, 'value': 1500},
                   {'emp_id': self.bob.id, 'field_id': ACC, 'value': '5554443332'}]
        for source in ('desk', 'import'):
            answer = self.Desk.apply_changes(0, changes, note='P3A grid', source=source)
            parts = self.parts(answer)
            self.assertEqual(set(parts), {'pay', 'bank'}, source)
            self.assertEqual(parts['pay'].approval_request_id.process_id.key, 'records')
            self.assertEqual(parts['bank'].approval_request_id.process_id.key, 'records_bank')
            self.assertNotIn(self.proposer, self.seat_users(parts['bank']))
            self.assertFalse(parts['pay'].details_now, "no relaxation on the Records screen")
            for rec in parts.values():
                self.Desk.cancel_apply(rec.id)
        history = self.Desk.get_history(10)['applies']
        self.assertTrue(any(h.get('lane') == 'bank' for h in history))

    def test_F11_unmixed_records_proposal_is_unchanged(self):
        changes = [{'emp_id': self.bob.id, 'field_id': JOB, 'value': 'Fitter'},
                   {'emp_id': self.bob.id, 'field_id': WAGE, 'value': 1500}]
        answer = self.Desk.apply_changes(0, changes, note='P3A grid')
        self.assertEqual(len(answer['apply_ids']), 1)
        rec = self.Apply.sudo().browse(answer['apply_id'])
        self.assertEqual(rec.approval_request_id.process_id.key, 'records')
        self.assertEqual(rec.values_count, 2)
        self.assertTrue(answer['pending'])
        self.assertFalse(rec.details_now)
        # an Updates file with one lane only (pay): one proposal, the route
        pay = self.send([['Code', 'Wage'], ['P3AU03', '1800']], {2: WAGE})
        self.assertEqual(len(pay['apply_ids']), 1)
        self.assertEqual(self.parts(pay)['pay'].state, 'pending')

    # ------------------------------------------------------------ F13
    def test_F13_bank_route_seeded_once_and_never_overwritten(self):
        Workflow = self.env['biz.approval.workflow'].sudo()
        process = self.env['biz.approval.process']._by_key('records_bank')
        self.assertTrue(process.connected)
        mine = Workflow.search([('company_id', '=', self.company.id),
                                ('process_id', '=', process.id)])
        self.assertEqual(len(mine), 1)
        self.assertTrue(self.Apply._approval_seed_bank(self.company))
        self.assertEqual(Workflow.search_count([('company_id', '=', self.company.id),
                                                ('process_id', '=', process.id)]), 1)
        version = mine.published_version_id
        self.assertEqual(D.normalise(version.definition)['steps'][0]['who']['role'], 'finance')
        # somebody edits it: a re-seed leaves their edit alone
        edited = self.publish_route(self.company, 'records_bank',
                                    RA._bank_definition(), name='Our bank check')
        self.Apply._approval_seed_bank(self.company)
        binding = self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id), ('process_id', '=', process.id),
            ('active', '=', True)])
        self.assertEqual(binding.workflow_id, edited.workflow_id)

    # ------------------------------------------------------------ outlook
    def test_outlook_says_what_each_lane_will_do(self):
        changes = [{'emp_id': self.ann.id, 'field_id': JOB, 'value': 'X'},
                   {'emp_id': self.ann.id, 'field_id': WAGE, 'value': 5},
                   {'emp_id': self.ann.id, 'field_id': ACC, 'value': '123456789'}]
        lanes = {l['lane']: l for l in self.Upd.lane_outlook(changes)['lanes']}
        self.assertEqual(lanes['details']['outcome'], 'now')
        self.assertEqual(lanes['pay']['outcome'], 'approval')
        self.assertIn(self.lead.name, lanes['pay']['line'])
        self.assertEqual(lanes['bank']['outcome'], 'second')
        self.assertNotIn(self.proposer.name, lanes['bank']['line'])

    def test_guarded_fields(self):
        bank = self.parts(self.mixed())['bank']
        with self.assertRaises(UserError):
            bank.with_user(self.proposer).write({'lane': 'pay'})
        with self.assertRaises(UserError):
            bank.with_user(self.proposer).write({'changes_json': '[]'})
        # content decides, not the label: a pay proposal carrying a bank value
        self.assertEqual(bank._approval_process_key_for(), 'records_bank')


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aEngineInert(P3aCommon):
    """F12 — another process with the new hooks present: identical."""

    def _flow(self, definition, subject_manager=None):
        company = self.company
        self.publish_route(company, 'generic', definition, name='P3A generic')
        if subject_manager and not self.ann.user_id:
            self.ann.user_id = self.env['res.users'].sudo().create({
                'name': 'P3A Ann login', 'login': 'p3a.ann.%s' % self.ann.id,
                'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
            self.ann.parent_id = subject_manager
        req = self.env['biz.approval.generic.request'].with_user(
            self.ann.user_id or self.proposer).create({
                'name': 'P3A ask', 'company_id': company.id})
        payload = self.Engine.with_user(req.requester_user_id).submit(req)
        request = self.env['biz.approval.request'].browse(payload['id'])
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seats = sorted(step.seat_ids.mapped('acting_user_id').ids)
        user = step.seat_ids[:1].acting_user_id
        self.Engine.with_user(user).decide(request.id, step.key, 'approve', 'fine')
        request.invalidate_recordset()
        events = [(e.kind, e.summary) for e in self.env['biz.approval.event'].sudo().search(
            [('request_id', '=', request.id)], order='id')] \
            if 'biz.approval.event' in self.env else []
        decisions = [(d.user_id.id, d.action) for d in request.decision_ids]
        return {'state': request.state, 'seats': seats, 'decisions': decisions,
                'events': [(k, m.replace(str(request.id), '#')) for k, m in events],
                'steps': [(s.key, s.status) for s in request.step_ids]}

    def _both(self, definition, subject_manager=None):
        with_hooks = self._flow(definition, subject_manager)
        base_people = records_engine.BizApprovalEngineOptInHooks.__bases__[0]
        with patch.object(records_engine.BizApprovalEngineOptInHooks, '_resolve_step_people',
                          lambda s, *a, **k: super(records_engine.BizApprovalEngineOptInHooks, s)
                          ._resolve_step_people(*a, **k)), \
                patch.object(records_engine.BizApprovalEngineOptInHooks, 'decide',
                             lambda s, *a, **k: super(records_engine.BizApprovalEngineOptInHooks, s)
                             .decide(*a, **k)), \
                patch.object(updates_managers.BizApprovalEnginePortalManagers,
                             '_resolve_step_people',
                             lambda s, *a, **k: super(updates_managers.BizApprovalEnginePortalManagers, s)
                             ._resolve_step_people(*a, **k)):
            without = self._flow(definition, subject_manager)
        self.assertTrue(base_people)
        return with_hooks, without

    def test_F12_role_route_identical(self):
        definition = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'HR lead',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'company'},
             'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        a, b = self._both(definition)
        self.assertEqual(a['state'], 'applied')
        self.assertEqual(a, b)

    def test_F12_manager_route_identical(self):
        boss = self._person('P3A Boss', 'P3AU07')
        boss.user_id = self.second
        definition = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'Their manager',
             'who': {'mode': 'manager'}, 'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        a, b = self._both(definition, subject_manager=boss)
        self.assertEqual(a['seats'], [self.second.id])
        self.assertEqual(a, b)

    def test_F12_hooks_are_opt_in(self):
        record = self.env['biz.approval.generic.request']
        self.assertIsNone(getattr(record, '_approval_step_people', None))
        self.assertIsNone(getattr(record, '_approval_may_decide', None))


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aPortalManager(P3aCommon):
    """F14 — D12."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'P3A Cat login', 'login': 'p3a.cat.portal',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.cat.user_id = cls.portal_user
        cls.no_approval_records = True

    def groups_of(self, user):
        user.invalidate_recordset()
        return (user.share, sorted(user.group_ids.ids))

    def test_F14_from_updates_records_and_form(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.company, 'records')
        before = self.groups_of(self.portal_user)
        # Updates (by employee code)
        answer = self.send([['Code', 'Manager'], ['P3AU01', 'P3AU03']], {2: MANAGER})
        self.assertTrue(self.parts(answer)['details'].applied, answer)
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.parent_id, self.cat)
        # Records screen
        res = self.Desk.apply_changes(0, [{'emp_id': self.bob.id, 'field_id': MANAGER,
                                           'value': 'P3A Cat'}])
        self.assertFalse(res['refused'], res['refused'])
        self.bob.invalidate_recordset()
        self.assertEqual(self.bob.parent_id, self.cat)
        # the employee form
        dee = self._person('P3A Dee', 'P3AU04')
        with Form(dee) as form:
            form.parent_id = self.cat
        self.assertEqual(dee.parent_id, self.cat)
        self.assertEqual(self.groups_of(self.portal_user), before)
        self.assertTrue(self.portal_user.share)
        if 'leave_manager_id' in self.ann._fields:
            self.assertNotEqual(self.ann.leave_manager_id, self.portal_user)
            self.assertNotEqual(dee.leave_manager_id, self.portal_user)

    def test_F14b_manager_step_falls_back(self):
        self.ann.parent_id = self.cat
        self.ann.user_id = self.env['res.users'].sudo().create({
            'name': 'P3A Ann login', 'login': 'p3a.ann.f14',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        definition = {'schema_version': 1, 'steps': [
            {'key': 's1', 'kind': 'approve', 'title': 'Their manager',
             'who': {'mode': 'manager'}, 'min_amount': 0, 'condition': None}],
            'tiers': {'enabled': False, 'fact': None},
            'safeguards': {'independent': True}}
        self.publish_route(self.company, 'generic', definition, name='P3A mgr')
        req = self.env['biz.approval.generic.request'].with_user(self.ann.user_id).create(
            {'name': 'P3A ask', 'company_id': self.company.id})
        payload = self.Engine.with_user(self.ann.user_id).submit(req)
        request = self.env['biz.approval.request'].browse(payload['id'])
        self.assertEqual(request.state, 'blocked')
        self.assertIn('No manager is recorded', request.block_reason)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aMonthOnly(P3aCommon):
    """F15 / F17 — D1, and the connected-system lane."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'P3A Monthly', 'code': 'P3AMONTHLY', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': cls.company.id, 'state': 'active'})
        cls.Batch = cls.env['hr.payroll.import.batch'].with_context(
            default_formula_config_id=cls.cfg.id)

    def in_request(self):
        return patch.object(updates_monthonly, 'request', object())

    def test_F15_a_person_cannot_make_a_lasting_pay_file(self):
        Batch = self.Batch
        with self.in_request():
            batch = Batch.create({'name': 'P3A lasting?', 'source_type': 'excel',
                                  'one_time': False, 'auto_create_employees': True,
                                  'auto_create_contracts': True})
            self.assertTrue(batch.one_time)
            self.assertFalse(batch.auto_create_employees)
            self.assertFalse(batch.auto_create_contracts)
            batch.write({'one_time': False, 'auto_create_employees': True})
            self.assertTrue(batch.one_time)
            self.assertFalse(batch.auto_create_employees)
            # a draft made before the rule is made month-only before processing
            stale = Batch.create({'name': 'P3A stale', 'source_type': 'excel'})
        stale_vals = {'one_time': False, 'auto_create_employees': True}
        super(updates_monthonly.HrPayrollImportBatchMonthOnly, stale).write(stale_vals)
        self.assertFalse(stale.one_time)
        self.assertFalse(stale._pb_month_only_belt(), "outside a request: untouched")
        with self.in_request():
            self.assertEqual(stale._pb_month_only_belt(), stale)
        self.assertTrue(stale.one_time)
        self.assertFalse(stale.auto_create_employees)
        # the guided import door ("Load Pay Data")
        if 'pb.import.wizard' in self.env:
            with self.in_request():
                res = self.env['pb.import.wizard'].create_and_load({
                    'name': 'P3A guided', 'source_type': 'excel',
                    'formula_config_id': self.cfg.id})
            made = Batch.search([('name', '=', 'P3A guided')], limit=1)
            if made:
                self.assertTrue(made.one_time)
                self.assertFalse(made.auto_create_employees)
            self.assertTrue(res is not None)
        # outside a person's request (a scheduled job, a script): unchanged
        plain = Batch.create({'name': 'P3A job', 'source_type': 'excel'})
        self.assertFalse(plain.one_time)

    def test_F15b_payrun_wizard_door(self):
        Wizard = self.env['pb.payrun.wizard']
        sig = inspect.signature(Wizard.attach_spreadsheet)
        self.assertIn('one_time', sig.parameters)
        with self.in_request():
            batch = self.Batch.create({
                'name': 'P3A run file', 'source_type': 'excel', 'one_time': False})
        self.assertTrue(batch.one_time)

    def test_F17_connected_system_lane_stays_lasting(self):
        Batch = self.Batch
        with self.in_request():
            lasting = updates_monthonly.lane_context(Batch).create({
                'name': 'P3A refresh', 'source_type': 'api_data_store',
                'one_time': False, 'auto_create_employees': False})
        self.assertFalse(lasting.one_time)
        # the record refresh runs inside the lane
        seen = {}

        def fake(rec, period_from, period_to):
            seen['lane'] = rec.env.context.get(updates_monthonly.LANE_KEY)
            return True
        from odoo.addons.pb_hr_payroll_formula.models import integration_cron
        with patch.object(integration_cron.HrIntegrationConnector,
                          '_rd54_writeback_from_store', fake):
            connector = self.env['hr.integration.connector'].sudo().new({})
            connector._rd54_writeback_from_store(None, None)
        self.assertIs(seen.get('lane'), updates_monthonly.LANE_TOKEN)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aRetired(P3aCommon):
    """F18 — the old employee import."""

    def test_F18_every_door_leads_to_updates(self):
        with self.assertRaisesRegex(UserError, 'retired'):
            self.env['employee.import.wizard'].create({})
        if 'payroll.dashboard' in self.env:
            Dash = self.env['payroll.dashboard']
            action = Dash.new({})._pb_open_updates()
            self.assertEqual(action.get('tag'), 'pb_updates_desk')
            self.assertEqual(Dash.new({}).action_get_employee_data().get('tag'),
                             'pb_updates_desk')
        self.assertFalse(self.env.ref('pb_import_advanced.action_pb_employee_wizard',
                                      raise_if_not_found=False))
        from odoo.addons.pb_import.models import pb_import
        xmlids = [row[0] for row in pb_import.LAUNCH_CANDIDATES]
        self.assertIn('pb_updates.action_pb_updates_desk', xmlids)
        self.assertNotIn('pb_import_advanced.action_pb_employee_wizard', xmlids)
        label = [r[1] for r in pb_import.LAUNCH_CANDIDATES
                 if r[0] == 'pb_updates.action_pb_updates_desk'][0]
        self.assertEqual(label, 'Update employees from a sheet')
        import ast
        from odoo.addons.pb_hr_payroll_base.wizards import employee_import_wizard
        tree = ast.parse(inspect.getsource(employee_import_wizard))
        calls = [n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertNotIn('exec', calls)
        self.assertNotIn('eval', calls)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3a')
class TestUpdatesP3aStrings(TransactionCase):
    """F21 (part) — no vendor name in this phase's sentences."""

    def test_F21_no_vendor_name(self):
        from odoo.addons.pb_updates.models import (
            updates_lanes, updates_retire, updates_managers as um)
        for module in (updates_lanes, updates_retire, um, RA):
            for line in inspect.getsource(module).splitlines():
                if '_(' in line or '_("' in line:
                    self.assertNotIn('Odoo', line, line)
