# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import timedelta


class HREmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # BFSI fields exposed on public profile
    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        readonly=True
    )

    banker_type = fields.Selection([
        ('rm', 'Relationship Manager'),
        ('branch_manager', 'Branch Manager'),
        ('regional_manager', 'Regional Manager'),
        ('telesales', 'Telesales Agent'),
        ('field_sales', 'Field Sales Officer'),
        ('loan_officer', 'Loan Officer'),
        ('insurance_advisor', 'Insurance Advisor'),
        ('wealth_manager', 'Wealth Manager'),
        ('banker', 'Banker (General)')
    ], string='Banker Type', readonly=True)

    current_month_rank = fields.Integer(string='Current Month Rank', readonly=True)
    previous_month_rank = fields.Integer(string='Previous Month Rank', readonly=True)
    rank_movement = fields.Integer(string='Rank Movement', readonly=True)
    latest_overall_score = fields.Float(string='Latest Performance Score', readonly=True)
    coaching_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Coaching Priority', readonly=True)
    ai_coaching_enabled = fields.Boolean(string='AI Coaching Enabled', readonly=True)

    # Skills & development fields
    skill_count = fields.Integer(string='Skills', readonly=True)
    avg_skill_proficiency = fields.Float(string='Avg. Proficiency', readonly=True)
    skills_matrix_data = fields.Text(string='Skills Matrix Data', readonly=True)
    active_development_plan_id = fields.Many2one('hr.development.plan', string='Active Plan', readonly=True)
    earned_certification_count = fields.Integer(string='Certifications', readonly=True)
    is_mentor = fields.Boolean(string='Available as Mentor', readonly=True)
    mentoring_capacity = fields.Integer(string='Mentoring Capacity', readonly=True)
    career_path_id = fields.Many2one('hr.career.path', string='Career Path', readonly=True)
    career_goals = fields.Html(string='Career Goals', readonly=True)


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    # ===================
    # BFSI-Specific Fields
    # ===================
    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        ondelete='set null',
        index=True,
        help='Bank branch this employee belongs to'
    )

    banker_type = fields.Selection([
        ('rm', 'Relationship Manager'),
        ('branch_manager', 'Branch Manager'),
        ('regional_manager', 'Regional Manager'),
        ('telesales', 'Telesales Agent'),
        ('field_sales', 'Field Sales Officer'),
        ('loan_officer', 'Loan Officer'),
        ('insurance_advisor', 'Insurance Advisor'),
        ('wealth_manager', 'Wealth Manager'),
        ('banker', 'Banker (General)')
    ], string='Banker Type', index=True)

    # Performance KPIs
    kpi_ids = fields.One2many(
        'bfsi.performance.kpi',
        'employee_id',
        string='Performance KPIs'
    )

    current_month_rank = fields.Integer(
        string='Current Month Rank',
        compute='_compute_performance_rank',
        store=True
    )

    previous_month_rank = fields.Integer(
        string='Previous Month Rank',
        compute='_compute_performance_rank',
        store=True
    )

    rank_movement = fields.Integer(
        string='Rank Movement',
        compute='_compute_rank_movement',
        store=True,
        help='Positive = improved, Negative = dropped'
    )

    latest_overall_score = fields.Float(
        string='Latest Performance Score',
        compute='_compute_latest_performance',
        store=True,
        digits=(5, 2)
    )

    coaching_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Coaching Priority', compute='_compute_latest_performance', store=True)

    # BFSI Coaching metrics
    coaching_sessions_received = fields.Integer(
        string='Sessions Received (MTD)',
        compute='_compute_bfsi_coaching_stats'
    )

    action_plan_ids = fields.One2many(
        'bfsi.action.plan',
        'employee_id',
        string='Action Plans'
    )

    active_action_plan_count = fields.Integer(
        string='Active Action Plans',
        compute='_compute_action_plan_stats'
    )

    action_plan_completion_rate = fields.Float(
        string='Action Plan Completion Rate',
        compute='_compute_action_plan_stats',
        digits=(5, 2)
    )

    # AI Coaching access
    ai_coaching_enabled = fields.Boolean(
        string='AI Coaching Enabled',
        default=True,
        help='Whether this employee has access to 24/7 AI coaching'
    )

    last_ai_coaching_date = fields.Datetime(
        string='Last AI Coaching',
        compute='_compute_last_ai_coaching'
    )

    # Skills
    skill_ids = fields.One2many(
        'hr.employee.skill',
        'employee_id',
        string='Skills'
    )

    skill_count = fields.Integer(
        string='Skills',
        compute='_compute_skill_count',
        store=True
    )

    avg_skill_proficiency = fields.Float(
        string='Avg. Proficiency',
        compute='_compute_avg_proficiency',
        store=True
    )

    # Dummy field for skills matrix widget attachment
    skills_matrix_data = fields.Text(
        string='Skills Matrix Data',
        help='Internal field for skills matrix visualization widget'
    )

    # Development
    development_plan_ids = fields.One2many(
        'hr.development.plan',
        'employee_id',
        string='Development Plans'
    )

    active_development_plan_id = fields.Many2one(
        'hr.development.plan',
        string='Active Plan',
        compute='_compute_active_plan',
        store=True
    )

    learning_enrollment_ids = fields.One2many(
        'hr.learning.enrollment',
        'employee_id',
        string='Learning Enrollments'
    )

    earned_certification_ids = fields.One2many(
        'hr.certification',
        'employee_id',
        string='Earned Certifications'
    )

    earned_certification_count = fields.Integer(
        string='Certifications',
        compute='_compute_certification_count',
        store=True
    )

    # Coaching
    coaching_session_ids = fields.One2many(
        'hr.coaching.session',
        'employee_id',
        string='Coaching Sessions'
    )

    coaching_nudge_ids = fields.One2many(
        'hr.coaching.nudge',
        'employee_id',
        string='Coaching Nudges'
    )

    unread_nudge_count = fields.Integer(
        string='Unread Nudges',
        compute='_compute_unread_nudges'
    )

    # Mentorship
    mentor_relationship_ids = fields.One2many(
        'hr.mentorship',
        'mentor_id',
        string='Mentoring'
    )

    mentee_relationship_ids = fields.One2many(
        'hr.mentorship',
        'mentee_id',
        string='Being Mentored'
    )

    is_mentor = fields.Boolean(
        string='Available as Mentor',
        default=False,
        help='This employee is available to mentor others'
    )

    mentoring_capacity = fields.Integer(
        string='Mentoring Capacity',
        default=3,
        help='Maximum number of mentees'
    )

    # Knowledge
    knowledge_expertise_ids = fields.Many2many(
        'hr.knowledge.node',
        'knowledge_node_expert_rel',
        'employee_id',
        'node_id',
        string='Knowledge Expertise'
    )

    # Career
    career_path_id = fields.Many2one(
        'hr.career.path',
        string='Career Path',
        help='Employee current career path'
    )

    career_goals = fields.Html(string='Career Goals')

    @api.depends('skill_ids')
    def _compute_skill_count(self):
        for employee in self:
            employee.skill_count = len(employee.skill_ids)

    @api.depends('skill_ids.proficiency_score')
    def _compute_avg_proficiency(self):
        for employee in self:
            if employee.skill_ids:
                employee.avg_skill_proficiency = sum(employee.skill_ids.mapped('proficiency_score')) / len(employee.skill_ids)
            else:
                employee.avg_skill_proficiency = 0.0

    @api.depends('earned_certification_ids')
    def _compute_certification_count(self):
        for employee in self:
            employee.earned_certification_count = len(employee.earned_certification_ids.filtered(lambda c: not c.is_expired))

    @api.depends('development_plan_ids.state')
    def _compute_active_plan(self):
        for employee in self:
            active_plan = employee.development_plan_ids.filtered(lambda p: p.state == 'active')
            employee.active_development_plan_id = active_plan[0] if active_plan else False

    def _compute_unread_nudges(self):
        for employee in self:
            employee.unread_nudge_count = len(employee.coaching_nudge_ids.filtered(lambda n: n.state == 'sent'))

    def action_view_skills(self):
        """View employee skills"""
        self.ensure_one()
        return {
            'name': f'Skills - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.skill',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def action_view_development_plan(self):
        """View development plan"""
        self.ensure_one()
        if self.active_development_plan_id:
            return {
                'name': 'Development Plan',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.development.plan',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'res_id': self.active_development_plan_id.id
            }
        else:
            return {
                'name': 'Create Development Plan',
                'type': 'ir.actions.act_window',
                'res_model': 'hr.development.plan',
                'view_mode': 'form',
                'views': [[False, 'form']],
                'context': {'default_employee_id': self.id},
                'target': 'new'
            }

    def action_infer_skills_ai(self):
        """Run AI skills inference"""
        self.ensure_one()

        # Run inference
        inference_engine = self.env['hr.skills.inference.engine']
        results = inference_engine.infer_skills_for_employee(self.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Skills Inference Complete',
                'message': f'Inferred {len(results)} skills from your work history',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_analyze_skill_gaps(self):
        """Analyze skill gaps for current job"""
        self.ensure_one()

        if not self.job_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Job Position',
                    'message': 'Employee must have a job position assigned',
                    'type': 'warning',
                }
            }

        # Run gap analysis
        gap_model = self.env['hr.skill.gap']
        analysis = gap_model.analyze_employee_for_job(self.id, self.job_id.id)

        # Show results
        return {
            'name': 'Skill Gap Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.skill.gap',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', self.id), ('job_id', '=', self.job_id.id)],
            'context': {
                'search_default_major_gaps': 1  # Filter for major gaps
            }
        }

    def action_view_coaching_nudges(self):
        """View coaching nudges"""
        self.ensure_one()
        return {
            'name': 'Coaching Nudges',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.nudge',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def get_skills_matrix_data(self):
        """Get employee skills organized by category for matrix visualization

        Returns:
            dict: Skills data organized by categories
        """
        self.ensure_one()

        # Get all employee skills with their current and target levels
        skills_data = []
        categories_set = set()

        for skill in self.skill_ids:
            # Get current proficiency (1-5 scale)
            current_level = int(skill.proficiency_score / 20) if skill.proficiency_score else 0  # Convert 0-100 to 0-5
            current_level = max(1, min(5, current_level))  # Ensure in 1-5 range

            # Get target level (from development plan objectives or default to one level above current)
            target_level = current_level + 1 if current_level < 5 else 5

            # Check if there's a specific target in development plans
            if self.active_development_plan_id:
                # Look for objectives related to this skill
                for objective in self.active_development_plan_id.objective_ids:
                    if objective.skill_id and objective.skill_id.id == skill.skill_id.id:
                        # Could define target level in objective metadata
                        # For now, use a reasonable default
                        target_level = min(5, current_level + 2)
                        break

            # Get category name
            category_name = skill.skill_id.category_id.name if skill.skill_id.category_id else 'Uncategorized'
            categories_set.add(category_name)

            skills_data.append({
                'id': skill.id,
                'name': skill.skill_id.name,
                'category': category_name,
                'current_level': current_level,
                'target_level': target_level,
                'proficiency_score': skill.proficiency_score,
            })

        return {
            'categories': sorted(list(categories_set)),
            'skills': skills_data
        }

    # ===================
    # BFSI Compute Methods
    # ===================
    @api.depends('kpi_ids', 'kpi_ids.branch_rank', 'kpi_ids.period_date')
    def _compute_performance_rank(self):
        """Compute current and previous month rankings"""
        today = fields.Date.today()
        current_month_start = today.replace(day=1)
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        for employee in self:
            # Current month rank - get latest KPI
            current_kpi = self.env['bfsi.performance.kpi'].search([
                ('employee_id', '=', employee.id),
                ('period_date', '>=', current_month_start)
            ], order='period_date desc', limit=1)

            employee.current_month_rank = current_kpi.branch_rank if current_kpi else 0

            # Previous month rank
            prev_kpi = self.env['bfsi.performance.kpi'].search([
                ('employee_id', '=', employee.id),
                ('period_date', '>=', previous_month_start),
                ('period_date', '<', current_month_start)
            ], order='period_date desc', limit=1)

            employee.previous_month_rank = prev_kpi.branch_rank if prev_kpi else 0

    @api.depends('current_month_rank', 'previous_month_rank')
    def _compute_rank_movement(self):
        """Compute rank movement (positive = improved)"""
        for employee in self:
            if employee.previous_month_rank and employee.current_month_rank:
                # Lower rank number is better, so improvement is prev - current
                employee.rank_movement = employee.previous_month_rank - employee.current_month_rank
            else:
                employee.rank_movement = 0

    @api.depends('kpi_ids', 'kpi_ids.overall_score', 'kpi_ids.coaching_priority')
    def _compute_latest_performance(self):
        """Get latest performance score and coaching priority"""
        for employee in self:
            latest_kpi = self.env['bfsi.performance.kpi'].search([
                ('employee_id', '=', employee.id)
            ], order='period_date desc', limit=1)

            if latest_kpi:
                employee.latest_overall_score = latest_kpi.overall_score
                employee.coaching_priority = latest_kpi.coaching_priority
            else:
                employee.latest_overall_score = 0
                employee.coaching_priority = 'low'

    def _compute_bfsi_coaching_stats(self):
        """Compute BFSI-specific coaching statistics"""
        today = fields.Date.today()
        month_start = today.replace(day=1)

        for employee in self:
            sessions = self.env['hr.coaching.session'].search([
                ('employee_id', '=', employee.id),
                ('session_date', '>=', month_start),
                ('state', 'in', ['in_progress', 'completed'])
            ])
            employee.coaching_sessions_received = len(sessions)

    def _compute_action_plan_stats(self):
        """Compute action plan statistics"""
        for employee in self:
            active_plans = employee.action_plan_ids.filtered(
                lambda p: p.state in ['committed', 'in_progress']
            )
            employee.active_action_plan_count = len(active_plans)

            completed = len(employee.action_plan_ids.filtered(lambda p: p.state == 'completed'))
            total = len(employee.action_plan_ids.filtered(
                lambda p: p.state in ['committed', 'in_progress', 'completed']
            ))
            employee.action_plan_completion_rate = (completed / total * 100) if total > 0 else 0

    def _compute_last_ai_coaching(self):
        """Get last AI coaching session date"""
        for employee in self:
            last_session = self.env['hr.coaching.session'].search([
                ('employee_id', '=', employee.id),
                ('session_type', 'in', ['ai', 'hybrid'])
            ], order='session_date desc', limit=1)

            employee.last_ai_coaching_date = last_session.session_date if last_session else False

    # ===================
    # BFSI Actions
    # ===================
    def action_view_performance(self):
        """View performance KPIs"""
        self.ensure_one()
        return {
            'name': _('Performance KPIs - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'bfsi.performance.kpi',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def action_view_action_plans(self):
        """View action plans"""
        self.ensure_one()
        return {
            'name': _('Action Plans - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'bfsi.action.plan',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }

    def action_start_ai_coaching(self):
        """Start a new AI coaching session"""
        self.ensure_one()

        # Create new coaching session
        session = self.env['hr.coaching.session'].create({
            'name': _('AI Coaching - %s') % self.name,
            'employee_id': self.id,
            'session_type': 'ai',
            'topic': 'performance',
        })

        return {
            'name': _('AI Coaching Session'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.coaching.session',
            'res_id': session.id,
            'view_mode': 'form',
        }

    def action_generate_coaching_strategy(self):
        """Generate AI coaching strategy for this banker"""
        self.ensure_one()

        # Create new strategy
        strategy = self.env['bfsi.coaching.strategy'].create({
            'banker_id': self.id,
            'manager_id': self.branch_id.manager_id.id if self.branch_id else False,
        })

        # Generate the strategy
        strategy.action_generate_strategy()

        return {
            'name': _('Coaching Strategy'),
            'type': 'ir.actions.act_window',
            'res_model': 'bfsi.coaching.strategy',
            'res_id': strategy.id,
            'view_mode': 'form',
        }

    def get_performance_context_for_ai(self):
        """Get comprehensive performance context for AI coaching"""
        self.ensure_one()

        # Get latest KPI
        latest_kpi = self.env['bfsi.performance.kpi'].search([
            ('employee_id', '=', self.id)
        ], order='period_date desc', limit=1)

        # Get target
        target = self.env['bfsi.kpi.target'].get_target_for_employee(self.id)

        # Get active action plans
        active_plans = self.action_plan_ids.filtered(
            lambda p: p.state in ['committed', 'in_progress']
        )

        context = {
            'employee_name': self.name,
            'role': self.job_id.name if self.job_id else self.banker_type or 'Banker',
            'branch': self.branch_id.name if self.branch_id else 'N/A',
            'current_rank': self.current_month_rank,
            'rank_movement': self.rank_movement,
            'latest_score': self.latest_overall_score,
            'coaching_priority': self.coaching_priority,
        }

        if latest_kpi:
            context['kpi_summary'] = latest_kpi.get_kpi_summary_for_ai()

        if target:
            context['target_summary'] = target.get_target_summary_for_ai()

        if active_plans:
            context['active_plans'] = [p.get_plan_summary_for_ai() for p in active_plans[:2]]

        # If this employee is a branch manager, include team data
        if self.branch_id and self.banker_type in ('branch_manager', 'regional_manager'):
            team_members = self.env['hr.employee'].search([
                ('branch_id', '=', self.branch_id.id),
                ('id', '!=', self.id),
                ('banker_type', 'not in', ['branch_manager', 'regional_manager']),
            ], order='current_month_rank asc')
            team_data = []
            for member in team_members:
                member_info = {
                    'name': member.name,
                    'role': member.job_id.name if member.job_id else member.banker_type or 'Banker',
                    'rank': member.current_month_rank,
                    'score': round(member.latest_overall_score, 1),
                    'rank_movement': member.rank_movement,
                    'coaching_priority': member.coaching_priority or 'low',
                    'sessions_received': member.coaching_sessions_received,
                    'active_plans': member.active_action_plan_count,
                }
                team_data.append(member_info)
            context['team_members'] = team_data
            context['is_manager'] = True

        return context

    def action_ai_coach_chat(self, message, context=None):
        """Handle AI coach chat message from persistent panel

        Args:
            message: User's chat message
            context: Additional context (kpi_data, action_plans, session_type, etc.)

        Returns:
            dict: {response, suggested_actions, learning_content}
        """
        self.ensure_one()

        # Use sudo() to bypass public profile field restrictions
        # so bankers can read their own performance data internally
        emp_sudo = self.sudo()

        # Get employee performance context
        perf_context = emp_sudo.get_performance_context_for_ai()

        # Merge with provided context
        full_context = {**perf_context, **(context or {})}

        # Determine chat intent
        session_type = context.get('session_type', 'general') if context else 'general'
        is_manager = context.get('is_manager', False) if context else False

        # Build AI prompt based on context and intent
        system_prompt = self._build_ai_coach_system_prompt(full_context, session_type, is_manager)
        user_prompt = self._build_ai_coach_user_prompt(message, full_context, session_type)

        # Get AI provider via factory
        try:
            from ..ai_providers.provider_factory import AIProviderFactory
            provider = AIProviderFactory.get_provider(env=self.env)
        except Exception as e:
            _logger = logging.getLogger(__name__)
            _logger.error("Failed to get AI provider: %s", str(e))
            provider = None

        if not provider:
            return {
                'response': 'AI coaching is temporarily unavailable. Please try again later or contact your manager.',
                'suggested_actions': [],
                'learning_content': None
            }

        try:
            # Build combined prompt
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            # Call AI provider
            ai_text = provider.generate_text(full_prompt, max_tokens=800, temperature=0.7)

            # Try to parse as JSON for structured response
            try:
                import json
                ai_response = json.loads(ai_text)
                return {
                    'response': ai_response.get('response', ai_text),
                    'suggested_actions': ai_response.get('suggested_actions', []),
                    'learning_content': ai_response.get('learning_content', None),
                    'follow_up_questions': ai_response.get('follow_up_questions', [])
                }
            except (json.JSONDecodeError, TypeError):
                # Plain text response
                return {
                    'response': ai_text,
                    'suggested_actions': self._get_fallback_actions(session_type),
                    'learning_content': None,
                    'follow_up_questions': []
                }

        except Exception as e:
            # Log error and return fallback response
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("AI Coach chat error: %s", str(e))

            return {
                'response': self._get_fallback_coaching_response(message, full_context, session_type),
                'suggested_actions': self._get_fallback_actions(session_type),
                'learning_content': None
            }

    def _build_ai_coach_system_prompt(self, context, session_type, is_manager):
        """Build system prompt for AI coach based on context"""
        base_prompt = """You are an AI Performance Coach for banking professionals. Your role is to:
1. Provide personalized coaching based on the banker's KPIs and performance data
2. Be encouraging but honest about areas needing improvement
3. Give specific, actionable advice based on banking industry best practices
4. Help with sales techniques, customer handling, and objection management
5. Support action plan tracking and progress monitoring

"""

        if is_manager:
            base_prompt += """You are assisting a Branch Manager. Focus on:
- Team performance analysis and coaching strategies
- How to effectively coach individual bankers
- Identifying patterns in team performance
- Preparing for coaching conversations

"""

        if session_type == 'kpi_review':
            base_prompt += """Focus on explaining the KPI metrics and what they mean, highlighting strengths and areas for improvement.
"""
        elif session_type == 'action_plan':
            base_prompt += """Focus on reviewing action plan progress, celebrating wins, and problem-solving blockers.
"""
        elif session_type == 'coaching':
            base_prompt += """Focus on providing specific coaching advice and skill-building recommendations.
"""

        return base_prompt

    def _build_ai_coach_user_prompt(self, message, context, session_type):
        """Build user prompt with context"""
        prompt = f"""User: {context.get('employee_name', 'Banker')}
Role: {context.get('role', 'Banking Professional')}
Branch: {context.get('branch', 'N/A')}
Current Performance Score: {context.get('latest_score', 'N/A')}%
Rank: #{context.get('current_rank', 'N/A')} (Movement: {context.get('rank_movement', 0)})
Coaching Priority: {context.get('coaching_priority', 'N/A')}

"""
        if 'kpi_summary' in context:
            prompt += f"Recent KPI Summary:\n{context['kpi_summary']}\n\n"

        if 'active_plans' in context and context['active_plans']:
            prompt += "Active Action Plans:\n"
            for plan in context['active_plans']:
                prompt += f"- {plan}\n"
            prompt += "\n"

        # Include team data for managers
        if context.get('team_members'):
            prompt += "TEAM MEMBERS (you manage these bankers):\n"
            for member in context['team_members']:
                priority_flag = '🔴' if member['coaching_priority'] == 'critical' else '🟡' if member['coaching_priority'] == 'high' else '🟢'
                prompt += f"  - {member['name']} ({member['role']}): Rank #{member['rank']}, Score {member['score']}%, Movement {member['rank_movement']:+d}, Priority: {priority_flag}{member['coaching_priority']}, Sessions: {member['sessions_received']}, Active Plans: {member['active_plans']}\n"
            prompt += "\n"

        prompt += f"User Message: {message}\n\nIMPORTANT: Answer using the ACTUAL data provided above. Reference specific names, scores, and metrics when answering questions about team or performance."

        return prompt

    def _get_fallback_coaching_response(self, message, context, session_type):
        """Generate a helpful fallback response when AI is unavailable"""
        score = context.get('latest_score', 0)
        name = context.get('employee_name', 'there')

        if session_type == 'kpi_review':
            if score >= 80:
                return f"Hi {name}! Your performance score of {score}% is excellent. Keep focusing on maintaining your strong results while continuing to develop your skills."
            elif score >= 60:
                return f"Hi {name}! Your performance score of {score}% shows good progress. Focus on your top improvement areas and consider reviewing your action plan for specific guidance."
            else:
                return f"Hi {name}! I see your performance score is {score}%. Let's work together on a focused improvement plan. Start by reviewing your daily activities and identifying quick wins."

        elif session_type == 'action_plan':
            return f"Hi {name}! To review your action plan progress, please check your Action Plans section in the dashboard. Remember to update your progress regularly and reach out to your manager if you're facing any blockers."

        else:
            return f"Hi {name}! I'm here to help with your performance coaching. While I'm having some technical difficulties, you can review your KPIs in the dashboard, check your action plans, or schedule time with your manager for personalized guidance."

    def _get_fallback_actions(self, session_type):
        """Get fallback suggested actions"""
        if session_type == 'kpi_review':
            return [
                {'type': 'check_kpis', 'label': 'View Full KPI Dashboard'},
                {'type': 'action_plan', 'label': 'Review Action Plan'}
            ]
        elif session_type == 'action_plan':
            return [
                {'type': 'log_activity', 'label': 'Log Progress'},
                {'type': 'get_coaching', 'label': 'Get Coaching Tips'}
            ]
        else:
            return [
                {'type': 'check_kpis', 'label': 'Check My KPIs'},
                {'type': 'action_plan', 'label': 'View Action Plan'}
            ]

    @api.model
    def get_dashboard_context(self):
        """Get dashboard context for the current user.
        
        Uses sudo() to bypass hr.employee public profile field restrictions
        so bankers can read their own performance data.
        
        Returns dict with employee data, role detection, and for managers: team data.
        """
        user_id = self.env.uid
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', user_id)], limit=1
        )
        
        if not employee:
            return {'error': 'No employee record found'}
        
        result = {
            'id': employee.id,
            'name': employee.name,
            'branch_id': employee.branch_id.id if employee.branch_id else False,
            'branch_name': employee.branch_id.name if employee.branch_id else '',
            'banker_type': employee.banker_type or '',
            'current_month_rank': employee.current_month_rank,
            'previous_month_rank': employee.previous_month_rank,
            'rank_movement': employee.rank_movement,
            'latest_overall_score': employee.latest_overall_score,
            'coaching_priority': employee.coaching_priority or 'low',
            'coaching_sessions_received': employee.coaching_sessions_received,
            'active_action_plan_count': employee.active_action_plan_count,
            'action_plan_completion_rate': employee.action_plan_completion_rate,
        }
        
        # Detect role
        manager_types = ['branch_manager', 'regional_manager']
        is_manager = employee.banker_type in manager_types
        result['is_manager'] = is_manager
        
        if is_manager and employee.branch_id:
            # Load team data for managers
            team = self.env['hr.employee'].sudo().search([
                ('branch_id', '=', employee.branch_id.id),
                ('banker_type', 'not in', manager_types),
                ('id', '!=', employee.id),
            ], order='current_month_rank asc')
            
            team_data = []
            for member in team:
                team_data.append({
                    'id': member.id,
                    'name': member.name,
                    'job_id': [member.job_id.id, member.job_id.name] if member.job_id else False,
                    'banker_type': member.banker_type or '',
                    'current_month_rank': member.current_month_rank,
                    'previous_month_rank': member.previous_month_rank,
                    'rank_movement': member.rank_movement,
                    'latest_overall_score': member.latest_overall_score,
                    'coaching_priority': member.coaching_priority or 'low',
                    'coaching_sessions_received': member.coaching_sessions_received,
                    'active_action_plan_count': member.active_action_plan_count,
                    'action_plan_completion_rate': member.action_plan_completion_rate,
                })
            result['team_members'] = team_data
        
        return result
