# -*- coding: utf-8 -*-
"""`pb.vendor` and `pb.vendor.agreement` — who we buy people services from, and
what we agreed with them.

A STANDALONE MODEL, DELIBERATELY. `res.partner` on this database is the payment
counterparty of an accounting system, and `vendor_license_core` is the product's
own self-licensing (ledger rule 8 — it is untouchable and shares nothing but a
word with this file). A recruitment agency, a training provider and a health
insurer are none of those things: they are people HR deals with, they have an
owner inside the company, and what matters about them is when the agreement runs
out. So this is its own small register with its own namespace, `pb.vendor.*`.

WHAT THE AGREEMENT STATE MEANS, AND WHY IT IS NEVER TYPED.
`state` is computed from the dates and one flag. A person cannot set an
agreement to "Running" when its end date was last March, and cannot forget to
move it to "Ended" — a heading that asserts something the data is free to
contradict is a heading that is wrong half the time (R68). The one thing a
person DOES say is that an agreement has been replaced, and that is a separate
boolean the renew action writes.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .vendor_common import AGREEMENT_STATES, VENDOR_TYPES, param_int

_logger = logging.getLogger(__name__)

#: How far before the end date the renewal reminder is prefilled. The ALERT
#: horizon is a config parameter; this is only where the default date lands when
#: somebody types an agreement in.
RENEWAL_LEAD_DAYS = 30


class PbVendor(models.Model):
    _name = 'pb.vendor'
    _description = 'Vendor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Who they are', required=True, index=True, tracking=True,
        help='The name you would use in a sentence — "Talentnet", "VietinBank '
             'Insurance".')
    vendor_type = fields.Selection(
        VENDOR_TYPES, string='What they do', required=True, default='services',
        index=True, tracking=True)
    active = fields.Boolean(default=True)

    contact_name = fields.Char(string='Who to ask for')
    contact_email = fields.Char(string='Their email')
    contact_phone = fields.Char(string='Their phone')

    department_id = fields.Many2one(
        'hr.department', string='Team they work with', index=True,
        ondelete='set null',
        help='The team inside the company that uses them most.')
    responsible_user_id = fields.Many2one(
        'res.users', string='Who looks after them', required=True, index=True,
        ondelete='restrict', tracking=True,
        default=lambda self: self.env.user,
        help='The person here who owns this relationship. They are the one who '
             'is told when an agreement is about to run out.')
    country_id = fields.Many2one(
        'res.country', string='Country', index=True, ondelete='set null',
        default=lambda self: self.env.company.country_id)

    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    agreement_ids = fields.One2many(
        'pb.vendor.agreement', 'vendor_id', string='Agreements')
    agreement_count = fields.Integer(
        string='Agreements', compute='_compute_agreements')
    #: The end date that matters — the LIVE agreement's, not the newest row's.
    #: A vendor whose only running agreement ends in March and whose expired one
    #: ended last year must read "March", and sorting by id would say otherwise.
    next_end_date = fields.Date(
        string='Next agreement ends', compute='_compute_agreements', store=True,
        index=True)
    agreement_state = fields.Selection(
        AGREEMENT_STATES, string='Agreement', compute='_compute_agreements',
        store=True, index=True)

    _name_uniq = models.Constraint(
        'unique(name, company_id)',
        'There is already a vendor with that name in this company.')

    # ---------------------------------------------------------------- computes
    @api.depends('agreement_ids.date_end', 'agreement_ids.state',
                 'agreement_ids.active')
    def _compute_agreements(self):
        """The vendor's headline agreement, and THE PROBLEM COMES FIRST.

        The obvious ranking is "the live one, then the one about to end, then
        the dead one", and it is exactly backwards for this screen. A supplier
        with a three-year licence running AND a support contract that lapsed
        last month rendered as "Running", the lapsed row was invisible on the
        board, and the "already run out" figure beside it read zero — over a
        register that had one. That is R80's shape: a chip counting one thing
        over a list showing another, and here the LIST was the one lying.

        So: ended beats ending-soon beats running. A vendor's headline is
        whatever most needs somebody to do something about it, and within a
        band the one that ends soonest — which is the date somebody has to act
        on. `_order` on the child cannot express that, so it is done here in
        Python over a set that is a handful of rows.
        """
        rank = {'expired': 0, 'expiring': 1, 'running': 2, 'draft': 3,
                'renewed': 4}
        for rec in self:
            live = rec.agreement_ids.filtered(lambda a: a.active)
            rec.agreement_count = len(live)
            if not live:
                rec.next_end_date = False
                rec.agreement_state = False
                continue
            best = sorted(
                live,
                key=lambda a: (rank.get(a.state, 9),
                               a.date_end or fields.Date.to_date('9999-12-31')),
            )[0]
            rec.next_end_date = best.date_end
            rec.agreement_state = best.state

    def _compute_display_name(self):
        """Friendly titles are `_compute_display_name` on Odoo 19; `name_get` is
        gone."""
        for rec in self:
            rec.display_name = rec.name or _('New vendor')

    # ------------------------------------------------------------------- rails
    @api.constrains('contact_email')
    def _check_email(self):
        for rec in self:
            raw = rec.contact_email
            # An unset Char reads as False, so empty-check before stripping.
            if not raw:
                continue
            if '@' not in raw or ' ' in raw.strip():
                raise ValidationError(_(
                    "\"%s\" does not look like an email address. Leave it "
                    "empty if you do not have one.", raw))


class PbVendorAgreement(models.Model):
    _name = 'pb.vendor.agreement'
    _description = 'Vendor agreement'
    _inherit = ['mail.thread']
    _order = 'date_end desc, id desc'

    vendor_id = fields.Many2one(
        'pb.vendor', string='Vendor', required=True, index=True,
        ondelete='cascade')
    name = fields.Char(
        string='What it covers', required=True, tracking=True,
        help='A short description — "Agency terms 2026", "Health cover, '
             '120 staff".')
    date_start = fields.Date(
        string='Starts', required=True, tracking=True,
        default=fields.Date.context_today)
    date_end = fields.Date(string='Ends', required=True, tracking=True)
    renewal_date = fields.Date(
        string='Talk about renewing on', tracking=True,
        help='When the conversation about renewing should start. It is filled '
             'in for you thirty days before the end date; move it if that is '
             'too early or too late.')

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    value = fields.Monetary(
        string='What it is worth', currency_field='currency_id',
        help='Optional. The value of the agreement over its whole term, in '
             'whatever currency it was signed in.')

    attachment_ids = fields.Many2many(
        'ir.attachment', 'pb_vendor_agreement_attachment_rel',
        'agreement_id', 'attachment_id', string='Files')
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    is_renewed = fields.Boolean(
        string='Replaced', readonly=True, copy=False,
        help='A newer agreement has taken over from this one.')
    renewed_by_id = fields.Many2one(
        'pb.vendor.agreement', string='Replaced by', readonly=True, copy=False,
        ondelete='set null')
    renewed_from_id = fields.Many2one(
        'pb.vendor.agreement', string='Replaces', readonly=True, copy=False,
        ondelete='set null')

    state = fields.Selection(
        AGREEMENT_STATES, string='Where it is', compute='_compute_state',
        store=True, index=True)
    days_left = fields.Integer(
        string='Days left', compute='_compute_state', store=True)

    company_id = fields.Many2one(
        'res.company', related='vendor_id.company_id', store=True, index=True,
        readonly=True)
    responsible_user_id = fields.Many2one(
        'res.users', related='vendor_id.responsible_user_id', store=True,
        index=True, readonly=True)

    #: The alert stamp. NOT what makes the job idempotent — the search for an
    #: open activity is (R21/R49's shape) — but it is what the screen shows and
    #: what stops a second mail going out the same day.
    last_alert_on = fields.Date(string='Last reminder sent', readonly=True,
                                copy=False)
    escalated_on = fields.Date(string='Escalated on', readonly=True, copy=False)

    # ---------------------------------------------------------------- computes
    @api.depends('date_start', 'date_end', 'is_renewed')
    def _compute_state(self):
        """Never typed. The dates decide, and the one human judgement — "this
        has been replaced" — is a separate flag the renew action writes."""
        today = fields.Date.context_today(self)
        horizon = param_int(self.env,
                            'pb_vendor_access.renewal_horizon_days', 45)
        for rec in self:
            end = rec.date_end
            rec.days_left = (end - today).days if end else 0
            if rec.is_renewed:
                rec.state = 'renewed'
            elif not end:
                rec.state = 'draft'
            elif end < today:
                rec.state = 'expired'
            elif rec.date_start and rec.date_start > today:
                rec.state = 'draft'
            elif rec.days_left <= horizon:
                rec.state = 'expiring'
            else:
                rec.state = 'running'

    def _compute_display_name(self):
        for rec in self:
            vendor = rec.vendor_id.name or ''
            rec.display_name = ('%s — %s' % (vendor, rec.name or '')).strip(' —')

    # ------------------------------------------------------------------- rails
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_(
                    "\"%s\" would end before it starts. Check the two dates.",
                    rec.name or ''))

    @api.onchange('date_end')
    def _onchange_date_end(self):
        for rec in self:
            if rec.date_end and not rec.renewal_date:
                rec.renewal_date = rec.date_end - timedelta(
                    days=RENEWAL_LEAD_DAYS)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('date_end') and not vals.get('renewal_date'):
                end = fields.Date.to_date(vals['date_end'])
                vals['renewal_date'] = end - timedelta(days=RENEWAL_LEAD_DAYS)
        return super().create(vals_list)

    # ------------------------------------------------------------------ renew
    def action_renew(self, vals=None):
        """The new agreement takes over; this one is marked replaced.

        A renewal is a NEW ROW, never an edit of the old one — ruling D1's
        shape, and for the same reason: what was agreed last year is a fact
        about last year, and a screen that overwrites it loses the only record
        of what the old terms were.

        Idempotent by refusal rather than by silence: an agreement that has
        already been replaced says which row replaced it instead of quietly
        making a second one (R100's lesson — a job that skips only OPEN work
        re-does the work that is finished).
        """
        self.ensure_one()
        if self.is_renewed:
            raise UserError(_(
                "\"%(name)s\" has already been replaced by \"%(new)s\". Open "
                "that one to change it.",
                name=self.name, new=self.renewed_by_id.name or _('a newer one')))
        vals = dict(vals or {})
        start = fields.Date.to_date(vals.get('date_start')) or (
            (self.date_end or fields.Date.context_today(self))
            + timedelta(days=1))
        end = fields.Date.to_date(vals.get('date_end'))
        if not end:
            # Same length as the term that is ending, so the prefill is a real
            # proposal rather than a blank the user has to guess at.
            span = ((self.date_end - self.date_start).days
                    if (self.date_end and self.date_start) else 365)
            end = start + timedelta(days=max(span, 1))
        new = self.create({
            'vendor_id': self.vendor_id.id,
            'name': vals.get('name') or self.name,
            'date_start': start,
            'date_end': end,
            'renewal_date': vals.get('renewal_date')
            or (end - timedelta(days=RENEWAL_LEAD_DAYS)),
            'currency_id': vals.get('currency_id') or self.currency_id.id,
            'value': vals.get('value') if vals.get('value') is not None
            else self.value,
            'note': vals.get('note') or '',
            'renewed_from_id': self.id,
        })
        self.write({'is_renewed': True, 'renewed_by_id': new.id})
        self._post(_(
            "Replaced by \"%(new)s\", which runs from %(start)s to %(end)s.",
            new=new.name, start=start, end=end))
        new._post(_("Takes over from \"%s\".", self.name))
        return new

    def _post(self, body):
        """A note is a courtesy and must never be able to affect anything
        (R66's rule, applied to a model that DOES have a chatter)."""
        try:
            self.message_post(body=body)
        except Exception:                       # noqa: BLE001
            _logger.warning('pb.vendor.agreement: could not post a note on %s',
                            self.id, exc_info=True)
