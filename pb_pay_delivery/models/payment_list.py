# -*- coding: utf-8 -*-
"""WDGAP IDB1 — the payment list (any bank, any country).

WHY THIS EXISTS. The bank file this module prepares knows Vietnamese banks
only: it reads the four `vietnam_bank_*` fields and refuses any bank its
registry does not know ("unknown bank"). Rize pays 126 people into Indonesian
banks (BCA, Mandiri …), so those people could not be paid by file at all. The
owner chose a GENERAL list for now (ruling IDB1, 2026-11-18): name, bank,
account number, amount — a plain Excel/CSV a finance team can upload or
retype into any bank. A bank-specific layout comes later, once the paying
bank is known; none is invented here.

WHAT IT READS, AND WHAT IT NEVER READS.
  * The account is the APPROVED account on record: the employee's first bank
    account (`hr.employee.bank_account_ids[:1]`, `res.partner.bank`) — the one
    every reader in this product takes first (pb_bank_ocr
    `pb_bank_two_stores.put_first`). Since WDGAP S6-A (BK1/BK2) nothing is
    written to that store until a second person approves, so what is on record
    IS the approved account. A change still waiting for approval lives on its
    own record (`pb.bank.change.request` in review, or a waiting Updates /
    Records proposal) and is NEVER used: the row keeps the last approved
    account and says so in "Check".
  * The amount is take-home from the one pay-band reading
    (`hr.payslip.pb_pay_totals()['net']`), never a rule category. Where it
    disagrees with the payslip's own take-home line (what the bank file pays,
    `_pb_net_amount`) the row says so rather than choosing silently.
  * Money is never added across currencies: one total per currency.

WHAT IT NEVER DOES. It writes nothing but one trail line per download (who,
when, how many rows — never an account number). It does not change the bank
file, the two bank stores, how they are approved, or any payment status.
"""

import csv
import io
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_bank_ocr.models.vn_bank_dictionary import name_similarity

#: The name bands of the bank-document check (`name_match_band`): 85 and up is
#: the same person's name; under 60 is somebody else's.
NAME_MATCH = 85.0
NAME_CLOSE = 60.0

#: A text cell that starts with one of these is read as a formula by a
#: spreadsheet. Escaped with a leading apostrophe in both files.
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')

#: The kinds of file the list is offered as.
FORMATS = ('xlsx', 'csv')


def _digits(text):
    """The account number as the bank reads it: letters and digits only."""
    return ''.join(ch for ch in str(text or '') if ch.isalnum()).upper()


def safe_text(value):
    """A text cell no spreadsheet will run as a formula."""
    text = '' if value is None else str(value)
    if text and text.startswith(FORMULA_START):
        return "'" + text
    return text


def _file_part(text):
    """A piece of a file name: no path signs, no control characters."""
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', ' ', str(text or ''))
    return re.sub(r'\s+', ' ', text).strip()[:80]


