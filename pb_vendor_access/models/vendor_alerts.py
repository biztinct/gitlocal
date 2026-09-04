# -*- coding: utf-8 -*-
"""`pb.vendor.alerts` — the nightly job that says an agreement is running out.

The vault's `_cron_expiry_check` is the canon and this is that shape: a horizon
from a config parameter, a search for an already-open activity BEFORE creating
one, a try/except per record, and a count in the log that is the number of
things actually done rather than the number of things looked at.

THREE THINGS IT DOES, AND THEY ARE THREE SEPARATE QUESTIONS.

  1. **A renewal is due.** The renewal date has arrived (or the end date is
     inside the horizon) and the agreement is still running. The person who
     looks after the vendor gets an activity and a mail.
  2. **It ran out and nobody renewed it.** The end date has passed, nothing
     replaced it, and the agreement is still active. That is an escalation and
     it goes to the HR team as well as the owner.
  3. **Nothing.** For everything else, and that is most of the register.

WHY "RUN IT NOW" RUNS ALL THREE. R53: a button that does four fifths of what the
night does produces a number nobody can compare with the morning's log, and the
piece it skips is usually the only one reachable for testing.

R47 — a mail queued with `force_send=False` on this database goes out within the
second, so every test address in this module is `@example.com` and the burst cap
is a real limit rather than a formality.
"""

import logging

from odoo import _, api, fields, models

from .vendor_common import (AGREEMENT_ROW_CAP, counted, flag, param_int)

_logger = logging.getLogger(__name__)


