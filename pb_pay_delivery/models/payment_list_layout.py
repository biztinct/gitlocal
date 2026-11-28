# -*- coding: utf-8 -*-
"""WDGAP S2-C — a bank's own payment file, made from the payment list.

The payment list (WDGAP IDB1/IDB2, `payment_list.py`) already reads the right
things for a bank in any country: the APPROVED account on record
(`hr.employee.bank_account_ids[:1]`), take-home from the one pay-band reading,
never two currencies added. This file puts those rows through a bank layout
(`pb.bank.file.layout` with `target = 'payment_list'`) so the finance team can
upload the bank's own format instead of retyping a list.

WHAT IT NEVER DOES.
  * It never changes which account is paid: the rows are the list's rows.
    A bank change waiting for approval is never used (the list keeps the last
    approved account and says so in its Check column).
  * It never cuts a value to fit, folds an accent or re-writes a sign: a row
    the layout cannot express — no bank code, an account number too long, a
    name with letters the bank refuses, a different money — is LEFT OUT, with
    a plain reason, listed on screen, in the approver's detail and in the
    general list's Check column.
  * It never adds two currencies: a file pays in one money (the layout's, or
    the pay run's own); people paid in another are left out, with the reason.

The file is stored and approved WITH the list (`pb.payment.list.file`, third
stored file beside the Excel and the CSV) — the bank file's own approval
gate, approved-bytes-only download, one trail line per download.
"""

import csv
import io
import json
import re
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .payment_list import FORMULA_START, _file_part

#: what a payment-list layout file is served as
LAYOUT_MIMETYPES = {
    'csv': 'text/csv',
    'txt': 'text/plain',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}

#: column sources that carry a number
NUMERIC_SOURCES = ('net_amount', 'control_total', 'row_count', 'row_number')
#: column sources whose text comes from people's records (checked for
#: formula signs, plain letters and encoding); literals are the layout's own
DATA_TEXT_SOURCES = ('account_number', 'account_name', 'bank_name',
                     'bank_branch', 'employee_code', 'employee_name',
                     'bank_bic', 'bank_clearing_code', 'beneficiary_email',
                     'company_account')

_TOKEN = re.compile(r'\{([a-z_]+)\}')


def _alnum(text):
    return ''.join(ch for ch in str(text or '') if ch.isalnum()).upper()


