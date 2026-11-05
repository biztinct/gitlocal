# -*- coding: utf-8 -*-
"""The Time clocks lens badge and the ribbon phrase on the Time hub.

CLOCK-1 (ledger D8): the badge counts unknown numbers with punches in the
context week. CLOCK-3 §4.2: while any time-clock alert is open the badge counts
the things that need attention instead, and the ribbon sentence gains
"· 2 time-clock alerts" — unknown numbers still count when nothing is open.
"""

from odoo import _, api, models


class PbTimeHub(models.AbstractModel):
    _inherit = 'pb.time.hub'

    @api.model
    def _clock_alert_count(self):
        if 'pb.clock.alert' not in self.env:
            return 0
        return self.env['pb.clock.alert']._count(
            self.env.companies.ids or [self.env.company.id])

    @api.model
    def _extra_lens_counts(self, ctx):
        res = super()._extra_lens_counts(ctx)
        alerts = self._clock_alert_count()
        res['clocks'] = alerts or self.env['pb.clock.lens']._unknown_count(
            ctx.get('week_start'))
        return res

    @api.model
    def _extra_ribbon(self, ctx):
        res = super()._extra_ribbon(ctx)
        n = self._clock_alert_count()
        if n:
            res.append({'key': 'clocks', 'n': n, 'lens': 'clocks',
                        'text': (_("1 time-clock alert") if n == 1
                                 else _("%s time-clock alerts") % n)})
        return res
