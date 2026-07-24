# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Filtered-view XLSX export for the Audit & Compliance console (Phase J §3).

A transient wizard whose ONLY write is its own ``export_file`` Binary (safety
rail 1). It reuses the console facade's collectors verbatim, so the export
carries EXACTLY the same rows and the same PII masking as the on-screen view
(safety rail 4), and streams up to a hard cap surfaced to the caller (never a
silent truncation — C18 no-silent-caps). Follows the in-memory xlsxwriter →
base64 → Binary re-open precedent (pb_hr_workforce_planning export wizard).
"""

import base64
import io

from odoo import fields, models, _
from odoo.exceptions import UserError

# Kept in step with the console's cap.
_EXPORT_CAP = 50000


class PbAuditExport(models.TransientModel):
    _name = 'pb.audit.export'
    _description = 'Audit Console Export'

    export_file = fields.Binary(string='Export File', readonly=True)
    export_filename = fields.Char(string='Filename', readonly=True)

    # --------------------------------------------------------------- build
    def build(self, filters, kind):
        """Generate the XLSX for one filtered view and return a download URL.

        Returns {url, filename, count, truncated, cap}."""
        self.ensure_one()
        # The console gate is the auth boundary; export_stream already required
        # a manager. Re-assert defensively (a direct call_kw to build must not
        # bypass it).
        self.env['pb.audit.console']._require_manager()
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_(
                "The xlsxwriter library is required for Excel export "
                "(pip install xlsxwriter)."))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        hdr = wb.add_format({'bold': True, 'bg_color': '#312E81',
                             'font_color': 'white', 'border': 1,
                             'valign': 'vcenter'})
        txt = wb.add_format({'border': 1})
        num = wb.add_format({'num_format': '#,##0', 'border': 1})
        pct = wb.add_format({'num_format': '0.0"%"', 'border': 1})

        builder = {
            'stream': self._build_stream,
            'salary': self._build_salary,
            'login': self._build_login,
        }.get(kind, self._build_stream)
        count, truncated = builder(wb, hdr, txt, num, pct, filters)

        wb.close()
        output.seek(0)
        self.export_file = base64.b64encode(output.read())
        self.export_filename = 'audit_%s.xlsx' % kind
        url = ('/web/content/pb.audit.export/%s/export_file'
               '?download=true&filename=%s' % (self.id, self.export_filename))
        return {'url': url, 'filename': self.export_filename,
                'count': count, 'truncated': truncated, 'cap': _EXPORT_CAP}

    # --------------------------------------------------------------- sheets
    def _build_stream(self, wb, hdr, txt, num, pct, filters):
        ws = wb.add_worksheet('Audit Trail')
        headers = ['When', 'Source', 'Actor', 'Employee', 'Event', 'Old', 'New',
                   'Reference']
        widths = [18, 14, 22, 24, 40, 22, 22, 24]
        for c, (h, w) in enumerate(zip(headers, widths)):
            ws.write(0, c, h, hdr)
            ws.set_column(c, c, w)

        console = self.env['pb.audit.console']
        rows, _capped, _status = console._collect_stream(filters, _EXPORT_CAP)
        truncated = len(rows) > _EXPORT_CAP
        rows = rows[:_EXPORT_CAP]
        for r, row in enumerate(rows, start=1):
            when = row['stamp'] or ''
            emp = (row['employee'] or {}).get('name', '') if row['employee'] else ''
            ref = ('%s#%s' % (row['ref']['model'], row['ref']['res_id'])
                   if row['ref'] else '')
            ws.write(r, 0, when, txt)
            ws.write(r, 1, row['source_label'], txt)
            ws.write(r, 2, row['actor']['name'] or '', txt)
            ws.write(r, 3, emp, txt)
            ws.write(r, 4, row['title'], txt)
            ws.write(r, 5, row['old'], txt)
            ws.write(r, 6, row['new'], txt)
            ws.write(r, 7, ref, txt)
        return len(rows), truncated

    def _build_salary(self, wb, hdr, txt, num, pct, filters):
        ws = wb.add_worksheet('Salary Adjustments')
        headers = ['Employee', 'Old Wage', 'New Wage', 'Delta %', 'Actor', 'When']
        widths = [26, 16, 16, 10, 22, 18]
        for c, (h, w) in enumerate(zip(headers, widths)):
            ws.write(0, c, h, hdr)
            ws.set_column(c, c, w)
        data = self.env['pb.audit.console'].get_salary_lens(filters)
        rows = data['rows'][:_EXPORT_CAP]
        for r, row in enumerate(rows, start=1):
            ws.write(r, 0, row['employee']['name'], txt)
            ws.write(r, 1, row['old'], txt)
            ws.write(r, 2, row['new'], txt)
            if row['delta_pct'] is not None:
                ws.write_number(r, 3, row['delta_pct'], pct)
            else:
                ws.write(r, 3, '', txt)
            ws.write(r, 4, row['actor']['name'] or '', txt)
            ws.write(r, 5, row['stamp_display'], txt)
        return len(rows), len(data['rows']) > _EXPORT_CAP

    def _build_login(self, wb, hdr, txt, num, pct, filters):
        ws = wb.add_worksheet('Sessions Started')
        headers = ['User', 'Login', 'Sessions', 'Sessions (30d)', 'Last Session']
        widths = [26, 26, 12, 14, 20]
        for c, (h, w) in enumerate(zip(headers, widths)):
            ws.write(0, c, h, hdr)
            ws.set_column(c, c, w)
        data = self.env['pb.audit.console'].get_login_lens(filters)
        cards = data['cards'][:_EXPORT_CAP]
        for r, card in enumerate(cards, start=1):
            ws.write(r, 0, card['name'], txt)
            ws.write(r, 1, card['login'] or '', txt)
            ws.write_number(r, 2, card['sessions'], num)
            ws.write_number(r, 3, card['sessions_30d'], num)
            ws.write(r, 4, card['last'], txt)
        return len(cards), len(data['cards']) > _EXPORT_CAP
