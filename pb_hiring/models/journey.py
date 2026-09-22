"""Guided hiring: one pipeline, tenant-owned content and explicit next actions."""
import base64
import json
import re
from pathlib import Path
from markupsafe import Markup, escape
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from .hiring_common import as_id, flag, P_CANDIDATE_MAIL

STAGES = [
    ('screening', 'Screening'), ('panel_review', 'Panel Review'),
    ('phone', 'Recruiter Phone Call'), ('assignment', 'Assignment'),
    ('discussion_1', 'Discussion 1'), ('discussion_2', 'Discussion 2'),
    ('discussion_3', 'Discussion 3'), ('reference', 'Reference Check'),
    ('offer', 'Offer Stage'), ('joined', 'Joined'),
    ('cv_reject', 'CV Reject'), ('interview_reject', 'Interview Reject'),
    ('drop_out', 'Drop Out'), ('on_hold', 'On Hold'),
    ('offer_drop_out', 'Offer Drop out'),
]
OUTCOMES = {'cv_reject', 'interview_reject', 'drop_out', 'on_hold', 'offer_drop_out'}
AUTHORIZATION = [('permit', 'Yes, I have a valid work permit/visa'),
                 ('citizen', 'Yes, I am a citizen/permanent resident'),
                 ('sponsor', 'No, I would require visa sponsorship'),
                 ('unsure', "I'm unsure")]
RELOCATION = [('yes', 'Yes'), ('no', 'No'), ('depends', 'Depends on the role/terms')]


def text_html(value):
    return Markup('<p>') + escape(value or '').replace('\n', Markup('<br/>')) + Markup('</p>')


class HiringBrand(models.Model):
    _inherit = 'res.company'

    pb_mr_approver_id = fields.Many2one('res.users', string='Manpower request approver', domain=[('share', '=', False)])
    pb_hiring_brand = fields.Char('Recruitment brand name')
    pb_hiring_intro = fields.Text('Application acknowledgement introduction')
    pb_hiring_linkedin = fields.Char('Company LinkedIn URL')
    pb_hiring_about = fields.Text('About the company')
    pb_hiring_building = fields.Text('What we are building')
    pb_hiring_mission = fields.Text('Our mission')
    pb_hiring_operate = fields.Text('Where we operate')
    pb_hiring_why = fields.Text('Why join us')

    def _hiring_brand(self):
        self.ensure_one()
        return self.pb_hiring_brand or self.name


class HiringStage(models.Model):
    _inherit = 'hr.recruitment.stage'
    pb_key = fields.Selection(STAGES, index=True, copy=False)

    @api.model
    def _ensure_journey_stages(self):
        Stage = self.sudo()
        for index, (key, name) in enumerate(STAGES):
            if not Stage.search_count([('pb_key', '=', key)]):
                Stage.create({'name': name, 'pb_key': key, 'sequence': (index + 1) * 10,
                              'fold': key in OUTCOMES, 'hired_stage': key == 'joined'})


