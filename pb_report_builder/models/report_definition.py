# -*- coding: utf-8 -*-
"""Saved reports (`pb.report.definition`) and the ready-made examples.

Cloned from the Explorer's saved views (`pb_explorer/models/pb_explorer_view.py`,
`security/pb_explorer_rules.xml`): private to whoever saved them unless they
share them with everyone who can open reports; changed only by their owner;
50 per owner, names up to 80 characters.

A saved report is a QUESTION, never an answer: it keeps the cleaned spec, and
every open runs it again AS THE READER through `pb.report.builder._clean_spec`
— so a shared report drops the columns the reader may not see (with a note)
and narrows to the reader's own records and companies. It never widens.

Examples are built from code when they are asked for (nothing is stored, so
installing creates no records); an example whose subject the reader cannot
open is not offered.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

NAME_MAX = 80
REPORT_CAP = 50


class PbReportDefinition(models.Model):
    _name = 'pb.report.definition'
    _description = 'Saved report'
    _order = 'sequence, last_opened desc, id desc'

    name = fields.Char(required=True)
    user_id = fields.Many2one('res.users', string='Saved by', required=True, index=True,
                              ondelete='cascade', default=lambda self: self.env.user)
    shared = fields.Boolean(string='Everyone who can open reports')
    subject = fields.Char(string='Each row is', required=True)
    spec = fields.Json(string='Layout', default=dict)
    sequence = fields.Integer(default=10)
    last_opened = fields.Datetime(string='Last opened', readonly=True)

    # ------------------------------------------------------------- helpers
    @api.model
    def _pbrb_clean_name(self, name):
        name = ' '.join(str(name or '').split())[:NAME_MAX]
        if not name:
            raise UserError(self.env._("Give the report a name."))
        return name

    def _pbrb_own(self):
        """Refuse, in words, a change to somebody else's report. The record
        rules refuse it anyway; this only makes the refusal readable."""
        for report in self:
            if report.user_id.id != self.env.uid and \
                    not self.env.user.has_group('base.group_system'):
                raise AccessError(self.env._("Only the person who saved this report can "
                                             "change it. Make a copy to change it your way."))

    def _pbrb_payload(self, subjects=None):
        self.ensure_one()
        subjects = subjects if subjects is not None else \
            self.env['pb.report.builder']._pbrb_subjects()
        subject = subjects.get(self.subject) or {}
        spec = self.spec if isinstance(self.spec, dict) else {}
        mine = self.user_id.id == self.env.uid
        return {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'subject_label': subject.get('label') or '',
            'icon': subject.get('icon') or 'table',
            'columns': len(spec.get('columns') or []),
            'grouped': bool(spec.get('group_by')),
            'shared': bool(self.shared),
            'mine': mine,
            'owner': '' if mine else (self.user_id.name or ''),
            'last_opened': format_date(self.env, self.last_opened) if self.last_opened else '',
            'updated': format_date(self.env, self.write_date) if self.write_date else '',
        }

    # ------------------------------------------------------------- the C1
    def _pbxl_table(self):
        """DOCSTUDIO ledger C1 — this report as a finished table, read as
        the CALLING user: {'title', 'columns', 'rows', 'truncated', 'note'}."""
        self.ensure_one()
        self.check_access('read')
        builder = self.env['pb.report.builder']
        builder._require()
        table = builder._pbrb_table(dict(self.spec or {}, subject=self.subject),
                                    title=self.name, strict=False)
        return {key: table[key] for key in ('title', 'columns', 'rows', 'truncated', 'note')}


class PbReportBuilderSaved(models.AbstractModel):
    """The facade's saved-report and example entry points."""
    _inherit = 'pb.report.builder'

    @api.model
    def _report(self, report_id, write=False):
        Report = self.env['pb.report.definition']
        try:
            report = Report.browse(int(report_id or 0)).exists()
            if report:
                report.check_access('read')
        except (AccessError, TypeError, ValueError):
            report = Report
        if not report:
            raise UserError(self.env._("This report is no longer available. It may have been "
                                       "deleted, or it is no longer shared with you."))
        if write:
            report._pbrb_own()
        return report

    @api.model
    def my_reports(self):
        """Mine first, then the ones shared with me — newest first."""
        self._require()
        subjects = self._pbrb_subjects()
        open_keys = {s['key'] for s, ok, why in self._subjects_for_reader() if ok}
        Report = self.env['pb.report.definition']
        out = []
        for report in Report.search([], order='last_opened desc, write_date desc, id desc',
                                    limit=200):
            item = report._pbrb_payload(subjects)
            item['locked'] = report.subject not in open_keys
            out.append(item)
        out.sort(key=lambda r: 0 if r['mine'] else 1)
        return out

    @api.model
    def save_report(self, name, spec, shared=False):
        """A new report owned by the reader; returns its card."""
        self._require()
        Report = self.env['pb.report.definition']
        if Report.search_count([('user_id', '=', self.env.uid)]) >= REPORT_CAP:
            raise UserError(self.env._(
                "You already have %(cap)s saved reports. Delete one you no longer use first.",
                cap=REPORT_CAP))
        clean, subject, cols, notes = self._clean_spec(spec)
        report = Report.create({
            'name': Report._pbrb_clean_name(name),
            'subject': subject['key'],
            'spec': clean,
            'shared': bool(shared),
            'user_id': self.env.uid,
            'last_opened': fields.Datetime.now(),
        })
        return report._pbrb_payload()

    @api.model
    def update_report(self, report_id, vals):
        """Rename, share or stop sharing, or save the new layout of one of
        your own reports."""
        self._require()
        report = self._report(report_id, write=True)
        vals = vals if isinstance(vals, dict) else {}
        clean = {}
        if 'name' in vals:
            clean['name'] = report._pbrb_clean_name(vals['name'])
        if 'shared' in vals:
            clean['shared'] = bool(vals['shared'])
        if 'spec' in vals:
            spec, subject, cols, notes = self._clean_spec(vals['spec'])
            clean.update({'spec': spec, 'subject': subject['key']})
        if clean:
            report.write(clean)
        return report._pbrb_payload()

    @api.model
    def remove_report(self, report_id):
        self._require()
        report = self._report(report_id, write=True)
        report.unlink()
        return True

    @api.model
    def duplicate_report(self, report_id, name=None):
        """A copy the reader owns, of any report they can open (theirs or a
        shared one). The copy keeps only what THIS reader may see."""
        self._require()
        report = self._report(report_id)
        spec = dict(report.spec or {}, subject=report.subject)
        clean, subject, cols, notes = self._clean_spec(spec, strict=False)
        copy_name = name or self.env._("%(name)s (copy)", name=report.name)
        return self.save_report(copy_name[:NAME_MAX], clean, shared=False)

    @api.model
    def open_report(self, report_id):
        """The saved report, cleaned for the reader, ready to run, with a
        plain note when part of it is hidden from them. Never a traceback."""
        self._require()
        try:
            report = self._report(report_id)
        except UserError as exc:
            return {'ok': False, 'msg': exc.args[0]}
        spec = dict(report.spec or {}, subject=report.subject)
        try:
            clean, subject, cols, notes = self._clean_spec(spec, strict=False)
        except AccessError as exc:
            return {'ok': False, 'msg': exc.args[0]}
        except UserError:
            return {'ok': False, 'msg': self.env._("This report can no longer be opened here.")}
        if report.user_id.id == self.env.uid:
            report.write({'last_opened': fields.Datetime.now()})
        return {'ok': True, 'report': report._pbrb_payload(), 'spec': clean, 'notes': notes}

    # ============================================================ examples
    @api.model
    def _pbrb_examples(self):
        """Ready-made recipes (built from code, never stored)."""
        _ = self.env._
        return [
            {'key': 'mix', 'icon': 'sparkles', 'name': _("Time off, attendance and assets per person"),
             'blurb': _("One row per person with counts from three areas, this month."),
             'spec': {'subject': 'people',
                      'columns': ['name', 'department', 'count.leave_days',
                                  'count.days_attended', 'count.assets_held'],
                      'period': {'preset': 'this_month'},
                      'totals': {'count.leave_days': 'sum', 'count.days_attended': 'sum',
                                 'count.assets_held': 'sum'}}},
            {'key': 'leave_by_dept', 'icon': 'umbrella',
             'name': _("Time off taken by department this year"),
             'blurb': _("Approved requests grouped by department, with total days."),
             'spec': {'subject': 'time_off',
                      'columns': ['employee', 'person.department', 'kind', 'from', 'days'],
                      'filters': [{'key': 'status', 'op': 'is', 'value': 'validate'}],
                      'period': {'preset': 'this_year', 'date': 'from'},
                      'group_by': ['person.department'], 'totals': {'days': 'sum'}}},
            {'key': 'country_contract', 'icon': 'globe',
             'name': _("People by country and contract type"),
             'blurb': _("How many people work in each country, by contract type."),
             'spec': {'subject': 'people',
                      'columns': ['name', 'country_of_work', 'contract_type', 'department'],
                      'group_by': ['country_of_work', 'contract_type'],
                      'totals': {'name': 'count'}, 'summary': True}},
            {'key': 'joiners', 'icon': 'userPlus', 'name': _("Joiners this quarter"),
             'blurb': _("Everyone who started this quarter, with their manager."),
             'spec': {'subject': 'people',
                      'columns': ['name', 'department', 'job', 'start_date', 'manager'],
                      'period': {'preset': 'this_quarter', 'date': 'start_date'},
                      'sort': {'key': 'start_date', 'dir': 'asc'}}},
            {'key': 'leavers', 'icon': 'userX', 'name': _("Leavers this year"),
             'blurb': _("Everyone who left this year, and why."),
             'spec': {'subject': 'people',
                      'columns': ['name', 'department', 'leaving_date', 'leaving_reason'],
                      'period': {'preset': 'this_year', 'date': 'leaving_date'},
                      'sort': {'key': 'leaving_date', 'dir': 'asc'}}},
            {'key': 'contracts_ending', 'icon': 'calendarClock',
             'name': _("Contracts ending in the next 60 days"),
             'blurb': _("Who needs a renewal decision soon."),
             'spec': {'subject': 'contracts',
                      'columns': ['employee', 'department', 'contract_type', 'date_end',
                                  'status'],
                      'period': {'preset': 'next_60', 'date': 'date_end'},
                      'sort': {'key': 'date_end', 'dir': 'asc'}}},
            {'key': 'assets_by_person', 'icon': 'laptop', 'name': _("Assets held by person"),
             'blurb': _("Every asset in someone's hands, grouped by who holds it."),
             'spec': {'subject': 'assets',
                      'columns': ['holder', 'name', 'category', 'code', 'bought_on'],
                      'filters': [{'key': 'holder', 'op': 'not_empty'}],
                      'group_by': ['holder'], 'totals': {'name': 'count'}}},
            {'key': 'applicants', 'icon': 'briefcase',
             'name': _("Applicants by open role and stage"),
             'blurb': _("Where every applicant stands, role by role."),
             'spec': {'subject': 'applicants',
                      'columns': ['name', 'open_role', 'job', 'stage', 'applied_on'],
                      'group_by': ['open_role', 'stage'], 'totals': {'name': 'count'},
                      'summary': True}},
            {'key': 'training_todo', 'icon': 'graduationCap',
             'name': _("Training still to finish"),
             'blurb': _("Courses people have not finished yet, soonest due first."),
             'spec': {'subject': 'training',
                      'columns': ['employee', 'course', 'status', 'due'],
                      'filters': [{'key': 'finished_on', 'op': 'empty'}],
                      'sort': {'key': 'due', 'dir': 'asc'}}},
            {'key': 'claims_waiting', 'icon': 'receipt',
             'name': _("Expense claims waiting for approval"),
             'blurb': _("Claims sent and not yet decided, with totals per person."),
             'spec': {'subject': 'expenses',
                      'columns': ['employee', 'reference', 'sent_on', 'total'],
                      'filters': [{'key': 'status', 'op': 'is', 'value': 'submitted'}],
                      'group_by': ['employee'], 'totals': {'total': 'sum'}}},
        ]

    @api.model
    def examples(self):
        """The recipes this reader can use, cleaned for them. An example
        whose subject they cannot open — or that keeps fewer than two of its
        columns for them — is not offered."""
        self._require()
        subjects = self._pbrb_subjects()
        out = []
        for ex in self._pbrb_examples():
            subject = subjects.get(ex['spec']['subject'])
            if not subject or not self._subject_open(subject)[0]:
                continue
            try:
                clean, subject, cols, notes = self._clean_spec(ex['spec'], strict=False)
            except (UserError, AccessError):
                continue
            if len(clean['columns']) < 2:
                continue
            out.append({'key': ex['key'], 'name': ex['name'], 'blurb': ex['blurb'],
                        'icon': ex['icon'], 'subject': subject['key'],
                        'subject_label': subject['label'], 'spec': clean})
        return out
