# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PbTripExpenseCategory(models.Model):
    _inherit = 'pb.trip.expense.category'

    product_id = fields.Many2one(
        'product.product', string='Expense Product',
        domain=[('can_be_expensed', '=', True)],
        help='Product used when a receipted line in this category becomes a '
             'draft expense.')


class PbBusinessTripLine(models.Model):
    _inherit = 'pb.business.trip.line'

    expense_id = fields.Many2one(
        'hr.expense', string='Expense', readonly=True, copy=False,
        help='Draft expense created from this line on trip authorization.')


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    pb_trip_id = fields.Many2one(
        'pb.business.trip', string='Business Trip', readonly=True,
        index=True, copy=False)


class PbBusinessTrip(models.Model):
    _inherit = 'pb.business.trip'

    expense_ids = fields.One2many('hr.expense', 'pb_trip_id', string='Expenses')
    expense_count = fields.Integer(compute='_compute_expense_count')
    per_diem_expense_id = fields.Many2one(
        'hr.expense', string='Per-Diem Expense', readonly=True, copy=False)

    @api.depends('expense_ids')
    def _compute_expense_count(self):
        for rec in self:
            rec.expense_count = len(rec.expense_ids)

    # -------------------------------------------------- expense product
    @api.model
    def _default_expense_product(self):
        prod = self.env.ref('pb_trip_expense_bridge.product_travel_expense',
                            raise_if_not_found=False)
        if not prod:
            prod = self.env['product.product'].search(
                [('can_be_expensed', '=', True)], limit=1)
        return prod

    # ------------------------------------------- create drafts on approval
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            self._create_trip_expenses()
        return res

    def _create_trip_expenses(self):
        """One draft hr.expense per receipted line; a per-diem expense when the
        policy channel is 'expense'. Idempotent — skips lines/per-diem already
        linked (safe to re-run)."""
        self.ensure_one()
        Expense = self.env['hr.expense'].sudo()
        default_product = self._default_expense_product()

        for line in self.line_ids:
            if line.expense_id:
                continue  # idempotent
            if not line.amount or not line.receipt_attachment_id:
                continue  # only RECEIPTED lines become expenses
            product = line.category_id.product_id or default_product
            exp = Expense.create({
                'name': line.description or _('%(trip)s — %(cat)s', **{
                    'trip': self.name,
                    'cat': line.category_id.name or _('Trip')}),
                'date': line.date or self.date_from,
                'employee_id': self.employee_id.id,
                'product_id': product.id if product else False,
                'currency_id': self.currency_id.id,
                'total_amount_currency': line.amount,
                'company_id': self.company_id.id,
                'pb_trip_id': self.id,
            })
            line.expense_id = exp.id
            if line.receipt_attachment_id:
                line.receipt_attachment_id.copy({
                    'res_model': 'hr.expense', 'res_id': exp.id})

        # per-diem via the EXPENSE channel (exclusive with the payroll bridge)
        channel = self.policy_id.per_diem_channel if self.policy_id else 'payroll'
        if (channel == 'expense' and self.per_diem_total
                and not self.per_diem_expense_id):
            product = default_product
            exp = Expense.create({
                'name': _('Per-diem — %(dest)s (%(days)s days)', **{
                    'dest': self.destination_city or self.name,
                    'days': self.duration_days}),
                'date': self.date_from,
                'employee_id': self.employee_id.id,
                'product_id': product.id if product else False,
                'currency_id': self.currency_id.id,
                'total_amount_currency': self.per_diem_total,
                'company_id': self.company_id.id,
                'pb_trip_id': self.id,
            })
            self.per_diem_expense_id = exp.id

    # ---------------------------------------------- cancel guard (rail)
    def _before_cancel(self):
        super()._before_cancel()
        Expense = self.env['hr.expense'].sudo()
        exps = Expense.search([('pb_trip_id', '=', self.id)])
        if not exps:
            return
        non_draft = exps.filtered(lambda e: e.state != 'draft')
        if non_draft:
            raise UserError(_(
                "Cannot cancel this trip — linked expenses are already "
                "submitted or posted: %s.", ', '.join(non_draft.mapped('name'))))
        # all draft → drop them and clear the links
        self.line_ids.filtered('expense_id').write({'expense_id': False})
        self.per_diem_expense_id = False
        exps.unlink()

    def action_view_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Trip Expenses'),
            'res_model': 'hr.expense',
            'view_mode': 'list,form',
            'domain': [('pb_trip_id', '=', self.id)],
            'context': {'default_pb_trip_id': self.id},
        }
