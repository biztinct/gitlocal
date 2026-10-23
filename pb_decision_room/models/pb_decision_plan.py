# -*- coding: utf-8 -*-
"""A saved what-if.

Kept on the SERVER and not in one browser, because a plan a board is going to
look at is not a private note: the finance lead has to be able to open the same
one the owner saved, on their own laptop, next week.

The record holds three JSON blobs and one summary. `state` is the levers, and
it is the only thing the room needs to redraw the whole year — everything else
on screen is computed from it. `summary` is the headline numbers as the client
computed them at save time, stored so the comparison table can be drawn without
recomputing twelve months for every row.

GROUP PHASE 4 added three things and one promise.

  * **A scope.** "Retail 2027" and "Logistics 2027" are two plans about two
    different parts of the same company, and until now they could not both
    exist without pretending to be about the whole of it. A plan now records
    what it is a plan FOR, and the dock says so.
  * **A state.** draft → proposed → approved (or rejected, back to draft). It
    is a decision, and a decision that nobody can point at the moment it was
    taken is a conversation, not a decision.
  * **Versions.** Proposing takes a SNAPSHOT — the levers, the goals, the
    headline numbers, the scope, and the rules the numbers were built on — so
    "the plan the board approved in November" survives every edit made to the
    plan afterwards. A snapshot also records what could NOT be converted, so
    an approval taken over a missing exchange rate says so in its own record
    rather than being quietly rounded into a number.

  The promise: none of this writes to payroll. A plan is still a saved
  what-if, and approving one changes nothing but this record.

THE MONEY IN A PLAN IS LOCAL MONEY (group ledger rule 7). `summary` holds each
company's own currency, and the group figure that the board reads is built at
READ time through `pb.fx`. Nothing converted is ever stored here.
"""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

#: How many plans one company may keep. A dock that scrolls is a dock nobody
#: reads; twenty is more than any board has ever needed at once.
MAX_PLANS = 20

#: How many versions of one plan are kept. Enough for a year of board
#: meetings; beyond that the oldest is dropped and the drawer says so.
MAX_VERSIONS = 30

STATES = [
    ('draft', "Draft"),
    ('proposed', "Waiting for approval"),
    ('approved', "Approved"),
    ('rejected', "Sent back"),
]


class PbDecisionPlanVersion(models.Model):
    _name = 'pb.decision.plan.version'
    _description = 'Decision Room plan version'
    _order = 'number desc, id desc'

    plan_id = fields.Many2one(
        'pb.decision.plan', string="Plan", required=True, index=True,
        ondelete='cascade')
    number = fields.Integer(string="Version", required=True, default=1)
    name = fields.Char(string="Name", required=True)
    label = fields.Char(
        string="What this version was",
        help="A few words about why this version exists — \"proposed to the "
             "board\", \"after the pay review\".")
    snapshot = fields.Json(
        string="Everything as it stood",
        help="The levers, the goals, the headline numbers, the scope and the "
             "rules the numbers were built on, exactly as they were.")
    created_by = fields.Many2one(
        'res.users', string="Kept by", default=lambda self: self.env.user,
        ondelete='set null')
    created_at = fields.Datetime(
        string="Kept on", default=fields.Datetime.now)

    @api.depends('plan_id', 'number')
    def _compute_display_name(self):
        for row in self:
            row.display_name = _("Version %(n)s · %(plan)s",
                                 n=row.number, plan=row.name or '')


