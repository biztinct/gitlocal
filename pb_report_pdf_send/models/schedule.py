# -*- coding: utf-8 -*-
"""DOCSTUDIO B4 — a regular send of a saved Explorer view as a PDF in my look.

The choice lives on the schedule (`pbrp_pdf`, "Send as: PDF in my look"),
beside the Excel layout choice of pb_excel_layout (one or the other). The
file is made in pb_explorer's one seam, `_pbx_attachment`, with the facade
AS THE RECIPIENT (their companies, divisions and language — the existing
`_pbx_mail_for` rule), so each person gets only their own figures; the look
is the one the person who set up the send prints this view with.

A PDF never stops a send: when it cannot be made the standard Excel goes
instead and that person's history line says why (pb_excel_layout's
`layout_failed` line, with this module's reason).
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_excel_layout.models.pb_explorer_schedule import LAYOUT_FAILS

_logger = logging.getLogger(__name__)

PDF_MIME = 'application/pdf'
PDF_FAIL = 'pdf_failed'
VIEW = 'pb.explorer.view'


class PbExplorerSchedule(models.Model):
    _inherit = 'pb.explorer.schedule'

    pbrp_pdf = fields.Boolean(string='Send as a PDF in my look')

    def _pbrp_build(self, user, explorer, spec):
        """(filename, bytes) — the PDF of this view for `user`, built through
        `explorer` (the facade as that person)."""
        self.ensure_one()
        view = self.view_id.sudo()
        env = explorer.env
        table = view._pbxl_table_for(explorer, spec)
        Pdf = env['pb.report.pdf']
        info = Pdf._pbrp_plain(table)
        try:
            info['sub'] = view.with_context(lang=env.lang)._pbx_period_label() or ''
        except Exception:                                    # noqa: BLE001
            info['sub'] = ''
        owner = self.user_id.sudo()
        look, _origin, _rec = env['pb.report.pdf.look']._pbrp_resolve(
            VIEW, view.id, owner, owner)
        pdf = Pdf._pbrp_pdf(info, look, company=env.company)
        return Pdf._pbrp_file_name(look['title'] or info['title'] or view.name), pdf

    def _pbx_attachment(self, user, standard, explorer=None, spec=None):
        if not self.pbrp_pdf or explorer is None:
            return super()._pbx_attachment(user, standard, explorer=explorer, spec=spec)
        try:
            with self.env.cr.savepoint():
                name, pdf = self._pbrp_build(user, explorer, spec)
            return name, pdf, PDF_MIME
        except Exception:                                    # noqa: BLE001
            _logger.warning('pb_report_pdf_send: schedule %s, user %s: the PDF could not '
                            'be made; the standard Excel was sent', self.id, user.id,
                            exc_info=True)
            fails = LAYOUT_FAILS.get()
            if fails is not None:
                fails[user.id] = (PDF_FAIL, '')
            return standard

    def _pbx_mail_for(self, user):
        """The email's line about the attachment says PDF when it is one."""
        mail = super()._pbx_mail_for(user)
        if not self.pbrp_pdf or not mail:
            return mail
        try:
            if any(att.mimetype == PDF_MIME for att in mail.sudo().attachment_ids):
                env = self.with_context(lang=user.lang or 'en_US').env
                old = env._("The full table is in the attached Excel file.")
                new = env._("The full table is in the attached PDF.")
                body = str(mail.sudo().body_html or '')
                if old in body:
                    mail.sudo().body_html = body.replace(old, new)
        except Exception:                                    # noqa: BLE001
            _logger.debug('pb_report_pdf_send: email line left as it was', exc_info=True)
        return mail

    def _pbx_history(self):
        out = super()._pbx_history()
        Log = self.env['pb.explorer.schedule.log'].sudo()
        failed = Log.search([('schedule_id', '=', self.id), ('state', '=', 'layout_failed'),
                             ('reason', '=like', PDF_FAIL + '|%')])
        if not failed:
            return out
        keys = {(log.batch, log.user_id.name or '') for log in failed}
        label = self.env._("Sent as the standard Excel — the PDF could not be made")
        for entry in out:
            for line in entry['lines']:
                if line['state'] == 'layout_failed' and (entry['batch'], line['name']) in keys:
                    line['label'] = label
        return out

    def _pbx_payload(self):
        out = super()._pbx_payload()
        out['pbrp_pdf'] = bool(self.pbrp_pdf)
        return out


class PbExplorerScheduleFacade(models.AbstractModel):
    """The drawer's "Send as: PDF in my look". Every entry point still
    passes the Explorer's own checks first (`super()`)."""
    _inherit = 'pb.explorer'

    @api.model
    def schedule_save(self, view_id, vals, schedule_id=False):
        vals = dict(vals) if isinstance(vals, dict) else {}
        want_pdf = bool(vals.pop('pbrp_pdf', False))
        if want_pdf and vals.get('layout_id'):
            raise UserError(self.env._("Choose one: your Excel layout or the PDF."))
        out = super().schedule_save(view_id, vals, schedule_id=schedule_id)
        sched = self.env['pb.explorer.schedule'].with_context(active_test=False).browse(out['id'])
        if bool(sched.pbrp_pdf) != want_pdf:
            sched.pbrp_pdf = want_pdf
            out = sched._pbx_payload()
        return out
