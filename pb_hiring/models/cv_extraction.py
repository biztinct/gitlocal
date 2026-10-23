import json
import re
import uuid

from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ApplicantCV(models.Model):
    _inherit = 'hr.applicant'

    pb_cv_state = fields.Selection([('none', 'Not extracted'), ('queued', 'Waiting for extraction'), ('failed', 'Extraction needs attention'), ('review', 'Review needed'), ('applied', 'Reviewed')], string='CV extraction status', default='none', copy=False)
    pb_cv_note = fields.Char(string='CV extraction update', readonly=True, copy=False)
    pb_cv_result = fields.Json(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_experience = fields.Text(string='CV employment history', groups='pb_hiring.group_hiring_user')
    pb_cv_education = fields.Text(string='CV education', groups='pb_hiring.group_hiring_user')
    pb_cv_employment = fields.Json(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_employment_html = fields.Html(string='Reviewed employment records', compute='_compute_cv_employment', groups='pb_hiring.group_hiring_user')
    pb_cv_skill_ids = fields.Many2many('hr.skill', 'pb_cv_applicant_skill_rel', string='Reviewed CV skills', copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_search_text = fields.Text(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_revision = fields.Char(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_checksum = fields.Char(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_attachment_id = fields.Many2one('ir.attachment', copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_reviewed_by = fields.Many2one('res.users', string='CV reviewed by', readonly=True, copy=False)
    pb_cv_reviewed_at = fields.Datetime(string='CV reviewed on', readonly=True, copy=False)

    @api.depends('pb_cv_employment')
    def _compute_cv_employment(self):
        for app in self:
            rows = app.pb_cv_employment or []
            app.pb_cv_employment_html = Markup('<table class="table"><thead><tr><th>Employer</th><th>Role</th><th>From</th><th>To</th></tr></thead><tbody>') + Markup('').join(
                Markup('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>') % tuple(escape(v) for v in (
                    r.get('employer', ''), r.get('title', ''), r.get('start', ''), _('Present') if r.get('current') else r.get('end', ''))) for r in rows) + Markup('</tbody></table>') if rows else False

    def _current_cv(self):
        docs = self.env['pb.hiring']._doc_rows(self, {'cv'})
        return self.env['ir.attachment'].sudo().browse(docs[0]['id']) if docs else self.env['ir.attachment']

    def action_extract_cv(self):
        self.ensure_one()
        self.env['pb.hiring']._require_recruit(self.pb_requisition_id)
        self.check_access('write')
        self._extract_cv()
        return self.action_review_cv()

    def _extract_cv(self):
        self.ensure_one()
        if self.pb_anonymised_on:
            raise UserError(_('Removed candidates cannot be parsed.'))
        conn = self.env['pb.hiring.connection']._for_company('cv', self.company_id)
        if not conn:
            raise UserError(_('Set up CV extraction in Hiring connections first.'))
        conn._ready()
        attachment = self._current_cv()
        if not attachment:
            raise UserError(_('Attach a CV before extracting it.'))
        if attachment.file_size > 5 * 1024 * 1024:
            raise UserError(_('Use a CV of at most 5 MB.'))
        checksum = attachment.checksum
        skills = self.env['hr.skill'].sudo().search_read([], ['name'], limit=5000)
        result = conn._http('POST', '/extract', files={'file': (attachment.name, attachment.raw, attachment.mimetype)},
                            data={'skills': json.dumps(skills)}, timeout=(5, 180)).json()
        if not isinstance(result, dict) or result.get('contract') != 'payobook-cv-v1' or not isinstance(result.get('text'), str) or not result['text'].strip():
            raise UserError(_('The parser did not return readable CV content.'))
        if not isinstance(result.get('skill_ids', []), list) or not isinstance(result.get('employment', []), list):
            raise UserError(_('The parser returned an invalid result.'))
        jobs = result.get('employment', [])
        if len(jobs) > 50 or any(not isinstance(r, dict) or any(not isinstance(r.get(k, ''), str) for k in ('employer', 'title', 'start', 'end', 'source', 'note')) or not isinstance(r.get('current', False), bool) for r in jobs):
            raise UserError(_('The parser returned invalid employment records.'))
        for key, limit in [('text', 200000), ('experience', 20000), ('education', 10000)]:
            if not isinstance(result.get(key, ''), str):
                raise UserError(_('The parser returned an invalid section.'))
            result[key] = result.get(key, '')[:limit]
        result['skill_ids'] = [s['id'] for s in skills if s['id'] in result.get('skill_ids', [])]
        self.sudo().write({'pb_cv_result': result, 'pb_cv_state': 'review', 'pb_cv_attachment_id': attachment.id,
                          'pb_cv_revision': uuid.uuid4().hex, 'pb_cv_checksum': checksum,
                          'pb_cv_search_text': result['text'],
                          'pb_cv_note': _('Extraction ready. Review the suggestions against the original CV.')})
        attachment.write({'index_content': result['text']})

    def action_review_cv(self):
        self.ensure_one()
        self.env['pb.hiring']._require_recruit(self.pb_requisition_id)
        self.check_access('read')
        if self.pb_cv_state != 'review' or not self.pb_cv_result:
            raise UserError(_('Extract the current CV before reviewing suggestions.'))
        result = self.sudo().pb_cv_result
        wizard = self.env['pb.hiring.cv.review'].create({
            'applicant_id': self.id, 'revision': self.pb_cv_revision,
            'experience': result.get('experience', ''), 'education': result.get('education', ''),
            'text': result.get('text', ''), 'skill_ids': [(6, 0, result.get('skill_ids', []))],
            'employment_ids': [(0, 0, {key: row.get(key, False) for key in ('employer', 'title', 'start', 'end', 'current', 'source', 'note')}) for row in result.get('employment', [])]})
        return {'type': 'ir.actions.act_window', 'name': _('Review CV extraction'),
                'res_model': wizard._name, 'res_id': wizard.id, 'views': [(False, 'form')], 'target': 'new'}

    def _pb_anonymise(self):
        result = super()._pb_anonymise()
        self.sudo().write({'pb_cv_result': False, 'pb_cv_employment': False, 'pb_cv_search_text': False,
                          'pb_cv_experience': False, 'pb_cv_education': False, 'pb_cv_skill_ids': [(5, 0, 0)],
                          'pb_cv_state': 'none', 'pb_cv_note': False, 'pb_cv_revision': False,
                          'pb_cv_checksum': False, 'pb_cv_attachment_id': False,
                          'pb_cv_reviewed_by': False, 'pb_cv_reviewed_at': False})
        self.env['pb.hiring.cv.review'].sudo().search([('applicant_id', 'in', self.ids)]).unlink()
        return result


class CVReview(models.TransientModel):
    _name = 'pb.hiring.cv.review'
    _description = 'Review CV extraction'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True, ondelete='cascade')
    revision = fields.Char(readonly=True)
    skill_ids = fields.Many2many('hr.skill', string='Skills mentioned in CV')
    employment_ids = fields.One2many('pb.hiring.cv.employment.review', 'review_id', string='Employment records')
    experience = fields.Text(string='Employment history evidence')
    education = fields.Text()
    text = fields.Text(string='Extracted text', readonly=True)
    replace_existing = fields.Boolean(string='Replace previously reviewed employment, education and CV skills')

    def action_apply(self):
        self.ensure_one()
        app = self.applicant_id
        self.env['pb.hiring']._require_recruit(app.pb_requisition_id)
        app.check_access('write')
        current = app._current_cv()
        if (app.pb_cv_state != 'review' or not self.revision or self.revision != app.pb_cv_revision
                or not current or current != app.pb_cv_attachment_id or current.checksum != app.pb_cv_checksum):
            raise UserError(_('This review is out of date. Extract and review the current CV again.'))
        self.employment_ids._validate_dates()
        jobs = [{k: row[k] or (False if k == 'current' else '') for k in ('employer', 'title', 'start', 'end', 'current', 'source')} for row in self.employment_ids]
        values = {'pb_cv_state': 'applied', 'pb_cv_revision': uuid.uuid4().hex,
                  'pb_cv_reviewed_by': self.env.uid, 'pb_cv_reviewed_at': fields.Datetime.now(),
                  'pb_cv_note': _('CV reviewed. Mentioned skills do not imply assessed proficiency.')}
        for target, source in [('pb_cv_experience', 'experience'), ('pb_cv_education', 'education')]:
            if self.replace_existing or not app[target]:
                values[target] = self[source]
        if self.replace_existing or not app.pb_cv_employment:
            values['pb_cv_employment'] = jobs
        # CV mentions are searchable but never invent a proficiency assessment.
        values['pb_cv_skill_ids'] = [(6, 0, (self.skill_ids if self.replace_existing else app.pb_cv_skill_ids | self.skill_ids).ids)]
        app.write(values)
        return {'type': 'ir.actions.act_window_close'}


class CVEmploymentReview(models.TransientModel):
    _name = 'pb.hiring.cv.employment.review'
    _description = 'Employment extracted from CV'
    _order = 'id'

    review_id = fields.Many2one('pb.hiring.cv.review', required=True, ondelete='cascade')
    employer = fields.Char()
    title = fields.Char(string='Job title')
    start = fields.Char(string='From (YYYY or YYYY-MM)')
    end = fields.Char(string='To (YYYY or YYYY-MM)')
    current = fields.Boolean(string='Current job')
    source = fields.Text(string='Source evidence', readonly=True)
    note = fields.Char(string='Check', readonly=True)

    def _validate_dates(self):
        for row in self:
            for date in (row.start, row.end):
                if date and not re.fullmatch(r'(?:19|20|21)\d{2}(?:-(?:0[1-9]|1[0-2]))?', date):
                    raise ValidationError(_('Use YYYY or YYYY-MM; leave unknown dates blank.'))
            if row.current and row.end:
                raise ValidationError(_('A current job cannot have an end date.'))
            if row.start and row.end:
                # Year-only values are intervals, not invented January dates.
                if (row.start + ('-01' if len(row.start) == 4 else '')) > (row.end + ('-12' if len(row.end) == 4 else '')):
                    raise ValidationError(_('Employment end cannot precede its start.'))


class NewCVAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _hiring_cv_applicants(self):
        apps = self.env['hr.applicant'].sudo().browse(self.sudo().filtered(
            lambda a: a.res_model == 'hr.applicant' and a.res_id).mapped('res_id')).exists()
        return apps.filtered(lambda a: a.pb_requisition_id and not a.pb_anonymised_on)

    def _queue_hiring_cv(self, apps=None):
        apps = apps if apps is not None else self._hiring_cv_applicants()
        for app in apps:
            current = app._current_cv()
            if current and current not in self and current == app.pb_cv_attachment_id and current.checksum == app.pb_cv_checksum:
                continue
            conn = self.env['pb.hiring.connection']._for_company('cv', app.company_id)
            queued = bool(current and conn.enabled and conn.check_ok)
            app.write({'pb_cv_state': 'queued' if queued else 'none', 'pb_cv_result': False,
                       'pb_cv_revision': uuid.uuid4().hex, 'pb_cv_checksum': False,
                       'pb_cv_attachment_id': False, 'pb_cv_search_text': False,
                       'pb_cv_note': _('CV changed; extraction is queued.') if queued else _('CV changed. Extraction is paused until the service is enabled.')})

    @api.model_create_multi
    def create(self, values):
        rows = super().create(values)
        rows._queue_hiring_cv()
        return rows

    def write(self, vals):
        changed = bool(set(vals) & {'res_id', 'res_model', 'pb_form_key', 'raw', 'datas', 'name'})
        apps = self._hiring_cv_applicants() if changed else None
        result = super().write(vals)
        if changed:
            self._queue_hiring_cv(apps | self._hiring_cv_applicants())
        return result

    def unlink(self):
        apps = self._hiring_cv_applicants()
        result = super().unlink()
        self.env['ir.attachment']._queue_hiring_cv(apps)
        return result


class HiringCVProfile(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def get_candidate(self, applicant_id):
        result = super().get_candidate(applicant_id)
        if result.get('can_recruit'):
            app = self.env['hr.applicant'].sudo().browse(applicant_id)
            result['cv_profile'] = {'state': app.pb_cv_state, 'note': app.pb_cv_note or '',
                                   'skills': app.pb_cv_skill_ids.mapped('name'),
                                   'employment': app.pb_cv_employment or [],
                                   'education': app.pb_cv_education or '',
                                   'experience': app.pb_cv_experience or ''}
        return result
