# -*- coding: utf-8 -*-
"""`pb.cost.transfer` — "home paid, host is charged", written down.

WHAT IT IS AND WHAT IT IS NOT
-----------------------------
It IS an internal statement that one entity in the group carried a cost that
belongs to another: a line in reports, a figure in the Explorer, a row in an
export somebody sends to finance.

It is NOT an accounting entry, and nothing here ever becomes one. The owner's
ruling stands: this product has no accounting connection. A transfer that
posted a journal entry would be exactly the irreversible thing the whole
programme has stayed away from.

RULE 7 LIVES HERE TOO
---------------------
The amount is stored in the currency the payroll was paid in — always, only,
and never converted on the way in. `amount_in(currency)` converts at READ time
through `pb.fx`, hands back the rate it used, and says so when nobody has
priced the pair rather than quietly using 1.0.
"""

from odoo import _, api, fields, models


class PbCostTransfer(models.Model):
    _name = 'pb.cost.transfer'
    _description = 'Charged between entities'
    _order = 'date_from desc, id desc'

    person_id = fields.Many2one('pb.person', string='Person', index=True,
                                ondelete='set null')
    home_employee_id = fields.Many2one(
        'hr.employee', string='Employment', index=True, ondelete='cascade')
    payslip_id = fields.Many2one(
        'hr.payslip', string='Payslip', index=True, ondelete='cascade')
    segment_ids = fields.Many2many(
        'pb.work.segment', string='Days this covers')

    from_company_id = fields.Many2one(
        'res.company', string='Charged from', required=True, index=True,
        ondelete='cascade',
        help="The entity that actually paid — the person's home.")
    to_company_id = fields.Many2one(
        'res.company', string='Charged to', required=True, index=True,
        ondelete='cascade',
        help="The entity whose days these were.")
    # `company_id` is the PAYING entity, so the platform's own company rules
    # scope a transfer to the books that carry it.
    company_id = fields.Many2one(
        'res.company', string='Company', related='from_company_id',
        store=True, readonly=True, index=True)

    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        help="The money this was paid in. Nothing is ever stored converted.")
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    share = fields.Float(string='Share of the month', digits=(16, 6))

    date_from = fields.Date(string='From', required=True, index=True)
    date_to = fields.Date(string='To', required=True)
    month = fields.Date(string='Month', compute='_compute_month', store=True,
                        index=True)
    note = fields.Text(string='Notes')

    @api.depends('date_from')
    def _compute_month(self):
        for row in self:
            row.month = row.date_from.replace(day=1) if row.date_from else False

    def _compute_display_name(self):
        for row in self:
            row.display_name = _(
                "%(amount)s charged to %(company)s",
                amount=row.currency_id.format(row.amount)
                if row.currency_id else '%s' % row.amount,
                company=row.to_company_id.name or '')

    # ------------------------------------------------------------- read time
    @api.model
    def amount_in(self, rows, currency, on_date=None):
        """`{id: (value, known, meta)}` in one currency, converted at read time.

        Uses the group's own conversion service so the rate policy, the rate
        date and the refusal to guess are all the ones every other group figure
        obeys. `known=False` means nobody has priced the pair — the screen says
        so and shows the amount in the money it was paid in.
        """
        rows = rows or self.browse()
        if 'pb.fx' not in self.env or not currency:
            return {row.id: (row.amount, False, {}) for row in rows}
        Fx = self.env['pb.fx']
        pairs = [{'amount': row.amount, 'src': row.currency_id.id,
                  'dst': currency.id if isinstance(currency, models.BaseModel)
                  else int(currency),
                  'when': on_date or row.date_to} for row in rows]
        try:
            answers = Fx.convert_many(pairs)
        except Exception:       # noqa: BLE001
            return {row.id: (row.amount, False, {}) for row in rows}
        out = {}
        for row, answer in zip(rows, answers):
            if isinstance(answer, dict):
                out[row.id] = (answer.get('value', row.amount),
                               bool(answer.get('known')),
                               answer.get('meta') or {})
            else:
                out[row.id] = (row.amount, False, {})
        return out
