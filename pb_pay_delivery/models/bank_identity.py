# -*- coding: utf-8 -*-
"""WDGAP S2-C — a bank's national code on the bank record.

`res.bank` (core) holds a name and a SWIFT/BIC code but no national clearing
code, and the accounts our importers make carry none either. A payment-list
bank layout that needs the code (`bank_clearing_code`) reads, in this order
(`pb.payment.list._pb_bank_identity`):

  1. the ACCOUNT's own code (`res.partner.bank.clearing_number`, core) — an
     Indian IFSC or a Singapore branch code is per account;
  2. this field on the bank record — the company's own correction;
  3. the bank directory (`pb.bank.registry`, by the bank's name and the
     layout's country).

Nothing here is read by the Vietnamese bank file.
"""

from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'

    pb_clearing_code = fields.Char(
        string='Bank code',
        help="The bank's national code, used by bank payment files: Indonesia "
             "the 3-digit bank code, Singapore the 4-digit bank code. (An "
             "Indian IFSC belongs to each account, not to the bank.)")
