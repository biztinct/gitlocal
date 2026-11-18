# -*- coding: utf-8 -*-
"""Data-driven bank-file layouts (Phase F §3, C18.42b; WDGAP S2-C).

A bank transfer file is described entirely by data: a ``pb.bank.file.layout``
header (file type / delimiter / encoding / header row) and an ordered set of
``pb.bank.file.column`` rows, each mapping to a value ``source`` from the slip /
employee master / run.

TWO KINDS OF LAYOUT (WDGAP S2-C, `target`):
  * ``bank_file`` — the Vietnamese bank file (`vietnam.bank.export.wizard`),
    reading the four `vietnam_bank_*` fields. Every layout that existed before
    S2-C is one of these; their bytes are pinned by a golden test.
  * ``payment_list`` — a bank's own file made from the PAYMENT LIST rows
    (`pb.payment.list`: the approved account on record, take-home from the
    one pay-band reading), for banks in any country. Rendered by
    `payment_list_layout.py`, stored beside the list's Excel and CSV and
    approved with them.

Since WDGAP S2-C the "adding a bank is data, zero code" claim is true for both
kinds: the Vietnamese wizard accepts any layout key (`pb_layout_key`, ledger
S2F-1), and shipped layouts are `noupdate` (S2F-2) so a correction made on a
database survives an upgrade. A company copies a shipped layout and edits the
COPY (Settings › Payroll › Bank layouts); a copy belongs to that company.

The layout carries NO code that reaches the employee master for writing: it only
declares which READ-ONLY source each column pulls.
"""

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# The fixed value vocabulary a column may pull. Every one of these is a READ of
# the slip / employee master / run — never a write (safety rail 1).
COLUMN_SOURCES = [
    ('account_number', 'Beneficiary Account Number'),
    ('account_name', 'Beneficiary Account Holder'),
    ('bank_name', 'Beneficiary Bank Name'),
    ('bank_branch', 'Beneficiary Bank Branch'),
    ('employee_code', 'Employee Code'),
    ('employee_name', 'Employee Name'),
    ('net_amount', 'Net Amount'),
    ('period', 'Payroll Period'),
    ('company_account', 'Company Debit Account'),
    ('row_number', 'Row Number (STT)'),
    ('literal', 'Literal / Constant'),
    # WDGAP S2-C — read for the payment-list layouts (a Vietnamese bank file
    # gives these an empty cell, exactly as an unknown source always did)
    ('payment_date', 'Payment date'),
    ('currency', 'Currency'),
    ('bank_bic', 'Bank SWIFT/BIC code'),
    ('bank_clearing_code', 'Bank code (IFSC, bank/branch code)'),
    ('beneficiary_email', 'Employee email'),
    ('reference', 'Payment reference'),
    ('row_count', 'Number of payments'),
    ('control_total', 'Total of the file'),
]

#: The sentence every layout not confirmed by the bank carries in its note
#: (WDGAP S2-C). It cannot be taken out of a shipped general layout, and a
#: company's copy may drop it only once somebody ticked "Confirmed with our
#: bank" (who and when are kept).
CHECK_WITH_BANK = "Check with your bank before the first upload."

#: The words a header or trailer line may carry, between braces.
TEMPLATE_TOKENS = ('count', 'total', 'date', 'company_account', 'reference',
                   'currency')
_TOKEN = re.compile(r'\{([a-z_]+)\}')