class PbPaymentListLayout(models.AbstractModel):
    _inherit = 'pb.payment.list'

    # ------------------------------------------------------------ layouts
    @api.model
    def _pb_layouts(self):
        """The payment-list layouts this person's companies may use: the
        shipped ones and their own companies' copies (record rule)."""
        return self.env['pb.bank.file.layout'].search(
            [('target', '=', 'payment_list')], order='name')

    @api.model
    def _pb_layout(self, layout):
        """A payment-list layout by record, id or key — or a plain refusal."""
        Layout = self.env['pb.bank.file.layout']
        if isinstance(layout, models.BaseModel):
            record = layout
        elif isinstance(layout, int):
            record = Layout.browse(layout)
        else:
            record = Layout._for_format(layout or '')
        record = record.exists()
        if record:
            # a copy of another company is refused by the record rule here
            record.check_access('read')
        if not record or record.target != 'payment_list' or not record.active:
            raise UserError(_("That bank layout is not available. Choose another one, or the general list."))
        return record

    @api.model
    def _pb_layout_payload(self):
        """What the screen offers. No account numbers, nothing private."""
        return [{
            'key': l.bank_format,
            'name': l.name,
            'country': l.country_id.name or '',
            'country_code': l.country_id.code or '',
            'inferred': bool(l.inferred),
            'own': bool(l.company_id),
        } for l in self._pb_layouts()]

    # ------------------------------------------------------------ the rows
    @api.model
    def _pb_bank_identity(self, account, country):
        """(BIC, bank code) of an account's bank: the account's own code first
        (an IFSC or a branch code is per account), then the bank record's
        code, then the bank directory by the bank's name and the country."""
        if not account:
            return '', ''
        bank = account.bank_id
        bic = (bank.bic or '').strip().upper() if bank else ''
        code = (account.clearing_number or '').strip() \
            if 'clearing_number' in account._fields else ''
        if not code and bank and 'pb_clearing_code' in bank._fields:
            code = (bank.pb_clearing_code or '').strip()
        if not code and bank and bank.name:
            country_code = country.code if country else (bank.country.code or '')
            if country_code and country_code.upper() != 'VN':
                found = self.env['pb.bank.registry'].sudo().match(
                    bank.name, country=country_code)
                code = (found.clearing_code or '').strip() if found else ''
        return bic, code

    @api.model
    def _pb_layout_rows(self, run, layout):
        """The list's rows (`_pb_build_rows`) with what a bank file also
        needs: the bank's codes, the email, the take-home line. Read under
        sudo after the door, as the list itself."""
        data = self._pb_build_rows(run)
        country = layout.country_id
        Slip = self.env['hr.payslip'].sudo()
        for row in data['rows']:
            slip = Slip.browse(row['slip_id'])
            emp = slip.employee_id.sudo()
            account = emp.bank_account_ids[:1] \
                if 'bank_account_ids' in emp._fields else emp.env['res.partner.bank']
            row['bic'], row['code'] = self._pb_bank_identity(account, country)
            row['email'] = (emp.work_email or '').strip()
            currency = slip._pb_slip_currency()
            row['take_home'] = currency.round(slip._pb_net_amount() or 0.0)
            # WDGAP S2-C ruling BL4: the paying company's own setting, read
            # when the file is made (a file already made keeps its bytes)
            row['other_name_policy'] = slip.company_id.sudo().pb_other_name_policy \
                or 'leave_out'
        return data

    # ------------------------------------------------------------ formatting
    @api.model
    def _pb_money_text(self, value, kind):
        value = float(value or 0.0)
        if kind == 'int':
            return '%d' % round(value)
        if kind == 'int_grouped':
            return '{:,.0f}'.format(value)
        if kind == 'implied2':
            return '%d' % int(round(value * 100))
        return '%.2f' % value

    @api.model
    def _pb_date_text(self, value, layout):
        if not value:
            return ''
        try:
            return value.strftime(layout.date_format or '%Y%m%d')
        except (ValueError, TypeError):
            return fields.Date.to_string(value)

    @api.model
    def _pb_cell_text(self, col, src, layout):
        """One cell as text, exactly as written (before fixed-width padding)."""
        if col.source == 'literal':
            return col.literal_value or ''
        value = src.get(col.source)
        if col.source == 'payment_date':
            return self._pb_date_text(value, layout)
        if col.source in NUMERIC_SOURCES:
            if col.source in ('row_count', 'row_number'):
                if col.number_format in (False, 'none', 'int', 'int_grouped'):
                    return '%d' % int(value or 0)
            kind = col.number_format if col.number_format not in (False, 'none') \
                else layout.amount_format or 'dec2'
            return self._pb_money_text(value, kind)
        return '' if value is None else str(value)

    @api.model
    def _pb_what(self, col, layout):
        """How a reason names a column."""
        names = {
            'account_number': _("The account number"),
            'account_name': _("The account holder name"),
            'bank_name': _("The bank name"),
            'bank_branch': _("The branch"),
            'employee_code': _("The employee number"),
            'employee_name': _("The employee name"),
            'bank_bic': _("The SWIFT/BIC code"),
            'bank_clearing_code': layout.code_label or _("The bank code"),
            'beneficiary_email': _("The email"),
            'company_account': _("The company account"),
            'reference': _("The payment reference"),
        }
        return names.get(col.source) or col.header or _("A column")

    @api.model
    def _pb_safe_reference(self, reference):
        """Our own reference text never starts with a formula sign."""
        text = (reference or '').strip()
        while text and text.startswith(FORMULA_START):
            text = text[1:].strip()
        return text

    # ------------------------------------------------------------ rendering
    @api.model
    def _pb_layout_render(self, layout, rows, options=None, run=None):
        """Put rows through a payment-list layout.

        ``rows``: dicts shaped like `_pb_build_rows` rows plus `bic`, `code`,
        `email`, `take_home` (see `_pb_layout_rows`). ``options``:
        `payment_date` (date), `company_account`, `reference`, `currency`
        (res.currency the file pays in).

        Returns {'payload', 'filename', 'mimetype', 'included', 'excluded',
        'count', 'total', 'currency', 'decimals'}. A row the layout cannot
        express is never written: it is in `excluded` with its reasons.
        """
        options = dict(options or {})
        pay_date = options.get('payment_date') or fields.Date.context_today(self)
        if isinstance(pay_date, str):
            pay_date = fields.Date.to_date(pay_date)
        company_account = (options.get('company_account') or '').strip()
        reference = self._pb_safe_reference(options.get('reference') or '')
        # the one money of the file: the layout's, else its country's, else
        # the pay run's own (never two added together)
        currency = layout.currency_id or layout.country_id.currency_id \
            or options.get('currency') or self.env.company.currency_id
        cols = list(layout.column_ids.sorted(lambda c: (c.sequence, c.id)))
        if not cols:
            raise UserError(_("“%s” has no columns yet. Add its columns on Settings › Bank layouts.", layout.name))
        file_type = layout.file_type or 'csv'
        encoding = layout.encoding or 'utf-8'
        code_re = re.compile(layout.code_pattern) if layout.code_pattern else None
        account_re = re.compile(layout.account_pattern) if layout.account_pattern else None
        uses_code = any(c.source == 'bank_clearing_code' for c in cols)

        def base_sources(row, number):
            return {
                'account_number': row.get('account') or '',
                'account_name': row.get('holder') or '',
                'bank_name': row.get('bank') or '',
                'bank_branch': row.get('branch') or '',
                'employee_code': row.get('employee_number') or '',
                'employee_name': row.get('employee_name') or '',
                'net_amount': row.get('amount') or 0.0,
                'period': self._pb_period(run) if run else '',
                'company_account': company_account,
                'row_number': number,
                'payment_date': pay_date,
                'currency': row.get('currency') or '',
                'bank_bic': row.get('bic') or '',
                'bank_clearing_code': row.get('code') or '',
                'beneficiary_email': row.get('email') or '',
                'reference': reference,
            }

        def text_problems(text, col, what):
            out = []
            if col.source not in DATA_TEXT_SOURCES or not text:
                return out
            if file_type in ('csv', 'xlsx') and text.startswith(FORMULA_START):
                out.append(self.env._("%s starts with a sign a spreadsheet would run as a formula", what))
            if layout.ascii_only and not text.isascii():
                out.append(self.env._("%s has letters this bank does not take (accents or other alphabets)", what))
            else:
                try:
                    text.encode(encoding)
                except (UnicodeEncodeError, LookupError):
                    out.append(self.env._("%s has letters this file cannot hold", what))
            return out

        # ---- pass 1: who can be in the file, and why not
        included, excluded = [], []
        for row in rows:
            reasons = []
            amount = float(row.get('amount') or 0.0)
            if not row.get('account'):
                reasons.append(_("No bank account on record"))
            if row.get('account') and not row.get('holder'):
                reasons.append(_("No account holder name on record"))
            if row.get('account') and row.get('name_band') == 'other' \
                    and row.get('other_name_policy') != 'pay':
                # WDGAP S2-C ruling BL1 (the default of BL4's company setting):
                # not sent to a bank in a file; finance pays it by hand (the
                # general list still lists it)
                reasons.append(_("Account is in another name"))
            if amount <= 0:
                reasons.append(_("Take-home is zero or below"))
            take_home = row.get('take_home')
            if take_home is not None and abs(amount - float(take_home or 0.0)) >= 0.01:
                reasons.append(_("The payslip shows take-home two ways; check it before paying"))
            if row.get('currency') and currency.name and row['currency'] != currency.name:
                reasons.append(_("Paid in %(paid)s; this bank file pays in %(file)s only",
                                 paid=row['currency'], file=currency.name))
            if row.get('account') and account_re \
                    and not account_re.search(_alnum(row['account'])):
                reasons.append(_("The account number is not in the form this bank needs"))
            if uses_code and code_re and row.get('code') \
                    and not code_re.search(row['code'].strip().upper()):
                reasons.append(_("%(what)s on record (%(value)s) is not in the form this bank needs",
                                 what=layout.code_label or _("The bank code"),
                                 value=row['code']))
            src = base_sources(row, 0)
            # no account: that is the one reason (nothing else can be said)
            for col in (cols if row.get('account') else []):
                if col.source in ('row_count', 'control_total', 'row_number', 'literal'):
                    continue
                what = self._pb_what(col, layout)
                if col.source == 'net_amount':
                    kind = col.number_format if col.number_format not in (False, 'none') \
                        else layout.amount_format
                    if kind in ('int', 'int_grouped') and abs(amount - round(amount)) >= 0.005:
                        # a whole-number column would round money: left out
                        reasons.append(_("The amount has cents, and this bank file takes whole amounts only"))
                text = self._pb_cell_text(col, src, layout)
                if col.required and not text.strip():
                    if col.source != 'account_name':     # said once, above
                        reasons.append(_("%s is missing", what))
                    continue
                limit = col.max_length or (col.width if file_type == 'txt' else 0)
                if limit and len(text) > limit:
                    reasons.append(_("%(what)s is longer than this bank takes (%(max)s characters)",
                                     what=what, max=limit))
                reasons += text_problems(text, col, what)
            # one reason once, in the order found
            seen, unique = set(), []
            for reason in reasons:
                if reason not in seen:
                    seen.add(reason)
                    unique.append(reason)
            if unique:
                excluded.append({
                    'employee': row.get('employee_name') or '',
                    'employee_id': row.get('employee_id'),
                    'slip_id': row.get('slip_id'),
                    'reasons': unique,
                    'amount': amount,
                    'currency': row.get('currency') or '',
                })
            else:
                included.append(row)

        count = len(included)
        total = sum(float(r.get('amount') or 0.0) for r in included)
        # what the people left out are owed, per money, never added across
        # (ruling BL1: they are paid another way, and the screen says how much)
        left_totals = {}
        for left in excluded:
            entry = left_totals.setdefault(left['currency'] or '', {
                'currency': left['currency'] or '', 'count': 0, 'amount': 0.0})
            entry['count'] += 1
            entry['amount'] += max(left['amount'], 0.0)
        left_totals = sorted(left_totals.values(), key=lambda t: t['currency'])
        # ruling BL4 "Pay by file": in the file, but counted apart, per money
        other_totals = {}
        for row in included:
            if row.get('name_band') != 'other':
                continue
            entry = other_totals.setdefault(row.get('currency') or '', {
                'currency': row.get('currency') or '', 'count': 0, 'amount': 0.0,
                'people': []})
            entry['count'] += 1
            entry['amount'] += float(row.get('amount') or 0.0)
            entry['people'].append(row.get('employee_name') or '')
        other_totals = sorted(other_totals.values(), key=lambda t: t['currency'])
        decimals = currency.decimal_places if currency else 2
        total = round(total, decimals)

        # ---- pass 2: the cells
        whole_total = (
            layout.amount_format == 'int'
            and '{total}' in (layout.header_template or '') + (layout.trailer_template or '')
        ) or any(c.source == 'control_total' and (
            c.number_format in ('int', 'int_grouped')
            or (c.number_format in (False, 'none') and layout.amount_format == 'int'))
            for c in cols)
        if whole_total and abs(total - round(total)) >= 0.005:
            raise UserError(_("The total of this file has cents, and this bank file writes its total as a whole number. Change how the total is written on Settings › Bank layouts."))
        tokens = {
            'count': '%d' % count,
            'total': self._pb_money_text(total, layout.amount_format or 'dec2'),
            'date': self._pb_date_text(pay_date, layout),
            'company_account': company_account,
            'reference': reference,
            'currency': currency.name or '',
        }

        def fill(template):
            lines = []
            for line in (template or '').splitlines():
                if not line.strip():
                    continue
                lines.append(_TOKEN.sub(lambda m: tokens.get(m.group(1), m.group(0)), line))
            return lines

        body = []
        for number, row in enumerate(included, start=1):
            src = base_sources(row, number)
            src.update(row_count=count, control_total=total)
            cells = []
            for col in cols:
                text = self._pb_cell_text(col, src, layout)
                limit = col.max_length or (col.width if file_type == 'txt' else 0)
                if limit and len(text) > limit:
                    # only a whole-file figure (the count or the total) can
                    # get here: the file cannot be made, nothing is cut
                    raise UserError(_("%(what)s of this file is longer than the bank takes (%(max)s characters), so the file cannot be made.",
                                      what=self._pb_what(col, layout), max=limit))
                cells.append(text)
            body.append((cells, src))

        head_lines, tail_lines = fill(layout.header_template), fill(layout.trailer_template)
        newline = '\n' if layout.line_ending == 'lf' else '\r\n'
        if file_type == 'xlsx':
            payload = self._pb_layout_xlsx(layout, cols, body, head_lines, tail_lines)
        elif file_type == 'txt':
            lines = list(head_lines)
            if layout.with_header:
                lines.append(''.join(self._pb_pad(c.header or '', c) for c in cols))
            for cells, _src in body:
                lines.append(''.join(self._pb_pad(cells[i], cols[i]) for i in range(len(cols))))
            lines += tail_lines
            payload = self._pb_encode(newline.join(lines) + newline, encoding)
        else:
            buf = io.StringIO()
            writer = csv.writer(buf, delimiter=(layout.delimiter or ',')[:1],
                                lineterminator=newline)
            for line in head_lines:
                buf.write(line + newline)
            if layout.with_header:
                writer.writerow([c.header or '' for c in cols])
            for cells, _src in body:
                writer.writerow(cells)
            for line in tail_lines:
                buf.write(line + newline)
            payload = self._pb_encode(buf.getvalue(), encoding)

        bits = [_file_part(layout.name)]
        if run:
            bits.append(_file_part(run.name))
            if run.date_end:
                bits.append(fields.Date.to_string(run.date_end))
        filename = '%s.%s' % (' - '.join(b for b in bits if b), file_type)
        return {
            'payload': payload,
            'filename': filename,
            'mimetype': LAYOUT_MIMETYPES.get(file_type, 'application/octet-stream'),
            'included': [{'slip_id': r.get('slip_id'), 'employee_id': r.get('employee_id'),
                          'employee': r.get('employee_name') or '',
                          'amount': float(r.get('amount') or 0.0)} for r in included],
            'excluded': excluded,
            'count': count,
            'total': total,
            'currency': currency.name or '',
            'decimals': decimals,
            'left_totals': left_totals,
            'other_name_totals': other_totals,
        }

    @api.model
    def _pb_encode(self, text, encoding):
        """The file's bytes. People's cells were checked one by one; what can
        still fail here is the layout's own text (a header, a fixed text, the
        company account) — refused in words, never written half."""
        try:
            return text.encode(encoding)
        except LookupError:
            raise UserError(_("The text encoding “%s” is not known. Use utf-8, utf-8-sig, ascii or latin-1.", encoding))
        except UnicodeEncodeError:
            raise UserError(_("The layout's own text (a column name, a fixed text, the lines before or after the payments, or the company account) has letters its text encoding (%s) cannot hold.", encoding))

    @api.model
    def _pb_pad(self, text, col):
        """Fixed-width padding. Never cuts (pass 1 left out what is too long)."""
        if not col.width or col.width <= 0:
            return text
        if col.pad == 'left':
            return text.rjust(col.width, ' ')
        if col.pad == 'zero':
            return text.rjust(col.width, '0')
        return text.ljust(col.width, ' ')

    @api.model
    def _pb_layout_xlsx(self, layout, cols, body, head_lines, tail_lines):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("The Excel file cannot be made on this server. Choose a CSV or text bank layout."))
        out = io.BytesIO()
        workbook = xlsxwriter.Workbook(out, {
            'in_memory': True,
            # every text cell is TEXT (leading zeros kept, never a formula)
            'strings_to_formulas': False,
            'strings_to_numbers': False,
            'strings_to_urls': False,
        })
        workbook.set_properties({'title': layout.name or '', 'author': '',
                                 'company': '', 'comments': ''})
        sheet = workbook.add_worksheet((_file_part(layout.name) or 'Sheet1')[:31])
        text = workbook.add_format({'num_format': '@'})
        numbers = {'0': workbook.add_format({'num_format': '0'}),
                   '0.00': workbook.add_format({'num_format': '0.00'})}
        r = 0
        for line in head_lines:
            sheet.write_string(r, 0, line, text)
            r += 1
        if layout.with_header:
            for c, col in enumerate(cols):
                sheet.write_string(r, c, col.header or '', text)
            r += 1
        for cells, src in body:
            for c, col in enumerate(cols):
                if col.source in NUMERIC_SOURCES and col.number_format in (False, 'none', 'int', 'dec2'):
                    value = float(src.get(col.source) or 0.0)
                    pattern = '0' if (col.number_format == 'int'
                                      or col.source in ('row_count', 'row_number')) else '0.00'
                    sheet.write_number(r, c, value, numbers[pattern])
                else:
                    sheet.write_string(r, c, cells[c], text)
            r += 1
        for line in tail_lines:
            sheet.write_string(r, 0, line, text)
            r += 1
        workbook.close()
        return out.getvalue()

    # ------------------------------------------------------------ for a run
    @api.model
    def _pb_layout_build(self, run, layout, options=None):
        """The bank file for a pay run (no door, no log, not a way out:
        `pb.payment.list.file` is the only door)."""
        layout = self._pb_layout(layout)
        options = dict(options or {})
        options.setdefault('reference', self._pb_reference(run))
        options.setdefault('currency', self.env['pb.pay.delivery']._primary_currency(run))
        data = self._pb_layout_rows(run, layout)
        result = self._pb_layout_render(layout, data['rows'], options, run=run)
        result['list_data'] = data
        return result

    @api.model
    def _pb_mark_left_out(self, data, layout, result):
        """The general list's Check column says who is not in the bank file
        and why (only when a bank layout was chosen — the general list made
        without one is byte-identical)."""
        by_slip = {x['slip_id']: x for x in result['excluded']}
        for row in data['rows']:
            left = by_slip.get(row['slip_id'])
            if left:
                row['checks'].append(_("Not in the %(layout)s file: %(reasons)s",
                                       layout=layout.name,
                                       reasons=', '.join(left['reasons'])))
        data['check_count'] = sum(1 for r in data['rows'] if r['checks'])
        return data

    # ------------------------------------------------------------ preview
    @api.model
    def _pb_sample_rows(self, layout):
        """Three made-up people for the layout preview (Settings › Bank
        layouts). Never a real person; the numbers are obviously not real."""
        code = layout.country_id.code or ''
        samples = {
            'ID': [('DEMO Ayu Lestari', 'BCA', '014'), ('DEMO Budi Santoso', 'Mandiri', '008'),
                   ('DEMO Citra Wijaya', 'BNI', '009')],
            'SG': [('DEMO Alice Tan', 'DBS', '7171005'), ('DEMO Ben Lim', 'OCBC', '7339550'),
                   ('DEMO Chloe Ng', 'UOB', '7375030')],
            'IN': [('DEMO Asha Rao', 'HDFC Bank', 'HDFC0000001'),
                   ('DEMO Bhavin Shah', 'ICICI Bank', 'ICIC0000002'),
                   ('DEMO Chitra Iyer', 'State Bank of India', 'SBIN0000003')],
        }.get(code, [('DEMO Anna Nguyen', 'Bank A', '001'), ('DEMO Binh Tran', 'Bank B', '002'),
                     ('DEMO Chau Le', 'Bank C', '003')])
        currency = layout.currency_id or layout.country_id.currency_id \
            or self.env.company.currency_id
        amounts = (7500000.0, 6250000.5, 4100000.0) if code == 'ID' else (4250.0, 3800.5, 5120.0)
        rows = []
        for i, (name, bank, bank_code) in enumerate(samples):
            rows.append({
                'slip_id': -(i + 1), 'employee_id': -(i + 1),
                'employee_number': 'DEMO%03d' % (i + 1),
                'employee_name': name, 'holder': name, 'bank': bank, 'branch': '',
                'account': '000000%04d' % (1234 + i), 'amount': amounts[i],
                'currency': currency.name, 'take_home': amounts[i],
                'bic': '', 'code': bank_code, 'email': '',
            })
        return rows, currency

    @api.model
    def _pb_preview(self, layout):
        rows, currency = self._pb_sample_rows(layout)
        result = self._pb_layout_render(layout, rows, {
            'payment_date': date(2026, 6, 30), 'company_account': '0000000000',
            'reference': 'DEMO June 2026', 'currency': currency})
        if layout.file_type == 'xlsx':
            # the workbook's cells, as rows of text, for the screen
            import openpyxl
            book = openpyxl.load_workbook(io.BytesIO(result['payload']), read_only=True)
            sheet = book.worksheets[0]
            text = '\n'.join(
                ' | '.join('' if v is None else str(v) for v in values)
                for values in sheet.iter_rows(values_only=True))
        else:
            text = result['payload'].decode(layout.encoding or 'utf-8', errors='replace')
            text = text.lstrip('﻿')
        return {
            'text': text,
            'count': result['count'],
            'total': result['total'],
            'currency': result['currency'],
            'excluded': [{'employee': x['employee'], 'reasons': x['reasons']}
                         for x in result['excluded']],
            'filename': result['filename'],
        }


