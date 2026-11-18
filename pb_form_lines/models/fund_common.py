# -*- coding: utf-8 -*-
"""WDGAP S2-B2 — what every fund file shares.

A FUND FILE NEVER MAKES UP A MEMBER NUMBER. A person whose member number is
missing (or cannot be written the way the fund's layout needs it) is LEFT OUT
of the upload file, with the plain reason, on the summary workbook that comes
with every fund file; the file's totals leave them out and the summary says
so beside the figures of everyone read (handover S2-B2 item 4, test 4).

THE ADVISER NOTE (G3) goes where the layout can carry it without breaking the
upload: a text file the fund's system reads line by line (EPF ECR, CPF EZPay)
cannot hold a comment, so there the note is the first row of the summary
workbook made in the same filing and on every screen; an upload workbook gets
a second sheet "Check first" (portals read the first sheet only).

Renderer hooks per form code (the S2-A contract):

    _pb_render_<code>(data) -> [(filename, bytes, mimetype)]
    _pb_fund_reasons_<code>(emp, data) -> [reason]   # extra reasons to leave out
"""
import io
from decimal import ROUND_HALF_UP, Decimal

from odoo import _, api, models
from odoo.exceptions import UserError

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def whole(value):
    """Half up to a whole unit (the funds' rounding; Python's round() is
    half-to-even)."""
    return int(Decimal(str(float(value or 0.0))).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def cents(value):
    return int(Decimal(str(float(value or 0.0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
               * 100)


def digits(text):
    return ''.join(ch for ch in (text or '') if ch.isdigit())


class PbGovFilingFundCommon(models.Model):
    _inherit = 'pb.gov.filing'

    # ------------------------------------------------------------ people
    @api.model
    def _pb_fund_split(self, form, data):
        """(kept, left_out): every person of the reading with the reasons
        they cannot go into the upload file."""
        hook = getattr(self, '_pb_fund_reasons_%s' % (form.code or '').lower(), None)
        kept, left = [], []
        for emp in data.get('employees') or []:
            ident = emp.get('identity') or {}
            reasons = list(ident.get('leave_out') or [])
            if not reasons and hook is not None:
                reasons += hook(emp, data) or []
            row = dict(emp, reasons=reasons)
            (left if reasons else kept).append(row)
        return kept, left

    @api.model
    def _pb_fund_nobody(self, left):
        """Nobody can go into the upload file: the refusal, with the reasons."""
        reasons = sorted({r for row in left for r in row['reasons']})
        return UserError(_("Nobody in this filing can go into the upload file: %s.",
                           '; '.join(reasons)))

    @api.model
    def _pb_fund_total(self, rows, code):
        return sum(float((r.get('lines') or {}).get(code) or 0.0) for r in rows)

    # ------------------------------------------------------------ workbooks
    @api.model
    def _pb_fund_book(self, title):
        import xlsxwriter
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {'in_memory': True})
        book.set_properties({'title': title, 'author': '', 'company': ''})
        return buf, book

    @api.model
    def _pb_fund_check_sheet(self, book, data):
        """A second sheet with the adviser note: the fund's portal reads the
        first sheet only, so the note never gets in the way of an upload."""
        if not data.get('adviser_mark'):
            return
        ws = book.add_worksheet(_("Check first"))
        note = book.add_format({'italic': True, 'bold': True, 'font_color': '#B45309'})
        ws.write_string(0, 0, data.get('adviser_text') or '', note)
        ws.set_column(0, 0, 70)

    def _pb_fund_summary(self, data, kept, left, member_heads, extra_lines=None):
        """The summary workbook every fund file comes with.

        member_heads: [(label, identity key)] — the numbers shown per person.
        extra_lines: [(label, value)] printed under the header (e.g. the
        submission number the file was made for).
        """
        self.ensure_one()
        form = self.form_id.sudo()
        buf, book = self._pb_fund_book(form.name or '')
        bold = book.add_format({'bold': True})
        h1 = book.add_format({'bold': True, 'font_size': 14})
        note = book.add_format({'italic': True, 'font_color': '#B45309', 'bold': True})
        head = book.add_format({'bold': True, 'bg_color': '#EEF0F8', 'border': 1, 'text_wrap': True})
        money = book.add_format({'num_format': '#,##0.00'})
        ws = book.add_worksheet(_("Summary"))
        r = 0
        if data.get('adviser_mark'):
            ws.write_string(r, 0, data.get('adviser_text') or '', note)
            r += 1
        ws.write_string(r, 0, form.name or '', h1)
        r += 1
        if form.official_name:
            ws.write_string(r, 0, form.official_name)
            r += 1
        for label, value in [(_("Company"), data.get('company_name') or ''),
                             (_("Period"), data.get('period_label') or ''),
                             (_("Currency"), data.get('currency') or '')] + list(extra_lines or []):
            ws.write_string(r, 0, label, bold)
            ws.write_string(r, 1, str(value or ''))
            r += 1
        r += 1
        ws.write_string(r, 0, _("Line"), head)
        ws.write_string(r, 1, _("Everyone read from payslips"), head)
        ws.write_string(r, 2, _("In the file"), head)
        r += 1
        lines = [l for l in form._pb_ordered_lines() if l.kind in ('money', 'computed')]
        totals = data.get('lines') or {}
        for line in lines:
            if line.code not in totals:
                continue
            ws.write_string(r, 0, '%s — %s' % (line.code, line.label))
            ws.write_number(r, 1, float(totals.get(line.code) or 0.0), money)
            ws.write_number(r, 2, self._pb_fund_total(kept, line.code), money)
            r += 1
        ws.write_string(r, 0, _("People"))
        ws.write_number(r, 1, len(kept) + len(left))
        ws.write_number(r, 2, len(kept))
        r += 2
        if left:
            if len(left) == 1:
                text = _("1 person is left out of the file. Their figures are not in the file's totals.")
            else:
                text = _("%s people are left out of the file. Their figures are not in the file's totals.",
                         len(left))
            ws.write_string(r, 0, text, bold)
            r += 1
            for row in left:
                ws.write_string(r, 0, row.get('name') or '')
                ws.write_string(r, 1, '; '.join(row['reasons']))
                r += 1
            r += 1
        for warn in data.get('warnings') or []:
            ws.write_string(r, 0, warn.get('message') or '')
            r += 1
        ws.set_column(0, 0, 60)
        ws.set_column(1, 2, 26)

        ws2 = book.add_worksheet(_("People"))
        person_lines = [l for l in lines if l.scope == 'employee']
        heads = [_("Name")] + [h for h, _k in member_heads] + \
            ['%s — %s' % (l.code, l.label) for l in person_lines] + \
            [_("In the file"), _("Why not / to check")]
        for col, text in enumerate(heads):
            ws2.write_string(0, col, text, head)
        for i, row in enumerate(sorted(kept + left, key=lambda x: ((x.get('name') or '').lower(),
                                                                   x.get('employee_id') or 0)),
                                start=1):
            ident = row.get('identity') or {}
            c = 0
            ws2.write_string(i, c, row.get('name') or '')
            for _h, key in member_heads:
                c += 1
                ws2.write_string(i, c, str(ident.get(key) or ''))
            for line in person_lines:
                c += 1
                ws2.write_number(i, c, float((row.get('lines') or {}).get(line.code) or 0.0), money)
            c += 1
            ws2.write_string(i, c, _("No") if row['reasons'] else _("Yes"))
            c += 1
            said = []
            for text in row['reasons'] + list(row.get('checks') or []):
                if text not in said:
                    said.append(text)
            ws2.write_string(i, c, '; '.join(said))
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, len(heads) - 2, 16)
        ws2.set_column(len(heads) - 1, len(heads) - 1, 50)
        book.close()
        return buf.getvalue()
