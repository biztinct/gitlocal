# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The expense claim: one approval for one or more receipts (ETP E1, D1/D2).

WHY A NEW MODEL AND NOT THE STOCK EXPENSE (ledger E1/E2). Stock expenses in
this release are approved one by one, an expense submitted by somebody with no
manager is approved by itself, and the engine's adapter mixin declares an
`approval_state` of its own that would collide with the stored one on
`hr.expense`. So the CLAIM is what is sent to the engine — one request for
1..N receipts — and each receipt stays an ordinary stock expense that finance
posts and pays exactly as today.

THE CLAIM DRIVES ITS EXPENSES, NEVER THE OTHER WAY ROUND.
  * sent      → each expense ``approval_state='submitted'`` (written under sudo
                by the portal facade; stock ``action_submit`` is never called,
                it would auto-approve an employee without a manager);
  * approved  → each expense ``_do_approve(check=False)``, as the person who
                decided (stock writes ``manager_id`` = that person);
  * refused   → each expense ``_do_refuse(reason)``;
  * back to draft (fix and resend, take back, sent back) → each expense
                ``_do_reset_approval()``;
  * paid      → read FROM the expenses: once every one is paid
                (`_sync_paid`, called from `hr.expense.write` and on read).

THE ENGINE IS THE ONLY THING THAT APPROVES. `_do_approve` is reached only from
`_after_approval_transition('approved')`, which the shim calls from
`_approval_apply` (route) or the claim's own fallback ladder (no route
published — an HR expense approver presses Approve on the backend form).
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, formatLang

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

EXPENSE_PROCESS_KEY = 'expense'

#: The claim's states (D1). `paid` is reached FROM the expenses, never from a
#: button: every expense of the claim is paid.
CLAIM_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Waiting approval'),
    ('approved', 'Approved'),
    ('refused', 'Refused'),
    ('paid', 'Paid'),
]

#: A stock expense state that counts as "paid" for the claim (D1).
PAID_EXPENSE_STATES = ('paid', 'done')

#: A receipt older than this at submission is a fact a route may ask about.
OLD_RECEIPT_DAYS = 30

#: Context key carrying the refusal reason into the transition hook.
REFUSAL_CTX = 'pb_expense_refusal'

#: NO `date_field` (read the long comment in pb_training/claim_approval.py):
#: the engine resolves who holds a seat ON that date, and a receipt from last
#: month must be decided by whoever holds the finance seat NOW.
register_chain(
    'pb.expense.claim', EXPENSE_PROCESS_KEY,
    submit_state='submitted',
    driven=('approved',),
    employee_field='employee_id',
    amount_field='total',
    currency_field='currency_id',
)


def expense_route(env):
    """The default route (D2): the person's manager, then the finance seat."""
    _ = env._
    return route(manager_step(_('Their manager')),
                 role_step(_('Finance approver'), 'finance'))


