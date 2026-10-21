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

IDEMPOTENT PER ATTEMPT AND PER CLAIM (LEARNING L1). Until L1 the "have we
filed this already" search was by `name` alone, and the name was the course's —
so a yearly compliance course passed again a year later filed NOTHING: the
first year's certificate blocked every renewal for ever. Now a test
certificate is keyed on the passed ATTEMPT and a claim certificate on the
CLAIM; the name carries the year for rows filed from now on; and a renewal
files a NEW document and marks the older one renewed. Name-only de-dup stays
for anything else (and as the fallback for rows filed before L1, which carry
no attempt link).

NEVER `report.sudo()._render_qweb_pdf` ON A FACADE (R89). The certification
report reads exactly one `survey.user_input` — the attempt being filed — and
nothing inside it calls a company-scoped reader, so rendering it as the system
leaks nothing. The company set is pinned anyway, because the rule is cheap to
keep and the day somebody adds a header that reads a facade is the day it
matters.
"""

import logging
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mimetypes import guess_mimetype

from .document_ext import KIND_CERT, KIND_LIC
from .training_common import as_id, leg

#: The vault portal's own limits (`pb_me_portal/controllers/portal.py:41-42`).
UPLOAD_MIME_OK = ('image/png', 'image/jpeg', 'application/pdf')
UPLOAD_MAX_BYTES = 10 * 1024 * 1024

_logger = logging.getLogger(__name__)

#: The vault category a certificate goes in, by CODE. The code is the stable
#: identifier — the name is translated per language, so matching on it would
#: work in English and file into a new category in Vietnamese.
VAULT_CATEGORY_CODE = 'CERT'

#: The engine's own certification report. Read off the route that serves it
#: (`survey/controllers/main.py:766`) rather than guessed.
CERT_REPORT = 'survey.certification_report'

#: "<course> — certificate" or "<course> — certificate (<provider or year>)",
#: the shape `_document_name` writes. Rows filed before L1 never carry a year,
#: so a bracket on one of THEM is always a claim's provider.
_PATTERN_SUFFIX = '— certificate'
_NAME_RE = re.compile(r'^(?P<course>.*) — certificate(?: \((?P<paren>.+)\))?$')


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
    def _document_name(self, course_name, provider=None, year=None):
        """THE NAME, BUILT IN ONE PLACE.

        A test certificate filed from LEARNING L1 on carries its year —
        "Fire safety — certificate (2026)" — so this year's and last year's
        sit side by side on somebody's record and can be told apart. Rows
        filed before L1 keep the name they were filed with.
        """
        base = _("%s — certificate", (course_name or _('Course')).strip())
        if provider:
            return '%s (%s)' % (base, provider.strip())
        if year:
            return '%s (%s)' % (base, year)
        return base

    @api.model
    def _already(self, employee, name=None, attempt=None, claim=None):
        """The document this filing would duplicate, or nothing.

        BY ATTEMPT for a test and BY CLAIM for a claim (L1): the same pass or
        the same claim never files twice, and a NEW pass of the same test —
        a renewal — files a new document. By name for anything else.
        """
        if 'pb.employee.document' not in self.env:
            return None
        Doc = self.env['pb.employee.document'].sudo().with_context(
            active_test=False)
        emp_id = as_id(employee)
        if attempt:
            return Doc.search([('employee_id', '=', emp_id),
                               ('attempt_id', '=', as_id(attempt))], limit=1)
        if claim:
            return Doc.search([('employee_id', '=', emp_id),
                               ('claim_id', '=', as_id(claim))], limit=1)
        return Doc.search([('employee_id', '=', emp_id),
                           ('name', '=', name)], limit=1)

    @api.model
    def _legacy(self, employee, name, since=None):
        """A row filed BEFORE L1 under the old name with no link, filed on
        or after `since` — i.e. the very filing we are about to repeat.

        Rows from before L1 carry no attempt or claim link (unless the L1
        migration could find it), so the new keyed search alone would file
        a second copy of a certificate that is already on somebody's record
        the next time the same pass is noticed.
        """
        if 'pb.employee.document' not in self.env:
            return None
        domain = [('employee_id', '=', as_id(employee)),
                  ('name', '=', name),
                  ('attempt_id', '=', False),
                  ('claim_id', '=', False)]
        if since:
            domain.append(('issue_date', '>=', since))
        return self.env['pb.employee.document'].sudo().with_context(
            active_test=False).search(domain, limit=1)

    @api.model
    def _file(self, employee, name, attachment, note='', extra=None):
        """One document in the vault, or the one that is already there.

        `extra` carries the L1 training facts (`training_source`,
        `channel_id`, `survey_id`, `attempt_id`, `claim_id`, `issuer`,
        `issue_date`, `expiry_date`). The keyed duplicate check is the
        CALLER's — this only guards a plain name clash when no key is given.
        """
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
        extra = dict(extra or {})
        if not (extra.get('attempt_id') or extra.get('claim_id')):
            existing = self._already(emp, name)
            if existing:
                return existing
        vals = {
            'employee_id': emp.id,
            'category_id': category.id,
            'name': name,
            'attachment_id': attachment.id,
            'issue_date': fields.Date.today(),
            # EMPTY UNLESS THE TEST SAYS OTHERWISE (L1). A valid-until date
            # comes only from the test's own validity months; a date
            # invented here would put a real person on a real expiry report.
            'expiry_date': False,
            'note': note or '',
            'company_id': (emp.company_id or self.env.company).id,
        }
        vals.update(extra)
        return self.env['pb.employee.document'].sudo().create(vals)

    @api.model
    def _validity_months(self, survey):
        """The test's own validity (hr_skills_survey), 0 when it never runs
        out — or when the field is not on this database."""
        try:
            return max(int(survey.sudo().certification_validity_months or 0), 0)
        except (AttributeError, TypeError, ValueError):
            return 0

    @api.model
    def _mark_renewed(self, document):
        """A new pass of a test: every older, unrenewed certificate of the
        same test on the same person is renewed BY the new one."""
        if not document or not document.survey_id:
            return 0
        older = self.env['pb.employee.document'].sudo().with_context(
            active_test=False).search([
                ('employee_id', '=', document.employee_id.id),
                ('survey_id', '=', document.survey_id.id),
                ('training_source', '=', 'test'),
                ('renewed_by_id', '=', False),
                ('id', '!=', document.id),
            ])
        # Only what came BEFORE the new one: an older pass filed late must
        # never mark a newer certificate renewed.
        older = older.filtered(
            lambda d: (d.issue_date or fields.Date.today())
            <= (document.issue_date or fields.Date.today()))
        if older:
            older.write({'renewed_by_id': document.id})
        return len(older)

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
        attempt = self.env['survey.user_input'].sudo().search([
            ('survey_id', '=', survey.id),
            ('partner_id', '=', partner.id),
            ('state', '=', 'done'),
            ('test_entry', '=', False),
            ('scoring_success', '=', True),
        ], order='create_date desc, id desc', limit=1)
        if not attempt:
            return None
        existing = self._already(emp, attempt=attempt)
        if existing:
            return existing
        issued = fields.Date.to_date(attempt.end_datetime) \
            if attempt.end_datetime else fields.Date.today()
        # The same pass, filed before L1 under the old name: link it and
        # stop, rather than filing a second copy of it.
        legacy = self._legacy(emp, self._document_name(channel.name),
                              since=fields.Date.to_date(attempt.create_date))
        if legacy:
            legacy.write({'training_source': 'test',
                          'channel_id': channel.id, 'survey_id': survey.id,
                          'attempt_id': attempt.id})
            return legacy
        months = self._validity_months(survey)
        name = self._document_name(channel.name, year=issued.year)
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
                   when=fields.Date.to_string(issued) or '',
                   score=int(round(attempt.scoring_percentage or 0))),
            extra={
                'training_source': 'test',
                'channel_id': channel.id,
                'survey_id': survey.id,
                'attempt_id': attempt.id,
                'issuer': (emp.company_id or self.env.company).name or '',
                'issue_date': issued,
                'expiry_date': issued + relativedelta(months=months)
                if months else False,
            })
        if document:
            renewed = self._mark_renewed(document)
            _logger.info('pb_training: the certificate for "%s" was filed on '
                         '%s (document %s%s)', channel.name, emp.name,
                         document.id,
                         ', renewing %s older' % renewed if renewed else '')
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
    #  LEARNING L1 — a certificate somebody uploads (employee or HR)
    # =====================================================================
    @api.model
    def _licence_category(self):
        cat = self.env.ref('pb_training.cat_licence',
                           raise_if_not_found=False)
        if cat:
            return cat.sudo()
        return self.env['pb.employee.document.category'].sudo().search(
            [('code', '=', 'LIC')], limit=1)

    @api.model
    def _date(self, value):
        if not value:
            return False
        try:
            return fields.Date.to_date(value)
        except (TypeError, ValueError):
            raise UserError(_("That date is not a date. Pick it from the "
                              "calendar."))

    @api.model
    def _create_upload(self, employee, values, upload, source='upload'):
        """ONE door for both uploads — the employee's own page and HR's
        drawer. The caller has proved who may file for this person; this
        checks the paper itself and files it AS THE SYSTEM (the vault's
        create guard, F2: the attachment is made here, by us, so it is never
        somebody else's file being claimed).

        `values` = {name, kind 'CERT'|'LIC', issuer, reference, issue_date,
        expiry_date, note}; `upload` = (filename, bytes).
        """
        values = values or {}
        name = (values.get('name') or '').strip()[:200]
        if not name:
            raise UserError(_("Give the certificate a name — what it says on "
                              "it."))
        kind = values.get('kind') or KIND_CERT
        category = self._licence_category() if kind == KIND_LIC \
            else self._category()
        if not category:
            raise UserError(_("Certificates cannot be filed on this system "
                              "yet. Tell your HR team."))
        issued = self._date(values.get('issue_date'))
        expiry = self._date(values.get('expiry_date'))
        if issued and expiry and expiry < issued:
            raise UserError(_("The valid-until date is before the issued-on "
                              "date."))
        if category.requires_expiry and not expiry:
            raise UserError(_("A licence needs a valid-until date."))
        if not upload or not upload[1]:
            raise UserError(_("Attach the certificate — a PDF, JPG or PNG."))
        filename, content = upload
        if len(content) > UPLOAD_MAX_BYTES:
            raise UserError(_("The file is bigger than 10 MB."))
        mimetype = guess_mimetype(content) or ''
        if mimetype not in UPLOAD_MIME_OK:
            raise UserError(_("Only PDF, JPG or PNG files."))
        emp = self.env['hr.employee'].sudo().browse(as_id(employee)).exists()
        if not emp:
            raise UserError(_("Pick the person the certificate belongs to."))
        attachment = self.env['ir.attachment'].sudo().create({
            'name': (filename or name)[:200],
            'raw': content,
            'mimetype': mimetype,
            'res_model': 'hr.employee',
            'res_id': emp.id,
        })
        return self.env['pb.employee.document'].sudo().create({
            'employee_id': emp.id,
            'category_id': category.id,
            'name': name,
            'attachment_id': attachment.id,
            'issue_date': issued or fields.Date.today(),
            'expiry_date': expiry,
            'note': (values.get('note') or '')[:2000],
            'training_source': source,
            'issuer': (values.get('issuer') or '').strip()[:200],
            'reference': (values.get('reference') or '').strip()[:100],
            'company_id': (emp.company_id or self.env.company).id,
        })

    # =====================================================================
    #  LEARNING L1 — the rows filed before L1, brought onto the register
    # =====================================================================
    @api.model
    def _backfill(self):
        """Give the certificates filed before L1 their training facts.

        Run by the 19.0.1.5.0 migration and safe to run again (the demo seed
        does, after setting a test's validity). It touches only "— certificate"
        rows in the CERT category:

          * rows with no `training_source`: "(provider)" at the end means it
            came from a claim, otherwise from a passed test; a test row is
            linked to its course, test and the passed attempt it was filed
            for, a claim row to its claim, when they can be found;
          * test rows with no valid-until date whose test now has validity
            months get `issue_date + months`. A test with no validity never
            gets a date (safety rail: no invented expiry).

        Returns the counts it logs.
        """
        counts = {'test': 0, 'claim': 0, 'linked': 0, 'stamped': 0}
        if 'pb.employee.document' not in self.env:
            return counts
        category = self._category()
        if not category:
            return counts
        Doc = self.env['pb.employee.document'].sudo().with_context(
            active_test=False)
        suffix = _PATTERN_SUFFIX
        rows = Doc.search([('category_id', '=', category.id),
                           ('training_source', '=', False),
                           ('name', 'like', suffix)])
        for doc in rows:
            match = _NAME_RE.match(doc.name or '')
            if not match:
                continue
            course, paren = match.group('course'), match.group('paren')
            try:
                with self.env.cr.savepoint():
                    if paren:
                        self._backfill_claim(doc, course, paren, counts)
                    else:
                        self._backfill_test(doc, course, counts)
            except Exception:               # noqa: BLE001 — one row, one grave
                _logger.warning('pb_training: certificate %s could not be '
                                'brought onto the register', doc.id,
                                exc_info=True)
        for doc in Doc.search([('training_source', '=', 'test'),
                               ('expiry_date', '=', False),
                               ('survey_id', '!=', False)]):
            months = self._validity_months(doc.survey_id)
            if months and doc.issue_date:
                doc.write({'expiry_date':
                           doc.issue_date + relativedelta(months=months)})
                counts['stamped'] += 1
        _logger.info('pb_training: certificates brought onto the register — '
                     '%(test)s from a test, %(claim)s from a claim, '
                     '%(linked)s linked to their attempt or claim, '
                     '%(stamped)s given a valid-until date', counts)
        return counts

    def _backfill_test(self, doc, course, counts):
        vals = {'training_source': 'test'}
        emp = doc.employee_id.sudo()
        vals['issuer'] = (emp.company_id or self.env.company).name or ''
        channel = self.env['slide.channel'].sudo().with_context(
            active_test=False).search([('name', '=', course)], limit=1)
        if channel:
            vals['channel_id'] = channel.id
            test_slide = channel._pb_test_slide()
            survey = test_slide.survey_id.sudo() if test_slide else None
            if survey:
                vals['survey_id'] = survey.id
                partner = emp.user_id.partner_id
                if partner:
                    attempts = self.env['survey.user_input'].sudo().search([
                        ('survey_id', '=', survey.id),
                        ('partner_id', '=', partner.id),
                        ('state', '=', 'done'),
                        ('test_entry', '=', False),
                        ('scoring_success', '=', True),
                    ], order='create_date desc, id desc')
                    # The pass this row was filed for: the latest one made
                    # on or before the day it was filed.
                    when = doc.issue_date
                    attempt = attempts.filtered(
                        lambda a: not when or
                        fields.Date.to_date(a.create_date) <= when)[:1] \
                        or attempts[:1]
                    taken = attempt and self.env['pb.employee.document'] \
                        .sudo().with_context(active_test=False).search_count(
                            [('attempt_id', '=', attempt.id)])
                    if attempt and not taken:
                        vals['attempt_id'] = attempt.id
                        counts['linked'] += 1
        doc.write(vals)
        counts['test'] += 1

    def _backfill_claim(self, doc, course, provider, counts):
        vals = {'training_source': 'claim', 'issuer': provider.strip()}
        if 'pb.training.claim' in self.env:
            claim = self.env['pb.training.claim'].sudo().search([
                ('employee_id', '=', doc.employee_id.id),
                ('course_name', '=', course),
                ('provider', '=', provider),
            ], order='id desc', limit=1)
            taken = claim and self.env['pb.employee.document'].sudo() \
                .with_context(active_test=False).search_count(
                    [('claim_id', '=', claim.id)])
            if claim and not taken:
                vals['claim_id'] = claim.id
                counts['linked'] += 1
        doc.write(vals)
        counts['claim'] += 1

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
        existing = self._already(claim.employee_id, claim=claim) \
            or self._legacy(claim.employee_id, name)
        if existing:
            if not existing.claim_id:
                existing.write({'training_source': 'claim',
                                'claim_id': claim.id})
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
                   fields.Date.to_string(fields.Date.today())),
            extra={
                'training_source': 'claim',
                'claim_id': claim.id,
                'issuer': (claim.provider or '').strip(),
            })
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
