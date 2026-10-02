# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BFSIRegion(models.Model):
    _name = 'bfsi.region'
    _description = 'BFSI Region'
    _order = 'sequence, name'

    name = fields.Char(string='Region Name', required=True, translate=True)
    code = fields.Char(string='Region Code', size=10)
    sequence = fields.Integer(string='Sequence', default=10)

    regional_manager_id = fields.Many2one(
        'hr.employee',
        string='Regional Manager',
        domain="[('banker_type', '=', 'regional_manager')]"
    )

    branch_ids = fields.One2many(
        'bfsi.branch',
        'region_id',
        string='Branches'
    )

    branch_count = fields.Integer(
        string='Number of Branches',
        compute='_compute_branch_count',
        store=True
    )

    active = fields.Boolean(default=True)

    @api.depends('branch_ids')
    def _compute_branch_count(self):
        for region in self:
            region.branch_count = len(region.branch_ids)


class BFSIBranch(models.Model):
    _name = 'bfsi.branch'
    _description = 'Bank Branch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Branch Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Branch Code', size=20, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)

    region_id = fields.Many2one(
        'bfsi.region',
        string='Region',
        ondelete='restrict',
        tracking=True
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Branch Manager',
        domain="[('banker_type', '=', 'branch_manager')]",
        tracking=True
    )

    banker_ids = fields.One2many(
        'hr.employee',
        'branch_id',
        string='Bankers',
        domain="[('banker_type', 'in', ['rm', 'banker'])]"
    )

    # Location
    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='ZIP Code')
    phone = fields.Char(string='Phone')

    # Computed Metrics
    banker_count = fields.Integer(
        string='Number of Bankers',
        compute='_compute_branch_metrics',
        store=True
    )

    avg_performance_score = fields.Float(
        string='Avg Performance Score',
        compute='_compute_branch_metrics',
        store=True,
        digits=(5, 2),
        help='Average performance score across all bankers in branch'
    )

    total_revenue = fields.Monetary(
        string='Total Revenue (MTD)',
        compute='_compute_branch_metrics',
        store=True,
        currency_field='currency_id'
    )

    bankers_needing_coaching = fields.Integer(
        string='Bankers Needing Coaching',
        compute='_compute_coaching_needs',
        store=True,
        help='Number of bankers with coaching_priority = high or critical'
    )

    coaching_sessions_this_month = fields.Integer(
        string='Sessions This Month',
        compute='_compute_coaching_stats'
    )

    bankers_coached_this_month = fields.Integer(
        string='Bankers Coached This Month',
        compute='_compute_coaching_stats'
    )

    action_plan_completion_rate = fields.Float(
        string='Action Plan Completion Rate',
        compute='_compute_coaching_stats',
        digits=(5, 2)
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Branch code must be unique!'),
    ]

    @api.depends('banker_ids', 'banker_ids.branch_id')
    def _compute_branch_metrics(self):
        """Compute branch-level metrics from banker KPIs"""
        for branch in self:
            bankers = branch.banker_ids.filtered(lambda e: e.active)
            branch.banker_count = len(bankers)

            # Calculate average performance score from latest KPIs
            if bankers:
                kpi_model = self.env['bfsi.performance.kpi']
                today = fields.Date.today()

                # Get latest KPI for each banker
                total_score = 0
                total_revenue = 0
                banker_with_kpi = 0

                for banker in bankers:
                    latest_kpi = kpi_model.search([
                        ('employee_id', '=', banker.id),
                        ('period_date', '<=', today)
                    ], order='period_date desc', limit=1)

                    if latest_kpi:
                        total_score += latest_kpi.overall_score or 0
                        total_revenue += latest_kpi.revenue or 0
                        banker_with_kpi += 1

                branch.avg_performance_score = total_score / banker_with_kpi if banker_with_kpi > 0 else 0
                branch.total_revenue = total_revenue
            else:
                branch.avg_performance_score = 0
                branch.total_revenue = 0

    @api.depends('banker_ids')
    def _compute_coaching_needs(self):
        """Count bankers needing coaching based on coaching_priority"""
        for branch in self:
            # Check KPIs for coaching priority
            kpi_model = self.env['bfsi.performance.kpi']
            today = fields.Date.today()

            need_coaching_count = 0
            for banker in branch.banker_ids.filtered(lambda e: e.active):
                latest_kpi = kpi_model.search([
                    ('employee_id', '=', banker.id),
                    ('period_date', '<=', today)
                ], order='period_date desc', limit=1)

                if latest_kpi and latest_kpi.coaching_priority in ['high', 'critical']:
                    need_coaching_count += 1

            branch.bankers_needing_coaching = need_coaching_count

    def _compute_coaching_stats(self):
        """Compute coaching statistics for the branch"""
        for branch in self:
            # Get date range for current month
            today = fields.Date.today()
            month_start = today.replace(day=1)

            # Count sessions this month
            session_model = self.env['hr.coaching.session']
            sessions = session_model.search([
                ('employee_id', 'in', branch.banker_ids.ids),
                ('session_date', '>=', month_start),
                ('state', 'in', ['in_progress', 'completed'])
            ])

            branch.coaching_sessions_this_month = len(sessions)
            branch.bankers_coached_this_month = len(sessions.mapped('employee_id'))

            # Calculate action plan completion rate
            action_plan_model = self.env['bfsi.action.plan']
            completed_plans = action_plan_model.search_count([
                ('employee_id', 'in', branch.banker_ids.ids),
                ('state', '=', 'completed')
            ])
            total_plans = action_plan_model.search_count([
                ('employee_id', 'in', branch.banker_ids.ids),
                ('state', 'in', ['committed', 'in_progress', 'completed'])
            ])

            branch.action_plan_completion_rate = (completed_plans / total_plans * 100) if total_plans > 0 else 0

    def action_view_bankers(self):
        """Open list of bankers in this branch"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Branch Bankers'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {'default_branch_id': self.id},
        }

    def action_view_performance(self):
        """Open performance dashboard for this branch"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Branch Performance'),
            'res_model': 'bfsi.performance.kpi',
            'view_mode': 'list,form',
            'domain': [('employee_id', 'in', self.banker_ids.ids)],
            'context': {
                'search_default_group_by_employee': 1,
            },
        }

    def action_start_coaching(self):
        """Open a new coaching session for a banker in this branch"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Start Coaching Session'),
            'res_model': 'hr.coaching.session',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_branch_id': self.id,
                'default_coach_id': self.env.user.employee_id.id if self.env.user.employee_id else False,
            },
        }
