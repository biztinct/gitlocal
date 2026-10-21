# -*- coding: utf-8 -*-
"""LEARNING L2 — `pb.training.requirement`: who must hold what.

ONE TABLE ANSWERS "WHO MUST HOLD WHAT, AND WHO IS MISSING IT". A requirement is
an AUDIENCE (departments with their sub-departments, jobs, kinds of contract,
sites, countries, Vietnam safety groups, a committee flag) × a TARGET (a course,
a certificate or licence found in the person's document folder by its name, or
a number of hours) × TIMING (how long it stays valid, how long someone has once
they fall due, how often it comes round).

Kinds: `always` (hold it at all times), `day_one` (within N days of joining),
`recurring` (every N months), `statutory` (a row from a country pack).

COUNTRY PACKS are TEMPLATE rows: `company_id` empty, `active` False,
`pack_key` set. Switching a pack on for a company COPIES the templates into
that company (auto-assign off until HR turns it on per row); switching it off
archives the copies; on again restores what was on. Template rows are never
read by the matrix, the jobs or the screens — every search here carries a
company.

THE EVALUATION IS SET-BASED (`evaluate`). One audience search per
requirement, ONE read of the assignments and ONE read of the documents for
all the people at once, one read of the joining dates — never a query per
cell. The matrix, the morning job, the Overview, the Numbers and the exports
all read it, so a cell says the same thing on every screen (R80).
"""

import logging
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .training_common import (
    ASSIGN_OPEN, P_RENEW_BEFORE, fold, number, tr,
)

_logger = logging.getLogger(__name__)

REQ_KINDS = [
    ('always', 'Hold it at all times'),
    ('day_one', 'Within days of joining'),
    ('recurring', 'Comes round again'),
    ('statutory', 'Required by law'),
]
REQ_TARGETS = [
    ('course', 'A course'),
    ('certificate', 'A certificate'),
    ('licence', 'A licence or permit'),
    ('hours', 'Hours of training'),
]
AUDIENCE_FLAGS = [
    ('posh_ic', 'Internal Committee members'),
]
#: The employee types a "contractor" filter leaves out when a rule does not
#: cover contractors. The stock values plus `intern` (pb_contract_lifecycle)
#: stay in.
CONTRACTOR_TYPES = ('contractor', 'freelance')

#: The cell states, in the order a reader acts on them.
STATES = ('missing', 'expiring', 'in_progress', 'not_due', 'valid', 'exempt')

#: The country packs. `key` is the stored `pack_key`; `cc` the switch suffix.
PACKS = [
    {'cc': 'vn', 'key': 'vn_osh', 'country': 'VN',
     'label': 'Vietnam — safety training groups',
     'blurb': 'Occupational-safety training by safety group 1 to 6, with the '
              'hours each group needs and a renewal every two years (every '
              'year for group 4). Report: renewals due in 30 days.'},
    {'cc': 'in', 'key': 'in_posh', 'country': 'IN',
     'label': 'India — harassment-awareness sessions',
     'blurb': 'A yearly awareness session for everybody, contractors and '
              'interns included, and an orientation for the Internal '
              'Committee. Report: the session attendance register.'},
    {'cc': 'id', 'key': 'id_k3', 'country': 'ID',
     'label': 'Indonesia — licences and K3 induction',
     'blurb': 'Operator licences (five years), safety-expert appointments '
              '(three years), the K3 induction for every new worker and fire '
              'wardens per site. Report: the licence register.'},
    {'cc': 'sg', 'key': 'sg_hours', 'country': 'SG',
     'label': 'Singapore — training hours',
     'blurb': 'Safety Orientation Course validity, first-aiders per site and '
              'the training-hours return per person and course.'},
]
PACK_BY_CC = {p['cc']: p for p in PACKS}
PACK_BY_KEY = {p['key']: p for p in PACKS}


def _csv(value):
    return [v.strip() for v in (value or '').split(',') if v.strip()]


