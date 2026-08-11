# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class PayrollAIReport(models.TransientModel):
    """
    PayAI Report Wizard — generates AI-narrated PDF payroll reports.
    Assembles data, calls GPT for executive summaries, and renders via QWeb.
    """

    _name = 'payroll.ai.report.wizard'
    _description = 'PayAI Report Generator'

    name = fields.Char(
        string='Report Title',
        default='PayAI Executive Report',
    )

    date_from = fields.Date(
        string='From Date',
        default=lambda self: fields.Date.today().replace(day=1),
        required=True,
    )

    date_to = fields.Date(
        string='To Date',
        default=lambda self: fields.Date.today(),
        required=True,
    )

    include_salary = fields.Boolean('Salary Distribution', default=True)
    include_headcount = fields.Boolean('Headcount Analysis', default=True)
    include_cost_trend = fields.Boolean('Cost Trend', default=True)
    include_forecast = fields.Boolean('Forecast', default=True)
    include_attendance = fields.Boolean('Attendance Summary', default=False)
    include_leaves = fields.Boolean('Leave Summary', default=False)
    include_anomalies = fields.Boolean('Anomaly Alerts', default=True)

    include_ai_narratives = fields.Boolean(
        'AI-Generated Narratives',
        default=False,
        help='Generate AI narrative summaries for each section. This makes multiple API calls and can take 30-60 seconds.',
    )

    report_format = fields.Selection([
        ('pdf', 'PDF Report'),
    ], default='pdf', string='Format', required=True)

    # Generated report data stored as JSON on the record
    report_json = fields.Text(string='Report Data (JSON)')

    def action_generate_report(self):
        """Generate the AI-narrated report."""
        self.ensure_one()

        # Collect all data sections
        sections = self._build_report_sections()

        # Generate AI executive summary (only if enabled)
        executive_summary = ''
        if self.include_ai_narratives:
            executive_summary = self._generate_executive_summary(sections)
        if not executive_summary:
            executive_summary = f'Payroll report for {self.env.company.name} covering {self.date_from.strftime("%d %b %Y")} to {self.date_to.strftime("%d %b %Y")}. Report includes {len(sections)} section(s) of payroll analytics data.'

        # Prepare report data and store on the record
        report_data = {
            'title': self.name,
            'date_from': self.date_from.strftime('%d %b %Y'),
            'date_to': self.date_to.strftime('%d %b %Y'),
            'generated_at': fields.Datetime.now().strftime('%d %b %Y %H:%M'),
            'generated_by': self.env.user.name,
            'company': self.env.company.name,
            'executive_summary': executive_summary,
            'sections': sections,
        }

        # Store on the record so QWeb can access it
        self.write({'report_json': json.dumps(report_data, default=str)})

        # Render PDF directly (bypasses Odoo 19 document layout wizard)
        import base64
        report = self.env.ref('pb_payroll_ai_insights.action_report_payai_executive')
        pdf_content, _content_type = report._render_qweb_pdf(report.report_name, self.ids)

        # Save as attachment
        filename = 'PayAI_Report_%s_%s.pdf' % (self.date_from, self.date_to)
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Download with proper filename
        download_url = '/web/content/%s/%s?download=true' % (
            attachment.id, filename,
        )
        return {
            'type': 'ir.actions.act_url',
            'url': download_url,
            'close': True,
        }

    def get_report_data(self):
        """Parse and return the stored report data for the QWeb template."""
        self.ensure_one()
        if self.report_json:
            try:
                return json.loads(self.report_json)
            except Exception:
                return {}
        return {}

    def _section_access(self, query_result):
        """The narrative half of a report section, when access decided it.

        The query layer runs with the READER's access rights (Phase D1), so a
        section can legitimately come back refused. Rendering it as an empty
        chart with no explanation would be the report quietly asserting that
        there is nothing there. The refusal sentence becomes the section's
        narrative instead, and the flag keeps `_generate_section_narratives`
        from overwriting it with prose about an empty list.
        """
        if query_result.get('access_refused'):
            return {'narrative': query_result.get('message', ''),
                    'access_refused': True}
        return {'narrative': '', 'access_refused': False}

    def _build_report_sections(self):
        """Build data for each enabled report section."""
        data_query = self.env['payroll.data.query']
        context = {}
        sections = []

        if self.include_salary:
            try:
                salary_data = data_query._query_salary_data('salary distribution', context)
                sections.append({
                    'title': 'Salary Distribution by Department',
                    'icon': 'fa-money',
                    'data': salary_data.get('data', {}),
                    'query_type': salary_data.get('query_type', ''),
                    **self._section_access(salary_data),
                })
            except Exception as e:
                _logger.warning("PayAI Report: salary section failed: %s", e)

        if self.include_headcount:
            try:
                headcount_data = data_query._query_headcount_data('headcount by department', context)
                sections.append({
                    'title': 'Headcount Analysis',
                    'icon': 'fa-users',
                    'data': headcount_data.get('data', {}),
                    'query_type': headcount_data.get('query_type', ''),
                    **self._section_access(headcount_data),
                })
            except Exception as e:
                _logger.warning("PayAI Report: headcount section failed: %s", e)

        if self.include_cost_trend:
            try:
                trend_data = data_query._query_trend_data('payroll cost trend monthly', context)
                sections.append({
                    'title': 'Payroll Cost Trend',
                    'icon': 'fa-line-chart',
                    'data': trend_data.get('data', {}),
                    'query_type': trend_data.get('query_type', ''),
                    **self._section_access(trend_data),
                })
            except Exception as e:
                _logger.warning("PayAI Report: trend section failed: %s", e)

        if self.include_forecast:
            try:
                forecast_data = data_query._query_forecast_data('forecast payroll costs', context)
                sections.append({
                    'title': 'Predictive Forecast',
                    'icon': 'fa-line-chart',
                    'data': forecast_data.get('data', {}),
                    'query_type': forecast_data.get('query_type', ''),
                    **self._section_access(forecast_data),
                })
            except Exception as e:
                _logger.warning("PayAI Report: forecast section failed: %s", e)

        if self.include_attendance:
            try:
                att_data = data_query._query_attendance_data('attendance summary', context)
                sections.append({
                    'title': 'Attendance Summary',
                    'icon': 'fa-clock-o',
                    'data': att_data.get('data', {}),
                    'query_type': att_data.get('query_type', ''),
                    **self._section_access(att_data),
                })
            except Exception:
                pass  # Module may not be installed

        if self.include_leaves:
            try:
                leave_data = data_query._query_leave_data('leave breakdown', context)
                sections.append({
                    'title': 'Leave Summary',
                    'icon': 'fa-calendar-times-o',
                    'data': leave_data.get('data', {}),
                    'query_type': leave_data.get('query_type', ''),
                    **self._section_access(leave_data),
                })
            except Exception:
                pass

        if self.include_anomalies:
            try:
                alerts = self.env['payroll.ai.pulse'].search([
                    ('state', 'in', ['new', 'acknowledged']),
                    ('create_date', '>=', self.date_from),
                ], order='severity desc, create_date desc', limit=10)

                if alerts:
                    alert_data = [{
                        'name': a.name,
                        'severity': a.severity,
                        'category': a.category,
                        'summary': a.summary or 'No AI summary yet.',
                        'deviation_pct': a.deviation_pct,
                    } for a in alerts]

                    sections.append({
                        'title': 'Anomaly Alerts',
                        'icon': 'fa-exclamation-triangle',
                        'data': alert_data,
                        'query_type': 'anomalies',
                        'narrative': '',
                    })
            except Exception as e:
                _logger.warning("PayAI Report: anomalies section failed: %s", e)

        # Generate AI narratives for each section (only if enabled)
        if self.include_ai_narratives:
            self._generate_section_narratives(sections)

        return sections

    def _generate_section_narratives(self, sections):
        """Generate AI narrative for each report section."""
        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return
            provider = config.get_provider_instance()
            if not provider:
                return
        except Exception:
            return

        for section in sections:
            if section.get('access_refused'):
                # Its narrative is the refusal, and its data is empty by
                # construction — nothing to send, nothing to say about it.
                continue
            try:
                prompt = f"""You are writing an executive payroll report section. Write a 3-4 sentence analytical narrative for this section:

Section: {section['title']}
Data: {json.dumps(section['data'], default=str)[:2000]}

Write in professional executive report style. Include key numbers, comparisons, and one actionable insight. Do NOT use bullet points or headers — write flowing prose."""

                narrative = provider.generate_text(prompt, max_tokens=300, temperature=0.5)
                section['narrative'] = narrative.strip()
            except Exception as e:
                section['narrative'] = f'Analysis could not be generated: {e}'
                _logger.warning("PayAI Report: narrative failed for %s: %s", section['title'], e)

    def _generate_executive_summary(self, sections):
        """Generate overall executive summary."""
        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return 'Executive summary not available — AI provider not configured.'
            provider = config.get_provider_instance()
            if not provider:
                return 'Executive summary not available.'
        except Exception:
            return 'Executive summary generation failed.'

        sections_overview = "\n".join([
            f"- {s['title']}: {json.dumps(s['data'], default=str)[:500]}"
            for s in sections
        ])

        prompt = f"""You are PayAI, writing an executive summary for a payroll report covering {self.date_from} to {self.date_to}.

Report sections and data:
{sections_overview}

Write a compelling 4-5 sentence executive summary that:
1. Highlights the most important finding
2. Notes any concerning trends
3. Provides a forward-looking recommendation
Write in formal executive report style."""

        try:
            return provider.generate_text(prompt, max_tokens=400, temperature=0.5).strip()
        except Exception as e:
            return f'Executive summary generation failed: {e}'
