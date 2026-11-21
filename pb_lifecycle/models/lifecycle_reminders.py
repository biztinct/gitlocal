# -*- coding: utf-8 -*-
"""One daily job, and the four things it nudges.

Cloned from the document vault's expiry watch, which is the reminder pattern
this codebase already trusts: a config-param horizon, a SEARCH BEFORE CREATE so
a second run of the same day adds nothing, one try/except per record so one bad
row cannot stop the rest, and a log line that says how many it really did.

The whole job is behind `pb_lifecycle.reminders_enabled`. A deployment that does
not want lifecycle email turns it off in one row and nothing else changes.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .lifecycle_common import (
    DEFAULT_REMIND_DAYS, GROUP_MANAGER, PARAM_REMIND_DAYS, PARAM_REMINDERS_ON,
)

_logger = logging.getLogger(__name__)

_OPEN = ('pending', 'in_progress', 'blocked')


class PbJourneyCaseReminders(models.Model):
    _inherit = 'pb.journey.case'

    # ------------------------------------------------------------- settings
    @api.model
    def _reminders_enabled(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_REMINDERS_ON, '1')
        return str(raw).strip() not in ('0', 'false', 'False', '')

    @api.model
    def _remind_days(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            PARAM_REMIND_DAYS, DEFAULT_REMIND_DAYS)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = DEFAULT_REMIND_DAYS
        return days if days >= 0 else DEFAULT_REMIND_DAYS

    # ------------------------------------------------------------- the job
    @api.model
    def _cron_lifecycle_reminders(self):
        if not self._reminders_enabled():
            _logger.info('pb_lifecycle: reminders are switched off')
            return {'off': True}
        today = fields.Date.today()
        horizon = today + timedelta(days=self._remind_days())
        counts = {
            'reminded': self._remind_due_tasks(today, horizon),
            'escalated': self._escalate_overdue_tasks(today),
            'checkins': self._remind_checkins(today),
            'feedback_expired': self._expire_feedback(today),
            'feedback_reminded': self._remind_feedback(today),
        }
        _logger.info(
            'pb_lifecycle reminders: %s task nudge(s), %s escalation(s), '
            '%s check-in nudge(s), %s feedback window(s) closed, '
            '%s feedback nudge(s)',
            counts['reminded'], counts['escalated'], counts['checkins'],
            counts['feedback_expired'], counts['feedback_reminded'])
        return counts

    @api.model
    def run_reminders(self):
        """The same job, on demand. Managers only — it sends email."""
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only a lifecycle manager can send the reminders by hand."))
        return self._cron_lifecycle_reminders()

    # ---------------------------------------------------------------- pieces
    def _mail(self, xmlid, record, email_to=None):
        """Queue one email. Never raises — a failed nudge is logged, not fatal.

        NO ADDRESS, NO MAIL. A queued message with an empty `email_to` is a dead
        letter that still counts as a nudge, so the log would claim somebody was
        told when nobody was. Answering False here keeps the count honest and
        leaves the step to the escalation, which goes to a different list.
        """
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_lifecycle: %s is missing', xmlid)
            return False
        if not email_to:
            _logger.info('pb_lifecycle: %s#%s has nobody to write to — not '
                         'queued', record._name, record.id)
            return False
        try:
            values = {'email_to': email_to} if email_to else {}
            template.sudo().send_mail(record.id, force_send=False,
                                      email_values=values)
            return True
        except Exception:
            _logger.exception('pb_lifecycle: could not queue %s for %s#%s',
                              xmlid, record._name, record.id)
            return False

    @api.model
    def _remind_due_tasks(self, today, horizon):
        Task = self.env['pb.journey.task'].sudo()
        Activity = self.env['mail.activity'].sudo()
        tasks = Task.search([
            ('state', 'in', _OPEN),
            ('due_date', '!=', False),
            ('due_date', '<=', horizon),
            ('case_id.state', '=', 'active'),
            ('assignee_user_id', '!=', False),
        ])
        made = 0
        for task in tasks:
            try:
                summary = _("Journey step due: %s", task.name)
                existing = Activity.search([
                    ('res_model', '=', 'pb.journey.case'),
                    ('res_id', '=', task.case_id.id),
                    ('summary', '=', summary)], limit=1)
                if not existing:
                    task.case_id.sudo().activity_schedule(
                        act_type_xmlid='mail.mail_activity_data_todo',
                        summary=summary,
                        note=_("'%(step)s' for %(who)s is due on %(when)s.",
                               step=task.name,
                               who=task.employee_id.name or '',
                               when=task.due_date),
                        user_id=task.assignee_user_id.id,
                        date_deadline=task.due_date)
                if task.reminded_on == today:
                    continue          # already nudged today; run twice, mail once
                if self._mail('pb_lifecycle.mail_template_task_reminder', task,
                              email_to=task.assignee_user_id.email):
                    task.write({'reminded_on': today})
                    made += 1
            except Exception:
                _logger.exception('pb_lifecycle: reminder for task %s',
                                  task.id)
        return made

    @api.model
    def _escalate_overdue_tasks(self, today):
        Task = self.env['pb.journey.task'].sudo()
        tasks = Task.search([
            ('state', 'in', _OPEN),
            ('escalated', '=', False),
            ('due_date', '!=', False),
            ('due_date', '<', today),
            ('case_id.state', '=', 'active'),
        ])
        made = 0
        for task in tasks:
            try:
                grace = task.escalation_days or 3
                if task.due_date + timedelta(days=grace) > today:
                    continue
                managers = self._users_in_group(
                    GROUP_MANAGER, task.company_id or self.env.company,
                    limit=0)
                to = ','.join(u.email for u in managers if u.email) or None
                if not self._mail(
                        'pb_lifecycle.mail_template_task_escalation', task,
                        email_to=to):
                    # NOT marked escalated. `escalated` is a "this has been
                    # raised" flag and it is checked once, forever — setting it
                    # when nobody was actually written to would bury the step
                    # for good. Left alone, tomorrow's run tries again, and the
                    # day somebody gives the lifecycle managers an email
                    # address the backlog goes out.
                    _logger.warning(
                        'pb_lifecycle: step %s is overdue but no lifecycle '
                        'manager has an email address — not escalated',
                        task.id)
                    continue
                task.write({'escalated': True})
                task.case_id.message_post(body=_(
                    "%(step)s is %(days)s day(s) overdue — the lifecycle "
                    "managers have been told.",
                    step=task.name, days=(today - task.due_date).days))
                made += 1
            except Exception:
                _logger.exception('pb_lifecycle: escalation for task %s',
                                  task.id)
        return made

    @api.model
    def _remind_checkins(self, today):
        Checkin = self.env['pb.employee.checkin'].sudo()
        due = Checkin.search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '=', today),
            ('owner_user_id', '!=', False),
        ])
        made = 0
        for checkin in due:
            try:
                if self._mail('pb_lifecycle.mail_template_checkin_today',
                              checkin, email_to=checkin.owner_user_id.email):
                    made += 1
            except Exception:
                _logger.exception('pb_lifecycle: check-in nudge %s', checkin.id)
        return made

    @api.model
    def _expire_feedback(self, today):
        Feedback = self.env['pb.feedback.request'].sudo()
        stale = Feedback.search([
            ('state', 'in', ('sent', 'extended')),
            ('window_end', '!=', False),
            ('window_end', '<', today),
        ])
        if stale:
            stale.write({'state': 'expired'})
        return len(stale)

    @api.model
    def _remind_feedback(self, today):
        Feedback = self.env['pb.feedback.request'].sudo()
        closing = Feedback.search([
            ('state', 'in', ('sent', 'extended')),
            ('window_end', '=', today),
        ])
        made = 0
        for req in closing:
            try:
                to = req.respondent_email or (
                    req.respondent_user_id.email
                    if req.respondent_user_id else None)
                if to and self._mail(
                        'pb_lifecycle.mail_template_feedback_invite', req,
                        email_to=to):
                    made += 1
            except Exception:
                _logger.exception('pb_lifecycle: feedback nudge %s', req.id)
        return made
