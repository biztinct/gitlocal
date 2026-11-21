# -*- coding: utf-8 -*-
"""UPDATES P5 (D20) — the employee's own tax summary includes the figures
before Payobook.

A small override of `/my/taxsheet` (pb_me_portal, not edited): the page's own
values are computed exactly as before, then — only when the person has
year-to-date figures for the summary's year — each figure whose pay items are
exactly ONE code the summary shows is added to that code's year total, and one
extra row "Before Payobook (up to <date>)" lists them. A figure that adds up
several codes (employee social contributions = three insurance lines) is not
split: it is shown under the table as one line. People without figures see
the page exactly as before.

UPDATES P5d (D29): before that, the year's totals are counted the way "paid
in Payobook" is (`pb.updates.ytd.line._tax_summary_counted`): a mid-month
advance is never added on top of the month-end payslip that carries the whole
month, one that cannot be matched is shown apart. Only for a person whose
year on the page includes an advance; the page's rows are never changed.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

_logger = logging.getLogger(__name__)


class PbMePortalYtd(PbMePortal):

    @http.route()
    def portal_my_taxsheet(self, **kw):
        response = super().portal_my_taxsheet(**kw)
        qcontext = getattr(response, 'qcontext', None)
        if not isinstance(qcontext, dict) or 'ytd' not in qcontext:
            return response
        try:
            emp = self._ess_employee()
            if emp:
                self._pb_updates_opening(emp, qcontext)
        except Exception:   # noqa: BLE001 — the page never breaks for this
            pass
        return response

    def _pb_updates_opening(self, emp, qcontext):
        Line = request.env['pb.updates.ytd.line'].sudo()
        # UPDATES P5d (D29) — the year's totals counted the way "paid in
        # Payobook" is (a mid-month advance never added on top of its
        # month-end payslip); only for a person whose year has an advance.
        try:
            Line._tax_summary_counted(emp, qcontext)
        except Exception:   # noqa: BLE001 — the page never breaks for this
            _logger.exception('pb_updates: the tax summary year totals could not be counted')
        Line._tax_summary_opening(emp, qcontext)
