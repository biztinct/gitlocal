# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta, datetime
import json
import logging
import math

_logger = logging.getLogger(__name__)


class BFSIAIDashboard(models.AbstractModel):
    _name = 'bfsi.ai.dashboard'
    _description = 'AI-Powered Performance Dashboard API'

    # ═══════════════════════════════════════════════════════════════
    #  MASTER API — Single entry point for the OWL dashboard
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def get_dashboard_data(self, branch_id=None, date_range='mtd', custom_from=None, custom_to=None):
        """
        Master API — returns all dashboard data in one RPC call.

        Args:
            branch_id: int — specific branch, or None for current user's branch
            date_range: str — 'today', 'yesterday', 'wtd', 'mtd', 'qtd', 'custom'
            custom_from: str — ISO date for custom range start
            custom_to: str — ISO date for custom range end

        Returns:
            dict with all dashboard sections
        """
        # Resolve branch from current user if not provided
        if not branch_id:
            emp = self.env.user.employee_id
            if emp and emp.branch_id:
                branch_id = emp.branch_id.id
            else:
                # Try finding via employee record
                emp_rec = self.env['hr.employee'].sudo().search(
                    [('user_id', '=', self.env.uid)], limit=1
                )
                if emp_rec and emp_rec.branch_id:
                    branch_id = emp_rec.branch_id.id

        if not branch_id:
            return {'error': 'No branch found for current user'}

        # Resolve date range
        date_from, date_to = self._resolve_date_range(date_range, custom_from, custom_to)

        branch = self.env['bfsi.branch'].sudo().browse(branch_id)
        if not branch.exists():
            return {'error': 'Branch not found'}

        # Collect all bankers in this branch
        banker_ids = branch.banker_ids.filtered(lambda e: e.active).ids

        return {
            'branch': {
                'id': branch.id,
                'name': branch.name,
                'code': branch.code or '',
                'manager': branch.manager_id.name if branch.manager_id else '',
                'region': branch.region_id.name if branch.region_id else '',
            },
            'date_range': {
                'type': date_range,
                'from': date_from.isoformat() if date_from else None,
                'to': date_to.isoformat() if date_to else None,
                'label': self._get_date_range_label(date_range, date_from, date_to),
            },
            'kpi_summary': self._get_kpi_summary(branch, banker_ids, date_from, date_to),
            'root_cause': self._get_root_cause_analysis(branch, banker_ids, date_from, date_to),
            'forecast': self._get_forecast_data(branch, banker_ids, date_to),
            'team_performance': self._get_team_performance(branch, banker_ids, date_from, date_to),
            'smart_insights': self._get_smart_insights(branch, banker_ids),
            'executive_summary': self._get_executive_summary(branch, banker_ids, date_from, date_to),
            'benchmarking': self._get_benchmarking(branch, banker_ids, date_from, date_to),
            'incentive_data': self._get_incentive_data(branch, banker_ids, date_from, date_to),
        }

    # ═══════════════════════════════════════════════════════════════
    #  DATE RANGE HELPERS
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def _resolve_date_range(self, range_type, custom_from=None, custom_to=None):
        """Resolve date range type to actual date boundaries."""
        today = fields.Date.today()

        if range_type == 'today':
            return today, today
        elif range_type == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif range_type == 'wtd':
            # Week-to-date (Monday start)
            week_start = today - timedelta(days=today.weekday())
            return week_start, today
        elif range_type == 'mtd':
            month_start = today.replace(day=1)
            return month_start, today
        elif range_type == 'qtd':
            quarter_month = ((today.month - 1) // 3) * 3 + 1
            quarter_start = today.replace(month=quarter_month, day=1)
            return quarter_start, today
        elif range_type == 'custom' and custom_from and custom_to:
            return (
                fields.Date.from_string(custom_from),
                fields.Date.from_string(custom_to),
            )
        else:
            # Default to MTD
            return today.replace(day=1), today

    @api.model
    def _get_date_range_label(self, range_type, date_from, date_to):
        """Human-readable label for the date range."""
        labels = {
            'today': 'Today',
            'yesterday': 'Yesterday (D-1)',
            'wtd': 'Week to Date',
            'mtd': 'Month to Date',
            'qtd': 'Quarter to Date',
        }
        if range_type in labels:
            return labels[range_type]
        if date_from and date_to:
            return f"{date_from.strftime('%b %d')} — {date_to.strftime('%b %d, %Y')}"
        return 'Custom'

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 1: KPI SUMMARY STRIP — 5 top-level metrics
    # ═══════════════════════════════════════════════════════════════

    def _get_kpi_summary(self, branch, banker_ids, date_from, date_to):
        """Aggregate top-level KPI metrics for the branch."""
        KPI = self.env['bfsi.performance.kpi'].sudo()
        Target = self.env['bfsi.kpi.target'].sudo()

        # Current period KPIs
        current_kpis = KPI.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', date_from),
            ('period_date', '<=', date_to),
        ])

        # Previous period (same duration, shifted back)
        period_days = (date_to - date_from).days + 1
        prev_from = date_from - timedelta(days=period_days)
        prev_to = date_from - timedelta(days=1)
        prev_kpis = KPI.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', prev_from),
            ('period_date', '<=', prev_to),
        ])

        # Current aggregates
        total_revenue = sum(current_kpis.mapped('revenue'))
        total_conversions = sum(current_kpis.mapped('conversions'))
        total_meetings = sum(current_kpis.mapped('meetings_conducted'))
        total_dials = sum(current_kpis.mapped('total_dials'))
        avg_score = (
            sum(current_kpis.mapped('overall_score')) / len(current_kpis)
            if current_kpis else 0
        )
        avg_conversion_rate = (
            sum(current_kpis.mapped('conversion_rate')) / len(current_kpis)
            if current_kpis else 0
        )

        # Previous aggregates
        prev_revenue = sum(prev_kpis.mapped('revenue'))
        prev_conversions = sum(prev_kpis.mapped('conversions'))
        prev_score = (
            sum(prev_kpis.mapped('overall_score')) / len(prev_kpis)
            if prev_kpis else 0
        )

        # Target comparison (get branch-level or any applicable target)
        target = Target.search([
            ('branch_id', '=', branch.id),
            ('valid_from', '<=', date_to),
            '|', ('valid_to', '=', False), ('valid_to', '>=', date_from),
        ], limit=1)

        target_revenue = target.target_revenue if target else 0
        forecast_pct = (
            round(total_revenue / target_revenue * 100, 1)
            if target_revenue > 0 else 0
        )

        # Bankers with activity this period
        active_banker_ids = set(current_kpis.mapped('employee_id').ids)
        active_pct = (
            round(len(active_banker_ids) / len(banker_ids) * 100)
            if banker_ids else 0
        )

        # Coverage: bankers who had meetings
        bankers_with_meetings = len([
            k for k in current_kpis
            if k.meetings_conducted and k.meetings_conducted > 0
        ])
        unique_meeting_bankers = len(set(
            k.employee_id.id for k in current_kpis
            if k.meetings_conducted and k.meetings_conducted > 0
        ))
        coverage_pct = (
            round(unique_meeting_bankers / len(banker_ids) * 100)
            if banker_ids else 0
        )

        # Revenue change
        revenue_change = (
            round((total_revenue - prev_revenue) / prev_revenue * 100, 1)
            if prev_revenue > 0 else 0
        )

        currency = self.env.company.currency_id

        return {
            'forecast_pct': forecast_pct,
            'forecast_explanation': self._explain_change(
                'Revenue forecast', forecast_pct, 100, '%'
            ),
            'mtd_revenue': total_revenue,
            'mtd_revenue_formatted': self._format_currency(total_revenue, currency),
            'revenue_change_pct': revenue_change,
            'revenue_explanation': self._explain_change(
                'Revenue', total_revenue, prev_revenue, currency.symbol
            ),
            'avg_conversion_rate': round(avg_conversion_rate, 2),
            'conversion_explanation': f"Avg across {len(active_banker_ids)} active bankers",
            'active_bankers_pct': active_pct,
            'active_bankers_count': len(active_banker_ids),
            'total_bankers': len(banker_ids),
            'coverage_pct': coverage_pct,
            'coverage_explanation': (
                f"{unique_meeting_bankers}/{len(banker_ids)} bankers had client meetings"
            ),
            'total_conversions': total_conversions,
            'total_meetings': total_meetings,
            'total_dials': total_dials,
            'avg_score': round(avg_score, 1),
            'target_revenue': target_revenue,
            'target_revenue_formatted': self._format_currency(target_revenue, currency),
            'currency_symbol': currency.symbol,
            'currency_name': currency.name,
        }

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 2: ROOT CAUSE ANALYSIS — categorized gap analysis
    # ═══════════════════════════════════════════════════════════════

    def _get_root_cause_analysis(self, branch, banker_ids, date_from, date_to):
        """Data-driven root cause analysis of performance gaps."""
        KPI = self.env['bfsi.performance.kpi'].sudo()

        period_days = (date_to - date_from).days + 1
        prev_from = date_from - timedelta(days=period_days)
        prev_to = date_from - timedelta(days=1)

        current = KPI.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', date_from),
            ('period_date', '<=', date_to),
        ])
        previous = KPI.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', prev_from),
            ('period_date', '<=', prev_to),
        ])

        if not current or not previous:
            return {
                'summary': 'Insufficient data for root cause analysis. Need at least 2 periods of data.',
                'categories': [],
                'ai_available': False,
            }

        # Current period aggregates
        c_revenue = sum(current.mapped('revenue'))
        c_dials = sum(current.mapped('total_dials'))
        c_meetings = sum(current.mapped('meetings_conducted'))
        c_conversions = sum(current.mapped('conversions'))
        c_script = sum(current.mapped('script_adherence')) / len(current) if current else 0
        c_objection = sum(current.mapped('objection_handling_score')) / len(current) if current else 0
        c_products = sum(current.mapped('products_sold'))

        # Previous period aggregates
        p_revenue = sum(previous.mapped('revenue'))
        p_dials = sum(previous.mapped('total_dials'))
        p_meetings = sum(previous.mapped('meetings_conducted'))
        p_conversions = sum(previous.mapped('conversions'))
        p_script = sum(previous.mapped('script_adherence')) / len(previous) if previous else 0
        p_objection = sum(previous.mapped('objection_handling_score')) / len(previous) if previous else 0
        p_products = sum(previous.mapped('products_sold'))

        revenue_delta = c_revenue - p_revenue
        currency = self.env.company.currency_id

        # Categorize root causes
        categories = []

        # 1. Activity Issues (Input KPIs)
        activity_impact = 0
        activity_details = []
        if p_dials > 0:
            dials_change = round((c_dials - p_dials) / p_dials * 100, 1)
            if dials_change < -5:
                activity_details.append(f"{abs(dials_change)}% fewer dials")
                activity_impact += revenue_delta * 0.3  # Approximate attribution
        if p_meetings > 0:
            meetings_change = round((c_meetings - p_meetings) / p_meetings * 100, 1)
            if meetings_change < -5:
                activity_details.append(f"{abs(meetings_change)}% fewer meetings")
                activity_impact += revenue_delta * 0.4

        if activity_details:
            categories.append({
                'type': 'activity',
                'label': 'Activity Issue',
                'impact': round(activity_impact),
                'impact_formatted': self._format_currency(abs(activity_impact), currency),
                'detail': 'from ' + ', '.join(activity_details),
                'color': '#3B82F6',
                'icon': 'fa-phone',
            })

        # 2. Behavior Issues
        behavior_impact = 0
        behavior_details = []
        if p_script > 0:
            script_change = round(c_script - p_script, 1)
            if script_change < -3:
                behavior_details.append(f"{abs(script_change)}% lower script adherence")
                behavior_impact += revenue_delta * 0.2
        if p_objection > 0:
            obj_change = round(c_objection - p_objection, 1)
            if obj_change < -3:
                behavior_details.append(f"{abs(obj_change)}pts lower objection handling")
                behavior_impact += revenue_delta * 0.2

        if behavior_details:
            categories.append({
                'type': 'behavior',
                'label': 'Behavior Issue',
                'impact': round(behavior_impact),
                'impact_formatted': self._format_currency(abs(behavior_impact), currency),
                'detail': 'from ' + ', '.join(behavior_details),
                'color': '#F59E0B',
                'icon': 'fa-user',
            })

        # 3. Product Mix Issues (revenue per conversion)
        product_impact = 0
        product_details = []
        if c_conversions > 0 and p_conversions > 0:
            c_rev_per_conv = c_revenue / c_conversions if c_conversions else 0
            p_rev_per_conv = p_revenue / p_conversions if p_conversions else 0
            if p_rev_per_conv > 0:
                rpconv_change = round(
                    (c_rev_per_conv - p_rev_per_conv) / p_rev_per_conv * 100, 1
                )
                if rpconv_change < -5:
                    product_details.append(
                        f"{abs(rpconv_change)}% lower revenue per conversion"
                    )
                    product_impact = revenue_delta * 0.3

        if product_details:
            categories.append({
                'type': 'product',
                'label': 'Product Mix Issue',
                'impact': round(product_impact),
                'impact_formatted': self._format_currency(abs(product_impact), currency),
                'detail': 'from ' + ', '.join(product_details),
                'color': '#EF4444',
                'icon': 'fa-cubes',
            })

        # Build summary
        if revenue_delta < 0:
            summary = (
                f"Revenue down {self._format_currency(abs(revenue_delta), currency)}. "
            )
            if activity_details:
                summary += f"Driven by {activity_details[0]}"
            if behavior_details:
                summary += f" + {behavior_details[0]}"
            summary += ". "
        elif revenue_delta > 0:
            summary = (
                f"Revenue up {self._format_currency(revenue_delta, currency)} "
                f"({round(revenue_delta / p_revenue * 100, 1) if p_revenue else 0}% growth). "
            )
        else:
            summary = "Revenue flat compared to previous period. "

        return {
            'summary': summary,
            'categories': categories,
            'revenue_delta': revenue_delta,
            'revenue_delta_formatted': self._format_currency(revenue_delta, currency),
            'ai_available': self._is_ai_available(),
        }

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 3: FORECAST PERFORMANCE — trend + prediction
    # ═══════════════════════════════════════════════════════════════

    def _get_forecast_data(self, branch, banker_ids, date_to):
        """Generate forecast using historical trends."""
        KPI = self.env['bfsi.performance.kpi'].sudo()
        Target = self.env['bfsi.kpi.target'].sudo()

        # Pull last 90 days of daily data
        history_start = date_to - timedelta(days=90)
        kpis = KPI.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', history_start),
            ('period_date', '<=', date_to),
        ], order='period_date asc')

        if not kpis:
            return {
                'on_track_pct': 0,
                'shortfall': 0,
                'chart': {'labels': [], 'actual': [], 'predicted': [], 'target': 0},
                'ai_prediction': '',
                'key_predictions': [],
            }

        # Group revenue by date (cumulative for MTD context)
        daily_revenue = {}
        for kpi in kpis:
            d = kpi.period_date.isoformat()
            daily_revenue.setdefault(d, 0)
            daily_revenue[d] += kpi.revenue or 0

        dates = sorted(daily_revenue.keys())
        revenues = [daily_revenue[d] for d in dates]

        # Calculate cumulative MTD revenue
        mtd_start = date_to.replace(day=1)
        cumulative = []
        running = 0
        mtd_labels = []
        for d in dates:
            dt = date.fromisoformat(d)
            if dt >= mtd_start:
                running += daily_revenue[d]
                cumulative.append(round(running, 2))
                mtd_labels.append(dt.strftime('%b %d'))

        # Simple linear regression for prediction
        predicted = []
        if len(cumulative) >= 3:
            # Predict to end of month
            import calendar
            _, last_day = calendar.monthrange(date_to.year, date_to.month)
            days_remaining = last_day - date_to.day

            # Calculate daily avg from recent 7 days
            recent = revenues[-7:] if len(revenues) >= 7 else revenues
            daily_avg = sum(recent) / len(recent) if recent else 0

            current_total = cumulative[-1] if cumulative else 0
            for i in range(1, days_remaining + 1):
                proj_date = date_to + timedelta(days=i)
                current_total += daily_avg
                predicted.append(round(current_total, 2))
                mtd_labels.append(proj_date.strftime('%b %d'))
        else:
            days_remaining = 0

        # Target for the month
        target = Target.search([
            ('branch_id', '=', branch.id),
            ('valid_from', '<=', date_to),
            '|', ('valid_to', '=', False), ('valid_to', '>=', date_to),
        ], limit=1)
        target_revenue = target.target_revenue if target else 0

        # Forecast percentage
        projected_total = predicted[-1] if predicted else (cumulative[-1] if cumulative else 0)
        on_track_pct = (
            round(projected_total / target_revenue * 100, 1)
            if target_revenue > 0 else 0
        )
        shortfall = projected_total - target_revenue

        currency = self.env.company.currency_id

        # Per-banker mini forecasts
        key_predictions = []
        # Use branch target / num bankers as fallback per-banker target
        per_banker_target = (
            target_revenue / len(banker_ids) if target_revenue and banker_ids else 0
        )
        for banker_id in banker_ids:
            banker = self.env['hr.employee'].sudo().browse(banker_id)
            b_kpis = kpis.filtered(lambda k: k.employee_id.id == banker_id)
            b_rev = sum(b_kpis.mapped('revenue')) if b_kpis else 0

            # Try individual target first, fall back to branch per-banker target
            b_target = Target.get_target_for_employee(banker_id, date_to)
            b_target_rev = b_target.target_revenue if b_target else per_banker_target
            b_pct = round(b_rev / b_target_rev * 100) if b_target_rev else 0

            key_predictions.append({
                'id': banker_id,
                'name': banker.name,
                'current_revenue': b_rev,
                'target_revenue': b_target_rev,
                'forecast_pct': b_pct,
            })

        return {
            'on_track_pct': on_track_pct,
            'shortfall': shortfall,
            'shortfall_formatted': self._format_currency(shortfall, currency),
            'chart': {
                'labels': mtd_labels,
                'actual': cumulative,
                'predicted': [None] * len(cumulative) + predicted,
                'target': target_revenue,
            },
            'ai_prediction': (
                f"Team is on track to close at {on_track_pct}% of target"
                + (f" ({self._format_currency(abs(shortfall), currency)} shortfall)"
                   if shortfall < 0 else "")
                + "."
            ),
            'key_predictions': key_predictions,
            'ai_available': self._is_ai_available(),
        }

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 4: SMART INSIGHTS — AI coaching nudges
    # ═══════════════════════════════════════════════════════════════

    def _get_smart_insights(self, branch, banker_ids):
        """Get AI-generated coaching insights for the team."""
        Nudge = self.env['hr.coaching.nudge'].sudo()
        KPI = self.env['bfsi.performance.kpi'].sudo()

        insights = []
        today = fields.Date.today()

        # Get recent nudges
        recent_nudges = Nudge.search([
            ('employee_id', 'in', banker_ids),
            ('create_date', '>=', datetime.combine(today - timedelta(days=7), datetime.min.time())),
            ('state', 'in', ['sent', 'read']),
        ], order='create_date desc', limit=10)

        for nudge in recent_nudges:
            insights.append({
                'id': nudge.id,
                'type': 'nudge',
                'banker_id': nudge.employee_id.id,
                'banker_name': nudge.employee_id.name,
                'title': nudge.title,
                'message': nudge.message or '',
                'priority': nudge.priority,
                'situation': nudge.situation,
                'timestamp': nudge.create_date.isoformat() if nudge.create_date else '',
                'time_ago': self._time_ago(nudge.create_date) if nudge.create_date else '',
            })

        # Generate data-driven insights from KPIs if no nudges
        if len(insights) < 5:
            for banker_id in banker_ids:
                banker = self.env['hr.employee'].sudo().browse(banker_id)
                latest_kpi = KPI.search([
                    ('employee_id', '=', banker_id),
                    ('period_date', '<=', today),
                ], order='period_date desc', limit=1)

                if latest_kpi and latest_kpi.coaching_priority in ['high', 'critical']:
                    insights.append({
                        'id': f'kpi_{latest_kpi.id}',
                        'type': 'kpi_alert',
                        'banker_id': banker_id,
                        'banker_name': banker.name,
                        'title': f'{banker.name}: Performance Alert',
                        'message': (
                            f"Score at {latest_kpi.overall_score:.0f}/100 "
                            f"(branch rank #{latest_kpi.branch_rank}). "
                            f"Coaching priority: {latest_kpi.coaching_priority}."
                        ),
                        'priority': latest_kpi.coaching_priority,
                        'situation': 'low_performance',
                        'timestamp': latest_kpi.period_date.isoformat(),
                        'time_ago': '',
                    })

                if len(insights) >= 10:
                    break

        return insights[:10]

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 5: TEAM PERFORMANCE TABLE — per-banker data
    # ═══════════════════════════════════════════════════════════════

    def _get_team_performance(self, branch, banker_ids, date_from, date_to):
        """Get rich per-banker performance data for the table."""
        KPI = self.env['bfsi.performance.kpi'].sudo()
        ActionPlan = self.env['bfsi.action.plan'].sudo()
        Target = self.env['bfsi.kpi.target'].sudo()
        currency = self.env.company.currency_id

        team = []
        for banker_id in banker_ids:
            banker = self.env['hr.employee'].sudo().browse(banker_id)

            # Current period KPIs
            period_kpis = KPI.search([
                ('employee_id', '=', banker_id),
                ('period_date', '>=', date_from),
                ('period_date', '<=', date_to),
            ])

            # Latest single KPI for score/rank
            latest_kpi = KPI.search([
                ('employee_id', '=', banker_id),
                ('period_date', '<=', date_to),
            ], order='period_date desc', limit=1)

            # Sparkline data (last 7 data points)
            spark_kpis = KPI.search([
                ('employee_id', '=', banker_id),
                ('period_date', '<=', date_to),
            ], order='period_date desc', limit=7)
            sparkline = list(reversed([k.overall_score for k in spark_kpis]))

            # Period aggregates
            total_revenue = sum(period_kpis.mapped('revenue'))
            total_conversions = sum(period_kpis.mapped('conversions'))
            avg_conversion_rate = (
                sum(period_kpis.mapped('conversion_rate')) / len(period_kpis)
                if period_kpis else 0
            )

            # Target & forecast
            target = Target.get_target_for_employee(banker_id, date_to)
            target_revenue = target.target_revenue if target else 0
            forecast_pct = (
                round(total_revenue / target_revenue * 100)
                if target_revenue > 0 else 0
            )

            # Active action plans
            active_plans = ActionPlan.search([
                ('employee_id', '=', banker_id),
                ('state', 'in', ['committed', 'in_progress']),
            ])

            # Banker type label
            banker_type_label = dict(
                self.env['hr.employee']._fields['banker_type'].selection
            ).get(banker.banker_type, banker.banker_type or 'Banker')

            team.append({
                'id': banker_id,
                'name': banker.name,
                'avatar_url': f'/web/image/hr.employee/{banker_id}/avatar_128',
                'banker_type': banker.banker_type or 'banker',
                'banker_type_label': banker_type_label,
                'branch_name': branch.name,

                # KPI metrics
                'overall_score': latest_kpi.overall_score if latest_kpi else 0,
                'branch_rank': latest_kpi.branch_rank if latest_kpi else 0,
                'rank_movement': latest_kpi.rank_movement if latest_kpi else 0,
                'coaching_priority': latest_kpi.coaching_priority if latest_kpi else 'low',

                # Period aggregates
                'revenue': total_revenue,
                'revenue_formatted': self._format_currency(total_revenue, currency),
                'conversions': total_conversions,
                'conversion_rate': round(avg_conversion_rate, 1),
                'forecast_pct': forecast_pct,

                # Sparkline
                'sparkline': sparkline,

                # Action plans
                'active_plans_count': len(active_plans),
                'has_next_steps': len(active_plans) > 0,
                'plan_ids': active_plans.ids,
            })

        # Sort by overall score descending
        team.sort(key=lambda x: x['overall_score'], reverse=True)

        return team

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 6: EXECUTIVE SUMMARY — AI-generated
    # ═══════════════════════════════════════════════════════════════

    def _get_executive_summary(self, branch, banker_ids, date_from, date_to):
        """Generate executive summary text — AI-enhanced if available."""
        kpi_summary = self._get_kpi_summary(branch, banker_ids, date_from, date_to)
        team_data = self._get_team_performance(branch, banker_ids, date_from, date_to)

        # Find top risk (lowest score)
        top_risk = min(team_data, key=lambda x: x['overall_score']) if team_data else None
        # Find top opportunity (highest rank movement)
        top_opp = max(team_data, key=lambda x: x['rank_movement']) if team_data else None

        currency_sym = self.env.company.currency_id.symbol

        summary_text = (
            f"SUMMARY — Overall branch performance at "
            f"{kpi_summary['avg_score']}/100 avg score. "
            f"Revenue MTD: {kpi_summary['mtd_revenue_formatted']} "
            f"({kpi_summary['forecast_pct']}% of target). "
            f"{kpi_summary['active_bankers_count']}/{kpi_summary['total_bankers']} "
            f"bankers active."
        )

        return {
            'text': summary_text,
            'top_risk': {
                'id': top_risk['id'] if top_risk else None,
                'name': top_risk['name'] if top_risk else '',
                'score': top_risk['overall_score'] if top_risk else 0,
                'revenue': top_risk['revenue_formatted'] if top_risk else '',
                'priority': top_risk['coaching_priority'] if top_risk else '',
            } if top_risk else None,
            'top_opportunity': {
                'id': top_opp['id'] if top_opp else None,
                'name': top_opp['name'] if top_opp else '',
                'rank_movement': top_opp['rank_movement'] if top_opp else 0,
                'revenue': top_opp['revenue_formatted'] if top_opp else '',
            } if top_opp else None,
            'ai_available': self._is_ai_available(),
        }

    # ═══════════════════════════════════════════════════════════════
    #  SECTION 7: BENCHMARKING — comparative metrics
    # ═══════════════════════════════════════════════════════════════

    def _get_benchmarking(self, branch, banker_ids, date_from, date_to):
        """Generate benchmarking comparison data."""
        team = self._get_team_performance(branch, banker_ids, date_from, date_to)
        if not team:
            return {'text': '', 'leader': None, 'avg_score': 0}

        avg_score = sum(t['overall_score'] for t in team) / len(team)
        leader = max(team, key=lambda x: x['overall_score'])
        leader_diff = round(leader['overall_score'] - avg_score, 1)

        text = (
            f"{leader['name']} leading at {leader['overall_score']:.0f}/100 — "
            f"{leader_diff} points higher than team average."
        )

        return {
            'text': text,
            'leader': {
                'id': leader['id'],
                'name': leader['name'],
                'score': leader['overall_score'],
            },
            'avg_score': round(avg_score, 1),
            'total_bankers': len(team),
        }

    # ═══════════════════════════════════════════════════════════════
    #  SECTIONS 8-10: FINTECH LAYER — Incentives & Earnings
    # ═══════════════════════════════════════════════════════════════

    def _get_incentive_data(self, branch, banker_ids, date_from, date_to):
        """Get incentive tier distribution and earnings data."""
        # Check if incentive models exist (Fintech Layer may be phased in)
        try:
            Incentive = self.env['bfsi.incentive.structure'].sudo()
            Earning = self.env['bfsi.earning.tracker'].sudo()
        except Exception:
            return {'available': False}

        # Get active incentive structure for this branch
        structure = Incentive.search([
            '|', ('branch_id', '=', branch.id), ('branch_id', '=', False),
            ('valid_from', '<=', date_to),
            '|', ('valid_to', '=', False), ('valid_to', '>=', date_from),
        ], order='branch_id desc', limit=1)  # Prefer branch-specific

        if not structure:
            return {'available': False}

        # Get earnings for all bankers this month
        earnings = Earning.search([
            ('employee_id', 'in', banker_ids),
            ('period_date', '>=', date_from),
            ('period_date', '<=', date_to),
        ])

        total_commission = sum(earnings.mapped('accrued_commission'))
        total_bonus = sum(earnings.mapped('bonus_earned'))
        currency = self.env.company.currency_id

        # Tier distribution
        tier_distribution = []
        for slab in structure.slab_ids:
            count = len(earnings.filtered(
                lambda e: e.incentive_tier == slab.label
            )) if hasattr(earnings, 'incentive_tier') else 0
            tier_distribution.append({
                'label': slab.label,
                'min_pct': slab.threshold_min,
                'max_pct': slab.threshold_max,
                'rate': slab.commission_rate,
                'color': slab.color or '#4F46E5',
                'banker_count': count,
            })

        return {
            'available': True,
            'structure_name': structure.name,
            'total_commission': total_commission,
            'total_commission_formatted': self._format_currency(total_commission, currency),
            'total_bonus': total_bonus,
            'total_bonus_formatted': self._format_currency(total_bonus, currency),
            'avg_commission': (
                round(total_commission / len(banker_ids))
                if banker_ids else 0
            ),
            'avg_commission_formatted': self._format_currency(
                total_commission / len(banker_ids) if banker_ids else 0, currency
            ),
            'tier_distribution': tier_distribution,
            'currency_symbol': currency.symbol,
        }

    # ═══════════════════════════════════════════════════════════════
    #  AI REPORT GENERATION
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def generate_ai_report(self, branch_id, date_range='mtd'):
        """Generate comprehensive AI report for the branch."""
        data = self.get_dashboard_data(branch_id, date_range)
        if 'error' in data:
            return {'error': data['error']}

        # Build report text
        report_sections = []

        # Header
        report_sections.append(
            f"# AI Performance Report — {data['branch']['name']}\n"
            f"**Period**: {data['date_range']['label']}\n"
            f"**Generated**: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        )

        # KPI Summary
        kpi = data['kpi_summary']
        report_sections.append(
            f"## KPI Summary\n"
            f"- Revenue MTD: {kpi['mtd_revenue_formatted']}\n"
            f"- Forecast: {kpi['forecast_pct']}% of target\n"
            f"- Avg Conversion Rate: {kpi['avg_conversion_rate']}%\n"
            f"- Active Bankers: {kpi['active_bankers_count']}/{kpi['total_bankers']}\n"
            f"- Coverage: {kpi['coverage_pct']}%\n"
        )

        # Root Cause
        rc = data['root_cause']
        report_sections.append(f"## Root Cause Analysis\n{rc['summary']}\n")
        for cat in rc.get('categories', []):
            report_sections.append(
                f"- **{cat['label']}**: {cat['impact_formatted']} ({cat['detail']})"
            )

        # Team Performance
        report_sections.append("\n## Team Performance\n")
        for member in data['team_performance']:
            report_sections.append(
                f"- **{member['name']}** ({member['banker_type_label']}): "
                f"Score {member['overall_score']:.0f}, "
                f"Revenue {member['revenue_formatted']}, "
                f"Rank #{member['branch_rank']}"
            )

        # Executive Summary
        exec_sum = data['executive_summary']
        report_sections.append(f"\n## Executive Summary\n{exec_sum['text']}\n")

        return {
            'report_text': '\n'.join(report_sections),
            'report_html': self._markdown_to_html('\n'.join(report_sections)),
        }

    # ═══════════════════════════════════════════════════════════════
    #  AI ENHANCEMENT — Call AI provider for richer analysis
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def get_ai_enhanced_analysis(self, branch_id, section, data_context):
        """
        Call AI provider to enhance a specific dashboard section.
        Used for lazy-loading AI content after initial data render.

        Args:
            branch_id: int
            section: str — 'root_cause', 'forecast', 'insights', 'executive_summary'
            data_context: dict — pre-computed data to send to AI
        """
        if not self._is_ai_available():
            return {'ai_text': '', 'available': False}

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            prompts = {
                'root_cause': (
                    f"Analyze this branch performance data and explain the root causes "
                    f"for the performance change:\n{json.dumps(data_context, indent=2)}\n"
                    f"Provide a concise 2-3 sentence explanation."
                ),
                'forecast': (
                    f"Based on this performance trend data, provide a prediction:\n"
                    f"{json.dumps(data_context, indent=2)}\n"
                    f"Give a 1-2 sentence forecast."
                ),
                'executive_summary': (
                    f"Generate an executive summary for this branch performance data:\n"
                    f"{json.dumps(data_context, indent=2)}\n"
                    f"Include: overall assessment, top risk, top opportunity. "
                    f"Keep it to 3-4 sentences."
                ),
            }

            prompt = prompts.get(section, '')
            if not prompt:
                return {'ai_text': '', 'available': False}

            response = ai_provider.generate_text(prompt, max_tokens=300, temperature=0.5)
            return {'ai_text': response, 'available': True}

        except Exception as e:
            _logger.warning(f"AI enhancement failed for {section}: {e}")
            return {'ai_text': '', 'available': False, 'error': str(e)}

    # ═══════════════════════════════════════════════════════════════
    #  UTILITY HELPERS
    # ═══════════════════════════════════════════════════════════════

    @api.model
    def _is_ai_available(self):
        """Check if AI provider is configured and active."""
        try:
            config = self.env['hr.ai.provider.config'].sudo().search([
                ('company_id', '=', self.env.company.id),
                ('is_active', '=', True),
                ('connection_status', '=', 'success'),
            ], limit=1)
            return bool(config)
        except Exception:
            return False

    @api.model
    def _format_currency(self, amount, currency=None):
        """Format currency amount with appropriate abbreviation."""
        if not currency:
            currency = self.env.company.currency_id
        symbol = currency.symbol or '$'

        abs_amount = abs(amount)
        sign = '-' if amount < 0 else ''

        if abs_amount >= 1_000_000_000:
            return f"{sign}{symbol}{abs_amount / 1_000_000_000:.1f}B"
        elif abs_amount >= 1_000_000:
            return f"{sign}{symbol}{abs_amount / 1_000_000:.1f}M"
        elif abs_amount >= 1_000:
            return f"{sign}{symbol}{abs_amount / 1_000:.1f}K"
        else:
            return f"{sign}{symbol}{abs_amount:,.0f}"

    @api.model
    def _explain_change(self, metric_name, current, previous, unit=''):
        """Generate a simple explanation of change."""
        if not previous or previous == 0:
            return f"{metric_name}: No previous data for comparison"
        change = ((current - previous) / abs(previous)) * 100
        direction = 'up' if change > 0 else 'down'
        return f"{metric_name} {direction} {abs(change):.1f}% vs previous period"

    @api.model
    def _time_ago(self, dt):
        """Convert datetime to 'X ago' string."""
        if not dt:
            return ''
        now = fields.Datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return 'Just now'
        elif seconds < 3600:
            return f"{int(seconds // 60)} min ago"
        elif seconds < 86400:
            return f"{int(seconds // 3600)} hrs ago"
        else:
            return f"{int(seconds // 86400)} days ago"

    @api.model
    def _markdown_to_html(self, text):
        """Simple markdown to HTML conversion."""
        import re
        html = text
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = html.replace('\n', '<br/>')
        return html
