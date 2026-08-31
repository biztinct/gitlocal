# -*- coding: utf-8 -*-
"""One thing the company owns and lends out.

A laptop and an email account are the same record here, and that is deliberate:
they are both something a person is given on their first day and something
somebody has to take back on their last. The only place the two part company is
the state ladder — a laptop goes to repair and eventually to scrap, an email
account is simply switched off.

THE CODE. `VN-LT-00042` is read left to right: the country it lives in, the kind
of thing it is, and its running number IN THAT COUNTRY. The number is per
country and not per category on purpose — an inventory is counted by the office
that holds it, and a code that restarts at 1 for every new category makes two
different things look like the same item.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .asset_common import (
    ASSET_KINDS, ASSET_STATES, DIGITAL_STATES, TANGIBLE_STATES,
    state_label,
)

_logger = logging.getLogger(__name__)

#: The `ir.sequence` code one country's numbering lives under.
SEQ_PREFIX = 'pb.asset.sequence.'


class PbAsset(models.Model):
    _name = 'pb.asset'
    _description = 'Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code desc, id desc'

    code = fields.Char(
        string='Asset code', readonly=True, copy=False, index=True,
        help='Given out by Payobook when the item is added. It never changes.')
    name = fields.Char(string='What it is', required=True, tracking=True)
    category_id = fields.Many2one(
        'pb.asset.category', string='Category', required=True, index=True,
        ondelete='restrict', tracking=True)
    kind = fields.Selection(
        ASSET_KINDS, string='Kind', related='category_id.kind', store=True,
        index=True, readonly=True)
    country_id = fields.Many2one(
        'res.country', string='Country', required=True, index=True,
        tracking=True,
        help='Where the item lives. It sets the first part of the asset code '
             'and cannot be changed afterwards.')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    state = fields.Selection(
        ASSET_STATES, string='Status', required=True, default='spare',
        index=True, tracking=True)
    current_employee_id = fields.Many2one(
        'hr.employee', string='With', compute='_compute_current', store=True,
        index=True, readonly=True)
    assignment_ids = fields.One2many(
        'pb.asset.assignment', 'asset_id', string='Who has had it')
    request_ids = fields.One2many(
        'pb.asset.request', 'asset_id', string='Requests')

    serial = fields.Char(
        string='Serial / address',
        help='The serial number, the email address, the phone number or the '
             'licence key — whatever identifies this one item.')
    model_name = fields.Char(string='Make and model')
    is_reused = fields.Boolean(
        string='Passed on', help='This item has been used by somebody before.')
    purchase_date = fields.Date(string='Bought on')
    delivery_date = fields.Date(string='Arrived on')
    warranty_end = fields.Date(string='Warranty ends')
    warranty_state = fields.Selection(
        [('none', 'No warranty date'), ('ok', 'In warranty'),
         ('soon', 'Ending soon'), ('over', 'Out of warranty')],
        string='Warranty', compute='_compute_warranty')

    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    cost = fields.Monetary(string='Cost', currency_field='currency_id')
    cost_usd = fields.Float(
        string='Cost (USD)', compute='_compute_cost_usd', digits=(16, 2),
        help='Shown for comparison only. Payobook keeps the original amount.')

    invoice_ref = fields.Char(string='Invoice reference')
    supplier_note = fields.Char(
        string='Bought from',
        help='Who supplied it. A proper supplier record comes later.')
    movable_note = fields.Char(
        string='Where it can go',
        help='Anything worth knowing about moving it — “desk only”, “travels '
             'with the person”.')
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    # ---------------------------------------------------------------- computes
    @api.depends('assignment_ids.state', 'assignment_ids.employee_id')
    def _compute_current(self):
        for rec in self:
            open_one = rec.assignment_ids.filtered(
                lambda a: a.state == 'open')[:1]
            rec.current_employee_id = open_one.employee_id.id or False

    @api.depends('warranty_end')
    def _compute_warranty(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.warranty_end:
                rec.warranty_state = 'none'
            elif rec.warranty_end < today:
                rec.warranty_state = 'over'
            elif (rec.warranty_end - today).days <= 60:
                rec.warranty_state = 'soon'
            else:
                rec.warranty_state = 'ok'

    @api.depends('cost', 'currency_id')
    def _compute_cost_usd(self):
        """Display only, and never stored: a rate read today must not be
        remembered as a fact about a purchase made three years ago.

        NO RATE MEANS NO NUMBER. When the database has no live rate between the
        two currencies, Odoo answers 1.0 for both and `_convert` hands back the
        amount UNCHANGED — so "32,000,000 ₫" is presented as "32,000,000 USD",
        which is not a rounding error, it is a lie by a factor of twenty-six
        thousand. The parity test below is what catches it: two DIFFERENT
        currencies reported at the same rate means nobody has told this database
        what a dong is worth, and the honest answer is to say nothing.
        """
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        today = fields.Date.today()
        for rec in self:
            if not rec.cost or not rec.currency_id or not usd:
                rec.cost_usd = 0.0
                continue
            if rec.currency_id == usd:
                rec.cost_usd = rec.cost
                continue
            company = rec.company_id or self.env.company
            try:
                scoped = rec.currency_id.with_company(company)
                target = usd.with_company(company)
                if not scoped.rate or not target.rate \
                        or scoped.rate == target.rate:
                    rec.cost_usd = 0.0
                    continue
                rec.cost_usd = scoped._convert(rec.cost, target, company, today)
            except Exception:       # noqa: BLE001 — a missing rate, not a bug
                rec.cost_usd = 0.0

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ('%s — %s' % (rec.code, rec.name)
                                if rec.code else (rec.name or _('Asset')))

    @property
    def state_word(self):
        self.ensure_one()
        return state_label(self.kind, self.state)

    # ------------------------------------------------------------ constraints
    @api.constrains('state', 'kind')
    def _check_state_fits_kind(self):
        for rec in self:
            allowed = DIGITAL_STATES if rec.kind == 'digital' \
                else TANGIBLE_STATES
            if rec.state not in allowed:
                raise ValidationError(_(
                    "“%(what)s” cannot be %(state)s. A %(kind)s item only goes "
                    "to: %(allowed)s.",
                    what=rec.name or rec.code or _('this item'),
                    state=state_label(rec.kind, rec.state),
                    kind=_('digital') if rec.kind == 'digital'
                    else _('physical'),
                    allowed=', '.join(
                        state_label(rec.kind, s) for s in allowed)))

    # ------------------------------------------------------------------ codes
    @api.model
    def _sequence_for(self, country):
        """This country's running number, made the first time it is needed."""
        cc = (country.code or 'XX').upper()
        code = SEQ_PREFIX + cc
        Seq = self.env['ir.sequence'].sudo()
        seq = Seq.search([('code', '=', code)], limit=1)
        if not seq:
            seq = Seq.create({
                'name': _('Asset numbers — %s', country.name or cc),
                'code': code,
                'implementation': 'standard',
                'padding': 5,
                'number_next': 1,
                'number_increment': 1,
                # Company-less on purpose: the numbering belongs to the
                # country, and a company-stamped sequence disappears behind the
                # standard company rule for everyone else (R8).
                'company_id': False,
            })
        return seq

    @api.model
    def _build_code(self, country, category):
        number = self._sequence_for(country).next_by_id()
        return '%s-%s-%s' % ((country.code or 'XX').upper(),
                             (category.code or 'XX').upper(), number)

    @api.model_create_multi
    def create(self, vals_list):
        Country = self.env['res.country']
        Category = self.env['pb.asset.category']
        for vals in vals_list:
            if vals.get('code'):
                continue
            country = Country.browse(vals.get('country_id')).exists()
            category = Category.browse(vals.get('category_id')).exists()
            if country and category:
                vals['code'] = self._build_code(country, category)
        records = super().create(vals_list)
        for rec in records:
            rec.message_post(body=_("Added to the register as %s.", rec.code))
        return records

    def write(self, vals):
        if 'country_id' in vals:
            for rec in self:
                if rec.code and rec.country_id.id != vals['country_id']:
                    raise UserError(_(
                        "The country is part of the asset code, so it cannot "
                        "be changed. Add the item again under the right "
                        "country and scrap this one."))
        return super().write(vals)

    # ---------------------------------------------------------------- actions
    def action_assign(self, employee_id, condition_out=None, notes=None):
        """Hand this item to somebody. One holder at a time, always."""
        self.ensure_one()
        employee = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not employee:
            raise UserError(_("Choose the person first."))
        if self.state in ('scrapped', 'to_scrap', 'deactivated'):
            raise UserError(_(
                "%(what)s is %(state)s, so it cannot be given to anybody.",
                what=self.display_name, state=self.state_word))
        if self.assignment_ids.filtered(lambda a: a.state == 'open'):
            raise UserError(_(
                "%(what)s is already with %(who)s. Return it first, or use "
                "Transfer to move it straight across.",
                what=self.display_name,
                who=self.current_employee_id.name or _('somebody')))
        assignment = self.env['pb.asset.assignment'].create({
            'asset_id': self.id,
            'employee_id': employee.id,
            'assigned_date': fields.Date.today(),
            'condition_out': condition_out or False,
            'notes': notes or False,
            'company_id': (self.company_id or employee.company_id
                           or self.env.company).id,
        })
        self.state = 'assigned'
        self.message_post(body=_(
            "Given to %(who)s.%(cond)s", who=employee.name,
            cond=(_(" Condition when it went out: %s.", condition_out)
                  if condition_out else '')))
        return assignment

    def action_transfer(self, employee_id, condition_in=None,
                        condition_out=None):
        """Straight from one person to the next — one click, two facts kept."""
        self.ensure_one()
        open_one = self.assignment_ids.filtered(lambda a: a.state == 'open')[:1]
        if open_one:
            open_one.action_return(condition_in=condition_in, quiet=True)
        return self.action_assign(employee_id, condition_out=condition_out)

    def action_set_state(self, state):
        self.ensure_one()
        allowed = DIGITAL_STATES if self.kind == 'digital' \
            else TANGIBLE_STATES
        if state not in allowed:
            raise UserError(_(
                "A %(kind)s item cannot be %(state)s.",
                kind=_('digital') if self.kind == 'digital' else _('physical'),
                state=state_label(self.kind, state)))
        if state == 'assigned' and not self.current_employee_id:
            raise UserError(_(
                "Nobody has this item, so it cannot be marked as given out. "
                "Use Give to someone instead."))
        if state != 'assigned':
            open_one = self.assignment_ids.filtered(
                lambda a: a.state == 'open')[:1]
            if open_one:
                open_one.action_return(quiet=True)
        was = self.state_word
        self.state = state
        self.message_post(body=_(
            "Status changed from %(was)s to %(now)s.",
            was=was, now=self.state_word))
        return True

    # ------------------------------------------------------ the leaver's check
    @api.model
    def open_items_for(self, employee_id):
        """Everything this person is still holding.

        THE SIGNATURE P4 CALLS. Returns::

            {'tangible': [{'id', 'code', 'name', 'category', 'assignment_id',
                           'since', 'serial'}, ...],
             'digital':  [ ...same shape... ],
             'total': <int>,
             'employee': <name>}

        `tangible` is what has to come back before a final settlement is paid;
        `digital` is what has to be switched off. Read under sudo on purpose:
        the answer is a gate, and a gate that a reader's own access can soften
        is not a gate.
        """
        employee = self.env['hr.employee'].sudo().browse(
            int(employee_id or 0)).exists()
        out = {'tangible': [], 'digital': [], 'total': 0,
               'employee': employee.name or ''}
        if not employee:
            return out
        open_rows = self.env['pb.asset.assignment'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
        ])
        for row in open_rows:
            asset = row.asset_id
            item = {
                'id': asset.id,
                'code': asset.code or '',
                'name': asset.name or '',
                'category': asset.category_id.name or '',
                'assignment_id': row.id,
                'since': str(row.assigned_date) if row.assigned_date else '',
                'serial': asset.serial or '',
            }
            out['digital' if asset.kind == 'digital' else 'tangible'].append(
                item)
        # A digital item can be live on somebody's name without an assignment
        # row — an email account switched on by IT and never formally issued.
        live = self.sudo().search([
            ('kind', '=', 'digital'),
            ('state', '=', 'assigned'),
            ('current_employee_id', '=', employee.id),
        ])
        seen = {i['id'] for i in out['digital']}
        for asset in live:
            if asset.id in seen:
                continue
            out['digital'].append({
                'id': asset.id, 'code': asset.code or '',
                'name': asset.name or '',
                'category': asset.category_id.name or '',
                'assignment_id': 0, 'since': '',
                'serial': asset.serial or '',
            })
        out['total'] = len(out['tangible']) + len(out['digital'])
        return out

    @api.model
    def find_spare(self, category_id, country_id=None):
        """The oldest spare of this kind — first in, first out."""
        domain = [('category_id', '=', int(category_id)),
                  ('state', '=', 'spare'), ('active', '=', True)]
        if country_id:
            domain.append(('country_id', '=', int(country_id)))
        return self.search(domain, order='purchase_date asc, id asc', limit=1)