class PbBankFileLayout(models.Model):
    # A layout decides what the bank is TOLD — which column carries the account
    # number, which carries the amount. Changing one is as consequential as
    # changing the file, and it is the one money-out surface Phase 5 leaves
    # without a request. So every change is written to the platform trail
    # instead (`data/audit_rules.xml` names the fields).
    _name = 'pb.bank.file.layout'
    _inherit = ['biz.audit.mixin']
    _description = 'Bank Transfer File Layout'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    bank_format = fields.Char(
        required=True, index=True,
        help="Key of this layout (vietcombank, bidv, …; a copy gets its own).")
    file_type = fields.Selection(
        [('csv', 'CSV'), ('txt', 'Fixed-width TXT'), ('xlsx', 'Excel (XLSX)')],
        required=True, default='csv')
    delimiter = fields.Char(
        default=',',
        help="Field delimiter for CSV files (ignored for txt/xlsx).")
    encoding = fields.Char(
        default='utf-8',
        help="Text encoding. VN banks that open the file in Excel usually need "
             "utf-8-sig so diacritics render (a BOM).")
    with_header = fields.Boolean(
        string='Header Row', default=True,
        help="Emit a first row of column headers.")
    active = fields.Boolean(default=True)
    note = fields.Text(
        help="Provenance of this layout (bank template doc, or inferred — flag "
             "inferred layouts for client confirmation).")
    column_ids = fields.One2many(
        'pb.bank.file.column', 'layout_id', string='Columns', copy=True)

    # ------------------------------------------------ WDGAP S2-C
    target = fields.Selection(
        [('bank_file', 'Vietnamese bank file'),
         ('payment_list', 'Payment list (any bank)')],
        string='Made from', required=True, default='bank_file', index=True)
    country_id = fields.Many2one('res.country', string='Country', index=True)
    currency_id = fields.Many2one(
        'res.currency', string='Pays in',
        help="The one money this bank file pays in. Empty: the pay run's own "
             "money. People paid in another money are left out of it, with "
             "the reason.")
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help="Empty for a layout Payobook ships; a company's own copy "
             "belongs to that company.")
    copied_from_id = fields.Many2one('pb.bank.file.layout', string='Copied from',
                                     ondelete='set null', copy=False)
    header_template = fields.Text(
        string='Lines before the payments',
        help="One line per line of text. Words in braces are filled in: "
             "{count} {total} {date} {company_account} {reference} {currency}.")
    trailer_template = fields.Text(
        string='Lines after the payments',
        help="Same words as the lines before the payments.")
    amount_format = fields.Selection(
        [('int', 'Whole number'),
         ('dec2', 'Two decimals (1234.50)'),
         ('implied2', 'Two decimals without the point (123450)')],
        string='Total written as', default='dec2',
        help="How {total} is written in the lines before and after the payments.")
    date_format = fields.Char(
        string='Date written as', default='%Y%m%d',
        help="How {date} and the payment-date column are written, e.g. %Y%m%d "
             "(20260630) or %d/%m/%Y (30/06/2026).")
    line_ending = fields.Selection(
        [('crlf', 'Windows (CR LF)'), ('lf', 'Unix (LF)')],
        string='Line ending', default='crlf')
    ascii_only = fields.Boolean(
        string='Plain letters only',
        help="The bank refuses letters with accents and other non-English "
             "characters: a person whose name or bank details carry one is "
             "left out of the file, with the reason (never changed or cut).")
    code_label = fields.Char(
        string='Name of the bank code',
        help="What this country calls the bank code the file carries "
             "(Indonesia \"Bank code\", India \"IFSC\", Singapore \"Bank / "
             "branch code\"). Used in the reasons people are left out.")
    code_pattern = fields.Char(
        string='Form of the bank code',
        help="A pattern the bank code must match, e.g. ^[A-Z]{4}0[A-Z0-9]{6}$ "
             "for an IFSC. A person whose code does not match is left out.")
    account_pattern = fields.Char(
        string='Form of the account number',
        help="A pattern the account number must match (e.g. ^[0-9]{10}$). "
             "A person whose number does not match is left out.")
    inferred = fields.Boolean(
        string='Not confirmed by the bank',
        help="This layout was not taken from the bank's own published "
             "specification. Check with your bank before the first upload.")
    is_shipped = fields.Boolean(compute='_compute_is_shipped')
    #: a company's copy, checked against the bank's own template by a person
    bank_confirmed = fields.Boolean(string='Confirmed with our bank', copy=False)
    bank_confirmed_by = fields.Many2one('res.users', string='Confirmed by',
                                        readonly=True, copy=False)
    bank_confirmed_on = fields.Datetime(string='Confirmed on', readonly=True,
                                        copy=False)

    _format_uniq = models.Constraint(
        'unique(bank_format)',
        'A bank-file layout already exists for this bank_format key.')

    @api.depends('company_id')
    def _compute_is_shipped(self):
        for rec in self:
            rec.is_shipped = not rec.company_id

    @api.model
    def _for_format(self, bank_format):
        """Resolve the (active) layout for a bank_format key, or empty."""
        if not bank_format:
            return self.browse()
        return self.search([('bank_format', '=', bank_format)], limit=1)

    # ------------------------------------------------------------- checks
    @api.constrains('header_template', 'trailer_template')
    def _check_templates(self):
        for rec in self:
            for text in (rec.header_template, rec.trailer_template):
                unknown = sorted({t for t in _TOKEN.findall(text or '')
                                  if t not in TEMPLATE_TOKENS})
                if unknown:
                    raise ValidationError(_(
                        "The lines before or after the payments use a word this file cannot fill in: %(words)s. Use only: %(known)s.",
                        words=', '.join('{%s}' % t for t in unknown),
                        known=', '.join('{%s}' % t for t in TEMPLATE_TOKENS)))

    @api.constrains('note', 'inferred', 'bank_confirmed', 'company_id', 'target')
    def _check_not_confirmed_note(self):
        """A layout the bank has not confirmed keeps saying so.

        * A shipped general layout (no company, made from the payment list)
          is never "confirmed" and never loses the sentence.
        * A company's copy of one keeps the sentence until somebody ticks
          "Confirmed with our bank" (`pb_set_bank_confirmed`, who + when).
        The Vietnamese layouts (`inferred` off) are not touched."""
        for rec in self:
            shipped_general = not rec.company_id and rec.target == 'payment_list'
            if shipped_general and (rec.bank_confirmed or not rec.inferred):
                raise ValidationError(_("A layout Payobook ships is not confirmed by any bank and stays marked that way. Make your own copy, check it with your bank, then tick “Confirmed with our bank” on the copy."))
            if rec.inferred and not rec.bank_confirmed \
                    and CHECK_WITH_BANK not in (rec.note or ''):
                raise ValidationError(_("Keep “%s” in the note until you tick “Confirmed with our bank”.", CHECK_WITH_BANK))
            if rec.company_id and not rec.inferred and not rec.bank_confirmed \
                    and rec.copied_from_id.inferred:
                raise ValidationError(_("Tick “Confirmed with our bank” before this copy stops saying it is not confirmed."))

    def pb_set_bank_confirmed(self, confirmed):
        """A company's copy: "Confirmed with our bank" on or off, with who
        and when. Off again puts the sentence back in the note."""
        self.ensure_one()
        if not self.company_id:
            raise UserError(_("A layout Payobook ships is not confirmed by any bank and stays marked that way. Make your own copy, check it with your bank, then tick “Confirmed with our bank” on the copy."))
        if confirmed:
            self.write({'bank_confirmed': True, 'inferred': False,
                        'bank_confirmed_by': self.env.uid,
                        'bank_confirmed_on': fields.Datetime.now()})
        else:
            note = self.note or ''
            if CHECK_WITH_BANK not in note:
                note = (note.rstrip() + ' ' + CHECK_WITH_BANK).strip()
            self.write({'bank_confirmed': False, 'inferred': True, 'note': note,
                        'bank_confirmed_by': False, 'bank_confirmed_on': False})
        return True

    @api.constrains('code_pattern', 'account_pattern')
    def _check_patterns(self):
        for rec in self:
            for pattern in (rec.code_pattern, rec.account_pattern):
                if not pattern:
                    continue
                try:
                    re.compile(pattern)
                except re.error:
                    raise ValidationError(_(
                        "The form “%s” cannot be read. Leave it empty, or write a pattern such as ^[0-9]{10}$.", pattern))

    @api.constrains('date_format')
    def _check_date_format(self):
        for rec in self:
            if rec.date_format and '%' not in rec.date_format:
                raise ValidationError(_(
                    "Write the date with %Y (year), %m (month) and %d (day), for example %Y%m%d."))

    # ------------------------------------------------------------- copies
    def _pb_copy_key(self, company):
        """A key nobody else holds: <source key>_c<company>_<n>."""
        self.ensure_one()
        base = re.sub(r'_c\d+_\d+$', '', self.bank_format or 'layout')
        n = 1
        while self.with_context(active_test=False).search_count(
                [('bank_format', '=', '%s_c%s_%s' % (base, company.id, n))]):
            n += 1
        return '%s_c%s_%s' % (base, company.id, n)

    def pb_copy_for_company(self, company=None):
        """A company's own editable copy of this layout (shipped or not)."""
        self.ensure_one()
        company = company or self.env.company
        if not self.exists():
            raise UserError(_("That bank layout no longer exists."))
        copy = self.sudo().copy({
            'name': _("%s (our copy)", self.name),
            'bank_format': self._pb_copy_key(company),
            'company_id': company.id,
            'copied_from_id': self.id,
            'active': True,
        })
        return copy.with_env(self.env)


