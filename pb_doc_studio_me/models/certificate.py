# -*- coding: utf-8 -*-
"""A person's own pay on their own certificate (owner ruling, F-b 2).

A certificate is asked for on My Payobook by the employee for THEMSELF
(`pb_portal_request` refuses anybody else's record). When HR has added the
studio field "Monthly pay" to its wording, the figure is the person's own:
it is worked out here exactly as the salary certificate works out its own
`${salary}` (the running contract's agreed wage, read by the server) and
handed to the letter as one of the certificate's own values — whoever
presses the button (the employee for an employment certificate, HR's
approver for a salary one). Nobody else's pay can come this way: the value
is computed for the certificate's own employee only, and only when the
wording asks for it. Outside certificates the studio's pay rail is
unchanged (a person preparing a letter for a colleague without the right to
see pay is refused).
"""
from odoo import models
from odoo.exceptions import AccessError
from odoo.tools.misc import format_amount

from odoo.addons.pb_doc_studio.models.doc_render import field_keys

PAY_KEY = 'monthly_pay'


class PbMeCertificateDocStudio(models.Model):
    _inherit = 'pb.me.certificate'

    def _pbdsme_wording_keys(self):
        """Every field the wording this certificate will print uses (its
        company / country copy, every language)."""
        self.ensure_one()
        rec = self.sudo()
        tmpl = rec._pb_template()
        if not tmpl:
            return set()
        chosen = self.env['pb.hr.letter'].sudo()._pbds_swap_template(tmpl, rec.employee_id)
        keys = set()
        for body in [chosen.with_context(lang=lang).body_html or ''
                     for lang in {'en_US', rec.lang or 'en_US'}] + \
                [v.body_html or '' for v in chosen.sudo().pbds_version_ids]:
            keys.update(field_keys(str(body)))
        return keys

    def _pbdsme_own_pay(self):
        """The certificate's own employee's monthly pay, in its language —
        the salary certificate's own reading. '' without a running contract;
        '' when the site's access rules refuse the figure even to the system
        (ledger DS-3)."""
        self.ensure_one()
        rec = self.sudo()
        contract = rec._pb_running_contract(rec.employee_id)
        if not contract:
            return ''
        env = rec.with_context(lang=rec.lang or 'en_US').env
        try:
            wage = contract.sudo().wage
            currency = contract.currency_id if 'currency_id' in contract._fields \
                and contract.currency_id else rec.company_id.currency_id
        except AccessError:
            return ''
        return format_amount(env, wage or 0.0, currency, lang_code=rec.lang or 'en_US')

    def _pb_values(self):
        values = super()._pb_values()
        if PAY_KEY not in values and PAY_KEY in self._pbdsme_wording_keys():
            values[PAY_KEY] = self._pbdsme_own_pay()
        return values
