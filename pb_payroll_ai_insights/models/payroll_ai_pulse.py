# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

from .ai_redaction import redact_names, restore_names

_logger = logging.getLogger(__name__)

#: WDGAP QF1 — most severe first. The selection sorts as TEXT ("warning" >
#: "info" > "critical"), so order is always worked out with this, in Python.
SEVERITY_RANK = {'info': 1, 'warning': 2, 'critical': 3}

#: How much worse an acknowledged alert has to get before it shows again on
#: Home: 5 more percentage points (cost, overtime) or 5 more of the thing
#: counted (people, leave requests) — or a higher severity.
REOPEN_STEP = 5.0

#: Alerts measured in percent; the others are counts.
PCT_CATEGORIES = ('cost', 'overtime')


def redacted_details(raw):
    """One alert's `details` as a JSON string with the people taken out.

    Returns (text, mapping). The field is a JSON string written by the
    detectors below; it is parsed so the names can be found by KEY rather than
    by pattern-matching prose, and re-serialised. A `details` that is not valid
    JSON — which nothing here writes, but a migration or a hand edit could — is
    treated as opaque text and gets the same name-free treatment through the
    empty mapping plus the generic patterns.

    Module level and not a model method, deliberately: it is the half of the
    pulse's egress that can be executed without a database, and the offline
    harness runs the real function rather than a copy of it.
    """
    raw = raw or ''
    if not raw.strip():
        return '', {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        redacted, mapping = redact_names({'details': raw})
        return redacted['details'], mapping
    redacted, mapping = redact_names(parsed)
    return json.dumps(redacted, default=str), mapping


def pulse_summary_prompt(name, category, severity, metric, baseline,
                         deviation, details):
    """The exact string the Pulse sends per alert, as a pure function.

    `details` must ALREADY be redacted. Two of the four detectors put people
    in it by name — the joiners and the leavers of the week — and until
    LEARNOS Phase 4 that dict went into this prompt verbatim.

    Everything else here is a title, a word from a selection field or a
    number. The TITLE is deliberately not redacted: the four detectors build
    it from a percentage, a count or a DEPARTMENT, never from a person, and a
    summary about "[person-1] Spike" would be unreadable for no gain.
    """
    return f"""You are PayAI, an HR analytics assistant. Write a brief 2-3 sentence executive summary for this payroll anomaly alert:

Alert: {name}
Category: {category}
Severity: {severity}
Current Value: {metric}
Baseline Value: {baseline}
Deviation: {deviation}%
Details: {details}

Names in the details have been replaced with placeholders of the form
[person-1]. Use those placeholders exactly as they appear. Do not invent real
names for them.

Write a clear, actionable summary. Include what happened, why it matters, and a recommended action. Keep it concise."""


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

    # WDGAP QF1 — an alert belongs to ONE company, there is ONE open alert per
    # thing, and "Got it" remembers how bad it was when it was pressed.
    company_id = fields.Many2one('res.company', string='Company', index=True)
    dedupe_key = fields.Char(
        string='Same-alert key', index=True, copy=False,
        help='Company, kind and department: one open alert per key.')
    direction = fields.Char(
        string='Direction',
        help='Which way it moved: up, down, joined, left, approved.')
    ack_level = fields.Float(
        string='Level when put away',
        help='How bad it was when somebody pressed "Got it".')
    ack_severity = fields.Char(
        string='Severity when put away',
        help='Its severity when somebody pressed "Got it".')

    @api.model
    def _badness(self, vals):
        """The figure "worse" is measured on: percentage points for cost and
        overtime, the count for people and leave."""
        if vals.get('category') in PCT_CATEGORIES:
            return abs(vals.get('deviation_pct') or 0.0)
        return abs(vals.get('metric_value') or 0.0)

    def action_acknowledge(self):
        for alert in self:
            alert.write({
                'state': 'acknowledged',
                'ack_level': self._badness({
                    'category': alert.category,
                    'deviation_pct': alert.deviation_pct,
                    'metric_value': alert.metric_value}),
                'ack_severity': alert.severity,
            })

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

        WDGAP QF1 — once PER COMPANY, each detector reading that company's
        payslips, people and leave only. A condition that still holds updates
        its one open alert instead of adding another every day; a condition
        that has gone resolves its alert. Returns the number of NEW alerts.
        """
        _logger.info("PayAI Pulse: Starting anomaly detection...")
        alerts_created = 0
        detectors = (
            ('cost', self._detect_payroll_cost_anomalies),
            ('headcount', self._detect_headcount_changes),
            ('overtime', self._detect_overtime_spikes),
            ('leave', self._detect_leave_anomalies),
        )
        for company in self._pulse_companies():
            seen, checked = set(), set()
            for category, detector in detectors:
                try:
                    with self.env.cr.savepoint():
                        alerts_created += detector(company, seen)
                    checked.add(category)
                except Exception as e:
                    _logger.error("PayAI Pulse: %s detection failed for "
                                  "company %s: %s", category, company.id, e)
            self._resolve_gone(company, checked, seen)

        _logger.info("PayAI Pulse: Detection complete. %d alerts created.", alerts_created)

        # Generate AI summaries for new alerts
        if alerts_created > 0:
            self._generate_ai_summaries()

        return alerts_created

    @api.model
    def _pulse_companies(self):
        """The companies that have people (and so, possibly, payslips)."""
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        return self.env['res.company'].sudo().search([]).filtered(
            lambda c: Employee.search_count([('company_id', '=', c.id)],
                                            limit=1))

    @api.model
    def _raise_alert(self, company, vals, seen, sub=''):
        """Create the alert, or refresh the one already open for the same
        thing. Returns 1 when a new alert was created, else 0.

        An acknowledged alert comes back (state "new") only when it is worse
        by REOPEN_STEP or its severity rose since "Got it" was pressed."""
        category = vals['category'] + ('.' + sub if sub else '')
        key = '%s:%s:%s' % (company.id, category,
                            vals.get('department_id') or 'none')
        seen.add(key)
        vals = dict(vals, company_id=company.id, dedupe_key=key)
        Pulse = self.sudo()
        alert = Pulse.search([('dedupe_key', '=', key),
                              ('state', 'in', ('new', 'acknowledged'))],
                             order='id desc', limit=1)
        if not alert:
            Pulse.create(vals)
            return 1
        update = dict(vals)
        if alert.state == 'acknowledged':
            was = alert.ack_severity or alert.severity
            worse = (self._badness(vals) >= (alert.ack_level or 0.0) + REOPEN_STEP
                     or SEVERITY_RANK.get(vals.get('severity'), 0)
                     > SEVERITY_RANK.get(was, 0))
            if worse:
                update['state'] = 'new'
        alert.write(update)
        return 0

    @api.model
    def _resolve_gone(self, company, checked, seen):
        """Open alerts of this company whose condition no longer holds (their
        detector ran and did not raise them again) are resolved. Old rows
        without a key are left exactly as they are."""
        if not checked:
            return 0
        stale = self.sudo().search([
            ('company_id', '=', company.id),
            ('state', 'in', ('new', 'acknowledged')),
            ('dedupe_key', '!=', False),
            ('category', 'in', sorted(checked)),
        ]).filtered(lambda a: a.dedupe_key not in seen)
        stale.write({'state': 'resolved'})
        return len(stale)

    def _detect_payroll_cost_anomalies(self, company, seen):
        """Compare current month payroll cost vs previous 3-month average."""
        Payslip = self.env['hr.payslip'].sudo()
        today = fields.Date.today()
        mine = [('company_id', '=', company.id)]

        # Current month
        month_start = today.replace(day=1)
        current_payslips = Payslip.search(mine + [
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
            prev_payslips = Payslip.search(mine + [
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

            return self._raise_alert(company, {
                'name': f'Payroll Cost {direction.title()} by {abs(deviation):.1f}%',
                'severity': severity,
                'category': 'cost',
                'direction': 'up' if deviation > 0 else 'down',
                'metric_value': current_cost,
                'baseline_value': avg_cost,
                'deviation_pct': round(deviation, 2),
                'details': json.dumps({
                    'current_month_cost': current_cost,
                    'avg_3m_cost': avg_cost,
                    'previous_months': prev_costs,
                }),
            }, seen)
        return 0

    def _detect_headcount_changes(self, company, seen):
        """Detect significant headcount changes (new hires, departures)."""
        Employee = self.env['hr.employee'].sudo()
        today = fields.Date.today()
        last_week = today - timedelta(days=7)
        mine = [('company_id', '=', company.id)]

        # New employees this week
        new_employees = Employee.search(mine + [
            ('create_date', '>=', last_week),
        ])
        # Departed employees this week (archived)
        departed = Employee.with_context(active_test=False).search(mine + [
            ('active', '=', False),
            ('write_date', '>=', last_week),
        ])

        alerts = 0
        if len(new_employees) >= 3:
            alerts += self._raise_alert(company, {
                'name': f'{len(new_employees)} New Employees Joined This Week',
                'severity': 'info',
                'category': 'headcount',
                'direction': 'joined',
                'metric_value': len(new_employees),
                'details': json.dumps({
                    'new_employees': [
                        {'name': e.name, 'department': e.department_id.name or 'Unassigned'}
                        for e in new_employees[:10]
                    ],
                }),
            }, seen, sub='joined')

        if len(departed) >= 2:
            alerts += self._raise_alert(company, {
                'name': f'{len(departed)} Employees Departed This Week',
                'severity': 'warning',
                'category': 'headcount',
                'direction': 'left',
                'metric_value': len(departed),
                'details': json.dumps({
                    'departed': [
                        {'name': e.name, 'department': e.department_id.name or 'Unassigned'}
                        for e in departed[:10]
                    ],
                }),
            }, seen, sub='left')

        return alerts

    def _detect_overtime_spikes(self, company, seen):
        """Detect departments with unusually high overtime."""
        Payslip = self.env['hr.payslip'].sudo()
        today = fields.Date.today()
        month_start = today.replace(day=1)
        mine = [('company_id', '=', company.id)]

        # Current month overtime by department
        payslips = Payslip.search(mine + [
            ('state', 'in', ['done', 'paid']),
            ('date_from', '>=', month_start),
        ])

        # Keyed on the DEPARTMENT name — a record value used as a key, and so
        # invisible to `redact_names`, which rewrites values only. A department
        # is not a person, so this is safe; see the note in
        # `_detect_leave_anomalies` and the residual list in ai_redaction.py.
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
                prev_ps = Payslip.search(mine + [
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
                        dept_rec = self.env['hr.department'].sudo().search([
                            ('name', '=', dept),
                            ('company_id', 'in', [company.id, False]),
                        ], limit=1)
                        alerts += self._raise_alert(company, {
                            'name': f'Overtime Spike in {dept}: +{deviation:.0f}%',
                            'severity': 'warning',
                            'category': 'overtime',
                            'direction': 'up',
                            'department_id': dept_rec.id if dept_rec else False,
                            'metric_value': ot_total,
                            'baseline_value': prev_ot,
                            'deviation_pct': round(deviation, 2),
                            'details': json.dumps({
                                'department': dept,
                                'current_ot': ot_total,
                                'previous_ot': prev_ot,
                            }),
                        }, seen)
        return alerts

    def _detect_leave_anomalies(self, company, seen):
        """Detect unusually high leave rates."""
        if not self._is_module_installed('hr_holidays'):
            return 0

        Leave = self.env['hr.leave'].sudo()
        today = fields.Date.today()
        week_start = today - timedelta(days=7)

        # Leaves this week
        current_leaves = Leave.search([
            ('employee_company_id', '=', company.id),
            ('state', '=', 'validate'),
            ('date_from', '>=', week_start),
        ])

        if len(current_leaves) >= 5:
            # Group by type
            # A DICTIONARY KEY BUILT FROM A RECORD. `redact_names` rewrites
            # VALUES and never keys — keys are normally our own field names,
            # and a payload with renamed keys is one the model cannot read.
            # These keys are the leave TYPE's name, which is not a person, so
            # the guarantee holds today. A detector that ever keys this on an
            # employee would leak straight past the redaction. Same note at
            # the overtime detector, which keys on the department.
            type_counts = {}
            for lv in current_leaves:
                lt = lv.holiday_status_id.name or 'Other'
                type_counts[lt] = type_counts.get(lt, 0) + 1

            return self._raise_alert(company, {
                'name': f'{len(current_leaves)} Approved Leaves This Week',
                'severity': 'info' if len(current_leaves) < 10 else 'warning',
                'category': 'leave',
                'direction': 'approved',
                'metric_value': len(current_leaves),
                'details': json.dumps({
                    'total_leaves': len(current_leaves),
                    'by_type': type_counts,
                }),
            }, seen)
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
        """Generate AI-powered narrative summaries for new alerts.

        TICKET 4, PULSE HALF (LEARNOS Phase 4). This used to ask
        `payroll.ai.config` for a provider factory under a name that model has
        never had, inside a bare `except Exception` — which turned a typo into
        a feature that was silently, permanently off. Every alert since it
        shipped has had an empty summary and nothing anywhere said so. The
        method that exists is `get_provider`, and it is the one called below.

        NOTE TO THE NEXT READER: do not write the old name here, not even to
        explain this. `tests/test_egress.py` pins its absence from this whole
        file, comments included, because a commented-out call is a template.

        Fixing it TURNS AN EGRESS PATH ON, which is why the redaction below is
        part of the same change rather than a follow-up: two of the four
        detectors list the week's joiners and leavers by name, and the moment
        this call works those names are on a wire.
        """
        new_alerts = self.search([('state', '=', 'new'), ('summary', '=', False)])
        if not new_alerts:
            return

        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return
            provider = config.get_provider()
            if not provider:
                return
        except Exception:
            _logger.info("PayAI Pulse: no usable provider for alert summaries",
                         exc_info=True)
            return

        for alert in new_alerts:
            try:
                details, mapping = redacted_details(alert.details)
                prompt = pulse_summary_prompt(
                    alert.name, alert.category, alert.severity,
                    alert.metric_value, alert.baseline_value,
                    alert.deviation_pct, details)
                summary = provider.generate_text(prompt, max_tokens=200, temperature=0.5)
                # STORED RESTORED. The database is inside the trust boundary
                # and the alert is read by people who can already open the
                # employee records behind it; the wire to the provider is what
                # was outside. A stored placeholder would also rot — the
                # mapping is per-call and nothing could resolve it later.
                alert.write({'summary': restore_names(summary.strip(), mapping)})
            except Exception as e:
                _logger.warning("PayAI Pulse: AI summary failed for alert %s: %s", alert.id, e)

    # =========================================================================
    # RPC Methods for Frontend
    # =========================================================================

    @api.model
    def rpc_get_active_alerts(self, limit=10):
        """Get recent unresolved alerts for the dashboard."""
        # PAYAI P0 — the detector reads payslips, people and leave as sudo
        # (it runs from a cron). The READER must not inherit that: an alert
        # is a department's payroll figure in a sentence, and every internal
        # user is a PayAI user. Whoever may not open a payslip gets no alerts.
        if not self.env['hr.payslip'].has_access('read'):
            return []
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
    def home_alerts(self, limit=3):
        """WDGAP QF1 — what Home's "PayAI noticed" card shows.

        Open, not yet acknowledged alerts of the reader's companies only (the
        record rule says the same; this says it again, explicitly), most
        severe first, then the newest. Facts, never sentences: the browser
        builds the words in the reader's language. NO `details` (the
        headcount detector lists people by name there), no stored English
        title, no summary. Old rows written before alerts had a company are
        never returned. Whoever may not open a payslip gets nothing — the
        same rule as `rpc_get_active_alerts`.
        """
        if not self.env['hr.payslip'].has_access('read'):
            return []
        try:
            limit = max(0, min(int(limit or 3), 10))
        except (TypeError, ValueError):
            limit = 3
        rows = self.search([
            ('state', '=', 'new'),
            ('dedupe_key', '!=', False),
            ('company_id', 'in', self.env.companies.ids),
        ], order='write_date desc, id desc', limit=60)
        rows = sorted(rows, key=lambda a: (
            -SEVERITY_RANK.get(a.severity, 0),
            -(a.write_date.timestamp() if a.write_date else 0), -a.id))
        return [{
            'id': a.id,
            'category': a.category,
            'severity': a.severity,
            'direction': a.direction or '',
            'pct': round(abs(a.deviation_pct or 0.0), 1),
            'value': a.metric_value or 0.0,
            'baseline': a.baseline_value or 0.0,
            'department': a.department_id.sudo().name or '',
            'since': fields.Date.to_string(a.create_date.date())
            if a.create_date else '',
        } for a in rows[:limit]]

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