class PbBankFileColumn(models.Model):
    _name = 'pb.bank.file.column'
    _inherit = ['biz.audit.mixin']
    _description = 'Bank Transfer File Column'
    _order = 'layout_id, sequence, id'

    layout_id = fields.Many2one(
        'pb.bank.file.layout', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    header = fields.Char(help="Column header emitted when the layout has a header row.")
    source = fields.Selection(COLUMN_SOURCES, required=True, default='literal')
    literal_value = fields.Char(help="Constant emitted when source = Literal.")
    width = fields.Integer(
        default=0,
        help="Fixed-width TXT column width. 0 = no padding (variable width).")
    pad = fields.Selection(
        [('right', 'Left-justify (pad right, spaces)'),
         ('left', 'Right-justify (pad left, spaces)'),
         ('zero', 'Right-justify (pad left, zeros)')],
        default='right',
        help="Padding direction for fixed-width TXT.")
    number_format = fields.Selection(
        [('none', 'Raw text'),
         ('int', 'Integer (no separator)'),
         ('int_grouped', 'Integer (thousands separator)'),
         # WDGAP S2-C
         ('dec2', 'Two decimals (1234.50)'),
         ('implied2', 'Two decimals without the point (123450)')],
        default='none',
        help="Numeric rendering for amount columns. Account numbers must stay "
             "'Raw text' to preserve leading zeros.")
    # WDGAP S2-C — a payment-list layout never cuts a value to fit: a value
    # longer than the bank takes leaves the person out, with the reason
    max_length = fields.Integer(
        string='Longest the bank takes', default=0,
        help="0 = no limit. A longer value leaves the person out of the file "
             "(it is never cut).")
    required = fields.Boolean(
        string='Must not be empty',
        help="A person with nothing to put here is left out of the file, "
             "with the reason.")
