# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""hr.attendance rail extension for Phase G.

Two things live here, on purpose, so both the guard and the single writer share
one object identity:

  * the ``pb_entry_source`` rail gains ``correction`` and ``import`` (extending
    the Phase-B ``grid`` value); a blank source is still a raw device/kiosk punch;
  * a delete guard — a DEVICE punch (blank source) may be unlinked ONLY through
    an approved correction, which carries the module-level ``_CORR_TOKEN`` in
    context. This extends the Phase-B "the grid never overwrites a device punch"
    rail to deletes (safety rail 1). A plain boolean context key would be
    forgeable over call_kw (C18.24) — the identity of a Python ``object()`` can
    never be produced by a JSON-RPC client.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# The context KEY a correction's guarded writer sets, and the object IDENTITY it
# sets it to. Imported by attendance_correction so the two sides compare the SAME
# object — a forged {'pb_att_correction': 1} from a browser is not this object.
PB_ATT_CORRECTION_CTX = 'pb_att_correction'
_CORR_TOKEN = object()


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Extend the Phase-B rail. 'set null' is the only ondelete a plain optional
    # Selection with no base default can honor (C9). 'correction'/'import' rows
    # are freely mutable by their own writers; a blank source is a device punch.
    pb_entry_source = fields.Selection(
        selection_add=[('correction', 'Correction'), ('import', 'Import')],
        ondelete={'correction': 'set null', 'import': 'set null'})

    def _is_device_row(self):
        """A raw device/kiosk/manual punch = blank pb_entry_source."""
        self.ensure_one()
        return not self.pb_entry_source

    def unlink(self):
        # su / admin and the sanctioned correction path (sentinel in context)
        # may delete anything; everyone else is blocked from destroying a
        # device punch. grid/correction/import rows keep their existing
        # behaviour (the grid deletes its own 'grid' rows; corrections delete
        # via the sentinel path).
        sanctioned = (self.env.su or self.env.user._is_admin()
                      or self.env.context.get(PB_ATT_CORRECTION_CTX) is _CORR_TOKEN)
        if not sanctioned:
            device = self.filtered(lambda a: a._is_device_row())
            if device:
                raise UserError(_(
                    "A device/kiosk punch can only be removed through an "
                    "approved attendance correction — it is never deleted "
                    "directly (%s).",
                    ', '.join(device.mapped('employee_id.name'))))
        return super().unlink()
