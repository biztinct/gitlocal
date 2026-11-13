# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ETP E3 — the facade (handover docs/handovers/etp/E3_HANDOVER.md, tests
E3.1–E3.9). Everything runs AS the employee login (`with_user(share)`): the
facade's sudo seams are what is under test."""
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_me_project_time.models.project_time import PARAM, PbMeProjectTime

from .common import MONDAY, TZ, lines_of, setup_e3

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestE3ProjectTime(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        setup_e3(cls, 'test_e3_facade')

    def _pt(self, user=None):
        return self.env['pb.me.project.time'].with_user(user or self.share)

    def _flat(self, groups):
        projects = [p for g in groups for p in g['projects']]
        return {p['id']: p for p in projects}

    # ------------------------------------------------------------- E3.1
    def test_e3_1_pickable_projects(self):
        groups = self._pt().pickable_projects(self.share_emp)
        self.assertTrue(groups)
        self.assertEqual(groups[0]['company_id'], self.company.id,
                         "the employee's company comes first")
        flat = self._flat(groups)
        if self.internal.privacy_visibility in ('employees', 'portal'):
            self.assertEqual(groups[0]['projects'][0]['id'], self.internal.id,
                             'the Internal project is listed first')
        self.assertIn(self.proj.id, flat)
        self.assertEqual([t['id'] for t in flat[self.proj.id]['tasks']],
                         [self.task_a.id, self.task_b.id])
        all_tasks = {t['id'] for p in flat.values() for t in p['tasks']}
        if self.leave_task:
            self.assertNotIn(self.leave_task.id, all_tasks, 'never the time-off task')
        self.assertNotIn(self.followers_proj.id, flat)
        self.assertNotIn(self.other_proj.id, flat)
        self.assertNotIn(self.tpl_proj.id, flat, 'a template is never listed')
        # following the project as the employee's partner makes it pickable
        self.followers_proj.message_subscribe(partner_ids=self.share.partner_id.ids)
        flat = self._flat(self._pt().pickable_projects(self.share_emp))
        self.assertIn(self.followers_proj.id, flat)
        self.assertNotIn(self.tpl_proj.id, flat)
        # the search narrows on project or task name
        found = self._flat(self._pt().pickable_projects(self.share_emp, query='e3 build'))
        self.assertEqual(list(found), [self.proj.id])
        self.assertEqual([t['id'] for t in found[self.proj.id]['tasks']], [self.task_b.id])

    # ------------------------------------------------------------- E3.2
    def test_e3_2_parse_hours(self):
        Pt = self._pt()
        for text, value in (('8', 8.0), ('7.5', 7.5), ('7,5', 7.5), ('1:30', 1.5),
                            ('1h30', 1.5), ('0:45', 0.75), ('', 0.0), (' 2 ', 2.0),
                            ('45m', 0.75), ('2h', 2.0), (None, 0.0), (6, 6.0),
                            ('24', 24.0)):
            self.assertEqual(Pt.parse_hours(text), value, repr(text))
        for junk, words in (('-1', 'below zero'), ('25', '24 hours at most'),
                            ('abc', 'Type hours like'), ('1:75', 'Minutes go up to 59'),
                            ('8..5', 'Type hours like')):
            with self.assertRaises(UserError) as caught:
                Pt.parse_hours(junk)
            self.assertIn(words, str(caught.exception), junk)

    # ------------------------------------------------------------- E3.3
    def test_e3_3_set_cell_creates_updates_unlinks(self):
        Pt = self._pt()
        res = Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '8')
        self.assertTrue(res['ok'])
        self.assertEqual(res['week_logged'], 8.0)
        self.assertEqual(res['week_target'], 40.0)
        lines = lines_of(self, self.share_emp)
        self.assertEqual(len(lines), 1)
        line = lines
        self.assertEqual(line.employee_id, self.share_emp)
        self.assertEqual(line.project_id, self.proj)
        self.assertEqual(line.task_id, self.task_a)
        self.assertEqual(line.date, MONDAY)
        self.assertEqual(line.unit_amount, 8.0)
        self.assertEqual(line.name, '/')
        self.assertEqual(line.create_uid, self.share, 'sudo keeps the uid (E-R2)')
        self.assertEqual(line.company_id, self.company)
        self.assertEqual(line.user_id, self.share)

        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '7.5')
        lines = lines_of(self, self.share_emp)
        self.assertEqual(lines, line, 'the same line is updated')
        self.assertEqual(line.unit_amount, 7.5)

        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '0')
        self.assertFalse(lines_of(self, self.share_emp), '0 and no note → unlinked')

        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '2',
                    note='Wireframes  for the  home page')
        line = lines_of(self, self.share_emp)
        self.assertEqual(line.name, 'Wireframes for the home page')
        # 0 with the note kept (note=None keeps it) → the line stays, at 0 h
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '')
        self.assertEqual(lines_of(self, self.share_emp), line)
        self.assertEqual(line.unit_amount, 0.0)
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '', note='')
        self.assertFalse(lines_of(self, self.share_emp))

        # a project the person may not log on → refused, nothing written
        for pid, tid in ((self.followers_proj.id, 0), (self.other_proj.id, 0),
                         (self.tpl_proj.id, 0), (self.proj.id, self.other_task().id)):
            with self.assertRaises(UserError) as caught:
                Pt.set_cell(self.share_emp, pid, tid, MONDAY, '1')
            self.assertIn('cannot log time on that project', str(caught.exception))
        if self.leave_task:
            with self.assertRaises(UserError):
                Pt.set_cell(self.share_emp, self.leave_task.project_id.id,
                            self.leave_task.id, MONDAY, '1')
        self.assertFalse(lines_of(self, self.share_emp))

        # more than 24 in a cell, and more than 24 in a day
        with self.assertRaises(UserError):
            Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '25')
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '20')
        with self.assertRaises(UserError) as caught:
            Pt.set_cell(self.share_emp, self.proj.id, self.task_b.id, MONDAY, '5')
        self.assertIn('A day has 24 hours', str(caught.exception))
        self.assertEqual(lines_of(self, self.share_emp).task_id, self.task_a)
        _logger.info('E3.3 | create → update → unlink → note → refusals')

    def other_task(self):
        """A task of ANOTHER project, passed with self.proj — refused."""
        return self.env['project.task'].create({
            'name': 'E3 Elsewhere', 'project_id': self.followers_proj.id})

    # ------------------------------------------------------------- E3.4
    def test_e3_4_two_backend_lines_on_one_key(self):
        tue = MONDAY + timedelta(days=1)
        for hours in (2.0, 3.0):
            self.Line.create({
                'project_id': self.proj.id, 'task_id': self.task_a.id,
                'employee_id': self.share_emp.id, 'date': tue,
                'unit_amount': hours, 'name': 'backend %s' % hours})
        week = self._pt().get_week(self.share_emp, MONDAY)
        row = next(r for r in week['rows'] if r['key'] == '%s-%s' % (self.proj.id, self.task_a.id))
        self.assertEqual(row['cells'][1]['hours'], 5.0, 'the grid shows their sum')
        self.assertEqual(len(row['cells'][1]['line_ids']), 2)
        self._pt().set_cell(self.share_emp, self.proj.id, self.task_a.id, tue, '6')
        lines = lines_of(self, self.share_emp)
        self.assertEqual(len(lines), 1, 'the first is kept, the rest unlinked')
        self.assertEqual(lines.unit_amount, 6.0)
        self.assertEqual(lines.name, 'backend 2.0', 'note=None keeps the note')

    # ------------------------------------------------------------- E3.5
    def test_e3_5_leave_lines_are_shown_and_never_written(self):
        if 'global_leave_id' not in self.Line._fields:
            self.skipTest('project_timesheet_holidays is not installed')
        wed = MONDAY + timedelta(days=2)
        # a public holiday on the person's calendar, the way
        # project_timesheet_holidays makes its lines (create generates them)
        start = datetime(2026, 9, 15, 17, 0)        # 00:00 Wednesday in UTC+7
        gl = self.env['resource.calendar.leaves'].create({
            'name': 'E3 Founders Day', 'calendar_id': self.cal.id,
            'company_id': self.company.id, 'time_type': 'leave',
            'date_from': start, 'date_to': start + timedelta(days=1)})
        generated = self.Line.search([('employee_id', '=', self.share_emp.id),
                                      ('global_leave_id', '=', gl.id)])
        if not generated:
            generated = self.Line.create({
                'project_id': self.internal.id,
                'task_id': self.leave_task.id or False,
                'employee_id': self.share_emp.id, 'date': wed,
                'unit_amount': 8.0, 'name': 'E3 Founders Day',
                'global_leave_id': gl.id})
        self.assertTrue(generated)
        # and a leave line on an ordinary, pickable key
        direct = self.Line.create({
            'project_id': self.proj.id, 'task_id': self.task_a.id,
            'employee_id': self.share_emp.id, 'date': wed, 'unit_amount': 1.0,
            'name': 'E3 leave on a work task', 'global_leave_id': gl.id})
        leave_hours = sum(generated.mapped('unit_amount')) + 1.0

        data = self._pt().get_week(self.share_emp, MONDAY)
        leave_row = next(r for r in data['rows'] if r['kind'] == 'leave')
        cell = leave_row['cells'][2]
        self.assertTrue(cell['locked'])
        self.assertIn('E3 Founders Day', cell['note'])
        self.assertAlmostEqual(cell['hours'], leave_hours, delta=0.01)
        day = data['week']['days'][2]
        self.assertEqual(day['target'], 0.0, 'a public holiday → target 0 (D4)')
        self.assertAlmostEqual(day['total'], leave_hours, delta=0.01,
                               msg='counted in the day total')
        self.assertEqual(day['logged'], 0.0)
        self.assertEqual(day['state'], 'leave')
        self.assertEqual(data['week']['target'], 32.0)
        work_row = [r for r in data['rows'] if r['kind'] == 'project'
                    and r['key'] == '%s-%s' % (self.proj.id, self.task_a.id)]
        self.assertFalse(work_row, 'a leave line does not make a work row')

        res = self._pt().set_cell(self.share_emp, self.proj.id, self.task_a.id, wed, '3')
        self.assertTrue(res['ok'])
        direct.invalidate_recordset()
        self.assertEqual(direct.unit_amount, 1.0, 'the leave line is left alone')
        work = self.Line.search([('employee_id', '=', self.share_emp.id),
                                 ('task_id', '=', self.task_a.id), ('date', '=', wed),
                                 ('global_leave_id', '=', False)])
        self.assertEqual(len(work), 1)
        self.assertEqual(work.unit_amount, 3.0)
        self._pt().set_cell(self.share_emp, self.proj.id, self.task_a.id, wed, '0')
        self.assertTrue(direct.exists(), 'clearing the cell never unlinks a leave line')
        self.assertFalse(work.exists())

    # ------------------------------------------------------------- E3.6
    def test_e3_6_week_targets_copy_and_fill(self):
        Pt = self._pt()
        today = MONDAY + timedelta(days=2)
        data = Pt.get_week(self.share_emp, MONDAY + timedelta(days=4), today=today)
        week = data['week']
        self.assertEqual(week['monday'], MONDAY.isoformat(), 'any date → its Monday')
        self.assertEqual([d['target'] for d in week['days']], [8.0] * 5 + [0.0] * 2)
        self.assertEqual(week['target'], 40.0)
        self.assertEqual(week['prev'], (MONDAY - timedelta(days=7)).isoformat())
        self.assertEqual(week['next'], (MONDAY + timedelta(days=7)).isoformat())
        self.assertEqual([d['is_today'] for d in week['days']],
                         [False, False, True, False, False, False, False])
        self.assertTrue(data['empty_ever'])
        self.assertFalse(data['can_copy_last_week'])

        # last week: Mon 8 on Design, Tue 4 on Build
        last = MONDAY - timedelta(days=7)
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, last, '8')
        Pt.set_cell(self.share_emp, self.proj.id, self.task_b.id, last + timedelta(days=1), '4')
        # this week Monday already has 2 on Design: it must keep its value
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '2')
        data = Pt.get_week(self.share_emp, MONDAY)
        self.assertFalse(data['empty_ever'])
        self.assertTrue(data['can_copy_last_week'])
        self.assertIn('%s-%s' % (self.proj.id, self.task_b.id), data['rows_param'],
                      "last week's rows are proposed again")
        res = Pt.copy_last_week(self.share_emp, MONDAY)
        self.assertEqual(res['copied'], 1)
        data = Pt.get_week(self.share_emp, MONDAY)
        rows = {r['key']: r for r in data['rows']}
        design = rows['%s-%s' % (self.proj.id, self.task_a.id)]
        build = rows['%s-%s' % (self.proj.id, self.task_b.id)]
        self.assertEqual(design['cells'][0]['hours'], 2.0, 'a filled cell keeps its value')
        self.assertEqual(build['cells'][1]['hours'], 4.0)
        self.assertFalse(data['can_copy_last_week'])
        self.assertEqual(Pt.copy_last_week(self.share_emp, MONDAY)['copied'], 0)

        # fill the week with 8 h: only empty working days
        res = Pt.fill_row(self.share_emp, self.proj.id, self.task_b.id, MONDAY)
        self.assertEqual(res['filled'], 4, 'Mon, Wed, Thu, Fri (Tue had 4)')
        build = next(r for r in Pt.get_week(self.share_emp, MONDAY)['rows']
                     if r['key'] == '%s-%s' % (self.proj.id, self.task_b.id))
        self.assertEqual([c['hours'] for c in build['cells']],
                         [8.0, 4.0, 8.0, 8.0, 8.0, 0.0, 0.0])

        # an added row (no hours) is carried, not stored; the rows param
        # replaces the proposal
        row = Pt.add_row(self.share_emp, self.internal.id, 0, MONDAY + timedelta(days=7))
        self.assertEqual(row['total'], 0.0)
        self.assertFalse(row['has_lines'])
        nxt = Pt.get_week(self.share_emp, MONDAY + timedelta(days=7), rows=[])
        self.assertFalse([r for r in nxt['rows'] if not r['has_lines']])
        with self.assertRaises(UserError):
            Pt.add_row(self.share_emp, self.other_proj.id, 0, MONDAY)

    def test_e3_6b_save_week_moves_hours_between_rows(self):
        """The no-JS form: decreases are written first, so moving 20 h from
        one row to another on the same day never trips the 24 h limit."""
        Pt = self._pt()
        Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '20')
        res = Pt.save_week(self.share_emp, MONDAY, [
            {'project_id': self.proj.id, 'task_id': self.task_b.id,
             'date': MONDAY.isoformat(), 'hours': '20', 'note': None},
            {'project_id': self.proj.id, 'task_id': self.task_a.id,
             'date': MONDAY.isoformat(), 'hours': '', 'note': None},
            {'project_id': self.proj.id, 'task_id': self.task_a.id,
             'date': (MONDAY + timedelta(days=1)).isoformat(), 'hours': 'abc', 'note': None},
        ])
        self.assertEqual(res['saved'], 2)
        self.assertEqual(len(res['errors']), 1)
        self.assertIn('Type hours like', res['errors'][0]['error'])
        line = lines_of(self, self.share_emp)
        self.assertEqual(line.task_id, self.task_b)
        self.assertEqual(line.unit_amount, 20.0)

    # ------------------------------------------------------------- E3.7
    def test_e3_7_switch_off(self):
        Pt = self._pt()
        self.assertEqual(Pt.page_state(self.company), 'ok', 'unset = on (D3)')
        self.env['ir.config_parameter'].sudo().set_param(PARAM % self.company.id, '0')
        self.assertFalse(Pt.enabled(self.company))
        with self.assertRaises(UserError) as caught:
            Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '1')
        self.assertIn('switched off for your company', str(caught.exception))
        self.assertFalse(lines_of(self, self.share_emp))
        self.assertIsNone(Pt.week_summary(self.share_emp))
        self.assertEqual(self.env['pb.me.project.time'].with_user(self.share).session_state(), 'off')
        # the settings box reads and writes the same parameter
        settings = self.env['res.config.settings'].create({})
        self.assertFalse(settings.pb_me_project_time_enabled)
        settings.pb_me_project_time_enabled = True
        settings.set_values()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(
            PARAM % self.company.id), '1')
        settings.pb_me_project_time_enabled = False
        settings.set_values()
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param(
            PARAM % self.company.id), '0')

    def test_e3_7b_days_unit_is_a_quiet_block(self):
        day = self.env.ref('uom.product_uom_day', raise_if_not_found=False)
        if not day:
            self.skipTest('no day unit')
        self.company.timesheet_encode_uom_id = day
        Pt = self._pt()
        self.assertEqual(Pt.page_state(self.company), 'days')
        with self.assertRaises(UserError) as caught:
            Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '1')
        self.assertIn('counts project time in days', str(caught.exception))

    # ------------------------------------------------------------- E3.8
    def test_e3_8_home_card_and_needs_you(self):
        wednesday = MONDAY + timedelta(days=2)
        Home = self.env['pb.me.home'].with_user(self.share)
        with patch.object(PbMeProjectTime, '_today', lambda self, emp: wednesday):
            # quiet at zero: nothing in 8 weeks → no card, no row
            self.assertIsNone(self._pt().week_summary(self.share_emp))
            self.assertFalse([c for c in Home._pbme_extra_cards(self.share_emp)
                              if c['key'] == 'project_time'])
            needs, _docs = Home._pbme_needs(self.share_emp, wednesday, MONDAY,
                                            datetime(2026, 9, 16, 9, 0))
            self.assertFalse([n for n in needs if n['key'] == 'project_time_missing'])

            # Monday logged, Tuesday empty → "1 day"; Wed/Thu/Fri bring 24 h
            Pt = self._pt()
            Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id, MONDAY, '8')
            summary = Pt.week_summary(self.share_emp)
            self.assertEqual(summary['missing'], 1)
            needs, _docs = Home._pbme_needs(self.share_emp, wednesday, MONDAY,
                                            datetime(2026, 9, 16, 9, 0))
            row = next(n for n in needs if n['key'] == 'project_time_missing')
            self.assertEqual(row['n'], 1)
            self.assertEqual(row['label'], '1 day this week has no project time')
            self.assertEqual(row['tone'], 'amber')
            self.assertEqual(row['url'], '/my/project-time')
            for offset in (2, 3):
                Pt.set_cell(self.share_emp, self.proj.id, self.task_a.id,
                            MONDAY + timedelta(days=offset), '8')
            summary = Pt.week_summary(self.share_emp)
            self.assertEqual((summary['logged'], summary['target']), (24.0, 40.0))
            cards = [c for c in Home._pbme_extra_cards(self.share_emp)
                     if c['key'] == 'project_time']
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0]['template'], 'pb_me_project_time.pbme_card_project_time')
            html = self.env['ir.qweb']._render(cards[0]['template'], {'card': cards[0]})
            text = ' '.join(str(html).replace('<b class="pbme-num">', '').replace('</b>', '').split())
            self.assertIn('24 of 40 h', text)
            self.assertIn('Open the week', text)

    # ------------------------------------------------------------- E3.9
    def test_e3_9_ownership(self):
        # plain's line is invisible in share's week
        self.env['pb.me.project.time'].with_user(self.plain).set_cell(
            self.plain_emp, self.proj.id, self.task_a.id, MONDAY, '5')
        data = self._pt().get_week(self.share_emp, MONDAY)
        self.assertEqual(data['week']['logged'], 0.0)
        self.assertFalse([r for r in data['rows'] if r['has_lines']])
        # another person's employee record (or an id over RPC) is refused
        with self.assertRaises(AccessError):
            self._pt().set_cell(self.plain_emp, self.proj.id, self.task_a.id, MONDAY, '1')
        with self.assertRaises(AccessError):
            self._pt().get_week(self.plain_emp, MONDAY)
        with self.assertRaises(AccessError):
            self._pt().set_cell(self.plain_emp.id, self.proj.id, self.task_a.id, MONDAY, '1')
        with self.assertRaises(AccessError):
            self._pt().pickable_projects(self.other_emp)
        self.assertEqual(len(lines_of(self, self.plain_emp)), 1)
        self.assertFalse(lines_of(self, self.share_emp))
        # no portal ACL on timesheet lines was added: the employee login
        # still cannot read lines directly
        with self.assertRaises(AccessError):
            self.env['account.analytic.line'].with_user(self.share).search([])
