# -*- coding: utf-8 -*-
"""What this module adds to P0's daily job — and what it deliberately does not.

NO SECOND CRON. Everything here rides `_cron_lifecycle_reminders`, extended the
way P5's automation extends it. Two jobs on the same tables are two jobs that
can disagree about what "today" means.

TWO PIECES, and both of them only ever tell somebody something:

  * **missed check-ins** — a conversation planned on a running plan that did not
    happen. This is the earliest available signal that a plan is drifting, and
    P0 has no way to know about it: its own check-in nudge writes to the owner
    of everything planned for TODAY and knows nothing about plans.
  * **plans that have run out of road** — a plan whose end date has passed and
    which is still `active`. It is COUNTED and logged and the HR owner is told;
    it is NOT moved to `evaluation` by itself, because moving it sends a form to
    a manager, and a module that emails managers about people's performance on
    its own the first night after installation is a module that gets switched
    off (R54's lesson, applied before it could bite).

WHAT P0 ALREADY DOES AND THIS DOES NOT REPEAT: the nudge to the owner of every
check-in planned for today. A PIP check-in is a check-in, and a second email
saying the same thing in different words is how a person learns to filter both.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .pip_common import GROUP_HEAD, GROUP_USER, PIP_OPEN

_logger = logging.getLogger(__name__)


class PbJourneyCasePipReminders(models.Model):
    _inherit = 'pb.journey.case'

    @api.model
    def _cron_lifecycle_reminders(self):
        """P0's job, plus the two things a running plan needs looked at.

        Each piece inside its OWN try/except: a failure in the improvement-plan
        additions must not stop the joining and leaving nudges P0's own job
        exists to send.
        """
        counts = super()._cron_lifecycle_reminders()
        if not isinstance(counts, dict):
            counts = {'base': counts}
        today = fields.Date.today()
        for key, fn in (
                ('pip_missed', lambda: self.env['pb.pip.case']
                 ._nudge_missed_checkins(today)),
                ('pip_due', lambda: self._pip_plans_past_their_end(today))):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — one piece, one grave
                _logger.exception('pb_pip: %s did not run', key)
                counts[key] = 0
        _logger.info('pb_pip: %s missed check-in alert(s), %s plan(s) past '
                     'their end date', counts.get('pip_missed', 0),
                     counts.get('pip_due', 0))
        return counts

    @api.model
    def _pip_plans_past_their_end(self, today=None):
        """Tell the HR owner; never move the plan on by itself.

        The transition to `evaluation` sends a private link to a line manager
        asking them to rate somebody. That is not a thing a cron should do on
        its own the night after somebody installs a module, so this counts them
        and writes to the person whose job it is. The lens says the same number
        on screen with a button beside it.

        IDEMPOTENT — the note is posted once per plan, and the flag that says
        so is the activity the note raises, searched for before it is created
        (the vault's expiry-cron pattern, which is the reminder shape this
        codebase already trusts).
        """
        today = today or fields.Date.today()
        Case = self.env['pb.pip.case'].sudo()
        Activity = self.env['mail.activity'].sudo()
        due = Case.search([
            ('state', '=', 'active'),
            ('end_date', '!=', False),
            ('end_date', '<', today),
        ])
        made = 0
        for case in due:
            try:
                summary = _("Growth plan has reached its end date")
                existing = Activity.search([
                    ('res_model', '=', 'pb.pip.case'),
                    ('res_id', '=', case.id),
                    ('summary', '=', summary)], limit=1)
                if existing:
                    continue
                owner = case.hr_owner_user_id
                case.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=summary,
                    note=_("%(who)s's plan ran to %(when)s. Ask their manager "
                           "how it went, then decide.",
                           who=case.employee_id.name or '',
                           when=case.end_date),
                    user_id=owner.id if owner else self.env.uid,
                    date_deadline=case.end_date)
                case._mail('pb_pip.mail_template_pip_due',
                           case._hr_addresses())
                made += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_pip: end-date note for plan %s', case.id)
        return made

    @api.model
    def run_pip_automation(self):
        """The same two pieces, on demand — and EXACTLY those two.

        R53: a "run it now" button that does a different amount of work from
        the night is a button whose number cannot be compared to the morning's
        log. So this runs the two pieces the daily job adds and nothing else;
        P0's own reminders stay behind `run_reminders`, which is where they
        have always been.
        """
        user = self.env.user
        if not (user.has_group(GROUP_USER) or user.has_group(GROUP_HEAD)):
            raise AccessError(_(
                "Growth plans are looked after by the HR team."))
        today = fields.Date.today()
        out = {'missed': 0, 'due': 0, 'open': 0}
        try:
            out['missed'] = self.env['pb.pip.case']._nudge_missed_checkins(
                today)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: the missed check-in pass failed')
        try:
            out['due'] = self._pip_plans_past_their_end(today)
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: the end-date pass failed')
        try:
            out['open'] = self.env['pb.pip.case'].sudo().search_count(
                [('state', 'in', list(PIP_OPEN))])
        except Exception:               # noqa: BLE001
            _logger.exception('pb_pip: could not count the open plans')
        return out
