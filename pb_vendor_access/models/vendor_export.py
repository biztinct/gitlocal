# -*- coding: utf-8 -*-
"""`pb.vendor.export` — the vendor spreadsheet.

Built from THE SAME FACADE THE SCREEN READS, never from a second query: a
spreadsheet that disagrees with the board it was exported from is worse than no
spreadsheet at all, and the way that happens is two pieces of code asking the
same question slightly differently.

THE THREE SPREADSHEET HELPERS AND THE TWO ACCESS EXPORTS ARE INHERITED from
`biz.access.export` (ACCESS P6) rather than copied. This model keeps only the
sheet that is about suppliers, and the model NAME does not change, so the
browser calls exactly what it called before.

The file comes back as base64 and the browser saves it without leaving the page
— the idiom `pb_records` uses. No attachment is left behind, because an export
is a copy somebody takes away, not a record.

NO SUDO ANYWHERE IN HERE. R89: a report that re-reads its own data as superuser
carries every company's rows into a company-scoped person's file, with totals
that then disagree with the screen beside it and nothing looking wrong. These
run as the person who pressed the button.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbVendorExport(models.TransientModel):
    _name = 'pb.vendor.export'
    _inherit = ['biz.access.export']
    _description = 'Vendor and access exports'

    kind = fields.Char(string='What it is')

    # ============================================================== the vendors
    @api.model
    def build_vendors(self):
        board = self.env['pb.vendors'].get_board(limit=None)
        openpyxl, Alignment, Font, PatternFill, get_column_letter = self._wb()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _('Vendors')

        cols = [_('Vendor'), _('What they do'), _('Who to ask for'),
                _('Their email'), _('Their phone'), _('Team'),
                _('Who looks after them'), _('Country'), _('Agreements'),
                _('Next one ends'), _('Where it is')]
        self._header(ws, cols, Font, PatternFill, Alignment)
        row = 2
        for r in board['rows']:
            for i, v in enumerate([
                    r['name'], r['type_label'], r['contact_name'],
                    r['contact_email'], r['contact_phone'], r['department'],
                    r['responsible'], r['country'], r['agreements'],
                    r['next_end'], r['state_label']], start=1):
                ws.cell(row=row, column=i, value=v)
            row += 1

        self._widths(ws, [30, 20, 22, 28, 16, 22, 24, 16, 12, 16, 20],
                     get_column_letter)
        ws.freeze_panes = 'A2'

        # A second sheet for the agreements themselves — the register answers
        # "who do we use", the agreements answer "what did we sign".
        ws2 = wb.create_sheet(_('Agreements'))
        cols2 = [_('Vendor'), _('What it covers'), _('Starts'), _('Ends'),
                 _('Talk about renewing on'), _('Days left'),
                 _('What it is worth'), _('Currency'), _('Where it is'),
                 _('Replaced by')]
        self._header(ws2, cols2, Font, PatternFill, Alignment)
        r2 = 2
        agreements = 0
        for r in board['rows']:
            drawer = self.env['pb.vendors'].get_vendor(r['id'])
            for a in drawer['agreements']:
                for i, v in enumerate([
                        r['name'], a['name'], a['date_start'], a['date_end'],
                        a['renewal_date'], a['days_left'], a['value'],
                        a['currency'], a['state_label'], a['renewed_by']],
                        start=1):
                    ws2.cell(row=r2, column=i, value=v)
                r2 += 1
                agreements += 1
        self._widths(ws2, [30, 34, 14, 14, 20, 12, 18, 12, 22, 26],
                     get_column_letter)
        ws2.freeze_panes = 'A2'

        return self._file(
            wb, _('Vendors and agreements %s.xlsx',
                  fields.Date.to_string(fields.Date.context_today(self))),
            len(board['rows']) + agreements)

