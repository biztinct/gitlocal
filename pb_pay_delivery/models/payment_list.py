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

THE GATE (WDGAP IDB2, owner ruling). The list is downloaded only once a
second person approved it, through the Vietnamese bank file's own approval
gate — see `PbPaymentListFile` below for which gate and why it is a record of
its own. Each download writes one trail line (who, when, how many rows — never
an account number).

WHAT IT NEVER DOES. It does not change the bank file, the two bank stores,
how they are approved, or any payment status.
"""

import csv
import hashlib
import io
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_bank_ocr.models.vn_bank_dictionary import name_similarity

from .bank_file import BANKFILE_PROCESS_KEY, STATES

_logger = logging.getLogger(__name__)

#: The name bands of the bank-document check (`name_match_band`): 85 and up is
#: the same person's name; under 60 is somebody else's.
NAME_MATCH = 85.0
NAME_CLOSE = 60.0

#: A text cell that starts with one of these is read as a formula by a
#: spreadsheet. Escaped with a leading apostrophe in both files.
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')

#: The kinds of file the list is offered as.
FORMATS = ('xlsx', 'csv')
MIMETYPES = {
    'csv': 'text/csv; charset=utf-8',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


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
    def _pb_summary(self, run):
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
            # what the list says right now, to tell whether the approved one
            # still says the same (WDGAP IDB2); popped before the screen
            'content_hash': self._pb_content_hash(self._pb_csv(data)),
        }

    @api.model
    def _pb_content_hash(self, csv_bytes):
        return hashlib.sha256(csv_bytes or b'').hexdigest()

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
    def _pb_build(self, run, fmt):
        """(filename, mimetype, bytes, data). No door and no log, and NOT a
        way out: nothing is ever downloaded from here (the approved record,
        `pb.payment.list.file`, is the only door). Used by the tests."""
        if fmt not in FORMATS:
            raise UserError(_("Choose Excel or CSV."))
        data = self._pb_build_rows(run)
        if fmt == 'csv':
            payload = self._pb_csv(data)
        else:
            payload = self._pb_xlsx(data, run)
        return self._pb_filename(run, fmt), MIMETYPES[fmt], payload, data

    # ------------------------------------------------------------ the way out
    @api.model
    def _pb_run(self, run_id):
        try:
            run = self.env['hr.payslip.run'].browse(int(run_id))
        except (TypeError, ValueError):
            raise UserError(_("That pay run no longer exists."))
        return self._pb_check_door(run)

    @api.model
    def _pb_approved_file(self, run_id, fmt):
        """The door, then the approved list — refused in the bank file's own
        words. Returns the `pb.payment.list.file`."""
        run = self._pb_run(run_id)
        # WDGAP S2-C: 'bank' = the bank's own file made with a bank layout
        if fmt not in FORMATS and fmt != 'bank':
            raise UserError(_("Choose Excel or CSV."))
        File = self.env['pb.payment.list.file']
        approved = File.search([('run_id', '=', run.id), ('state', '=', 'approved')],
                               order='id desc', limit=1)
        if not approved:
            latest = File._pb_latest(run)
            waiting = ''
            if latest and latest.state == 'pending':
                waiting = ' ' + _("The one that was prepared is with %s.",
                                  latest._waiting_for() or _('its approver'))
            raise UserError(_("There is no approved payment list for this pay run yet.") + waiting)
        return approved

    @api.model
    def _pb_download(self, run_id, fmt):
        """The one way out: the door, the APPROVED bytes, one trail line."""
        return self._pb_approved_file(run_id, fmt)._pb_download_bytes(fmt)


class PbPaymentListFile(models.Model):
    """WDGAP IDB2 (owner ruling): the payment list needs the SAME second
    approval as the Vietnamese bank file before it can be downloaded.

    WHICH GATE, AND WHY ITS OWN RECORD. The bank file's gate approves ONE set
    of bytes (`pb.bank.file`: the approval stamps `approved_hash`, a download
    re-checks it) — it is keyed per FILE, not per pay run. An approval of the
    Vietnamese file therefore cannot cover the list, whose bytes are
    different. So the list is its own record, approved through the SAME
    mechanism: the same catalogue process (`bankfile`), hence the same
    published route, the same approvers, the same independence setting per
    company, the same engine. Nothing is added to the catalogue and no route
    is laid: this model has no `_approval_seed_default`, and its capabilities
    and coverage are the bank file's own.

    Like the bank file: preparing writes the bytes (Excel AND CSV, approved
    together), a sha256 of them, and asks; a download is refused unless the
    record is approved and the stored bytes still hash to what was approved;
    preparing again replaces the previous list and withdraws its request.
    """
    _name = 'pb.payment.list.file'
    _inherit = ['biz.approval.adapter.mixin', 'pb.money.approval.mixin']
    _description = 'Payment list (any bank)'
    _order = 'id desc'

    #: the Vietnamese bank file's own catalogue process — its routes, its
    #: approvers, its independence setting (`pb.bank.file`)
    _approval_process_key = BANKFILE_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', required=True,
                             index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency')
    xlsx_attachment_id = fields.Many2one('ir.attachment', readonly=True,
                                         ondelete='restrict', copy=False)
    csv_attachment_id = fields.Many2one('ir.attachment', readonly=True,
                                        ondelete='restrict', copy=False)
    file_hash = fields.Char(string='File stamp', readonly=True, copy=False)
    approved_hash = fields.Char(string='Approved stamp', readonly=True,
                                copy=False)
    #: what the list said when it was prepared (its CSV), to tell the screen
    #: when the pay run's people or bank details have moved on since
    content_hash = fields.Char(readonly=True, copy=False)
    row_count = fields.Integer(string='Rows', readonly=True)
    check_count = fields.Integer(string='Rows with a check', readonly=True)
    control_total = fields.Monetary(string='Control total', readonly=True,
                                    currency_field='currency_id')
    totals_json = fields.Text(readonly=True)
    generated_by = fields.Many2one('res.users', string='Prepared by',
                                   readonly=True, default=lambda s: s.env.user)
    generated_at = fields.Datetime(readonly=True, default=fields.Datetime.now)
    superseded_by_id = fields.Many2one('pb.payment.list.file',
                                       string='Replaced by', readonly=True,
                                       ondelete='set null')
    downloaded_at = fields.Datetime(readonly=True)
    downloaded_by = fields.Many2one('res.users', readonly=True)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)
    #: A seat is also a read (ledger AM60), as on the bank file.
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_payment_list_file_seat_rel', 'file_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('run_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _("Payment list (any bank) · %s", rec.run_id.name or '')

    # ------------------------------------------------------------ reading
    @api.model
    def _pb_latest(self, run):
        return self.search([('run_id', '=', run.id), ('state', '!=', 'superseded')],
                           order='id desc', limit=1)

    def _pb_totals(self):
        self.ensure_one()
        try:
            rows = json.loads(self.totals_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    # ------------------------------------------------------------ preparing
    @api.model
    def prepare(self, run, layout=None, payment_date=None, company_account=None):
        """Build both files, store them, replace the last try. The caller
        sends the record in (`biz.approval.engine.submit`).

        WDGAP S2-C: with a bank ``layout`` (a payment-list layout), the bank's
        own file is made from the same rows and stored as a THIRD file,
        approved with the other two; the general list's Check column then
        says who is not in the bank file and why. Without one, nothing
        differs from before (the general list is byte-identical)."""
        run = run if isinstance(run, models.BaseModel) \
            else self.env['hr.payslip.run'].browse(int(run))
        List = self.env['pb.payment.list']
        List._pb_check_door(run)
        self.require_pay()
        if (run.state or '') != 'done':
            raise UserError(_("“%s” has not been approved yet, so its payment list cannot be prepared. Send the pay run in for approval first.", run.name or ''))
        bank = None
        if layout:
            layout = List._pb_layout(layout)
            if payment_date and isinstance(payment_date, str):
                payment_date = fields.Date.to_date(payment_date)
            payment_date = payment_date or fields.Date.context_today(self)
            bank = List._pb_layout_build(run, layout, {
                'payment_date': payment_date,
                'company_account': company_account or ''})
            data = List._pb_mark_left_out(bank['list_data'], layout, bank)
            if data['count'] and not bank['count']:
                raise UserError(_("Nobody in this pay run can be put in the %s file. See who is left out and why, or prepare the general list instead.", layout.name))
        else:
            data = List._pb_build_rows(run)
        if not data['count']:
            raise UserError(_("Nobody in this pay run is left to pay by bank transfer, so there is no payment list."))
        files = {'csv': List._pb_csv(data), 'xlsx': List._pb_xlsx(data, run)}
        Attachment = self.env['ir.attachment'].sudo()
        attachments = {}
        for fmt, payload in files.items():
            attachments[fmt] = Attachment.create({
                'name': List._pb_filename(run, fmt),
                'type': 'binary',
                'raw': payload,
                'res_model': self._name,
                'res_id': 0,
                'mimetype': MIMETYPES[fmt],
            })
        company = getattr(run, 'company_id', False) or self.env.company
        primary = self.env['pb.pay.delivery']._primary_currency(run)
        first = data['totals'][0] if data['totals'] else {}
        record = self.create({
            'run_id': run.id,
            'company_id': company.id,
            'currency_id': primary.id,
            'xlsx_attachment_id': attachments['xlsx'].id,
            'csv_attachment_id': attachments['csv'].id,
            'file_hash': self._pb_hash(files['xlsx'], files['csv']),
            # what the GENERAL list says (the screen compares it with the
            # general list now; a bank layout's left-out notes are not in it)
            'content_hash': List._pb_content_hash(
                List._pb_csv(List._pb_build_rows(run)) if bank else files['csv']),
            'row_count': data['count'],
            'check_count': data['check_count'],
            # the fact a route may test is the bank file's "control total":
            # the total in the run's own money (never two currencies added)
            'control_total': first.get('amount', 0.0)
            if first.get('currency') == primary.name else 0.0,
            'totals_json': json.dumps([{'currency': t['currency'],
                                        'amount': t['amount'],
                                        'count': t['count']}
                                       for t in data['totals']]),
            'generated_by': self.env.uid,
            'generated_at': fields.Datetime.now(),
        })
        attachments['xlsx'].write({'res_id': record.id})
        attachments['csv'].write({'res_id': record.id})
        if bank:
            payload = bank['payload']
            bank_attachment = Attachment.create({
                'name': bank['filename'], 'type': 'binary', 'raw': payload,
                'res_model': self._name, 'res_id': record.id,
                'mimetype': bank['mimetype'],
            })
            record.sudo().write({
                'layout_id': layout.id,
                'layout_name': layout.name,
                'layout_attachment_id': bank_attachment.id,
                'layout_hash': hashlib.sha256(payload).hexdigest(),
                'layout_row_count': bank['count'],
                'layout_total': bank['total'],
                'layout_currency': bank['currency'],
                'layout_excluded_json': json.dumps(bank['excluded']),
                'layout_excluded_count': len(bank['excluded']),
                'payment_date': payment_date,
                'company_account': company_account or False,
                # the stamp covers all three files
                'file_hash': self._pb_hash(files['xlsx'], files['csv'], payload),
            })
        record._supersede_earlier()
        return record

    @staticmethod
    def _pb_hash(xlsx_bytes, csv_bytes, bank_bytes=None):
        stamp = (hashlib.sha256(xlsx_bytes or b'').hexdigest().encode()
                 + hashlib.sha256(csv_bytes or b'').hexdigest().encode())
        if bank_bytes is not None:
            # WDGAP S2-C: the bank's own file is approved with the list
            stamp += hashlib.sha256(bank_bytes).hexdigest().encode()
        return hashlib.sha256(stamp).hexdigest()

    def _live_hash(self):
        """The stamp of ALL the files as they are right now, read from the
        attachments every time (ledger AM46, as the bank file)."""
        self.ensure_one()
        xlsx = self.xlsx_attachment_id.sudo()
        csv_file = self.csv_attachment_id.sudo()
        if not xlsx or not csv_file:
            return ''
        if self.layout_hash:
            bank = self.layout_attachment_id.sudo()
            if not bank:
                return ''
            return self._pb_hash(xlsx.raw or b'', csv_file.raw or b'', bank.raw or b'')
        return self._pb_hash(xlsx.raw or b'', csv_file.raw or b'')

    def _supersede_earlier(self):
        self.ensure_one()
        earlier = self.sudo().search([
            ('run_id', '=', self.run_id.id), ('id', '!=', self.id),
            ('state', 'not in', ('superseded', 'rejected'))])
        engine = self.env['biz.approval.engine']
        for old in earlier:
            request = old.approval_request_id
            if request and request.state in ('pending', 'blocked'):
                try:
                    engine.sudo().cancel(
                        request, _("A newer payment list replaced this one."))
                except Exception:   # noqa: BLE001 — never stop the new list
                    _logger.warning('pb_pay_delivery: could not withdraw the '
                                    'request on payment list %s', old.id)
            old.write({'state': 'superseded', 'superseded_by_id': self.id,
                       'approved_hash': False})
        return True

    # ------------------------------------------------------------ adapter
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'approved'):
            raise UserError(_("This payment list has already been sent in."))
        if self.state == 'superseded':
            raise UserError(_("A newer payment list has replaced this one. Send that one in instead."))
        if not self.xlsx_attachment_id or not self.csv_attachment_id:
            raise UserError(_("There is no file to approve."))
        return True

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        run = self.run_id
        scope_keys, scope_label = self.scope_of_run(run)
        first = not bool(self.sudo().search_count([
            ('run_id', '=', run.id), ('id', '!=', self.id),
            ('state', '=', 'approved')]))
        makers = set(self.run_makers(run))
        if self.generated_by:
            makers.add(self.generated_by.id)
        totals = ' · '.join('{:,.0f} {}'.format(t.get('amount') or 0.0, t.get('currency') or '')
                            for t in self._pb_totals())
        return {
            'company_id': company.id,
            'title': self.name or _("Payment list (any bank)"),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            # any bank: the route that covers every bank file
            'kind_key': 'any',
            # the bank file's own facts, so a route that tests them reads them
            'facts': {
                'control_total': {'value': float(self.control_total or 0.0),
                                  'unit': currency.name or ''},
                'row_count': {'value': self.row_count, 'unit': ''},
                'excluded_count': {'value': self.layout_excluded_count or 0, 'unit': ''},
                'run_approved': {'value': self.run_is_approved(run), 'unit': ''},
                'first_file_for_run': {'value': first, 'unit': ''},
            },
            'amount': float(self.control_total or 0.0),
            'currency_id': currency.id,
            'maker_uids': sorted(u for u in makers if u),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._live_hash(),
            'evidence': [
                {'key': 'run_approved', 'name': _('The pay run is approved'),
                 'ok': self.run_is_approved(run), 'note': run.name or ''},
                {'key': 'payment_list_totals',
                 'name': _("Totals per currency"), 'ok': True, 'note': totals},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return self.env['pb.bank.file']._approval_capabilities()

    @api.model
    def _approval_scope_options(self, company):
        return self.env['pb.bank.file']._approval_scope_options(company)

    @api.model
    def _approval_coverage_scopes(self, company):
        return self.env['pb.bank.file']._approval_coverage_scopes(company)

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.row_count == 1:
            return _("1 payment")
        return _("%s payments", self.row_count)

    def _approval_detail(self, request):
        """What an approver asks: how much, in which money, and who needs a
        look. Names and the Check words only — never an account number."""
        self.ensure_one()
        chips = [{'label': _("Kind of file"), 'value': _("Payment list (any bank)")}]
        if self.layout_name:
            # WDGAP S2-C: the bank's own file goes with it
            chips.append({'label': _("Bank layout"), 'value': self.layout_name})
            chips.append({'label': _("In the bank file"),
                          'value': _("%(n)s payments · %(total)s %(currency)s",
                                     n=self.layout_row_count,
                                     total='{:,.2f}'.format(self.layout_total or 0.0),
                                     currency=self.layout_currency or '')})
        for total in self._pb_totals():
            chips.append({'label': _("Total %s", total.get('currency') or ''),
                          'value': '{:,.0f}'.format(total.get('amount') or 0.0)})
        rows = []
        for left in self._pb_layout_excluded()[:40]:
            rows.append({'head': (left.get('employee') or '')[:40],
                         'sub': _("Not in the bank file"),
                         'cells': ['; '.join(left.get('reasons') or [])[:120]],
                         'tone': 'off'})
        data = self.env['pb.payment.list'].sudo()._pb_build_rows(self.run_id.sudo())
        for row in [r for r in data['rows'] if r['checks']][:max(40 - len(rows), 0)]:
            rows.append({'head': (row['employee_name'] or '')[:40], 'sub': '',
                         'cells': ['; '.join(row['checks'])[:120]], 'tone': 'off'})
        if not rows:
            return {'title': _("Nobody in this list needs a check"),
                    'columns': [], 'rows': [], 'chips': chips, 'note': ''}
        return {'title': _("Rows that need a check"), 'columns': [_("Check")],
                'rows': rows, 'chips': chips,
                'note': _("Account numbers come from approved bank details only. Read the Check column before paying.")}

    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned', 'approved_hash': False})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected', 'approved_hash': False})
        return True

    def _approval_apply(self, request):
        """Approved: THESE bytes, and nothing else, may be downloaded."""
        self.ensure_one()
        if self.state == 'approved' and self.approved_hash:
            return True
        self.require_pay(_("the payment list"))
        live = self._live_hash()
        if not live:
            raise UserError(_("The file is missing, so it cannot be approved."))
        if self.file_hash and live != self.file_hash:
            raise UserError(_("The payment list changed after it was sent in, so this approval no longer covers it. Prepare it again."))
        self.sudo().write({'state': 'approved', 'approved_hash': live})
        self.env['biz.approval.event']._log(
            'applied',
            _("%(who)s approved the payment list %(name)s (%(rows)s payments)",
              who=self.env.user.name, name=self.name or '', rows=self.row_count),
            company=self.company_id, request=request)
        self.audit(self, 'state', _("Payment list (any bank)"),
                   _('Waiting for approval'), _('Approved'))
        return True

    # ------------------------------------------------------------ the way out
    def _pb_download_bytes(self, fmt):
        """Refuses anything but the approved bytes; one trail line on the
        pay run (who, how many rows — never an account number)."""
        self.ensure_one()
        self.require_pay(_("the payment list"))
        if self.state == 'superseded':
            raise UserError(_("A newer payment list has replaced this one. Download that one instead."))
        if self.state != 'approved' or not self.approved_hash:
            raise UserError(_("This payment list has not been approved yet, so it cannot be downloaded. It is with %s.", self._waiting_for() or _('its approver')))
        if self._live_hash() != self.approved_hash:
            raise UserError(_("This is not the approved payment list — what is stored no longer matches what was signed off. Prepare it again."))
        if fmt == 'bank':
            # WDGAP S2-C: the bank's own file, approved with the list
            if not self.layout_attachment_id:
                raise UserError(_("This payment list was prepared without a bank layout, so there is no bank file to download. Prepare it again with a bank layout."))
            attachment = self.layout_attachment_id.sudo()
            self.sudo().write({'downloaded_at': fields.Datetime.now(),
                               'downloaded_by': self.env.uid})
            self.audit(
                self.run_id, 'pb_payment_list', _("Bank file (any bank) downloaded"), '',
                _("%(who)s · %(kind)s · %(rows)s rows · %(left)s left out",
                  who=self.env.user.name, kind=self.layout_name or '',
                  rows=self.layout_row_count, left=self.layout_excluded_count))
            return attachment.name, attachment.mimetype or 'application/octet-stream', \
                attachment.raw or b''
        attachment = (self.xlsx_attachment_id if fmt == 'xlsx'
                      else self.csv_attachment_id).sudo()
        self.sudo().write({'downloaded_at': fields.Datetime.now(),
                           'downloaded_by': self.env.uid})
        self.audit(
            self.run_id, 'pb_payment_list', _("Payment list (any bank) downloaded"), '',
            _("%(who)s · %(kind)s · %(rows)s rows · %(checks)s need a check",
              who=self.env.user.name, kind=fmt.upper(), rows=self.row_count,
              checks=self.check_count))
        return attachment.name, MIMETYPES[fmt], attachment.raw or b''


class PbPayDeliveryPaymentList(models.AbstractModel):
    _inherit = 'pb.pay.delivery'

    def _payment_list_file_payload(self, run, current_hash):
        latest = self.env['pb.payment.list.file']._pb_latest(run)
        payload = self._route_payload(latest)
        payload.update({
            'downloadable': bool(latest and latest.state == 'approved'),
            'fast_lane': self._fast_lane('pb.payment.list.file', run),
            'row_count': latest.row_count if latest else 0,
            # WDGAP S2-C: the bank's own file prepared with it, if any
            'layout_name': latest.layout_name or '' if latest else '',
            'layout_key': latest.layout_id.bank_format or '' if latest else '',
            'layout_row_count': latest.layout_row_count if latest else 0,
            'layout_excluded_count': latest.layout_excluded_count if latest else 0,
            # the run's people or bank details moved on since it was prepared
            'changed': bool(latest and latest.content_hash
                            and latest.content_hash != current_hash),
        })
        return payload

    @api.model
    def get_delivery_data(self, run_id):
        data = super().get_delivery_data(run_id)
        run = self._run(run_id)
        summary = self.env['pb.payment.list']._pb_summary(run)
        payable = set(summary.pop('payable_slip_ids', []))
        current = summary.pop('content_hash', '')
        # the bank file's left-out list is no longer a dead end: how many of
        # the people it leaves out the payment list can pay (approved account)
        validation = data.get('validation') or {}
        validation['payment_list_can_pay'] = len(
            {x.get('slip_id') for x in validation.get('excluded') or []} & payable)
        summary['file'] = self._payment_list_file_payload(run, current)
        # WDGAP S2-C: the bank layouts the list can also be made in
        summary['layouts'] = self.env['pb.payment.list']._pb_layout_payload()
        summary['today'] = fields.Date.to_string(fields.Date.context_today(self))
        data['payment_list'] = summary
        return data

    @api.model
    def prepare_payment_list(self, run_id, layout_key=None, payment_date=None,
                             company_account=None):
        """Prepare the payment list and send it in — the bank file's gate.
        With a bank layout (WDGAP S2-C) the bank's own file goes with it."""
        self._require_access()
        run = self._run(run_id)
        record = self.env['pb.payment.list.file'].prepare(
            run, layout=layout_key or None, payment_date=payment_date or None,
            company_account=company_account or None)
        self.env['biz.approval.engine'].submit(record)
        return {'state': record.state}

    @api.model
    def payment_list_layout_preview(self, run_id, layout_key, payment_date=None,
                                    company_account=None):
        """Who would be in the bank's own file and who is left out, and
        why — before anything is prepared. Writes nothing; no account
        number in the answer."""
        self._require_access()
        List = self.env['pb.payment.list']
        run = List._pb_check_door(self._run(run_id))
        layout = List._pb_layout(layout_key)
        if payment_date and isinstance(payment_date, str):
            payment_date = fields.Date.to_date(payment_date)
        result = List._pb_layout_build(run, layout, {
            'payment_date': payment_date or fields.Date.context_today(self),
            'company_account': company_account or ''})
        return {
            'name': layout.name,
            'inferred': bool(layout.inferred),
            'note': layout.note or '',
            'count': result['count'],
            'total': result['total'],
            'currency': result['currency'],
            'excluded': [{'employee': x['employee'], 'reasons': x['reasons']}
                         for x in result['excluded']],
        }

    @api.model
    def payment_list_check(self, run_id, fmt):
        """Asked by the screen before it downloads, so a refusal is a plain
        sentence on screen rather than a failed download. Writes nothing."""
        record = self.env['pb.payment.list']._pb_approved_file(run_id, fmt)
        if record._live_hash() != record.approved_hash:
            raise UserError(_("This is not the approved payment list — what is stored no longer matches what was signed off. Prepare it again."))
        if fmt == 'bank' and not record.layout_attachment_id:
            raise UserError(_("This payment list was prepared without a bank layout, so there is no bank file to download. Prepare it again with a bank layout."))
        return {'ok': True}
