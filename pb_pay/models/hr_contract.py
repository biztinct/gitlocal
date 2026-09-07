# -*- coding: utf-8 -*-
"""What a contract screen reads: the band, and how far through it the pay is.

THREE READ-ONLY FIELDS AND NOTHING ELSE. This module writes nothing to
`hr.contract` — not the wage, not a stored figure, not a tracked value. The
three fields below are computed from `pb.pay.position` at read time and stored
nowhere, so there is no second copy of the truth to drift and no column on the
payroll's own table that a bug here could corrupt.

That is the whole difference from the old `compa_ratio`: it was a STORED
compute on `hr.contract` that depended on the wage and on the grade record, so
it recomputed when somebody's pay changed and silently did not when the grade's
midpoint moved. These read the derived table, which the band itself rebuilds.

WRITES ELSEWHERE THAT MOVE A PERSON'S POSITION — a wage change, a job change, a
contract opening or closing — mark the company for a rebuild rather than
recomputing 4,500 rows inside somebody's save.
"""

from odoo import api, fields, models

from .pb_pay_position import STATES

#: Changing any of these moves somebody in (or out of) a band.
_WATCHED = ('wage', 'state', 'job_id', 'employee_id', 'company_id')


class HrContract(models.Model):
    _inherit = 'hr.contract'

    pb_band_id = fields.Many2one(
        'pb.pay.band', string='Pay band', compute='_compute_pb_band',
        readonly=True)
    pb_position_pct = fields.Float(
        string='Position in band', compute='_compute_pb_band', readonly=True,
        digits=(16, 2),
        help='0 is the bottom of the band and 100 the top.')
    pb_band_state = fields.Selection(
        STATES, string='Band standing', compute='_compute_pb_band',
        readonly=True)

    def _compute_pb_band(self):
        rows = {}
        if self.ids:
            for row in self.env['pb.pay.position'].sudo().search_read(
                    [('contract_id', 'in', self.ids)],
                    ['contract_id', 'band_id', 'position_pct', 'state']):
                rows[row['contract_id'][0]] = row
        for contract in self:
            row = rows.get(contract.id)
            contract.pb_band_id = (row['band_id'] or [False])[0] \
                if row and row.get('band_id') else False
            contract.pb_position_pct = row['position_pct'] if row else 0.0
            contract.pb_band_state = row['state'] if row else False

    # ------------------------------------------------------------- triggers
    def _pb_schedule_rebuild(self):
        """One rebuild per transaction, however many contracts were saved.

        A payroll import writes hundreds of contracts in one go; rebuilding
        4,500 position rows after each of them would turn a two-second import
        into a ten-minute one for a figure nobody reads until the screen opens.
        The work is queued on the cursor's PRECOMMIT — it runs once, inside
        the same transaction, just before the save lands, so a screen opened
        immediately afterwards reads the new positions and a rollback takes
        the rebuild with it.
        """
        if self.env.context.get('pb_pay_no_rebuild'):
            return
        companies = set(self.mapped('company_id').ids)
        if not companies:
            return
        pending = self.env.cr.precommit.data.setdefault('pb_pay.rebuild', set())
        if not pending:
            env = self.env

            def _run():
                todo = sorted(env.cr.precommit.data.pop('pb_pay.rebuild', ()))
                if todo:
                    env['pb.pay.position'].touch_companies(todo)

            self.env.cr.precommit.add(_run)
        pending.update(companies)

    def write(self, vals):
        result = super().write(vals)
        if any(name in vals for name in _WATCHED):
            self._pb_schedule_rebuild()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._pb_schedule_rebuild()
        return records
