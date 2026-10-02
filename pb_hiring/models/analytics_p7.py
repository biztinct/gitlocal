# -*- coding: utf-8 -*-
"""RECRUIT P7 — Hiring numbers: each agency's own figures.

Per agency, for the people it put forward in the date range on roles the
filters keep: put forward, turned away by the 6-month rule, reached an
interview, offers, joined — and the days to fill on the roles it worked on
that filled. Submission-based, never "the filled count of the roles it was
on" (which credited an agency with the team's own hires).
"""

import logging
from datetime import datetime, time

from odoo import _, api, models

_logger = logging.getLogger(__name__)


class PbHiringAnalyticsP7(models.AbstractModel):
    _inherit = 'pb.hiring.analytics'

    @api.model
    def get_board(self, date_from=None, date_to=None, department_id=None,
                  country_id=None, recruiter_id=None):
        board = super().get_board(date_from, date_to, department_id, country_id, recruiter_id)
        if not board.get('allowed'):
            return board
        filters = self._filters(department_id, country_id, recruiter_id)
        board['agencies'] = self._safe(
            lambda: self.with_context(pb_hn_filters=filters)._agency_rows(date_from, date_to), [])
        return board

    @api.model
    def _agency_rows(self, date_from=None, date_to=None):
        start, end = self._window(date_from, date_to)
        co_ids = self.env.companies.ids or [self.env.company.id]
        role_dom = [('company_id', 'in', co_ids)] + self._filter_domain()
        roles = self.env['pb.hiring.requisition'].sudo().search(role_dom)
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        subs = Sub.search([('requisition_id', 'in', roles.ids),
                           ('submitted_on', '>=', datetime.combine(start, time.min)),
                           ('submitted_on', '<=', datetime.combine(end, time.max))])
        vendors = subs.mapped('vendor_id') | roles.mapped('agency_vendor_ids')
        out = []
        for v in vendors.sorted(lambda x: (x.name or '').lower()):
            mine = subs.filtered(lambda s, v=v: s.vendor_id == v)
            figures = Sub._figures(mine)
            filled = roles.filtered(lambda r, v=v: v in r.agency_vendor_ids
                                    and r.filled_on and r.opened_on)
            spans = [max(0, (r.filled_on - r.opened_on).days) for r in filled]
            out.append(dict(figures, id=v.id, name=v.name or '',
                            roles=len(roles.filtered(lambda r, v=v: v in r.agency_vendor_ids)),
                            days=round(sum(spans) / len(spans), 1) if spans else None))
        return out

    @api.model
    def export_xlsx(self, date_from=None, date_to=None, kind='all', department_id=None,
                    country_id=None, recruiter_id=None):
        res = super().export_xlsx(date_from, date_to, kind, department_id, country_id,
                                  recruiter_id)
        if kind not in ('all', 'agency') or not res.get('ok'):
            return res
        try:
            import base64
            import io
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(res['file_b64'])))
            rows = self.with_context(pb_hn_filters=self._filters(
                department_id, country_id, recruiter_id))._agency_rows(date_from, date_to)
            ws = wb.create_sheet(_('Agencies')[:31])
            heads = [_('Agency'), _('Roles'), _('Put forward'), _('Turned away (6-month rule)'),
                     _('Reached an interview'), _('Offers'), _('Joined'), _('Days to fill')]
            for i, label in enumerate(heads, start=1):
                cell = ws.cell(row=1, column=i, value=label)
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='6355C7')
            for r, row in enumerate(rows, start=2):
                for i, value in enumerate([row['name'], row['roles'], row['submitted'],
                                           row['refused'], row['interviewed'], row['offers'],
                                           row['joined'], row['days']], start=1):
                    ws.cell(row=r, column=i, value=value)
            ws.column_dimensions['A'].width = 34
            out = io.BytesIO()
            wb.save(out)
            res['file_b64'] = base64.b64encode(out.getvalue()).decode()
        except Exception:               # noqa: BLE001 — the rest of the workbook still goes
            _logger.warning('pb_hiring: the Agencies sheet could not be added', exc_info=True)
        return res