class HiringApplicant(models.Model):
    _inherit = 'hr.applicant'
    pb_location = fields.Char('Current location')
    pb_nationality = fields.Char('Nationality')
    pb_linkedin = fields.Char('LinkedIn profile')
    pb_portfolio = fields.Char('Website / portfolio')
    pb_work_authorization = fields.Selection(AUTHORIZATION, string='Work authorization')
    pb_relocation = fields.Selection(RELOCATION, string='Willing to relocate')
    pb_motivation = fields.Text('Why join us?')
    pb_first_touch = fields.Json('First touch', readonly=True, copy=False)
    pb_application_touch = fields.Json('Application touch', readonly=True, copy=False)
    pb_hold_until = fields.Date('Next candidate update')
    pb_stage_reason = fields.Text('Stage decision reason')

    def write(self, vals):
        if not self.env.su and set(vals) & {'pb_first_touch', 'pb_application_touch'}:
            raise AccessError(_('Source attribution is captured automatically and cannot be edited.'))
        if vals.get('stage_id'):
            stage = self.env['hr.recruitment.stage'].sudo().browse(vals['stage_id'])
            if stage.pb_key in ('offer', 'joined'):
                for rec in self:
                    offers = self.env['pb.hiring.offer'].sudo().search([('applicant_id', '=', rec.id)])
                    if stage.pb_key == 'joined' and not offers.filtered(lambda o: o.state in ('signed', 'closed') and o.employee_id):
                        raise UserError(_('Record joining through the signed offer workspace first.'))
                    if stage.pb_key == 'offer' and not offers.filtered(lambda o: o.bgv_id and o.bgv_id.check_ready()[0]):
                        raise UserError(_('Complete the background checks and create the offer first.'))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        first = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'screening')], limit=1)
        for vals in vals_list:
            if vals.get('job_id') and not vals.get('stage_id') and first:
                vals['stage_id'] = first.id
        return super().create(vals_list)

    def _pb_next_stage(self, step=None):
        self.ensure_one()
        if step and step.stage_id:
            return step.stage_id
        if self.stage_id.pb_key:
            domain = [('pb_key', 'not in', list(OUTCOMES) + ['joined', 'offer']),
                      ('pb_key', '!=', False), ('sequence', '>', self.stage_id.sequence)]
            if not self.pb_requisition_id.pb_assignment:
                domain.append(('pb_key', '!=', 'assignment'))
            return self.env['hr.recruitment.stage'].sudo().search(domain, order='sequence,id', limit=1)
        # Legacy records keep their historical stage; the next deliberate move
        # enters the canonical pipeline rather than a rejection outcome.
        return self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'panel_review')], limit=1)

    def _pb_shortlist(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'panel_review')], limit=1)
        if stage:
            self.write({'stage_id': stage.id, 'kanban_state': 'done'})
            return True
        return super()._pb_shortlist()

    def _pb_reject(self, reason_id=None):
        for rec in self:
            key = 'cv_reject' if rec.stage_id.pb_key in ('screening', 'panel_review') else 'interview_reject'
            stage = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', key)], limit=1)
            if stage:
                rec.write({'stage_id': stage.id})
        return super()._pb_reject(reason_id)


class HiringOfferJourney(models.Model):
    _inherit = 'pb.hiring.offer'

    @api.model
    def draft_for(self, requisition_id, values=None):
        offer = super().draft_for(requisition_id, values)
        stage = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'offer')], limit=1)
        if stage and offer.state != 'closed':
            offer.applicant_id.sudo().write({'stage_id': stage.id})
        return offer

    def _mark_applicant_hired(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'joined')], limit=1)
        if stage:
            self.applicant_id.sudo().write({'stage_id': stage.id})
            return True
        return super()._mark_applicant_hired()



class HiringRequest(models.Model):
    _inherit = 'pb.hiring.requisition'
    pb_target_close_date = fields.Date('Target position closing date')
    pb_role_level = fields.Char('Role level / seniority')
    pb_assignment = fields.Boolean('Include an assignment')
    pb_jd_file = fields.Binary('Job description attachment', attachment=True)
    pb_jd_filename = fields.Char('JD filename')
    pb_assignment_file = fields.Binary('Assignment attachment', attachment=True)
    pb_assignment_filename = fields.Char('Assignment filename')

    def _approval_manager_uids(self):
        self.ensure_one()
        approver = self.company_id.pb_mr_approver_id
        return approver.ids if approver else super()._approval_manager_uids()

    def _chain_revision_values(self):
        vals = super()._chain_revision_values()
        # These are part of the proposal that approvers agree to.
        vals.update({'pb_role_level': self.pb_role_level, 'pb_assignment': self.pb_assignment,
                     'reporting_manager_id': self.reporting_manager_id.id,
                     'pb_target_close_date': self.pb_target_close_date})
        return vals