class PbExpenseClaim(models.Model):
    _name = 'pb.expense.claim'
    _description = 'Expense claim'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'id desc'

    _approval_process_key = EXPENSE_PROCESS_KEY

    #: The ladder the claim keeps for itself when no route is published for
    #: its company (the shim is dormant then). An HR expense approver decides
    #: from the backend form. Under a route the shim takes every press and the
    #: route decides (AM84).
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): 'hr_expense.group_hr_expense_team_approver',
        ('submitted', 'refused'): 'hr_expense.group_hr_expense_team_approver',
    }
    _approval_dead_states = ('refused', 'paid')

    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True, default='/', index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='restrict', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', related='company_id.currency_id',
        store=True, readonly=True)
    expense_ids = fields.One2many('hr.expense', 'pb_claim_id',
                                  string='Receipts')
    receipt_count = fields.Integer(string='Number of receipts', compute='_compute_total',
                                   store=True)
    total = fields.Monetary(string='Total', compute='_compute_total',
                            store=True, currency_field='currency_id')
    state = fields.Selection(CLAIM_STATES, string='Status', default='draft',
                             required=True, index=True, tracking=True,
                             copy=False)
    note = fields.Text(string='Note')
    refusal_reason = fields.Text(
        string='Why it was refused', copy=False, tracking=True,
        help='Written by the approver who refused or sent it back. The '
             'employee sees it on their claim.')
    submitted_on = fields.Datetime(string='Sent on', readonly=True, copy=False)
    decided_on = fields.Datetime(string='Decided on', readonly=True,
                                 copy=False)
    paid_on = fields.Date(string='Paid on', readonly=True, copy=False)

    # ------------------------------------------------------------ computes
    @api.depends('expense_ids', 'expense_ids.total_amount_currency')
    def _compute_total(self):
        for rec in self:
            exps = rec.expense_ids
            rec.receipt_count = len(exps)
            rec.total = sum(exps.mapped('total_amount_currency'))

    # ------------------------------------------------------------ the ORM
    @api.model_create_multi
    def create(self, vals_list):
        Seq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == '/':
                vals['name'] = Seq.next_by_code('pb.expense.claim') or '/'
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_open(self):
        for rec in self:
            if rec.state in ('submitted', 'approved', 'paid'):
                raise UserError(self.env._(
                    "Claim %s is sent, approved or paid, so it cannot be "
                    "deleted.", rec.name))

    # =====================================================================
    #  the ladder hooks (route and fallback alike)
    # =====================================================================
    def _before_approval_transition(self, to_state):
        res = super()._before_approval_transition(to_state)
        if to_state == 'submitted':
            for rec in self:
                rec._check_ready()
        return res

    def _check_ready(self):
        """Every receipt has an amount, a category and its file (D3)."""
        self.ensure_one()
        _ = self.env._
        exps = self.sudo().expense_ids
        if not exps:
            raise UserError(_("Add at least one receipt before you send the "
                              "claim."))
        for exp in exps:
            if exp.currency_id.compare_amounts(exp.total_amount_currency or 0.0,
                                               0.0) <= 0:
                raise UserError(_("Every receipt needs an amount above zero. "
                                  "Check \"%s\".", exp.name))
            if not exp.product_id:
                raise UserError(_("Every receipt needs to say what it was for. "
                                  "Check \"%s\".", exp.name))
            if not (exp.message_main_attachment_id or exp.attachment_ids):
                raise UserError(_("Every receipt needs its photo or PDF. Add "
                                  "it to \"%s\", or remove that receipt.",
                                  exp.name))
        return True

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        now = fields.Datetime.now()
        for rec in self:
            claim = rec.sudo()
            if to_state == 'submitted':
                claim.write({'submitted_on': now, 'decided_on': False})
            elif to_state == 'approved':
                # As the person who decided: sudo keeps env.user, so stock's
                # `_do_approve` writes them as `manager_id` (D3).
                claim.expense_ids.filtered(
                    lambda e: e.state in ('draft', 'submitted')
                )._do_approve(check=False)
                claim.write({'decided_on': now})
            elif to_state == 'refused':
                reason = (self.env.context.get(REFUSAL_CTX)
                          or claim.refusal_reason or '')
                todo = claim.expense_ids.filtered(
                    lambda e: e.approval_state != 'refused')
                if todo:
                    todo._do_refuse(reason or self.env._('No reason given'))
                claim.write({'decided_on': now,
                             'refusal_reason': reason or False})
        return res

    def _pb_back_to_draft(self, reason=None):
        """The expenses of a claim that is a draft again (fix and resend,
        take back, sent back) lose their approval, so they can be edited
        and sent again. Sudo: the caller passed the ownership guard or is
        the engine."""
        for claim in self.sudo():
            exps = claim.expense_ids.filtered('approval_state')
            if exps:
                exps._do_reset_approval()
            vals = {'decided_on': False}
            if reason is not None:
                vals['refusal_reason'] = reason or False
            claim.write(vals)
        return True

    # =====================================================================
    #  the engine's answers (adapter contract, on top of the shim)
    # =====================================================================
    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'refusal_reason': reason or False})
        return super(PbExpenseClaim, self.with_context(
            **{REFUSAL_CTX: reason or ''}))._approval_reject(request, reason)

    def _approval_return(self, request, reason):
        """Sent back by an approver: a draft again, with the reason shown."""
        self.ensure_one()
        res = super()._approval_return(request, reason)
        self._pb_back_to_draft(reason=reason or '')
        return res

    def _approval_withdraw(self, request, reason):
        """Taken back (by the person, from their page or the inbox): a draft
        again. The shim does not mirror a withdrawal on the record (ledger
        E8), so the claim does it itself."""
        self.ensure_one()
        if self.state == 'submitted':
            self._chain_engine_write('draft')
            self._chain_log('submitted', 'draft', reason or '')
        self._pb_back_to_draft()
        return True

    def _approval_manager_uids(self):
        """"Their manager" for an expense is the expense approver HR set on
        the employee, else their line manager's login (stock's own order of
        preference). A login that is archived or is an employee login cannot
        decide in the inbox, so it is not a seat — the request then stops
        with the engine's plain sentence and HR fixes the employee record."""
        self.ensure_one()
        emp = self._chain_employee()
        user = emp.sudo().expense_manager_id or emp.sudo().parent_id.user_id
        return user.filtered(lambda u: u.active and not u.share).ids

    def _chain_title(self):
        self.ensure_one()
        _ = self.env._
        rec = self.sudo()
        n = len(rec.expense_ids)
        who = rec.employee_id.name or ''
        if n == 1:
            return _("Expense claim · %(who)s · 1 receipt", who=who)
        return _("Expense claim · %(who)s · %(n)s receipts", who=who, n=n)

    def _chain_company(self):
        self.ensure_one()
        return self.sudo().company_id[:1] or self.env.company

    def _pb_receipt_facts(self):
        """The facts of the receipts as they are now (sudo — the maker is an
        employee login with no right on expenses)."""
        self.ensure_one()
        rec = self.sudo()
        exps = rec.expense_ids
        today = fields.Date.context_today(rec)
        return {
            'n': len(exps),
            'categories': ', '.join(sorted({p for p in exps.mapped('product_id.name') if p})),
            'has_file': bool(exps) and all(
                bool(e.message_main_attachment_id or e.attachment_ids) for e in exps),
            'old': any(e.date and (today - e.date).days > OLD_RECEIPT_DAYS
                       for e in exps),
        }

    def _chain_facts(self):
        self.ensure_one()
        rec = self.sudo()
        facts = rec._pb_receipt_facts()
        # THE UNIT IS THE CURRENCY (AM25), so "over 5,000,000" means dong to
        # somebody reading the route anywhere.
        unit = rec.currency_id.name or ''
        return {
            'amount': {'value': float(rec.total or 0.0), 'unit': unit},
            'receipts': {'value': facts['n'], 'unit': self.env._('receipts')},
            'categories': {'value': facts['categories'], 'unit': ''},
            'has_receipt_file': {'value': facts['has_file'], 'unit': ''},
            'over_30_days': {'value': facts['old'], 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        _ = self.env._
        return {
            'amount': {'type': 'decimal', 'label': _('What it comes to')},
            'receipts': {'type': 'int', 'label': _('How many receipts')},
            'categories': {'type': 'char', 'label': _('What they were for')},
            'has_receipt_file': {'type': 'bool',
                                 'label': _('Every receipt has its photo')},
            'over_30_days': {'type': 'bool',
                             'label': _('A receipt is more than 30 days old')},
        }

    def _chain_revision_values(self):
        """What an approver agrees to: these receipts, these amounts, these
        files (D2). Never `write_date` (AM32)."""
        self.ensure_one()
        rec = self.sudo()
        return {
            'receipts': sorted(
                [exp.id, round(float(exp.total_amount_currency or 0.0), 2),
                 exp.message_main_attachment_id.id or 0]
                for exp in rec.expense_ids),
            'currency': rec.currency_id.id,
        }

    def _approval_detail(self, request):
        self.ensure_one()
        _ = self.env._
        rec = self.sudo()
        env = self.env
        facts = rec._pb_receipt_facts()
        rows = [{
            'head': exp.product_id.name or exp.name or '',
            'sub': format_date(env, exp.date) if exp.date else '',
            'cells': [formatLang(env, exp.total_amount_currency,
                                 currency_obj=exp.currency_id)],
            'tone': 'on',
        } for exp in rec.expense_ids[:20]]
        chips = [
            {'label': _('Total'),
             'value': formatLang(env, rec.total, currency_obj=rec.currency_id)},
            {'label': _('Receipts'), 'value': str(facts['n'])},
        ]
        trips = rec.expense_ids.mapped('pb_trip_id') \
            if 'pb_trip_id' in env['hr.expense']._fields else None
        if trips:
            chips.append({'label': _('Trip'),
                          'value': ', '.join(trips.mapped('name'))})
        if facts['old']:
            chips.append({'label': _('Careful'),
                          'value': _('a receipt is more than 30 days old')})
        return {'title': _('What they paid for'), 'columns': [_('Amount')],
                'rows': rows, 'chips': chips, 'note': rec.note or ''}

    # =====================================================================
    #  paid — read from the expenses
    # =====================================================================
    def _sync_paid(self):
        """An approved claim whose every expense is paid reads "Paid" (D1).
        Cheap: only approved claims are looked at."""
        for claim in self.sudo().filtered(
                lambda c: c.state == 'approved' and c.expense_ids):
            if all(e.state in PAID_EXPENSE_STATES for e in claim.expense_ids):
                claim._chain_engine_write('paid')
                claim.write({'paid_on': fields.Date.context_today(claim)})
                claim._chain_log('approved', 'paid', '')
        return True

    # =====================================================================
    #  the backend form's buttons (admin fallback, D10)
    # =====================================================================
    def action_submit(self):
        for rec in self:
            rec._advance_state('submitted')
        return True

    def action_approve(self):
        for rec in self:
            rec._advance_state('approved')
        return True

    def action_refuse(self):
        for rec in self:
            if not (rec.refusal_reason or '').strip():
                raise UserError(self.env._(
                    "Write why it is refused first. The employee sees it on "
                    "their claim."))
            rec.with_context(**{REFUSAL_CTX: rec.refusal_reason}) \
                .action_refuse_chain(rec.refusal_reason)
        return True

    # =====================================================================
    #  the default route
    # =====================================================================
    @api.model
    def _approval_seed_default(self, company):
        """Lay "Their manager → Finance approver" for one company (D2, cloned
        from pb_business_trip_approval.py). Idempotent."""
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'finance',
            ['om_hr_payroll.group_hr_payroll_manager',
             'hr_expense.group_hr_expense_manager'])
        return Seed.lay(
            company, EXPENSE_PROCESS_KEY, 'Expense claims',
            expense_route(self.env),
            binding_note='The route every expense claim follows unless a part '
                         'of the business is given its own.',
            model_name='pb.expense.claim',
            role_keys=('finance',),
            reason='Set up when expense claims were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.expense.claim']._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_me_expense: %s has no expense route',
                              company.name)
    return done
