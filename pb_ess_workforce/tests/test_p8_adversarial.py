# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T2 — the adversarial suite. Forge an identity into every door and be refused.

The shape of every test here is the same: Alpha calls a method while trying to
be Beta, and the assertion is about BETA'S data, not about the error. That
matters. A method that raises AccessError is safe; a method that quietly answers
about the caller instead is ALSO safe, and it is the shape most of this module
takes, because none of these methods has an identity parameter to reject in the
first place. What must never happen is Beta's row coming back.

Where a test asserts an exception it is because the operation is a MUTATION and
silence would be a lie: an employee who is told "confirmed" about a shift that
was never theirs has been misinformed, which is worse than being refused.
"""

import inspect
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import EssWorkforceCase
from ..controllers import portal as portal_controller
from ..models import ess_workforce


@tagged('post_install', '-at_install')
class TestP8Adversarial(EssWorkforceCase):

    # ============================================================ the reads
    def test_a_forged_employee_id_in_the_kwargs_changes_nothing(self):
        """Every public facade method swallows unknown kwargs the way a JSON-RPC
        caller would supply them. Passing Beta's id must answer about Alpha."""
        day = self._future_day()
        self._shift(self.emp_a, day, state='published')
        beta_shift = self._shift(self.emp_b, day, state='published')
        ess = self._as(self.user_a)

        sched = ess.get_my_schedule()
        ids = [s['id'] for w in sched['weeks'] for d in w['days'] for s in d['shifts']]
        self.assertNotIn(beta_shift.id, ids)
        self.assertEqual(sched['employee']['id'], self.emp_a.id)

        self.assertEqual(ess.get_my_week()['employee']['id'], self.emp_a.id)
        self.assertEqual(ess.get_my_leave()['employee']['id'], self.emp_a.id)
        self.assertEqual(ess.get_my_overtime()['employee']['id'], self.emp_a.id)

    def test_no_facade_method_accepts_an_employee_parameter(self):
        """The structural version of the test above, and the one that survives a
        future contributor adding a fifth page: a signature that has nowhere to
        put an employee cannot be given one. Read from the SOURCE, because a
        behavioural test can only cover the methods that exist today (W79)."""
        offenders = []
        for name, fn in inspect.getmembers(ess_workforce.PbEssWorkforce,
                                           predicate=inspect.isfunction):
            if name.startswith('_'):
                continue
            for param in inspect.signature(fn).parameters:
                if 'employee' in param or param in ('emp', 'uid', 'user_id'):
                    offenders.append('%s(%s)' % (name, param))
        self.assertEqual(offenders, [],
                         'a public ESS method grew an identity parameter')

    def test_no_portal_route_accepts_an_employee_parameter(self):
        """Same gate on the HTTP surface. A route signature is the other place
        an identity could sneak in, and `**kw` does not count — the controller
        never reads one out of it (asserted by the source gate below)."""
        offenders = []
        for name, fn in inspect.getmembers(
                portal_controller.PbEssWorkforcePortal,
                predicate=inspect.isfunction):
            if not hasattr(fn, 'original_routing') and not name.startswith('portal_my_work'):
                continue
            for param in inspect.signature(fn).parameters:
                if 'employee' in param:
                    offenders.append('%s(%s)' % (name, param))
        self.assertEqual(offenders, [])
        src = inspect.getsource(portal_controller)
        for needle in ("'employee_id'", '"employee_id"', "get('employee')"):
            self.assertNotIn(needle, src,
                             'the portal controller reads an employee out of the request')

    def test_the_person_week_twin_is_private_and_the_public_door_still_gated(self):
        """W53's contract, both halves. `_person_week` must stay underscore-
        private (unreachable over call_kw, C18.32) and `get_person_week` must
        still refuse a non-officer — if the gate had moved to the twin, the ESS
        facade would have widened the officer surface instead of narrowing it."""
        hub = self.env['pb.time.hub']
        self.assertTrue(hasattr(hub, '_person_week'))
        with self.assertRaises(AccessError):
            hub.with_user(self.user_a).get_person_week(self.emp_b.id)

    def test_a_plain_employee_cannot_read_the_shift_table_directly(self):
        """The reason no ACL was widened (see security/pb_ess_workforce_security
        .xml). The portal reads sudo behind its own gate; the MODEL stays shut,
        so a hand-rolled call_kw is refused outright rather than record-ruled."""
        with self.assertRaises(AccessError):
            self.env['hr.shift.planning'].with_user(self.user_a).search([])
        with self.assertRaises(AccessError):
            self.env['hr.overtime.request'].with_user(self.user_a).search([])

    # ======================================================== the mutations
    def test_acking_another_employees_shift_is_refused(self):
        day = self._future_day()
        beta_shift = self._shift(self.emp_b, day, state='published')
        with self.assertRaises(Exception):
            self._as(self.user_a).ack_shift(beta_shift.id)
        self.assertEqual(beta_shift.ack_state, 'pending',
                         "Beta's shift was acknowledged by Alpha")

    def test_ack_week_only_touches_my_own_shifts(self):
        day = self._future_day()
        mine = self._shift(self.emp_a, day, state='published')
        theirs = self._shift(self.emp_b, day, state='published')
        res = self._as(self.user_a).ack_week(self.monday)
        self.assertEqual(res['acked'], 1)
        self.assertEqual(mine.ack_state, 'acked')
        self.assertEqual(theirs.ack_state, 'pending')

    def test_a_correction_filed_from_the_portal_is_forced_to_the_caller(self):
        """I-H3, the whole reason this method exists rather than a generic
        create: the request carries no employee, so there is nothing to forge."""
        yesterday = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        res = self._as(self.user_a).request_fix(
            yesterday.isoformat(), 'Forged?', '08:00')
        corr = self.env['hr.attendance.correction'].sudo().browse(res['id'])
        self.assertEqual(corr.employee_id, self.emp_a)

    def test_a_leave_applied_from_the_portal_is_forced_to_the_caller(self):
        lt = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', False)], limit=1)
        if not lt:
            self.skipTest('no allocation-free leave type on this database')
        day = self._future_day(7)
        try:
            res = self._as(self.user_a).apply_leave(
                lt.id, day.isoformat(), day.isoformat(), 'P8 fixture')
        except Exception:
            self.skipTest('core hr_holidays refused the fixture leave')
        leave = self.env['hr.leave'].sudo().browse(res['id'])
        self.assertEqual(leave.employee_id, self.emp_a)

    # ============================================== the acknowledgment write
    def test_the_ack_fields_cannot_be_written_without_the_sentinel(self):
        """C18.24. Not even sudo, and not even the admin — there is exactly one
        code path, and a bypass that "only" an admin could use is a bypass a
        future refactor will use by accident."""
        day = self._future_day()
        shift = self._shift(self.emp_a, day, state='published')
        for vals in ({'ack_state': 'acked'},
                     {'acked_at': fields.Datetime.now()},
                     {'ack_token': 'forged-token-value-0123456789'}):
            with self.assertRaises(AccessError):
                shift.sudo().write(dict(vals))
        # …and a context that merely CLAIMS the sentinel is still refused: the
        # guard tests object IDENTITY, which JSON cannot carry.
        with self.assertRaises(AccessError):
            shift.sudo().with_context(pb_ess_ack='pb_ess_ack').write(
                {'ack_state': 'acked'})
        with self.assertRaises(AccessError):
            shift.sudo().with_context(pb_ess_ack=True).write({'ack_state': 'acked'})
        self.assertEqual(shift.ack_state, 'pending')

    def test_the_ack_writes_exactly_two_fields(self):
        """The token page points a PUBLIC visitor at a sudo write. What keeps
        that safe is not the token alone, it is that the write cannot touch
        anything else on the record."""
        day = self._future_day()
        shift = self._shift(self.emp_a, day, state='published')
        before = {
            'state': shift.state, 'employee_id': shift.employee_id.id,
            'date': shift.date, 'start_datetime': shift.start_datetime,
            'end_datetime': shift.end_datetime, 'note': shift.note,
            'shift_template_id': shift.shift_template_id.id,
            'ack_token': shift.sudo().ack_token,
        }
        self.assertTrue(shift._ess_ack('test'))
        self.assertEqual(shift.ack_state, 'acked')
        self.assertTrue(shift.acked_at)
        for field, was in before.items():
            now = shift.sudo()[field]
            now = now.id if hasattr(now, 'id') and field.endswith('_id') else now
            self.assertEqual(now, was, 'the ack write touched %s' % field)
