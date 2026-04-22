# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollAIPulse(models.Model):
    """
    Proactive Pulse Engine — Detects payroll anomalies and generates AI-powered alerts.
    Runs via scheduled cron job, compares current metrics against KPI baselines.
    """

    _name = 'payroll.ai.pulse'
    _description = 'PayAI Pulse — Proactive Anomaly Detection'
    _order = 'create_date desc'

    name = fields.Char(string='Alert Title', required=True)
    severity = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='Severity', default='info', required=True)

    category = fields.Selection([
        ('cost', 'Payroll Cost'),
        ('headcount', 'Headcount'),
        ('overtime', 'Overtime'),
        ('attendance', 'Attendance'),
        ('leave', 'Leave / Absence'),
        ('other', 'Other'),
    ], string='Category', default='other', required=True)

    summary = fields.Text(string='AI Summary', help='AI-generated narrative explaining the anomaly')
    details = fields.Text(string='Raw Details', help='JSON with metric values')
    metric_value = fields.Float(string='Current Value')
    baseline_value = fields.Float(string='Expected Baseline')
    deviation_pct = fields.Float(string='Deviation %', help='How far the metric is from baseline')
    department_id = fields.Many2one('hr.department', string='Department')

    state = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ], default='new', string='Status')

    chart_config = fields.Text(
        string='Mini Chart Config',
        help='Chart.js JSON config for mini-chart visualization in the alert card',
    )

    user_id = fields.Many2one(
        'res.users', string='Detected By',
        default=lambda self: self.env.user,
    )

    def action_acknowledge(self):
        self.write({'state': 'acknowledged'})

    def action_resolve(self):
        self.write({'state': 'resolved'})

    # =========================================================================
    # Anomaly Detection Engine — Called by Cron
    # =========================================================================

    @api.model
    def run_anomaly_detection(self):
        """
        Main entry point for the scheduled cron job.
        Detects anomalies across payroll data and creates pulse alerts.
        """
        _logger.info("PayAI Pulse: Starting anomaly detection...")
        alerts_created = 0

        try:
            alerts_created += self._detect_payroll_cost_anomalies()
        except Exception as e:
            _logger.error("PayAI Pulse: Cost anomaly detection failed: %s", e)

        try:
            alerts_created += self._detect_headcount_changes()
        except Exception as e:
            _logger.error("PayAI Pulse: Headcount detection failed: %s", e)

        try:
            alerts_created += self._detect_overtime_spikes()
        except Exception as e:
            _logger.error("PayAI Pulse: Overtime detection failed: %s", e)

        try:
            alerts_created += self._detect_leave_anomalies()
        except Exception as e:
            _logger.error("PayAI Pulse: Leave detection failed: %s", e)

        _logger.info("PayAI Pulse: Detection complete. %d alerts created.", alerts_created)

        # Generate AI summaries for new alerts
        if alerts_created > 0:
            self._generate_ai_summaries()

        return alerts_created

    def _detect_payroll_cost_anomalies(self):
        """Compare current month payroll cost vs previous 3-month average."""
        Payslip = self.env['hr.payslip'].sudo()
        today = fields.Date.today()

        # Current month
        month_start = today.replace(day=1)
        current_payslips = Payslip.search([
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', month_start),
        ])
        current_cost = sum(
            sum(l.total for l in ps.line_ids if l.total > 0)
            for ps in current_payslips
        )

        if current_cost == 0:
            return 0  # No payroll processed yet this month

        # Previous 3 months average
        prev_costs = []
        for i in range(1, 4):
            m_start = (month_start - relativedelta(months=i))
            m_end = (month_start - relativedelta(months=i-1)) - timedelta(days=1)
            prev_payslips = Payslip.search([
                ('state', 'in', ['done', 'paid']),
                ('date_from', '>=', m_start),
                ('date_from', '<=', m_end),
            ])
            cost = sum(
                sum(l.total for l in ps.line_ids if l.total > 0)
                for ps in prev_payslips
            )
            if cost > 0:
                prev_costs.append(cost)

        if not prev_costs:
            return 0

        avg_cost = sum(prev_costs) / len(prev_costs)
        deviation = ((current_cost - avg_cost) / avg_cost) * 100 if avg_cost else 0

        # Alert if deviation > 10%
        if abs(deviation) > 10:
            severity = 'critical' if abs(deviation) > 25 else 'warning'
            direction = 'increased' if deviation > 0 else 'decreased'

            self.create({
                'name': f'Payroll Cost {direction.title()} by {abs(deviation):.1f}%',
                'severity': severity,
                'category': 'cost',
                'metric_value': current_cost,
                'baseline_value': avg_cost,
                'deviation_pct': round(deviation, 2),
                'details': json.dumps({
                    'current_month_cost': current_cost,
                    'avg_3m_cost': avg_cost,
                    'previous_months': prev_costs,
                }),
            })
            return 1
        return 0

    def _detect_headcount_changes(self):
        """Detect significant headcount changes (new hires, departures)."""
        Employee = self.env['hr.employee'].sudo()
        today = fields.Date.today()
        last_week = today - timedelta(days=7)

        # New employees this week
        new_employees = Employee.search([
            ('create_date', '>=', last_week),
        ])
        # Departed employees this week (archived)
        departed = Employee.with_context(active_test=False).search([
            ('active', '=', False),
            ('write_date', '>=', last_week),
        ])

        alerts = 0
        if len(new_employees) >= 3:
            self.create({
                'name': f'{len(new_employees)} New Employees Joined This Week',
                'severity': 'info',
                'category': 'headcount',
                'metric_value': len(new_employees),
                'details': json.dumps({
                    'new_employees': [
                        {'name': e.name, 'department': e.department_id.name or 'Unassigned'}
                        for e in new_employees[:10]
                    ],
                }),
            })
            alerts += 1

        if len(departed) >= 2:
            self.create({
                'name': f'{len(departed)} Employees Departed This Week',
                'severity': 'warning',
                'category': 'headcount',
                'metric_value': len(departed),
                'details': json.dumps({
                    'departed': [
                        {'name': e.name, 'department': e.department_id.name or 'Unassigned'}
                        for e in departed[:10]
                    ],
                }),
            })
            alerts += 1

        return alerts

    def _detect_overtime_spikes(self):
        """Detect departments with unusually high overtime."""
        Payslip = self.env['hr.payslip'].sudo()
        today = fields.Date.today()
        month_start = today.replace(day=1)

        # Current month overtime by department
        payslips = Payslip.search([
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', month_start),
        ])

        dept_overtime = {}
        for ps in payslips:
            dept = ps.employee_id.department_id.name or 'Unassigned'
            ot_lines = ps.line_ids.filtered(
                lambda l: l.salary_rule_id.code and 'OT' in l.salary_rule_id.code.upper()
            )
            ot_amount = sum(l.total for l in ot_lines)
            if dept not in dept_overtime:
                dept_overtime[dept] = 0
            dept_overtime[dept] += ot_amount

        alerts = 0
        for dept, ot_total in dept_overtime.items():
            if ot_total > 0:
                # Check against previous month
                prev_start = month_start - relativedelta(months=1)
                prev_end = month_start - timedelta(days=1)
                prev_ps = Payslip.search([
                    ('state', 'in', ['done', 'paid']),
                    ('date_from', '>=', prev_start),
                    ('date_from', '<=', prev_end),
                    ('employee_id.department_id.name', '=', dept),
                ])
                prev_ot = sum(
                    sum(l.total for l in ps.line_ids.filtered(
                        lambda l: l.salary_rule_id.code and 'OT' in l.salary_rule_id.code.upper()
                    ))
                    for ps in prev_ps
                )

                if prev_ot > 0:
                    deviation = ((ot_total - prev_ot) / prev_ot) * 100
                    if deviation > 30:
                        dept_rec = self.env['hr.department'].search([('name', '=', dept)], limit=1)
                        self.create({
                            'name': f'Overtime Spike in {dept}: +{deviation:.0f}%',
                            'severity': 'warning',
                            'category': 'overtime',
                            'department_id': dept_rec.id if dept_rec else False,
                            'metric_value': ot_total,
                            'baseline_value': prev_ot,
                            'deviation_pct': round(deviation, 2),
                            'details': json.dumps({
                                'department': dept,
                                'current_ot': ot_total,
                                'previous_ot': prev_ot,
                            }),
                        })
                        alerts += 1
        return alerts

    def _detect_leave_anomalies(self):
        """Detect unusually high leave rates."""
        if not self._is_module_installed('hr_holidays'):
            return 0

        Leave = self.env['hr.leave'].sudo()
        today = fields.Date.today()
        week_start = today - timedelta(days=7)

        # Leaves this week
        current_leaves = Leave.search([
            ('state', '=', 'validate'),
            ('date_from', '>=', week_start),
        ])

        if len(current_leaves) >= 5:
            # Group by type
            type_counts = {}
            for lv in current_leaves:
                lt = lv.holiday_status_id.name or 'Other'
                type_counts[lt] = type_counts.get(lt, 0) + 1

            self.create({
                'name': f'{len(current_leaves)} Approved Leaves This Week',
                'severity': 'info' if len(current_leaves) < 10 else 'warning',
                'category': 'leave',
                'metric_value': len(current_leaves),
                'details': json.dumps({
                    'total_leaves': len(current_leaves),
                    'by_type': type_counts,
                }),
            })
            return 1
        return 0

    def _is_module_installed(self, module_name):
        """Check if a module is installed."""
        try:
            return self.env['ir.module.module'].sudo().search_count([
                ('name', '=', module_name),
                ('state', '=', 'installed'),
            ]) > 0
        except Exception:
            return False

    def _generate_ai_summaries(self):
        """Generate AI-powered narrative summaries for new alerts."""
        new_alerts = self.search([('state', '=', 'new'), ('summary', '=', False)])
        if not new_alerts:
            return

        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return
            provider = config.get_provider_instance()
            if not provider:
                return
        except Exception:
            return

        for alert in new_alerts:
            try:
                prompt = f"""You are PayAI, an HR analytics assistant. Write a brief 2-3 sentence executive summary for this payroll anomaly alert:

Alert: {alert.name}
Category: {alert.category}
Severity: {alert.severity}
Current Value: {alert.metric_value}
Baseline Value: {alert.baseline_value}
Deviation: {alert.deviation_pct}%
Details: {alert.details or ''}

Write a clear, actionable summary. Include what happened, why it matters, and a recommended action. Keep it concise."""

                summary = provider.generate_text(prompt, max_tokens=200, temperature=0.5)
                alert.write({'summary': summary.strip()})
            except Exception as e:
                _logger.warning("PayAI Pulse: AI summary failed for alert %s: %s", alert.id, e)

    # =========================================================================
    # RPC Methods for Frontend
    # =========================================================================

    @api.model
    def rpc_get_active_alerts(self, limit=10):
        """Get recent unresolved alerts for the dashboard."""
        alerts = self.search([
            ('state', 'in', ['new', 'acknowledged']),
        ], limit=limit, order='create_date desc')

        return [{
            'id': a.id,
            'name': a.name,
            'severity': a.severity,
            'category': a.category,
            'summary': a.summary or '',
            'metric_value': a.metric_value,
            'baseline_value': a.baseline_value,
            'deviation_pct': a.deviation_pct,
            'department': a.department_id.name or '',
            'state': a.state,
            'created': a.create_date.isoformat() if a.create_date else '',
            'chart_config': json.loads(a.chart_config) if a.chart_config else None,
        } for a in alerts]

    @api.model
    def rpc_acknowledge_alert(self, alert_id):
        """Acknowledge an alert."""
        alert = self.browse(alert_id).exists()
        if alert:
            alert.action_acknowledge()
        return True

    @api.model
    def rpc_resolve_alert(self, alert_id):
        """Resolve an alert."""
        alert = self.browse(alert_id).exists()
        if alert:
            alert.action_resolve()
        return True