class PbPaymentList(models.AbstractModel):
    _name = 'pb.payment.list'
    _description = 'Payment list (any bank)'

    # ------------------------------------------------------------ the door
    @api.model
    def _pb_check_door(self, run):
        """The same people who may download the bank file; nobody else."""
        self.env['pb.pay.delivery']._require_access()
        if not run or not run.exists():
            raise UserError(_("That pay run no longer exists."))
        # a pay run the reader may not see (another company) is refused by
        # the record rules here, before anything is read for them
        run.check_access('read')
        return run

    # ------------------------------------------------------------- reading
    @api.model
    def _pb_columns(self):
        return [
            ('employee_number', _("Employee number")),
            ('employee_name', _("Employee name")),
            ('holder', _("Account holder")),
            ('bank', _("Bank")),
            ('branch', _("Branch")),
            ('account', _("Account number")),
            ('amount', _("Amount")),
            ('currency', _("Currency")),
            ('reference', _("Payment reference")),
            ('in_bank_file', _("In the bank file")),
            ('check', _("Check")),
        ]

    @api.model
    def _pb_period(self, run):
        # plain characters only: a bank's reference box often takes no more
        if run.date_start and run.date_end:
            return '%s - %s' % (fields.Date.to_string(run.date_start),
                                fields.Date.to_string(run.date_end))
        return ''

    @api.model
    def _pb_reference(self, run):
        period = self._pb_period(run)
        return ', '.join(bit for bit in ((run.name or '').strip(), period) if bit)

    @api.model
    def _pb_slips(self, run):
        """The payslips the list pays: finished, paid by bank transfer, not
        on hold, not paid yet. Returned with the counts of those left out."""
        done = run.slip_ids.filtered(lambda s: s.state == 'done')
        left = {'held': 0, 'paid_other': 0, 'paid': 0}
        keep = []
        for slip in done:
            if 'pb_paid_method' in slip._fields and slip.pb_paid_method:
                left['paid_other'] += 1
            elif slip.pb_pay_hold:
                left['held'] += 1
            elif slip.pb_paid_on:
                left['paid'] += 1
            else:
                keep.append(slip.id)
        return done.browse(keep).sorted(
            key=lambda s: (s.employee_id.name or '', s.id)), left

    @api.model
    def _pb_waiting_changes(self, employees):
        """{employee id: [what each waiting change proposes]} for the bank
        changes still waiting for approval: a dict (number digits, bank,
        holder) for a bank-document request, None for an Updates / Records
        proposal (not compared: always a change). Read for the list only;
        never applied."""
        waiting = {}
        employees = employees.sudo()
        if not employees:
            return waiting
        Req = self.env.get('pb.bank.change.request')
        if Req is not None:
            Req = Req.sudo().with_context(active_test=False)
            domain = [('employee_id', 'in', employees.ids)]
            if 'pb_origin' in Req._fields:
                # in review; or held from an import for HR to look at first
                domain += ['|', ('state', 'in', ('hr_review', 'finance_review')),
                           '&', ('state', '=', 'draft'), ('pb_origin', '=', 'import')]
            else:
                domain += [('state', 'in', ('hr_review', 'finance_review'))]
            for req in Req.search(domain):
                waiting.setdefault(req.employee_id.id, []).append({
                    'number': _digits(req.x_account_number),
                    'bank': (req.x_bank_name or '').strip().lower(),
                    'holder': (req.x_account_name or '').strip().lower(),
                })
        Apply = self.env.get('pb.records.apply')
        if Apply is not None and 'touches_bank' in Apply._fields:
            wanted = set(employees.ids)
            for proposal in Apply.sudo().search([('state', '=', 'pending'),
                                                 ('touches_bank', '=', True)]):
                try:
                    rows = json.loads(proposal.plan_json or '[]')
                except (TypeError, ValueError):
                    continue
                for row in rows if isinstance(rows, list) else []:
                    if not isinstance(row, dict):
                        continue
                    emp_id = row.get('emp_id')
                    if emp_id in wanted and str(row.get('field_id') or '')[:2] == 'b:':
                        waiting.setdefault(emp_id, []).append(None)
        return waiting

    @api.model
    def _pb_is_change(self, proposed, number, bank, holder):
        """Does a waiting change propose anything other than what is paid
        to? (A copy of the account on record into the bank-file fields —
        the BG1 batches — proposes the same account: not a change.)"""
        if proposed is None:
            return True
        return not (proposed['number'] == number
                    and proposed['bank'] in ('', bank.strip().lower())
                    and proposed['holder'] in ('', holder.strip().lower()))

    @api.model
    def _pb_in_bank_file(self, run):
        """Payslips that are rows of the current bank file of this run."""
        File = self.env['pb.bank.file'].sudo()
        latest = File.search([('run_id', '=', run.id),
                              ('state', 'not in', ('superseded', 'rejected'))],
                             order='id desc', limit=1)
        return set(latest._pb_file_slips().ids) if latest else set()

    @api.model
    def _pb_build_rows(self, run):
        """Every row of the list, with its checks, and the totals.

        Read under sudo after the door (`_pb_check_door`): bank accounts and
        employee numbers are HR fields a finance reader of the bank file does
        not otherwise hold.
        """
        slips, left = self._pb_slips(run)
        employees = slips.mapped('employee_id').sudo()
        waiting = self._pb_waiting_changes(employees)
        in_file = self._pb_in_bank_file(run)
        reference = self._pb_reference(run)
        rows = []
        for slip in slips:
            emp = slip.employee_id.sudo()
            account = emp.bank_account_ids[:1] \
                if 'bank_account_ids' in emp._fields else emp.env['res.partner.bank']
            number = (account.acc_number or '').strip() if account else ''
            holder = (account.acc_holder_name or '').strip() if account else ''
            bank = (account.bank_id.name or '').strip() if account else ''
            branch = ''
            if number and 'vietnam_bank_account_number' in emp._fields \
                    and _digits(emp.vietnam_bank_account_number) == _digits(number):
                branch = (emp.vietnam_bank_branch or '').strip()
            currency = slip._pb_slip_currency()
            amount = currency.round(slip.pb_pay_totals().get('net') or 0.0)
            take_home = currency.round(slip._pb_net_amount() or 0.0)
            checks = []
            if not number:
                checks.append(_("No bank account on record"))
            else:
                if not holder:
                    checks.append(_("No account holder name on record"))
                else:
                    score = name_similarity(holder, emp.name or '')
                    if score < NAME_CLOSE:
                        checks.append(_("The account is in another person's name"))
                    elif score < NAME_MATCH:
                        checks.append(_("The account holder name is close to, but not the same as, the employee's name"))
            changes = [p for p in waiting.get(emp.id, [])
                       if self._pb_is_change(p, _digits(number), bank, holder)]
            if changes:
                checks.append(_("A bank change is waiting for approval; this list uses the last approved account") if number else _("A bank change is waiting for approval; until it is approved there is no account to pay"))
            if amount <= 0:
                checks.append(_("Take-home is zero or below"))
            if abs(amount - take_home) >= 0.01:
                checks.append(_("The payslip shows take-home two ways (%(a)s and %(b)s); check it before paying",
                                a='{:,.2f}'.format(amount), b='{:,.2f}'.format(take_home)))
            rows.append({
                'slip_id': slip.id,
                'employee_id': emp.id,
                # "Employee number" on the employee record, else the badge
                'employee_number': emp.employee_id or emp.barcode or '',
                'employee_name': emp.name or '',
                'holder': holder,
                'bank': bank,
                'branch': branch,
                'account': number,
                'account_key': _digits(number),
                'amount': amount,
                'currency': currency.name or '',
                'currency_id': currency.id,
                'symbol': currency.symbol or '',
                'decimals': currency.decimal_places,
                'reference': reference,
                'in_bank_file': _("Yes") if slip.id in in_file else '',
                'checks': checks,
            })
        # the same account for two people of THIS list: both are flagged
        by_account = {}
        for row in rows:
            if row['account_key']:
                by_account.setdefault(row['account_key'], []).append(row)
        for group in by_account.values():
            people = {r['employee_id'] for r in group}
            if len(people) < 2:
                continue
            for row in group:
                others = sorted({r['employee_name'] for r in group
                                 if r['employee_id'] != row['employee_id']})
                row['checks'].append(_("Same account as %s in this list",
                                       ', '.join(others)))
        totals = {}
        for row in rows:
            total = totals.setdefault(row['currency_id'], {
                'currency': row['currency'], 'symbol': row['symbol'],
                'decimals': row['decimals'], 'count': 0, 'amount': 0.0})
            total['count'] += 1
            # what is sent: a zero or negative take-home pays nothing
            total['amount'] += max(row['amount'], 0.0)
        primary = self.env['pb.pay.delivery']._primary_currency(run)
        totals = sorted(totals.values(),
                        key=lambda t: (t['currency'] != (primary.name or ''),
                                       t['currency']))
        return {
            'rows': rows,
            'totals': totals,
            'count': len(rows),
            'check_count': sum(1 for r in rows if r['checks']),
            'left_out': left,
        }

    # ------------------------------------------------------- the screen
    @api.model
    def pb_summary(self, run):
        """What Pay & deliver shows beside the button. No account numbers."""
        data = self._pb_build_rows(run)
        return {
            'count': data['count'],
            'check_count': data['check_count'],
            'no_account': sum(1 for r in data['rows'] if not r['account']),
            'totals': [{'currency': t['currency'], 'symbol': t['symbol'],
                        'amount': t['amount'], 'count': t['count']}
                       for t in data['totals']],
            'left_out': data['left_out'],
            'approved': (run.state or '') == 'done',
            'formats': list(FORMATS),
            # for the bank file's left-out hint only; popped before the screen
            'payable_slip_ids': [r['slip_id'] for r in data['rows'] if r['account']],
        }

    # --------------------------------------------------------- the files
    @api.model
    def _pb_filename(self, run, fmt):
        bits = [_("Payment list"), _file_part(run.name)]
        if run.date_end:
            bits.append(fields.Date.to_string(run.date_end))
        return '%s.%s' % (' - '.join(b for b in bits if b), fmt)

    @api.model
    def _pb_amount_text(self, row):
        return ('%.' + str(max(int(row['decimals'] or 0), 0)) + 'f') % row['amount']

    @api.model
    def _pb_cells(self, row):
        """One row as the file's cells, text escaped (amount stays a number)."""
        out = []
        for key, _label in self._pb_columns():
            if key == 'amount':
                out.append(row['amount'])
            elif key == 'check':
                out.append(safe_text('; '.join(row['checks'])))
            else:
                out.append(safe_text(row[key]))
        return out

    @api.model
    def _pb_footer(self, data):
        """Totals per currency, the row count and the rows with a check."""
        lines = []
        for total in data['totals']:
            lines.append((_("Total %s", total['currency']), total['count'],
                          total['amount'], total['currency'], total['decimals']))
        return lines

    @api.model
    def _pb_csv(self, data):
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator='\r\n')
        writer.writerow([label for _key, label in self._pb_columns()])
        for row in data['rows']:
            cells = self._pb_cells(row)
            cells[6] = self._pb_amount_text(row)
            writer.writerow(cells)
        writer.writerow([])
        for label, count, amount, currency, decimals in self._pb_footer(data):
            writer.writerow([label, _("%s people", count) if count != 1 else _("1 person"),
                             '', '', '', '',
                             ('%.' + str(max(int(decimals or 0), 0)) + 'f') % amount,
                             currency])
        writer.writerow([_("Rows"), data['count']])
        writer.writerow([_("Rows with a check"), data['check_count']])
        # a byte-order mark so a spreadsheet reads the names' accents right
        return buf.getvalue().encode('utf-8-sig')

    @api.model
    def _pb_xlsx(self, data, run):
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("The Excel file cannot be made on this server. Download the CSV file instead."))
        out = io.BytesIO()
        workbook = xlsxwriter.Workbook(out, {
            'in_memory': True,
            # every text cell is TEXT: never a formula, never a number (an
            # account number keeps its leading zeros and its every digit)
            'strings_to_formulas': False,
            'strings_to_numbers': False,
            'strings_to_urls': False,
        })
        workbook.set_properties({'title': _("Payment list"), 'author': '',
                                 'company': '', 'comments': ''})
        sheet = workbook.add_worksheet(_("Payment list")[:31])
        head = workbook.add_format({'bold': True, 'bg_color': '#EDEAF8',
                                    'font_color': '#241F52', 'border': 1})
        text = workbook.add_format({'num_format': '@', 'border': 1})
        bold = workbook.add_format({'bold': True})
        number_formats = {}

        def money(decimals, strong=False):
            key = (int(decimals or 0), strong)
            if key not in number_formats:
                pattern = '#,##0' + ('.' + '0' * key[0] if key[0] > 0 else '')
                spec = {'num_format': pattern, 'border': 1}
                if strong:
                    spec.update(bold=True, border=0)
                number_formats[key] = workbook.add_format(spec)
            return number_formats[key]

        columns = self._pb_columns()
        widths = [16, 28, 28, 22, 18, 22, 16, 10, 34, 14, 60]
        for c, (_key, label) in enumerate(columns):
            sheet.write_string(0, c, label, head)
            sheet.set_column(c, c, widths[c] if c < len(widths) else 16)
        r = 0
        for r, row in enumerate(data['rows'], start=1):
            for c, value in enumerate(self._pb_cells(row)):
                if c == 6:
                    sheet.write_number(r, c, float(value or 0.0), money(row['decimals']))
                else:
                    sheet.write_string(r, c, value or '', text)
        r += 2
        for label, count, amount, currency, decimals in self._pb_footer(data):
            sheet.write_string(r, 0, label, bold)
            sheet.write_string(r, 1, _("%s people", count) if count != 1 else _("1 person"))
            sheet.write_number(r, 6, float(amount), money(decimals, strong=True))
            sheet.write_string(r, 7, currency)
            r += 1
        sheet.write_string(r, 0, _("Rows"), bold)
        sheet.write_number(r, 1, data['count'])
        sheet.write_string(r + 1, 0, _("Rows with a check"), bold)
        sheet.write_number(r + 1, 1, data['check_count'])
        sheet.freeze_panes(1, 0)
        workbook.close()
        return out.getvalue()

    @api.model
    def pb_build(self, run, fmt):
        """(filename, mimetype, bytes, data) — no access check: callers use
        `pb_download`, which holds the door and writes the trail line."""
        if fmt not in FORMATS:
            raise UserError(_("Choose Excel or CSV."))
        data = self._pb_build_rows(run)
        if fmt == 'csv':
            payload = self._pb_csv(data)
            mimetype = 'text/csv; charset=utf-8'
        else:
            payload = self._pb_xlsx(data, run)
            mimetype = ('application/vnd.openxmlformats-officedocument.'
                        'spreadsheetml.sheet')
        return self._pb_filename(run, fmt), mimetype, payload, data

    @api.model
    def _pb_ready(self, run_id, fmt):
        """The door, then the two plain refusals. Returns the run."""
        try:
            run = self.env['hr.payslip.run'].browse(int(run_id))
        except (TypeError, ValueError):
            raise UserError(_("That pay run no longer exists."))
        self._pb_check_door(run)
        if fmt not in FORMATS:
            raise UserError(_("Choose Excel or CSV."))
        if (run.state or '') != 'done':
            raise UserError(_("“%s” has not been approved yet, so its payment list cannot be downloaded. Send the pay run in for approval first.", run.name or ''))
        return run

    @api.model
    def pb_download(self, run_id, fmt):
        """The one way out: the door, the file, one trail line."""
        run = self._pb_ready(run_id, fmt)
        filename, mimetype, payload, data = self.pb_build(run, fmt)
        if not data['count']:
            raise UserError(_("Nobody in this pay run is left to pay by bank transfer, so there is no payment list."))
        # the trail: who, when (the entry's own time), what — never a number
        self.env['pb.money.approval.mixin'].audit(
            run, 'pb_payment_list', _("Payment list (any bank) downloaded"), '',
            _("%(who)s · %(kind)s · %(rows)s rows · %(checks)s need a check",
              who=self.env.user.name, kind=fmt.upper(), rows=data['count'],
              checks=data['check_count']))
        return filename, mimetype, payload


class PbPayDeliveryPaymentList(models.AbstractModel):
    _inherit = 'pb.pay.delivery'

    @api.model
    def get_delivery_data(self, run_id):
        data = super().get_delivery_data(run_id)
        run = self._run(run_id)
        summary = self.env['pb.payment.list'].pb_summary(run)
        payable = set(summary.pop('payable_slip_ids', []))
        # the bank file's left-out list is no longer a dead end: how many of
        # the people it leaves out the payment list can pay (approved account)
        validation = data.get('validation') or {}
        validation['payment_list_can_pay'] = len(
            {x.get('slip_id') for x in validation.get('excluded') or []} & payable)
        data['payment_list'] = summary
        return data

    @api.model
    def payment_list_check(self, run_id, fmt):
        """Asked by the screen before it downloads, so a refusal is a plain
        sentence on screen rather than a failed download."""
        List = self.env['pb.payment.list']
        run = List._pb_ready(run_id, fmt)
        if not List._pb_slips(run)[0]:
            raise UserError(_("Nobody in this pay run is left to pay by bank transfer, so there is no payment list."))
        return {'ok': True}
