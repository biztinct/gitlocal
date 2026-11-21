# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The Team pulse tile on the Today board — additive, floored, and read-only.

`pb.today` was built with no `create`, `write` or `unlink` in it at all, and a
static test asserts that (W25): it is polled every 30 seconds and clicked
reflexively, and P1a's 591 junk corrections came from a surface nobody was even
clicking. This extension keeps that property — it adds exactly one read.

The tile's scope is the board's scope, so the department the officer is looking
at is the department they get a pulse for. The FLOOR is resolved on the server
inside `get_pulse_tile`, which returns no figures at all below it; nothing here
re-decides that, and nothing here can.
"""

from odoo import api, models


class PbTodayPulse(models.AbstractModel):
    _inherit = 'pb.today'

    @api.model
    def get_today_data(self, department_id=False, day=False):
        data = super().get_today_data(department_id=department_id, day=day)
        try:
            data['pulse'] = self.env['pb.shift.pulse'].get_pulse_tile(
                department_id)
        except Exception:                                     # pragma: no cover
            # Same rail as the Schedule badge: an instrument that cannot be
            # computed must not take the board down with it. An absent key is
            # exactly what the template already guards for.
            data['pulse'] = {'shown': False}
        return data
