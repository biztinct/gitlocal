# -*- coding: utf-8 -*-
"""One running journey for one person.

THE ONE RULE THIS FILE EXISTS TO ENFORCE: a template is read ONCE, when the
journey opens. From that moment the tasks are the truth — their dates, their
owners and their wording are the case's own. Editing the checklist next month
does not move a date somebody already worked to, and re-opening a case does not
quietly re-plan it.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .lifecycle_common import (
    CASE_STATES, CASE_TYPE_LABEL, CASE_TYPES,
)

_logger = logging.getLogger(__name__)

#: Where an unresolvable role falls back to, in order. Never a dead end: an
#: unassigned task is a task nobody is reminded about.
_ROLE_PARAMS = {
    'hr': 'pb_lifecycle.hr_user_id',
    'it': 'pb_lifecycle.it_user_id',
    'finance': 'pb_lifecycle.finance_user_id',
    'admin': 'pb_lifecycle.admin_user_id',
}

#: Fields P3 will add to `hr.employee` for the two roles this phase cannot
#: answer. PROBED rather than declared, so the day they exist every template
#: that already says "HRBP" resolves to one without a line changing here.
_ROLE_EMPLOYEE_FIELDS = {
    'hrbp': ('hrbp_user_id', 'hrbp_id'),
    'buddy': ('buddy_user_id', 'buddy_id'),
}


class PbJourneyCase(models.Model):
    _name = 'pb.journey.case'
    _description = 'Employee Journey'
    # `mail.activity.mixin` as well as `mail.thread`, and it is load-bearing:
    # `activity_schedule()` lives on the ACTIVITY mixin, not on the thread one,
    # and the daily reminder raises its one to-do per due step through it. With
    # only `mail.thread` the call fails with AttributeError — contained by the
    # per-record try/except, so the job carries on and the nudges silently never
    # happen. Caught on 2026-08-31.
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'anchor_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Journey')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    case_type = fields.Selection(
        CASE_TYPES, string='Journey type', required=True, default='onboarding',
        tracking=True)
    template_id = fields.Many2one(
        'pb.journey.template', string='Checklist used', ondelete='set null')
    anchor_date = fields.Date(
        string='Key date', tracking=True,
        help='The joining date, the last working day or the probation end — '
             'whichever this journey counts its steps from.')
    state = fields.Selection(
        CASE_STATES, string='Status', default='draft', required=True,
        tracking=True)
    source = fields.Selection(
        [('manual', 'Manual'), ('zoho', 'Connected system'),
         ('portal', 'Portal')],
        string='Started by', default='manual', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    task_ids = fields.One2many('pb.journey.task', 'case_id', string='Steps')
    checkin_ids = fields.One2many(
        'pb.employee.checkin', 'case_id', string='Check-ins')
    letter_ids = fields.One2many('pb.hr.letter', 'case_id', string='Letters')
    progress = fields.Integer(
        compute='_compute_progress', store=True, string='Done (%)')
    task_count = fields.Integer(compute='_compute_progress', store=True,
                                string='Steps')
    open_task_count = fields.Integer(
        compute='_compute_counts', string='Still to do')
    overdue_task_count = fields.Integer(
        compute='_compute_counts', string='Overdue')
    red_flag_count = fields.Integer(
        compute='_compute_counts', string='Red flags')
    next_due_date = fields.Date(compute='_compute_counts', string='Next due')
    date_opened = fields.Date(string='Opened on', readonly=True)
    date_closed = fields.Date(string='Closed on', readonly=True)
    note = fields.Text(string='Notes')

    # ------------------------------------------------------------- computes
    @api.depends('employee_id', 'case_type')
    def _compute_name(self):
        for rec in self:
            label = CASE_TYPE_LABEL.get(rec.case_type, rec.case_type or '')
            rec.name = '%s — %s' % (rec.employee_id.name or _('Employee'),
                                    label)

    def _compute_display_name(self):
        # Odoo 19 has no `name_get`; a friendly title is this override.
        for rec in self:
            rec.display_name = rec.name or _('Journey')

    @api.depends('task_ids.state')
    def _compute_progress(self):
        for rec in self:
            tasks = rec.task_ids
            total = len(tasks)
            settled = len(tasks.filtered(
                lambda t: t.state in ('done', 'skipped')))
            rec.task_count = total
            rec.progress = int(round(settled * 100.0 / total)) if total else 0

    @api.depends('task_ids.state', 'task_ids.due_date',
                 'checkin_ids.red_flag', 'checkin_ids.state')
    def _compute_counts(self):
        today = fields.Date.today()
        for rec in self:
            open_tasks = rec.task_ids.filtered(
                lambda t: t.state in ('pending', 'in_progress', 'blocked'))
            rec.open_task_count = len(open_tasks)
            rec.overdue_task_count = len(open_tasks.filtered(
                lambda t: t.due_date and t.due_date < today))
            due = sorted(t.due_date for t in open_tasks if t.due_date)
            rec.next_due_date = due[0] if due else False
            rec.red_flag_count = len(rec.checkin_ids.filtered(
                lambda c: c.red_flag and c.state != 'cancelled'))

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.company_id:
            self.company_id = self.employee_id.company_id

    @api.onchange('case_type', 'employee_id')
    def _onchange_pick_template(self):
        if self.case_type and not self.template_id:
            self.template_id = self.env['pb.journey.template'].pick_for(
                self.case_type,
                country_id=self._employee_country(self.employee_id),
                company_id=(self.company_id or self.env.company).id)

    # --------------------------------------------------------------- anchors
    @staticmethod
    def _employee_country(employee):
        if not employee:
            return False
        country = getattr(employee, 'country_id', False)
        addr = getattr(employee, 'address_id', False)
        if addr and getattr(addr, 'country_id', False):
            return addr.country_id.id
        return country.id if country else False

    def _joining_date(self):
        """The joining date this journey counts from.

        THE TYPED DATE WINS. Whoever opened the journey put a key date on it,
        and they know something the record does not — a re-hire, a transfer, a
        start that has not been contracted yet. Deriving it from the person's
        oldest contract instead would silently plan a new joiner's laptop for
        the day they joined three years ago, and the screen would give no hint
        why. The contract is the FALLBACK, for the case opened with nothing but
        a name.
        """
        self.ensure_one()
        if self.anchor_date:
            return self.anchor_date
        emp = self.employee_id
        d = getattr(emp, 'first_contract_date', False)
        if not d:
            starts = [c.date_start for c in getattr(emp, 'contract_ids', [])
                      if getattr(c, 'date_start', False)]
            d = min(starts) if starts else False
        return d or fields.Date.today()

    def _anchor_base(self, anchor):
        self.ensure_one()
        today = fields.Date.today()
        if anchor == 'doj':
            return self._joining_date()
        if anchor in ('lwd', 'probation_end'):
            return self.anchor_date or today
        return today

    # ------------------------------------------------------- who owns a step
    def _users_in_group(self, group_xmlid, company=None, limit=1):
        """Members of a group — INCLUDING the ones who hold it by implication.

        `res.users.group_ids` holds DIRECT memberships only, so a search on it
        misses every administrator who has the manager tier through the ladder
        rather than by name — which on this module is most of them, since
        `group_lifecycle_admin` implies `group_lifecycle_manager`. Odoo 19's
        `res.groups.all_user_ids` is the transitive set and is what this reads;
        the direct search stays as a fallback for a build that lacks the field.

        Own company first, because a nudge is more useful from someone who can
        act on it.
        """
        grp = self.env.ref(group_xmlid, raise_if_not_found=False)
        Users = self.env['res.users']
        if not grp:
            return Users.browse()
        grp = grp.sudo()
        if 'all_user_ids' in grp._fields:
            members = grp.all_user_ids
        else:
            members = Users.sudo().search([('group_ids', 'in', grp.id)])
        members = members.filtered(lambda u: u.active)
        if company:
            same = members.filtered(lambda u: company.id in u.company_ids.ids)
            if same:
                return same[:limit] if limit else same
        return members[:limit] if limit else members

    def _resolve_assignee(self, rule, employee):
        """A role becomes a person, ONCE, when the journey opens.

        Returns an empty recordset for `candidate` — that step is answered
        through a link, by someone who has no login at all — and for any role
        this database genuinely cannot answer. The caller decides what an
        unanswered role falls back to, and says so in the case log.
        """
        self.ensure_one()
        Users = self.env['res.users']
        company = self.company_id or employee.company_id or self.env.company

        if rule == 'candidate':
            return Users.browse()
        if rule == 'employee':
            return employee.user_id or Users.browse()
        if rule == 'manager':
            mgr = employee.parent_id
            return (mgr.user_id if mgr else Users.browse()) or Users.browse()
        if rule in _ROLE_EMPLOYEE_FIELDS:
            # P3's fields, picked up the day they exist (never edited in here).
            for fname in _ROLE_EMPLOYEE_FIELDS[rule]:
                if fname in employee._fields:
                    val = employee[fname]
                    if val and val._name == 'res.users':
                        return val[:1]
                    if val and 'user_id' in val._fields and val.user_id:
                        return val.user_id[:1]
            return Users.browse()
        if rule in _ROLE_PARAMS:
            raw = self.env['ir.config_parameter'].sudo().get_param(
                _ROLE_PARAMS[rule])
            if raw:
                try:
                    user = Users.sudo().browse(int(raw)).exists()
                    if user:
                        return user
                except (TypeError, ValueError):
                    _logger.warning('pb_lifecycle: %s is not a user id',
                                    _ROLE_PARAMS[rule])
            return self._users_in_group('pb_lifecycle.group_lifecycle_manager',
                                        company)
        return Users.browse()

    # ---------------------------------------------------------- the lifecycle
    def action_open(self):
        """Draft → running: turn the checklist into dated, owned steps."""
        for rec in self:
            if rec.state not in ('draft',):
                raise UserError(_(
                    "This journey is already running — it cannot be started "
                    "twice."))
            rec._generate_tasks()
            rec.write({'state': 'active',
                       'date_opened': fields.Date.today()})
            rec.message_post(body=_(
                "Journey started with %(count)s step(s).",
                count=len(rec.task_ids)))
        return True

    def _generate_tasks(self):
        self.ensure_one()
        template = self.template_id
        if not template:
            return self.env['pb.journey.task'].browse()
        Task = self.env['pb.journey.task']
        emp = self.employee_id
        fallback = self.create_uid or self.env.user
        unresolved = []
        vals_list = []
        for step in template.step_ids:
            if step.assignee_rule == 'user':
                user = step.assignee_user_id
            else:
                user = self._resolve_assignee(step.assignee_rule, emp)
            if not user and step.assignee_rule != 'candidate':
                user = fallback
                unresolved.append(step.name)
            base = self._anchor_base(step.anchor)
            vals_list.append({
                'case_id': self.id,
                'step_id': step.id,
                'sequence': step.sequence,
                'name': step.name,
                'description': step.description,
                'assignee_rule': step.assignee_rule,
                'assignee_user_id': user.id if user else False,
                'due_date': base + timedelta(days=step.offset_days or 0),
                'step_kind': step.step_kind,
                'blocking_ff': step.blocking_ff,
                'escalation_days': step.escalation_days or 3,
                'form_questions_json': step.form_questions_json,
                'mail_template_id': step.mail_template_id.id or False,
                'letter_template_id': step.letter_template_id.id or False,
                'company_id': (self.company_id or self.env.company).id,
            })
        tasks = Task.create(vals_list) if vals_list else Task.browse()
        if unresolved:
            self.message_post(body=_(
                "No owner could be worked out for %(steps)s, so they were "
                "given to %(who)s. Change the owner on the step if that is "
                "not right.",
                steps=', '.join(unresolved), who=fallback.name))
        return tasks

    def action_done(self):
        for rec in self:
            rec.write({'state': 'done', 'date_closed': fields.Date.today()})
            rec.message_post(body=_("Journey marked finished."))
        return True

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled',
                       'date_closed': fields.Date.today()})
            rec.message_post(body=_("Journey cancelled."))
        return True

    def action_hold(self):
        for rec in self:
            rec.state = 'on_hold'
            rec.message_post(body=_("Journey put on hold."))
        return True

    def action_resume(self):
        for rec in self:
            rec.state = 'active'
            rec.message_post(body=_("Journey resumed."))
        return True

    def action_back_to_draft(self):
        for rec in self:
            if rec.task_ids:
                raise UserError(_(
                    "This journey already has steps, so it cannot go back to "
                    "draft. Cancel it instead."))
            rec.state = 'draft'
        return True

    # ----------------------------------------------------------- final money
    @api.model
    def blocking_tasks_for(self, employee_id):
        """The steps that must be done before a final settlement is paid.

        P4 reads this; nothing in P0 calls it. It lives here because the fact —
        "this step blocks the money" — is a property of the journey and must
        have exactly one source.
        """
        return self.env['pb.journey.task'].sudo().search([
            ('case_id.employee_id', '=', employee_id),
            ('case_id.state', 'in', ('draft', 'active', 'on_hold')),
            ('blocking_ff', '=', True),
            ('state', 'not in', ('done', 'skipped')),
        ])
