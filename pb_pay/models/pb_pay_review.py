# -*- coding: utf-8 -*-
"""`pb.pay.review` — a pay review, and the people in it.

WHAT A REVIEW IS
----------------
One decision, made once a year, about what a defined group of people will be
paid next. It is not a workflow and it is not a performance product: it is a
worksheet with a budget on top of it, a set of limits that explain themselves,
and an approval chain that ends in the one write this whole module is allowed to
make.

WHY IT OPENS FULL
-----------------
The screen a manager dreads is four thousand empty boxes. So a review is BORN
with an answer in every row: the guidance grid is read for each person from
their score and where their pay already sits, and the number it gives is
written into the proposal before anybody has looked at the screen. The budget
meter is therefore already moving, the fairness line already says what this
review would do to the gap, and the rows that break a limit are already marked.
Everything after that is judgement, which is the only part a human is needed
for.

WHAT IT NEVER DOES ON ITS OWN
-----------------------------
Nothing here writes a wage. The proposal is a number on a row of this module's
own table until somebody with the right role walks it through four approvals
and presses Apply — and Apply is a different model (`pb.pay.apply`) precisely so
that the one dangerous act in this area has one door, one preview and one undo.

THE COMPANY RAIL
----------------
A review names its companies explicitly and every read is scoped to them. It
never reads `self.env.companies` (the switcher) to decide who is in it — that
mistake has cost this programme four bugs (GR3, GR16, GR27, GR37).
"""

import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

GROUP_MANAGER = 'pb_pay.group_pay_manager'
GROUP_FINANCE = 'pb_pay.group_pay_finance'
GROUP_CEO = 'pb_pay.group_pay_ceo'

#: Above this a review is built in the background rather than in the click.
MAX_LINES = 20000

#: How long Apply can be taken back.
UNDO_HOURS = 24

STATES = [
    ('draft', 'Being written'),
    ('proposed', 'With HR'),
    ('hr_review', 'With finance'),
    ('finance', 'With the CEO'),
    ('approved', 'Approved'),
    ('applied', 'Applied'),
    ('closed', 'Closed'),
    ('refused', 'Sent back'),
]

LIMIT_KINDS = [
    ('max_raise_pct', 'Nobody rises by more than'),
    ('max_raise_amount', 'No rise is bigger than'),
    ('band_ceiling', 'Nobody ends above the top of their band'),
    ('division_budget', 'One division may not spend more than'),
    ('min_rating', 'Nobody scored below this gets a rise'),
]

LINE_STATES = [
    ('open', 'Open'),
    ('submitted', 'Sent on'),
    ('returned', 'Sent back'),
]


class PbPayReviewLimit(models.Model):
    """A rule a review will not quietly break.

    A limit is written once and then explains itself on every row it touches.
    `block` means Send for approval is refused until the row is fixed; `warn`
    means the row carries the sentence and the review goes on. Both are worth
    having: "nobody above 15%" is usually a rule, and "nobody ends above the
    top of their band" is usually a conversation.
    """
    _name = 'pb.pay.review.limit'
    _description = 'Limit on a pay review'
    _order = 'kind, id'

    review_id = fields.Many2one(
        'pb.pay.review', string='Review', ondelete='cascade', index=True)
    settings_id = fields.Many2one(
        'pb.pay.settings', string='Company settings', ondelete='cascade',
        index=True)
    kind = fields.Selection(LIMIT_KINDS, string='Limit', required=True)
    value = fields.Float(string='Amount', digits=(16, 2))
    enforcement = fields.Selection(
        [('block', 'Stop the review'), ('warn', 'Show a warning')],
        string='What happens', default='block', required=True)
    division_id = fields.Many2one(
        'pb.division', string='Division', ondelete='cascade')
    name = fields.Char(string='Limit', compute='_compute_name')

    @api.depends('kind', 'value', 'division_id', 'enforcement')
    def _compute_name(self):
        for limit in self:
            limit.name = limit.sentence()

    @api.constrains('review_id', 'settings_id')
    def _check_owner(self):
        for limit in self:
            if not limit.review_id and not limit.settings_id:
                raise ValidationError(_(
                    "A limit belongs either to one review or to a company's "
                    "pay settings."))

    def money(self):
        self.ensure_one()
        currency = self.review_id.currency_id or self.env.company.currency_id
        return self.env['pb.pay.bands']._money(self.value, currency)

    def sentence(self):
        """The limit in one line, in the words the screen uses."""
        self.ensure_one()
        if self.kind == 'max_raise_pct':
            return _("Nobody rises by more than %(pct)s%%.",
                     pct=('%g' % (self.value or 0)))
        if self.kind == 'max_raise_amount':
            return _("No single rise is bigger than %(amount)s a month.",
                     amount=self.money())
        if self.kind == 'band_ceiling':
            return _("Nobody ends up paid above the top of their band.")
        if self.kind == 'division_budget':
            name = self.division_id.name or _('each division')
            return _("%(division)s may not spend more than %(amount)s a year.",
                     division=name, amount=self.money())
        if self.kind == 'min_rating':
            return _("Nobody scored below %(score)s gets a rise.",
                     score=int(self.value or 0))
        return _("Limit")

    def summary(self):
        self.ensure_one()
        return {
            'id': self.id, 'kind': self.kind, 'value': float(self.value or 0),
            'enforcement': self.enforcement,
            'division_id': self.division_id.id or 0,
            'division': self.division_id.name or '',
            'sentence': self.sentence(),
            'blocks': self.enforcement == 'block',
        }


