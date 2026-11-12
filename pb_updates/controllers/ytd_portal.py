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
"""
from odoo import http
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal


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
        request.env['pb.updates.ytd.line'].sudo()._tax_summary_opening(emp, qcontext)
