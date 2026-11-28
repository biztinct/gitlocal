# -*- coding: utf-8 -*-
"""Year-end certificates: one PDF per person, released to employees (WDGAP S2-B).

MADE WITH THE FILING. A form with `employee_certificates` makes, when it is
prepared, one PDF per person through the country's hook

    def _pb_certificate_<form code lower>(self, data, person) -> spec dict

(the shape `cert_pdf.build` draws), plus one zip of all of them as an ordinary
file of the filing. The certificates' sha256 are part of the filing's one
stamp (`_pb_hash_parts`), so the approval covers every certificate: what an
employee downloads is what was approved, byte for byte.

RELEASED BY A PAYROLL MANAGER, AFTER APPROVAL. `_pb_release(True)` on an
approved filing (stamp checked again) makes each person's own certificate
visible on My Payobook (`pb_me_tax_cert`); `_pb_release(False)` hides them
again. Both are written in the filing's history and the platform trail.
A filing that is replaced, sent back or turned down shows nothing: the
employee side asks for an APPROVED, RELEASED filing every time.

NO EMPLOYEE RIGHT ON THESE RECORDS. Employees never read this model through
the ORM; the portal route checks that the certificate is the session's own
employee's, then reads under sudo (`_pb_employee_certificates`,
`_pb_portal_download`).
"""
import hashlib
import io
import logging
import zipfile

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from . import cert_pdf
from .filing import _safe_name
from .form import MANAGER_GROUPS, has_any

_logger = logging.getLogger(__name__)


class PbGovFilingCertificate(models.Model):
    _name = 'pb.gov.filing.certificate'
    _description = "A person's year-end certificate"
    _order = 'filing_id, employee_name, id'

    filing_id = fields.Many2one('pb.gov.filing', required=True, index=True,
                                ondelete='cascade')
    company_id = fields.Many2one(related='filing_id.company_id', store=True, index=True)
    form_id = fields.Many2one(related='filing_id.form_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True,
                                  ondelete='cascade')
    employee_name = fields.Char()
    name = fields.Char(required=True)
    title = fields.Char(help="The certificate's title, as printed on it.")
    list_note = fields.Char(help="A short line shown beside the download on My Payobook "
                                 "(e.g. that this is an information copy).")
    period_label = fields.Char()
    attachment_id = fields.Many2one('ir.attachment', required=True, ondelete='restrict')
    sha256 = fields.Char(readonly=True)
    size = fields.Integer(readonly=True)
    download_count = fields.Integer(readonly=True)
    last_download = fields.Datetime(readonly=True)

    def _pb_raw(self):
        self.ensure_one()
        return self.sudo().attachment_id.raw or b''

    def _pb_intact(self):
        self.ensure_one()
        return hashlib.sha256(self._pb_raw()).hexdigest() == self.sha256

    def _pb_visible(self):
        """Approved, released, the stamp still right."""
        self.ensure_one()
        filing = self.sudo().filing_id
        return bool(filing.state == 'approved' and filing.approved_hash
                    and filing.pb_released
                    and not filing._pb_cert_withheld(self.employee_id)
                    and filing._live_hash() == filing.approved_hash)

    @api.model
    def _pb_employee_certificates(self, employee):
        """The person's own certificates an employee may see (sudo, after the
        portal route's own check that `employee` is the session's)."""
        certs = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('filing_id.state', '=', 'approved'),
            ('filing_id.pb_released', '=', True)], order='id desc')
        return certs.filtered(lambda c: c._pb_visible())

    def _pb_portal_download(self, employee):
        """(filename, bytes) for the person themself; refused otherwise.
        Logged on the filing (who, which certificate — no figures)."""
        self.ensure_one()
        cert = self.sudo()
        if cert.employee_id != employee:
            raise AccessError(_("This certificate is not yours."))
        if not cert._pb_visible():
            raise UserError(_("This certificate is not available any more."))
        if not cert._pb_intact():
            raise UserError(_("This certificate is not available any more."))
        cert.write({'download_count': cert.download_count + 1,
                    'last_download': fields.Datetime.now()})
        filing = cert.filing_id
        filing._log(_("%(who)s downloaded their own certificate %(file)s.",
                      who=employee.name or '', file=cert.name))
        filing._audit(_("Year-end certificate downloaded"),
                      _("%(who)s · %(file)s", who=employee.name or '', file=cert.name))
        return cert.name, cert._pb_raw()


