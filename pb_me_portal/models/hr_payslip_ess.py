# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ESS tax-sheet helper — a PIT summary per payslip, config-driven.

Which line codes are surfaced is a CONFIG param (`pb_me_portal.tax_codes`) — the
VN PIT-relevant codes come from the live formula config, never hardcoded logic
(handover §2). The helper reads `line_ids` by code (the NET precedent), so it
degrades gracefully when a code is absent from a given config.
"""

from odoo import api, models

_TAXCODES_PARAM = 'pb_me_portal.tax_codes'
# VN demo config PIT-relevant lines (demo_catalog.py): gross, the employee
# insurance that reduces the base, and the tax itself. TXBASE is a helper that
# does not emit a payslip line in this config, so it is intentionally omitted.
_DEFAULT_TAXCODES = 'GROSS,SIEMP,HIEMP,UIEMP,PIT'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _ess_tax_codes(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _TAXCODES_PARAM, _DEFAULT_TAXCODES)
        # order-preserving, de-duplicated
        seen, out = set(), []
        for c in (raw or '').split(','):
            c = c.strip()
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _ess_tax_rows(self, codes):
        """{code: {'label', 'amount'}} for THIS slip, in `codes` order. A code
        with no matching line is omitted (degrade gracefully)."""
        self.ensure_one()
        by_code = {}
        for line in self.line_ids:
            if line.code and line.code in codes and line.code not in by_code:
                by_code[line.code] = {'label': line.name, 'amount': line.total}
        return by_code
