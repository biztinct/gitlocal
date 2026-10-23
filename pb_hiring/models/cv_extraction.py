import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class ApplicantCV(models.Model):
    _inherit = 'hr.applicant'

    pb_cv_state = fields.Selection([('none', 'Not extracted'), ('queued', 'Waiting for extraction'), ('failed', 'Extraction needs attention'), ('review', 'Review needed'), ('applied', 'Reviewed')], default='none', copy=False)
    pb_cv_note = fields.Char(readonly=True, copy=False)
    pb_cv_result = fields.Json(copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_experience = fields.Text(string='CV employment history', groups='pb_hiring.group_hiring_user')
    pb_cv_education = fields.Text(string='CV education', groups='pb_hiring.group_hiring_user')
    pb_cv_attachment_id = fields.Many2one('ir.attachment', copy=False, groups='pb_hiring.group_hiring_user')
    pb_cv_reviewed_by = fields.Many2one('res.users', readonly=True, copy=False)
    pb_cv_reviewed_at = fields.Datetime(readonly=True, copy=False)

    def action_extract_cv(self):
        self.ensure_one()
        self.env['pb.hiring']._require_recruit(self.pb_requisition_id)
        self.check_access('write')
        self._extract_cv()
        return self.action_review_cv()

    def _extract_cv(self):
        self.ensure_one()
        conn = self.env['pb.hiring.connection']._for_company('cv', self.company_id)
        if not conn:
            raise UserError(_('Set up CV extraction in Hiring connections first.'))
        conn._ready()
        docs = self.env['pb.hiring']._doc_rows(self, {'cv'})
        if not docs:
            raise UserError(_('Attach a CV before extracting it.'))
        attachment = self.env['ir.attachment'].sudo().browse(docs[0]['id'])
        if attachment.file_size > 5 * 1024 * 1024:
            raise UserError(_('Use a CV of at most 5 MB.'))
        skills = self.env['hr.skill'].sudo().search_read([], ['name'], limit=5000)
        result = conn._http('POST', '/extract', files={'file': (attachment.name, attachment.raw, attachment.mimetype)},
                            data={'skills': json.dumps(skills)}).json()
        if result.get('contract') != 'payobook-cv-v1' or not result.get('text'):
            raise UserError(_('The parser did not return readable CV content.'))
        result['skill_ids'] = [s['id'] for s in skills if s['id'] in result.get('skill_ids', [])]
        self.sudo().write({'pb_cv_result': result, 'pb_cv_state': 'review', 'pb_cv_attachment_id': attachment.id,
                          'pb_cv_note': _('Extraction ready. Review the suggestions against the original CV.')})
        attachment.write({'index_content': str(result['text'])[:200000]})

    def action_review_cv(self):
        self.ensure_one()
        self.env['pb.hiring']._require_recruit(self.pb_requisition_id)
        self.check_access('read')
        result = self.sudo().pb_cv_result or {}
        wizard = self.env['pb.hiring.cv.review'].create({
            'applicant_id': self.id, 'experience': result.get('experience', ''),
            'education': result.get('education', ''), 'text': result.get('text', ''),
            'skill_ids': [(6, 0, result.get('skill_ids', []))]})
        return {'type': 'ir.actions.act_window', 'name': _('Review CV extraction'),
                'res_model': wizard._name, 'res_id': wizard.id, 'views': [(False, 'form')], 'target': 'new'}


class CVReview(models.TransientModel):
    _name = 'pb.hiring.cv.review'
    _description = 'Review CV extraction'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True)
    skill_ids = fields.Many2many('hr.skill', string='Skills found')
    experience = fields.Text(string='Employment history')
    education = fields.Text()
    text = fields.Text(string='Extracted text', readonly=True)
    replace_existing = fields.Boolean(string='Replace existing employment and education text')

    def action_apply(self):
        self.ensure_one()
        app = self.applicant_id
        self.env['pb.hiring']._require_recruit(app.pb_requisition_id)
        app.check_access('write')
        if app.pb_cv_state != 'review':
            raise UserError(_('Extract the current CV before applying suggestions.'))
        values = {'pb_cv_state': 'applied', 'pb_cv_reviewed_by': self.env.uid, 'pb_cv_reviewed_at': fields.Datetime.now()}
        for target, source in [('pb_cv_experience', 'experience'), ('pb_cv_education', 'education')]:
            if self.replace_existing or not app[target]:
                values[target] = self[source]
        app.write(values)
        # Standard recruitment skills; preserve existing recruiter assessments.
        for skill in self.skill_ids:
            if skill in app.skill_ids:
                continue
            level = self.env['hr.skill.level'].sudo().search([('skill_type_id', '=', skill.skill_type_id.id)], order='level_progress', limit=1)
            if level:
                self.env['hr.applicant.skill'].sudo().create({'applicant_id': app.id,
                    'skill_id': skill.id, 'skill_type_id': skill.skill_type_id.id, 'skill_level_id': level.id})
        return {'type': 'ir.actions.act_window_close'}


class NewCVAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _queue_hiring_cv(self):
        for attachment in self.sudo().filtered(lambda a: a.res_model == 'hr.applicant' and a.res_id and a.pb_form_key == 'cv'):
            app = self.env['hr.applicant'].sudo().browse(attachment.res_id).exists()
            if not app or not app.pb_requisition_id:
                continue
            conn = self.env['pb.hiring.connection']._for_company('cv', app.company_id)
            if conn.enabled and conn.check_ok:
                app.write({'pb_cv_state': 'queued', 'pb_cv_note': _('New CV received; extraction is queued.')})

    @api.model_create_multi
    def create(self, values):
        rows = super().create(values)
        rows._queue_hiring_cv()
        return rows

    def write(self, vals):
        result = super().write(vals)
        if set(vals) & {'res_id', 'res_model', 'pb_form_key', 'raw', 'datas'}:
            self._queue_hiring_cv()
        return result
