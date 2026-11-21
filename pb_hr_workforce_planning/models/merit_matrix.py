# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class WfpMeritMatrix(models.Model):
    """Merit matrix: Performance rating × Compa-ratio → increase %."""
    _name = 'wfp.merit.matrix'
    _description = 'Merit Matrix'
    _order = 'name'

    name = fields.Char(
        string='Matrix Name',
        required=True,
        help="e.g. 'FY27 Standard Merit Matrix'"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    cell_ids = fields.One2many(
        'wfp.merit.matrix.cell',
        'matrix_id',
        string='Matrix Cells',
        copy=True,
    )
    note = fields.Text(string='Description')

    def get_increase_pct(self, compa_ratio, employee):
        """Look up the increase % for a given compa-ratio and employee.

        Currently uses compa-ratio ranges. Performance rating integration
        can be added when a performance module is available.
        """
        self.ensure_one()
        for cell in self.cell_ids.sorted(key=lambda c: c.sequence):
            if (cell.compa_min <= compa_ratio <= cell.compa_max):
                return cell.increase_pct
        return 0.0


class WfpMeritMatrixCell(models.Model):
    """Individual cell in the merit matrix."""
    _name = 'wfp.merit.matrix.cell'
    _description = 'Merit Matrix Cell'
    _order = 'sequence, id'

    matrix_id = fields.Many2one(
        'wfp.merit.matrix',
        string='Matrix',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)

    # Performance dimension (placeholder — can integrate with perf module)
    performance_label = fields.Char(
        string='Performance Rating',
        help="e.g. 'Exceptional', 'Meets', 'Developing'"
    )
    performance_min = fields.Integer(
        string='Perf. Min Score',
    )
    performance_max = fields.Integer(
        string='Perf. Max Score',
    )

    # Compa-ratio dimension
    compa_min = fields.Float(
        string='Compa-Ratio Min',
        digits=(5, 2),
        help="e.g. 0, 85, 100"
    )
    compa_max = fields.Float(
        string='Compa-Ratio Max',
        digits=(5, 2),
        help="e.g. 85, 100, 115"
    )

    # Result
    increase_pct = fields.Float(
        string='Increase %',
        digits=(5, 2),
        help="The merit increase percentage for this cell."
    )
