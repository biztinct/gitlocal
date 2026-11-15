# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The weekly Close carries the "Time into pay" section.

`get_close_data` gains ONE key, ``time_pay``, read by the section this module
registers into the Close lens (`pb_close_lens_section`). Everything the board
had before is unchanged, with one exception that is the point of owner ruling
L5: once a company maps late or early minutes into pay, minutes nobody has
confirmed or excused hold the week — the CTA stays disabled and the checklist
says why — exactly like an open flag. Before that mapping exists the minutes
are shown for information only and hold nothing.

Never breaks the board: if this section cannot be read, the board is returned
exactly as it was and the reason goes to the log.
"""

import logging

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class PbCloseTimePay(models.AbstractModel):
    _inherit = 'pb.close'

    @api.model
    def get_close_data(self, department_id=False, week_start=False,
                       search=False, kind=False, reviewed=False, page=1):
        data = super().get_close_data(
            department_id=department_id, week_start=week_start,
            search=search, kind=kind, reviewed=reviewed, page=page)
        try:
            section = self.env['pb.time.pay']._close_payload(
                department_id, week_start, search)
        except Exception:                                   # noqa: BLE001
            _logger.exception('pb_time_pay: the Close section could not be '
                              'read; the board is shown without it')
            return data
        data['time_pay'] = section
        if section.get('late_in_pay'):
            n = section['late_stats']['open']
            data.setdefault('checklist', []).append({
                'key': 'late_minutes', 'done': n == 0,
                'label': (_("Late and early minutes all decided") if n == 0
                          else _("%s late or early minute row(s) to confirm "
                                 "or excuse", n))})
            if n:
                data['can_lock'] = False
        return data