class HiringReferral(models.Model):
    _inherit = 'pb.hiring.referral'
    pb_consent = fields.Boolean('Candidate consent')
    pb_declaration = fields.Boolean('Relationship and panel declaration')
    pb_relationship = fields.Char('Relationship with candidate')
    pb_nationality = fields.Char('Candidate nationality')
    pb_location = fields.Char('Candidate current location')
    pb_linkedin = fields.Char('Candidate LinkedIn profile')
    pb_employment_type = fields.Char('Referrer employment type')
    pb_referrer_email = fields.Char('Referrer email')
    pb_department = fields.Char('Referrer department')
    pb_designation = fields.Char('Referrer designation')
    pb_entity = fields.Char('Referrer employment entity')

    @api.model
    def _state_of(self, applicant):
        applicant = applicant.sudo()
        if applicant and applicant.active and applicant.stage_id.pb_key == 'screening':
            return 'received'
        return super()._state_of(applicant)

    @api.model
    def refer(self, requisition_id, employee_id, values):
        employee = self.env['hr.employee'].sudo().browse(as_id(employee_id)).exists()
        if not self.env.su and (not employee or employee.user_id != self.env.user):
            raise AccessError(_('You can submit a referral only as yourself.'))
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if not req or req.state != 'open' or not req.referral_open or req.role_type == 'sensitive_replacement':
            raise ValueError('This role is not open to referrals.')
        if not values.get('consent') or not values.get('declaration'):
            raise UserError(_('Candidate consent and the relationship declaration are required.'))
        for key in ('name', 'email', 'phone', 'nationality', 'location', 'relationship', 'linkedin'):
            if not str(values.get(key) or '').strip():
                raise UserError(_('Complete the candidate contact, profile and relationship fields.'))
        if not values.get('attachment'):
            raise UserError(_('Attach the candidate’s updated resume.'))
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id)).exists()
        if req and req.role_type == 'sensitive_replacement':
            raise UserError(_('This role is not open to referrals.'))
        referral = super().refer(requisition_id, employee_id, values)
        referral.sudo().write({
            'pb_consent': True, 'pb_declaration': True,
            'pb_relationship': values['relationship'], 'pb_nationality': values['nationality'],
            'pb_location': values['location'], 'pb_linkedin': values['linkedin'],
            'pb_referrer_email': employee.work_email or employee.user_id.email,
            'pb_department': employee.department_id.name, 'pb_designation': employee.job_title,
            'pb_employment_type': employee.employee_type, 'pb_entity': employee.company_id.name,
        })
        referral.applicant_id.sudo().write({
            'pb_nationality': values['nationality'], 'pb_location': values['location'],
            'pb_linkedin': values['linkedin'],
            'pb_application_touch': {'source': 'Referral', 'referrer_employee_id': employee.id},
        })
        return referral


class HiringInterview(models.Model):
    _inherit = 'pb.hiring.interview'

    @api.constrains('panel_employee_ids', 'applicant_id')
    def _check_referrer_panel(self):
        for rec in self:
            referrers = rec.applicant_id.sudo().pb_referral_ids.employee_id
            if rec.panel_employee_ids & referrers:
                raise ValidationError(_('A referrer cannot sit on the candidate’s interview panel.'))


class HiringMessageTemplate(models.Model):
    _name = 'pb.hiring.message.template'
    _description = 'Hiring communication template'
    _order = 'sequence, id'
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    key = fields.Selection([('received', 'Application received'), ('phone', 'Recruiter phone call'),
                            ('assignment', 'Assignment'), ('on_hold', 'On hold'), ('cv_reject', 'CV rejection')], required=True)
    subject = fields.Char(required=True)
    body = fields.Text(required=True)
    active = fields.Boolean(default=True)

    def _render(self, applicant, values=None):
        self.ensure_one()
        company = self.company_id
        tokens = {'first_name': (applicant.partner_name or '').split(' ')[0],
                  'role': applicant.job_id.name or '', 'brand': company._hiring_brand(),
                  'website': company.website or '', 'linkedin': company.pb_hiring_linkedin or '',
                  'company_intro': company.pb_hiring_intro or '',
                  'sender_name': self.env.user.name, 'hr_name': applicant.user_id.name or self.env.user.name}
        tokens.update(values or {})
        required = set(re.findall(r'{{\s*(\w+)\s*}}', self.subject + self.body))
        missing = sorted(k for k in required if not str(tokens.get(k) or '').strip()
                         and k not in ('website', 'linkedin', 'company_intro'))
        if missing:
            raise UserError(_('Complete these message details first: %s', ', '.join(missing)))
        render = lambda text: re.sub(r'{{\s*(\w+)\s*}}', lambda m: str(tokens.get(m[1]) or ''), text)
        return {'subject': render(self.subject), 'body': render(self.body)}


