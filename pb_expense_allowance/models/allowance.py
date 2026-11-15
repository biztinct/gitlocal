# -*- coding: utf-8 -*-
"""`pb.expense.allowance` — a yearly limit per kind of expense.

Cloned from `pb.training.allowance` (pb_training/models/allowance.py): a
company figure per year per category, an optional figure for one person that
WINS over it. The arithmetic is ONE answer used everywhere
(`facts_for`): limit, used (approved and paid claims), waiting (claims sent,
not decided), left. A receipt counts in the year of its own date.

AS THE SYSTEM. The person whose limit it is holds no right on this table and
must still see their own figures on their own page; every search below names
the employee, the category and the year explicitly.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang

USED_STATES = ('approved', 'paid')
WAITING_STATES = ('submitted',)


class PbExpenseAllowance(models.Model):
    _name = 'pb.expense.allowance'
    _description = 'Yearly claim limit'
    _order = 'year desc, product_id, employee_id, id desc'

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, default=lambda self: self.env.company)
    year = fields.Integer(string='Year', required=True, index=True,
                          default=lambda self: fields.Date.today().year)
    product_id = fields.Many2one(
        'product.product', string='Kind of expense', required=True, index=True,
        domain=[('can_be_expensed', '=', True)], ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Just for', index=True, ondelete='cascade',
        help='Leave it empty and this is the limit for everybody in the company. '
             'Name somebody and it is theirs alone, and it wins over the company '
             'figure.')
    amount = fields.Monetary(string='Yearly limit', required=True,
                             currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True,
                                  default=lambda self: self.env.company.currency_id)
    note = fields.Char(string='Why this figure')
    active = fields.Boolean(default=True)

    _uniq_allowance = models.Constraint(
        'unique (company_id, year, product_id, employee_id)',
        'There is already a limit for that kind of expense, that year and that '
        'person. Change the one that is there.')

    @api.constrains('amount', 'year')
    def _check_values(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("A yearly limit cannot be below zero. Set it "
                                        "to zero if nobody may claim it."))
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_("%s does not look like a year.", rec.year))

    @api.constrains('company_id', 'year', 'product_id', 'employee_id')
    def _check_one_company_row(self):
        """The half the unique index cannot reach (NULLs are distinct)."""
        for rec in self:
            if rec.employee_id:
                if rec.employee_id.sudo().company_id not in (rec.company_id, False) \
                        and rec.employee_id.sudo().company_id:
                    raise ValidationError(_(
                        "%(who)s works for another company, so their limit cannot be "
                        "set under %(here)s.", who=rec.employee_id.sudo().name or '',
                        here=rec.company_id.name or ''))
                continue
            clash = self.sudo().search([
                ('id', '!=', rec.id), ('employee_id', '=', False),
                ('company_id', '=', rec.company_id.id), ('year', '=', rec.year),
                ('product_id', '=', rec.product_id.id)], limit=1)
            if clash:
                raise ValidationError(_(
                    "There is already a company limit for %(what)s in %(year)s. "
                    "Change that one rather than adding a second.",
                    what=rec.product_id.name or '', year=rec.year))

    def _compute_display_name(self):
        for rec in self:
            who = rec.employee_id.sudo().name or rec.company_id.name or ''
            rec.display_name = '%s · %s · %s' % (rec.product_id.name or '', who, rec.year)

    # =====================================================================
    #  the one question
    # =====================================================================
    @api.model
    def limit_for(self, employee, product, year):
        """The row that governs one person, one kind of expense, one year."""
        emp = employee.sudo()
        if not emp or not product:
            return self.sudo().browse()
        mine = self.sudo().search([('employee_id', '=', emp.id), ('year', '=', int(year)),
                                   ('product_id', '=', product.id)], limit=1)
        if mine:
            return mine
        return self.sudo().search([('employee_id', '=', False),
                                   ('company_id', '=', emp.company_id.id),
                                   ('year', '=', int(year)),
                                   ('product_id', '=', product.id)], limit=1)

    @api.model
    def facts_for(self, employee, product, year, skip_claim=None):
        """{'row', 'limit', 'used', 'waiting', 'left', 'currency', 'year'} or
        None when no limit governs it. `skip_claim` is the claim being
        weighed, which is never counted as already used."""
        row = self.limit_for(employee, product, year)
        if not row:
            return None
        Exp = self.env['hr.expense'].sudo()
        base = [('employee_id', '=', employee.id), ('product_id', '=', product.id),
                ('date', '>=', '%s-01-01' % int(year)), ('date', '<=', '%s-12-31' % int(year)),
                ('pb_claim_id', '!=', False)]
        if skip_claim:
            base.append(('pb_claim_id', '!=', skip_claim.id))
        used = sum(Exp.search(base + [('pb_claim_id.state', 'in', USED_STATES)])
                   .mapped('total_amount_currency'))
        waiting = sum(Exp.search(base + [('pb_claim_id.state', 'in', WAITING_STATES)])
                      .mapped('total_amount_currency'))
        cur = row.currency_id
        return {'row': row, 'limit': row.amount, 'used': cur.round(used),
                'waiting': cur.round(waiting),
                'left': cur.round(max(row.amount - used - waiting, 0.0)),
                'currency': cur, 'year': int(year)}

    @api.model
    def money(self, amount, currency):
        return formatLang(self.env, amount or 0.0, currency_obj=currency)

    @api.model
    def refusal(self, product, facts, asked):
        """The sentence with the arithmetic in it."""
        m = lambda v: self.money(v, facts['currency'])   # noqa: E731
        if facts['waiting']:
            return _(
                "That is more than is left for %(what)s this year. Your limit for "
                "%(year)s is %(limit)s, %(used)s is already approved and %(waiting)s "
                "is waiting approval, so %(left)s is left and this comes to %(asked)s.",
                what=product.name or '', year=facts['year'], limit=m(facts['limit']),
                used=m(facts['used']), waiting=m(facts['waiting']), left=m(facts['left']),
                asked=m(asked))
        return _(
            "That is more than is left for %(what)s this year. Your limit for %(year)s "
            "is %(limit)s, %(used)s is already approved, so %(left)s is left and this "
            "comes to %(asked)s.",
            what=product.name or '', year=facts['year'], limit=m(facts['limit']),
            used=m(facts['used']), left=m(facts['left']), asked=m(asked))

    @api.model
    def my_limits(self, employee):
        """The person's own limits this year (caller's own employee only)."""
        emp = employee.sudo()[:1] if employee else employee
        if not emp or emp.user_id.id != self.env.uid:
            return []
        year = fields.Date.context_today(self).year
        rows = self.sudo().search([('year', '=', year), '|',
                                   ('employee_id', '=', emp.id),
                                   '&', ('employee_id', '=', False),
                                   ('company_id', '=', emp.company_id.id)])
        out = []
        for product in rows.mapped('product_id'):
            facts = self.facts_for(emp, product, year)
            if not facts:
                continue
            limit = facts['limit'] or 0.0
            spent = facts['used'] + facts['waiting']
            pct = int(max(0.0, min(100.0, spent / limit * 100.0))) if limit > 0 else 100
            out.append({'what': product.name or '',
                        'limit': self.money(facts['limit'], facts['currency']),
                        'used': self.money(facts['used'], facts['currency']),
                        'waiting': self.money(facts['waiting'], facts['currency'])
                        if facts['waiting'] else '',
                        'left': self.money(facts['left'], facts['currency']),
                        'pct': pct, 'none_left': not facts['left']})
        return out
