# -*- coding: utf-8 -*-
"""LEARNING L3 — learning paths.

A PATH is an ordered set of courses with a purpose (a role, a career move, a
skill) that a person is put on as ONE thing. Three tables:

  * `pb.training.path`             the path: name, purpose, blurb, who gets it
                                   on day one, how long the whole thing takes;
  * `pb.training.path.step`        one step = one course (kinds for sessions,
                                   sign-offs and outside courses are reserved
                                   for L4/L5). A step may be a GATE: the steps
                                   after it wait until it is finished;
  * `pb.training.path.enrolment`   one person on one path.

THE STEPS ARE ORDINARY ASSIGNMENTS. Enrolling somebody does not invent a
second way of being on a course: each step that may open is put on the person
through the existing assignment engine (`assign_many(..., extra=…)`), linked
back with `path_enrolment_id` / `path_step_id`. So reminders, more time, the
trial-period link, the Numbers and certificates all work unchanged — the path
only decides WHEN each step opens.

ONE OPEN ASSIGNMENT PER PERSON PER COURSE STILL HOLDS (safety rail 2): a step
whose course the person is already doing outside the path ADOPTS that
assignment instead of making a second one.

THE ENROLMENT'S STATE IS STORED AND WRITTEN BY ONE METHOD, `_refresh()`, which
the daily job, the assignment's own `_refresh_one` (when it carries a path
link) and the path page call — the same rule the assignment keeps.

QUIETSTEPS CONTRACT (the station line): every enrolled person is at exactly
ONE station — the first unfinished step, or "Finished" — so the counts add up.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .training_common import (
    ASSIGN_OPEN, ASSIGN_REASONS, P_DEFAULT_DUE, as_id, fold, leg, number, tr,
)

_logger = logging.getLogger(__name__)

PATH_PURPOSES = [
    ('role', 'For a role'),
    ('career', 'For a career move'),
    ('skills', 'For a skill'),
]
PATH_PURPOSE_LABEL = dict(PATH_PURPOSES)

#: What a step is. Only `course` exists in L3; the other kinds are reserved
#: (L4 sessions and sign-offs, L5 outside courses) and refused by the step
#: constraint until those phases ship.
STEP_KINDS = [
    ('course', 'A course'),
]

ENROL_STATES = [
    ('not_started', 'Not started'),
    ('in_progress', 'Under way'),
    ('overdue', 'Late'),
    ('done', 'Finished'),
    ('cancelled', 'Taken off the path'),
]
ENROL_STATE_LABEL = dict(ENROL_STATES)
ENROL_OPEN = ('not_started', 'in_progress', 'overdue')

#: Context key: set while a path opens its own steps, so the assignment's
#: refresh hook does not call back into the enrolment it is being made for.
NO_PATH_HOOK = 'pb_training_no_path_hook'


class PbTrainingPath(models.Model):
    _name = 'pb.training.path'
    _description = 'Learning path'
    _order = 'name, id'

    name = fields.Char(string='What it is called', required=True,
                       translate=True)
    purpose = fields.Selection(PATH_PURPOSES, string='What it is for',
                               required=True, default='role')
    blurb = fields.Text(string='In one sentence', translate=True,
                        help='Shown on the path card and to the learner.')
    step_ids = fields.One2many('pb.training.path.step', 'path_id',
                               string='Steps', copy=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    due_days = fields.Integer(
        string='Days for the whole path', default=90,
        help='Counted from the day a person is put on it. Each step is due '
             'by its own date, never later than this.')
    counts_for_probation = fields.Boolean(
        string='Their trial period waits for it',
        help='Every step is put on the person with the trial-period link.')
    day_one = fields.Boolean(
        string='Give it on day one',
        help='New joiners in these departments or jobs are put on the path by '
             'the joining checklist (while day-one training is switched on).')
    department_ids = fields.Many2many(
        'hr.department', 'pb_training_path_dept_rel', 'path_id', 'dept_id',
        string='Day one for these departments',
        help='These departments and every department under them.')
    job_ids = fields.Many2many(
        'hr.job', 'pb_training_path_job_rel', 'path_id', 'job_id',
        string='Day one for these jobs')
    enrolment_ids = fields.One2many('pb.training.path.enrolment', 'path_id',
                                    string='People on it')

    steps_count = fields.Integer(string='Steps', compute='_compute_counts')
    people_count = fields.Integer(string='People on it',
                                  compute='_compute_counts')
    done_count = fields.Integer(string='Finished', compute='_compute_counts')

    @api.depends('step_ids', 'enrolment_ids.state')
    def _compute_counts(self):
        for rec in self:
            enrol = rec.enrolment_ids.filtered(lambda e: e.state != 'cancelled')
            rec.steps_count = len(rec.step_ids)
            rec.people_count = len(enrol)
            rec.done_count = len(enrol.filtered(lambda e: e.state == 'done'))

    @api.constrains('name', 'company_id')
    def _check_name(self):
        for rec in self:
            name = fold(rec.name or '').strip()
            if not name:
                continue
            others = self.with_context(active_test=False).search([
                ('id', '!=', rec.id), ('company_id', '=', rec.company_id.id)])
            if any(fold(o.name or '').strip() == name for o in others):
                raise ValidationError(_(
                    "There is already a path called %s in this company. Give "
                    "this one another name.", rec.name))

    @api.constrains('due_days')
    def _check_due(self):
        for rec in self:
            if rec.due_days < 0:
                raise ValidationError(_("These numbers cannot be below zero."))

    # ------------------------------------------------------------ helpers
    def _ordered_steps(self):
        self.ensure_one()
        return self.step_ids.sorted(lambda s: (s.sequence, s.id))

    def _matches(self, emp):
        """Is this day-one path about this joiner? A department means it and
        everything under it (the rule precedent, schedule.py `_matches`); an
        empty audience means everybody in the company."""
        self.ensure_one()
        if self.department_ids:
            covered = self.env['hr.department'].sudo().search(
                [('id', 'child_of', self.department_ids.ids)])
            dept_ok = emp.department_id in covered
        else:
            dept_ok = None
        job_ok = (emp.job_id in self.job_ids) if self.job_ids else None
        if dept_ok is None and job_ok is None:
            return True
        return bool(dept_ok) or bool(job_ok)

    @api.model
    def _for_employee(self, employee):
        """Every live day-one path that is about this person (as the system:
        the joining checklist runs as whoever ticked the step)."""
        if not employee:
            return self.browse()
        emp = employee.sudo()
        paths = self.sudo().search([
            ('active', '=', True), ('day_one', '=', True),
            ('company_id', '=', (emp.company_id or self.env.company).id)])
        return paths.filtered(lambda p: p.step_ids and p._matches(emp))

    def _purpose_word(self, env=None):
        self.ensure_one()
        return tr(env or self.env, PATH_PURPOSE_LABEL.get(self.purpose, ''))

    def _audience_words(self):
        """"Given on day one to Agronomists, Agronomy" — or ''."""
        self.ensure_one()
        if not self.day_one:
            return ''
        bits = self.job_ids.sudo().mapped('name') \
            + self.department_ids.sudo().mapped('name')
        if not bits:
            return self.env._("Given on day one to everybody in the company")
        return self.env._("Given on day one to %s", ', '.join(bits))

    def _stations(self, enrolments=None):
        """The station line: one station per step plus "Finished", each with
        how many people are at it right now and how many of them are late.
        Every open or finished enrolment is at EXACTLY one station."""
        self.ensure_one()
        steps = self._ordered_steps()
        if enrolments is None:
            enrolments = self.enrolment_ids
        live = enrolments.filtered(lambda e: e.state != 'cancelled')
        at = {s.id: [] for s in steps}
        done = []
        for enr in live:
            if enr.state == 'done':
                done.append(enr)
                continue
            key = enr.current_step_id.id if enr.current_step_id.id in at \
                else (steps[:1].id if steps else 0)
            if key:
                at[key].append(enr)
        out = []
        for i, step in enumerate(steps):
            rows = at.get(step.id, [])
            late = len([e for e in rows if e.state == 'overdue'])
            out.append({
                'key': str(step.id), 'step_id': step.id,
                'n': '%02d' % (i + 1),
                'title': step.channel_id.sudo().name or '',
                'count': len(rows),
                'late': late,
                'gate': bool(step.gate),
            })
        out.append({
            'key': 'done', 'step_id': 0,
            'n': '%02d' % (len(steps) + 1),
            'title': '', 'count': len(done), 'late': 0, 'gate': False,
        })
        return out


class PbTrainingPathStep(models.Model):
    _name = 'pb.training.path.step'
    _description = 'Learning path step'
    _order = 'sequence, id'

    path_id = fields.Many2one('pb.training.path', string='Path',
                              required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(STEP_KINDS, string='Kind', required=True,
                            default='course')
    channel_id = fields.Many2one('slide.channel', string='Course', index=True,
                                 ondelete='cascade')
    gate = fields.Boolean(
        string='Later steps wait for this one',
        help='The steps after this one open only when it is finished.')
    due_days = fields.Integer(
        string='Days for this step',
        help='Counted from the day the step opens. Empty = the usual number '
             'of days for a course.')
    name = fields.Char(related='channel_id.name', string='Course name',
                       readonly=True)
    hours = fields.Float(string='Hours', compute='_compute_hours',
                         digits=(6, 2))
    company_id = fields.Many2one(related='path_id.company_id', store=True,
                                 index=True, readonly=True)

    @api.depends('channel_id')
    def _compute_hours(self):
        for rec in self:
            rec.hours = rec.channel_id._pb_hours() if rec.channel_id else 0.0

    @api.constrains('kind', 'channel_id', 'due_days')
    def _check_step(self):
        for rec in self:
            if rec.kind == 'course' and not rec.channel_id:
                raise ValidationError(_("Every step needs a course."))
            if rec.due_days < 0:
                raise ValidationError(_("These numbers cannot be below zero."))


class PbTrainingPathEnrolment(models.Model):
    _name = 'pb.training.path.enrolment'
    _description = 'Person on a learning path'
    _inherit = ['mail.thread']
    _order = 'started_on desc, id desc'

    path_id = fields.Many2one('pb.training.path', string='Path',
                              required=True, index=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Who', required=True,
                                  index=True, ondelete='cascade')
    partner_id = fields.Many2one(
        'res.partner', string='Their contact', index=True,
        compute='_compute_partner', store=True, readonly=True)
    reason = fields.Selection(ASSIGN_REASONS, string='Why', required=True,
                              default='adhoc')
    started_on = fields.Date(string='Put on it', readonly=True,
                             default=fields.Date.context_today)
    due_date = fields.Date(string='Whole path due by')
    state = fields.Selection(ENROL_STATES, string='Where they are',
                             index=True, readonly=True, copy=False,
                             tracking=True)
    current_step_id = fields.Many2one(
        'pb.training.path.step', string='Step they are on', readonly=True,
        ondelete='set null')
    percent = fields.Integer(string='Steps finished (%)', readonly=True)
    completed_on = fields.Date(string='Finished on', readonly=True,
                               copy=False)
    assignment_ids = fields.One2many('pb.training.assignment',
                                     'path_enrolment_id',
                                     string='Step assignments')
    assigned_by_id = fields.Many2one('res.users', string='Put on it by',
                                     readonly=True,
                                     default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True,
                                 default=lambda self: self.env.company)

    state_words = fields.Char(string='Where they stand',
                              compute='_compute_words')
    where_words = fields.Char(string='Where they are',
                              compute='_compute_words')

    @api.depends('employee_id')
    def _compute_partner(self):
        for rec in self:
            emp = rec.employee_id.sudo()
            rec.partner_id = emp.user_id.partner_id.id if emp.user_id \
                else False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.employee_id.sudo().name or _('Somebody'),
                rec.path_id.sudo().name or _('a path'))

    @api.depends('state', 'current_step_id', 'path_id.step_ids')
    def _compute_words(self):
        for rec in self:
            rec.state_words = tr(self.env, ENROL_STATE_LABEL.get(
                rec.state or 'not_started', ''))
            rec.where_words = rec._where_words()

    def _where_words(self, env=None):
        """"At step 2 of 4: Pesticide handling" — the whole sentence (R117)."""
        self.ensure_one()
        env = env or self.env
        steps = self.path_id.sudo()._ordered_steps()
        total = len(steps)
        if self.state == 'cancelled':
            return tr(env, 'Taken off the path')
        if self.state == 'done':
            return tr(env, 'Finished all %s steps', total) if total != 1 \
                else tr(env, 'Finished the one step')
        step = self.current_step_id
        if not step or step not in steps:
            step = steps[:1]
        if not step:
            return ''
        index = list(steps.ids).index(step.id) + 1
        return tr(env, 'At step %s of %s: %s', index, total,
                  step.channel_id.sudo().name or '')

    # =====================================================================
    #  the rules
    # =====================================================================
    def _guard_one_open_path(self):
        """One open enrolment per person per path."""
        self.ensure_one()
        clash = self.sudo().search_count([
            ('id', '!=', self.id), ('path_id', '=', self.path_id.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ENROL_OPEN)])
        if clash:
            raise UserError(_(
                "%(who)s is already on %(path)s.",
                who=self.employee_id.sudo().name or '',
                path=self.path_id.sudo().name or ''))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('state', 'not_started')
            if not vals.get('company_id') and vals.get('employee_id'):
                emp = self.env['hr.employee'].sudo().browse(
                    vals['employee_id'])
                vals['company_id'] = (emp.company_id or self.env.company).id
        records = super().create(vals_list)
        for rec in records:
            rec._guard_one_open_path()
        return records

    # =====================================================================
    #  enrolling
    # =====================================================================
    @api.model
    def enrol_many(self, path_id, employee_ids, reason='adhoc',
                   due_date=None):
        """Put people on a path. Trainers and training managers only; the
        work itself is done as the system (the steps are assignments, which
        the trainer may create anyway)."""
        self.env['pb.training']._require_write()
        return self.sudo()._enrol_people(
            path_id, employee_ids, reason, due_date,
            by_user=self.env.user, companies=self.env.companies)

    @api.model
    def _enrol_people(self, path_id, employee_ids, reason='adhoc',
                      due_date=None, by_user=None, companies=None):
        """The engine. FOUR OUTCOMES, all reported (the `assign_many`
        rule): put on, already on it, no login, could not be done."""
        path = self.env['pb.training.path'].sudo().browse(
            as_id(path_id)).exists()
        if not path:
            raise UserError(_("That path is not here any more."))
        if not path.step_ids:
            raise UserError(_("Add at least one course to the path first."))
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        if not ids:
            raise UserError(_("Pick at least one person."))
        domain = [('id', 'in', ids)]
        if companies is not None:
            domain.append(('company_id', 'in', companies.ids))
        rows = self.env['hr.employee'].sudo().search(domain)
        today = fields.Date.today()
        if due_date:
            due = fields.Date.to_date(due_date)
        else:
            due = today + timedelta(days=max(path.due_days or 0, 1))
        made, already, no_login, failed = [], [], [], []
        for emp in rows:
            if not emp.user_id or not emp.user_id.partner_id:
                no_login.append(emp.name or '')
                continue
            if self.search_count([('path_id', '=', path.id),
                                  ('employee_id', '=', emp.id),
                                  ('state', 'in', ENROL_OPEN)]):
                already.append(emp.name or '')
                continue
            try:
                with self.env.cr.savepoint():
                    enr = self.create({
                        'path_id': path.id,
                        'employee_id': emp.id,
                        'reason': reason or 'adhoc',
                        'due_date': due,
                        'started_on': today,
                        'assigned_by_id': (by_user or self.env.user).id,
                        'company_id': (emp.company_id or path.company_id).id,
                    })
                    enr._refresh(today)
                    enr.message_post(body=_(
                        "Put on %(path)s by %(who)s.", path=path.name,
                        who=(by_user or self.env.user).name or ''))
                made.append(enr.id)
            except Exception:           # noqa: BLE001 — one person, one grave
                _logger.warning('pb_training: %s could not be put on path %s',
                                emp.id, path.id, exc_info=True)
                failed.append(emp.name or '')
        return {
            'made': made, 'already': already, 'no_login': no_login,
            'failed': failed,
            'message': self._enrol_sentence(path, made, already, no_login,
                                            failed),
        }

    @api.model
    def _enrol_sentence(self, path, made, already, no_login, failed):
        bits = []
        if len(made) == 1:
            bits.append(_("1 person is now on %s.", path.name or ''))
        elif made:
            bits.append(_("%(n)s people are now on %(path)s.", n=len(made),
                          path=path.name or ''))
        else:
            bits.append(_("Nobody new was put on the path."))
        if already:
            bits.append(_("%s was already on it.", ', '.join(already[:5]))
                        if len(already) == 1
                        else _("%s were already on it.",
                               ', '.join(already[:5])))
        if no_login:
            bits.append(_("%s has no login yet, so there is nowhere for the "
                          "courses to appear.", ', '.join(no_login[:5]))
                        if len(no_login) == 1
                        else _("%s have no login yet, so there is nowhere for "
                               "the courses to appear.",
                               ', '.join(no_login[:5])))
        if failed:
            bits.append(_("%s could not be put on — tell the training team.",
                          ', '.join(failed[:5])))
        return ' '.join(bits)

    # =====================================================================
    #  opening the steps
    # =====================================================================
    def _step_rows(self):
        """{step_id: assignment} — the assignment that stands for each step:
        the one linked to it (newest first), else the person's open
        assignment on that course (a step shared with another path)."""
        self.ensure_one()
        out = {}
        linked = self.assignment_ids.sudo().sorted(lambda a: -a.id)
        for row in linked:
            if row.path_step_id and row.path_step_id.id not in out:
                out[row.path_step_id.id] = row
        missing = [s for s in self.path_id.sudo().step_ids
                   if s.id not in out and s.channel_id]
        if missing:
            open_rows = self.env['pb.training.assignment'].sudo().search([
                ('employee_id', '=', self.employee_id.id),
                ('channel_id', 'in', [s.channel_id.id for s in missing]),
                ('state', 'in', ASSIGN_OPEN)])
            by_channel = {r.channel_id.id: r for r in open_rows}
            for step in missing:
                if step.channel_id.id in by_channel:
                    out[step.id] = by_channel[step.channel_id.id]
        return out

    def _step_due(self, step, today):
        self.ensure_one()
        days = step.due_days or number(self.env, P_DEFAULT_DUE, 14)
        due = today + timedelta(days=max(days, 1))
        if self.due_date:
            due = min(due, max(self.due_date, today))
        return due

    def _open_step(self, step, today):
        """Put one step on the person, or adopt the assignment they already
        have on that course. Returns the assignment, or an empty recordset."""
        self.ensure_one()
        Assignment = self.env['pb.training.assignment'].sudo().with_context(
            **{NO_PATH_HOOK: True})
        channel = step.channel_id.sudo()
        emp = self.employee_id.sudo()
        if not channel or not channel.active:
            return Assignment.browse()
        links = {'path_enrolment_id': self.id, 'path_step_id': step.id}
        open_row = Assignment.search([
            ('channel_id', '=', channel.id), ('employee_id', '=', emp.id),
            ('state', 'in', ASSIGN_OPEN)], limit=1)
        if open_row:
            # ADOPTION (safety rail 2): never a second open assignment.
            if not open_row.path_enrolment_id:
                open_row.write(links)
            return open_row
        company = emp.company_id or self.company_id
        res = Assignment.with_context(
            allowed_company_ids=[company.id]).assign_many(
            channel.id, [emp.id], self.reason or 'adhoc',
            self._step_due(step, today),
            True if self.path_id.counts_for_probation else None,
            extra=links)
        if res.get('made'):
            return Assignment.browse(res['made'][0])
        return Assignment.browse()

    def _open_steps(self, today=None):
        """Walk the steps in order; open every step not yet opened until a
        GATE that is not finished. A step that cannot be opened (no login,
        an archived course) stops the walk too — nothing jumps the queue."""
        today = today or fields.Date.today()
        for enr in self.filtered(lambda e: e.state in ENROL_OPEN):
            rows = enr._step_rows()
            for step in enr.path_id.sudo()._ordered_steps():
                row = rows.get(step.id)
                if row and not row.path_enrolment_id:
                    # ADOPTION: the person's own open assignment on this
                    # course becomes the step (safety rail 2).
                    row.with_context(**{NO_PATH_HOOK: True}).sudo().write(
                        {'path_enrolment_id': enr.id,
                         'path_step_id': step.id})
                if not row:
                    row = enr._open_step(step, today)
                    if not row:
                        break
                if step.gate and row.state != 'done':
                    break
        return True

    # =====================================================================
    #  bringing it up to date
    # =====================================================================
    def _refresh(self, today=None):
        today = today or fields.Date.today()
        for rec in self:
            try:
                with self.env.cr.savepoint():
                    rec._refresh_one(today)
            except Exception:           # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: path enrolment %s could not be '
                                'brought up to date', rec.id, exc_info=True)
        return True

    def _refresh_one(self, today=None):
        self.ensure_one()
        today = today or fields.Date.today()
        if self.state not in ENROL_OPEN:
            return self.state
        self._open_steps(today)
        steps = self.path_id.sudo()._ordered_steps()
        rows = self._step_rows()
        done = [s for s in steps if rows.get(s.id) and
                rows[s.id].state == 'done']
        current = next((s for s in steps if s not in done), None)
        percent = int(round(100.0 * len(done) / len(steps))) if steps else 0
        linked = [rows[s.id] for s in steps if rows.get(s.id)]
        if steps and len(done) == len(steps):
            state = 'done'
        elif any(r.state == 'overdue' for r in linked) or (
                self.due_date and self.due_date < today):
            state = 'overdue'
        elif done or any(r.state in ('in_progress', 'excused')
                         for r in linked):
            state = 'in_progress'
        else:
            state = 'not_started'
        vals = {}
        if state != self.state:
            vals['state'] = state
        if percent != self.percent:
            vals['percent'] = percent
        cur_id = current.id if current else False
        if cur_id != self.current_step_id.id:
            vals['current_step_id'] = cur_id
        if state == 'done' and not self.completed_on:
            vals['completed_on'] = today
        if vals:
            self.sudo().with_context(tracking_disable=True,
                                     mail_notrack=True).write(vals)
            if vals.get('state') == 'done':
                leg(self.env, 'path finished note', lambda: self.message_post(
                    body=_("Finished every step of %s.",
                           self.path_id.sudo().name or '')))
        return state

    # =====================================================================
    #  taking somebody off
    # =====================================================================
    def unenrol(self):
        """Cancel the enrolment and remove ONLY the step assignments nobody
        has started. A started or finished one stays (safety rail 3) — as an
        ordinary assignment — and no certificate is ever touched."""
        removed = kept = 0
        for rec in self.sudo():
            if rec.state == 'cancelled':
                continue
            for row in rec.assignment_ids:
                if row.state == 'done':
                    continue
                started = row.state != 'assigned' or row._progress().get(
                    'done')
                if started:
                    row.with_context(**{NO_PATH_HOOK: True}).write(
                        {'path_enrolment_id': False, 'path_step_id': False})
                    kept += 1
                else:
                    row.unlink()
                    removed += 1
            rec.with_context(tracking_disable=True).write(
                {'state': 'cancelled'})
            rec.message_post(body=_(
                "Taken off %(path)s by %(who)s.",
                path=rec.path_id.name or '', who=self.env.user.name or ''))
        return {'removed': removed, 'kept': kept}

    # =====================================================================
    #  the learner's view of one enrolment
    # =====================================================================
    def _learner_steps(self):
        """[{name, state: done|now|next|waits, channel_id, assignment_id,
        after}] — the dot rail on My learning and the portal."""
        self.ensure_one()
        steps = self.path_id.sudo()._ordered_steps()
        rows = self._step_rows()
        out = []
        current = self.current_step_id
        gate_name = ''
        for step in steps:
            row = rows.get(step.id)
            name = step.channel_id.sudo().name or ''
            if row and row.state == 'done':
                state = 'done'
            elif row and step == current:
                state = 'now'
            elif row:
                state = 'next'
            else:
                state = 'waits'
            out.append({
                'id': step.id, 'name': name, 'state': state,
                'gate': bool(step.gate),
                'channel_id': step.channel_id.id if row else 0,
                'assignment_id': row.id if row else 0,
                'after': gate_name if state == 'waits' else '',
            })
            if step.gate and not (row and row.state == 'done') \
                    and not gate_name:
                gate_name = name
        return out


class PbTrainingAssignmentPath(models.Model):
    """Which path (and which step of it) put somebody on a course."""
    _inherit = 'pb.training.assignment'

    path_enrolment_id = fields.Many2one(
        'pb.training.path.enrolment', string='From the learning path',
        index=True, ondelete='set null', readonly=True)
    path_step_id = fields.Many2one(
        'pb.training.path.step', string='Path step', index=True,
        ondelete='set null', readonly=True)

    def _refresh_one(self, today=None):
        state = super()._refresh_one(today)
        if self.path_enrolment_id and not self.env.context.get(NO_PATH_HOOK):
            enrolment = self.path_enrolment_id.sudo().with_context(
                **{NO_PATH_HOOK: True})
            leg(self.env, 'learning path follow',
                lambda: enrolment._refresh_one(today))
        return state

    def _step_words(self):
        """"Step 2 of 4 · DEMO New agronomist" — or ''."""
        self.ensure_one()
        step = self.path_step_id.sudo()
        if not step or not self.path_enrolment_id:
            return ''
        steps = step.path_id._ordered_steps()
        if step not in steps:
            return ''
        return self.env._('Step %(n)s of %(total)s · %(path)s',
                          n=list(steps.ids).index(step.id) + 1,
                          total=len(steps), path=step.path_id.name or '')

    def _payload(self, today=None):
        data = super()._payload(today)
        try:
            data['path_name'] = self.path_enrolment_id.sudo().path_id.name \
                or ''
            data['step_words'] = self._step_words()
        except Exception:               # noqa: BLE001 — a word is not fatal
            data['path_name'] = ''
            data['step_words'] = ''
        return data
