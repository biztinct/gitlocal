# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`/my/holidays` — which days the company is closed, for everybody.

READ ONLY, AND THAT IS THE WHOLE SECURITY DESIGN. This page has no form, no
POST and no id in any route: there is nothing on it a crafted URL could reach
that the page does not already show every reader. `pb.holidays.my_year` is the
one reader and it filters to PUBLIC rows — `resource_id` empty — so a person's
own time off can never surface here, whoever is looking.

EVERY PRIVATE HELPER HERE CARRIES `_lv_`, AND THAT IS NOT A STYLE CHOICE
(R186). All `CustomerPortal` subclasses merge into ONE class, so a helper
called `_notice` in this file and `_notice` in `pb_rnr` are the same attribute
and whichever module loads last silently wins. It has bitten this programme
three times, and every one of them was invisible at runtime.
"""

import logging

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PbHolidaysPortal(CustomerPortal):

    # --------------------------------------------------------------- helpers
    def _lv_facade(self):
        return request.env['pb.holidays']

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'pb_holidays_count' in counters:
            try:
                data = self._lv_facade().my_year()
                mine = (data.get('companies') or [{}])[0]
                values['pb_holidays_count'] = mine.get('count') or 0
            except Exception:                               # noqa: BLE001
                _logger.warning('pb_timeoff: the holidays counter failed',
                                exc_info=True)
                values['pb_holidays_count'] = 0
        return values

    def _prepare_portal_layout_values(self):
        """The EAGER key the home card's subtitle is drawn from (R62).

        `portal.portal_my_home` fetches its counters lazily, AFTER the page has
        rendered, so anything a card's own markup reads at render time has to
        be computed here. QWeb raises on a name it has never heard of, so a
        missing key would turn one card into a 500 for the whole of `/my` —
        which is why this one is set on every path through the method,
        including the failure.
        """
        values = super()._prepare_portal_layout_values()
        values['pb_holidays_next'] = ''
        try:
            nxt = self._lv_facade().next_one()
            if nxt:
                away = nxt['days_away']
                if away <= 0:
                    when = _("today")
                elif away == 1:
                    when = _("tomorrow")
                else:
                    when = _("in %s days", away)
                values['pb_holidays_next'] = _(
                    "Next: %(what)s, %(when)s", what=nxt['name'], when=when)
        except Exception:                                   # noqa: BLE001
            _logger.warning('pb_timeoff: the holidays card failed',
                            exc_info=True)
        return values

    # ============================================================ the page
    @http.route(['/my/holidays'], type='http', auth='user', website=True)
    def portal_my_holidays(self, year=None, **kw):
        data = self._lv_facade().my_year(year or False)
        return request.render('pb_timeoff.portal_my_holidays', {
            'page_name': 'holidays',
            'hol': data,
        })