class PbTrainingRequirement(models.Model):
    _name = 'pb.training.requirement'
    _description = 'Required training'
    _order = 'sequence, id'

    # ------------------------------------------------------------ identity
    name = fields.Char(string='What it is called', required=True,
                       translate=True)
    code = fields.Char(string='Code', index=True,
                       help='A short code, unique per company. Country-pack '
                            'rows carry the pack\'s own code.')
    kind = fields.Selection(REQ_KINDS, string='Kind', required=True,
                            default='always')
    pack_key = fields.Char(string='Country pack', index=True, copy=True,
                           help='Set on rows that came from a country pack.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company,
        help='Empty only on a country-pack template, which nobody is ever '
             'measured against until a company switches the pack on.')
    sequence = fields.Integer(default=10)
    note = fields.Text(string='Why it is required', translate=True,
                       help='Plain words for the matrix: the law it comes '
                            'from, or what to confirm before switching it on.')
    unverified = fields.Boolean(
        string='To confirm before use',
        help='A country-pack rule whose detail is not settled yet. It arrives '
             'switched off; read the note, then switch it on.')
    ship_inactive = fields.Boolean(
        string='Arrives switched off',
        help='Country-pack template only: the copy starts archived.')
    pack_paused = fields.Boolean(
        string='Paused with its pack', copy=False,
        help='Archived because its country pack was switched off; switching '
             'the pack on again brings it back.')
    template_id = fields.Many2one(
        'pb.training.requirement', string='Copied from', copy=False,
        ondelete='set null', index=True)

    # ------------------------------------------------------------ audience
    department_ids = fields.Many2many(
        'hr.department', 'pb_training_req_dept_rel', 'requirement_id',
        'dept_id', string='Departments',
        help='These departments and every department under them. Empty = '
             'every department.')
    job_ids = fields.Many2many(
        'hr.job', 'pb_training_req_job_rel', 'requirement_id', 'job_id',
        string='Jobs')
    employee_types = fields.Char(
        string='Kinds of contract',
        help='Comma-separated employee types (employee, worker, student, '
             'trainee, contractor, freelance, intern). Empty = every kind.')
    work_location_ids = fields.Many2many(
        'hr.work.location', 'pb_training_req_loc_rel', 'requirement_id',
        'location_id', string='Sites')
    country_ids = fields.Many2many(
        'res.country', 'pb_training_req_country_rel', 'requirement_id',
        'country_id', string='Countries',
        help='The country people WORK in: their work address, else their '
             'company. Nationality is never used.')
    safety_groups = fields.Char(
        string='Safety groups',
        help='Comma-separated Vietnam safety groups (1 to 6).')
    audience_flag = fields.Selection(
        AUDIENCE_FLAGS, string='Only people marked as')
    include_contractors = fields.Boolean(
        string='Contractors too', default=True)
    needs_audience = fields.Boolean(
        string='Who it is for must be picked',
        help='Nobody is measured until at least one department, job, site, '
             'kind of contract or safety group is picked.')

    # -------------------------------------------------------------- target
    target = fields.Selection(REQ_TARGETS, string='What they must hold',
                              required=True, default='course')
    channel_id = fields.Many2one('slide.channel', string='Course',
                                 ondelete='set null', index=True)
    survey_id = fields.Many2one('survey.survey', string='Test',
                                ondelete='set null',
                                help='Optional: the test whose certificate '
                                     'counts.')
    document_category_id = fields.Many2one(
        'pb.employee.document.category', string='Document kind',
        ondelete='set null')
    name_pattern = fields.Char(
        string='Name on the paper',
        help='A certificate or licence counts when its name contains these '
             'words (accents do not matter). Separate alternatives with |.')
    hours_required = fields.Float(string='Hours', digits=(6, 2))
    same_company_only = fields.Boolean(
        string='Only while with the company that applied',
        help='A licence issued while the person worked for another company '
             'does not count.')

    # -------------------------------------------------------------- timing
    validity_months = fields.Integer(
        string='Valid for (months)',
        help='0 = never runs out. Overrides the test\'s own validity.')
    validity_months_experienced = fields.Integer(
        string='Valid for, experienced (months)',
        help='Used instead for people marked as having more than six years '
             'in the sector. 0 = the same as above.')
    due_days = fields.Integer(string='Days they get', default=30)
    every_months = fields.Integer(string='Comes round every (months)')
    grace_days = fields.Integer(
        string='Expiring window (days)',
        default=lambda self: number(self.env, P_RENEW_BEFORE, 60),
        help='Inside this many days before it runs out, the matrix shows it '
             'as expiring.')
    refresher_channel_id = fields.Many2one(
        'slide.channel', string='Refresher course', ondelete='set null')
    refresher_hours = fields.Float(string='Refresher hours', digits=(6, 2))

    # ------------------------------------------------------ headcount rules
    ratio_people = fields.Integer(
        string='One group of',
        help='Headcount rule: for every this many people at a site …')
    ratio_holders = fields.Integer(
        string='… this many must hold it')
    ratio_min_people = fields.Integer(
        string='Only from this headcount',
        help='The rule applies only to sites with at least this many people.')

    # ----------------------------------------------------------- behaviour
    auto_assign = fields.Boolean(
        string='Assign it by itself', default=True,
        help='The morning job puts the course on everybody who is missing '
             'it. Country-pack rows arrive with this off.')
    counts_for_probation = fields.Boolean(
        string='Their trial period waits for it')

    # --------------------------------------------------------------- links
    rule_id = fields.Many2one('pb.training.rule', string='From the day-one '
                              'rule', ondelete='set null', copy=False,
                              index=True)
    schedule_id = fields.Many2one('pb.training.schedule', string='From the '
                                  'schedule', ondelete='set null', copy=False,
                                  index=True)

    @api.constrains('due_days', 'validity_months', 'every_months',
                    'ratio_people', 'ratio_holders')
    def _check_numbers(self):
        for rec in self:
            if min(rec.due_days, rec.validity_months, rec.every_months,
                   rec.ratio_people, rec.ratio_holders) < 0:
                raise ValidationError(_("These numbers cannot be below zero."))
            if rec.kind == 'recurring' and rec.company_id \
                    and rec.every_months < 1 and rec.validity_months < 1:
                raise ValidationError(_(
                    "Say how often it comes round — one month or more."))

    @api.constrains('code', 'company_id')
    def _check_code(self):
        for rec in self:
            if not rec.code:
                continue
            clash = self.with_context(active_test=False).search_count([
                ('id', '!=', rec.id), ('code', '=', rec.code),
                ('company_id', '=', rec.company_id.id)])
            if clash:
                raise ValidationError(_(
                    "Another rule in this company already uses the code %s.",
                    rec.code))

    # =====================================================================
    #  facts about one rule
    # =====================================================================
    def _is_headcount(self):
        self.ensure_one()
        return bool(self.ratio_people and self.ratio_holders)

    def _has_audience(self):
        self.ensure_one()
        return bool(self.department_ids or self.job_ids
                    or _csv(self.employee_types) or self.work_location_ids
                    or _csv(self.safety_groups) or self.audience_flag)

    def _course(self):
        """The course an assignment for this rule puts somebody on."""
        self.ensure_one()
        return self.channel_id

    def _patterns(self):
        self.ensure_one()
        return [fold(p.strip()) for p in (self.name_pattern or '').split('|')
                if p.strip()]

    # =====================================================================
    #  the audience
    # =====================================================================
    def _people_domain(self):
        self.ensure_one()
        domain = [('active', '=', True),
                  ('company_id', '=', self.company_id.id)]
        if self.department_ids:
            domain.append(('department_id', 'child_of',
                           self.department_ids.ids))
        if self.job_ids:
            domain.append(('job_id', 'in', self.job_ids.ids))
        types = _csv(self.employee_types)
        if types:
            domain.append(('employee_type', 'in', types))
        if not self.include_contractors:
            domain.append(('employee_type', 'not in', list(CONTRACTOR_TYPES)))
        if self.work_location_ids:
            domain.append(('work_location_id', 'in',
                           self.work_location_ids.ids))
        groups = _csv(self.safety_groups)
        if groups:
            domain.append(('pb_safety_group', 'in', groups))
        if self.audience_flag == 'posh_ic':
            domain.append(('pb_posh_ic_member', '=', True))
        if self.country_ids:
            # The country people WORK in (handover F2, without nationality):
            # the work address's country, else the company's.
            ids = self.country_ids.ids
            domain += ['|', ('address_id.country_id', 'in', ids),
                       '&', ('address_id.country_id', '=', False),
                       ('company_id.country_id', 'in', ids)]
        return domain

    def _people(self):
        """Everybody this rule is about (as the system, narrowly)."""
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()
        if not self.company_id or self._is_headcount():
            return Employee.browse()
        if self.needs_audience and not self._has_audience():
            return Employee.browse()
        return Employee.search(self._people_domain())

    # =====================================================================
    #  the evaluation — set-based
    # =====================================================================
    @api.model
    def _join_dates(self, employees):
        """{employee_id: date} — the onboarding journey's key date, else the
        first contract start, else the day the record was made. Three
        queries for the whole set (pb_onboarding's `_pb_join_date` asks per
        person)."""
        out = {}
        ids = employees.ids
        if not ids:
            return out
        if 'pb.journey.case' in self.env:
            for row in self.env['pb.journey.case'].sudo().search_read(
                    [('employee_id', 'in', ids),
                     ('case_type', '=', 'onboarding'),
                     ('anchor_date', '!=', False)],
                    ['employee_id', 'anchor_date'],
                    order='anchor_date desc'):
                out.setdefault(row['employee_id'][0], row['anchor_date'])
        missing = [i for i in ids if i not in out]
        if missing:
            groups = self.env['hr.version'].sudo()._read_group(
                [('employee_id', 'in', missing),
                 ('contract_date_start', '!=', False)],
                ['employee_id'], ['contract_date_start:min'])
            for emp, start in groups:
                out[emp.id] = start
        for emp in employees:
            if emp.id not in out and emp.create_date:
                out[emp.id] = emp.create_date.date()
        return out

    def _valid_until_doc(self, doc, experienced=False):
        """When a document stops counting for THIS rule, or None (never).

        The rule's own validity wins for a test certificate (handover T2);
        for paper from outside, the date printed on it wins."""
        months = self._months(experienced)
        issued = doc['issue_date']
        if months and doc['training_source'] == 'test' and issued:
            return issued + relativedelta(months=months)
        if doc['expiry_date']:
            return doc['expiry_date']
        if months and issued:
            return issued + relativedelta(months=months)
        return None

    def _months(self, experienced=False):
        if experienced and self.validity_months_experienced:
            return self.validity_months_experienced
        return self.validity_months

    def _doc_matches(self, doc, emp_company):
        """Does this document count as evidence for this rule?"""
        if self.same_company_only and doc['company_id'] \
                and doc['company_id'][0] != emp_company:
            return False
        if self.survey_id and doc['survey_id'] \
                and doc['survey_id'][0] == self.survey_id.id:
            return True
        if self.target == 'course' and self.channel_id and doc['channel_id'] \
                and doc['channel_id'][0] == self.channel_id.id:
            return True
        patterns = self._patterns()
        if not patterns:
            return False
        if self.document_category_id and (
                not doc['category_id']
                or doc['category_id'][0] != self.document_category_id.id):
            return False
        name = fold(doc['name'])
        # WHOLE WORDS: "SIO" must not match "Pension".
        return any(re.search(r'(?<!\w)%s(?!\w)' % re.escape(p), name)
                   for p in patterns)

    @api.model
    def evaluate(self, requirements, employees=None, today=None):
        """{(requirement_id, employee_id): cell} for every rule in
        `requirements` and every person in its audience (or in `employees`,
        when given — a cell for somebody outside a rule's audience is
        `exempt`).

        cell = {state, valid_until, words, evidence: {kind, id} | None,
                course_id, open_id}
        """
        today = today or fields.Date.today()
        reqs = requirements.filtered(
            lambda r: r.company_id and not r._is_headcount())
        audience = {r.id: set(r._people().ids) for r in reqs}
        if employees is None:
            all_ids = set()
            for ids in audience.values():
                all_ids |= ids
            employees = self.env['hr.employee'].sudo().browse(sorted(all_ids))
        else:
            employees = employees.sudo()
        emp_ids = employees.ids
        if not emp_ids or not reqs:
            return {}
        emp_info = {e['id']: e for e in employees.read(
            ['company_id', 'pb_sg_experienced', 'user_id'])}

        # ---- ONE read of the assignments ---------------------------------
        channels = (reqs.mapped('channel_id')
                    | reqs.mapped('refresher_channel_id')).ids
        by_pair = {}
        hours_by_emp = {}
        if channels or any(r.target == 'hours' for r in reqs):
            domain = [('employee_id', 'in', emp_ids)]
            if not any(r.target == 'hours' for r in reqs):
                domain.append(('channel_id', 'in', channels))
            for row in self.env['pb.training.assignment'].sudo().search_read(
                    domain, ['channel_id', 'employee_id', 'state',
                             'completed_on', 'due_date', 'hours'],
                    order='completed_on desc, id desc'):
                key = (row['channel_id'][0], row['employee_id'][0])
                by_pair.setdefault(key, []).append(row)
                if row['state'] == 'done':
                    hours_by_emp.setdefault(row['employee_id'][0], []) \
                        .append(row)

        # ---- ONE read of the documents -----------------------------------
        docs_by_emp = {}
        if 'pb.employee.document' in self.env:
            for doc in self.env['pb.employee.document'].sudo().search_read(
                    [('employee_id', 'in', emp_ids),
                     ('renewed_by_id', '=', False)],
                    ['employee_id', 'name', 'category_id', 'survey_id',
                     'channel_id', 'issue_date', 'expiry_date',
                     'training_source', 'company_id', 'reference', 'issuer',
                     'hours']):
                docs_by_emp.setdefault(doc['employee_id'][0], []).append(doc)

        joins = self._join_dates(employees) \
            if any(r.kind == 'day_one' for r in reqs) else {}

        out = {}
        for req in reqs:
            members = audience[req.id]
            course = req.channel_id.id
            refresher = req.refresher_channel_id.id
            for emp_id in emp_ids:
                if emp_id not in members:
                    out[(req.id, emp_id)] = {
                        'state': 'exempt', 'valid_until': None,
                        'words': tr(self.env, 'Not for them'),
                        'evidence': None, 'open_id': 0}
                    continue
                info = emp_info.get(emp_id, {})
                out[(req.id, emp_id)] = req._cell(
                    today, emp_id, info,
                    docs_by_emp.get(emp_id, []),
                    by_pair.get((course, emp_id), []) if course else [],
                    by_pair.get((refresher, emp_id), []) if refresher else [],
                    hours_by_emp.get(emp_id, []),
                    joins.get(emp_id))
        return out

    def _cell(self, today, emp_id, info, docs, rows, refresher_rows,
              done_rows, joined):
        """One person against one rule. Order: a document in date → a
        finished course in date → an open assignment → not due yet →
        missing."""
        self.ensure_one()
        env = self.env
        experienced = bool(info.get('pb_sg_experienced'))
        company = info.get('company_id') and info['company_id'][0]
        grace = max(self.grace_days or 0, 0)
        best = None          # (valid_until or date.max, kind, id, words)

        def consider(until, kind, rid):
            nonlocal best
            key = until or fields.Date.to_date('9999-12-31')
            if best is None or key > best[0]:
                best = (key, until, kind, rid)

        # ---- hours: a total over the window ---------------------------
        if self.target == 'hours':
            months = self._months(experienced)
            since = today - relativedelta(months=months) if months \
                else today.replace(month=1, day=1)
            total = sum(r['hours'] or 0.0 for r in done_rows
                        if r['completed_on'] and r['completed_on'] >= since)
            need = self.hours_required or 0.0
            if need and total >= need:
                return {'state': 'valid', 'valid_until': None,
                        'words': tr(env, '%s of %s hours',
                                    _num(total), _num(need)),
                        'evidence': None, 'open_id': 0}
            state = 'in_progress' if total else 'missing'
            return {'state': state, 'valid_until': None,
                    'words': tr(env, '%s of %s hours', _num(total),
                                _num(need)),
                    'evidence': None, 'open_id': 0}

        for doc in docs:
            if self._doc_matches(doc, company):
                until = self._valid_until_doc(doc, experienced)
                if until is None or until >= today:
                    consider(until, 'document', doc['id'])
        for row in rows + refresher_rows:
            if row['state'] != 'done' or not row['completed_on']:
                continue
            months = self._months(experienced)
            until = row['completed_on'] + relativedelta(months=months) \
                if months else None
            if until is None or until >= today:
                consider(until, 'assignment', row['id'])
        open_row = next((r for r in rows + refresher_rows
                         if r['state'] in ASSIGN_OPEN), None)
        open_id = open_row['id'] if open_row else 0

        if best:
            _key, until, kind, rid = best
            evidence = {'kind': kind, 'id': rid}
            if until is not None and (until - today).days <= grace:
                days = (until - today).days
                words = tr(env, 'Expires today') if days == 0 else (
                    tr(env, 'Expires tomorrow') if days == 1
                    else tr(env, 'Expires in %s days', days))
                return {'state': 'expiring', 'valid_until': until,
                        'words': words, 'evidence': evidence,
                        'open_id': open_id}
            words = tr(env, 'Valid until %s', _date(env, until)) \
                if until else tr(env, 'Done, never expires')
            return {'state': 'valid', 'valid_until': until, 'words': words,
                    'evidence': evidence, 'open_id': open_id}
        if open_row:
            return {'state': 'in_progress', 'valid_until': None,
                    'words': tr(env, 'On the course, due %s',
                                _date(env, open_row['due_date'])),
                    'evidence': {'kind': 'assignment', 'id': open_id},
                    'open_id': open_id}
        if self.kind == 'day_one' and joined \
                and joined + timedelta(days=max(self.due_days, 0)) > today:
            due = joined + timedelta(days=max(self.due_days, 0))
            return {'state': 'not_due', 'valid_until': None,
                    'words': tr(env, 'Due by %s', _date(env, due)),
                    'evidence': None, 'open_id': 0}
        if self.target in ('certificate', 'licence') and not self.channel_id:
            words = tr(env, 'Not on file')
        else:
            words = tr(env, 'Missing')
        return {'state': 'missing', 'valid_until': None, 'words': words,
                'evidence': None, 'open_id': 0}

    # =====================================================================
    #  putting somebody on the course
    # =====================================================================
    def _due_for(self, today, joined=None):
        """Day one: joining date + days they get — unless that is already
        behind us (somebody who joined long before the rule existed), when
        they get the same number of days from today rather than a course
        that is overdue the moment it is made. Everybody else: today + days."""
        self.ensure_one()
        days = max(self.due_days or 0, 1)
        if self.kind == 'day_one' and joined:
            due = joined + timedelta(days=days)
            if due >= today:
                return due
        return today + timedelta(days=days)

    def _assignment_vals(self, emp, channel, today, joined=None, cell=None):
        self.ensure_one()
        due = self._due_for(today, joined)
        if cell and cell.get('state') == 'expiring' and cell.get(
                'valid_until') and cell['valid_until'] >= today:
            # A renewal is due by the day the old one runs out.
            due = max(cell['valid_until'], today + timedelta(days=1))
        return {
            'channel_id': channel.id,
            'employee_id': emp.id,
            'reason': 'required',
            'requirement_id': self.id,
            'due_date': due,
            'counts_for_probation': bool(self.counts_for_probation),
            'company_id': (emp.company_id or self.company_id).id,
        }

    # =====================================================================
    #  headcount rules (Indonesia fire wardens, first-aiders)
    # =====================================================================
    def _shortfalls(self, today=None):
        """[{requirement_id, name, site, people, need, has, words}] — one line
        per site that has fewer holders than the rule asks for. A site is the
        work location when people have one, else their department."""
        today = today or fields.Date.today()
        out = []
        Employee = self.env['hr.employee'].sudo()
        for req in self.filtered(lambda r: r.company_id
                                 and r._is_headcount()):
            people = Employee.search(
                [('active', '=', True), ('company_id', '=', req.company_id.id)]
                + ([('work_location_id', 'in', req.work_location_ids.ids)]
                   if req.work_location_ids else []))
            if not people:
                continue
            docs = {}
            for doc in self.env['pb.employee.document'].sudo().search_read(
                    [('employee_id', 'in', people.ids),
                     ('renewed_by_id', '=', False)],
                    ['employee_id', 'name', 'category_id', 'survey_id',
                     'channel_id', 'issue_date', 'expiry_date',
                     'training_source', 'company_id']):
                docs.setdefault(doc['employee_id'][0], []).append(doc)
            sites = {}
            for emp in people:
                site = emp.work_location_id.name or emp.department_id.name \
                    or tr(self.env, 'No site')
                entry = sites.setdefault(site, {'people': 0, 'has': 0})
                entry['people'] += 1
                for doc in docs.get(emp.id, []):
                    if req._doc_matches(doc, emp.company_id.id):
                        until = req._valid_until_doc(doc)
                        if until is None or until >= today:
                            entry['has'] += 1
                            break
            for site, entry in sorted(sites.items()):
                if req.ratio_min_people and \
                        entry['people'] < req.ratio_min_people:
                    continue
                groups = -(-entry['people'] // req.ratio_people)
                need = groups * req.ratio_holders
                if entry['has'] >= need:
                    continue
                out.append({
                    'requirement_id': req.id, 'name': req.name,
                    'site': site, 'people': entry['people'],
                    'need': need, 'has': entry['has'],
                    'words': self.env._(
                        '%(site)s needs %(need)s, has %(has)s (%(people)s '
                        'people).', site=site, need=need, has=entry['has'],
                        people=entry['people']),
                })
        return out

    # =====================================================================
    #  the legacy rows (migration 19.0.1.6.0)
    # =====================================================================
    @api.model
    def _convert_legacy(self):
        """One requirement per course of every live day-one rule, one per
        live schedule. Idempotent: matched on `rule_id` + course and on
        `schedule_id`. The legacy rows keep running; leg 5 skips anything
        converted (its own mechanism assigns it)."""
        Req = self.sudo().with_context(active_test=False)
        counts = {'rules': 0, 'schedules': 0}
        for rule in self.env['pb.training.rule'].sudo().search(
                [('active', '=', True)]):
            for channel in rule.channel_ids:
                if Req.search_count([('rule_id', '=', rule.id),
                                     ('channel_id', '=', channel.id)]):
                    continue
                name = rule.name if len(rule.channel_ids) == 1 \
                    else '%s — %s' % (rule.name, channel.name)
                Req.create({
                    'name': name, 'kind': 'day_one', 'target': 'course',
                    'channel_id': channel.id, 'due_days': rule.due_days,
                    'department_ids': [(6, 0, rule.department_ids.ids)],
                    'job_ids': [(6, 0, rule.job_ids.ids)],
                    'company_id': rule.company_id.id, 'rule_id': rule.id,
                    'auto_assign': True,
                })
                counts['rules'] += 1
        for sch in self.env['pb.training.schedule'].sudo().search(
                [('active', '=', True)]):
            if Req.search_count([('schedule_id', '=', sch.id)]):
                continue
            vals = {
                'name': sch.name, 'kind': 'recurring', 'target': 'course',
                'channel_id': sch.channel_id.id,
                'every_months': sch.every_months,
                'validity_months': sch.every_months,
                'due_days': sch.due_days, 'company_id': sch.company_id.id,
                'schedule_id': sch.id, 'auto_assign': True,
            }
            if sch.audience == 'department' and sch.department_id:
                vals['department_ids'] = [(6, 0, sch.department_id.ids)]
            elif sch.audience == 'job' and sch.job_id:
                vals['job_ids'] = [(6, 0, sch.job_id.ids)]
            Req.create(vals)
            counts['schedules'] += 1
        _logger.info('pb_training: legacy rows converted to required '
                     'training — %(rules)s from day-one rules, %(schedules)s '
                     'from schedules', counts)
        return counts

    # =====================================================================
    #  country packs
    # =====================================================================
    @api.model
    def _templates(self, pack_key):
        return self.sudo().with_context(active_test=False).search([
            ('company_id', '=', False), ('pack_key', '=', pack_key)])

    @api.model
    def _pack_is_on(self, cc, company):
        from .training_common import P_PACK_SWITCH
        raw = self.env['ir.config_parameter'].sudo().get_param(
            P_PACK_SWITCH % (cc, company.id), '0')
        return str(raw).strip() == '1'

    @api.model
    def _switch_pack(self, cc, company, on):
        """Copy a pack's templates into `company` (on) or archive the copies
        (off). Idempotent: a copy is found by pack + code + company; on again
        brings back exactly what the switch-off paused. Never auto-assigns:
        copies arrive with `auto_assign` off (safety rail 4)."""
        from .training_common import P_PACK_SWITCH
        pack = PACK_BY_CC.get(cc)
        if not pack:
            raise ValidationError(_("There is no such country pack."))
        Req = self.sudo().with_context(active_test=False)
        made = restored = paused = 0
        for tpl in self._templates(pack['key']):
            copy = Req.search([('company_id', '=', company.id),
                               ('pack_key', '=', pack['key']),
                               ('code', '=', tpl.code)], limit=1)
            if on:
                if not copy:
                    tpl.copy({
                        'company_id': company.id,
                        'active': not (tpl.unverified or tpl.ship_inactive),
                        'auto_assign': False,
                        'template_id': tpl.id,
                        'grace_days': tpl.grace_days,
                    })
                    made += 1
                elif copy.pack_paused:
                    copy.write({'active': True, 'pack_paused': False})
                    restored += 1
            elif copy and copy.active:
                copy.write({'active': False, 'pack_paused': True})
                paused += 1
        self.env['ir.config_parameter'].sudo().set_param(
            P_PACK_SWITCH % (cc, company.id), '1' if on else '0')
        _logger.info('pb_training: pack %s %s for %s — %s copied, %s back, '
                     '%s paused', cc, 'on' if on else 'off', company.name,
                     made, restored, paused)
        return {'made': made, 'restored': restored, 'paused': paused}


def _num(value):
    value = float(value or 0.0)
    return ('%d' % value) if value == int(value) else ('%.1f' % value)


def _date(env, day):
    if not day:
        return ''
    try:
        from odoo.tools.misc import format_date
        return format_date(env, day, date_format='d MMM y')
    except Exception:                       # noqa: BLE001 — a date is not fatal
        return fields.Date.to_string(day)


class PbTrainingAssignmentRequirement(models.Model):
    """Which required-training rule put somebody on a course."""
    _inherit = 'pb.training.assignment'

    requirement_id = fields.Many2one(
        'pb.training.requirement', string='From the required-training rule',
        index=True, ondelete='set null', readonly=True)
