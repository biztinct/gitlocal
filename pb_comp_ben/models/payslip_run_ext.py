# -*- coding: utf-8 -*-
"""The finance pack — what finance is handed the moment a run is approved.

THE HOOK IS `action_payslip_run_level2_done`, NOT `done_payslip_run`.

The handover named `done_payslip_run()` as "the done transition". The code says
otherwise and the code wins: on this build `done_payslip_run` is the
**draft → level0** entry (`pb_payruns/models/hr_payslip_run.py:550`, its own
docstring says so), and the final Finance approval that writes 'done' is
`action_payslip_run_level2_done` (`:472`). Hooking the wrong one would have
built a pack on submission and marked awards paid before anybody approved them.

THE PACK NEVER BLOCKS THE APPROVAL. `super()` runs FIRST and its result is what
is returned; everything after it is inside a try/except that ends in a chatter
note. A bank layout that is missing, a report that will not render, an SMTP
server that is down — none of those are reasons a run somebody approved should
fail to be approved.

IT IS SWITCHED OFF ON INSTALL (`pb_comp_ben.finance_pack`), for the same reason
every other sending switch in this programme is: the first run approved after an
upgrade must not email a finance team a file nobody asked for.

MARKING AWARDS PAID IS NOT BEHIND THE SWITCH. That is a fact about the awards,
not a document anybody is sent, and an award that was paid stays paid whether or
not finance wanted a PDF.
"""

import base64
import logging

from odoo import _, models

from .comp_common import (
    P_BANK_FORMAT, P_FINANCE_EMAIL, P_FINANCE_PACK, flag, param,
)

_logger = logging.getLogger(__name__)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_payslip_run_level2_done(self):
        """Finance approval → done, then the pack. ADDITIVE, in that order."""
        res = super().action_payslip_run_level2_done()
        for run in self:
            # Awards first, and outside the switch: this is the ledger catching
            # up with the money, not a document.
            try:
                self.env['pb.oneoff.feed'].mark_paid_for_run(run.id)
            except Exception:               # noqa: BLE001
                _logger.exception(
                    'pb_comp_ben: could not mark awards paid for run %s', run.id)
            if not flag(self.env, P_FINANCE_PACK):
                continue
            try:
                run._pb_build_finance_pack()
            except Exception:               # noqa: BLE001 — never blocks
                _logger.exception(
                    'pb_comp_ben: the finance pack failed for run %s', run.id)
                try:
                    run.sudo().message_post(body=_(
                        "This run is approved. The finance pack could not be "
                        "put together — ask an administrator to check the log; "
                        "the approval itself is unaffected."))
                except Exception:           # noqa: BLE001
                    pass
        return res

    # ------------------------------------------------------------- the pack
    def _pb_build_finance_pack(self):
        """Bank file + one-page summary, attached to the run, then emailed."""
        self.ensure_one()
        made = []
        bank = self._pb_bank_file()
        if bank:
            made.append(bank)
        summary = self._pb_run_summary_pdf()
        if summary:
            made.append(summary)
        if not made:
            self.sudo().message_post(body=_(
                "Nothing could be put in the finance pack for this run."))
            return False
        note = self._pb_pack_email(made)
        self.sudo().message_post(body=_(
            "Finance pack ready: %(files)s.%(note)s",
            files=', '.join(a.name for a in made), note=note))
        return made

    def _pb_bank_file(self):
        """The transfer file, or an honest note saying why there is none.

        The generator refuses (correctly) when no layout is configured, when
        there are no confirmed payslips, or when every row fails validation. Each
        refusal is a SENTENCE the officer can act on, so it is repeated into the
        chatter rather than swallowed — its own refusal pattern
        (`bank_export_wizard.py:224-232`) already says exactly what is wrong.
        """
        self.ensure_one()
        Wizard = self.env['vietnam.bank.export.wizard'].sudo()
        fmt = param(self.env, P_BANK_FORMAT).strip()
        if not fmt:
            layout = self.env['pb.bank.file.layout'].sudo().search(
                [], order='id', limit=1)
            fmt = getattr(layout, 'bank_format', '') or getattr(
                layout, 'code', '') or ''
        if not fmt:
            self.sudo().message_post(body=_(
                "No bank file was built: this company has no bank file layout "
                "set up yet."))
            return None
        try:
            wizard = Wizard.create({
                'payslip_run_id': self.id,
                'bank_format': fmt,
            })
            result = wizard._generate()
        except Exception as e:              # noqa: BLE001 — an honest skip
            self.sudo().message_post(body=_(
                "No bank file was built — %s", str(e)))
            return None
        return self.env['ir.attachment'].sudo().create({
            'name': result['filename'],
            'type': 'binary',
            'datas': result['file_b64'],
            'res_model': self._name,
            'res_id': self.id,
        })

    def _pb_run_summary_pdf(self):
        """One page: the period, the headcount, the totals, who approved it."""
        self.ensure_one()
        report = self.env.ref('pb_comp_ben.action_report_run_summary',
                              raise_if_not_found=False)
        if not report:
            _logger.warning('pb_comp_ben: the run summary report is missing')
            return None
        pdf, _ext = report.sudo()._render_qweb_pdf(
            'pb_comp_ben.report_run_summary_document', res_ids=self.ids)
        name = _('Run summary — %s.pdf') % (self.name or '')
        return self.env['ir.attachment'].sudo().create({
            'name': name.replace('/', '-'),
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

    def _pb_pack_email(self, attachments):
        """Send it on, if somebody said where. Recipient passed EXPLICITLY (R6)."""
        self.ensure_one()
        to = param(self.env, P_FINANCE_EMAIL).strip()
        if not to:
            return _(" Nobody is set to receive it, so it was not emailed.")
        template = self.env.ref('pb_comp_ben.mail_template_finance_pack',
                                raise_if_not_found=False)
        if not template:
            return _(" The pack email is not set up, so it was not sent.")
        try:
            template.sudo().send_mail(
                self.id, force_send=False,
                email_values={
                    'email_to': to,
                    'attachment_ids': [(6, 0, [a.id for a in attachments])],
                })
        except Exception:                   # noqa: BLE001
            _logger.exception('pb_comp_ben: could not email the pack for run %s',
                              self.id)
            return _(" It could not be emailed.")
        return _(" Emailed to %s.") % to

    # -------------------------------------------------- what the page prints
    def pb_pack_summary(self):
        """The numbers the summary page shows. Read-only, and never raises."""
        self.ensure_one()
        slips = self.slip_ids
        total = 0.0
        for slip in slips:
            try:
                total += self.env['vietnam.bank.export.wizard']._slip_net(slip)
            except Exception:               # noqa: BLE001 — one slip, not all
                continue
        trail = []
        for log in self.env['biz.approval.step.log'].sudo().search(
                [('res_model', '=', 'hr.payslip.run'), ('res_id', '=', self.id)],
                order='stamp'):
            trail.append({'to': log.to_state, 'user': log.user_id.name or '',
                          'stamp': log.stamp})
        return {
            'headcount': len(slips),
            'total_net': total,
            # `hr.payslip.run` has NO `company_id` on this build (ledger).
            'currency': (getattr(self, 'company_id', False)
                         or self.env.company).currency_id,
            'trail': trail,
        }
