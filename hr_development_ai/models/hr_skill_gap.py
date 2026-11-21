# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HRSkillGap(models.Model):
    _name = 'hr.skill.gap'
    _description = 'Employee Skill Gap Analysis'
    _order = 'employee_id, gap_score desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='cascade',
        index=True
    )

    job_id = fields.Many2one(
        'hr.job',
        string='Target Job',
        required=True,
        ondelete='cascade',
        index=True,
        help='Job position being analyzed for gaps'
    )

    skill_id = fields.Many2one(
        'hr.skill',
        string='Skill',
        required=True,
        ondelete='cascade',
        index=True
    )

    skill_category_id = fields.Many2one(
        related='skill_id.category_id',
        string='Category',
        store=True,
        readonly=True
    )

    # Current vs Required
    current_score = fields.Float(
        string='Current Proficiency',
        help='Employee current proficiency (0-100)'
    )

    required_score = fields.Float(
        string='Required Proficiency',
        help='Job required proficiency (0-100)'
    )

    gap_score = fields.Float(
        string='Gap Score',
        compute='_compute_gap_score',
        store=True,
        help='Positive number indicates skill gap'
    )

    gap_percentage = fields.Float(
        string='Gap %',
        compute='_compute_gap_percentage',
        store=True
    )

    # Status
    status = fields.Selection([
        ('exceeds', 'Exceeds Requirements'),
        ('meets', 'Meets Requirements'),
        ('minor_gap', 'Minor Gap'),
        ('major_gap', 'Major Gap'),
        ('missing', 'Skill Missing')
    ], string='Status', compute='_compute_status', store=True)

    is_required = fields.Boolean(
        string='Required Skill',
        help='Is this a mandatory skill for the job?'
    )

    # AI Recommendations
    recommended_courses = fields.Many2many(
        'slide.channel',
        string='Recommended Courses',
        help='AI-recommended courses to close this gap'
    )

    recommended_actions = fields.Text(
        string='Recommended Actions',
        help='AI-generated recommendations to close this gap'
    )

    estimated_time_to_close = fields.Integer(
        string='Est. Time to Close (days)',
        help='AI-estimated time to close this gap'
    )

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Priority', compute='_compute_priority', store=True)

    # Metadata
    analysis_date = fields.Datetime(
        string='Analysis Date',
        default=fields.Datetime.now
    )

    @api.depends('current_score', 'required_score')
    def _compute_gap_score(self):
        for record in self:
            record.gap_score = max(0, record.required_score - record.current_score)

    @api.depends('gap_score', 'required_score')
    def _compute_gap_percentage(self):
        for record in self:
            if record.required_score > 0:
                record.gap_percentage = (record.gap_score / record.required_score) * 100
            else:
                record.gap_percentage = 0.0

    @api.depends('gap_score', 'current_score')
    def _compute_status(self):
        for record in self:
            if record.current_score == 0:
                record.status = 'missing'
            elif record.gap_score <= 0:
                if record.current_score > record.required_score:
                    record.status = 'exceeds'
                else:
                    record.status = 'meets'
            elif record.gap_score <= 10:
                record.status = 'minor_gap'
            else:
                record.status = 'major_gap'

    @api.depends('gap_score', 'is_required')
    def _compute_priority(self):
        for record in self:
            if record.gap_score == 0:
                record.priority = 'low'
            elif record.is_required:
                if record.gap_score > 30:
                    record.priority = 'critical'
                elif record.gap_score > 15:
                    record.priority = 'high'
                else:
                    record.priority = 'medium'
            else:
                if record.gap_score > 30:
                    record.priority = 'high'
                else:
                    record.priority = 'medium'

    @api.model
    def analyze_employee_for_job(self, employee_id, job_id):
        """
        Perform comprehensive skill gap analysis for employee vs job

        Args:
            employee_id: Employee record ID
            job_id: Job record ID

        Returns:
            dict: Analysis results with gaps and recommendations
        """
        employee = self.env['hr.employee'].browse(employee_id)
        job = self.env['hr.job'].browse(job_id)

        # Delete existing gap records
        self.search([
            ('employee_id', '=', employee_id),
            ('job_id', '=', job_id)
        ]).unlink()

        gaps = []
        employee_skills = {
            es.skill_id.id: es.proficiency_score
            for es in employee.skill_ids
        }

        # Analyze each job requirement
        for job_skill in job.skill_ids:
            current_score = employee_skills.get(job_skill.skill_id.id, 0.0)

            gap = self.create({
                'employee_id': employee_id,
                'job_id': job_id,
                'skill_id': job_skill.skill_id.id,
                'current_score': current_score,
                'required_score': job_skill.required_score,
                'is_required': job_skill.is_required
            })

            # Get AI recommendations if gap exists
            if gap.gap_score > 0:
                gap._generate_ai_recommendations()

            gaps.append(gap)

        # Calculate overall readiness score
        total_gaps = len(gaps)
        if total_gaps > 0:
            total_gap_score = sum(g.gap_score for g in gaps)
            avg_gap = total_gap_score / total_gaps
            readiness_score = max(0, 100 - avg_gap)
        else:
            readiness_score = 100

        return {
            'gaps': gaps,
            'total_gaps': total_gaps,
            'major_gaps': len([g for g in gaps if g.status in ['major_gap', 'missing']]),
            'readiness_score': readiness_score,
            'is_ready': readiness_score >= 80
        }

    def _generate_ai_recommendations(self):
        """Generate AI-powered recommendations to close skill gap"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider

            ai_provider = get_ai_provider(self.env)

            # Find relevant courses
            courses = self.env['slide.channel'].search([
                ('skill_ids', 'in', [self.skill_id.id])
            ])

            course_data = [{
                'id': c.id,
                'name': c.name,
                'total_slides': c.total_slides,
                'skills': c.skill_ids.mapped('name')
            } for c in courses]

            # Get AI recommendations
            recommendations = ai_provider.recommend_learning(
                employee_skills=[{'skill': self.skill_id.name, 'level': self.current_score}],
                job_requirements=[{'skill': self.skill_id.name, 'level': self.required_score}],
                available_courses=course_data
            )

            if recommendations:
                recommended_course_ids = [r['course_id'] for r in recommendations[:3]]
                self.recommended_courses = [(6, 0, recommended_course_ids)]

                actions = []
                for rec in recommendations[:3]:
                    course = courses.filtered(lambda c: c.id == rec['course_id'])
                    if course:
                        actions.append(f"• Complete '{course.name}' - {rec.get('reason', '')}")

                self.recommended_actions = '\n'.join(actions)

                # Estimate time based on course content
                total_slides = sum(courses.filtered(lambda c: c.id in recommended_course_ids).mapped('total_slides'))
                self.estimated_time_to_close = total_slides * 2  # Assume 2 days per slide

        except Exception as e:
            _logger = logging.getLogger(__name__)
            _logger.warning(f"AI recommendations failed: {e}")

    def action_view_recommended_courses(self):
        """View recommended courses"""
        self.ensure_one()
        return {
            'name': _('Recommended Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'slide.channel',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.recommended_courses.ids)]
        }
