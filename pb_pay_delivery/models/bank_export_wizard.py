# -*- coding: utf-8 -*-
"""Real, validated bank-file generation on the existing VN export wizard.

The base ``vietnam.bank.export.wizard`` (pb_hr_payroll_vietnam) was a
notification stub. Here it becomes a real generator driven ENTIRELY by data
layouts (``pb.bank.file.layout``): resolve the layout, validate every row
(``account_ok`` + registry match + holder + positive net), NEVER silently drop a
failing row (they surface as exclusions), then build csv / fixed-width txt / xlsx
per the layout and hand back a downloadable file.

Read-only over the employee master (safety rail 1): the four ``vietnam_bank_*``
Chars are READ; nothing here writes them.
"""

import base64
import csv
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_bank_ocr.models import vn_bank_dictionary as vnd

_logger = logging.getLogger(__name__)

# Access to money-file generation: payroll manager OR a finance group (clone of
# pb_bank_ocr's _FINANCE_GROUPS, safety rail 3).
_PAY_GROUPS = ('om_hr_payroll.group_hr_payroll_manager',
               'account.group_account_invoice', 'account.group_account_user')


class VietnamBankExportWizard(models.TransientModel):
    _inherit = 'vietnam.bank.export.wizard'

    bank_format = fields.Selection(
        selection_add=[('vietinbank', 'VietinBank'), ('acb', 'ACB')],
        ondelete={'vietinbank': 'set default', 'acb': 'set default'})

    # Convenience: fill payslip_ids from a whole run's done slips.
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Pay Run')
    company_account_number = fields.Char(
        string='Company Debit Account',
        help="The company account debited for the transfer (optional; used by "
             "layouts that carry a company_account column).")

    # Result of a generation pass (download + audit).
    export_file = fields.Binary(string='Generated File', readonly=True)
    export_filename = fields.Char(string='Generated Filename', readonly=True)
    excluded_note = fields.Text(string='Excluded Rows', readonly=True)

    # ------------------------------------------------------------- access
    def _check_pay_access(self):
        user = self.env.user
        if user._is_admin():
            return
        for g in _PAY_GROUPS:
            try:
                if user.has_group(g):
                    return
            except (ValueError, KeyError):
                continue
        raise AccessError(_(
            "You are not allowed to generate bank payment files. "
            "This requires the Payroll Manager or a Finance role."))

    # ------------------------------------------------------------- helpers
    @api.model
    def _slip_net(self, slip):
        """NET amount via the verified :267 pattern, category fallback."""
        lines = slip.line_ids.filtered(lambda l: (l.code or '').upper() == 'NET')
        if lines:
            return sum(lines.mapped('total'))
        cat = slip.line_ids.filtered(
            lambda l: l.category_id and (l.category_id.code or '').upper() == 'NET')
        return sum(cat.mapped('total')) if cat else 0.0

    def _resolve_slips(self):
        """The slips to export: explicit payslip_ids, else the run's done slips."""
        self.ensure_one()
        slips = self.payslip_ids
        if not slips and self.payslip_run_id:
            slips = self.payslip_run_id.slip_ids
        return slips.filtered(lambda s: s.state == 'done')

    def _period_label(self):
        run = self.payslip_run_id
        if run and run.date_start and run.date_end:
            return "%s - %s" % (run.date_start, run.date_end)
        return run.name if run else ''

    def _row_sources(self, slip, idx, registry):
        """Build the {source_key: value} map for one slip, plus exclusion reasons.

        Pure reads of the employee master (rail 1). ``reasons`` is empty for a
        valid, payable row; any entry means the row is excluded (never silently
        dropped — no-silent-caps rule / C18.42b)."""
        emp = slip.employee_id
        account = emp.vietnam_bank_account_number or ''
        holder = (emp.vietnam_bank_account_name or emp.name or '').strip()
        bank_raw = emp.vietnam_bank_name or ''
        net = self._slip_net(slip)
        matched = registry.match(bank_raw)

        reasons = []
        if not vnd.account_ok(account):
            reasons.append(_('invalid account'))
        if not holder:
            reasons.append(_('missing account holder'))
        if not matched:
            reasons.append(_('unknown bank'))
        if net <= 0:
            reasons.append(_('no net pay'))

        sources = {
            'account_number': account,
            'account_name': holder,
            'bank_name': matched.short_name if matched else bank_raw,
            'bank_branch': emp.vietnam_bank_branch or '',
            'employee_code': emp.barcode or emp.identification_id or '',
            'employee_name': emp.name or '',
            'net_amount': net,
            'period': self._period_label(),
            'company_account': self.company_account_number or '',
            'row_number': idx,
            'literal': '',
        }
        return sources, reasons, net

    def _format_number(self, value, number_format):
        try:
            num = float(value or 0.0)
        except (TypeError, ValueError):
            return str(value or '')
        if number_format == 'int':
            return '%d' % round(num)
        if number_format == 'int_grouped':
            return '{:,.0f}'.format(num)
        return str(value or '')

    def _render_cell(self, col, sources):
        """Resolve a column to its raw string cell (before fixed-width padding)."""
        if col.source == 'literal':
            return col.literal_value or ''
        raw = sources.get(col.source, '')
        if col.number_format and col.number_format != 'none':
            return self._format_number(raw, col.number_format)
        return '' if raw is None else str(raw)

    def _pad_cell(self, text, col):
        if not col.width or col.width <= 0:
            return text
        text = text[:col.width]  # never overflow the fixed field
        if col.pad == 'left':
            return text.rjust(col.width, ' ')
        if col.pad == 'zero':
            return text.rjust(col.width, '0')
        return text.ljust(col.width, ' ')

    # ------------------------------------------------------------- builders
    def _build_csv(self, layout, rows):
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=(layout.delimiter or ','),
                            lineterminator='\r\n')
        if layout.with_header:
            writer.writerow([c.header or '' for c in layout.column_ids])
        for cells in rows:
            writer.writerow(cells)
        return buf.getvalue().encode(layout.encoding or 'utf-8')

    def _build_txt(self, layout, rows):
        lines = []
        if layout.with_header:
            lines.append(''.join(
                self._pad_cell(c.header or '', c) for c in layout.column_ids))
        cols = list(layout.column_ids)
        for cells in rows:
            lines.append(''.join(
                self._pad_cell(cells[i], cols[i]) for i in range(len(cols))))
        return ('\r\n'.join(lines) + '\r\n').encode(layout.encoding or 'utf-8')

    def _build_xlsx(self, layout, rows, numeric_cols):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_(
                "The xlsxwriter library is required for this bank's Excel "
                "format. Please install it or choose a CSV/TXT bank layout."))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {'in_memory': True})
        ws = wb.add_worksheet('Transfer')
        hfmt = wb.add_format({'bold': True, 'bg_color': '#21435F',
                              'font_color': 'white', 'border': 1})
        nfmt = wb.add_format({'num_format': '#,##0', 'border': 1})
        tfmt = wb.add_format({'border': 1})
        r0 = 0
        if layout.with_header:
            for c, col in enumerate(layout.column_ids):
                ws.write(0, c, col.header or '', hfmt)
            r0 = 1
        cols = list(layout.column_ids)
        for r, cells in enumerate(rows, start=r0):
            for c, col in enumerate(cols):
                if c in numeric_cols:
                    try:
                        ws.write_number(r, c, float(cells[c] or 0), nfmt)
                        continue
                    except (TypeError, ValueError):
                        pass
                ws.write(r, c, cells[c], tfmt)
        wb.close()
        out.seek(0)
        return out.read()

    # ------------------------------------------------------------- generate
    def _generate(self):
        """Validate + build the file. Returns a payload dict for the cockpit.

        Raises UserError with no layout, or when zero rows are payable (never
        emits an empty file). Excluded rows are always reported."""
        self.ensure_one()
        self._check_pay_access()

        layout = self.env['pb.bank.file.layout']._for_format(self.bank_format)
        if not layout:
            raise UserError(_(
                "No bank-file layout is configured for '%s'. A layout is a data "
                "record (pb.bank.file.layout) — add one to support this bank.",
                self.bank_format))

        slips = self._resolve_slips()
        if not slips:
            raise UserError(_(
                "There are no confirmed (Done) payslips to export for this "
                "selection."))

        registry = self.env['pb.bank.registry']
        cols = list(layout.column_ids)
        numeric_cols = {i for i, c in enumerate(cols)
                        if c.number_format and c.number_format != 'none'}

        rows, excluded, valid_count, total_amount = [], [], 0, 0.0
        for idx, slip in enumerate(slips.sorted(key=lambda s: s.employee_id.name or ''), start=1):
            sources, reasons, net = self._row_sources(slip, valid_count + 1, registry)
            if reasons:
                excluded.append({
                    'employee': slip.employee_id.name or '',
                    'employee_id': slip.employee_id.id,
                    'reasons': reasons,
                })
                continue
            valid_count += 1
            total_amount += net
            rows.append([self._render_cell(c, sources) for c in cols])

        if not rows:
            raise UserError(_(
                "No valid rows to export — every payslip failed validation "
                "(check the employee bank accounts). %s row(s) were excluded.",
                len(excluded)))

        if layout.file_type == 'xlsx':
            data = self._build_xlsx(layout, rows, numeric_cols)
            ext = 'xlsx'
        elif layout.file_type == 'txt':
            data = self._build_txt(layout, rows)
            ext = 'txt'
        else:
            data = self._build_csv(layout, rows)
            ext = 'csv'

        filename = '%s_%s.%s' % (
            self.bank_format, (self._period_label() or 'transfer').replace(' ', ''), ext)
        return {
            'file_b64': base64.b64encode(data).decode(),
            'filename': filename,
            'file_type': layout.file_type,
            'valid': valid_count,
            'excluded': excluded,
            'total_amount': total_amount,
            'byte_size': len(data),
        }

    def _soft_log_export(self, result):
        """Soft-reference bank.export.log (payroll_analytics_approval is OPTIONAL)."""
        if 'bank.export.log' not in self.env:
            return
        fmt = {'csv': 'csv', 'txt': 'txt', 'xlsx': 'excel'}.get(
            result['file_type'], 'csv')
        try:
            # sudo: the audit row is a system record; a finance user who can
            # generate a file need not hold create rights on the optional
            # analytics log model.
            self.env['bank.export.log'].sudo().create({
                'period_name': self._period_label() or (
                    self.payslip_run_id.name if self.payslip_run_id else 'Bank export'),
                'country': 'VN',
                'total_records': result['valid'],
                'total_amount': result['total_amount'],
                'export_format': fmt,
                'export_file': result['file_b64'],
                'filename': result['filename'],
                'export_details': result['excluded'] and _(
                    '%s row(s) excluded', len(result['excluded'])) or '',
            })
        except Exception as e:  # logging must never break the export
            _logger.warning("pb_pay_delivery: bank.export.log soft-log failed: %s", e)

    def action_export_file(self):
        """Real generation (replaces the stub). Off-menu admin fallback path;
        the primary surface is the Pay & Deliver cockpit. Sets the binary and
        re-opens the wizard so the browser can download it."""
        self.ensure_one()
        result = self._generate()
        self.export_file = result['file_b64']
        self.export_filename = result['filename']
        self.file_name = result['filename']
        if result['excluded']:
            self.excluded_note = "\n".join(
                "%s — %s" % (x['employee'], ", ".join(x['reasons']))
                for x in result['excluded'])
        self._soft_log_export(result)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'vietnam.bank.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
