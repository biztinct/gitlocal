# -*- coding: utf-8 -*-
"""One job a morning: bring every assignment up to date, then chase it.

CLONED FROM THE PATTERN THIS CODEBASE ALREADY TRUSTS — the document vault's
expiry watch and `pb_lifecycle`'s reminder cron: a config-param horizon, a
ledger so a second run of the same day sends nothing twice, one try/except AND
one savepoint per record (R131), honest counts in the log, and the whole thing
behind a switch that SAYS it is off (R54).

THE LEDGER IS KEYS AND NOT DATES, and that is the important design decision.
"Have they been told it is due in three days" is a question with one answer for
ever, so the key is `d3` and it is written once. The overdue nudges are bucketed
— `od0`, `od1`, `od2` — by how many whole three-day windows have passed, so a
job that misses a night catches up with ONE message rather than four, and a job
that runs twice in a morning sends none.

A CAP THAT IS RIGHT FOR A SCREEN IS A BUG IN A JOB (R76). The cap here is not a
page size: it is a safety rail so a schedule somebody pointed at "everybody in
every company" cannot mail five thousand people twice before anybody notices.
When it bites, the log says so by name and the rest go out tomorrow.

WHO GETS TOLD, in order: the person, then their manager, then whoever holds the
HR lead responsibility in the Approval Matrix for that company — and only if
nobody holds it, the training managers. Every address is read AS THE SYSTEM,
because a manager holds no HR group by definition and `work_email` sits behind
one (R56/R104).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .training_common import (
    ASSIGN_OPEN, GROUP_MANAGER, P_HR_DAYS, P_MANAGER_DAYS, P_REMINDER_CAP,
    P_REMINDERS, counted, days_over, flag, number,
)

_logger = logging.getLogger(__name__)


class PbTrainingAutomation(models.AbstractModel):
    """The jobs. An AbstractModel because it owns no rows — only behaviour."""
    _name = 'pb.training.automation'
    _description = 'Payobook Training — the jobs that run themselves'

    # =====================================================================
    #  the daily job
    # =====================================================================
    @api.model
    def _cron_daily(self):
        today = fields.Date.today()
        counts = {'refreshed': 0, 'scheduled': 0, 'employee': 0,
                  'manager': 0, 'hr': 0, 'capped': 0}
        counts['refreshed'] = self._leg('bring assignments up to date',
                                        lambda: self._refresh_all(today))
        counts['scheduled'] = self._leg('run the compliance schedules',
                                        lambda: self._run_schedules(today))
        if not flag(self.env, P_REMINDERS):
            _logger.info(
                'pb_training: %s assignment(s) brought up to date, %s new '
                'from a schedule — the chasing is switched off '
                '(pb_training.reminders), so nobody was written to',
                counts['refreshed'], counts['scheduled'])
            return counts
        chased = self._leg('chase what is due and what is late',
                           lambda: self._chase(today), default={})
        counts.update(chased or {})
        _logger.info(
            'pb_training: %s assignment(s) brought up to date, %s new from a '
            'schedule, %s nudge(s) to people, %s to managers, %s to the HR '
            'lead%s',
            counts['refreshed'], counts['scheduled'], counts['employee'],
            counts['manager'], counts['hr'],
            ' — the send cap was reached, the rest go out tomorrow'
            if counts.get('capped') else '')
        return counts

    @api.model
    def run_now(self):
        """The same job, by hand. Managers only — it sends email.

        A "RUN IT NOW" BUTTON MUST DO EXACTLY WHAT THE NIGHT DOES (R53), or
        the number it reports cannot be compared with the morning's log. This
        is the same method, not a subset of it.
        """
        if not (self.env.user.has_group(GROUP_MANAGER)
                or self.env.user._is_admin()):
            raise AccessError(_(
                "Only a training manager can send the reminders by hand."))
        return self._cron_daily()

    # --------------------------------------------------------------- legs
    @api.model
    def _leg(self, label, fn, default=0):
        """One piece of the job, inside its own savepoint (R131)."""
        try:
            with self.env.cr.savepoint():
                return fn()
        except Exception:               # noqa: BLE001 — a job never raises
            _logger.warning('pb_training: %s failed', label, exc_info=True)
            return default

    # =====================================================================
    #  bringing the states up to date
    # =====================================================================
    @api.model
    def _refresh_all(self, today):
        """Every open assignment, plus anything that has quietly finished.

        `state = False` is included because a row whose creation was rolled
        back half way has no state at all, and a row nobody can see the state
        of is a row nobody chases.
        """
        rows = self.env['pb.training.assignment'].sudo().search([
            '|', ('state', 'in', ASSIGN_OPEN), ('state', '=', False)])
        done = 0
        for row in rows:
            try:
                with self.env.cr.savepoint():
                    row._refresh_one(today)
                done += 1
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: assignment %s could not be '
                                'brought up to date', row.id, exc_info=True)
        return done

    # =====================================================================
    #  the compliance schedules
    # =====================================================================
    @api.model
    def _run_schedules(self, today):
        schedules = self.env['pb.training.schedule'].sudo().search([
            ('active', '=', True), ('next_run', '<=', today)])
        made = 0
        for schedule in schedules:
            try:
                with self.env.cr.savepoint():
                    made += schedule.run_now()
            except Exception:           # noqa: BLE001 — one schedule, one grave
                _logger.warning('pb_training: schedule %s could not run',
                                schedule.id, exc_info=True)
        return made

    # =====================================================================
    #  the chasing
    # =====================================================================
    @api.model
    def _chase(self, today):
        cap = number(self.env, P_REMINDER_CAP, 400)
        mgr_days = max(number(self.env, P_MANAGER_DAYS, 2), 0)
        hr_days = max(number(self.env, P_HR_DAYS, 5), 0)
        counts = {'employee': 0, 'manager': 0, 'hr': 0, 'capped': 0}
        rows = self.env['pb.training.assignment'].sudo().search([
            ('state', 'in', ASSIGN_OPEN),
            ('due_date', '!=', False),
        ])
        for row in rows:
            if counts['employee'] + counts['manager'] + counts['hr'] >= cap:
                counts['capped'] += 1
                continue
            try:
                with self.env.cr.savepoint():
                    self._chase_one(row, today, mgr_days, hr_days, counts)
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: assignment %s could not be '
                                'chased', row.id, exc_info=True)
        return counts

    @api.model
    def _chase_one(self, row, today, mgr_days, hr_days, counts):
        """Every nudge one assignment owes today, and no more."""
        # MORE TIME AGREED MEANS NOT CHASED. The excuse runs to the new due
        # date and no further — after that it is simply late again.
        if row.excused_until and row.excused_until >= today:
            return
        sent = row._sent()
        due = row.due_date
        late = days_over(due, today)
        left = (due - today).days if due else None

        # ---- the person -------------------------------------------------
        key = None
        if late:
            # every three days while it is late, bucketed so a missed night
            # catches up with one message rather than four
            if late >= 3:
                key = 'od%s' % (late // 3)
            else:
                key = 'od0'
        elif left == 0:
            key = 'd0'
        elif left == 1:
            key = 'd1'
        elif left == 3:
            key = 'd3'
        if key and key not in sent:
            template = 'pb_training.mail_template_assignment_overdue' if late \
                else 'pb_training.mail_template_assignment_due'
            if row._mail(template, row._their_email()):
                row._mark_sent(key, today)
                counts['employee'] += 1

        if not late:
            return

        # ---- their manager ----------------------------------------------
        if late >= mgr_days:
            bucket = (late - mgr_days) // 7
            key = 'mgr%s' % bucket
            if key not in sent:
                if row._mail(
                        'pb_training.mail_template_assignment_manager_late',
                        row._manager_email()):
                    row._mark_sent(key, today)
                    counts['manager'] += 1

        # ---- the HR lead --------------------------------------------------
        if late >= hr_days:
            bucket = (late - hr_days) // 7
            key = 'hr%s' % bucket
            if key not in sent:
                if row._mail('pb_training.mail_template_assignment_hr_late',
                             self._hr_email(row.company_id)):
                    row._mark_sent(key, today)
                    counts['hr'] += 1

    # =====================================================================
    #  who the HR lead is
    # =====================================================================
    @api.model
    def _hr_email(self, company):
        """The HR lead's address, from the Matrix; the training managers if
        nobody holds it.

        THE RESPONSIBILITY AND NOT A GROUP, because that is where this product
        already keeps the answer to "who is the HR lead here" — the same seat
        every approval route resolves. The group is the fall-back and it is
        named in the log when it is used, so "the HR lead was told" never
        quietly means "somebody in the training team was told".
        """
        holders = self._hr_users(company)
        if holders:
            return ','.join(sorted({u.email for u in holders if u.email}))
        managers = self._group_users(GROUP_MANAGER, company)
        if managers:
            _logger.info('pb_training: nobody holds the HR lead seat for %s — '
                         'the late courses went to the training managers',
                         company.display_name)
        return ','.join(sorted({u.email for u in managers if u.email}))

    @api.model
    def _hr_users(self, company):
        """Everybody holding the `hr_lead` seat for this company today."""
        if 'biz.approval.responsibility' not in self.env:
            return self.env['res.users']
        today = fields.Date.today()
        rows = self.env['biz.approval.responsibility'].sudo().search([
            ('role_key', '=', 'hr_lead'),
            ('company_id', '=', company.id),
            ('active', '=', True),
        ])
        users = self.env['res.users']
        for row in rows:
            if row.date_from and row.date_from > today:
                continue
            if row.date_to and row.date_to < today:
                continue
            users |= row.user_id | row.backup_user_id | row.pool_user_ids
        return users.filtered(lambda u: u.active and not u.share)

    @api.model
    def _group_users(self, xmlid, company):
        """Everybody in a group, INCLUDING the ones who hold it by implication.

        `res.users.group_ids` is direct membership only and misses everybody
        who holds a group through `implied_ids` — which is most administrators
        (R7). `res.groups.all_user_ids` is the transitive set.
        """
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        users = group.sudo().all_user_ids
        return users.filtered(
            lambda u: u.active and not u.share
            and (not company or company in u.company_ids))

    # =====================================================================
    #  what a manager's own page counts
    # =====================================================================
    @api.model
    def team_overdue_count(self, user=None):
        """How many of this person's team are late. Never raises."""
        try:
            user = user or self.env.user
            emp = self.env['hr.employee'].sudo().search(
                [('user_id', '=', user.id)], limit=1)
            if not emp:
                return 0
            reports = self.env['hr.employee'].sudo().search(
                [('parent_id', '=', emp.id)])
            if not reports:
                return 0
            return self.env['pb.training.assignment'].sudo().search_count([
                ('employee_id', 'in', reports.ids),
                ('state', '=', 'overdue')])
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the team overdue count could not be '
                            'read', exc_info=True)
            return 0

    @api.model
    def counted_words(self, count, one, many):
        return counted(count, one, many)
