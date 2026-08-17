# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P4 — T2: the lock is the phase's security core.

Every writer that can reach a closed week is tested LOCKED, UNLOCKED and
BYPASSED, because a guard that only works on the path somebody remembered is
not a guard. §2's measured fact is the reason this file is long: `hr.attendance`
has no state and no period guard anywhere in Odoo or in this codebase, and six
different writers reach it.

The bypass gets its own emphasis: `wf_lock_bypass` must work under `env.su` and
must do NOTHING for a normal session, or the whole model is a suggestion.
"""

from datetime import datetime, time, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import CloseCase


@tagged('post_install', '-at_install')
class TestWfLock(CloseCase):

    # ==================================================================
    #  the model itself
    # ==================================================================
    def test_a_row_is_a_lock_and_the_grain_is_company_day(self):
        self.assertFalse(self.Lock._is_locked(self.company, self.day))
        self._lock()
        self.assertTrue(self.Lock._is_locked(self.company, self.day))
        # the neighbouring day is untouched — a lock is a DAY, not a week
        self.assertFalse(self.Lock._is_locked(self.company, self.day2))

    def test_locking_a_locked_day_is_idempotent(self):
        a = self._lock()
        b = self._lock()
        self.assertEqual(a, b, 'a second lock must reuse the day"s row')
        self.assertEqual(
            self.Lock.sudo().search_count(
                [('company_id', '=', self.company.id), ('date', '=', self.day)]),
            1, 'unique(company_id, date) must hold')

    def test_the_unique_constraint_reached_postgres(self):
        """W33 — `models.Constraint`, not `_sql_constraints`. Odoo 19 logs one
        warning for the legacy form and then the constraint does not exist, and
        every model-level test still passes. So: read pg_indexes back."""
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'pb_wf_lock'")
        defs = [r[0] for r in self.env.cr.fetchall()]
        match = [d for d in defs
                 if 'UNIQUE' in d.upper() and 'company_id' in d and 'date' in d]
        self.assertTrue(
            match,
            'no UNIQUE(company_id, date) index in PostgreSQL; found %s' % defs)

    def test_reopening_requires_a_reason_and_posts_it(self):
        """§3.2 / W42: the reason is required BECAUSE it is recorded. It lands
        on the row AND in the chatter, and the chatter is why a reopen flips a
        state instead of deleting the row — a deleted thread takes its messages
        with it."""
        self._lock()
        rec = self.Lock.sudo().search(
            [('company_id', '=', self.company.id), ('date', '=', self.day)])
        with self.assertRaises(UserError):
            self.Lock.sudo().unlock_day(self.company.id, self.day, '   ')
        self.assertEqual(rec.state, 'locked', 'a refused reopen changes nothing')

        self._unlock(reason='payroll found a missing punch')
        self.assertEqual(rec.state, 'open')
        self.assertEqual(rec.reason, 'payroll found a missing punch')
        bodies = ' '.join(rec.message_ids.mapped('body'))
        self.assertIn('REOPENED', bodies)
        self.assertIn('payroll found a missing punch', bodies)
        # …and the LOCK note is still there: one row, the day's whole history
        self.assertIn('locked by', bodies)

    def test_a_reopened_day_no_longer_locks_anything(self):
        self._lock()
        self._unlock()
        self.assertFalse(self.Lock._is_locked(self.company, self.day))
        self._punch()                    # writes again, no raise

    def test_only_a_manager_tier_may_lock_or_reopen(self):
        officer = self._officer('p4_lock_officer')
        Lock = self.Lock.with_user(officer)
        with self.assertRaises(AccessError):
            Lock.lock_day(self.company.id, self.day, 'nope')
        self._lock()
        with self.assertRaises(AccessError):
            Lock.unlock_day(self.company.id, self.day, 'nope')
        # …and the raw ORM door is the same wall (the gate is on the MODEL, W31)
        with self.assertRaises(AccessError):
            Lock.create({'company_id': self.company.id, 'date': self.day2})

        manager = self._manager('p4_lock_manager')
        self.Lock.with_user(manager).unlock_day(
            self.company.id, self.day, 'the manager may')
        self.assertFalse(self.Lock._is_locked(self.company, self.day))

    def test_an_officer_may_still_READ_the_locks(self):
        """The Close board is officer-gated; only the locking is manager-tier."""
        self._lock()
        officer = self._officer('p4_lock_reader')
        rows = self.env['pb.wf.lock'].with_user(officer).search(
            [('date', '=', self.day)])
        self.assertTrue(rows, 'an officer must be able to see the lock state')

    def test_a_lock_is_scoped_to_its_company(self):
        other = self.env['res.company'].create({'name': 'P4 Other Co'})
        self._lock()
        self.assertTrue(self.Lock._is_locked(self.company, self.day))
        self.assertFalse(self.Lock._is_locked(other, self.day))

    # ==================================================================
    #  hr.attendance — the punch table
    # ==================================================================
    def test_punch_create_is_blocked_on_a_locked_day(self):
        self._lock()
        # the message must name the DAY that stopped it, not just say "locked"
        with self.assertRaises(ValidationError) as caught:
            self._punch()
        self.assertIn(self.day.strftime('%d %b'), str(caught.exception.args[0]))

    def test_punch_create_is_fine_on_an_unlocked_day(self):
        self._lock()
        att = self._punch(day=self.day2)
        self.assertTrue(att.id)

    def test_punch_write_is_blocked_from_BOTH_sides_of_a_move(self):
        """A write that moves a punch OFF a closed day is exactly as
        destructive as one that moves it ON — it removes the evidence."""
        att_open = self._punch(day=self.day2)
        att_locked = self._punch(day=self.day)
        self._lock()                       # day is now closed, day2 is not

        # onto the locked day
        with self.assertRaises(ValidationError):
            att_open.write({
                'check_in': datetime.combine(self.day, time(9, 0)),
                'check_out': datetime.combine(self.day, time(17, 0))})
        # off the locked day
        with self.assertRaises(ValidationError):
            att_locked.write({
                'check_in': datetime.combine(self.day2, time(9, 0)),
                'check_out': datetime.combine(self.day2, time(17, 0))})
        # and a plain edit inside the locked day
        with self.assertRaises(ValidationError):
            att_locked.write({
                'check_out': datetime.combine(self.day, time(18, 0))})

    def test_an_unwatched_field_write_is_not_blocked(self):
        """Only a write that touches the punch's PLACEMENT can violate a lock.
        Guarding everything would make every recompute in the system query the
        lock table — and would break stamping a source on an old row."""
        att = self._punch()
        self._lock()
        att.write({'pb_entry_source': 'import'})   # no raise
        self.assertEqual(att.pb_entry_source, 'import')

    def test_punch_unlink_is_blocked_on_a_locked_day(self):
        att = self._punch()
        self._lock()
        with self.assertRaises(ValidationError):
            att.unlink()
        self._unlock()
        att.unlink()                       # and works once reopened

    def test_sudo_alone_does_not_open_the_guard(self):
        """The correction workflow's single writer runs sudo'd. If sudo were
        enough, an approved correction would silently rewrite a closed week."""
        self._lock()
        with self.assertRaises(ValidationError):
            self.Att.sudo().create({
                'employee_id': self.emp.id,
                'check_in': datetime.combine(self.day, time(8, 0)),
                'check_out': datetime.combine(self.day, time(16, 0)),
                'pb_entry_source': 'correction'})

    # ==================================================================
    #  the bypass
    # ==================================================================
    def test_the_bypass_works_under_su(self):
        """pb_demo's regenerator rewrites a year of punches; a lock left behind
        by a demo of the Close ritual must not be able to defeat a regen."""
        self._lock()
        att = self.Att.sudo().with_context(wf_lock_bypass=True).create({
            'employee_id': self.emp.id,
            'check_in': datetime.combine(self.day, time(8, 0)),
            'check_out': datetime.combine(self.day, time(16, 0)),
            'pb_entry_source': 'grid'})
        self.assertTrue(att.id)
        att.with_context(wf_lock_bypass=True).unlink()

    def test_the_bypass_does_NOTHING_without_su(self):
        """A context key alone is forgeable over call_kw (C18.24). This is the
        assertion that makes `wf_lock_bypass` a rail rather than a suggestion."""
        officer = self._officer('p4_bypass_officer')
        self._lock()
        Att = self.Att.with_user(officer).with_context(wf_lock_bypass=True)
        with self.assertRaises(ValidationError):
            Att.create({
                'employee_id': self.emp.id,
                'check_in': datetime.combine(self.day, time(8, 0)),
                'check_out': datetime.combine(self.day, time(16, 0)),
                'pb_entry_source': 'grid'})
        # …and the admin user is NOT su either — `_is_admin()` opens plenty of
        # other doors in this codebase, deliberately not this one.
        self.assertFalse(self.Lock.with_user(officer)
                         .with_context(wf_lock_bypass=True)._bypass())

    # ==================================================================
    #  the Weekly-Entry grid
    # ==================================================================
    def test_the_grid_refuses_a_locked_cell_with_a_sentence(self):
        """The ORM guard alone would surface as the generic 'exc' code, which
        the grid renders as "Could not be saved." — a message that sends an
        officer to a log they cannot read."""
        officer = self._officer('p4_grid_officer')
        self._lock()
        res = self.Grid.with_user(officer).save_week_entries({'cells': [{
            'rowId': self.emp.id, 'dayISO': self.day.isoformat(),
            'measure': 'reg', 'value': 8.0, 'token': ''}]})
        row = res['results'][0]
        self.assertFalse(row['ok'])
        self.assertIn('closed for payroll', row['error'])
        self.assertNotEqual(row['error'], 'exc',
                            'the cell must explain itself, not report an '
                            'internal exception code')
        self.assertFalse(self.Att.sudo().search_count([
            ('employee_id', '=', self.emp.id),
            ('check_in', '>=', datetime.combine(self.day, time.min)),
            ('check_in', '<=', datetime.combine(self.day, time.max))]),
            'nothing may be written on a locked day')

    def test_the_grid_still_saves_on_an_open_day(self):
        officer = self._officer('p4_grid_officer_ok')
        self._lock()                                  # day locked, day2 open
        res = self.Grid.with_user(officer).save_week_entries({'cells': [{
            'rowId': self.emp.id, 'dayISO': self.day2.isoformat(),
            'measure': 'reg', 'value': 8.0, 'token': ''}]})
        self.assertTrue(res['results'][0]['ok'], res['results'][0])

    # ==================================================================
    #  the bulk import
    # ==================================================================
    def test_import_rows_on_a_locked_day_are_skipped_with_a_reason(self):
        """§3.2: flagged as skipped, not written — and flagged in the DRY RUN
        too, or the verdict table would be lying about what Import will do."""
        import base64
        self._lock()
        csv = ('Employee,Date,Check In,Check Out\n'
               '%s,%s,08:00,16:00\n'
               '%s,%s,08:00,16:00\n' % (
                   self.emp.barcode, self.day.isoformat(),
                   self.emp.barcode, self.day2.isoformat()))
        blob = base64.b64encode(csv.encode()).decode()
        mapping = {'employee': 'Employee', 'date': 'Date',
                   'check_in': 'Check In', 'check_out': 'Check Out'}
        Wiz = self.env['pb.attendance.import.wizard'].sudo()

        verdicts = Wiz.validate(blob, 'p4.csv', mapping)
        rows = {r['date']: r for r in verdicts['rows']}
        self.assertFalse(rows[self.day.isoformat()]['ok'])
        self.assertTrue(any('closed for payroll' in e
                            for e in rows[self.day.isoformat()]['errors']))
        self.assertTrue(rows[self.day2.isoformat()]['ok'])

        res = Wiz.commit(blob, 'p4.csv', mapping)
        self.assertEqual(res['created'], 1, 'only the open day may land')
        self.assertEqual(res['skipped'], 1)
        self.assertFalse(self.Att.sudo().search_count([
            ('employee_id', '=', self.emp.id),
            ('check_in', '>=', datetime.combine(self.day, time.min)),
            ('check_in', '<=', datetime.combine(self.day, time.max))]))

    # ==================================================================
    #  corrections
    # ==================================================================
    def test_a_correction_cannot_be_SUBMITTED_for_a_locked_day(self):
        """The friendly refusal, at the point the officer can still act on it."""
        self._lock()
        corr = self.Corr.sudo().create({
            'employee_id': self.emp.id, 'date': self.day,
            'correction_type': 'create',
            'new_check_in': datetime.combine(self.day, time(8, 0)),
            'new_check_out': datetime.combine(self.day, time(16, 0)),
            'reason': 'forgot to punch', 'company_id': self.company.id})
        with self.assertRaises(ValidationError):
            corr.action_submit()
        self.assertEqual(corr.state, 'draft', 'nothing may have advanced')

    def test_a_correction_locked_AFTER_submit_lands_refused_not_raised(self):
        """§3.2's exact requirement, and the young-worker precedent: the model
        already runs `_apply` in a savepoint and turns a ValidationError into
        `refused` + `apply_error`. The lock must ride that path, because raising
        mid-apply would abort the approver's whole batch."""
        corr = self.Corr.sudo().create({
            'employee_id': self.emp.id, 'date': self.day,
            'correction_type': 'create',
            'new_check_in': datetime.combine(self.day, time(8, 0)),
            'new_check_out': datetime.combine(self.day, time(16, 0)),
            'reason': 'forgot to punch', 'company_id': self.company.id})
        corr.action_submit()
        self.assertEqual(corr.state, 'submitted')

        self._lock()                       # closed between submit and approve
        corr.action_approve()              # must NOT raise

        self.assertEqual(corr.state, 'refused')
        self.assertTrue(corr.apply_error)
        self.assertIn('closed', corr.apply_error)
        self.assertFalse(self.Att.sudo().search_count([
            ('employee_id', '=', self.emp.id),
            ('check_in', '>=', datetime.combine(self.day, time.min)),
            ('check_in', '<=', datetime.combine(self.day, time.max))]),
            'a refused correction must not have applied anything')

    def test_a_correction_on_an_open_day_still_applies(self):
        self._lock()                       # day locked, day2 open
        corr = self.Corr.sudo().create({
            'employee_id': self.emp.id, 'date': self.day2,
            'correction_type': 'create',
            'new_check_in': datetime.combine(self.day2, time(8, 0)),
            'new_check_out': datetime.combine(self.day2, time(16, 0)),
            'reason': 'forgot to punch', 'company_id': self.company.id})
        corr.action_submit()
        corr.action_approve()
        self.assertEqual(corr.state, 'approved')
        self.assertFalse(corr.apply_error)

    # ==================================================================
    #  overtime — the one MONEY guard in P4
    # ==================================================================
    def _ot(self, day=None, hours=2.0):
        return self.OT.sudo().create({
            'employee_id': self.emp.id, 'date': day or self.day,
            'overtime_type': 'weekday', 'planned_hours': hours,
            'actual_hours': hours, 'reason': 'P4 test',
            'company_id': self.company.id})

    def test_overtime_submit_approve_refuse_are_all_blocked_when_locked(self):
        """`approved_hours` feeds the payroll formula inputs (the OT bridge,
        hr_payslip.py:27). A closed week that can still grow approved overtime
        is not closed."""
        draft = self._ot()
        pending = self._ot(day=self.day2)
        pending.action_submit()
        pending.sudo().write({'date': self.day})   # now it sits on the locked day
        self._lock()

        with self.assertRaises(ValidationError):
            draft.action_submit()
        self.assertEqual(draft.state, 'draft')

        with self.assertRaises(ValidationError):
            pending.action_approve()
        self.assertEqual(pending.state, 'submitted')

        with self.assertRaises(ValidationError):
            pending.action_refuse()
        self.assertEqual(pending.state, 'submitted')

    def test_overtime_on_an_open_day_is_untouched(self):
        self._lock()                       # day locked, day2 open
        req = self._ot(day=self.day2)
        req.action_submit()
        self.assertEqual(req.state, 'submitted')
        req.action_approve()
        self.assertEqual(req.state, 'approved')

    def test_a_no_op_transition_is_not_refused(self):
        """The model itself filters on state; refusing something that would not
        have transitioned anyway would be a lie about what was blocked."""
        req = self._ot(day=self.day2)
        req.action_submit()
        req.action_approve()
        self._lock(day=self.day2)
        req.action_submit()                # already approved → no-op, no raise
        self.assertEqual(req.state, 'approved')

    # ==================================================================
    #  the driver PWA / raw ORM path
    # ==================================================================
    def test_a_raw_orm_punch_hits_the_same_wall(self):
        """There is no seventh door: the guard is on the ORM, so the live PWA
        punch, a call_kw and a shell one-liner all meet it."""
        officer = self._officer('p4_raw_officer')
        self._lock()
        with self.assertRaises(ValidationError):
            self.Att.with_user(officer).create({
                'employee_id': self.emp.id,
                'check_in': datetime.combine(self.day, time(8, 0))})

    # ==================================================================
    #  residue (T16)
    # ==================================================================
    def test_the_suite_leaves_no_locks_behind(self):
        """Belt and braces on the transaction rollback: every lock this suite
        creates is inside the test transaction, so a `search_count` at the end
        of a case must only ever see this case's own rows."""
        before = self.Lock.sudo().search_count([('date', '=', self.day)])
        self._lock()
        self.assertEqual(
            self.Lock.sudo().search_count([('date', '=', self.day)]), before + 1)
