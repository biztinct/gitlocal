# -*- coding: utf-8 -*-
"""UPDATES P3b — new employees from a sheet, drafts, "since the last pay run"
(H1-H16 in UPDATES_P3B_HANDOVER.md §6).

A company of its own (the P3a fixture: proposer, second, lead; Ann, Bob and
Cat with contracts), plus:

    Kitchen   paid under "P3B Monthly" (pay item P3BX)
    Dining    paid under "P3B Daily"
    Garden    no pay scheme (two schemes in the company, so no "only one")

New test people are named "DEMO …".
"""
import base64
import json
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.biz_approval_workflow.models.ir_http import (
    is_guarded_key, scrub_params)
from odoo.addons.pb_hr_payroll_formula.models import payroll_preparation as PP
from odoo.addons.pb_updates.models import updates_joiners as UJ
from odoo.addons.pb_updates.tests.test_updates_p3a import (
    P3aCommon, csv_b64, JOB, ACC, BANK)

TEAM = 'f:hr.employee:department_id'
START = 'f:hr.contract:date_start'
WAGE = 'f:hr.contract:wage'
JOBID = 'f:hr.employee:job_id'
MGR = 'f:hr.employee:parent_id'
ITEM = 'c:P3BX'
HEAD = ['Code', 'Name', 'Team', 'Start', 'Wage', 'Meal', 'Account', 'Bank']
USED = {3: TEAM, 4: START, 5: WAGE, 6: ITEM, 7: ACC, 8: BANK}