class HiringJourney(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _seed_journey(self):
        seed_journey(self.env)

    @api.model
    def journey_options(self):
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        company = self.env.company
        return {'brand': company._hiring_brand(),
                'requestor': self.env.user.name,
                'currencies': self.env['res.currency'].search_read([('active', '=', True)], ['name']),
                'currency_id': company.currency_id.id,
                'countries': self.env['res.country'].search_read([], ['name']),
                'message_fields': {t.key: sorted(set(re.findall(r'{{\s*(\w+)\s*}}', t.subject + t.body)) -
                    {'first_name', 'role', 'brand', 'website', 'linkedin', 'company_intro', 'sender_name', 'hr_name'})
                    for t in self.env['pb.hiring.message.template'].search([('company_id', '=', company.id)])},
                'managers': self.env['hr.employee'].sudo().search_read(
                    [('company_id', 'in', self.env.companies.ids)], ['name'], limit=1000),
                'users': self.env['res.users'].sudo().search_read(
                    [('share', '=', False), ('company_ids', 'in', self.env.companies.ids)], ['name'], limit=1000),
                'stages': [{'id': s.id, 'key': s.pb_key, 'name': s.name, 'outcome': s.pb_key in OUTCOMES}
                           for s in self.env['hr.recruitment.stage'].sudo().search([('pb_key', '!=', False)], order='sequence,id')],
                'company_sections': [{'key': k, 'title': title, 'body': company['pb_hiring_' + k] or ''}
                    for k, title in [('about', 'About ' + company._hiring_brand()), ('building', 'What we are building'),
                                     ('mission', 'Our mission'), ('operate', 'Where we operate'), ('why', 'Why join us')]]}

    def _row(self, req):
        row = super()._row(req)
        row['target_close_date'] = str(req.pb_target_close_date or '')
        return row

    def _act_create(self, payload):
        result = super()._act_create(payload)
        req = self.env['pb.hiring.requisition'].browse(result['id'])
        extra = {'pb_role_level': str(payload.get('role_level') or '')[:200],
                 'pb_assignment': bool(payload.get('assignment')),
                 'pb_target_close_date': payload.get('target_close_date') or False}
        manager = self.env['hr.employee'].sudo().browse(as_id(payload.get('reporting_manager_id'))).exists()
        if manager:
            if manager.company_id != req.company_id:
                raise UserError(_('Choose a reporting manager in this company.'))
            extra['reporting_manager_id'] = manager.id
        if payload.get('currency_id'):
            extra['currency_id'] = as_id(payload['currency_id'])
        for kind in ('jd', 'assignment'):
            upload = payload.get(kind + '_file')
            if upload:
                if len(upload) > 14000000:
                    raise UserError(_('Attachments must be smaller than 10 MB.'))
                extra['pb_' + kind + '_file'] = upload
                extra['pb_' + kind + '_filename'] = str(payload.get(kind + '_filename') or kind)[:200]
        req.write(extra)
        for index, step in enumerate(payload.get('interviews') or []):
            if not step.get('owner_id') or not step.get('focus'):
                continue
            owner = self.env['res.users'].sudo().browse(as_id(step['owner_id'])).exists()
            if not owner or req.company_id not in owner.company_ids:
                raise UserError(_('Choose interviewers in this company.'))
            stage = self.env['hr.recruitment.stage'].sudo().search([('pb_key', '=', 'discussion_%s' % (index + 1))], limit=1)
            self.env['pb.hiring.step'].create({'requisition_id': req.id, 'name': 'Discussion %s' % (index + 1),
                'sequence': (index + 1) * 10, 'owner_id': owner.id, 'notes': step['focus'],
                'kind': 'interview', 'stage_id': stage.id})
        return result

    def _act_new_jd(self, payload):
        if payload.get('sections'):
            req = self._get(payload)
            self._require_recruit(req)
            company = req.company_id
            html = Markup('')
            for key, title in [('about', 'About ' + company._hiring_brand()), ('building', 'What we are building'),
                               ('mission', 'Our mission'), ('operate', 'Where we operate')]:
                if company['pb_hiring_' + key]:
                    html += Markup('<h2>%s</h2>') % title + text_html(company['pb_hiring_' + key])
            for key, title in [('role', 'What the role is about'), ('duties', 'What you will be doing'),
                               ('must', 'Must-have skills and characteristics'), ('nice', 'Nice-to-have skills and characteristics'),
                               ('process', 'Interview process')]:
                value = payload['sections'].get(key, '').strip()
                if key in ('role', 'duties', 'must') and not value:
                    raise UserError(_('Complete the role summary, responsibilities and must-have criteria.'))
                if value:
                    html += Markup('<h2>%s</h2>') % title + text_html(value)
            if company.pb_hiring_why:
                html += Markup('<h2>Why join %s</h2>') % company._hiring_brand() + text_html(company.pb_hiring_why)
            payload = dict(payload, body=str(html))
        return super()._act_new_jd(payload)

    def _act_journey_stage(self, payload):
        applicant = self.env['hr.applicant'].with_context(active_test=False).browse(as_id(payload.get('applicant_id'))).exists()
        if not applicant:
            raise UserError(_('This candidate is no longer available.'))
        applicant.check_access('write')
        self._require_recruit(applicant.pb_requisition_id)
        stage = self.env['hr.recruitment.stage'].browse(as_id(payload.get('stage_id'))).exists()
        if not stage or not stage.pb_key:
            raise UserError(_('Choose a hiring stage.'))
        if stage.pb_key in ('offer', 'joined'):
            raise UserError(_('Use the offer workspace to complete the required checks and record joining.'))
        reason = (payload.get('reason') or '').strip()
        if stage.pb_key in OUTCOMES and not reason:
            raise UserError(_('Add a reason for this decision.'))
        if stage.pb_key == 'on_hold' and not payload.get('update_date'):
            raise UserError(_('Set the date when you will update the candidate.'))
        vals = {'stage_id': stage.id, 'pb_stage_reason': reason,
                'pb_hold_until': payload.get('update_date') or False}
        applicant.write(vals)
        applicant.message_post(body=_('Moved to %(stage)s. %(reason)s', stage=stage.name, reason=reason))
        return {'id': applicant.id, 'note': _('Candidate stage updated.')}

    def _act_open_brand(self, payload):
        if not self._can_admin():
            raise AccessError(_('Hiring administrator access is required.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'res.company', 'res_id': self.env.company.id,
                'views': [(self.env.ref('pb_hiring.view_hiring_brand').id, 'form')], 'target': 'new', 'name': _('Recruitment identity')}

    def _act_open_templates(self, payload):
        self._require_recruit()
        return {'type': 'ir.actions.act_window', 'res_model': 'pb.hiring.message.template',
                'view_mode': 'list,form', 'views': [(False, 'list'), (False, 'form')], 'name': _('Candidate emails')}

    def _act_message_preview(self, payload):
        applicant = self.env['hr.applicant'].with_context(active_test=False).browse(as_id(payload.get('applicant_id'))).exists()
        applicant.check_access('read')
        self._require_recruit(applicant.pb_requisition_id)
        template = self.env['pb.hiring.message.template'].search([
            ('company_id', '=', applicant.company_id.id), ('key', '=', payload.get('key'))], limit=1)
        if not template:
            raise UserError(_('Configure this candidate email for the company first.'))
        return template._render(applicant, payload.get('values'))

    def _act_message_send(self, payload):
        rendered = self._act_message_preview(payload)
        applicant = self.env['hr.applicant'].browse(as_id(payload['applicant_id']))
        if not flag(self.env, P_CANDIDATE_MAIL):
            raise UserError(_('Candidate emails are switched off in Hiring settings.'))
        if not applicant.email_from:
            raise UserError(_('Add a candidate email address first.'))
        applicant.message_post(subject=rendered['subject'], body=text_html(rendered['body']),
                               message_type='comment', subtype_xmlid='mail.mt_note')
        self.env['mail.mail'].sudo().create({'subject': rendered['subject'],
            'body_html': text_html(rendered['body']), 'email_to': applicant.email_from,
            'email_from': self.env.company.email or self.env.user.email_formatted,
            'model': 'hr.applicant', 'res_id': applicant.id, 'auto_delete': False})
        return {'note': _('Candidate email queued. Delivery is tracked in the mail queue.')}


def seed_journey(env):
    env['hr.recruitment.stage']._ensure_journey_stages()
    source = json.loads((Path(__file__).parent.parent / 'data/journey_content.json').read_text())
    for company in env['res.company'].sudo().search([]):
        if env.cr.dbname == 'rize' and not company.pb_mr_approver_id:
            matches = env['res.users'].sudo().search([('name', '=ilike', 'Dhruv%'), ('share', '=', False), ('company_ids', 'in', company.id)])
            if len(matches) == 1:
                company.pb_mr_approver_id = matches
        if env.cr.dbname == 'rize' and not company.pb_hiring_brand:
            company.write(dict(pb_hiring_brand='Rize', pb_hiring_intro=source['intro'],
                               **{'pb_hiring_' + k: v for k, v in source['sections'].items()}))
        for index, template in enumerate(source['emails']):
            if not env['pb.hiring.message.template'].sudo().search_count([('company_id', '=', company.id), ('key', '=', template['key'])]):
                env['pb.hiring.message.template'].sudo().create(dict(template, company_id=company.id, sequence=index * 10))
