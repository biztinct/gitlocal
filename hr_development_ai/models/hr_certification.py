# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRCertification(models.Model):
    _name = 'hr.certification'
    _description = 'Employee Certification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc'

    name = fields.Char(string='Certification Name', required=True, tracking=True)

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    certification_type = fields.Selection([
        ('internal', 'Internal Certification'),
        ('external', 'External Certification'),
        ('license', 'Professional License'),
        ('course_completion', 'Course Completion')
    ], string='Type', required=True, default='internal')

    issuing_organization = fields.Char(string='Issuing Organization')

    issue_date = fields.Date(
        string='Issue Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )

    expiry_date = fields.Date(string='Expiry Date', tracking=True)

    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        store=True
    )

    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry'
    )

    # Related course
    course_id = fields.Many2one(
        'slide.channel',
        string='Related Course',
        ondelete='set null',
        help='Course that led to this certification'
    )

    # Skills
    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills Certified',
        help='Skills validated by this certification'
    )

    # Documentation
    certificate_file = fields.Binary(string='Certificate File')
    certificate_filename = fields.Char(string='Filename')

    credential_id = fields.Char(string='Credential ID')
    credential_url = fields.Char(string='Verification URL')

    description = fields.Html(string='Description')
    notes = fields.Text(string='Notes')

    active = fields.Boolean(default=True)

    @api.depends('expiry_date')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for cert in self:
            if cert.expiry_date:
                cert.is_expired = cert.expiry_date < today
            else:
                cert.is_expired = False

    @api.depends('expiry_date')
    def _compute_days_until_expiry(self):
        today = fields.Date.today()
        for cert in self:
            if cert.expiry_date and not cert.is_expired:
                delta = cert.expiry_date - today
                cert.days_until_expiry = delta.days
            else:
                cert.days_until_expiry = 0

    @api.model
    def check_expiring_certifications(self):
        """
        Cron job: Send notifications for expiring certifications
        """
        # Find certifications expiring in next 30 days
        expiring_date = fields.Date.today() + relativedelta(days=30)

        expiring_certs = self.search([
            ('expiry_date', '<=', expiring_date),
            ('expiry_date', '>=', fields.Date.today()),
            ('active', '=', True)
        ])

        for cert in expiring_certs:
            if cert.employee_id.user_id:
                cert.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=cert.expiry_date,
                    summary=f'Certification Expiring: {cert.name}',
                    note=f'Your {cert.name} certification expires on {cert.expiry_date}. Please renew.',
                    user_id=cert.employee_id.user_id.id
                )

        return True

    @api.model_create_multi
    def create(self, vals_list):
        """Update employee skills when certification is created"""
        certifications = super().create(vals_list)

        for cert in certifications:
            # Update employee skills from certification
            for skill in cert.skill_ids:
                employee_skill = self.env['hr.employee.skill'].search([
                    ('employee_id', '=', cert.employee_id.id),
                    ('skill_id', '=', skill.id)
                ], limit=1)

                if employee_skill:
                    employee_skill.certification_score = 90  # High score for certification
                    employee_skill.aggregate_proficiency_score()
                else:
                    new_skill = self.env['hr.employee.skill'].create({
                        'employee_id': cert.employee_id.id,
                        'skill_id': skill.id,
                        'certification_score': 90,
                        'source': 'certification',
                        'evidence_text': f'Certified: {cert.name}'
                    })
                    new_skill.aggregate_proficiency_score()

        return certifications
