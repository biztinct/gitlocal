# -*- coding: utf-8 -*-
"""Data-driven bank-file layouts (Phase F §3, C18.42b).

A bank transfer file is described entirely by data: a ``pb.bank.file.layout``
header (file type / delimiter / encoding / header row) and an ordered set of
``pb.bank.file.column`` rows, each mapping to a value ``source`` from the slip /
employee master / run. Adding a new bank is a data file — zero code.

The layout carries NO code that reaches the employee master for writing: it only
declares which READ-ONLY source each column pulls. Actual value resolution +
validation live on the export wizard (``bank_export_wizard.py``).
"""

from odoo import api, fields, models

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
]


class PbBankFileLayout(models.Model):
    _name = 'pb.bank.file.layout'
    _description = 'Bank Transfer File Layout'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    bank_format = fields.Char(
        required=True, index=True,
        help="Key matching the export wizard's bank_format selection "
             "(vietcombank, bidv, techcombank, mb_bank, vietinbank, acb, generic).")
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

    _format_uniq = models.Constraint(
        'unique(bank_format)',
        'A bank-file layout already exists for this bank_format key.')

    @api.model
    def _for_format(self, bank_format):
        """Resolve the (active) layout for a bank_format key, or empty."""
        if not bank_format:
            return self.browse()
        return self.search([('bank_format', '=', bank_format)], limit=1)


class PbBankFileColumn(models.Model):
    _name = 'pb.bank.file.column'
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
         ('int_grouped', 'Integer (thousands separator)')],
        default='none',
        help="Numeric rendering for amount columns. Account numbers must stay "
             "'Raw text' to preserve leading zeros.")