class P3bCommon(P3aCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dept = cls.env['hr.department']
        cls.kitchen = Dept.create({'name': 'P3B Kitchen', 'company_id': cls.company.id})
        cls.dining = Dept.create({'name': 'P3B Dining', 'company_id': cls.company.id})
        cls.garden = Dept.create({'name': 'P3B Garden', 'company_id': cls.company.id})
        Config = cls.env['hr.formula.config']
        cls.monthly = Config.create({'name': 'P3B Monthly', 'code': 'P3BMONTHLY',
                                     'cycle_type': 'end_cycle', 'country_code': 'VN',
                                     'company_id': cls.company.id, 'state': 'active'})
        cls.daily = Config.create({'name': 'P3B Daily', 'code': 'P3BDAILY',
                                   'cycle_type': 'end_cycle', 'country_code': 'VN',
                                   'company_id': cls.company.id, 'state': 'active'})
        cls.env['hr.formula.rule'].create({
            'config_id': cls.monthly.id, 'name': 'P3B Meal', 'code': 'P3BX',
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
            'is_contract_component': True})
        Assign = cls.env['hr.formula.scheme.assignment']
        Assign.create({'config_id': cls.monthly.id, 'department_id': cls.kitchen.id,
                       'cycle_type': 'any'})
        Assign.create({'config_id': cls.daily.id, 'department_id': cls.dining.id,
                       'cycle_type': 'any'})
        cls.job = cls.env['hr.job'].create({'name': 'P3B Cook', 'company_id': cls.company.id})
        cls.ann.department_id = cls.kitchen
        cls.bob.work_email = 'p3b.bob@example.com'

    # ------------------------------------------------------------ helpers
    def jcols(self, used=None, scheme=0, name_col=2):
        used = dict(used or USED)
        if scheme:
            used[scheme] = UJ.SCHEME_TARGET
        return {'used': {str(k): v for k, v in used.items()},
                'identity': {'code': 1, 'name': name_col, 'email': 0}, 'heads': {}}

    def review(self, rows, used=None, scheme=0, upd=None, name_col=2):
        upd = upd if upd is not None else self.Upd
        rev = upd.review(csv_b64(rows), 'p3b.csv', self.jcols(used, scheme, name_col))
        self.assertTrue(rev['ok'], rev.get('msg'))
        return rev

    def payload(self, rev):
        return [{'row': u['row'], 'code': u['code'], 'name': u['name'],
                 'email': u['email'], 'values': u['values'],
                 'scheme': u.get('scheme') or '', 'start': u.get('start') or {}}
                for u in rev['unmatched']]

    def judge(self, rows, used=None, scheme=0, name_col=2):
        rev = self.review(rows, used, scheme, name_col=name_col)
        res = self.Upd.judge_joiners(self.payload(rev))
        self.assertTrue(res['ok'], res.get('msg'))
        return {j['row']: j for j in res['rows']}

    def add(self, rows, used=None, scheme=0, upd=None, name_col=2, **kw):
        upd = upd if upd is not None else self.Upd
        rev = self.review(rows, used, scheme, upd=upd, name_col=name_col)
        answer = upd.apply(kw.pop('name', 'P3B update'), csv_b64(rows), 'p3b.csv',
                           self.jcols(used, scheme, name_col), rev['changes'],
                           {'rows': len(rows) - 1}, joiners=self.payload(rev), **kw)
        return answer

    def people(self, name):
        return self.env['hr.employee'].with_context(active_test=False).search(
            [('name', '=', name)])

    def counts(self):
        return (self.env['hr.employee'].with_context(active_test=False).search_count([]),
                self.env['hr.contract'].with_context(active_test=False).search_count([]),
                self.env['hr.department'].with_context(active_test=False).search_count([]),
                self.env['hr.job'].with_context(active_test=False).search_count([]))

    def row(self, code, name, team='P3B Kitchen', start='2026-12-01', wage='15000000',
            meal='', acc='', bank=''):
        return [code, name, team, start, wage, meal, acc, bank]


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3b')
class TestUpdatesP3bJoiners(P3bCommon):

    # ------------------------------------------------------------ H1
    def test_H1_toggle_off_is_today(self):
        rows = [HEAD, self.row('P3AU01', 'P3A Ann', wage='2000'),
                self.row('P3BNEW1', 'DEMO P3B Nobody')]
        before = self.counts()
        rev = self.review(rows)
        self.assertEqual(len(rev['unmatched']), 1)
        self.assertNotIn('scheme', rev['unmatched'][0],
                         "no pay scheme column: the row reads as before")
        answer = self.Upd.apply('P3B off', csv_b64(rows), 'p3b.csv', self.jcols(),
                                rev['changes'], {'rows': 2, 'unmatched': 1})
        self.assertTrue(answer['ok'])
        self.assertNotIn('joiners', answer)
        self.assertEqual(self.counts()[0], before[0], "nobody created")
        self.assertFalse(self.env['pb.updates.joiner'].search(
            [('batch_id', '=', answer['batch_id'])]))
        # `joiners=[]` is the same call.
        rev = self.review(rows)
        answer2 = self.Upd.apply('P3B off 2', csv_b64(rows), 'p3b.csv', self.jcols(),
                                 rev['changes'], {'rows': 2}, joiners=[])
        self.assertTrue(answer2['ok'])
        self.assertNotIn('joiners', answer2)

    # ------------------------------------------------------------ H2
    def test_H2_no_approval_route(self):
        self.no_approval('newhire')
        calls = []
        Wizard = type(self.env['pb.people.onboard.wizard'])
        real = Wizard.create_employee

        def spy(wiz, vals):
            calls.append((dict(vals), bool(wiz.env.context.get('pb_newhire_approved_write'))))
            return real(wiz, vals)

        rows = [HEAD, self.row('P3BN01', 'DEMO P3B One', meal='250000',
                               acc='1234567890', bank='P3B Bank')]
        with patch.object(Wizard, 'create_employee', spy):
            answer = self.add(rows)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(calls[0][1], False, "the first call is a request, never the approved write")
        person = self.people('DEMO P3B One')
        self.assertEqual(len(person), 1)
        self.assertEqual(person.department_id, self.kitchen)
        self.assertEqual(person.barcode, 'P3BN01')
        contract = self.env['hr.contract'].search([('employee_id', '=', person.id)])
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract.wage, 15000000.0)
        self.assertEqual(str(contract.date_start), '2026-12-01')
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        self.assertEqual(joiner.state, 'created')
        self.assertEqual(joiner.employee_id, person)
        self.assertTrue(joiner.proposal_id.applied)
        self.assertEqual(answer['joiners_added'], 1)
        parts = self.parts(answer)
        self.assertIn('pay', parts, "the pay item goes through its lane")
        self.assertIn(person.id, [int(r['emp_id']) for r in parts['pay'].plan()])
        self.assertEqual(parts['bank'].state, 'pending', "bank waits for a second person")
        self.assertNotIn(self.proposer, self.seat_users(parts['bank']))
        self.assertEqual(self.account(person), '', "account not written yet")
        self.assertEqual(parts['bank'].updates_batch_id.id, answer['batch_id'])

    # ------------------------------------------------------------ H3
    def test_H3_approval_route_then_hook(self):
        # The HR lead who approves also makes the contract (rail 5: the last
        # approver writes as themselves), so it is an HR manager here — as the
        # shipped route seeds it (`fill_role_from_group`, HR managers).
        self.second.group_ids = [(4, self.env.ref(
            'hr_contract.group_hr_contract_manager').id)]
        self._hold(self.company, 'hr_lead', self.second)
        before = self.counts()
        rows = [HEAD, self.row('P3BN02', 'DEMO P3B Two', meal='300000',
                               acc='5550001111', bank='P3B Bank')]
        answer = self.add(rows)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(self.counts()[:2], before[:2], "nothing created while waiting")
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        self.assertEqual(joiner.state, 'waiting')
        self.assertTrue(joiner.reference.startswith('NEW'))
        self.assertEqual(answer['joiners_waiting'], 1)
        prop = joiner.proposal_id
        self.assertEqual(prop.state, 'pending')
        request = prop.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.Engine.with_user(self.second).decide(request.id, step.key, 'approve', 'ok')
        joiner.invalidate_recordset()
        person = self.people('DEMO P3B Two')
        self.assertEqual(len(person), 1, "the approved request made the person")
        self.assertEqual(joiner.state, 'created', joiner.note)
        self.assertTrue(joiner.cells_done)
        self.assertEqual(joiner.employee_id, person)
        self.assertEqual(person.barcode, 'P3BN02')
        batch = self.env['pb.updates.batch'].browse(answer['batch_id'])
        lanes = {a.lane: a for a in batch.apply_ids}
        self.assertIn('pay', lanes, "the row's pay item followed (hook): %s %s" % (
            joiner.note, [(a.lane, a.state, a.plan(), a.late_refusals()) for a in batch.apply_ids]))
        self.assertIn('bank', lanes)
        self.assertEqual(lanes['bank'].user_id, self.proposer, "sent as the proposer")
        self.assertEqual(lanes['bank'].state, 'pending')
        row = self.Upd._batch_row(batch, True)
        self.assertEqual(row['joiners'][0]['state'], 'created')

    def test_H3b_turned_down(self):
        before = self.counts()
        answer = self.add([HEAD, self.row('P3BN03', 'DEMO P3B Three')])
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        request = joiner.proposal_id.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.Engine.with_user(self.lead).decide(request.id, step.key, 'reject', 'no')
        joiner.invalidate_recordset()
        self.assertEqual(joiner.state, 'turned_down')
        self.assertEqual(self.counts()[:2], before[:2])
        self.assertFalse(self.people('DEMO P3B Three'))

    def test_H3c_apply_now_when_the_follow_up_failed(self):
        answer = self.add([HEAD, self.row('P3BN04', 'DEMO P3B Four', meal='100')])
        joiner = self.env['pb.updates.joiner'].search([('batch_id', '=', answer['batch_id'])])
        request = joiner.proposal_id.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        Desk = type(self.env['pb.updates.desk'])
        with patch.object(Desk, '_joiner_apply_cells',
                          side_effect=ValueError('P3B boom')):
            self.Engine.with_user(self.lead).decide(request.id, step.key, 'approve', 'ok')
        joiner.invalidate_recordset()
        self.assertTrue(self.people('DEMO P3B Four'), "the hire stands")
        self.assertEqual(joiner.state, 'needs_attention')
        self.assertIn('still to apply', joiner.note)
        home = self.Upd.get_joiners_waiting()['items']
        self.assertTrue(any(i['id'] == joiner.id and i['can_apply_now'] for i in home))
        res = self.Upd.apply_now(joiner.id)
        self.assertTrue(res['ok'], res.get('msg'))
        joiner.invalidate_recordset()
        self.assertEqual(joiner.state, 'created')
        self.assertTrue(joiner.cells_done)

    # ------------------------------------------------------------ H4
    def test_H4_duplicates_refused(self):
        self.cat.department_id = self.garden
        self.cat.active = False
        first = self.add([HEAD, self.row('P3BW01', 'DEMO P3B Waiting')])
        self.assertTrue(first['ok'])
        before = self.counts()
        # The row finds its person by code only, and the name is a value:
        # a name that IS the identity finds the active person instead.
        used = dict(USED)
        used[2] = 'f:hr.employee:name'
        rows = [HEAD,
                self.row('P3AU03', 'DEMO P3B Code twin'),               # Cat's code (archived)
                self.row('P3BD02', 'P3A Ann'),                          # Ann, Kitchen
                self.row('P3BD03', 'P3A Cat', team='P3B Garden'),       # archived
                self.row('P3BD04', 'DEMO P3B Twin'),
                self.row('P3BD05', 'DEMO P3B Twin'),
                self.row('P3BD06', 'DEMO P3B Waiting')]
        judged = self.judge(rows, used=used, name_col=0)
        self.assertIn('P3A Cat', judged[2]['block'])
        self.assertIn('P3A Ann', judged[3]['block'])
        self.assertIn('already here', judged[3]['block'])
        self.assertIn('archived', judged[4]['block'])
        self.assertIn('twice', judged[5]['block'])
        self.assertIn('twice', judged[6]['block'])
        self.assertIn('already waiting for approval', judged[7]['block'])
        self.assertFalse(any(j['addable'] for j in judged.values()))
        email = self.judge([['Code', 'Name', 'Team', 'Start', 'Email'],
                            ['P3BD07', 'DEMO P3B Mail', 'P3B Kitchen', '2026-12-01',
                             'p3b.bob@example.com']],
                           used={3: TEAM, 4: START, 5: 'f:hr.employee:work_email'})
        self.assertIn('P3A Bob', email[2]['block'])
        answer = self.add(rows, used=used, name_col=0)
        self.assertFalse(answer['ok'])
        self.assertEqual(self.counts(), before, "nothing created")

    # ------------------------------------------------------------ H5
    def test_H5_unknowns_bad_date_bad_wage(self):
        before = self.counts()
        used = {3: TEAM, 4: START, 5: WAGE, 6: JOBID, 7: MGR}
        head = ['Code', 'Name', 'Team', 'Start', 'Wage', 'Job', 'Manager']
        rows = [head,
                ['P3BU01', 'DEMO P3B U1', 'P3B Nowhere', '2026-12-01', '100', '', ''],
                ['P3BU02', 'DEMO P3B U2', 'P3B Kitchen', '2026-12-01', '100', 'P3B Astronaut', ''],
                ['P3BU03', 'DEMO P3B U3', 'P3B Kitchen', '2026-12-01', '100', '', 'Nobody P3B'],
                ['P3BU04', 'DEMO P3B U4', 'P3B Kitchen', 'next week', '100', '', ''],
                ['P3BU05', 'DEMO P3B U5', 'P3B Kitchen', '2029-01-01', '100', '', ''],
                ['P3BU06', 'DEMO P3B U6', 'P3B Kitchen', '2026-12-01', '-5', '', ''],
                ['P3BU07', 'DEMO P3B U7', 'P3B Kitchen', '2026-12-01', 'abc', '', '']]
        judged = self.judge(rows, used=used)
        self.assertIn('No team', judged[2]['cells'][TEAM]['why'])
        self.assertIn('No job', judged[3]['cells'][JOBID]['why'])
        self.assertIn('Nobody is called', judged[4]['cells'][MGR]['why'])
        self.assertIn('not a date', judged[5]['cells'][START]['why'])
        self.assertIn('year', judged[6]['cells'][START]['why'])
        self.assertIn('positive', judged[7]['cells'][WAGE]['why'])
        self.assertIn('positive', judged[8]['cells'][WAGE]['why'])
        self.assertFalse(any(j['addable'] for j in judged.values()))
        answer = self.add(rows, used=used)
        self.assertFalse(answer['ok'])
        self.assertEqual(self.counts(), before, "no team, job or person created")

    # ------------------------------------------------------------ H6
    def test_H6_pay_scheme_column(self):
        Assign = self.env['hr.formula.scheme.assignment'].with_context(active_test=False)
        map_before = Assign.search_count([])
        used = {3: TEAM, 4: START, 5: WAGE}
        head = ['Code', 'Name', 'Team', 'Start', 'Wage', 'Pay scheme']
        rows = [head,
                ['P3BS01', 'DEMO P3B S1', 'P3B Kitchen', '2026-12-01', '100', 'P3B Monthly'],
                ['P3BS02', 'DEMO P3B S2', 'P3B Kitchen', '2026-12-01', '100', 'P3B Daily'],
                ['P3BS03', 'DEMO P3B S3', 'P3B Garden', '2026-12-01', '100', 'P3B Daily']]
        judged = self.judge(rows, used=used, scheme=6)
        self.assertTrue(judged[2]['addable'], judged[2])
        self.assertEqual(judged[2]['scheme'], 'P3B Monthly')
        self.assertFalse(judged[3]['addable'])
        self.assertEqual(judged[3]['cells'][TEAM]['why'],
                         "P3B Kitchen is paid under P3B Monthly, not P3B Daily. "
                         "Change the team or the pay scheme column.")
        self.assertTrue(judged[4]['addable'], judged[4])
        self.assertIn('No pay scheme covers P3B Garden', judged[4]['scheme_note'])
        self.no_approval('newhire')
        answer = self.add(rows, used=used, scheme=6)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(answer['joiners_added'], 2)
        self.assertEqual(Assign.search_count([]), map_before, "the scheme map is untouched")
        # The column reads as the check by its heading, and is remembered.
        cols = self.Upd.read_columns(csv_b64(rows), 'p3b.csv')
        self.assertEqual(cols['columns'][5]['target'], UJ.SCHEME_TARGET)

    # ------------------------------------------------------------ H7
    def test_H7_no_wage_no_contract(self):
        self.no_approval('newhire')
        used = {3: TEAM, 4: START}
        rows = [['Code', 'Name', 'Team', 'Start'],
                ['P3BC01', 'DEMO P3B NoPay', 'P3B Kitchen', '2026-12-01']]
        judged = self.judge(rows, used=used)
        self.assertTrue(judged[2]['addable'])
        self.assertTrue(judged[2]['no_contract'])
        answer = self.add(rows, used=used)
        self.assertTrue(answer['ok'], answer.get('msg'))
        person = self.people('DEMO P3B NoPay')
        self.assertTrue(person)
        self.assertFalse(self.env['hr.contract'].search([('employee_id', '=', person.id)]))

    # ------------------------------------------------------------ H8
    def test_H8_more_than_200(self):
        rows = [HEAD] + [self.row('P3BM%03d' % i, 'DEMO P3B Many %03d' % i)
                         for i in range(201)]
        rev = self.review(rows)
        res = self.Upd.judge_joiners(self.payload(rev))
        self.assertFalse(res['ok'])
        self.assertIn('At most 200', res['msg'])
        before = self.counts()
        answer = self.add(rows)
        self.assertFalse(answer['ok'])
        self.assertIn('At most 200', answer['msg'])
        self.assertEqual(self.counts(), before)

    def test_H8b_copies_do_not_count_towards_200(self):
        # 199 new people and 5 rows that are Ann (name + team): 204 rows,
        # 199 that could be new — allowed; Ann's rows are refused as copies.
        used = dict(USED)
        used[2] = 'f:hr.employee:name'
        rows = [HEAD] + [self.row('P3BQ%03d' % i, 'DEMO P3B Quota %03d' % i) for i in range(199)] \
            + [self.row('P3BA%02d' % i, 'P3A Ann') for i in range(5)]
        rev = self.review(rows, used=used, name_col=0)
        res = self.Upd.judge_joiners(self.payload(rev))
        self.assertTrue(res['ok'], res.get('msg'))
        blocked = [j for j in res['rows'] if j['block']]
        self.assertEqual(len(blocked), 5)
        self.assertTrue(all('P3A Ann' in j['block'] for j in blocked))

    # ------------------------------------------------------------ H9
    def test_H9_undo_keeps_new_people(self):
        self.no_approval('newhire')
        self.no_approval('records')
        used = {3: TEAM, 4: START, 5: WAGE, 6: JOB}
        rows = [['Code', 'Name', 'Team', 'Start', 'Wage', 'Job title'],
                ['P3AU01', 'P3A Ann', '', '', '', 'Head Cook'],
                ['P3BK01', 'DEMO P3B Keep', 'P3B Kitchen', '2026-12-01', '100', 'Cook']]
        answer = self.add(rows, used=used)
        self.assertTrue(answer['ok'], answer.get('msg'))
        person = self.people('DEMO P3B Keep')
        self.assertTrue(person)
        self.assertEqual(self.ann.job_title, 'Head Cook')
        res = self.Upd.undo(answer['batch_id'])
        self.assertTrue(res['ok'], res.get('msg'))
        self.ann.invalidate_recordset()
        self.assertEqual(self.ann.job_title, 'Operator', "existing person undone")
        person.invalidate_recordset()
        self.assertTrue(person.exists() and person.active, "the new person stays")
        row = self.Upd._batch_row(self.env['pb.updates.batch'].browse(answer['batch_id']), True)
        self.assertTrue(row['joiners'])

    # ------------------------------------------------------------ H10
    def test_H10_no_back_door(self):
        self.assertTrue(is_guarded_key('pb_newhire_approved_write'))
        params = {'model': 'pb.updates.desk', 'method': 'apply', 'args': [],
                  'kwargs': {'context': {'pb_newhire_approved_write': True}}}
        self.assertEqual(scrub_params(params), ['pb_newhire_approved_write'])
        before = self.counts()
        upd = self.Upd.with_context(pb_newhire_approved_write=True)
        answer = self.add([HEAD, self.row('P3BB01', 'DEMO P3B Backdoor')], upd=upd)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(answer['joiners_waiting'], 1, "still a request")
        self.assertEqual(self.counts()[:2], before[:2], "nobody created")
        with self.assertRaises(AccessError):
            self.env['pb.updates.joiner'].with_user(self.proposer).create({
                'batch_id': answer['batch_id'], 'company_id': self.company.id,
                'user_id': self.proposer.id, 'name': 'DEMO P3B Forged'})
        # Updates has no method that creates a person without the wizard.
        src = open(UJ.__file__).read()
        self.assertNotIn("['hr.employee'].create", src)
        self.assertNotIn("[EMP].create", src)
        self.assertNotIn("['hr.contract'].create", src)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3b')