class PbVendorAlerts(models.AbstractModel):
    _name = 'pb.vendor.alerts'
    _description = 'Vendor agreement reminders'

    # ------------------------------------------------------------------ entry
    @api.model
    def cron_alerts(self):
        """The nightly job. Everything it does, it does once."""
        return self.run(limit=None)

    @api.model
    def run(self, limit=AGREEMENT_ROW_CAP):
        """One pass. `limit=None` means every row — R76: the cap that is right
        for a screen is a bug in a job, so the job passes None and the button
        on the board passes the default."""
        today = fields.Date.context_today(self)
        horizon = param_int(self.env,
                            'pb_vendor_access.renewal_horizon_days', 45)
        burst = param_int(self.env, 'pb_vendor_access.mail_burst', 80)
        mails_on = flag(self.env, 'pb_vendor_access.alerts_enabled')

        due = self._due_for_renewal(today, horizon, limit)
        gone = self._overdue(today, limit)

        counters = {'reminded': 0, 'escalated': 0, 'mailed': 0, 'skipped': 0,
                    'would_mail': 0}
        for agreement in due:
            self._one(agreement, 'renewal', today, counters, burst, mails_on)
        for agreement in gone:
            self._one(agreement, 'expired', today, counters, burst, mails_on)

        _logger.info(
            'pb.vendor.alerts: %s due, %s overdue, %s reminders raised, '
            '%s escalations, %s mails sent, %s mails held (switch off), '
            '%s already handled',
            len(due), len(gone), counters['reminded'], counters['escalated'],
            counters['mailed'], counters['would_mail'], counters['skipped'])
        counters['due'] = len(due)
        counters['overdue'] = len(gone)
        counters['message'] = self._message(counters, mails_on)
        return counters

    # ----------------------------------------------------------- who is in it
    @api.model
    def _due_for_renewal(self, today, horizon, limit):
        """Still running, and the conversation should have started.

        The renewal date OR the horizon, whichever arrives first: somebody who
        pushed the renewal date out past the horizon still gets told, because
        the end date is the fact and the renewal date is only a plan.
        """
        Agreement = self.env['pb.vendor.agreement'].sudo()
        horizon_date = fields.Date.add(today, days=horizon)
        return Agreement.search([
            ('active', '=', True),
            ('is_renewed', '=', False),
            ('date_end', '!=', False),
            ('date_end', '>=', today),
            '|', ('renewal_date', '<=', today),
            ('date_end', '<=', horizon_date),
        ], limit=limit or None, order='date_end')

    @api.model
    def _overdue(self, today, limit):
        """It ended, nothing replaced it, and it is still on the register."""
        Agreement = self.env['pb.vendor.agreement'].sudo()
        return Agreement.search([
            ('active', '=', True),
            ('is_renewed', '=', False),
            ('date_end', '!=', False),
            ('date_end', '<', today),
        ], limit=limit or None, order='date_end desc')

    # ---------------------------------------------------------------- one row
    def _one(self, agreement, kind, today, counters, burst, mails_on):
        """One agreement, with its OWN try/except.

        Every independent probe gets its own — a shared block turns the first
        bad row into a job that stops, and the log then says nothing about the
        nine hundred rows it never reached.
        """
        try:
            stamp = ('escalated_on' if kind == 'expired' else 'last_alert_on')
            if agreement[stamp] == today:
                counters['skipped'] += 1
                return
            made = self._activity(agreement, kind)
            if made:
                counters['reminded' if kind == 'renewal' else 'escalated'] += 1
            if not mails_on:
                counters['would_mail'] += 1
            elif counters['mailed'] >= burst:
                counters['would_mail'] += 1
            elif self._mail(agreement, kind):
                counters['mailed'] += 1
            agreement.sudo().write({stamp: today})
        except Exception:                       # noqa: BLE001
            _logger.warning(
                'pb.vendor.alerts: agreement %s could not be processed',
                agreement.id, exc_info=True)

    def _summary(self, agreement, kind):
        """The idempotency key, and it is one an agreement actually HAS (R49).

        The agreement id is in it on purpose: two agreements with the same
        vendor and the same title are two different pieces of work, and a key
        built from names alone would recognise the second as a duplicate of the
        first and never raise it.
        """
        if kind == 'expired':
            return _("Vendor agreement has ended: %(vendor)s — %(name)s (#%(id)s)",
                     vendor=agreement.vendor_id.name or '',
                     name=agreement.name or '', id=agreement.id)
        return _("Vendor agreement to renew: %(vendor)s — %(name)s (#%(id)s)",
                 vendor=agreement.vendor_id.name or '',
                 name=agreement.name or '', id=agreement.id)

    def _activity(self, agreement, kind):
        """One open activity per agreement per kind, ever.

        `pb.vendor.agreement` inherits `mail.thread` only, and
        `activity_schedule` lives on `mail.activity.mixin` (R3) — so the
        activity is scheduled on the VENDOR, which has both. That is also where
        somebody would look for it: the work is "sort out this supplier", not
        "sort out row 41".
        """
        vendor = agreement.vendor_id
        if not vendor:
            return False
        summary = self._summary(agreement, kind)
        Activity = self.env['mail.activity'].sudo()
        existing = Activity.search([
            ('res_model', '=', 'pb.vendor'),
            ('res_id', '=', vendor.id),
            ('summary', '=', summary),
        ], limit=1)
        if existing:
            return False
        responsible = agreement.responsible_user_id or self.env.user
        note = (_("The agreement \"%(name)s\" with %(vendor)s ended on "
                  "%(date)s and nothing has replaced it.",
                  name=agreement.name or '', vendor=vendor.name or '',
                  date=agreement.date_end)
                if kind == 'expired' else
                _("The agreement \"%(name)s\" with %(vendor)s ends on "
                  "%(date)s. Renew it, replace it or let it go.",
                  name=agreement.name or '', vendor=vendor.name or '',
                  date=agreement.date_end))
        vendor.sudo().activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            summary=summary,
            note=note,
            user_id=responsible.id,
            date_deadline=agreement.renewal_date or agreement.date_end)
        return True

    def _mail(self, agreement, kind):
        """The mail, with its recipient passed EXPLICITLY (R6).

        A template's own rendered `email_to` can reach `mail.mail` empty, and
        the message is then created, queued and addressed to nobody with no
        error anywhere. The template's field stays as documentation of who it
        is for; this is what actually addresses it.
        """
        xmlid = ('pb_vendor_access.mail_template_agreement_expired'
                 if kind == 'expired'
                 else 'pb_vendor_access.mail_template_agreement_renewal')
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return False
        to = self._recipients(agreement, kind)
        if not to:
            return False
        template.sudo().send_mail(
            agreement.id, force_send=False,
            email_values={'email_to': ','.join(to)})
        return True

    def _recipients(self, agreement, kind):
        """The owner always; the HR team as well when it has already run out.

        Read AS THE SYSTEM (R56/R104): one field of a user or an employee
        prefetches forty, about forty of which sit behind payroll groups, so a
        reader holding this module's group and not the payroll ones would get
        an AccessError in the middle of working out who to email — and the
        caller's try/except would report a perfectly good agreement as a failed
        one.
        """
        out = []
        owner = agreement.sudo().responsible_user_id
        if owner and owner.email:
            out.append(owner.email)
        if kind == 'expired':
            for xmlid in ('pb_vendor_access.group_vendor_manager',
                          'pb_lifecycle.group_lifecycle_manager'):
                group = self.env.ref(xmlid, raise_if_not_found=False)
                if not group:
                    continue
                # R7 — `res.users.group_ids` is DIRECT membership only and
                # misses everyone who holds the group through `implied_ids`.
                # `res.groups.all_user_ids` is the transitive set.
                for user in group.sudo().all_user_ids:
                    if user.email and user.email not in out:
                        out.append(user.email)
        return out

    # ------------------------------------------------------------- the wording
    def _message(self, counters, mails_on):
        """One sentence, built as ONE expression so the spaces survive (R34)."""
        if not (counters['due'] or counters['overdue']):
            return _("Nothing needs renewing. Every agreement on the register "
                     "has time left on it.")
        parts = []
        if counters['reminded']:
            parts.append(counted(
                counters['reminded'],
                _("1 renewal was raised"),
                _("%s renewals were raised")))
        if counters['escalated']:
            parts.append(counted(
                counters['escalated'],
                _("1 agreement has run out and was escalated"),
                _("%s agreements have run out and were escalated")))
        if counters['skipped']:
            parts.append(counted(
                counters['skipped'],
                _("1 was already handled today"),
                _("%s were already handled today")))
        if not parts:
            return _("Everything due had already been handled today.")
        line = _("%s.", '; '.join(parts))
        if not mails_on:
            return _("%s No mail was sent — the reminder emails are switched "
                     "off on this system.", line)
        return line
