# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import json


class BFSIPerformanceKPI(models.Model):
    _name = 'bfsi.performance.kpi'
    _description = 'BFSI Performance KPI'
    _inherit = ['mail.thread']
    _order = 'period_date desc, employee_id'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True
    )

    @api.depends('employee_id', 'period_date')
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.period_date:
                rec.name = f"{rec.employee_id.name} - {rec.period_date.strftime('%b %d')}"
            elif rec.employee_id:
                rec.name = rec.employee_id.name
            else:
                rec.name = f"KPI #{rec.id or 'New'}"

    employee_id = fields.Many2one(
        'hr.employee',
        string='Banker',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    branch_id = fields.Many2one(
        'bfsi.branch',
        string='Branch',
        related='employee_id.branch_id',
        store=True,
        index=True
    )

    period_date = fields.Date(
        string='Date',
        required=True,
        index=True,
        default=fields.Date.today,
        tracking=True
    )

    period_type = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ], string='Period Type', default='daily', required=True)

    # ===================
    # INPUT KPIs
    # ===================
    dials_per_hour = fields.Float(
        string='Dials/Hour',
        digits=(5, 2),
        help='Number of outbound call dials per hour'
    )

    total_dials = fields.Integer(
        string='Total Dials',
        help='Total number of dials made today'
    )

    connects = fields.Integer(
        string='Connects',
        help='Number of successful connections'
    )

    meetings_scheduled = fields.Integer(
        string='Meetings Scheduled',
        help='Number of meetings scheduled'
    )

    meetings_conducted = fields.Integer(
        string='Meetings Conducted',
        help='Number of meetings actually held'
    )

    calls_made = fields.Integer(
        string='Calls Made',
        help='Total calls made'
    )

    hours_worked = fields.Float(
        string='Hours Worked',
        digits=(4, 2),
        default=8.0
    )

    # ===================
    # BEHAVIOR KPIs
    # ===================
    script_adherence = fields.Float(
        string='Script Adherence %',
        digits=(5, 2),
        help='Percentage adherence to call scripts (0-100)'
    )

    objection_handling_score = fields.Float(
        string='Objection Handling Score',
        digits=(5, 2),
        help='Score for handling customer objections (0-100)'
    )

    need_analysis_quality = fields.Float(
        string='Need Analysis Quality',
        digits=(5, 2),
        help='Quality score for customer need analysis (0-100)'
    )

    product_knowledge_score = fields.Float(
        string='Product Knowledge',
        digits=(5, 2),
        help='Score for product knowledge demonstration (0-100)'
    )

    compliance_score = fields.Float(
        string='Compliance Score',
        digits=(5, 2),
        help='Regulatory compliance adherence score (0-100)'
    )

    customer_satisfaction = fields.Float(
        string='Customer Satisfaction',
        digits=(5, 2),
        help='Customer satisfaction rating (0-100)'
    )

    # ===================
    # OUTPUT KPIs
    # ===================
    conversions = fields.Integer(
        string='Conversions',
        help='Number of successful conversions/sales'
    )

    products_sold = fields.Integer(
        string='Products Sold',
        help='Number of products sold'
    )

    appointments_set = fields.Integer(
        string='Appointments Set',
        help='Number of appointments set for future'
    )

    leads_generated = fields.Integer(
        string='Leads Generated',
        help='Number of new leads generated'
    )

    proposals_submitted = fields.Integer(
        string='Proposals Submitted',
        help='Number of proposals submitted to clients'
    )

    # ===================
    # OUTCOME KPIs
    # ===================
    revenue = fields.Monetary(
        string='Revenue',
        currency_field='currency_id',
        tracking=True
    )

    commission = fields.Monetary(
        string='Commission',
        currency_field='currency_id'
    )

    aum = fields.Monetary(
        string='Assets Under Management',
        currency_field='currency_id',
        help='Total AUM for wealth management'
    )

    loan_amount = fields.Monetary(
        string='Loan Amount',
        currency_field='currency_id',
        help='Total loan amount disbursed'
    )

    premium_collected = fields.Monetary(
        string='Premium Collected',
        currency_field='currency_id',
        help='Insurance premium collected'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    # ===================
    # COMPUTED METRICS
    # ===================
    connect_rate = fields.Float(
        string='Connect Rate %',
        compute='_compute_rates',
        store=True,
        digits=(5, 2)
    )

    conversion_rate = fields.Float(
        string='Conversion Rate %',
        compute='_compute_rates',
        store=True,
        digits=(5, 2)
    )

    overall_score = fields.Float(
        string='Overall Score',
        compute='_compute_overall_score',
        store=True,
        digits=(5, 2),
        help='Weighted average of all KPI categories (0-100)'
    )

    deviation_score = fields.Float(
        string='Deviation from Target',
        compute='_compute_deviation',
        store=True,
        digits=(5, 2),
        help='Percentage deviation from target (negative = below target)'
    )

    coaching_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Coaching Priority', compute='_compute_coaching_priority', store=True)

    # Ranking
    branch_rank = fields.Integer(
        string='Branch Rank',
        compute='_compute_rankings',
        store=True,
        help='Rank within branch based on overall score'
    )

    rank_movement = fields.Integer(
        string='Rank Movement',
        compute='_compute_rank_movement',
        store=True,
        help='Change in rank vs previous period (positive = improved)'
    )

    # AI Analysis
    ai_analysis = fields.Text(
        string='AI Analysis',
        help='AI-generated analysis of performance (JSON)'
    )

    ai_recommendations = fields.Text(
        string='AI Recommendations',
        help='AI-generated improvement recommendations'
    )

    # Strategic Selection - Session count for this employee
    coaching_session_count = fields.Integer(
        string='Sessions',
        compute='_compute_coaching_session_count',
        help='Number of coaching sessions for this employee'
    )

    def _compute_coaching_session_count(self):
        Session = self.env['hr.coaching.session']
        for rec in self:
            rec.coaching_session_count = Session.search_count([
                ('employee_id', '=', rec.employee_id.id),
            ])

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('employee_date_unique', 'unique(employee_id, period_date, period_type)',
         'Only one KPI record per employee per date per period type!')
    ]

    @api.depends('total_dials', 'connects', 'meetings_conducted', 'conversions')
    def _compute_rates(self):
        for kpi in self:
            kpi.connect_rate = (kpi.connects / kpi.total_dials * 100) if kpi.total_dials > 0 else 0
            kpi.conversion_rate = (kpi.conversions / kpi.meetings_conducted * 100) if kpi.meetings_conducted > 0 else 0

    @api.depends(
        'script_adherence', 'objection_handling_score', 'need_analysis_quality',
        'product_knowledge_score', 'compliance_score', 'customer_satisfaction',
        'conversion_rate', 'connect_rate'
    )
    def _compute_overall_score(self):
        """Calculate weighted overall score from KPI components"""
        for kpi in self:
            # Weighted scoring:
            # Behavior KPIs: 40% (most coachable)
            # Output metrics: 40% (results-oriented)
            # Input metrics: 20% (activity-based)

            behavior_score = (
                (kpi.script_adherence or 0) * 0.15 +
                (kpi.objection_handling_score or 0) * 0.10 +
                (kpi.need_analysis_quality or 0) * 0.10 +
                (kpi.product_knowledge_score or 0) * 0.05
            )

            output_score = (
                (kpi.conversion_rate or 0) * 0.25 +
                (kpi.customer_satisfaction or 0) * 0.15
            )

            input_score = (
                (kpi.connect_rate or 0) * 0.20
            )

            kpi.overall_score = behavior_score + output_score + input_score

    @api.depends('employee_id', 'period_date')
    def _compute_deviation(self):
        """Calculate deviation from target"""
        for kpi in self:
            target = self.env['bfsi.kpi.target'].get_target_for_employee(
                kpi.employee_id.id,
                kpi.period_date
            )
            if target and target.target_overall_score > 0:
                kpi.deviation_score = ((kpi.overall_score - target.target_overall_score) /
                                       target.target_overall_score * 100)
            else:
                kpi.deviation_score = 0

    @api.depends('deviation_score', 'overall_score')
    def _compute_coaching_priority(self):
        """Determine coaching priority based on deviation and overall score"""
        for kpi in self:
            if kpi.deviation_score <= -30 or kpi.overall_score < 40:
                kpi.coaching_priority = 'critical'
            elif kpi.deviation_score <= -20 or kpi.overall_score < 55:
                kpi.coaching_priority = 'high'
            elif kpi.deviation_score <= -10 or kpi.overall_score < 70:
                kpi.coaching_priority = 'medium'
            else:
                kpi.coaching_priority = 'low'

    @api.depends('overall_score', 'branch_id', 'period_date')
    def _compute_rankings(self):
        """Calculate rank within branch"""
        # Group KPIs by branch and date
        branch_date_groups = {}
        for kpi in self:
            key = (kpi.branch_id.id, kpi.period_date)
            if key not in branch_date_groups:
                branch_date_groups[key] = []
            branch_date_groups[key].append(kpi)

        for (branch_id, period_date), kpis in branch_date_groups.items():
            # Sort by overall_score descending
            sorted_kpis = sorted(kpis, key=lambda k: k.overall_score or 0, reverse=True)
            for rank, kpi in enumerate(sorted_kpis, 1):
                kpi.branch_rank = rank

    @api.depends('branch_rank', 'employee_id', 'period_date')
    def _compute_rank_movement(self):
        """Calculate rank movement vs previous period"""
        for kpi in self:
            # Find previous period KPI
            if kpi.period_type == 'daily':
                prev_date = kpi.period_date - timedelta(days=1)
            elif kpi.period_type == 'weekly':
                prev_date = kpi.period_date - timedelta(weeks=1)
            else:
                # Monthly - go back ~30 days
                prev_date = kpi.period_date - timedelta(days=30)

            prev_kpi = self.search([
                ('employee_id', '=', kpi.employee_id.id),
                ('period_type', '=', kpi.period_type),
                ('period_date', '<', kpi.period_date)
            ], order='period_date desc', limit=1)

            if prev_kpi and prev_kpi.branch_rank:
                # Positive movement = improved (lower rank number is better)
                kpi.rank_movement = prev_kpi.branch_rank - kpi.branch_rank
            else:
                kpi.rank_movement = 0

    def get_kpi_summary_for_ai(self):
        """Generate a text summary of KPIs for AI context"""
        self.ensure_one()
        summary = f"""
Performance Summary for {self.employee_id.name} on {self.period_date}:

INPUT METRICS:
- Dials/Hour: {self.dials_per_hour or 0:.1f}
- Total Dials: {self.total_dials or 0}
- Connects: {self.connects or 0} (Connect Rate: {self.connect_rate:.1f}%)
- Meetings Conducted: {self.meetings_conducted or 0}

BEHAVIOR METRICS:
- Script Adherence: {self.script_adherence or 0:.1f}%
- Objection Handling: {self.objection_handling_score or 0:.1f}/100
- Need Analysis Quality: {self.need_analysis_quality or 0:.1f}/100
- Product Knowledge: {self.product_knowledge_score or 0:.1f}/100

OUTPUT METRICS:
- Conversions: {self.conversions or 0} (Rate: {self.conversion_rate:.1f}%)
- Products Sold: {self.products_sold or 0}
- Revenue: {self.currency_id.symbol}{self.revenue or 0:,.2f}

OVERALL:
- Overall Score: {self.overall_score:.1f}/100
- Branch Rank: #{self.branch_rank or 'N/A'}
- Rank Movement: {'+' if (self.rank_movement or 0) > 0 else ''}{self.rank_movement or 0}
- Coaching Priority: {self.coaching_priority or 'N/A'}
- Target Deviation: {self.deviation_score:+.1f}%
"""
        return summary

    @api.model
    def get_performance_trend(self, employee_id, days=30):
        """Get performance trend for an employee over specified days"""
        end_date = fields.Date.today()
        start_date = end_date - timedelta(days=days)

        kpis = self.search([
            ('employee_id', '=', employee_id),
            ('period_date', '>=', start_date),
            ('period_date', '<=', end_date),
            ('period_type', '=', 'daily')
        ], order='period_date asc')

        return [{
            'date': kpi.period_date.isoformat(),
            'overall_score': kpi.overall_score,
            'revenue': kpi.revenue,
            'conversions': kpi.conversions,
            'coaching_priority': kpi.coaching_priority,
            'rank': kpi.branch_rank
        } for kpi in kpis]

    @api.model
    def get_branch_rankings(self, branch_id, period_date=None):
        """Get current rankings for a branch"""
        if not period_date:
            period_date = fields.Date.today()

        # Get most recent KPIs for each banker in the branch
        branch = self.env['bfsi.branch'].browse(branch_id)
        rankings = []

        for banker in branch.banker_ids:
            kpi = self.search([
                ('employee_id', '=', banker.id),
                ('period_date', '<=', period_date)
            ], order='period_date desc', limit=1)

            if kpi:
                rankings.append({
                    'employee_id': banker.id,
                    'employee_name': banker.name,
                    'overall_score': kpi.overall_score,
                    'rank': kpi.branch_rank,
                    'rank_movement': kpi.rank_movement,
                    'coaching_priority': kpi.coaching_priority,
                    'revenue': kpi.revenue,
                })

        # Sort by overall_score descending
        rankings.sort(key=lambda x: x['overall_score'] or 0, reverse=True)

        # Assign current ranks
        for i, r in enumerate(rankings, 1):
            r['current_rank'] = i

        return rankings

    def action_generate_ai_analysis(self):
        """Generate AI analysis for this KPI record"""
        self.ensure_one()
        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get target for context
            target = self.env['bfsi.kpi.target'].get_target_for_employee(
                self.employee_id.id,
                self.period_date
            )

            kpi_summary = self.get_kpi_summary_for_ai()
            target_summary = target.get_target_summary_for_ai() if target else "No targets set"

            prompt = f"""Analyze the following banker's performance KPIs and provide insights:

{kpi_summary}

TARGETS:
{target_summary}

Provide analysis in the following JSON format:
{{
    "strengths": ["List of 2-3 strength areas"],
    "improvement_areas": ["List of 2-3 areas needing improvement"],
    "root_causes": ["Potential root causes for any gaps"],
    "quick_wins": ["1-2 quick wins for immediate improvement"],
    "coaching_focus": "Primary area to focus coaching on"
}}
"""
            response = ai_provider.generate_text(prompt, max_tokens=800, temperature=0.5)

            # Parse and format the response
            formatted = self._format_ai_analysis(response)
            self.ai_analysis = formatted

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Analysis Generated'),
                    'message': _('AI analysis has been generated successfully.'),
                    'type': 'success',
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Analysis Failed'),
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def _format_ai_analysis(self, response):
        """Format AI analysis JSON into clean readable text"""
        import re
        try:
            # Try to parse as JSON
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            # Try to extract JSON from response text
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    return response  # Return as-is if no JSON found
            except (json.JSONDecodeError, TypeError):
                return response

        sections = []

        # Strengths
        if data.get('strengths'):
            lines = ['✅ STRENGTHS']
            for item in data['strengths']:
                lines.append(f'  • {item}')
            sections.append('\n'.join(lines))

        # Improvement Areas
        if data.get('improvement_areas'):
            lines = ['⚠️ IMPROVEMENT AREAS']
            for item in data['improvement_areas']:
                lines.append(f'  • {item}')
            sections.append('\n'.join(lines))

        # Root Causes
        if data.get('root_causes'):
            lines = ['🔍 ROOT CAUSES']
            for item in data['root_causes']:
                lines.append(f'  • {item}')
            sections.append('\n'.join(lines))

        # Quick Wins
        if data.get('quick_wins'):
            lines = ['🚀 QUICK WINS']
            for i, item in enumerate(data['quick_wins'], 1):
                lines.append(f'  {i}. {item}')
            sections.append('\n'.join(lines))

        # Coaching Focus
        if data.get('coaching_focus'):
            sections.append(f'🎯 COACHING FOCUS\n  {data["coaching_focus"]}')

        return '\n\n'.join(sections) if sections else response