class TestUpdatesP3bDrafts(P3bCommon):

    def test_H11_draft_private_and_continued(self):
        rows = [HEAD, self.row('P3AU01', 'P3A Ann', wage='2000'),
                self.row('P3AU02', 'P3A Bob', wage='3000')]
        b64 = csv_b64(rows)
        saved = self.Upd.save_draft(0, 'lasting', None, 'p3b.csv', b64,
                                    self.jcols(), {'fixes': [{'row': 2, 'field_id': WAGE,
                                                              'value': '2100'}],
                                                   'matched': {'2': self.ann.id, '3': self.bob.id}},
                                    'review')
        self.assertTrue(saved['ok'])
        draft_id = saved['draft_id']
        again = self.Upd.save_draft(draft_id, 'lasting', None, 'p3b.csv', '', None,
                                    {'addNew': True}, 'apply')
        self.assertEqual(again['draft_id'], draft_id, "same draft, no second file")
        mine = self.Upd.list_drafts()['drafts']
        self.assertEqual([d['id'] for d in mine], [draft_id])
        self.assertEqual(mine[0]['step'], 'apply')
        other = self.uenv(user=self.second)['pb.updates.desk']
        self.assertFalse(other.list_drafts()['drafts'], "private to its owner")
        self.assertFalse(self.env['pb.updates.batch'].with_user(self.second).search(
            [('id', '=', draft_id)]))
        self.assertFalse(other.open_draft(draft_id)['ok'])
        opened = self.Upd.open_draft(draft_id)
        self.assertTrue(opened['ok'])
        self.assertEqual(opened['file_b64'], b64)
        self.assertEqual(opened['choices']['fixes'][0]['value'], '2100')
        self.assertTrue(opened['choices']['addNew'], "choices merged")
        self.assertEqual(opened['step'], 'apply')
        # Bob archived meanwhile: reading the file again finds nobody for row 3
        # (the screen lists him in its notice, from the saved `matched`).
        self.bob.active = False
        rev = self.review(rows)
        self.assertEqual([u['row'] for u in rev['unmatched']], [3])
        self.assertEqual(str(self.bob.id), str(opened['choices']['matched']['3']))

    def test_H12_draft_becomes_the_update(self):
        rows = [HEAD, self.row('P3AU01', 'P3A Ann', wage='2000')]
        b64 = csv_b64(rows)
        Batch = self.env['pb.updates.batch']
        history_before = self.Upd.get_history(200)['total']
        draft_id = self.Upd.save_draft(0, 'lasting', None, 'p3b.csv', b64,
                                       self.jcols(), {}, 'review')['draft_id']
        self.assertEqual(self.Upd.get_history(200)['total'], history_before,
                         "a draft is never counted")
        self.assertNotIn(draft_id, [h['id'] for h in self.Upd.get_history(200)['batches']])
        rev = self.review(rows)
        answer = self.Upd.apply('P3B from a draft', b64, 'p3b.csv', self.jcols(),
                                rev['changes'], {'rows': 1}, draft_id=draft_id)
        self.assertTrue(answer['ok'], answer.get('msg'))
        self.assertEqual(answer['batch_id'], draft_id, "the same record")
        batch = Batch.browse(draft_id)
        self.assertEqual(batch.state, 'sent')
        self.assertEqual(batch.name, 'P3B from a draft')
        self.assertEqual(self.env['ir.attachment'].search_count(
            [('res_model', '=', 'pb.updates.batch'), ('res_id', '=', draft_id)]), 1)
        self.assertEqual(self.Upd.get_history(200)['total'], history_before + 1)
        self.assertFalse(self.Upd.list_drafts()['drafts'])
        # Discard.
        gone = self.Upd.save_draft(0, 'lasting', None, 'p3b.csv', b64, {}, {}, 'match')['draft_id']
        att = Batch.browse(gone).attachment_id
        res = self.Upd.discard_draft(gone)
        self.assertTrue(res['ok'])
        self.assertFalse(Batch.browse(gone).exists())
        self.assertFalse(att.exists())
        # Somebody else's draft: not theirs to discard (unless records manager).
        other = self.Upd.save_draft(0, 'lasting', None, 'p3b.csv', b64, {}, {}, 'match')['draft_id']
        lead = self.uenv(user=self.lead)['pb.updates.desk']
        self.assertFalse(lead.discard_draft(other)['ok'])
        manager = self.uenv(user=self.second)['pb.updates.desk']
        self.assertTrue(manager.discard_draft(other)['ok'])
        # An apply-less non-draft batch reads as before.
        plain = Batch.create({'name': 'P3B plain'})
        self.assertEqual(plain.state, 'sent')
        self.assertEqual(self.Upd._batch_state(plain.apply_ids)[0], 'applied')

    def test_H12b_oneoff_draft_kind(self):
        b64 = csv_b64([['Code', 'Bonus'], ['P3AU01', '100']])
        res = self.Upd.save_draft(0, 'oneoff', '2026-11-01', 'p3b.csv', b64, {}, {}, 'match')
        self.assertTrue(res['ok'])
        draft = self.Upd.list_drafts()['drafts'][0]
        self.assertEqual(draft['kind'], 'oneoff')
        self.assertEqual(draft['month'], '2026-11-01')


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3b')
class TestUpdatesP3bSinceLastRun(P3bCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dan = cls._person('DEMO P3B Dan', 'P3BDAN')
        cls.dan_contract = cls.env['hr.contract'].create({
            'name': 'P3B Dan', 'employee_id': cls.dan.id, 'company_id': cls.company.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2026-11-05',
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.kind.id})
        cls.contracts = {c.employee_id.id: c for c in cls.env['hr.contract'].search(
            [('employee_id', 'in', (cls.ann | cls.bob | cls.cat).ids)])}
        for person in (cls.ann, cls.bob, cls.cat):
            slip = cls.env['hr.payslip'].create({
                'name': 'P3B Oct %s' % person.name, 'employee_id': person.id,
                'contract_id': cls.contracts[person.id].id,
                'date_from': '2026-10-01', 'date_to': '2026-10-31',
                'company_id': cls.company.id, 'formula_config_id': cls.monthly.id})
            slip.write({'state': 'done'})
        cls.prep = cls.env['hr.payroll.preparation'].with_context(
            **{PP._CTX: PP._TOKEN}).create({
                'config_id': cls.monthly.id, 'owner_id': cls.env.uid,
                'date_from': '2026-11-01', 'date_to': '2026-11-30',
                'scope_key': 'p3b-since',
                'employee_ids': [(6, 0, (cls.ann | cls.bob | cls.cat | cls.dan).ids)]})

    def _apply(self, **vals):
        rec = self.Apply.sudo().create(dict({
            'name': 'RDP3B', 'source': 'import', 'company_id': self.company.id,
            'user_id': self.proposer.id, 'applied': True, 'state': 'applied',
            'plan_json': '[]'}, **vals))
        return rec

    def _change(self, apply_rec, person, key, label, old, new, day):
        return self.env['pb.records.change'].sudo().create({
            'apply_id': apply_rec.id, 'employee_id': person.id, 'field_key': key,
            'field_label': label, 'old_label': old, 'new_label': new,
            'effective_date': day})

    def _prep(self, people, key):
        return self.env['hr.payroll.preparation'].with_context(
            **{PP._CTX: PP._TOKEN}).create({
                'config_id': self.monthly.id, 'owner_id': self.env.uid,
                'date_from': '2026-11-01', 'date_to': '2026-11-30',
                'scope_key': key, 'employee_ids': [(6, 0, people.ids)]})

    def test_H13_five_sources(self):
        quiet = self._prep(self.ann | self.bob | self.cat, 'p3b-quiet')
        self.assertIsNone(quiet._updates_since_last_run(), "nothing to show yet")
        written = self._apply()
        self._change(written, self.ann, 'c:P3BX', 'P3B Meal', '0', '250,000', date(2026, 11, 3))
        self._change(written, self.ann, 'f:hr.contract:wage', 'Wage', '1,000', '2,000', date(2026, 11, 3))
        self._change(written, self.bob, 'b:acc_number', 'Account number', '1111222233',
                     '9988776655', date(2026, 11, 4))
        self._change(written, self.bob, 'f:hr.employee:job_title', 'Job title', 'Operator',
                     'Fitter', date(2026, 11, 4))
        undone = self._apply(undone=True)
        self._change(undone, self.cat, 'f:hr.employee:job_title', 'Job title', 'A', 'B',
                     date(2026, 11, 4))
        old = self._apply()
        before = self._change(old, self.cat, 'f:hr.employee:work_phone', 'Work phone', '1', '2',
                              date(2026, 10, 15))
        self.env.cr.execute("UPDATE pb_records_change SET create_date = '2026-10-15' WHERE id = %s",
                            (before.id,))
        self.env.invalidate_all()
        # One-off for November.
        batch = self.env['pb.updates.batch'].create({'name': 'P3B one-off', 'kind': 'oneoff'})
        self.env['pb.updates.oneoff'].sudo().create({
            'employee_id': self.cat.id, 'company_id': self.company.id, 'code': 'P3BBONUS',
            'label': 'P3B Bonus', 'period_month': '2026-11-01', 'action': 'set',
            'amount': 500.0, 'state': 'approved', 'batch_id': batch.id,
            'net_role': 'earning'})
        # Scheduled inside the period.
        self._apply(applied=False, state='scheduled', start_date='2026-11-20',
                    plan_json=json.dumps([{'emp_id': self.cat.id, 'field_id': 'f:hr.contract:wage',
                                           'field_label': 'Wage', 'new_label': '3,000'}]))
        # Pay-item history: one by Records (same code + date as above, de-duplicated)
        # and one by something else.
        Template = self.env['hr.contract.advantage.template']
        tmpl = Template.search([('code', '=', 'P3BX')], limit=1) or Template.create(
            {'name': 'P3B Meal', 'code': 'P3BX'})
        Change = self.env['hr.contract.advantage.change'].sudo()
        Change.create({'contract_id': self.contracts[self.ann.id].id,
                       'advantage_template_id': tmpl.id, 'old_amount': 0,
                       'new_amount': 250000, 'effective_date': '2026-11-03',
                       'change_source': 'manual'})
        Change.create({'contract_id': self.contracts[self.cat.id].id,
                       'advantage_template_id': tmpl.id, 'old_amount': 0,
                       'new_amount': 70000, 'effective_date': '2026-11-02',
                       'change_source': 'import'})
        since = self.prep._updates_since_last_run()
        by = {p['name']: p for p in since['people']}
        ann = [i['text'] for i in by['P3A Ann']['items']]
        self.assertEqual(sum('P3B Meal' in t for t in ann), 1, ann)
        self.assertTrue(any('by %s' % self.proposer.name in t for t in ann))
        self.assertIn('contract', by['P3A Ann']['kinds'])
        bob = ' '.join(i['text'] for i in by['P3A Bob']['items'])
        self.assertIn('•••• 6655', bob)
        self.assertNotIn('9988776655', bob)
        self.assertNotIn('1111222233', bob)
        cat = [i['text'] for i in by['P3A Cat']['items']]
        self.assertFalse(any('→ B' in t for t in cat), "an undone change is not shown")
        self.assertFalse(any('Work phone' in t for t in cat), "before the last pay run")
        self.assertTrue(any('P3B Bonus' in t for t in cat))
        self.assertTrue(any('Scheduled' in t for t in cat))
        self.assertTrue(any('changed on the contract' in t for t in cat))
        self.assertTrue(any(t.startswith('New: DEMO P3B Dan') for t in
                            (i['text'] for i in by['DEMO P3B Dan']['items'])))
        self.assertEqual(since['people_count'], 4)
        self.assertTrue(since['line'].startswith('Since the last pay run: 4 people have changes ('))
        self.assertIn('1 new', since['line'])

    def test_H13b_never_paid_since_contract_start(self):
        written = self._apply()
        self._change(written, self.dan, 'f:hr.employee:job_title', 'Job title', '', 'Cook',
                     date(2026, 11, 6))
        early = self._change(written, self.dan, 'f:hr.employee:work_phone', 'Work phone', '',
                             '1', date(2026, 10, 1))
        self.env.cr.execute("UPDATE pb_records_change SET create_date = '2026-10-01' WHERE id = %s",
                            (early.id,))
        self.env.invalidate_all()
        since = self.prep._updates_since_last_run()
        dan = [i['text'] for p in since['people'] if p['name'] == 'DEMO P3B Dan'
               for i in p['items']]
        self.assertTrue(any('Cook' in t for t in dan))
        self.assertFalse(any('Work phone' in t for t in dan), "before the contract start")

    def test_H14_nothing_to_show_adds_no_key(self):
        Base = PP.PayrollPreparation
        quiet = self._prep(self.ann | self.bob | self.cat, 'p3b-quiet14')
        with patch.object(Base, '_workspace', lambda self: {'base': 1}):
            answer = quiet._workspace()
        self.assertNotIn('since_last_run', answer)
        self.assertEqual(set(answer), {'base', 'scheduled_changes', 'updates_oneoffs_note'},
                         "exactly the keys of before this phase")
        written = self._apply()
        self._change(written, self.ann, 'f:hr.employee:job_title', 'Job title', 'A', 'B',
                     date(2026, 11, 4))
        with patch.object(Base, '_workspace', lambda self: {'base': 1}):
            answer = quiet._workspace()
        self.assertIn('since_last_run', answer)


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p3b')
class TestUpdatesP3bSheet(P3bCommon):

    def test_blank_new_employee_sheet(self):
        import openpyxl
        import io
        res = self.Upd.download_joiner_sheet(self.monthly.id)
        self.assertTrue(res['ok'])
        self.assertNotIn('Odoo', res['filename'])
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
        heads = [c.value for c in wb['Records'][1]]
        self.assertEqual(heads[:3], ['Employee code', 'Name', 'Work email'])
        self.assertIn('P3B Meal', heads)
        self.assertEqual(heads[-1], 'Pay scheme')
        self.assertEqual(wb['Records'].max_row, 1, "headings only")
        self.assertIn('Read me', wb.sheetnames)
        # It reads back as a sheet of ours: no matching step.
        out = io.BytesIO()
        wb['Records'].append(['P3BX01', 'DEMO P3B Sheet', '', 'P3B Kitchen'])
        wb.save(out)
        cols = self.Upd.read_columns(base64.b64encode(out.getvalue()).decode(), 'new.xlsx')
        self.assertTrue(cols['ok'], cols.get('msg'))
        self.assertTrue(cols['from_sheet'])
        self.assertEqual(cols['columns'][-1]['target'], UJ.SCHEME_TARGET)

    def test_H16_no_vendor_name_in_new_strings(self):
        import os
        root = os.path.dirname(os.path.dirname(__file__))
        for rel in ('models/updates_joiners.py', 'models/updates_drafts.py',
                    'models/updates_sincerun.py', 'static/src/js/payrun_since.js',
                    'static/src/xml/payrun_since.xml'):
            with open(os.path.join(root, rel)) as handle:
                self.assertNotIn('Odoo', handle.read(), rel)
