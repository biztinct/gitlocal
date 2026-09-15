# -*- coding: utf-8 -*-
"""`pb.hiring.requisition` — asking for a person, and what happens when the
answer is yes.

THE ONE THING THIS RECORD KNOWS THAT NOBODY ELSE DOES is whether there is any
money for the role. Everything else about a hiring request — the title, the
department, how many, by when — is a form. The budget answer is a READ of the
one budget table the product has (ruling D2), taken at the moment the request
is written and again whenever anybody asks, and it is what decides whether the
Finance approver is asked at all.

THE BUDGET ANSWER IS ALLOWED TO BE "I DO NOT KNOW", and that is the whole
design. A department with no budget rows is not within budget and it is not
over budget: nobody has said. R23 and R88 between them say a number built on a
missing rate or a missing row is a lie rather than an estimate, so the third
answer exists and is shown in those words. No conversion is attempted either:
if the request is priced in a currency the budget rows are not in, the honest
answer is the same one.

FOUR THINGS HAPPEN WHEN THE WHOLE ROUTE SAYS YES, and each of them is in its
own try/except. R104: the first live contract extension built the contract,
filed the letter and then died working out who to email — and reported "the
new contract could not be prepared" about a contract that existed. Paperwork
must never be able to fail an approval.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang

from .hiring_common import (
    BUDGET_STATUS, GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, P_NOTIFY_MAIL,
    P_REFERRAL_AUTO, REQUISITION_STATES, ROLE_TYPES, SENSITIVE_TYPES,
    STEP_KINDS, counted, flag,
)

_logger = logging.getLogger(__name__)


class PbHiringStep(models.Model):
    """What the candidate will actually be put through, written down up front.

    A2 turns these into interview rounds. They are declared here, on the
    request, because the person asking for the role is the person who knows
    whether it needs a written exercise — and because a hiring manager reading
    a request a month later wants to see what was agreed, not what a recruiter
    later decided.
    """
    _name = 'pb.hiring.step'
    _description = 'Hiring stage'
    _order = 'requisition_id, sequence, id'

    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    sequence = fields.Integer(string='Order', default=10)
    name = fields.Char(string='What happens', required=True)
    kind = fields.Selection(STEP_KINDS, string='Kind', default='interview',
                            required=True)
    owner_id = fields.Many2one('res.users', string='Who runs it',
                               domain="[('share', '=', False)]")
    days_expected = fields.Integer(
        string='Days it should take', default=3,
        help='Used to say how long the whole process should take. It is a '
             'plan, not a deadline.')
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Stage')


class PbHiringRequisition(models.Model):
    _name = 'pb.hiring.requisition'
    _description = 'Hiring request'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'id desc'

    #: The ladder the record keeps for itself when no route is published.
    #: Under a published route the shim takes every one of these presses and
    #: the route decides the order (ledger AM84); this table is what the
    #: product does on a database where hiring approvals were never switched
    #: on, and the two must agree on WHO, which is why the manager rung is
    #: `None` and narrowed in `_approval_can` rather than gated on a group.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager_ok'): None,
        ('manager_ok', 'hr_ok'): GROUP_MANAGER,
        ('hr_ok', 'open'): GROUP_MANAGER,
        ('submitted', 'refused'): None,
        ('manager_ok', 'refused'): GROUP_MANAGER,
        ('hr_ok', 'refused'): GROUP_MANAGER,
        ('draft', 'refused'): None,
        # past the route's last rung and always the record's own business
        ('open', 'filled'): GROUP_USER,
        ('open', 'closed'): GROUP_MANAGER,
    }

    # ------------------------------------------------------- what it is about
    name = fields.Char(string='Reference', copy=False, readonly=True,
                       index=True, default=lambda self: _('New'))
    title = fields.Char(
        string='What the role is called', required=True, tracking=True,
        help='The job title a candidate would recognise. "Site Agronomist", '
             'not "Req for AG-2".')
    role_type = fields.Selection(
        ROLE_TYPES, string='Why it is needed', default='new_role',
        required=True, tracking=True,
        help='Replacing somebody quietly keeps the role off the referral '
             'page — the person being replaced is usually still at their '
             'desk.')
    department_id = fields.Many2one(
        'hr.department', string='Which part of the business', required=True,
        index=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one('res.country', string='Country', index=True)
    location = fields.Char(string='Where they would work')
    headcount = fields.Integer(string='How many people', default=1,
                               required=True, tracking=True)
    target_start_date = fields.Date(string='Wanted by', tracking=True)

    requested_by_id = fields.Many2one(
        'hr.employee', string='Asked for by', required=True, index=True,
        tracking=True, ondelete='restrict')
    requested_by_user_id = fields.Many2one(
        'res.users', string='Asked for by (login)', index=True,
        compute='_compute_requested_by_user', store=True, readonly=True)
    reporting_manager_id = fields.Many2one(
        'hr.employee', string='Who they would report to', tracking=True)
    recruiter_id = fields.Many2one(
        'res.users', string='Recruiter', tracking=True, index=True,
        domain="[('share', '=', False)]")
    recruiter_manager_id = fields.Many2one(
        'res.users', string="Recruiter's manager",
        domain="[('share', '=', False)]")

    requirements = fields.Text(
        string='What the person needs to be able to do',
        help='The short version. The full advert is the job description.')
    remarks = fields.Text(string='Anything else worth saying')

    # ------------------------------------------------------------- the money
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    budget_cost = fields.Monetary(
        string='What it is expected to cost', currency_field='currency_id',
        tracking=True,
        help='A year of everything this role costs the company. It is what '
             'the budget check is made against.')
    budget_status = fields.Selection(
        BUDGET_STATUS, string='Budget', default='unknown', readonly=True,
        copy=False, tracking=True)
    budget_remaining = fields.Monetary(
        string='Left in the budget', currency_field='budget_currency_id',
        readonly=True, copy=False)
    budget_currency_id = fields.Many2one(
        'res.currency', string='Budget currency', readonly=True, copy=False)
    budget_over_by = fields.Monetary(
        string='Over by', currency_field='budget_currency_id', readonly=True,
        copy=False)
    budget_checked_on = fields.Datetime(string='Budget last read', readonly=True,
                                        copy=False)
    budget_note = fields.Char(string='What the budget says', readonly=True,
                              copy=False)

    # ------------------------------------------------------ what it produces
    state = fields.Selection(
        REQUISITION_STATES, string='How far it has got', default='draft',
        required=True, tracking=True, copy=False)
    job_id = fields.Many2one('hr.job', string='The job', copy=False,
                             tracking=True, ondelete='set null')
    jd_ids = fields.One2many('pb.hiring.jd', 'requisition_id',
                             string='Job descriptions')
    jd_current_id = fields.Many2one('pb.hiring.jd', string='Agreed description',
                                    copy=False, ondelete='set null')
    step_ids = fields.One2many('pb.hiring.step', 'requisition_id',
                               string='Stages', copy=True)
    posting_ids = fields.One2many('pb.hiring.posting', 'requisition_id',
                                  string='Adverts')
    referral_ids = fields.One2many('pb.hiring.referral', 'requisition_id',
                                   string='Referrals')
    applicant_ids = fields.One2many(
        'hr.applicant', 'pb_requisition_id', string='Candidates')

    referral_open = fields.Boolean(
        string='Open to referrals', copy=False, tracking=True,
        help='On, every employee can put somebody forward for this role on '
             'their own page.')
    published = fields.Boolean(string='Advertised', copy=False, readonly=True)
    opened_on = fields.Date(string='Opened on', readonly=True, copy=False)
    closed_on = fields.Date(string='Closed on', readonly=True, copy=False)
    closing_note = fields.Text(string='Why it was closed', copy=False)

    # -------------------------------------------------------------- counters
    referral_count = fields.Integer(compute='_compute_counts',
                                    string='Referrals')
    applicant_count = fields.Integer(compute='_compute_counts',
                                     string='Candidates')
    jd_count = fields.Integer(compute='_compute_counts',
                              string='Job descriptions')
    days_open = fields.Integer(compute='_compute_days_open', string='Days open')

    # =====================================================================
    #  Names and small computes
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        # THE ACCESS LIST CANNOT ASK THIS QUESTION. Every internal user needs
        # create rights on the model, because a department head holds no
        # hiring group by definition — so the real boundary is here, where
        # the org chart can be read. Over JSON-RPC this is the only thing
        # between "anybody with a login" and a hiring request.
        if not self.env.su:
            self._require_raise()
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                seq = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.hiring.requisition')
                vals['name'] = seq or _('New')
        records = super().create(vals_list)
        for rec in records:
            rec._refresh_budget(silent=True)
        return records

    def _compute_display_name(self):
        for rec in self:
            bits = [b for b in (rec.name, rec.title) if b]
            rec.display_name = ' · '.join(bits) or _('Hiring request')

    @api.depends('requested_by_id')
    def _compute_requested_by_user(self):
        """Stored, because a record rule is a domain: "the ones I asked for"
        cannot be answered through a non-stored hop."""
        for rec in self:
            rec.requested_by_user_id = rec.requested_by_id.sudo().user_id

    @api.depends('referral_ids', 'applicant_ids', 'jd_ids')
    def _compute_counts(self):
        for rec in self:
            rec.referral_count = len(rec.referral_ids)
            rec.applicant_count = len(rec.applicant_ids)
            rec.jd_count = len(rec.jd_ids)

    @api.depends('opened_on', 'closed_on')
    def _compute_days_open(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.opened_on:
                rec.days_open = 0
            else:
                end = rec.closed_on or today
                rec.days_open = max(0, (end - rec.opened_on).days)

    @api.constrains('headcount')
    def _check_headcount(self):
        for rec in self:
            if rec.headcount < 1:
                raise ValidationError(_(
                    "A hiring request has to be for at least one person."))

    @api.onchange('department_id')
    def _onchange_department(self):
        """The manager of the part of the business is the obvious answer for
        who the person would report to, and it is only ever a suggestion."""
        if self.department_id and not self.reporting_manager_id:
            self.reporting_manager_id = self.department_id.manager_id

    # =====================================================================
    #  R56 — an employee read AS THE SYSTEM
    # =====================================================================
    @api.model
    def _person(self, employee):
        """Reading one field of an `hr.employee` reads forty, half of them
        behind payroll groups this module's holders have no reason to hold
        (R56). The security boundary stays the search that found the record.
        """
        from .hiring_common import as_id
        emp_id = as_id(employee)
        if not emp_id:
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().browse(emp_id).exists()

    # =====================================================================
    #  The budget question
    # =====================================================================
    @api.model
    def _fy_window(self, on_date=None):
        """The financial year the check is made over, as two dates.

        `pb.budget`'s own helpers are private (`_fy_months`, `_current_fy`),
        which is correct — they are not RPC business — so they are called
        from Python here and nowhere else.
        """
        Budget = self.env['pb.budget']
        on_date = on_date or fields.Date.context_today(self)
        fy = Budget._current_fy(on_date)
        months = Budget._fy_months(fy)
        return months[0], months[-1], fy

    def _read_budget(self):
        """(status, remaining, currency, note) for ONE request.

        `sudo()` with the company clause written out, never sudo instead of
        it: R89's lesson is that a read made as the system must carry the
        company boundary in the domain, because there is nothing else left to
        carry it.
        """
        self.ensure_one()
        if not self.department_id or not self.company_id:
            return ('unknown', 0.0, self.currency_id,
                    _("No part of the business has been named yet."))
        first, last, _fy = self._fy_window()
        rows = self.env['pb.budget.line'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('department_id', '=', self.department_id.id),
            ('period_month', '>=', first),
            ('period_month', '<=', last),
        ])
        if not rows:
            return ('unknown', 0.0, self.currency_id, _(
                "Nothing has been budgeted for %s this year, so there is no "
                "figure to check this against.", self.department_id.name))

        currencies = rows.mapped('currency_id')
        if len(currencies) > 1:
            return ('unknown', 0.0, self.currency_id, _(
                "The budget for %s is kept in more than one currency, so the "
                "two figures cannot honestly be compared.",
                self.department_id.name))
        currency = currencies[:1] or self.currency_id
        # NO CONVERSION, EVER (R23/R88). A rate that is missing reads as 1.0
        # and turns twenty-six thousand dong into a dollar without a word.
        if self.currency_id and currency and self.currency_id != currency:
            return ('unknown', 0.0, currency, _(
                "This request is priced in %(asked)s and the budget for %(dept)s "
                "is kept in %(held)s. Payobook does not guess an exchange rate, "
                "so nobody can say whether it fits.",
                asked=self.currency_id.name, dept=self.department_id.name,
                held=currency.name))

        budgeted = sum(rows.mapped('forecast_cost'))
        spent = sum(rows.mapped('actual_cost'))
        remaining = currency.round(budgeted - spent) if currency \
            else budgeted - spent
        asked = self.budget_cost or 0.0
        if asked <= remaining:
            note = _("%(left)s of the %(dept)s budget is unspent this year, "
                     "and this role asks for %(asked)s of it.",
                     left=self._money(remaining, currency),
                     dept=self.department_id.name,
                     asked=self._money(asked, currency))
            return ('within', remaining, currency, note)
        over = currency.round(asked - remaining) if currency \
            else asked - remaining
        note = _("This asks for %(over)s more than the %(dept)s budget has "
                 "left this year.", over=self._money(over, currency),
                 dept=self.department_id.name)
        return ('over', remaining, currency, note)

    @api.model
    def _money(self, amount, currency):
        """An amount as a PERSON reads it, and never as markup.

        `ir.qweb.field.monetary.value_to_html` is the obvious helper and the
        wrong one here: it answers
        `<span class="oe_currency_value">600,000,000</span> ₫`, which is
        correct inside a rendered report and is the report's own source code
        when it lands in a Char field that a board shows with `t-esc` (R51,
        reached from the writing side rather than the reading side).
        `formatLang` answers the same number as plain text.
        """
        try:
            return formatLang(self.env, amount or 0.0, currency_obj=currency)
        except Exception:               # noqa: BLE001 — never fail a sentence
            return '%s %s' % (amount, currency.name if currency else '')

    def _refresh_budget(self, silent=False):
        for rec in self:
            try:
                status, remaining, currency, note = rec._read_budget()
            except Exception:           # noqa: BLE001
                _logger.warning('pb_hiring: the budget read failed on %s',
                                rec.id, exc_info=True)
                if silent:
                    continue
                raise
            over = 0.0
            if status == 'over':
                over = (currency.round(rec.budget_cost - remaining)
                        if currency else rec.budget_cost - remaining)
            rec.sudo().write({
                'budget_status': status,
                'budget_remaining': remaining,
                'budget_currency_id': currency.id if currency else False,
                'budget_over_by': over,
                'budget_note': note,
                'budget_checked_on': fields.Datetime.now(),
            })
        return True

    def action_refresh_budget(self):
        """The button. It says what it found, because a button that changes a
        field silently is a button nobody presses twice."""
        self.ensure_one()
        self._refresh_budget()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info' if self.budget_status != 'over'
                       else 'warning',
                       'title': dict(BUDGET_STATUS).get(self.budget_status,
                                                        ''),
                       'message': self.budget_note or '',
                       'sticky': False},
        }

    def write(self, vals):
        res = super().write(vals)
        if {'budget_cost', 'department_id', 'company_id',
                'currency_id'} & set(vals):
            self.filtered(
                lambda r: r.state in ('draft', 'submitted'))._refresh_budget(
                    silent=True)
        return res

    # =====================================================================
    #  Who may ask for a person
    # =====================================================================
    @api.model
    def _can_raise(self, user=None):
        """A function head, or somebody the HR team has named.

        "A function head" is not a group on this database and should not
        become one: it is a fact the org chart already knows — this person
        manages a part of the business. Asking the org chart means a new
        department head can raise a request the day they are appointed,
        without anybody remembering to grant them anything.
        """
        user = user or self.env.user
        # No `_is_admin()` fallback: see the note on `pb.hiring._can_read`.
        # The two built-in administrator accounts hold `group_hiring_admin`
        # already, and anybody else is granted it by name.
        if user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN):
            return True
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1)
        if not employee:
            return False
        return bool(self.env['hr.department'].sudo().search_count([
            ('manager_id', '=', employee.id),
            ('company_id', 'in', self.env.companies.ids
             or [self.env.company.id]),
        ]))

    @api.model
    def _require_raise(self):
        if not self._can_raise():
            raise AccessError(_(
                "Asking for a new person is done by whoever runs that part of "
                "the business. If that is you and this screen disagrees, ask "
                "the HR team to put your name against your department."))
        return True

    def _approval_can(self, from_state, to_state):
        """The manager rung is open to the RIGHT manager and to the HR team.

        The mixin's table says `None` for that rung, which on its own means
        "anybody" — correct as a default and much too wide here. Narrowed to
        the person the request names.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if to_state == 'submitted':
            return bool(self.requested_by_user_id
                        and self.requested_by_user_id.id == self.env.uid) \
                or self.env.user.has_group(GROUP_MANAGER)
        if to_state in ('manager_ok', 'refused') and from_state == 'submitted':
            boss = self._person(self.requested_by_id).parent_id.user_id
            if boss and boss.id == self.env.uid:
                return True
        return super()._approval_can(from_state, to_state)

    # =====================================================================
    #  The buttons
    # =====================================================================
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This one has already been sent in."))
            if not rec.jd_ids and not rec.requirements:
                raise UserError(_(
                    "Say what the person needs to be able to do before you "
                    "send this in — either in the box on this form or as a "
                    "job description. Nobody can agree to a role they cannot "
                    "picture."))
            rec._refresh_budget(silent=True)
            rec._advance_state('submitted')
            rec.sudo().message_post(body=_(
                "Sent in. %s", rec.budget_note or ''))
        return True

    def action_manager_agree(self, note=False):
        for rec in self:
            rec._advance_state('manager_ok', note=note or False)
        return True

    def action_hr_agree(self, note=False):
        for rec in self:
            rec._advance_state('hr_ok', note=note or False)
        return True

    def action_open_role(self, note=False):
        for rec in self:
            rec._advance_state('open', note=note or False)
        return True

    def action_refuse(self, note=False):
        return self.action_refuse_chain(note=note or False)

    def action_mark_filled(self):
        for rec in self:
            if rec.state != 'open':
                raise UserError(_(
                    "Only a role that is open for candidates can be marked "
                    "filled."))
            rec._advance_state('filled')
            rec.sudo().write({'closed_on': fields.Date.context_today(rec),
                              'referral_open': False})
            rec._close_job()
        return True

    def action_close(self, note=False):
        for rec in self:
            if rec.state not in ('open', 'hr_ok', 'manager_ok', 'submitted'):
                raise UserError(_("This one is already closed."))
            if rec.state == 'open':
                rec._advance_state('closed')
            else:
                rec.action_refuse_chain(note=note or _("Closed"))
            rec.sudo().write({'closed_on': fields.Date.context_today(rec),
                              'referral_open': False,
                              'closing_note': note or rec.closing_note})
            rec._close_job()
        return True

    def action_reopen(self):
        """Back to being written, for a request that was turned down and has
        been rethought. The route is re-run from the top — an approval given
        to an earlier version of a request is not an approval of this one."""
        for rec in self:
            if rec.state not in ('refused', 'closed'):
                raise UserError(_(
                    "Only a request that was turned down or closed can be "
                    "opened again."))
            rec._chain_state_write('draft')
            rec.sudo().write({'closed_on': False})
            rec.sudo().message_post(body=_(
                "Opened again. It has to go all the way round the sign-off "
                "once more."))
        return True

    def _close_job(self):
        self.ensure_one()
        if not self.job_id:
            return False
        try:
            self.job_id.sudo().write({'website_published': False})
        except Exception:               # noqa: BLE001
            _logger.warning('pb_hiring: could not take job %s off the careers '
                            'page', self.job_id.id, exc_info=True)
        return True

    # =====================================================================
    #  What happens when everybody has said yes
    # =====================================================================
    def _chain_engine_write(self, to_state):
        """The ENGINE'S OWN write of this record's status runs as the system.

        A SEAT IS A READ AND NEVER A WRITE (ledger AM60), which is exactly
        right — but this chain has TWO intermediate statuses, so the middle of
        the route is mirrored onto the record while the acting user is the
        approver. That approver is, by design, somebody who may hold no
        hiring permission at all: a department head's own manager. The mirror
        was therefore refused by the record rule, the engine swallowed it (it
        must — a decision a person really made can never be undone by a
        consumer that cannot follow its own route), and the request sat at
        "Sent in" with one rung already decided. No error reaches anybody:
        the only trace is one line in the server log.

        Doing it as the system is the honest fix rather than a wider rule.
        The engine has ALREADY decided who may decide; this write is
        bookkeeping about a decision that has happened. The trail is
        unaffected — `_chain_log` still runs as the acting user, so the row
        in the approval log keeps the real name.

        Every consumer whose `driven` tuple has more than one intermediate
        status needs this. P10's extension has none, which is why wave 1
        never met it.
        """
        return super(PbHiringRequisition,
                     self.sudo())._chain_engine_write(to_state)

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'open':
            self._on_opened()
        return res

    def _leg(self, name, fn):
        """One piece of paperwork, inside its own SAVEPOINT.

        A try/except IS NOT ENOUGH when the thing that failed reached the
        DATABASE. Postgres aborts the whole transaction on an error, and
        Python catching the exception does not undo that: every statement
        after it fails too. Proven live — a duplicate job name blew up leg
        one, and legs two, three and four then failed on a transaction that
        was already dead, taking the record's own status write with them.
        The request read "approved" in the inbox and the role read "Manager
        agreed" on the board, for ever, with four cheerful WARNING lines in
        the log and nothing on screen.

        `cr.savepoint()` rolls back just this leg and leaves the transaction
        usable, which is the only thing that makes "paperwork never fails an
        approval" (R104) actually true rather than merely intended.
        """
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                return fn()
        except Exception:               # noqa: BLE001 — never fail an approval
            _logger.warning('pb_hiring: %s failed on request %s', name,
                            self.id, exc_info=True)
            return False

    def _on_opened(self):
        """Four legs, four savepoints (R104).

        The role is open the moment the status says so. Everything below is
        paperwork, and paperwork must never be able to report an approval as
        a failure — nor quietly undo one.
        """
        self.ensure_one()
        if not self.opened_on:
            self.sudo().write({'opened_on': fields.Date.context_today(self)})

        # THE RULE COMES FIRST, AND THE ORDER IS LOAD-BEARING. The job carries
        # the recruiter as its own `user_id`, which is what the standard
        # pipeline screens filter on and what "My jobs" means to a recruiter.
        # Named second, the job was already created with nobody on it and
        # nothing ever went back for it: every job read `user_id = False` over
        # a request that named a recruiter perfectly well, and no screen said
        # anything was wrong.
        self._leg('the hiring rule', self._apply_country_rule)
        self._leg('the job', self._ensure_job)
        self._leg('the recruiter notice', self._notify_recruiters)
        self._leg('opening referrals', self._open_referrals)
        return True

    def _ensure_job(self):
        """The job the candidates hang off — CREATED OR LINKED, never doubled.

        `hr.job` carries a unique constraint on (name, company, department).
        A company that asks for two Field Officers in the same team in the
        same year is not doing anything unusual, and the second request's
        job creation died on a raw Postgres error — swallowed by the
        try/except that `_on_opened` correctly has, so the request opened
        with no job, no advert and no candidates, and nothing anywhere said
        why.

        Linking is also the better answer on its own terms: candidates apply
        to a ROLE, not to a piece of paperwork, and two requests for the same
        role should share one pipeline. The target head count is then the sum
        of every live request pointing at that job, which is the number a
        recruiter actually has to fill.
        """
        self.ensure_one()
        Job = self.env['hr.job'].sudo()
        if self.job_id:
            job = self.job_id
        else:
            job = Job.search([
                ('name', '=', self.title),
                ('company_id', '=', self.company_id.id),
                ('department_id', '=', self.department_id.id),
            ], limit=1)
            if job:
                _logger.info('pb_hiring: %s joined the existing job %s',
                             self.name, job.id)
            else:
                job = Job.create({
                    'name': self.title,
                    'department_id': self.department_id.id,
                    'company_id': self.company_id.id,
                    'no_of_recruitment': max(1, self.headcount),
                    'user_id': self.recruiter_id.id or False,
                    'manager_id': self.reporting_manager_id.id or False,
                    'address_id': self.company_id.partner_id.id,
                })
            self.sudo().write({'job_id': job.id})
        vals = {'no_of_recruitment': max(1, self._wanted_on(job))}
        if self.recruiter_id and job.user_id != self.recruiter_id:
            vals['user_id'] = self.recruiter_id.id
        if self.reporting_manager_id \
                and job.manager_id != self.reporting_manager_id:
            vals['manager_id'] = self.reporting_manager_id.id
        if self.jd_current_id and self.jd_current_id.body:
            vals['website_description'] = self.jd_current_id.body
        if self.requirements:
            vals['requirements'] = self.requirements
        job.write(vals)
        return job

    def _wanted_on(self, job):
        """How many people that job is actually for: every live request on
        it added up, so a second request for the same role raises the target
        rather than replacing it."""
        self.ensure_one()
        others = self.sudo().search([
            ('job_id', '=', job.id), ('id', '!=', self.id),
            ('state', 'in', ('open',)),
        ])
        return (self.headcount or 1) + sum(o.headcount or 1 for o in others)

    def _apply_country_rule(self):
        """Who picks this up. Absence is an answer and it is logged (R120)."""
        self.ensure_one()
        # THE COMPANY'S OWN COUNTRY IS THE SECOND QUESTION, not a guess.
        # Most requests are raised without a country typed on them, because
        # in a single-country company nobody thinks to. Asking only what the
        # request says leaves a Vietnamese company with a Vietnam rule
        # answering "no recruiter" on every request anybody raises — a rule
        # that matches nothing is a broken promise (R27).
        rule = self.env['pb.hiring.country.rule'].rule_for(
            self.company_id, self.country_id or self.company_id.country_id)
        if not rule:
            _logger.warning(
                'pb_hiring: request %s was approved and no hiring rule covers '
                '%s / %s, so no recruiter was named', self.name,
                self.company_id.name, self.country_id.name or '-')
            return False
        vals = {}
        if not self.recruiter_id:
            vals['recruiter_id'] = rule.recruiter_id.id
        if not self.recruiter_manager_id and rule.recruiter_manager_id:
            vals['recruiter_manager_id'] = rule.recruiter_manager_id.id
        if vals:
            self.sudo().write(vals)
        return rule

    def _notify_recruiters(self):
        """Two mails and one to-do, each addressed explicitly (R6)."""
        self.ensure_one()
        if not flag(self.env, P_NOTIFY_MAIL):
            _logger.info('pb_hiring: recruiter notices are switched off; %s '
                         'would have told %s', self.name,
                         self.recruiter_id.name or 'nobody')
            return 0
        sent = 0
        pairs = (
            ('pb_hiring.mail_template_requisition_recruiter',
             self.recruiter_id),
            ('pb_hiring.mail_template_requisition_recruiter_manager',
             self.recruiter_manager_id),
        )
        for xmlid, user in pairs:
            if not user or not user.email:
                continue
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if not template:
                continue
            try:
                template.sudo().send_mail(
                    self.id, force_send=False,
                    email_values={'email_to': user.email})
                sent += 1
            except Exception:           # noqa: BLE001
                _logger.warning('pb_hiring: the notice to %s did not go out',
                                user.login, exc_info=True)
        if self.recruiter_id:
            try:
                self.sudo().activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Start hiring: %s', self.title),
                    note=_("%(who)s asked for this and it has been agreed. "
                           "%(count)s to find.",
                           who=self._person(self.requested_by_id).name or '',
                           count=_('%(n)s %(word)s', n=self.headcount,
                                   word=counted(self.headcount, _('person'),
                                                _('people')))),
                    user_id=self.recruiter_id.id)
            except Exception:           # noqa: BLE001
                _logger.warning('pb_hiring: the recruiter to-do was not '
                                'raised on %s', self.id, exc_info=True)
        return sent

    def _open_referrals(self):
        self.ensure_one()
        wanted = (flag(self.env, P_REFERRAL_AUTO)
                  and self.role_type not in SENSITIVE_TYPES)
        if self.referral_open != wanted:
            self.sudo().write({'referral_open': wanted})
        return wanted

    # =====================================================================
    #  Publishing the advert
    # =====================================================================
    def action_publish(self):
        self.ensure_one()
        return self.env['pb.hiring.posting'].publish_for(self.id)

    # =====================================================================
    #  The doors (every hand-built act_window dict carries `views`, R125)
    # =====================================================================
    def action_open_job(self):
        self.ensure_one()
        if not self.job_id:
            raise UserError(_(
                "There is no job behind this request yet. One is made the "
                "moment the request is agreed."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.job',
                'res_id': self.job_id.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'name': self.job_id.name}

    def action_open_candidates(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.applicant',
                'view_mode': 'list,form', 'views': [[False, 'list'],
                                                    [False, 'form']],
                'name': _('Candidates'),
                'domain': [('pb_requisition_id', '=', self.id)],
                'context': {'active_test': False}}