class PbPaymentListFileLayout(models.Model):
    _inherit = 'pb.payment.list.file'

    #: WDGAP S2-C — the bank's own file, made with a layout from the same rows
    layout_id = fields.Many2one('pb.bank.file.layout', string='Bank layout',
                                readonly=True, ondelete='set null')
    layout_name = fields.Char(string='Bank layout name', readonly=True)
    layout_attachment_id = fields.Many2one('ir.attachment', readonly=True,
                                           ondelete='restrict', copy=False)
    layout_hash = fields.Char(string='Bank file stamp', readonly=True, copy=False)
    layout_row_count = fields.Integer(string='Rows in the bank file', readonly=True)
    layout_total = fields.Float(string='Total of the bank file', readonly=True)
    layout_currency = fields.Char(readonly=True)
    layout_excluded_json = fields.Text(readonly=True)
    layout_excluded_count = fields.Integer(string='Left out of the bank file',
                                           readonly=True)
    payment_date = fields.Date(readonly=True)
    company_account = fields.Char(string='Company debit account', readonly=True)
    #: ruling BL4: people paid into another person's account by this file
    layout_other_name_json = fields.Text(readonly=True)

    def _pb_layout_other_name(self):
        self.ensure_one()
        try:
            rows = json.loads(self.layout_other_name_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    def _pb_layout_excluded(self):
        self.ensure_one()
        try:
            rows = json.loads(self.layout_excluded_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []
