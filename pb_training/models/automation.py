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
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    ASSIGN_OPEN, GROUP_MANAGER, P_CERT_MANAGER_DAYS, P_CERT_REMINDERS,
    P_HR_DAYS, P_MANAGER_DAYS, P_RENEW_BEFORE, P_REMINDER_CAP, P_REMINDERS,
    counted, days_over, flag, number,
)

#: LEARNING L1 — the certificate ladder, to the person. Each band fires once
#: (the first morning the certificate is inside it), so a certificate added
#: with twenty days left gets the 30-day mail and not a late 60-day one.
CERT_BANDS = (('x60', 60, 31), ('x30', 30, 8), ('x7', 7, 1), ('x0', 0, 0))

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
                  'manager': 0, 'hr': 0, 'capped': 0, 'renewals': 0,
                  'certificates': 0, 'required': 0}
        counts['refreshed'] = self._leg('bring assignments up to date',
                                        lambda: self._refresh_all(today))
        counts['scheduled'] = self._leg('run the compliance schedules',
                                        lambda: self._run_schedules(today))
        # LEARNING L2, leg 5: whoever is missing a required course (or whose
        # one is about to run out) is put on it. Beside the schedules and not
        # behind the reminders switch, because it MAKES assignments rather
        # than chasing them — the same as a schedule does.
        required = self._leg('put required courses on people',
                             lambda: self._enforce_requirements(today),
                             default={})
        counts['required'] = (required or {}).get('made', 0)
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
        # LEARNING L1, leg 3b: a certificate inside its renewal window puts
        # the refresher course on the person by itself.
        counts['renewals'] = self._leg(
            'put renewal courses on people', lambda: self._renewals(today))
        # Leg 4: the certificate ladder, under the same send cap.
        if flag(self.env, P_CERT_REMINDERS):
            self._leg('chase certificates that are running out',
                      lambda: self._chase_certificates(today, counts),
                      default=None)
        _logger.info(
            'pb_training: %s assignment(s) brought up to date, %s new from a '
            'schedule, %s nudge(s) to people, %s to managers, %s to the HR '
            'lead, %s renewal course(s) put on, %s certificate reminder(s), '
            '%s required course(s) put on%s',
            counts['refreshed'], counts['scheduled'], counts['employee'],
            counts['manager'], counts['hr'], counts['renewals'],
            counts['certificates'], counts['required'],
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
    #  LEARNING L1 — renewal courses
    # =====================================================================
    @api.model
    def _renewal_candidates(self, today):
        window = max(number(self.env, P_RENEW_BEFORE, 60), 0)
        if 'pb.employee.document' not in self.env:
            return self.env['res.partner'].browse()
        # NOT YET EXPIRED, ON PURPOSE. A certificate that ran out before this
        # system ever saw it (a back-filled row from years ago) must not wake
        # up as a renewal course that is overdue the moment it is made — and
        # mails its manager and the HR lead the same morning. The window is
        # sixty days, so a certificate this job is watching is caught long
        # before its day; anything older is a person for HR to decide on
        # (the register's "Assign the refresher").
        docs = self.env['pb.employee.document'].sudo().search([
            ('training_source', '=', 'test'),
            ('renewed_by_id', '=', False),
            ('renewal_assignment_id', '=', False),
            ('channel_id', '!=', False),
            ('expiry_date', '>=', today),
            ('expiry_date', '<=', today + timedelta(days=window)),
            ('employee_id.active', '=', True),
        ])
        # LEARNING L2: ONE OWNER PER COURSE. A course a required-training rule
        # assigns by itself is renewed by that rule (leg 5), never by this
        # leg as well — one course, one person, one assignment.
        owned = self._required_owned_courses()
        if owned:
            docs = docs.filtered(
                lambda d: (d.channel_id.id, d.company_id.id) not in owned)
        return docs

    @api.model
    def _renewals(self, today):
        made = 0
        for doc in self._renewal_candidates(today):
            try:
                with self.env.cr.savepoint():
                    if self._assign_renewal(doc, today=today):
                        made += 1
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: no renewal course could be put '
                                'on for certificate %s', doc.id, exc_info=True)
        return made

    @api.model
    def _assign_renewal(self, doc, today=None, raise_on_clash=False):
        """The refresher course for one certificate. ONE per certificate,
        ever: `renewal_assignment_id` is the guard, and an assignment already
        open on that course is left alone (`_guard_one_open` would refuse a
        second one anyway).

        From the morning job (`raise_on_clash=False`) a reason not to is a
        quiet `False`; from the register's button it is a sentence.
        """
        today = today or fields.Date.today()

        def refuse(message):
            if raise_on_clash:
                raise UserError(message)
            return False

        doc = doc.sudo()
        emp = doc.employee_id.sudo()
        channel = doc.channel_id.sudo()
        if not channel:
            return refuse(_("This certificate is not tied to a course here, "
                            "so there is no refresher to assign."))
        if not channel.active:
            return refuse(_("%s is archived, so it cannot be assigned.",
                            channel.name))
        renewal = doc.renewal_assignment_id
        if renewal and renewal.state in ASSIGN_OPEN:
            return refuse(_("The renewal course is already assigned — due "
                            "%s.", renewal.due_date or ''))
        if not emp.user_id:
            return refuse(_("%s has no login yet, so there is nowhere for the "
                            "course to appear.", emp.name or ''))
        Assignment = self.env['pb.training.assignment'].sudo()
        clash = Assignment.search([('channel_id', '=', channel.id),
                                   ('employee_id', '=', emp.id),
                                   ('state', 'in', ASSIGN_OPEN)], limit=1)
        if clash:
            return refuse(_("%(who)s is already doing %(course)s — it is due "
                            "on %(when)s.", who=emp.name or '',
                            course=channel.name or '',
                            when=clash.due_date or ''))
        due = doc.expiry_date if doc.expiry_date and doc.expiry_date >= today \
            else Assignment._default_due(today)
        # The morning job puts it on as the system; the register's button as
        # the person who pressed it (sudo keeps their uid).
        maker = Assignment if raise_on_clash \
            else Assignment.with_user(SUPERUSER_ID).sudo()
        row = maker.create({
            'channel_id': channel.id,
            'employee_id': emp.id,
            'reason': 'renewal',
            'due_date': due,
            'counts_for_probation': False,
            'company_id': (emp.company_id or self.env.company).id,
        })
        doc.write({'renewal_assignment_id': row.id})
        return {'assignment_id': row.id,
                'message': _("%(who)s is on %(course)s again, to be finished "
                             "by %(when)s.", who=emp.name or '',
                             course=channel.name or '', when=due)}

    # =====================================================================
    #  LEARNING L2 — leg 5, required training
    # =====================================================================
    @api.model
    def _enforce_rules(self):
        """The rules this leg owns: live, auto-assigned, in a company, with a
        course to put people on, and not a converted legacy row (a day-one
        rule or a schedule still assigns through its own mechanism)."""
        return self.env['pb.training.requirement'].sudo().search([
            ('active', '=', True), ('auto_assign', '=', True),
            ('company_id', '!=', False), ('channel_id', '!=', False),
            ('rule_id', '=', False), ('schedule_id', '=', False),
            ('ratio_people', '=', 0),
        ])

    @api.model
    def _required_owned_courses(self):
        out = set()
        for req in self._enforce_rules():
            for channel in req.channel_id | req.refresher_channel_id:
                out.add((channel.id, req.company_id.id))
        return out

    @api.model
    def _enforce_requirements(self, today, rules=None):
        """For every missing cell (or expiring one) of every rule above,
        the course — reason `required`, `requirement_id` set, due per
        `_required_due`. Never a second open one (`_guard_one_open`), each in
        its own savepoint, capped per run (`pb_training.enforce_cap`)."""
        from .training_common import P_ENFORCE_CAP
        cap = max(number(self.env, P_ENFORCE_CAP, 500), 0)
        counts = {'made': 0, 'capped': 0, 'no_login': 0, 'failed': 0}
        # `rules` narrows the run (tests, a future "run this rule now");
        # the morning job passes nothing and gets every rule it owns.
        rules = self._enforce_rules() if rules is None \
            else rules & self._enforce_rules()
        if not rules:
            return counts
        Req = self.env['pb.training.requirement']
        cells = Req.evaluate(rules, today=today)
        employees = self.env['hr.employee'].sudo().browse(
            sorted({emp for _rid, emp in cells}))
        logins = {e.id: bool(e.user_id) for e in employees}
        joins = Req._join_dates(employees) \
            if any(r.kind == 'day_one' for r in rules) else {}
        Assignment = self.env['pb.training.assignment'].with_user(
            SUPERUSER_ID).sudo()
        for rule in rules:
            for emp in employees:
                cell = cells.get((rule.id, emp.id))
                if not cell or cell['state'] not in ('missing', 'expiring'):
                    continue
                if cell.get('open_id'):
                    continue
                channel = rule.refresher_channel_id \
                    if cell['state'] == 'expiring' and rule.refresher_channel_id \
                    else rule.channel_id
                if counts['made'] >= cap:
                    counts['capped'] += 1
                    continue
                if not logins.get(emp.id):
                    counts['no_login'] += 1
                    continue
                if Assignment.search_count([
                        ('channel_id', '=', channel.id),
                        ('employee_id', '=', emp.id),
                        ('state', 'in', ASSIGN_OPEN)]):
                    continue
                try:
                    with self.env.cr.savepoint():
                        Assignment.create(rule._assignment_vals(
                            emp, channel, today, joins.get(emp.id),
                            cell))
                    counts['made'] += 1
                except Exception:       # noqa: BLE001 — one person, one grave
                    counts['failed'] += 1
                    _logger.warning('pb_training: required course %s could '
                                    'not be put on %s', channel.id, emp.id,
                                    exc_info=True)
        if counts['capped']:
            _logger.info('pb_training: the required-training cap (%s) was '
                         'reached; %s more go on tomorrow', cap,
                         counts['capped'])
        return counts

    # =====================================================================
    #  LEARNING L1 — the certificate ladder
    # =====================================================================
    @api.model
    def _chase_certificates(self, today, counts):
        cap = number(self.env, P_REMINDER_CAP, 400)
        mgr_days = max(number(self.env, P_CERT_MANAGER_DAYS, 14), 0)
        if 'pb.employee.document' not in self.env:
            return counts
        docs = self.env['pb.employee.document'].sudo().search([
            ('training_source', '!=', False),
            ('renewed_by_id', '=', False),
            ('expiry_date', '>=', today),
            ('expiry_date', '<=', today + timedelta(days=60)),
            ('employee_id.active', '=', True),
        ])
        for doc in docs:
            sent = (counts.get('employee', 0) + counts.get('manager', 0)
                    + counts.get('hr', 0) + counts.get('certificates', 0))
            if sent >= cap:
                counts['capped'] = counts.get('capped', 0) + 1
                continue
            try:
                with self.env.cr.savepoint():
                    self._chase_cert_one(doc, today, mgr_days, counts)
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: certificate %s could not be '
                                'chased', doc.id, exc_info=True)
        return counts

    @api.model
    def _chase_cert_one(self, doc, today, mgr_days, counts):
        """Every reminder one certificate owes today, and no more. Nothing
        after its day (the renewal course's own chase takes over) and
        nothing for a certificate a newer one has replaced."""
        if doc.renewed_by_id or not doc.expiry_date:
            return
        left = (doc.expiry_date - today).days
        if left < 0:
            return
        sent = doc._pb_sent()
        counts.setdefault('certificates', 0)
        # ---- the person: one band at a time --------------------------------
        for key, top, bottom in CERT_BANDS:
            if bottom <= left <= top:
                if key not in sent and doc._pb_training_mail(
                        'pb_training.mail_template_certificate_expiring',
                        doc._pb_their_email()):
                    doc._pb_mark_sent(key, today)
                    counts['certificates'] += 1
                break
        # ---- their manager ---------------------------------------------------
        if left <= mgr_days and 'xm14' not in sent:
            if doc._pb_training_mail(
                    'pb_training.mail_template_certificate_expiring_manager',
                    doc._pb_manager_email()):
                doc._pb_mark_sent('xm14', today)
                counts['certificates'] += 1
        # ---- the HR lead, on the day -----------------------------------------
        if left == 0 and 'xh0' not in sent:
            if doc._pb_training_mail(
                    'pb_training.mail_template_certificate_expired_hr',
                    self._hr_email(doc.company_id or doc.employee_id.company_id)):
                doc._pb_mark_sent('xh0', today)
                counts['certificates'] += 1

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
