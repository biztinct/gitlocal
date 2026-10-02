# -*- coding: utf-8 -*-
"""`/my/assets` — what the company has given me.

THE ROUTE IS THE GATE. The employee is re-resolved from the SESSION user on
every request and no route accepts an employee id, so a crafted URL can never
reach another person's list. Everything read past that point is read under
`sudo()` — the same doctrine `pb_me_portal` uses for documents and payslips —
because the record it reads has already been proved to be the caller's own.

The one write the page can make is "yes, I have it", and it is checked twice:
the assignment must belong to the session employee, and it must still be open.
"""

import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class PbAssetsPortal(CustomerPortal):

    # ------------------------------------------------------------- helpers
    def _assets_employee(self):
        """The OWN employee, from the session user. Never a parameter."""
        Emp = request.env['hr.employee'].sudo()
        emp = Emp.search([('user_id', '=', request.env.user.id),
                          ('company_id', '=', request.env.company.id)],
                         limit=1)
        return emp or Emp.search(
            [('user_id', '=', request.env.user.id)], limit=1)

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'asset_count' in counters:
            emp = self._assets_employee()
            values['asset_count'] = request.env[
                'pb.asset.assignment'].sudo().search_count(
                    [('employee_id', '=', emp.id),
                     ('state', '=', 'open')]) if emp else 0
        return values

    # ---------------------------------------------------------------- page
    @http.route(['/my/assets'], type='http', auth='user', website=True)
    def portal_my_assets(self, **kw):
        emp = self._assets_employee()
        if not emp:
            return request.redirect('/my')
        Assignment = request.env['pb.asset.assignment'].sudo()
        open_rows = Assignment.search(
            [('employee_id', '=', emp.id), ('state', '=', 'open')],
            order='assigned_date desc')
        past_rows = Assignment.search(
            [('employee_id', '=', emp.id), ('state', '=', 'returned')],
            order='returned_date desc', limit=20)
        # A digital item can be live on somebody's name with no handover row —
        # an account IT switched on directly. It still belongs on this page.
        seen = open_rows.mapped('asset_id').ids
        digital = request.env['pb.asset'].sudo().search([
            ('kind', '=', 'digital'), ('state', '=', 'assigned'),
            ('current_employee_id', '=', emp.id), ('id', 'not in', seen),
        ])
        values = {
            'page_name': 'assets',
            'employee': emp,
            'items': [self._assignment_card(r) for r in open_rows],
            'past': [self._assignment_card(r) for r in past_rows],
            'extra_digital': [self._asset_card(a) for a in digital],
            'unconfirmed': len(open_rows.filtered(
                lambda r: not r.receipt_confirmed)),
            'notice': kw.get('ok') and _("Thank you — that is noted.") or '',
        }
        return request.render('pb_assets.portal_my_assets', values)

    def _assignment_card(self, row):
        asset = row.asset_id
        return {
            'id': row.id,
            'code': asset.code or '',
            'name': asset.name or '',
            'category': asset.category_id.name or '',
            'kind': asset.kind or 'tangible',
            'serial': asset.serial or '',
            'model_name': asset.model_name or '',
            'since': row.assigned_date,
            'until': row.returned_date,
            'condition_out': row.condition_out or '',
            'condition_in': row.condition_in or '',
            'confirmed': row.receipt_confirmed,
        }

    def _asset_card(self, asset):
        return {
            'id': 0,
            'code': asset.code or '',
            'name': asset.name or '',
            'category': asset.category_id.name or '',
            'kind': asset.kind or 'digital',
            'serial': asset.serial or '',
            'model_name': asset.model_name or '',
            'since': False, 'until': False,
            'condition_out': '', 'condition_in': '',
            'confirmed': True,
        }

    # ------------------------------------------------------------- the write
    @http.route(['/my/assets/confirm/<int:assignment_id>'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_assets_confirm(self, assignment_id, **post):
        """“Yes, I have it.” The only thing this page may change."""
        emp = self._assets_employee()
        if not emp:
            return request.redirect('/my')
        row = request.env['pb.asset.assignment'].sudo().browse(
            int(assignment_id)).exists()
        # Two checks, not one: whose it is, and whether it is still open.
        if not row or row.employee_id.id != emp.id or row.state != 'open':
            return request.redirect('/my/assets')
        try:
            row.action_confirm_receipt()
        except Exception:           # noqa: BLE001 — never a 500 on a portal
            _logger.exception('pb_assets: receipt confirm failed for %s',
                              assignment_id)
            return request.redirect('/my/assets')
        return request.redirect('/my/assets?ok=1')
