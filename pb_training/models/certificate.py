# -*- coding: utf-8 -*-
"""Certificates, filed where the employee's other documents already live.

A CERTIFICATE THAT LIVES ONLY IN THE TEST ENGINE IS A CERTIFICATE NOBODY CAN
FIND. It is reachable from one page, it is regenerated on every download, and
the day the course is archived it is gone. The vault (`pb.employee.document`)
is where this product already keeps a person's papers — their contract, their
ID, their work permit — and a training certificate is one of those. So when
somebody passes a test, the PDF is rendered once and filed under the "Degree /
Certificate" category on their own record, and when an outside course is
claimed the certificate they uploaded is filed beside it.

FILED AS THE SYSTEM, AND THAT IS THE ONLY WAY IT CAN BE DONE. The vault gates
a self-served create on an attachment the CALLER owns and that no record has
claimed (`employee_document.py:114-135`) — a rail that exists so probing a
stranger's attachment id cannot get their file deleted later. Neither filing
here is self-served: one is the system noticing a pass, the other is the HR
lead agreeing a claim somebody else uploaded a file to. Both run as the system
over an employee the caller has already been proved to be acting for.

IDEMPOTENT, PER (EMPLOYEE, COURSE) AND PER CLAIM. Finishing a course twice —
which a yearly compliance course IS — must not leave two identical documents
on somebody's record, and an approval that ran twice must not file two copies
of one certificate. The search that proves it is by `name`, because that is the
only thing a vault document carries that could identify what it is about; the
name is built in ONE place below so the write and the search can never drift.

NEVER `report.sudo()._render_qweb_pdf` ON A FACADE (R89). The certification
report reads exactly one `survey.user_input` — the attempt being filed — and
nothing inside it calls a company-scoped reader, so rendering it as the system
leaks nothing. The company set is pinned anyway, because the rule is cheap to
keep and the day somebody adds a header that reads a facade is the day it
matters.
"""

import logging

from odoo import _, api, fields, models

from .training_common import as_id, leg

_logger = logging.getLogger(__name__)

#: The vault category a certificate goes in, by CODE. The code is the stable
#: identifier — the name is translated per language, so matching on it would
#: work in English and file into a new category in Vietnamese.
VAULT_CATEGORY_CODE = 'CERT'

#: The engine's own certification report. Read off the route that serves it
#: (`survey/controllers/main.py:766`) rather than guessed.
CERT_REPORT = 'survey.certification_report'