class PbPayReviewLine(models.Model):
    """One person in a review."""
    _name = 'pb.pay.review.line'
    _description = 'Person in a pay review'
    _order = 'review_id, department_id, employee_id'
    _rec_name = 'employee_id'

    review_id = fields.Many2one(
        'pb.pay.review', string='Review', required=True, ondelete='cascade',
        index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, ondelete='cascade',
        index=True)
    person_id = fields.Integer(string='Person', index=True)
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', ondelete='set null', index=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager', ondelete='set null', index=True)
    department_id = fields.Many2one('hr.department', string='Team', index=True)
    job_id = fields.Many2one('hr.job', string='Job position', index=True)
    division_id = fields.Many2one('pb.division', string='Division', index=True)
    band_id = fields.Many2one('pb.pay.band', string='Band',
                              ondelete='set null')
    level = fields.Integer(string='Level')
    sex = fields.Char(string='Recorded sex')
    position_pct = fields.Float(string='Position in band', digits=(16, 2))
    has_band = fields.Boolean(string='Has a band')
    rating = fields.Integer(string='How well they did')

    currency_id = fields.Many2one('res.currency', string='Currency')
    current_wage = fields.Monetary(string='Paid now')
    guidance_pct = fields.Float(string='Guidance', digits=(16, 2))
    proposal_pct = fields.Float(string='Proposed rise', digits=(16, 2))
    proposal_amount = fields.Monetary(string='Rise')
    new_wage = fields.Monetary(string='New pay')
    annual_cost_delta = fields.Monetary(string='A year')

    chips = fields.Json(string='What to know')
    manager_note = fields.Text(string='Note')
    returned_note = fields.Text(string='Why it came back')
    state = fields.Selection(LINE_STATES, string='Row', default='open',
                             index=True)

    _line_uniq = models.Constraint(
        'unique(review_id, employee_id)',
        'That person is already in this review.')

    # ------------------------------------------------------------- the maths
    def _recalc(self, pct=None, amount=None):
        """Keep the four money fields telling the same story.

        A raise can be typed as a percentage or as an amount, and the one the
        reader did not type has to follow instantly or the two numbers on the
        row disagree in front of them. Neither is a stored compute: an editable
        stored compute with a default never runs (ledger GR34), and this one is
        written from three directions.
        """
        for line in self:
            base = float(line.current_wage or 0.0)
            if amount is not None:
                rise = float(amount or 0.0)
                percentage = (rise / base * 100.0) if base else 0.0
            else:
                percentage = float(
                    line.proposal_pct if pct is None else pct or 0.0)
                rise = base * percentage / 100.0
            line.proposal_pct = round(percentage, 4)
            line.proposal_amount = rise
            line.new_wage = base + rise
            line.annual_cost_delta = rise * 12.0

    def set_proposal(self, pct=None, amount=None):
        """The one way a proposal is written."""
        self._recalc(pct=pct, amount=amount)
        return True

    def take_guidance(self):
        for line in self:
            line._recalc(pct=line.guidance_pct)
        return True

    # ------------------------------------------------------------- the chips
    def payload(self, can_see_names=True):
        self.ensure_one()
        money = self.env['pb.pay.bands']
        currency = self.currency_id or self.env.company.currency_id
        return {
            'id': self.id,
            'employee_id': self.employee_id.id,
            'name': self.employee_id.name if can_see_names
            else _('Person %(number)s', number=self.id),
            'job': self.job_id.display_name or '',
            'team': self.department_id.display_name or '',
            'manager': self.manager_id.name or '',
            'division': self.division_id.name or '',
            'band': self.band_id.name or '',
            'position_pct': round(float(self.position_pct or 0.0), 1),
            'position_label': self._position_label(),
            'has_band': bool(self.has_band),
            'rating': int(self.rating or 0),
            'currency': currency.name or '',
            'current_wage': float(self.current_wage or 0.0),
            'current_label': money._money(self.current_wage, currency),
            'guidance_pct': round(float(self.guidance_pct or 0.0), 2),
            'proposal_pct': round(float(self.proposal_pct or 0.0), 2),
            'proposal_amount': float(self.proposal_amount or 0.0),
            'new_wage': float(self.new_wage or 0.0),
            'new_label': money._money(self.new_wage, currency),
            'rise_label': money._money(self.proposal_amount, currency),
            'annual_label': money._short(self.annual_cost_delta, currency),
            'chips': self.chips or [],
            'blocked': any(c.get('blocks') for c in (self.chips or [])),
            'note': self.manager_note or '',
            'returned_note': self.returned_note or '',
            'state': self.state or 'open',
        }

    def _position_label(self):
        self.ensure_one()
        if not self.has_band:
            return _("No band for this job yet")
        pct = float(self.position_pct or 0.0)
        if pct < 0:
            return _("Below the band")
        if pct > 100:
            return _("Above the band")
        return _("%(pct)s%% of the way through the band", pct=int(round(pct)))


