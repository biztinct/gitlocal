# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T3 — the acknowledgment lifecycle, and the token's five refusals.

The token half of this file is adversarial (T2) and reads like it: every wrong
way to hold the link is tried, and after each one the shift is re-read to prove
nothing moved. The lifecycle half is the happy path plus the two transitions
that have to invalidate it.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import EssWorkforceCase


@tagged('post_install', '-at_install')
class TestP8Ack(EssWorkforceCase):

    def _published(self, offset=1):
        return self._shift(self.emp_a, self._future_day(offset), state='published')

    def _token(self, shift):
        return shift.sudo().ack_token

    # ======================================================= mint / lifecycle
    def test_publishing_mints_a_pending_token(self):
        shift = self._shift(self.emp_a, self._future_day())
        self.assertEqual(shift.ack_state, 'pending')
        self.assertFalse(self._token(shift), 'a draft shift is not a promise yet')
        shift.action_publish()
        self.assertEqual(shift.ack_state, 'pending')
        self.assertTrue(self._token(shift))
        self.assertGreaterEqual(len(self._token(shift)), 16)

    def test_two_shifts_never_share_a_token(self):
        a = self._published(1)
        b = self._published(2)
        self.assertNotEqual(self._token(a), self._token(b))

    def test_republishing_an_already_published_shift_does_not_remint(self):
        """`action_publish` filters on draft, and the mint follows the same
        set — so calling it twice is not a way to silently revoke a link an
        employee already has in their inbox."""
        shift = self._published()
        first = self._token(shift)
        shift.action_publish()
        self.assertEqual(self._token(shift), first)

    def test_the_portal_ack_and_the_token_ack_land_in_the_same_state(self):
        by_portal = self._published(1)
        by_link = self._published(2)
        self._as(self.user_a).ack_shift(by_portal.id)
        self.env['hr.shift.planning']._ess_ack_by_token(self._token(by_link))
        for shift in (by_portal, by_link):
            self.assertEqual(shift.ack_state, 'acked')
            self.assertTrue(shift.acked_at)

    def test_cancelling_a_shift_invalidates_the_mailed_link(self):
        shift = self._published()
        old = self._token(shift)
        shift.action_cancel()
        self.assertNotEqual(self._token(shift), old, 'the old link still resolves')
        _found, status = self.env['hr.shift.planning']._ess_shift_for_token(old)
        self.assertEqual(status, 'invalid')

    def test_pulling_a_shift_back_to_draft_invalidates_it_too(self):
        shift = self._published()
        shift.action_cancel()
        shift.action_reset_draft()
        self.assertEqual(shift.ack_state, 'pending')
        self.assertFalse(shift.acked_at)

    def test_an_acknowledged_shift_that_is_republished_starts_over(self):
        """A roster that is withdrawn and re-issued is a NEW promise. Carrying
        the old acknowledgment forward would tell the manager somebody had
        confirmed a shift they have never seen."""
        shift = self._published()
        shift._ess_ack('test')
        self.assertEqual(shift.ack_state, 'acked')
        shift.action_cancel()
        shift.action_reset_draft()
        shift.action_publish()
        self.assertEqual(shift.ack_state, 'pending')

    # ============================================================ the token
    def test_an_unknown_token_resolves_to_nothing(self):
        Shift = self.env['hr.shift.planning']
        for bad in ('', '   ', 'short', 'x' * 40, None, 'a' * 24):
            found, status = Shift._ess_shift_for_token(bad)
            self.assertFalse(found, 'token %r matched a shift' % bad)
            self.assertEqual(status, 'invalid')

    def test_an_empty_token_never_matches_a_tokenless_shift(self):
        """The trap this refusal exists for: a draft shift has ack_token False,
        and an unguarded `search([('ack_token','=','')])` on a database where one
        row holds '' instead of False would hand a stranger a real shift."""
        draft = self._shift(self.emp_a, self._future_day())
        self.assertFalse(self._token(draft))
        found, status = self.env['hr.shift.planning']._ess_shift_for_token('')
        self.assertFalse(found)
        self.assertEqual(status, 'invalid')

    def test_a_reused_token_is_refused_and_writes_nothing(self):
        shift = self._published()
        token = self._token(shift)
        _s, status = self.env['hr.shift.planning']._ess_ack_by_token(token)
        self.assertEqual(status, 'acked')
        acked_at = shift.acked_at
        _s, status = self.env['hr.shift.planning']._ess_ack_by_token(token)
        self.assertEqual(status, 'used')
        self.assertEqual(shift.acked_at, acked_at,
                         'a replay moved the acknowledgment timestamp')

    def test_a_token_for_a_shift_that_has_started_is_refused(self):
        past = fields.Date.context_today(self.env['hr.employee']) - timedelta(days=1)
        shift = self._shift(self.emp_a, past, state='published')
        token = self._token(shift)
        _s, status = self.env['hr.shift.planning']._ess_ack_by_token(token)
        self.assertEqual(status, 'expired')
        self.assertEqual(shift.ack_state, 'pending')

    def test_a_token_for_a_cancelled_shift_reports_stale_not_ok(self):
        """The token is re-minted on cancel, so the OLD link is invalid; the NEW
        one exists but points at a withdrawn shift, and must not confirm it."""
        shift = self._published()
        shift.action_cancel()
        _s, status = self.env['hr.shift.planning']._ess_shift_for_token(
            self._token(shift))
        self.assertEqual(status, 'stale')

    def test_the_token_field_is_system_restricted(self):
        """A credential that shows up in an officer's read() is a credential
        anybody with the roster can use. The ORM strips a `groups=` field from
        every non-member's read, which is the mechanism — so the assertion is on
        the mechanism, not on one caller that happens to be refused today."""
        field = self.env['hr.shift.planning']._fields['ack_token']
        self.assertEqual(field.groups, 'base.group_system')
        # …and the sudo path still works, which is what the whole flow depends on
        self.assertTrue(self._token(self._published()))

    def test_the_token_ack_still_cannot_touch_a_third_field(self):
        shift = self._published()
        with self.assertRaises(AccessError):
            shift.sudo().write({'ack_state': 'acked', 'state': 'completed'})

    # ========================================================= notification
    def test_publish_reports_three_counts_and_never_mails_by_default(self):
        """C18.48: the default is silence. `mail_enabled: False` is in the
        payload so the toast cannot claim an email that was not sent."""
        Mail = self.env['mail.mail'].sudo()
        self.emp_a.write({'work_email': 'p8.alpha@example.invalid'})
        # emp_b has a login but no work email; a third has neither
        emp_c = self.env['hr.employee'].create({
            'name': 'ESS Gamma', 'company_id': self.company.id, 'tz': self.tz})
        day = self._future_day()
        for emp in (self.emp_a, self.emp_b, emp_c):
            self._shift(emp, day)

        before = Mail.search_count([])
        # Scoped to the FIXTURE employees, not to the day. This suite runs
        # against the live demo world, where "every shift on this date" is
        # several hundred other people's — the first live run came back
        # `portal: 4` because two demo employees happened to be rostered too.
        # A test whose population is whatever else is in the database is a test
        # that reports a different number every week.
        res = self.env['hr.shift.planning'].sudo().search([
            ('date', '=', day),
            ('employee_id', 'in', (self.emp_a | self.emp_b | emp_c).ids),
        ])._ess_notify_published()
        after = Mail.search_count([])

        self.assertFalse(res['mail_enabled'])
        self.assertEqual(res['emailed'], 0)
        self.assertEqual(after, before, 'a mail was queued with mail off')
        self.assertEqual(res['portal'], 2)
        self.assertEqual(res['no_channel'], 1)
        self.assertEqual(res['notified'], 2)

    def test_with_mail_on_one_message_per_shift_carries_the_token_link(self):
        Mail = self.env['mail.mail'].sudo()
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_ess_workforce.publish_mail', '1')
        self.addCleanup(self.env['ir.config_parameter'].sudo().set_param,
                        'pb_ess_workforce.publish_mail', '0')
        self.emp_a.write({'work_email': 'p8.alpha@example.invalid'})
        shift = self._published()
        before = Mail.search_count([])
        res = shift._ess_notify_published()
        self.assertTrue(res['mail_enabled'])
        self.assertEqual(res['emailed'], 1)
        self.assertEqual(Mail.search_count([]), before + 1)
        mail = Mail.search([], order='id desc', limit=1)
        self.assertIn('/work/ack/%s' % self._token(shift), mail.body_html)
        self.assertEqual(mail.email_to, 'p8.alpha@example.invalid')
        self.assertEqual(mail.state, 'outgoing',
                         'the message must be QUEUED, never sent from a publish')
        mail.unlink()

    def test_a_mail_failure_never_costs_the_publish(self):
        """Best-effort by contract (§3.2). The publish is the truth; the email
        is the courtesy, and the courtesy cannot hold the truth hostage.

        The failure is INJECTED at the mail layer rather than simulated, so what
        is proven is that a real `mail.mail.create` explosion is contained —
        which is the thing an SMTP outage actually does."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_ess_workforce.publish_mail', '1')
        self.addCleanup(self.env['ir.config_parameter'].sudo().set_param,
                        'pb_ess_workforce.publish_mail', '0')
        self.emp_a.write({'work_email': 'p8.alpha@example.invalid'})
        shift = self._published()

        MailMail = type(self.env['mail.mail'])
        original = MailMail.create

        def boom(self, vals_list):
            raise RuntimeError('SMTP is on fire')

        MailMail.create = boom
        try:
            res = shift._ess_notify_published()
        finally:
            MailMail.create = original

        self.assertEqual(res['emailed'], 0)
        self.assertEqual(shift.state, 'published',
                         'a mail failure rolled the publish back')
        self.assertEqual(shift.ack_state, 'pending')
        self.assertTrue(self._token(shift), 'the token survived the mail failure')

    def test_publish_shifts_keeps_its_int_contract(self):
        """pb_schedule's docstring freezes the seven base-facade shapes. The
        counts live on a NEW method beside it, exactly as get_schedule_data
        lives beside get_grid_data."""
        day = self._future_day()
        self._shift(self.emp_a, day)
        n = self.env['hr.shift.planning.grid'].with_user(
            self.env.ref('base.user_admin')).publish_shifts(
                self.monday.isoformat(), num_days=14)
        self.assertIsInstance(n, int)

    def test_publish_shifts_notified_returns_the_counts(self):
        day = self._future_day()
        self._shift(self.emp_a, day)
        res = self.env['hr.shift.planning.grid'].with_user(
            self.env.ref('base.user_admin')).publish_shifts_notified(
                self.monday.isoformat(), num_days=14)
        for key in ('published', 'notified', 'portal', 'emailed',
                    'no_channel', 'mail_enabled', 'capped'):
            self.assertIn(key, res)
        self.assertGreaterEqual(res['published'], 1)

    # ========================================================== the backfill
    def test_the_backfill_catches_shifts_published_before_the_module_existed(self):
        """The gap psql found on the live world, pinned.

        `action_publish` only sees the future. A module installed onto a tenant
        whose roster was published last week arrives with the token channel
        dead for every existing shift — and nothing errors, which is why the
        live row count was the only thing that could say so.
        """
        shift = self._published()
        # simulate the pre-module world: a published shift with no token
        shift._ess_ack_env().write({'ack_token': False})
        self.assertFalse(self._token(shift))

        n = self.env['hr.shift.planning']._ess_backfill_tokens()
        self.assertGreaterEqual(n, 1)
        self.assertTrue(self._token(shift))
        _s, status = self.env['hr.shift.planning']._ess_shift_for_token(
            self._token(shift))
        self.assertEqual(status, 'ok')

    def test_the_backfill_is_idempotent_and_never_remints(self):
        shift = self._published()
        token = self._token(shift)
        self.env['hr.shift.planning']._ess_backfill_tokens()
        self.assertEqual(self._token(shift), token,
                         'the backfill revoked a link somebody already has')

    def test_the_backfill_mints_nothing_for_a_shift_nobody_can_confirm(self):
        """A credential nobody needs is a credential somebody can leak."""
        from datetime import timedelta as _td
        past = fields.Date.context_today(self.env['hr.employee']) - _td(days=3)
        old = self._shift(self.emp_a, past, state='published')
        old._ess_ack_env().write({'ack_token': False})
        draft = self._shift(self.emp_a, self._future_day(5))
        self.env['hr.shift.planning']._ess_backfill_tokens()
        self.assertFalse(self._token(old), 'a started shift was given a link')
        self.assertFalse(self._token(draft), 'a draft shift was given a link')