class PbTrainingCertificate(models.AbstractModel):
    """The filing clerk. An AbstractModel because it owns no rows."""
    _name = 'pb.training.certificate'
    _description = 'Payobook Training — certificates in the vault'

    # =====================================================================
    #  where it goes
    # =====================================================================
    @api.model
    def _category(self):
        """The "Degree / Certificate" category, or nothing.

        A vault with no such category is not a fault to shout about — the
        module is optional on a tenant — so the answer is empty and the caller
        logs it.
        """
        if 'pb.employee.document.category' not in self.env:
            return None
        return self.env['pb.employee.document.category'].sudo().search(
            [('code', '=', VAULT_CATEGORY_CODE)], limit=1)

    @api.model
    def _document_name(self, course_name, provider=None):
        """THE NAME, BUILT IN ONE PLACE, because it is also the key.

        The write and the "have we filed this already" search both come here,
        so an idempotency check can never be looking for a name nothing writes.
        """
        base = _("%s — certificate", (course_name or _('Course')).strip())
        if provider:
            return '%s (%s)' % (base, provider.strip())
        return base

    @api.model
    def _already(self, employee, name):
        if 'pb.employee.document' not in self.env:
            return None
        return self.env['pb.employee.document'].sudo().with_context(
            active_test=False).search([
                ('employee_id', '=', as_id(employee)),
                ('name', '=', name),
            ], limit=1)

    @api.model
    def _file(self, employee, name, attachment, note=''):
        """One document in the vault, or the one that is already there."""
        if 'pb.employee.document' not in self.env:
            _logger.info('pb_training: there is no document vault on this '
                         'database, so nothing was filed')
            return None
        category = self._category()
        if not category:
            _logger.warning('pb_training: the vault has no "%s" category, so '
                            '"%s" could not be filed', VAULT_CATEGORY_CODE,
                            name)
            return None
        emp = self.env['hr.employee'].sudo().browse(as_id(employee)).exists()
        if not emp or not attachment:
            return None
        existing = self._already(emp, name)
        if existing:
            return existing
        return self.env['pb.employee.document'].sudo().create({
            'employee_id': emp.id,
            'category_id': category.id,
            'name': name,
            'attachment_id': attachment.id,
            'issue_date': fields.Date.today(),
            # EMPTY ON PURPOSE. The category does not require one and a
            # training certificate does not run out; a date invented here
            # would put a real person on a real expiry report.
            'expiry_date': False,
            'note': note or '',
        })

    # =====================================================================
    #  a test that was passed
    # =====================================================================
    @api.model
    def file_course_certificate(self, channel, partner):
        """Render the passed attempt's certificate and file it. Idempotent."""
        channel = self.env['slide.channel'].sudo().browse(
            as_id(channel)).exists()
        partner = self.env['res.partner'].sudo().browse(
            as_id(partner)).exists()
        if not channel or not partner:
            return None
        emp = self.env['hr.employee'].sudo().search(
            [('user_id.partner_id', '=', partner.id)], limit=1)
        if not emp:
            _logger.info('pb_training: %s passed %s but has no employee '
                         'record, so there is no vault to file it in',
                         partner.name, channel.name)
            return None
        test_slide = channel._pb_test_slide()
        if not test_slide or not test_slide.survey_id:
            return None
        survey = test_slide.survey_id.sudo()
        if not survey.certification:
            return None
        name = self._document_name(channel.name)
        existing = self._already(emp, name)
        if existing:
            return existing
        attempt = self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', survey.id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'done'),
            ('test_entry', '=', False),
            ('scoring_success', '=', True),
        ], order='create_date desc, id desc', limit=1)
        if not attempt:
            return None
        pdf = self._render(attempt)
        if not pdf:
            return None
        attachment = self.env['ir.attachment'].sudo().create({
            'name': '%s.pdf' % name,
            'raw': pdf,
            'mimetype': 'application/pdf',
            'res_model': 'hr.employee',
            'res_id': emp.id,
        })
        document = self._file(
            emp, name, attachment,
            note=_("Passed on %(when)s with %(score)s%%.",
                   when=fields.Date.to_string(
                       fields.Date.to_date(attempt.create_date)) or '',
                   score=int(round(attempt.scoring_percentage or 0))))
        if document:
            _logger.info('pb_training: the certificate for "%s" was filed on '
                         '%s (document %s)', channel.name, emp.name,
                         document.id)
        return document

    @api.model
    def _render(self, attempt):
        """The engine's own certificate, as bytes. Never fatal."""
        try:
            report = self.env['ir.actions.report'].sudo().with_context(
                allowed_company_ids=self.env.companies.ids or [])
            pdf, _kind = report._render_qweb_pdf(
                CERT_REPORT, [attempt.id], data={'report_type': 'pdf'})
            return pdf
        except Exception:                   # noqa: BLE001 — filing is not fatal
            _logger.warning('pb_training: the certificate for attempt %s could '
                            'not be rendered', attempt.id, exc_info=True)
            return None

    # =====================================================================
    #  a certificate somebody uploaded with a claim
    # =====================================================================
    @api.model
    def file_claim_certificate(self, claim):
        """The uploaded certificate for an outside course. Idempotent."""
        claim = self.env['pb.training.claim'].sudo().browse(
            as_id(claim)).exists()
        if not claim or not claim.certificate_attachment_id:
            return None
        name = self._document_name(claim.course_name, claim.provider)
        existing = self._already(claim.employee_id, name)
        if existing:
            return existing
        # A COPY AND NOT THE CLAIM'S OWN ATTACHMENT. The vault OWNS its
        # attachment and deletes it when the document goes
        # (`employee_document.unlink`), so handing it the claim's file would
        # make deleting a vault document silently empty the claim it came
        # from.
        source = claim.certificate_attachment_id.sudo()
        attachment = self.env['ir.attachment'].sudo().create({
            'name': source.name or ('%s.pdf' % name),
            'raw': source.raw,
            'mimetype': source.mimetype,
            'res_model': 'hr.employee',
            'res_id': claim.employee_id.id,
        })
        document = self._file(
            claim.employee_id, name, attachment,
            note=_("From a training claim agreed on %s.",
                   fields.Date.to_string(fields.Date.today())))
        if document:
            _logger.info('pb_training: the certificate from claim %s was filed '
                         'on %s (document %s)', claim.id,
                         claim.employee_id.sudo().name, document.id)
        return document


class SurveyUserInputCertificate(models.Model):
    """Passing the test files the certificate, whether or not it was assigned.

    THE ASSIGNMENT IS NOT THE TRIGGER, and it must not be. Plenty of people are
    simply put on a course (E1's own door does exactly that) with no assignment
    behind it, and their certificate is as real as anybody's — hooking only the
    assignment would file a document for the people who were chased and not for
    the people who volunteered.
    """
    _inherit = 'survey.user_input'

    def _mark_done(self):
        result = super()._mark_done()
        for answer in self:
            if not answer.scoring_success or answer.test_entry:
                continue
            slide = answer.slide_id
            if not slide or not slide.channel_id or not answer.partner_id:
                continue
            leg(self.env, 'file the certificate',
                lambda a=answer: self.env['pb.training.certificate']
                .file_course_certificate(a.slide_id.channel_id, a.partner_id))
        return result


class PbTrainingAssignmentCertificate(models.Model):
    """Finishing a course files its certificate, the moment it is finished."""
    _inherit = 'pb.training.assignment'

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        # ONLY ON THE CROSSING, never on every read: this method is called by
        # every board read and by the nightly job, and a filing clerk asked
        # four hundred times a minute whether a document already exists is a
        # filing clerk nobody can afford.
        if state == 'done' and was != 'done':
            leg(self.env, 'file the certificate', self._file_certificate)
        return state

    def _file_certificate(self):
        self.ensure_one()
        if not self.partner_id:
            return None
        return self.env['pb.training.certificate'].file_course_certificate(
            self.channel_id, self.partner_id)
