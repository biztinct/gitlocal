"""Tenant-scoped application forms with server-side validation and attribution."""
import base64
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from markupsafe import Markup
from odoo import _, fields, http
from odoo.http import request
from odoo.tools import email_normalize
from odoo.exceptions import UserError
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
from ..models.journey import AUTHORIZATION, RELOCATION, text_html
from ..models.hiring_common import flag, P_CANDIDATE_MAIL


def clean_url(value):
    try:
        parts = urlsplit(value or '')
        if parts.scheme not in ('https', 'http'):
            return ''
        # Do not retain arbitrary URL tokens or fragments in candidate records.
        query = urlencode([(k, v[:200]) for k, v in parse_qsl(parts.query) if k.startswith('utm_')])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))[:2000]
    except ValueError:
        return ''


class HiringApplications(WebsiteHrRecruitment):
    def _pb_hiring_public_job(self, job):
        # The rule lives on hr.job so the careers page can ask it too.
        job = job.sudo().exists()
        return job if job.pb_hiring_accepts_applications(request.website) else None

    def _pb_hiring_touch(self, kwargs):
        touch = {key: str(kwargs.get('utm_' + key) or '')[:200] for key in ('source', 'medium', 'campaign', 'term', 'content')}
        touch.update({'referrer': clean_url(request.httprequest.referrer),
                      'landing_url': clean_url(request.httprequest.url),
                      'at': fields.Datetime.to_string(fields.Datetime.now())})
        stored = request.session.get('pb_hiring_attribution') or {}
        if not stored:
            stored['first'] = touch
        if any(touch[k] for k in ('source', 'medium', 'campaign')) or not stored.get('latest'):
            stored['latest'] = touch
        request.session['pb_hiring_attribution'] = stored
        return stored

    @http.route()
    def jobs(self, **kwargs):
        self._pb_hiring_touch(kwargs)
        return super().jobs(**kwargs)

    @http.route()
    def job(self, job, **kwargs):
        self._pb_hiring_touch(kwargs)
        return super().job(job, **kwargs)

    @http.route()
    def jobs_apply(self, job, **kwargs):
        job = self._pb_hiring_public_job(job)
        if not job:
            return request.not_found()
        self._pb_hiring_touch(kwargs)
        request.session['pb_application_opened'] = time.time()
        return self._pb_hiring_render(job)

    def _pb_hiring_render(self, job, values=None, error=None, done=False):
        requisition = request.env['pb.hiring.requisition'].sudo().search([('job_id', '=', job.id)], order='id desc', limit=1)
        return request.render('pb_hiring.application_journey', {
            'job': job, 'brand': job.company_id._hiring_brand(), 'values': values or {},
            'role_country': requisition.country_id.name or job.address_id.country_id.name or job.company_id.country_id.name or 'the role’s country',
            'role_location': requisition.location or job.address_id.city or 'the role’s location',
            'error': error, 'done': done, 'authorizations': AUTHORIZATION, 'relocations': RELOCATION,
        })

    @http.route('/hiring/apply/<int:job_id>', type='http', auth='public', website=True, methods=['POST'])
    def pb_hiring_apply_submit(self, job_id, **post):
        job = self._pb_hiring_public_job(request.env['hr.job'].browse(job_id))
        if not job:
            return request.not_found()
        values = {key: str(post.get(key) or '').strip()[:12000] for key in
                  ('name', 'email', 'phone', 'location', 'linkedin', 'portfolio', 'authorization', 'relocation', 'motivation')}
        try:
            if post.get('company_website') or not request.session.get('pb_application_opened'):
                raise UserError(_('Please open the application form and try again.'))
            if time.time() - request.session.get('pb_application_last', 0) < 30:
                raise UserError(_('Your application is being processed. Please wait before trying again.'))
            if not all(values[k] for k in ('name', 'email', 'phone', 'location', 'linkedin')):
                raise UserError(_('Complete your name, email, phone, location and LinkedIn profile.'))
            if not email_normalize(values['email']):
                raise UserError(_('Enter a valid email address.'))
            for key in ('linkedin', 'portfolio'):
                if values[key] and not clean_url(values[key]):
                    raise UserError(_('Use a full https:// URL for your profile or portfolio.'))
            if values['authorization'] not in dict(AUTHORIZATION) or values['relocation'] not in dict(RELOCATION):
                raise UserError(_('Answer the work authorization and relocation questions.'))
            words = len(values['motivation'].split())
            if not 150 <= words <= 250:
                raise UserError(_('Tell us why you would like to join in 150–250 words. You have %s words.', words))
            upload = post.get('cv')
            if not upload or not getattr(upload, 'filename', ''):
                raise UserError(_('Attach your updated resume as a PDF or Word document.'))
            data = upload.read(5 * 1024 * 1024 + 1)
            suffix = upload.filename.lower().rsplit('.', 1)[-1]
            if len(data) > 5 * 1024 * 1024 or suffix not in ('pdf', 'doc', 'docx'):
                raise UserError(_('Attach a PDF or Word document smaller than 5 MB.'))
            if (suffix == 'pdf' and not data.startswith(b'%PDF')) or (suffix == 'docx' and not data.startswith(b'PK')) or (suffix == 'doc' and not data.startswith(b'\xd0\xcf\x11\xe0')):
                raise UserError(_('The uploaded file does not match its document type.'))
            req = request.env['pb.hiring.requisition'].sudo().search([('job_id', '=', job.id), ('state', '=', 'open')], limit=1)
            attribution = request.session.get('pb_hiring_attribution') or {}
            vals = {'partner_name': values['name'], 'email_from': values['email'], 'partner_phone': values['phone'],
                    'job_id': job.id, 'company_id': job.company_id.id, 'department_id': job.department_id.id,
                    'user_id': job.user_id.id, 'pb_requisition_id': req.id,
                    'pb_location': values['location'], 'pb_linkedin': values['linkedin'], 'pb_portfolio': values['portfolio'],
                    'pb_work_authorization': values['authorization'], 'pb_relocation': values['relocation'],
                    'pb_motivation': values['motivation'], 'pb_first_touch': attribution.get('first', {}),
                    'pb_application_touch': attribution.get('latest', {})}
            for key in ('source', 'medium', 'campaign'):
                name = attribution.get('latest', {}).get(key)
                if name:
                    model = request.env['utm.' + key].sudo()
                    rec = model.search([('name', '=', name)], limit=1) or model.create({'name': name})
                    vals[key + '_id'] = rec.id
            with request.env.cr.savepoint():
                applicant = request.env['hr.applicant'].sudo().create(vals)
                request.env['ir.attachment'].sudo().create({'name': upload.filename[:200], 'datas': base64.b64encode(data),
                    'res_model': 'hr.applicant', 'res_id': applicant.id, 'public': False})
                template = request.env['pb.hiring.message.template'].sudo().search([
                    ('company_id', '=', job.company_id.id), ('key', '=', 'received')], limit=1)
                if template and flag(request.env, P_CANDIDATE_MAIL):
                    rendered = template._render(applicant)
                    request.env['mail.mail'].sudo().create({'subject': rendered['subject'], 'body_html': text_html(rendered['body']),
                        'email_to': values['email'], 'email_from': job.company_id.email or job.user_id.email_formatted,
                        'model': 'hr.applicant', 'res_id': applicant.id, 'auto_delete': False})
            request.session['pb_application_last'] = time.time()
            return self._pb_hiring_render(job, done=True)
        except UserError as err:
            return self._pb_hiring_render(job, values, str(err))
