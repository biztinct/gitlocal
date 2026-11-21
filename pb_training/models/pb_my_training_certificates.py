# -*- coding: utf-8 -*-
"""LEARNING L1 — a person's own certificates, on every learner surface.

The same facade feeds Learning › My learning (back-office staff) and the
portal page `/my/training/certificates` (employees, ledger LN8), so the two
can never show different certificates.

WHO "ME" IS HAS NOT CHANGED: the session user's own employee record, resolved
on every call and never a parameter. The one place an employee id is accepted
is the learning-record PDF, and only from somebody in the training team.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .document_ext import KIND_CERT, KIND_LIC
from .training_common import as_id

_logger = logging.getLogger(__name__)

_RANK = {'expired': 0, 'soon': 1, 'valid': 2, 'none': 3, 'renewed': 4}


class PbMyTrainingCertificates(models.AbstractModel):
    _inherit = 'pb.my.training'

    # =====================================================================
    #  my certificates
    # =====================================================================
    @api.model
    def _my_cert_docs(self, emp=None):
        emp = emp or self._my_employee()
        if not emp or 'pb.employee.document' not in self.env:
            return self.env['res.partner'].browse()
        docs = self.env['pb.employee.document'].sudo().search([
            ('employee_id', '=', emp.id),
            ('training_source', '!=', False),
        ])
        return docs.sorted(lambda d: (
            _RANK.get(d.training_state, 5),
            d.expiry_date or fields.Date.to_date('9999-12-31'), -d.id))

    @api.model
    def my_certificates(self):
        """Everything the wallet and the My learning block draw, in one read.

        `next` is the certificate that needs the reader first — expired or
        inside its renewal window — with its renewal course when one is open,
        so the page can offer a single "Start renewal".
        """
        emp = self._my_employee()
        blank = {'has_employee': bool(emp), 'rows': [], 'next': None,
                 'live': 0, 'soon': 0, 'expired': 0,
                 'kinds': self._cert_kinds(),
                 'record_url': '/my/training/record.pdf'}
        if not emp:
            return blank
        rows = [d._pb_cert_payload() for d in self._my_cert_docs(emp)]
        urgent = [r for r in rows if r['state'] in ('expired', 'soon')]
        blank.update({
            'rows': rows,
            'next': urgent[0] if urgent else None,
            'live': len([r for r in rows if r['state'] != 'renewed']),
            'soon': len([r for r in rows if r['state'] == 'soon']),
            'expired': len([r for r in rows if r['state'] == 'expired']),
        })
        return blank

    @api.model
    def _cert_kinds(self):
        return [{'key': KIND_CERT, 'label': _("Certificate")},
                {'key': KIND_LIC, 'label': _("Licence or permit")}]

    @api.model
    def certificates_count(self):
        """The number on the portal home card. Cheap, and never raises."""
        try:
            return len(self._my_cert_docs().filtered(
                lambda d: not d.renewed_by_id))
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the certificate count could not be '
                            'read', exc_info=True)
            return 0

    @api.model
    def add_certificate(self, values, upload):
        """An employee adds an outside certificate or licence of their own.

        Filed as `upload`, NOT verified — HR checks it from the register.
        """
        emp = self._my_employee()
        if not emp:
            raise AccessError(_("Only employees can add certificates."))
        doc = self.env['pb.training.certificate']._create_upload(
            emp, values or {}, upload, 'upload')
        return {'id': doc.id}

    # =====================================================================
    #  the certificate on a course tile and a course page (L1 §3.2)
    # =====================================================================
    @api.model
    def _course_certificate(self, channel_id, emp=None):
        emp = emp or self._my_employee()
        if not emp or not channel_id or 'pb.employee.document' not in self.env:
            return None
        doc = self.env['pb.employee.document'].sudo().search([
            ('employee_id', '=', emp.id),
            ('channel_id', '=', as_id(channel_id)),
            ('training_source', '=', 'test'),
            ('renewed_by_id', '=', False),
        ], order='issue_date desc, id desc', limit=1)
        if not doc:
            return None
        return {'id': doc.id, 'valid_words': doc.valid_words or '',
                'expiry_date': fields.Date.to_string(doc.expiry_date) or '',
                'state': doc.training_state}

    def _tile(self, row):
        tile = super()._tile(row)
        try:
            tile['certificate'] = self._course_certificate(row.channel_id.id)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the certificate could not be read '
                            'for course %s', row.channel_id.id, exc_info=True)
            tile['certificate'] = None
        return tile

    @api.model
    def course(self, channel_id):
        data = super().course(channel_id)
        if not data:
            return data
        try:
            data['certificate'] = self._course_certificate(channel_id)
        except Exception:               # noqa: BLE001
            data['certificate'] = None
        return data

    # =====================================================================
    #  the learning record (PDF)
    # =====================================================================
    @api.model
    def record_pdf(self, employee_id=None):
        """`(pdf_bytes, filename)` for the reader's own record — or, for
        somebody in the training team, anybody's in their companies.

        Rendered AS THE SYSTEM over exactly one employee the caller has just
        been proved to be allowed to see.
        """
        mine = self._my_employee()
        wanted = as_id(employee_id)
        if wanted and (not mine or wanted != mine.id):
            if not self.env['pb.training']._can_read():
                raise AccessError(_("You can only print your own learning "
                                    "record."))
            emp = self.env['hr.employee'].sudo().browse(wanted).exists()
            if not emp or emp.company_id.id not in self.env.companies.ids:
                raise AccessError(_("That person is not in your company."))
        else:
            emp = mine
        if not emp:
            raise AccessError(_("Only employees have a learning record."))
        report = self.env['ir.actions.report'].sudo().with_context(
            allowed_company_ids=self.env.companies.ids or [],
            lang=self.env.lang)
        pdf, _kind = report._render_qweb_pdf(
            'pb_training.report_learning_record', [emp.id])
        filename = _("Learning record — %s.pdf", emp.name or '')
        return pdf, filename.replace('/', '-')