class PbPayReview(models.Model):
    _name = 'pb.pay.review'
    _description = 'Pay review'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'year desc, id desc'

    name = fields.Char(string='Review', required=True, tracking=True)
    scope_kind = fields.Selection(
        [('company', 'One company'), ('division', 'One division'),
         ('scheme', 'One payroll scheme')],
        string='Who it covers', default='company', required=True)
    scope_ref = fields.Integer(string='Which one')
    scope_label = fields.Char(string='Covers')
    scope_note = fields.Char(
        string='What that means',
        help='Set when the people this review covers had to be worked out a '
             'different way from the one that was asked for.')
    company_ids = fields.Many2many('res.company', string='Companies')
    company_id = fields.Many2one(
        'res.company', string='Main company', index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.context_today(self).year)
    effective_date = fields.Date(
        string='New pay starts on', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self))
    budget_amount = fields.Monetary(string='Budget for the year',
                                    tracking=True)
    guidance_id = fields.Many2one(
        'pb.pay.guidance', string='Guidance', ondelete='set null')
    rating_scale = fields.Selection(
        related='guidance_id.rating_scale', string='Scale', readonly=True)
    limit_ids = fields.One2many('pb.pay.review.limit', 'review_id',
                                string='Limits')
    line_ids = fields.One2many('pb.pay.review.line', 'review_id',
                               string='People')
    note = fields.Text(string='Why this review')

    allocated_amount = fields.Monetary(
        string='Proposed for the year', compute='_compute_meters')
    remaining_amount = fields.Monetary(
        string='Left', compute='_compute_meters')
    people = fields.Integer(string='People', compute='_compute_meters')
    lines_blocked = fields.Integer(
        string='Rows that stop approval', compute='_compute_meters')

    fairness_before = fields.Json(string='Fairness now')
    fairness_after = fields.Json(string='Fairness if applied')
    fairness_dirty = fields.Boolean(default=True)

    state = fields.Selection(
        STATES, string='Status', default='draft', tracking=True, index=True,
        copy=False)
    is_legacy = fields.Boolean(
        string='Carried over', default=False,
        help='A review that came from the old planning screens. It is kept '
             'so the history is not lost and cannot be edited.')
    decision_plan_id = fields.Integer(string='Born from a plan')

    applied_at = fields.Datetime(string='Applied on', readonly=True)
    applied_by = fields.Many2one('res.users', string='Applied by',
                                 readonly=True)
    undo_until = fields.Datetime(string='Can be taken back until',
                                 readonly=True)
    apply_ids = fields.One2many('pb.pay.apply', 'review_id',
                                string='What was written')
    approval_widget_json = fields.Char(compute='_compute_approval_widget')

    # ===================================================== the approval chain
    _approval_transitions = {
        ('draft', 'proposed'): None,
        ('proposed', 'hr_review'): GROUP_MANAGER,
        ('hr_review', 'finance'): GROUP_FINANCE,
        ('finance', 'approved'): GROUP_CEO,
        ('approved', 'applied'): GROUP_MANAGER,
        ('applied', 'closed'): GROUP_MANAGER,
        # sent back down, by whoever the review is waiting on. An APPROVED
        # review can go back too: an approval that cannot be reopened before
        # it is applied is a screen with no way out of the one state where
        # somebody has changed their mind and nothing has happened yet.
        ('proposed', 'draft'): GROUP_MANAGER,
        ('hr_review', 'draft'): GROUP_FINANCE,
        ('finance', 'draft'): GROUP_CEO,
        ('approved', 'draft'): GROUP_CEO,
    }
    _approval_dead_states = ('refused',)

    #: The ladder the stepper draws, in plain words.
    def _approval_steps(self):
        return [
            {'state': 'draft', 'label': _('Being written'),
             'group_label': _('The manager')},
            {'state': 'proposed', 'label': _('With HR'),
             'group_label': _('HR')},
            {'state': 'hr_review', 'label': _('With finance'),
             'group_label': _('Finance')},
            {'state': 'finance', 'label': _('With the CEO'),
             'group_label': _('The CEO')},
            {'state': 'approved', 'label': _('Approved'),
             'group_label': _('Ready to apply')},
            {'state': 'applied', 'label': _('Applied'),
             'group_label': _('Pay changed')},
        ]

    @api.depends('state')
    def _compute_approval_widget(self):
        for review in self:
            review.approval_widget_json = \
                review._approval_widget_payload(review._approval_steps()) \
                if review.id else False

    def _approval_can(self, from_state, to_state):
        """Whoever the review is waiting on, plus the person who wrote it.

        A review that only its author can send on would dead-end the moment
        that person is on leave, so HR can always move it forward too.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        if (from_state, to_state) == ('draft', 'proposed'):
            if self.create_uid.id == self.env.uid:
                return True
            return self.env.user.has_group(GROUP_MANAGER)
        return super()._approval_can(from_state, to_state)

    def _before_approval_transition(self, to_state):
        super()._before_approval_transition(to_state)
        if to_state == 'proposed':
            self._refuse_if_blocked()

    def _after_approval_transition(self, to_state):
        super()._after_approval_transition(to_state)
        self._notify_next_step(to_state)

    def _refuse_if_blocked(self):
        """A review with a row that breaks a hard limit does not go on."""
        self.ensure_one()
        if self.is_legacy:
            raise UserError(_(
                "This review was carried over from the old screens and is "
                "kept as history. It cannot be changed."))
        self.recompute_chips()
        blocked = self.lines_blocked
        if blocked:
            raise UserError(_(
                "%(count)s rows break a limit this review will not bend. Open "
                "“What stops approval” and fix them, or change the limit.",
                count=blocked))
        over = self.allocated_amount - self.budget_amount
        if self.budget_amount and over > 0:
            raise UserError(_(
                "This review proposes %(over)s more than its budget. Lower "
                "some rises or raise the budget.",
                over=self.env['pb.pay.bands']._money(
                    over, self.currency_id or self.env.company.currency_id)))

    def _notify_next_step(self, to_state):
        """Give the next person a real task, not a hope that they look."""
        self.ensure_one()
        group = {'proposed': GROUP_MANAGER, 'hr_review': GROUP_FINANCE,
                 'finance': GROUP_CEO}.get(to_state)
        if not group:
            return
        try:
            record = self.env.ref(group).sudo()
            people = record.all_user_ids if 'all_user_ids' in record._fields \
                else record.user_ids
        except Exception:                       # noqa: BLE001
            return
        people = people.filtered(lambda u: u.active and u.id != self.env.uid)
        for user in people[:10]:
            try:
                self.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_('A pay review is waiting for you'),
                    note=_('“%(name)s” covers %(people)s people and proposes '
                           '%(amount)s for the year.',
                           name=self.name or '',
                           people=self.people,
                           amount=self.env['pb.pay.bands']._money(
                               self.allocated_amount,
                               self.currency_id
                               or self.env.company.currency_id)),
                    user_id=user.id)
            except Exception:                   # noqa: BLE001
                _logger.info('pb_pay: could not raise a task for user %s',
                             user.id)

    # ------------------------------------------------------------ the meters
    @api.depends('line_ids.annual_cost_delta', 'line_ids.chips',
                 'budget_amount')
    def _compute_meters(self):
        totals, counts, blocked = {}, {}, {}
        if self.ids:
            # GR13: the ORM is still holding writes to these rows. Flush
            # first, or the raw count below reads yesterday's chips.
            self.env.flush_all()
            rows = self.env['pb.pay.review.line'].sudo()._read_group(
                [('review_id', 'in', self.ids)], ['review_id'],
                ['annual_cost_delta:sum', '__count'])
            for review, total, count in rows:
                totals[review.id] = float(total or 0.0)
                counts[review.id] = count
            self.env.cr.execute("""
                SELECT review_id, COUNT(*) FROM pb_pay_review_line
                 WHERE review_id IN %s AND chips::text LIKE '%%"blocks": true%%'
              GROUP BY review_id
            """, [tuple(self.ids)])
            blocked = dict(self.env.cr.fetchall())
        for review in self:
            review.allocated_amount = totals.get(review.id, 0.0)
            review.people = counts.get(review.id, 0)
            review.remaining_amount = (review.budget_amount or 0.0) \
                - review.allocated_amount
            review.lines_blocked = blocked.get(review.id, 0)

    # ================================================== building the worksheet
    @api.model
    def _scope_companies(self, kind, ref):
        """The companies a scope covers, always inside what the reader may see."""
        Fair = self.env['pb.pay.fairness']
        if kind == 'scheme' and ref and 'hr.formula.config' in self.env:
            config = self.env['hr.formula.config'].sudo().browse(
                int(ref)).exists()
            companies = self.env['pb.pay.bands']._companies()
            inside = companies.filtered(
                lambda c: c.id == config.company_id.id) or companies[:1]
            return {'kind': 'scheme', 'ref': int(ref),
                    'label': config.name or _('a payroll scheme'),
                    'companies': inside, 'division_id': 0,
                    'config_id': int(ref)}
        resolved = Fair._resolve_scope(
            kind if kind in ('company', 'division') else 'company', ref)
        resolved['config_id'] = 0
        return resolved

    @api.model
    def scopes(self):
        """Everything a review can be run for, in one list."""
        out = []
        for scope in self.env['pb.pay.fairness'].get_scopes():
            if scope['kind'] == 'group':
                continue
            out.append(scope)
        if 'hr.formula.config' not in self.env:
            return out
        Config = self.env['hr.formula.config'].sudo()
        companies = self.env['pb.pay.bands']._companies()
        for config in Config.search(
                [('company_id', 'in', companies.ids)], limit=40):
            out.append({'kind': 'scheme', 'ref': config.id,
                        'label': config.name,
                        'sub': config.company_id.display_name or ''})
        return out

    def build_lines(self):
        """Fill the worksheet from the roster this review covers.

        Read as one SQL join for the same reason the Decision Room's baseline
        is (WF12): four and a half thousand people through the ORM is eight
        hundred milliseconds and through one join it is seventy.
        """
        self.ensure_one()
        scope = self._scope_companies(self.scope_kind, self.scope_ref)
        companies = scope['companies']
        if not companies:
            return 0
        self.sudo().write({
            'company_ids': [(6, 0, companies.ids)],
            'scope_label': scope['label'],
        })
        rows, note = self._roster(companies, scope)
        self.sudo().scope_note = note
        if len(rows) > MAX_LINES:
            raise UserError(_(
                "This covers %(count)s people, which is more than one review "
                "can hold. Run it for one company or one division at a time.",
                count=len(rows)))
        existing = {line.employee_id.id: line for line in self.line_ids}
        Line = self.env['pb.pay.review.line'].sudo()
        made = []
        for row in rows:
            if row['employee_id'] in existing:
                continue
            made.append(dict(row, review_id=self.id))
        if made:
            Line.create(made)
        self.invalidate_recordset(['line_ids'])
        self._seed_ratings()
        self.apply_guidance_to(self.line_ids.filtered(
            lambda l: not l.proposal_pct))
        self.mark_fairness_dirty()
        return len(self.line_ids)

    def _seed_ratings(self):
        """Copy the latest score anybody recorded into this review.

        A review that opens with every row saying "nobody has scored this
        person" when the company DOES hold scores is a screen that has thrown
        away what it knew. The copy is one-way and once: the review then keeps
        its own, so re-scoring somebody next year never rewrites this one.
        """
        self.ensure_one()
        Employee = self.env['hr.employee']
        if 'pb_performance_rating' not in Employee._fields:
            return 0
        have = set(self.env['pb.pay.rating'].sudo().search(
            [('review_id', '=', self.id)]).mapped('employee_id').ids)
        rows = []
        for line in self.line_ids:
            if line.employee_id.id in have:
                continue
            try:
                value = int(line.employee_id.sudo().pb_performance_rating or 0)
            except (TypeError, ValueError):
                continue
            if value:
                rows.append({'employee_id': line.employee_id.id,
                             'rating': value})
        if rows:
            self.env['pb.pay.rating']._write_many(self, rows, 'synced')
        return len(rows)

    def _roster(self, companies, scope):
        """`(rows, note)` — one dict per person, and what the reader has to know.

        The note is RETURNED rather than stashed on the record: a recordset on
        this platform cannot hold an instance attribute, and a builder that
        tries to becomes a stateless method with a bug in it.
        """
        self.ensure_one()
        cr = self.env.cr
        person_col = 'e.pb_person_id' \
            if 'pb_person_id' in self.env['hr.employee']._fields \
            else 'NULL::int'
        cr.execute("""
            SELECT DISTINCT ON (c.employee_id)
                   c.employee_id, c.id AS contract_id, c.company_id,
                   COALESCE(c.wage, 0)::numeric AS wage,
                   COALESCE(c.job_id, v.job_id) AS job_id,
                   COALESCE(c.department_id, v.department_id) AS dep_id,
                   e.parent_id, v.sex, """ + person_col + """ AS person_id
              FROM hr_contract c
              JOIN hr_employee e ON e.id = c.employee_id AND e.active
         LEFT JOIN hr_version v ON v.id = e.current_version_id
             WHERE c.state = 'open' AND c.active AND c.company_id IN %s
          ORDER BY c.employee_id, c.date_start DESC NULLS LAST, c.id DESC
        """, [tuple(companies.ids)])
        raw = cr.fetchall()

        positions = {}
        for row in self.env['pb.pay.position'].sudo().search_read(
                [('company_id', 'in', companies.ids)],
                ['employee_id', 'band_id', 'position_pct', 'state']):
            positions[(row['employee_id'] or [0])[0]] = row
        bands = {b.id: b for b in self.env['pb.pay.band'].sudo().browse(
            list({(r['band_id'] or [0])[0] for r in positions.values()
                  if r.get('band_id')}))}

        by_department, chains = {}, {}
        if 'pb.division' in self.env:
            Division = self.env['pb.division'].sudo()
            try:
                by_department = Division._links_on() or {}
                chains = Division._department_chains(companies.ids) or {}
            except Exception:                   # noqa: BLE001
                by_department, chains = {}, {}

        wanted, note = self._scheme_population(
            scope, [row[0] for row in raw])
        currencies = {c.id: c.currency_id.id for c in companies}
        out = []
        for (employee_id, contract_id, company_id, wage, job_id, dep_id,
             parent_id, sex, person_id) in raw:
            if wanted is not None and employee_id not in wanted:
                continue
            position = positions.get(employee_id) or {}
            band_id = (position.get('band_id') or [0])[0] \
                if position.get('band_id') else 0
            band = bands.get(band_id)
            division = 0
            if dep_id:
                for candidate in reversed(chains.get(dep_id) or [dep_id]):
                    if candidate in by_department:
                        division = by_department[candidate]
                        break
            out.append({
                'employee_id': employee_id,
                'person_id': person_id or employee_id,
                'contract_id': contract_id,
                'company_id': company_id,
                'manager_id': parent_id or False,
                'department_id': dep_id or False,
                'job_id': job_id or False,
                'division_id': division or False,
                'band_id': band_id or False,
                'level': band.level if band else 0,
                'sex': (sex or '').lower() or 'unknown',
                'position_pct': float(position.get('position_pct') or 0.0),
                'has_band': bool(band_id),
                'currency_id': currencies.get(company_id),
                'current_wage': float(wage or 0.0),
            })
        if scope.get('division_id'):
            out = [row for row in out
                   if row['division_id'] == scope['division_id']]
        return out, note

    def _scheme_population(self, scope, employee_ids):
        """Whose scheme this is, when the review is run for one scheme.

        Asked of the map for the scheme's OWN kind of run: a scheme that pays
        the mid-month advance answers a different question from the one that
        pays at the end of the month, and asking about "any" kind of run reads
        every advance scheme as covering nobody (ledger GR18).
        """
        if not scope.get('config_id') or 'pb.scheme.map' not in self.env:
            return None, ''
        config_id = int(scope['config_id'])
        config = self.env['hr.formula.config'].sudo().browse(config_id)
        cycle = config.cycle_type or 'any'
        try:
            answers = self.env['pb.scheme.map'].sudo().resolve_many(
                employee_ids, cycle_type=cycle)
        except Exception:                       # noqa: BLE001
            _logger.exception('pb_pay: the scheme map could not say who this '
                              'scheme pays')
            return None, _(
                "The scheme map could not be read just now, so this review "
                "covers everybody in the company.")
        wanted = set()
        for employee_id, answer in (answers or {}).items():
            found = answer.get('config_id') if isinstance(answer, dict) \
                else None
            if found and int(found) == config_id:
                wanted.add(int(employee_id))
        if not wanted:
            _logger.info('pb_pay: the map says this scheme pays nobody, so '
                         'the review covers the whole company instead')
            return None, _(
                "Nobody has said yet which people this scheme pays, so this "
                "review covers everybody in the company. Set that up on the "
                "“Who is paid by what” board and start this one again to "
                "narrow it.")
        return wanted, ''

    # =============================================================== guidance
    def apply_guidance_to(self, lines=None):
        """Write the grid's answer into every row it is asked about."""
        self.ensure_one()
        lines = lines if lines is not None else self.line_ids
        if not lines:
            return 0
        grid = self.guidance_id
        ratings = self._ratings_by_employee()
        for line in lines:
            rating = ratings.get(line.employee_id.id, 0)
            line.rating = rating
            if grid:
                pct = grid.pct_for(rating or grid.middle_rating(),
                                   line.position_pct, line.has_band)
            else:
                pct = 0.0
            line.guidance_pct = pct
            line._recalc(pct=pct)
        self.recompute_chips(lines)
        self.mark_fairness_dirty()
        return len(lines)

    def _ratings_by_employee(self):
        self.ensure_one()
        rows = self.env['pb.pay.rating'].sudo().search_read(
            [('review_id', '=', self.id)], ['employee_id', 'rating'])
        return {(row['employee_id'] or [0])[0]: row['rating'] for row in rows}

    # ================================================================== chips
    def recompute_chips(self, lines=None):
        """Everything a row has to say about itself, worked out in one pass."""
        self.ensure_one()
        lines = lines if lines is not None else self.line_ids
        if not lines:
            return 0
        limits = self.limit_ids
        by_kind = defaultdict(list)
        for limit in limits:
            by_kind[limit.kind].append(limit)

        bands = {b.id: b for b in self.line_ids.mapped('band_id')}
        division_totals = defaultdict(float)
        for line in self.line_ids:
            if line.division_id:
                division_totals[line.division_id.id] += \
                    float(line.annual_cost_delta or 0.0)

        # Who ends up paid less than somebody who reports to them. Read once
        # for the whole review rather than per row.
        new_pay = {line.employee_id.id: float(line.new_wage or 0.0)
                   for line in self.line_ids}
        reports = defaultdict(list)
        for line in self.line_ids:
            if line.manager_id:
                reports[line.manager_id.id].append(line.employee_id.id)

        for line in lines:
            chips = []
            if not line.rating:
                chips.append({'key': 'unrated', 'tone': 'warn',
                              'blocks': False,
                              'text': _("Nobody has scored this person, so "
                                        "the guidance used the middle.")})
            if not line.has_band:
                chips.append({'key': 'no_band', 'tone': 'info',
                              'blocks': False,
                              'text': _("This job has no band yet, so the "
                                        "guidance used the middle column.")})
            for limit in by_kind['max_raise_pct']:
                if line.proposal_pct > limit.value:
                    chips.append(self._chip(limit, _(
                        "%(pct)s%% is above the %(cap)s%% this review allows.",
                        pct=('%g' % round(line.proposal_pct, 2)),
                        cap=('%g' % limit.value))))
            for limit in by_kind['max_raise_amount']:
                if line.proposal_amount > limit.value:
                    chips.append(self._chip(limit, _(
                        "%(rise)s is a bigger rise than this review allows.",
                        rise=self.env['pb.pay.bands']._money(
                            line.proposal_amount,
                            line.currency_id or self.currency_id))))
            for limit in by_kind['band_ceiling']:
                band = bands.get(line.band_id.id)
                if band and line.new_wage > band.max_amount:
                    chips.append(self._chip(limit, _(
                        "%(pay)s is above the top of %(band)s.",
                        pay=self.env['pb.pay.bands']._money(
                            line.new_wage,
                            line.currency_id or self.currency_id),
                        band=band.name)))
            for limit in by_kind['min_rating']:
                if line.proposal_pct > 0 and line.rating \
                        and line.rating < int(limit.value or 0):
                    chips.append(self._chip(limit, _(
                        "This review gives no rise to anybody scored below "
                        "%(score)s.", score=int(limit.value or 0))))
            for limit in by_kind['division_budget']:
                if not line.division_id:
                    continue
                if limit.division_id and limit.division_id != line.division_id:
                    continue
                spent = division_totals.get(line.division_id.id, 0.0)
                if spent > limit.value:
                    chips.append(self._chip(limit, _(
                        "%(division)s has proposed %(spent)s of "
                        "%(allowed)s for the year.",
                        division=line.division_id.name,
                        spent=self.env['pb.pay.bands']._short(
                            spent, self.currency_id),
                        allowed=self.env['pb.pay.bands']._short(
                            limit.value, self.currency_id))))
            below = [employee for employee in reports.get(
                line.employee_id.id, [])
                if new_pay.get(employee, 0.0) > float(line.new_wage or 0.0)]
            if below:
                chips.append({
                    'key': 'inversion', 'tone': 'warn', 'blocks': False,
                    'text': _("After this, %(count)s of their team would be "
                              "paid more than they are.", count=len(below))})
            line.chips = chips
        return len(lines)

    @staticmethod
    def _chip(limit, text):
        return {'key': limit.kind, 'tone': 'bad',
                'blocks': limit.enforcement == 'block', 'text': text,
                'limit_id': limit.id}

    # =============================================================== fairness
    def mark_fairness_dirty(self):
        for review in self:
            review.sudo().fairness_dirty = True
        return True

    def fairness(self):
        """The gap now and the gap this review would leave, recomputed lazily.

        Recomputing on every keystroke over four thousand rows would make the
        worksheet unusable, so the flag is set on a write and the answer is
        worked out the next time somebody READS it.
        """
        self.ensure_one()
        if not self.fairness_dirty and self.fairness_before:
            return {'before': self.fairness_before or {},
                    'after': self.fairness_after or {},
                    'sentence': self._fairness_sentence(
                        self.fairness_before or {}, self.fairness_after or {})}
        Fair = self.env['pb.pay.fairness']
        people_now, people_then = [], []
        for line in self.line_ids:
            base = {'sex': line.sex or 'unknown', 'level': line.level or 0,
                    'job_id': line.job_id.id or 0}
            people_now.append(dict(base, wage=float(line.current_wage or 0.0)))
            people_then.append(dict(base, wage=float(line.new_wage or 0.0)))
        before = Fair.gap_for(people_now)
        after = Fair.gap_for(people_then)
        self.sudo().write({'fairness_before': before, 'fairness_after': after,
                           'fairness_dirty': False})
        return {'before': before, 'after': after,
                'sentence': self._fairness_sentence(before, after)}

    def _fairness_sentence(self, before, after):
        """One line a person can read out in a meeting."""
        self.ensure_one()
        if not before or before.get('gap') is None:
            return _("There are not enough people with a recorded sex to "
                     "measure the gap fairly.")
        # `gap_for` answers in PERCENTAGE POINTS already — multiplying again
        # is the classic way to print "240% less" and be believed once.
        now = float(before.get('gap') or 0.0)
        then = float(after.get('gap') or 0.0)
        where = self.scope_label or self.name or ''
        if abs(then - now) < 0.05:
            return _("This review leaves the gap in %(where)s where it is, at "
                     "%(now)s%%.", where=where, now=('%.1f' % abs(now)))
        verb = _("narrows") if abs(then) < abs(now) else _("widens")
        return _("This review %(verb)s the gap in %(where)s from %(now)s%% to "
                 "%(then)s%%.", verb=verb, where=where,
                 now=('%.1f' % abs(now)), then=('%.1f' % abs(then)))

    # ================================================================ writing
    def write(self, vals):
        # `env.su` and not `_is_admin()`: the migration that WRITES the history
        # runs as the server itself, and an administrator clicking on a screen
        # is still a person editing the past.
        touched = set(vals) - {'fairness_before', 'fairness_after',
                               'fairness_dirty'}
        if touched and not self.env.su:
            for review in self:
                if review.is_legacy:
                    raise UserError(_(
                        "This review was carried over from the old screens "
                        "and is kept as history. It cannot be changed."))
        result = super().write(vals)
        if {'budget_amount', 'guidance_id'} & set(vals):
            self.mark_fairness_dirty()
        return result

    def unlink(self):
        for review in self:
            if review.state in ('applied', 'closed'):
                raise UserError(_(
                    "A review that has been applied is kept. Nothing about "
                    "what people were paid may be deleted."))
        return super().unlink()

    # -------------------------------------------------------------- the doors
    def action_submit(self):
        self.ensure_one()
        return self._advance_state('proposed')

    def action_hr_approve(self):
        self.ensure_one()
        return self._advance_state('hr_review')

    def action_finance_approve(self):
        self.ensure_one()
        return self._advance_state('finance')

    def action_ceo_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    def action_send_back(self, note=False):
        self.ensure_one()
        return self._advance_state('draft', note=note)

    def action_close(self):
        self.ensure_one()
        return self._advance_state('closed')
