# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 — T5: the `is_clean` truth table.

"Clean" is a promise made to somebody who is about to approve twenty things
without reading them, so every condition gets its own case AND its own negative
case. The verdict is conservative by construction: three conditions, all of
which must hold, and any read the server could not make resolves to NOT clean.

The batch itself is exercised through `pb.team.act` — the same door the dock
uses, as the real user — so what is proved here is what the button does.
"""

from datetime import timedelta

from unittest.mock import patch

from odoo.tests import tagged

from .common import CloseCase


@tagged('post_install', '-at_install')
class TestCleanBatch(CloseCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # pb_team and pb_close do not depend on each other in either direction:
        # the lock check inside `_ot_clean_map` is a soft `in self.env` hook, so
        # each module is installable alone. This suite is about the SEAM, so it
        # is the one thing here that has to say "not applicable" rather than
        # fail when only one half is present.
        if 'pb.team' not in cls.env:
            cls.skipTest(cls, 'pb_team is not installed on this database')
        cls.Team = cls.env['pb.team']
        # A manager who has a REPORT, so the team-scoped queue is non-empty and
        # `act`'s team-scope check has something true to find.
        cls.boss = cls._mk_user('p4_batch_boss', [
            'hr.group_hr_user', 'hr.group_hr_manager',
            'hr_attendance.group_hr_attendance_officer',
            'hr_attendance.group_hr_attendance_manager'])
        cls.boss_emp = cls.env['hr.employee'].create({
            'name': 'P4 Boss', 'company_id': cls.company.id, 'tz': 'UTC',
            'user_id': cls.boss.id})
        cls.emp.sudo().write({'parent_id': cls.boss_emp.id})
        cls.emp2.sudo().write({'parent_id': cls.boss_emp.id})

    # ------------------------------------------------------------- helpers
    def _ot(self, emp=None, day=None, hours=2.0, submit=True):
        req = self.OT.sudo().create({
            'employee_id': (emp or self.emp).id,
            'date': day or self.day,
            'overtime_type': 'weekday',
            'planned_hours': hours, 'actual_hours': hours,
            'reason': 'P4 clean batch', 'company_id': self.company.id})
        if submit:
            req.action_submit()
        return req

    def _verdict(self, recs):
        return self.Team.sudo()._ot_clean_map(recs)

    # ==================================================================
    #  the truth table
    # ==================================================================
    def test_a_grid_entered_request_under_the_ceilings_is_clean(self):
        req = self._ot()
        self.assertTrue(self._verdict(req).get(req.id))

    def test_a_request_edited_after_entry_is_NOT_clean(self):
        """The grid writes planned_hours and actual_hours to the same figure. A
        row where they have since diverged was touched by a human, and a human
        edit is exactly what a batch must not sweep up."""
        req = self._ot()
        req.sudo().write({'actual_hours': 3.5})
        self.assertFalse(self._verdict(req).get(req.id))

    def test_a_zero_hour_request_is_NOT_clean(self):
        req = self._ot(hours=0.0)
        self.assertFalse(self._verdict(req).get(req.id))

    def test_a_request_on_a_LOCKED_day_is_NOT_clean(self):
        """Approving OT onto a closed week is refused by pb_close anyway —
        offering it in a batch would produce a row that fails halfway through
        and stops the rest (W29's door that can only error)."""
        req = self._ot()
        self.assertTrue(self._verdict(req).get(req.id))
        self._lock(self.day)
        self.assertFalse(self._verdict(req).get(req.id))
        self._unlock(self.day)
        self.assertTrue(self._verdict(req).get(req.id))

    def test_a_request_over_the_MONTHLY_ceiling_is_NOT_clean(self):
        req = self._ot(hours=2.0)
        real = self.env['hr.attendance.weekentry'].sudo()._ot_ceilings(
            self.emp.ids, self.day)
        squeezed = {self.emp.id: {**real[self.emp.id],
                                  'mtd': 999.0, 'cap_month': 40.0}}
        with patch.object(
                type(self.env['hr.attendance.weekentry']),
                '_ot_ceilings', return_value=squeezed):
            self.assertFalse(self._verdict(req).get(req.id))

    def test_a_request_over_the_ANNUAL_ceiling_is_NOT_clean(self):
        req = self._ot(hours=2.0)
        real = self.env['hr.attendance.weekentry'].sudo()._ot_ceilings(
            self.emp.ids, self.day)
        squeezed = {self.emp.id: {**real[self.emp.id],
                                  'ytd': 9999.0, 'cap_year': 300.0}}
        with patch.object(
                type(self.env['hr.attendance.weekentry']),
                '_ot_ceilings', return_value=squeezed):
            self.assertFalse(self._verdict(req).get(req.id))

    def test_an_unreadable_ceiling_makes_NOTHING_clean(self):
        """Fail-closed. A batch button is a promise that these were checked; a
        promise made on data we could not read is worse than no button."""
        req = self._ot()
        with patch.object(
                type(self.env['hr.attendance.weekentry']), '_ot_ceilings',
                side_effect=RuntimeError('ceiling read exploded')):
            self.assertEqual(self._verdict(req), {})

    # ==================================================================
    #  the payload
    # ==================================================================
    def test_every_queue_source_declares_is_clean(self):
        """A missing key is not a False, and JSON will not say which one you
        got (W45). Only OVERTIME can ever be true in v1."""
        self._ot()
        data = self.Team.with_user(self.boss).get_team_data(
            recursive=True, queues_only=True)
        items = data['queues']['items']
        self.assertTrue(items, 'the boss must see their report"s request')
        for it in items:
            self.assertIn('is_clean', it,
                          '%s must declare is_clean' % it['model'])
            if it['model'] != 'hr.overtime.request':
                self.assertFalse(it['is_clean'],
                                 'only overtime participates in v1')

    def test_the_payload_marks_the_clean_request_clean(self):
        req = self._ot()
        data = self.Team.with_user(self.boss).get_team_data(
            recursive=True, queues_only=True)
        row = [i for i in data['queues']['items']
               if i['model'] == 'hr.overtime.request' and i['res_id'] == req.id]
        self.assertTrue(row, 'the request must be in the queue')
        self.assertTrue(row[0]['is_clean'])

    # ==================================================================
    #  the batch
    # ==================================================================
    def test_the_batch_approves_exactly_the_clean_set_as_the_real_user(self):
        """`act` is the door the dock uses: whitelisted, real-user, through the
        model's own gated method. The dirty row must survive untouched."""
        clean_a = self._ot(emp=self.emp, day=self.day)
        clean_b = self._ot(emp=self.emp2, day=self.day2)
        dirty = self._ot(emp=self.emp, day=self.day2)
        dirty.sudo().write({'actual_hours': 4.25})     # edited after entry

        verdict = self._verdict(clean_a | clean_b | dirty)
        self.assertTrue(verdict.get(clean_a.id))
        self.assertTrue(verdict.get(clean_b.id))
        self.assertFalse(verdict.get(dirty.id))

        for req in (clean_a, clean_b):
            res = self.Team.with_user(self.boss).act(
                'hr.overtime.request', req.id, 'approve')
            self.assertTrue(res['ok'], res)

        self.assertEqual(clean_a.sudo().state, 'approved')
        self.assertEqual(clean_b.sudo().state, 'approved')
        self.assertEqual(dirty.sudo().state, 'submitted',
                         'a batch must never touch what it did not certify')

    def test_the_batch_stops_at_a_locked_day_instead_of_half_approving(self):
        """The lock guard raises ValidationError, `act` catches it and returns
        {ok: False}, and the dock's loop breaks on the first one. Proving the
        server half here is what makes that loop meaningful."""
        req = self._ot(day=self.day)
        self._lock(self.day)
        res = self.Team.with_user(self.boss).act(
            'hr.overtime.request', req.id, 'approve')
        self.assertFalse(res['ok'])
        self.assertIn('closed', res['error'])
        self.assertEqual(req.sudo().state, 'submitted')

    def test_no_pre_existing_request_is_disturbed(self):
        """T16, asserted rather than promised: the verdict is a pure READ."""
        before = self.OT.sudo().search_count([('state', '=', 'submitted')])
        req = self._ot()
        self._verdict(req)
        self.Team.with_user(self.boss).get_team_data(
            recursive=True, queues_only=True)
        after = self.OT.sudo().search_count([('state', '=', 'submitted')])
        self.assertEqual(after, before + 1,
                         'reading the queue must not change it')
