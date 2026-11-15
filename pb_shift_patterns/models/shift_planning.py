# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The "made from a pattern" mark on a planned shift, and on the roster card.

`pb_pattern_id` says which pattern made the shift. `pb_pattern_sig` is the
shift's own fingerprint at the moment the pattern made it (person, shift, day,
start, end). A draft whose fingerprint still matches is UNTOUCHED: making the
drafts again may replace it. Anything else — a draft somebody moved, changed
or gave to another person, and every published or completed shift — is left
exactly as it is. No `write` override: the fingerprint is compared, so nothing
on the hot path of the roster pays for this.
"""

from odoo import api, fields, models


def pattern_signature(employee_id, template_id, day, start, end):
    """The one spelling of a shift's fingerprint (vals and records agree)."""
    return '%s|%s|%s|%s|%s' % (
        employee_id or 0, template_id or 0,
        fields.Date.to_string(day) if day else '',
        fields.Datetime.to_string(start) if start else '',
        fields.Datetime.to_string(end) if end else '')


class ShiftPlanning(models.Model):
    _inherit = 'hr.shift.planning'

    pb_pattern_id = fields.Many2one(
        'pb.shift.pattern', string='Made from pattern', index=True,
        ondelete='set null', copy=False, readonly=True)
    pb_pattern_sig = fields.Char(string='Pattern fingerprint', copy=False, readonly=True)

    def _pb_pattern_signature(self):
        self.ensure_one()
        return pattern_signature(self.employee_id.id, self.shift_template_id.id,
                                 self.date, self.start_datetime,
                                 self.end_datetime)

    def _pb_pattern_untouched(self):
        """A draft the pattern made and nobody has changed since."""
        self.ensure_one()
        return bool(self.pb_pattern_id and self.state == 'draft'
                    and self.pb_pattern_sig
                    and self.pb_pattern_sig == self._pb_pattern_signature())


class ShiftPlanningGrid(models.TransientModel):
    _inherit = 'hr.shift.planning.grid'

    @api.model
    def _pb_shift_card(self, shift, tmap, has_conflict, tzname=False):
        """The roster card says when a pattern made the shift (additive key)."""
        card = super()._pb_shift_card(shift, tmap, has_conflict, tzname=tzname)
        pattern = shift.pb_pattern_id
        card['pattern'] = pattern.sudo().name or '' if pattern else ''
        return card
