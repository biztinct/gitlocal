# -*- coding: utf-8 -*-
"""The AI-narrated PDF — and the egress it switched on when it was repaired.

THIS FILE'S TWO PROVIDER CALLS WERE DEAD FOR FOUR PHASES. Both asked
`payroll.ai.config` for a provider-factory method it does not have — the
misspelling is deliberately NOT written out here, because `tests/test_egress.py`
greps this whole file for it and a comment showing the next reader how to
re-add it is halfway to somebody re-adding it. The call sat inside a
`try/except` that swallowed the AttributeError, so the section narratives never
generated and the executive summary always printed "Executive summary
generation failed."

LEARNOS Phase 4 found them and deliberately LEFT them dead, pinned by an
exact-count test, with the reason written down: `_generate_section_narratives`
puts `json.dumps(section['data'])` in a prompt, and the salary section's data
is a list of employees with their job titles and their wages. Repairing the
lookup without redacting the payload would have switched on a third
unredacted egress path in the same commit that closed two.

Phase 6 does both halves in one change, which is the ruling:

  * the lookup is `get_provider()`, the method that exists;
  * every section's data goes through `redact_names` before it is serialised,
    with ONE mapping shared across the sections of a report so that
    "[person-1]" means the same person in the salary narrative and in the
    executive summary;
  * the narrative comes back through `restore_names`, because the READER of
    this PDF is the person who generated it and has already passed the query
    layer's access gate — the provider was never entitled to the names, and
    the reader always was;
  * the prompts are PURE FUNCTIONS at module level, so "no employee name is
    in this prompt" is asserted against the actual string with no provider, no
    network and no database (`tests/test_redaction.py`).

A section that came back access-refused is skipped exactly as before: its
narrative is the refusal sentence and its data is empty by construction.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

from .ai_redaction import (
    PERSON_KEYS, collect_names, extend_mapping, redact_names, redact_text,
    restore_names,
)

_logger = logging.getLogger(__name__)

# How much of a section's data the model is shown. Applied to the REDACTED
# serialisation, never to the raw one — truncating first and redacting second
# would mean the length of a name decided what got cut.
SECTION_DATA_CHARS = 2000
SUMMARY_DATA_CHARS = 500

# Told to the model in both prompts, in the same words the other two egress
# paths use. If the placeholder shape ever changes, every prompt that
# describes it has to change with it — `test_egress::test_03c` pins that.
_PLACEHOLDER_NOTE = """Names have been replaced with placeholders of the form
[person-1]. Use those placeholders exactly as they appear. Do not invent real
names for them and do not guess who they are."""


# Detectors whose summaries can name people, read off the pulse: only
# `_detect_headcount_changes` writes person names into `details`. This is NOT
# the guard — the guard is the mapping — it decides when an EMPTY name set is
# suspicious rather than ordinary.
PERSON_NAMING_CATEGORIES = ('headcount',)


def alert_names(details_raw):
    """(names in this alert's details, parsed details or None)."""
    raw = (details_raw or '').strip()
    if not raw:
        return [], None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return [], None
    return collect_names(parsed), parsed


def summary_is_traceable(category, parsed, names):
    """Can every name this sentence might carry be in the mapping?

    Not a name detector — there is no honest one, and one that guessed would
    either drop every summary or miss the one that mattered. It is a
    PROVENANCE question with two answers that mean no: the details did not
    parse (so nothing could be collected from them), or the detector is one
    that names people and its details named none, which means the sentence and
    the payload no longer come from the same place.
    """
    if parsed is None:
        return False
    if not names and category in PERSON_NAMING_CATEGORIES:
        return False
    return True


def alert_rows(raws, mapping=None):
    """([row], mapping) — the anomaly section, with the prose accounted for."""
    mapping = dict(mapping or {})
    rows = []
    for raw in raws:
        names, parsed = alert_names(raw.get('details'))
        mapping = extend_mapping(names, mapping)
        summary = (raw.get('summary') or '').strip()
        if summary and summary_is_traceable(raw.get('category'), parsed, names):
            summary = redact_text(summary, mapping)
        elif summary:
            _logger.info(
                "PayAI Report: alert %s keeps its summary out of the prompt — "
                "its details do not account for the names it could contain.",
                raw.get('id'))
            summary = ''
        rows.append({
            # `name` is the alert TITLE — "2 New Employees Joined This Week" —
            # built by the detectors from a count, a percentage or a
            # department, never from a person. It is excluded from the
            # collector below for exactly that reason: collecting it produced
            # "[person-3]" as a section heading, which is unreadable and
            # protects nobody.
            'name': raw.get('name'),
            'severity': raw.get('severity'),
            'category': raw.get('category'),
            'summary': summary or 'No AI summary available.',
            'deviation_pct': raw.get('deviation_pct'),
        })
    # A second pass over the finished rows, with `name` excluded from the
    # collector: it catches a person named in any OTHER string here, and the
    # summaries are already placeholder-only by now.
    return redact_names(rows, person_keys=PERSON_KEYS - {'name'},
                        mapping=mapping)


def redact_sections(sections, mapping=None):
    """([(section, data_json)], mapping) — the ONE place a report is redacted.

    Both loops go through this: the per-section narratives and the executive
    summary. That is not tidiness, it is the guarantee — one accumulator means
    the same employee is the same placeholder everywhere in the document, and
    a `restore_names` at the end of either loop can put every one of them
    back. The first draft had a loop in each method and a claim in a comment.

    Access-refused sections are LEFT OUT. Their data is empty by construction
    and their narrative is already the refusal sentence; sending an empty list
    to be narrated is asking a model to write prose about nothing.

    Module level and pure, so the property "no name is in this string" is
    assertable with no provider, no network and no database.
    """
    mapping = dict(mapping or {})
    out = []
    for section in sections:
        if section.get('access_refused'):
            continue
        redacted, mapping = redact_names(section.get('data') or {},
                                         mapping=mapping)
        out.append((section,
                    json.dumps(redacted, default=str, ensure_ascii=False)))
    return out, mapping


def report_section_prompt(title, data_json):
    """The exact string one report section sends. `data_json` is ALREADY
    redacted; this builder cleans nothing, for the same reason
    `data_query_prompt` does not — a builder that quietly launders its inputs
    is a builder whose caller stops thinking about them."""
    return f"""You are writing an executive payroll report section. Write a 3-4 sentence analytical narrative for this section:

Section: {title}
Data: {data_json}

Write in professional executive report style. Include key numbers, comparisons, and one actionable insight. Do NOT use bullet points or headers — write flowing prose.

{_PLACEHOLDER_NOTE}"""


def report_executive_prompt(date_from, date_to, sections_overview):
    """The exact string the executive summary sends. Same contract."""
    return f"""You are PayAI, writing an executive summary for a payroll report covering {date_from} to {date_to}.

Report sections and data:
{sections_overview}

Write a compelling 4-5 sentence executive summary that:
1. Highlights the most important finding
2. Notes any concerning trends
3. Provides a forward-looking recommendation
Write in formal executive report style.

{_PLACEHOLDER_NOTE}"""


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

        # ONE PLACEHOLDER TABLE FOR THE WHOLE REPORT, created here and threaded
        # through everything below it. The first Phase 6 draft claimed this and
        # did not do it: the narratives built one mapping and the executive
        # summary built another, so the same employee could be [person-1] in a
        # section and [person-4] in the summary. Nothing leaked, but the claim
        # was false and the restore was luckier than it looked.
        mapping = {}

        # Collect all data sections
        sections = self._build_report_sections(mapping)

        # Generate AI executive summary (only if enabled)
        executive_summary = ''
        if self.include_ai_narratives:
            executive_summary = self._generate_executive_summary(sections, mapping)
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

    def _build_report_sections(self, mapping=None):
        """Build data for each enabled report section.

        `mapping` is the report's one placeholder table. It is MUTATED in
        place — the anomalies section extends it while it is being built (see
        `_alert_rows`), and the narrative pass extends it again — so the
        caller's dict is the accumulator and there is exactly one.
        """
        data_query = self.env['payroll.data.query']
        context = {}
        sections = []
        mapping = {} if mapping is None else mapping

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
                    sections.append({
                        'title': 'Anomaly Alerts',
                        'icon': 'fa-exclamation-triangle',
                        'data': self._alert_rows(alerts, mapping),
                        'query_type': 'anomalies',
                        'narrative': '',
                        # The rows are already redacted, by a rule the generic
                        # collector cannot reproduce. Redacting them a second
                        # time is harmless, but the flag says which pass owns
                        # them so the next reader does not add a third.
                        'pre_redacted': True,
                    })
            except Exception as e:
                _logger.warning("PayAI Report: anomalies section failed: %s", e)

        # Generate AI narratives for each section (only if enabled)
        if self.include_ai_narratives:
            self._generate_section_narratives(sections, mapping)

        return sections

    # ------------------------------------------------------------------
    # THE ANOMALY SECTION, AND THE HOLE THE PHASE 6 REVIEW FOUND IN IT
    #
    # An alert's `summary` is PROSE A MODEL WROTE, stored with the names put
    # back into it: `payroll_ai_pulse._generate_ai_summaries` redacts the
    # details, asks for a sentence, and calls `restore_names` before saving.
    # That is right for the database, which is inside the trust boundary — and
    # it means the stored sentence says "Bùi Anh Tuấn and Lê Thu Trang joined
    # this week" under the key `summary`, which is not a person key, so
    # `collect_names` never sees it and `redact_names` had nothing to remove.
    # The whole section went out with the joiners named in full.
    #
    # The fix is provenance. Every name a generated summary can contain came
    # from THAT alert's own `details`, so the details are redacted first — into
    # the report's shared mapping — and the summary is then redacted against
    # the extended mapping, which by construction knows every one of them.
    #
    # WHEN THE PROVENANCE CANNOT BE CHECKED, THE SUMMARY DOES NOT GO. A details
    # field that is missing or unparseable, or a person-naming detector whose
    # details yielded no names at all, means the sentence and the payload no
    # longer come from the same place — and a summary is not worth guessing
    # over. The row keeps its title, severity, category and deviation, which is
    # enough to narrate from.
    # ------------------------------------------------------------------

    @api.model
    def _alert_rows(self, alerts, mapping):
        """Alert rows for the prompt, with the people taken out of the prose.

        Records in, plain dicts out, and then `alert_rows` — which is a pure
        function at module level, for the same reason the prompt builders are:
        this is a privacy rule, and a privacy rule that only executes on a
        database is a privacy rule nobody has run.
        """
        rows, extended = alert_rows([{
            'name': alert.name,
            'severity': alert.severity,
            'category': alert.category,
            'summary': alert.summary,
            'deviation_pct': alert.deviation_pct,
            'details': alert.details,
            'id': alert.id,
        } for alert in alerts], mapping)
        mapping.update(extended)
        return rows

    def _narrative_provider(self):
        """`get_provider` — the method `payroll.ai.config` actually has.

        Kept in one place so there is exactly one lookup to read and exactly
        one to fix. It returns None rather than raising, because a report
        without narratives is a report; the difference from the four phases
        this spent broken is that the failure is now LOGGED.
        """
        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return None
            return config.get_provider()
        except Exception as exc:                                # noqa: BLE001
            _logger.warning("PayAI Report: no usable provider (%s)", exc)
            return None

    def _generate_section_narratives(self, sections, mapping=None):
        """Generate AI narrative for each report section, names out and back.

        `mapping` is the report's accumulator and is UPDATED IN PLACE, so the
        executive summary that runs afterwards inherits every placeholder this
        pass issued.
        """
        provider = self._narrative_provider()
        if provider is None:
            return

        mapping = {} if mapping is None else mapping
        prepared, extended = redact_sections(sections, mapping)
        mapping.update(extended)
        for section, data_json in prepared:
            try:
                prompt = report_section_prompt(
                    section['title'], data_json[:SECTION_DATA_CHARS])
                narrative = provider.generate_text(prompt, max_tokens=300, temperature=0.5)
                section['narrative'] = restore_names(narrative.strip(), mapping)
            except Exception as e:
                section['narrative'] = f'Analysis could not be generated: {e}'
                _logger.warning("PayAI Report: narrative failed for %s: %s", section['title'], e)

    def _generate_executive_summary(self, sections, mapping=None):
        """Generate overall executive summary, names out and back."""
        provider = self._narrative_provider()
        if provider is None:
            return 'Executive summary not available — AI provider not configured.'

        mapping = {} if mapping is None else mapping
        prepared, extended = redact_sections(sections, mapping)
        mapping.update(extended)
        lines = ["- %s: %s" % (section['title'], data_json[:SUMMARY_DATA_CHARS])
                 for section, data_json in prepared]
        prompt = report_executive_prompt(
            self.date_from, self.date_to, "\n".join(lines))

        try:
            summary = provider.generate_text(prompt, max_tokens=400, temperature=0.5)
            return restore_names(summary.strip(), mapping)
        except Exception as e:
            return f'Executive summary generation failed: {e}'