class PbDecisionPlan(models.Model):
    _name = 'pb.decision.plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Decision Room saved plan'
    _order = 'is_reference desc, write_date desc, id desc'

    name = fields.Char(
        string="Plan name", required=True, tracking=True,
        help="What you would call this in a meeting.")
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, ondelete='cascade',
        default=lambda self: self.env.company, index=True)
    user_id = fields.Many2one(
        'res.users', string="Saved by", default=lambda self: self.env.user,
        ondelete='set null')

    # ------------------------------------------------------------- the scope
    scope_kind = fields.Selection(
        [('group', "Whole group"), ('country', "Country"),
         ('company', "Company"), ('division', "Division"),
         ('scheme', "Payroll scheme")],
        string="This is a plan for", required=True, default='company',
        index=True, tracking=True)
    scope_ref = fields.Char(string="Which one", index=True)
    scope_label = fields.Char(string="Scope", tracking=True)
    # GROUP P7 — the division a plan is FOR, as a real link rather than as a
    # number inside a Char. It exists so the "who sees what" record rule can
    # be the same one-line domain every other model in this programme uses,
    # and so a report can group plans by division without parsing `scope_ref`.
    pb_division_id = fields.Many2one(
        'pb.division', string="Division", index=True, store=True,
        compute='_compute_pb_division_id',
        help="Filled when this plan is a plan for one division.")
    company_ids = fields.Many2many(
        'res.company', 'pb_decision_plan_company_rel', 'plan_id', 'company_id',
        string="Companies in this plan")

    @api.depends('scope_kind', 'scope_ref')
    def _compute_pb_division_id(self):
        for plan in self:
            division = False
            if plan.scope_kind == 'division' and plan.scope_ref:
                try:
                    division = int(plan.scope_ref)
                except (TypeError, ValueError):
                    division = False
            plan.pb_division_id = division or False

    state = fields.Json(
        string="The levers",
        help="Everything you moved: people per team, the raise, overtime, "
             "when the hires arrive, and the revenue target.")
    goals = fields.Json(
        string="The goals",
        help="What you said would make this a good plan.")
    summary = fields.Json(
        string="Headline numbers",
        help="Profit, cost, revenue, demand served, people and margin, as "
             "they stood when the plan was saved.")

    # ------------------------------------------------------- the decision
    status = fields.Selection(
        STATES, string="Where it stands", default='draft', required=True,
        index=True, tracking=True,
        help="A plan starts as a draft, is proposed, and is then approved or "
             "sent back. Nothing about payroll changes at any point.")
    proposed_by = fields.Many2one(
        'res.users', string="Proposed by", ondelete='set null', tracking=True)
    proposed_at = fields.Datetime(string="Proposed on", tracking=True)
    decided_by = fields.Many2one(
        'res.users', string="Decided by", ondelete='set null', tracking=True)
    decided_at = fields.Datetime(string="Decided on", tracking=True)
    decision_note = fields.Text(
        string="What they said",
        help="The sentence that came with the decision.")
    version_ids = fields.One2many(
        'pb.decision.plan.version', 'plan_id', string="Versions", copy=False)
    version_count = fields.Integer(
        string="Versions kept", compute='_compute_version_count')

    exact_result = fields.Json(
        string="Exact cost",
        help="What this plan's people cost when each one is run through their "
             "own payroll scheme's formulas, rather than through company "
             "averages.")

    is_reference = fields.Boolean(
        string="Compare against this by default", tracking=True,
        help="One plan per company can be the one everything else is "
             "measured against.")
    note = fields.Text(string="Note")
    active = fields.Boolean(default=True)

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    _name_uniq = models.Constraint(
        'unique(company_id, scope_kind, scope_ref, name)',
        "A plan with this name already exists for this scope.")

    # --------------------------------------------------------------- rails
    @api.depends('version_ids')
    def _compute_version_count(self):
        for plan in self:
            plan.version_count = len(plan.version_ids)

    @api.constrains('summary', 'state', 'goals')
    def _check_payload(self):
        """The three blobs are objects or they are nothing.

        "Nothing" has three spellings here and all of them are legitimate:
        `None` for a field never written, `False` for one Odoo read back out of
        a NULL column, and `{}` for an empty plan. Only a value that is
        genuinely THERE and genuinely not an object is refused — a list or a
        number would sail through `fields.Json` and break the room on the next
        read, days later, with nothing to point at.
        """
        for plan in self:
            for value, label in ((plan.state, 'state'),
                                 (plan.goals, 'goals'),
                                 (plan.summary, 'summary')):
                if value and not isinstance(value, dict):
                    raise ValidationError(_(
                        "This plan could not be saved: its %s is not in the "
                        "shape the room writes.", label))

    def _drop_other_references(self):
        """At most one reference plan per company."""
        for plan in self.filtered('is_reference'):
            others = self.sudo().search([
                ('company_id', '=', plan.company_id.id),
                ('is_reference', '=', True),
                ('id', '!=', plan.id),
            ])
            if others:
                others.write({'is_reference': False})

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        plans._drop_other_references()
        return plans

    def write(self, vals):
        # An APPROVED plan is a record of what a board agreed to. Editing its
        # levers afterwards would rewrite that agreement without a trace, so
        # the levers are frozen and the room offers a copy instead. Everything
        # that is ABOUT the decision — the note, the state, who decided —
        # stays writable, or the decision could never be recorded at all.
        frozen = {'state', 'goals', 'summary', 'name', 'scope_kind',
                  'scope_ref', 'company_ids'}
        if frozen & set(vals):
            locked = self.filtered(lambda p: p.status == 'approved')
            if locked:
                raise UserError(_(
                    "\"%s\" has been approved, so its numbers stay as they "
                    "were agreed. Use \"Keep editing a copy\" to carry on "
                    "from here.", locked[0].name))
        res = super().write(vals)
        if vals.get('is_reference'):
            self._drop_other_references()
        return res

    # ------------------------------------------------------- the decision
    def _keep_version(self, label='', extra=None):
        """Freeze everything this plan is, right now."""
        self.ensure_one()
        Version = self.env['pb.decision.plan.version'].sudo()
        number = max(self.version_ids.mapped('number') or [0]) + 1
        snapshot = {
            'state': self.state or {},
            'goals': self.goals or {},
            'summary': self.summary or {},
            'scope': {
                'kind': self.scope_kind,
                'ref': self.scope_ref or '',
                'label': self.scope_label or '',
                'company_ids': self.company_ids.ids or self.company_id.ids,
            },
            'note': self.note or '',
            'status': self.status,
        }
        snapshot.update(extra or {})
        version = Version.create({
            'plan_id': self.id,
            'number': number,
            'name': self.name,
            'label': label or '',
            'snapshot': snapshot,
        })
        old = self.version_ids.sorted(lambda v: v.number)[:-MAX_VERSIONS]
        if old:
            old.sudo().unlink()
        return version

    def _managers(self):
        group = self.env.ref('pb_decision_room.group_decision_manager',
                             raise_if_not_found=False)
        if not group:
            return self.env['res.users'].browse()
        return group.sudo().all_user_ids.filtered(
            lambda u: u.active and (
                not u.company_ids or self.company_id in u.company_ids))

    def action_propose(self, note=''):
        """Hand the plan to whoever approves plans here.

        A person proposing their own plan is ALLOWED — on a small company the
        owner is both — and the record says who did both halves, which is the
        honest version of a control nobody can actually enforce.
        """
        self.ensure_one()
        if self.status == 'approved':
            raise UserError(_("\"%s\" has already been approved.", self.name))
        self.write({
            'status': 'proposed',
            'proposed_by': self.env.user.id,
            'proposed_at': fields.Datetime.now(),
            'decision_note': note or '',
            'decided_by': False,
            'decided_at': False,
        })
        version = self._keep_version(label=_("Proposed"), extra={
            # What could NOT be converted when this was proposed. A decision
            # taken over a missing exchange rate has to say so in its own
            # record rather than be quietly rounded into a number.
            'unconverted': (self.summary or {}).get('unconverted') or [],
        })
        self.message_post(body=_(
            "%(who)s proposed this plan for approval.",
            who=self.env.user.display_name))
        for approver in self._managers():
            self.sudo().activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=approver.id,
                summary=_("Approve the plan \"%s\"", self.name),
                note=_("%(who)s would like a decision on \"%(plan)s\" "
                       "(%(scope)s).",
                       who=self.env.user.display_name, plan=self.name,
                       scope=self.scope_label or ''))
        return version.id

    def _close_activities(self):
        self.sudo().activity_ids.filtered(
            lambda a: a.summary and self.name in a.summary).unlink()

    def action_approve(self, note=''):
        self.ensure_one()
        if not self.env['pb.decision.room']._can_manage():
            raise AccessError(_(
                "Approving a plan is your HR or finance lead's to do. Ask "
                "them to take a look — they will see it waiting on their home "
                "page."))
        self.write({
            'status': 'approved',
            'decided_by': self.env.user.id,
            'decided_at': fields.Datetime.now(),
            'decision_note': note or '',
        })
        self._keep_version(label=_("Approved"), extra={
            'unconverted': (self.summary or {}).get('unconverted') or [],
        })
        self._close_activities()
        self.message_post(body=_(
            "%(who)s approved this plan.%(note)s",
            who=self.env.user.display_name,
            note=(" " + note) if note else ""))
        return True

    def action_reject(self, note=''):
        self.ensure_one()
        if not self.env['pb.decision.room']._can_manage():
            raise AccessError(_(
                "Sending a plan back is your HR or finance lead's to do."))
        self.write({
            'status': 'rejected',
            'decided_by': self.env.user.id,
            'decided_at': fields.Datetime.now(),
            'decision_note': note or '',
        })
        self._close_activities()
        self.message_post(body=_(
            "%(who)s sent this plan back.%(note)s",
            who=self.env.user.display_name,
            note=(" " + note) if note else ""))
        return True

    def action_copy_for_editing(self):
        """A fresh draft that starts exactly where the approved plan ends."""
        self.ensure_one()
        name = _("%s (carrying on)", self.name)
        existing = self.sudo().search_count([
            ('company_id', '=', self.company_id.id),
            ('scope_kind', '=', self.scope_kind),
            ('scope_ref', '=', self.scope_ref or ''),
            ('name', '=', name)])
        if existing:
            name = _("%(name)s (carrying on %(n)s)",
                     name=self.name, n=existing + 1)
        # The three blobs are named EXPLICITLY rather than left to the
        # platform's own copy: a plan that carries on from an approved one and
        # arrives with no levers in it is the most expensive kind of empty.
        return self.copy({
            'name': name,
            'status': 'draft',
            'is_reference': False,
            'state': dict(self.state or {}),
            'goals': dict(self.goals or {}),
            'summary': dict(self.summary or {}),
            'scope_kind': self.scope_kind,
            'scope_ref': self.scope_ref or '',
            'scope_label': self.scope_label or '',
            'company_ids': [(6, 0, self.company_ids.ids)],
            'proposed_by': False, 'proposed_at': False,
            'decided_by': False, 'decided_at': False,
            'decision_note': '',
            'exact_result': False,
        })
