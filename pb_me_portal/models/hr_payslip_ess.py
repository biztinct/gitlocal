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
    def _ess_visible_domain(self):
        """What an employee may see of their own payslips beyond the state.

        WDGAP PR-C: a payslip whose pay the pay team has put ON HOLD is not
        shown on My Payobook until the hold is released (pb_pay_delivery owns
        `pb_pay_hold`; this module does not depend on it, so the filter is
        applied only where the field exists).
        """
        if 'pb_pay_hold' in self._fields:
            return [('pb_pay_hold', '=', False)]
        return []

    def _ess_visible(self):
        """These payslips, minus the ones the employee may not see yet."""
        domain = self._ess_visible_domain()
        if not domain:
            return self
        return self.filtered_domain(domain)

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