class PbGovFilingRelease(models.Model):
    _inherit = 'pb.gov.filing'

    certificate_ids = fields.One2many('pb.gov.filing.certificate', 'filing_id',
                                      readonly=True)
    certificate_count = fields.Integer(compute='_compute_certificate_count')
    pb_released = fields.Boolean(string='Released to employees', readonly=True,
                                 copy=False, index=True)
    pb_released_by = fields.Many2one('res.users', string='Released by', readonly=True,
                                     copy=False)
    pb_released_at = fields.Datetime(string='Released on', readonly=True, copy=False)

    def _compute_certificate_count(self):
        for rec in self:
            rec.certificate_count = len(rec.sudo().certificate_ids)

    # ----------------------------------------------------------- making
    def _pb_after_render(self, data):
        res = super()._pb_after_render(data)
        rec = self.sudo()
        if not rec.form_id.employee_certificates:
            return res
        code = (rec.form_id.code or '').lower()
        hook = getattr(self, '_pb_certificate_%s' % code, None)
        if hook is None:
            return res
        Attachment = self.env['ir.attachment'].sudo()
        Cert = self.env['pb.gov.filing.certificate'].sudo()
        buf = io.BytesIO()
        made = 0
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
            for person in data.get('employees') or []:
                spec = hook(data, person)
                if not spec:
                    continue
                try:
                    payload = cert_pdf.build(spec)
                except ValueError as exc:
                    raise UserError(_("The certificates could not be printed: %s", exc)) from exc
                filename = '%s_%s_%s.pdf' % (
                    spec.get('file_stem') or rec.form_id.code,
                    _safe_name(data.get('period_label') or '')[:20],
                    _safe_name(person.get('name') or str(person['employee_id'])))
                attachment = Attachment.create({
                    'name': filename, 'type': 'binary', 'raw': payload,
                    'res_model': self._name, 'res_id': rec.id,
                    'mimetype': 'application/pdf'})
                Cert.create({
                    'filing_id': rec.id, 'employee_id': person['employee_id'],
                    'employee_name': person.get('name') or '', 'name': filename,
                    'title': spec.get('title') or '',
                    'list_note': spec.get('list_note') or '',
                    'period_label': data.get('period_label') or '',
                    'attachment_id': attachment.id,
                    'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)})
                archive.writestr(filename, payload)
                made += 1
        if made:
            payload = buf.getvalue()
            name = self._pb_filename(data, 'certificates', 'zip')
            attachment = Attachment.create({
                'name': name, 'type': 'binary', 'raw': payload,
                'res_model': self._name, 'res_id': rec.id, 'mimetype': 'application/zip'})
            self.env['pb.gov.filing.file'].sudo().create({
                'filing_id': rec.id, 'sequence': 900, 'name': name,
                'mimetype': 'application/zip', 'attachment_id': attachment.id,
                'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)})
        return res

    def _pb_cert_withheld(self, employee):
        """Hook: True when this filing's certificate must not be shown to
        `employee` any more (Vietnam: "Asked us to settle year-end tax",
        owner ruling YE1). Checked every time an employee asks."""
        return False

    def _pb_hash_parts(self):
        parts = super()._pb_hash_parts()
        if parts is None:
            return None
        for cert in self.sudo().certificate_ids.sorted('id'):
            raw = cert.attachment_id.raw if cert.attachment_id else None
            if raw is None:
                return None
            parts.append(hashlib.sha256(raw).hexdigest())
        return parts

    # ----------------------------------------------------------- release
    def _pb_release(self, value):
        """Payroll manager only; approved filings only (the stamp is checked
        again); undo allowed. Who and when are kept; both directions are
        written in the history and the trail."""
        self.ensure_one()
        if not has_any(self.env.user, MANAGER_GROUPS):
            raise AccessError(_("Only a payroll manager can release certificates to employees."))
        rec = self.sudo()
        value = bool(value)
        if not rec.certificate_ids:
            raise UserError(_("This filing has no certificates for employees."))
        if value:
            if rec.state != 'approved' or not rec.approved_hash:
                raise UserError(_("The filing must be approved before its certificates can be released."))
            if rec._live_hash() != rec.approved_hash:
                raise UserError(_("This is not the approved filing — what is stored no longer matches what was signed off. Prepare it again."))
        if value == bool(rec.pb_released):
            return True
        if value:
            rec.write({'pb_released': True, 'pb_released_by': self.env.uid,
                       'pb_released_at': fields.Datetime.now()})
            body = _("%(who)s released %(n)s certificates to employees on My Payobook.",
                     who=self.env.user.name, n=len(rec.certificate_ids))
            label = _("Year-end certificates released")
        else:
            rec.write({'pb_released': False, 'pb_released_by': False,
                       'pb_released_at': False})
            body = _("%(who)s took the certificates back from My Payobook.",
                     who=self.env.user.name)
            label = _("Year-end certificates taken back")
        rec._log(body)
        rec._audit(label, '%s · %s' % (self.env.user.name, rec.name or ''))
        return True

    # ------------------------------------------------- shared certificate parts
    @api.model
    def _pb_cert_amount(self, value, currency=None, kind='money'):
        if kind == 'count':
            return str(int(value or 0))
        if isinstance(value, str):
            return value
        number = float(value or 0.0)
        digits = currency.decimal_places if currency else 2
        return ('{:,.%df}' % max(digits, 0)).format(number)

    def _pb_cert_lines(self, person, codes=None, totals=()):
        """Table rows (code, label, amount, kind) for a person's lines in the
        form's order; `codes` limits them, `totals` are drawn bold."""
        self.ensure_one()
        rec = self.sudo()
        currency = rec.currency_id or rec.company_id.currency_id
        values = person.get('lines') or {}
        rows = []
        for line in rec.form_id._pb_ordered_lines():
            if codes is not None and line.code not in codes:
                continue
            if line.kind == 'text' or line.scope != 'employee':
                continue
            value = values.get(line.code, 0.0)
            rows.append((line.code, cert_pdf.row_label(line.label, line.official_label),
                         self._pb_cert_amount(value, currency, line.kind),
                         'total' if line.code in totals else ''))
        return rows

    def _pb_cert_base(self, data, person, title, official=''):
        """The parts every country's certificate has: title, the adviser
        mark (G3), the employer block, the footer."""
        self.ensure_one()
        rec = self.sudo()
        settings = data.get('settings') or {}
        employer = [(_("Name"), data.get('company_name') or '')]
        if settings.get('employer_tax_id'):
            employer.append((_("Tax number"), settings['employer_tax_id']))
        employer.append((_("Tax year"), data.get('period_label') or ''))
        return {
            'title': title,
            'official': official or rec.form_id.official_name or '',
            'subtitle': _("%(name)s · tax year %(year)s",
                          name=person.get('name') or '', year=data.get('period_label') or ''),
            'author': data.get('company_name') or '',
            'mark': data.get('adviser_text') if data.get('adviser_mark') else '',
            'blocks': [{'title': _("Employer"), 'rows': employer}],
            'tables': [],
            'notes': [_("Figures read from the finished payslips of this tax year. Nothing was worked out again.")],
            'footer': _("%(company)s · %(form)s · %(year)s",
                        company=data.get('company_name') or '', form=rec.form_id.name or '',
                        year=data.get('period_label') or ''),
        }
