# -*- coding: utf-8 -*-
"""Who had what, when, and what state it was in each way.

One row per handover. The row is never edited away: when the item comes back
the row closes and a new one opens for the next person, so the history reads
like a logbook rather than a current position.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .asset_common import ASSIGNMENT_STATES

_logger = logging.getLogger(__name__)


class PbAssetAssignment(models.Model):
    _name = 'pb.asset.assignment'
    _description = 'Asset Assignment'
    _order = 'assigned_date desc, id desc'

    asset_id = fields.Many2one(
        'pb.asset', string='Item', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='restrict')
    asset_code = fields.Char(related='asset_id.code', store=False,
                             string='Asset code')
    kind = fields.Selection(related='asset_id.kind', store=True, index=True,
                            string='Kind', readonly=True)
    assigned_date = fields.Date(
        string='Given on', default=fields.Date.context_today, required=True)
    returned_date = fields.Date(string='Back on', readonly=True)
    condition_out = fields.Char(
        string='Condition going out',
        help='How the item looked when it was handed over.')
    condition_in = fields.Char(
        string='Condition coming back', readonly=True)
    receipt_confirmed = fields.Boolean(
        string='Employee confirmed', readonly=True, copy=False)
    receipt_confirmed_at = fields.Datetime(
        string='Confirmed on', readonly=True, copy=False)
    state = fields.Selection(
        ASSIGNMENT_STATES, string='Status', default='open', required=True,
        index=True)
    assigned_by = fields.Many2one(
        'res.users', string='Handed over by', readonly=True,
        default=lambda self: self.env.user)
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s → %s' % (
                rec.asset_id.code or rec.asset_id.name or _('Item'),
                rec.employee_id.name or '')

    def init(self):
        """One open holder per item, enforced by the database itself.

        The Python check below gives a person a readable message; this index is
        what makes the rule true when two screens save at the same second. A
        partial unique index is the only shape that works — a plain unique
        constraint would also forbid the SECOND completed loan of the same
        laptop, which is exactly the history this table exists to keep.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS pb_asset_assignment_open_uniq
            ON pb_asset_assignment (asset_id) WHERE state = 'open'
        """)

    @api.constrains('asset_id', 'state')
    def _check_one_open(self):
        for rec in self:
            if rec.state != 'open':
                continue
            other = self.search_count([
                ('asset_id', '=', rec.asset_id.id),
                ('state', '=', 'open'),
                ('id', '!=', rec.id),
            ])
            if other:
                raise ValidationError(_(
                    "%(what)s is already with somebody. Take it back first, or "
                    "use Transfer to move it across in one step.",
                    what=rec.asset_id.display_name))

    # ---------------------------------------------------------------- actions
    def action_return(self, condition_in=None, quiet=False):
        """Close the loan and put the item back on the shelf."""
        for rec in self:
            if rec.state == 'returned':
                continue
            rec.write({
                'state': 'returned',
                'returned_date': fields.Date.today(),
                'condition_in': condition_in or rec.condition_in or False,
            })
            asset = rec.asset_id
            if asset.kind == 'digital':
                # Handing an email account "back" is switching it off.
                if asset.state == 'assigned':
                    asset.state = 'deactivated'
            elif asset.state == 'assigned':
                asset.state = 'spare'
            if not quiet:
                asset.message_post(body=_(
                    "Taken back from %(who)s.%(cond)s",
                    who=rec.employee_id.name or _('the employee'),
                    cond=(_(" Condition on return: %s.", condition_in)
                          if condition_in else '')))
        # The close MUST reach the database before the caller's next act.
        # A transfer returns and re-issues in one breath, and Odoo 19 keeps a
        # write in the buffer while an immediately following create flushes its
        # own INSERT first — so the partial unique index above sees two open
        # rows for one asset and refuses the handover with a raw Postgres
        # message. Flushing here makes the ORDER a property of this method
        # rather than of every caller's luck.
        self.env.flush_all()
        return True

    def action_confirm_receipt(self):
        """The employee says “yes, I have it”. Only they can say it."""
        for rec in self:
            if rec.receipt_confirmed:
                continue
            rec.write({'receipt_confirmed': True,
                       'receipt_confirmed_at': fields.Datetime.now()})
            rec.asset_id.message_post(body=_(
                "%(who)s confirmed they have this item.",
                who=rec.employee_id.name or _('The employee')))
        return True

    def unlink(self):
        if any(rec.state == 'open' for rec in self):
            raise UserError(_(
                "This item is still with somebody. Take it back first — "
                "deleting the record would lose who had it."))
        return super().unlink()
