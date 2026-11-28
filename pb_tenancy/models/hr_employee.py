# -*- coding: utf-8 -*-
"""FLEET P5 — the employee limit, enforced where employees are actually made.

ONE OVERRIDE, ON `create`, AND NOWHERE ELSE. Every screen, wizard, import and
script in the product that adds a person goes through `hr.employee.create` —
so this is the only place the limit has to be, and putting it anywhere else
would be a second place to keep in step.

WHAT IT DOES NOT DO. It does not archive anybody, it does not stop anybody
being PAID, and it does not touch a company that has no limit — which is every
company on a plan whose employee limit is nought, and every database the
platform has never told anything (fail open, and the whole module works that
way).

THE REFUSAL IS A SENTENCE, NOT A CODE. It names the number, the number they
already have, and the person who can change it. A wall with no door on it is
the worst thing a payroll product can put in front of somebody at month end.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from .standing import seat_refusal

_logger = logging.getLogger(__name__)

#: The escape hatch, for the platform's own tooling and for a restore that has
#: to put a database back exactly as it was. Nothing in the product sets it.
SKIP_CTX = 'pb_tenancy_skip_seat'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):
        self._pb_check_seats(len(vals_list))
        return super().create(vals_list)

    @api.model
    def _pb_check_seats(self, adding=1):
        """Refuse the create when the plan's limit is already reached.

        The count is taken FRESH here — the five-minute cache behind the banner
        is fine for a warning and is not fine for a refusal, because the person
        who has just archived somebody to make room must be able to add the
        next one straight away.
        """
        if self.env.context.get(SKIP_CTX):
            return
        Tenancy = self.env['pb.tenancy'].sudo()
        try:
            seat = Tenancy.seat_state(fresh=True)
        except Exception:                                    # noqa: BLE001
            # FAIL OPEN. A settings row that cannot be read must never stop a
            # payroll office adding the person who starts on Monday.
            _logger.warning("pb_tenancy: could not read the employee limit; "
                            "allowing the employee.", exc_info=True)
            return
        limit = seat.get('limit') or 0
        if not limit:
            return
        count = seat.get('count') or 0
        if count + max(1, int(adding or 1)) > limit:
            raise UserError(_(seat_refusal(limit, count)))
