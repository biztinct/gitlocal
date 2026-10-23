# -*- coding: utf-8 -*-
"""Learning › REQUIRED — the matrix, the rules and the settings (LEARNING L2).

One read per screen, behind the board's gate (`{'allowed': False}` without a
training group, never an AccessError):

  * `matrix(filters)`          people × rules, a cell per pair, the summary
                               sentence, headcount shortfalls, paging;
  * `required_rules(filters)`  the Rules / Day one / Comes round again tabs,
                               with the legacy rows read-only;
  * `required_settings()`      the Settings card's screen.

WHO MAY DO WHAT (handover §3.7, fixing F5): a trainer may READ every rule and
may put somebody on a course from a cell (assigning people is the trainer's
own job); only a training manager or the head of training may create, edit,
switch off or bulk-reclassify — the verbs check `_require_manager` and the
screen hides the buttons.

The cells come from ONE function, `pb.training.requirement.evaluate`, which
the morning job, the Overview, the Numbers and the exports read too.
"""

import base64
import io
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .hr_employee_ext import (
    SAFETY_GROUP_LABEL, SAFETY_GROUPS, effective_safety_group,
)
from .pb_training_certificates import PbTrainingCertificates
from .requirement import PACKS, PACK_BY_CC, PACK_BY_KEY, _csv
from .training_common import (
    GROUP_ADMIN, GROUP_MANAGER, P_DAY1_AUTO, P_ENFORCE_CAP, P_RENEW_BEFORE,
    as_id, flag, fold, number, tr,
)

_logger = logging.getLogger(__name__)

#: People per page on the matrix (the roster's own cap, handover F6).
ROW_CAP = 200

#: The most people one auditor print-out takes (5 printed pages of 40).
PDF_MAX_PEOPLE = 200

#: Problem first: who is missing something, then expiring, then under way.
_ROW_RANK = {'missing': 0, 'expiring': 1, 'in_progress': 2, 'not_due': 3}

EMPLOYEE_TYPES = [
    ('employee', 'Employee'), ('worker', 'Worker'), ('student', 'Student'),
    ('trainee', 'Trainee'), ('contractor', 'Contractor'),
    ('freelance', 'Freelancer'), ('intern', 'Intern'),
]


class PbTrainingRequired(models.AbstractModel):
    _inherit = 'pb.training'

    _VERBS = PbTrainingCertificates._VERBS + (
        'assign_from_cell', 'bulk_assign_required', 'set_safety_group',
        'save_requirement', 'toggle_requirement_auto',
        'archive_requirement', 'switch_pack', 'save_required_settings',
    )

    # =====================================================================
    #  gates
    # =====================================================================
    @api.model
    def _can_manage(self):
        user = self.env.user
        return user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)

    @api.model
    def _require_manager(self):
        self._require_read()
        if not self._can_manage():
            raise AccessError(_(
                "Only a training manager can change the required-training "
                "rules."))

    # F5: the stock forms for day-one rules and schedules are a manager's
    # (the trainer's ACL is read-only, so the form could never be saved).
    @api.model
    def new_schedule(self):
        self._require_manager()
        return super().new_schedule()

    @api.model
    def new_rule(self):
        self._require_manager()
        return super().new_rule()

    # =====================================================================
    #  the rules a reader sees
    # =====================================================================
    @api.model
    def _live_requirements(self, requirement_id=None, active=True):
        domain = [('company_id', 'in', self.env.companies.ids)]
        if active is not None:
            domain.append(('active', '=', active))
        if requirement_id:
            domain.append(('id', '=', as_id(requirement_id)))
        return self.env['pb.training.requirement'].sudo().with_context(
            active_test=False).search(domain)

    @api.model
    def _kind_word(self, req):
        return tr(self.env, dict(req._fields['kind'].selection).get(
            req.kind, ''))

    @api.model
    def _pack_word(self, req):
        pack = PACK_BY_KEY.get(req.pack_key or '')
        return tr(self.env, pack['label']) if pack else ''

    @api.model
    def _target_words(self, req):
        if req.target == 'hours':
            return _("%s hours of training", _num(req.hours_required))
        if req.target == 'path':
            if not req.path_id:
                return _("No path linked yet")
            return _("Path: %s", req.path_id.sudo().name or '')
        if req.target in ('certificate', 'licence'):
            what = req.name_pattern or req.name
            if req.target == 'licence':
                return _("Licence: %s", what.replace('|', ' / '))
            return _("Certificate: %s", what.replace('|', ' / '))
        return req.channel_id.sudo().name or _("No course linked yet")

    @api.model
    def _audience_words(self, req):
        bits = []
        groups = _csv(req.safety_groups)
        if groups:
            bits.append(_("Safety group %s", ', '.join(groups)))
        bits += req.department_ids.sudo().mapped('name')
        bits += req.job_ids.sudo().mapped('name')
        bits += req.work_location_ids.sudo().mapped('name')
        types = dict(EMPLOYEE_TYPES)
        bits += [tr(self.env, types.get(t, t))
                 for t in _csv(req.employee_types)]
        if req.audience_flag == 'posh_ic':
            bits.append(_("Internal Committee members"))
        bits += req.country_ids.sudo().mapped('name')
        if bits:
            return ', '.join(bits)
        if req.needs_audience:
            return _("Pick who this is for")
        return _("Everybody in the company")

    @api.model
    def _timing_words(self, req):
        if req.kind == 'day_one':
            return _("Within %s days of joining", req.due_days)
        if req.validity_months:
            if req.validity_months % 12 == 0:
                years = req.validity_months // 12
                return _("Every year") if years == 1 \
                    else _("Every %s years", years)
            return _("Every %s months", req.validity_months)
        if req.every_months:
            return _("Every %s months", req.every_months)
        return _("Once, never runs out")

    @api.model
    def _column(self, req):
        return {
            'id': req.id,
            'name': req.name or '',
            'kind': req.kind,
            'kind_word': self._kind_word(req),
            'pack': req.pack_key or '',
            'pack_word': self._pack_word(req),
            'target': req.target,
            'target_words': self._target_words(req),
            'timing_words': self._timing_words(req),
            'no_course': (req.target == 'course' and not req.channel_id)
            or (req.target == 'path' and not req.path_id),
            'no_audience': bool(req.needs_audience
                                and not req._has_audience()),
            'note': req.note or '',
            'auto': bool(req.auto_assign),
            'unverified': bool(req.unverified),
            'can_assign': bool(req.path_id) if req.target == 'path'
            else bool(req.channel_id),
        }

    # =====================================================================
    #  the matrix
    # =====================================================================
    @api.model
    def _person_facts(self, employees):
        """{id: {name, department, job, site, country, group, …}} in a
        handful of reads, never per person."""
        rows = employees.sudo().read(
            ['name', 'department_id', 'job_id', 'job_title',
             'work_location_id', 'pb_safety_group', 'company_id',
             'address_id', 'user_id'])
        partner_ids = {r['address_id'][0] for r in rows if r['address_id']}
        p_country = {}
        if partner_ids:
            for p in self.env['res.partner'].sudo().browse(
                    sorted(partner_ids)).read(['country_id']):
                p_country[p['id']] = p['country_id']
        companies = {c.id: c.partner_id.country_id for c in
                     self.env['res.company'].sudo().browse(sorted(
                         {r['company_id'][0] for r in rows
                          if r['company_id']}))}
        codes = {}
        country_ids = {c[0] for c in p_country.values() if c}
        if country_ids:
            codes = {c['id']: c['code'] for c in self.env['res.country']
                     .sudo().browse(sorted(country_ids)).read(['code'])}
        out = {}
        for r in rows:
            comp_code = companies[r['company_id'][0]].code \
                if r['company_id'] and companies.get(r['company_id'][0]) \
                else ''
            group, by_default = effective_safety_group(
                r['pb_safety_group'] or '', comp_code)
            country = p_country.get(r['address_id'][0]) \
                if r['address_id'] else False
            if country:
                code, cname = codes.get(country[0], ''), country[1]
            else:
                comp = companies.get(r['company_id'][0]) \
                    if r['company_id'] else None
                code = comp.code if comp else ''
                cname = comp.name if comp else ''
            out[r['id']] = {
                'name': r['name'] or '',
                'department_id': r['department_id'][0]
                if r['department_id'] else 0,
                'department': r['department_id'][1]
                if r['department_id'] else '',
                'job_id': r['job_id'][0] if r['job_id'] else 0,
                'job': (r['job_id'][1] if r['job_id'] else '')
                or r['job_title'] or '',
                'site_id': r['work_location_id'][0]
                if r['work_location_id'] else 0,
                'site': r['work_location_id'][1]
                if r['work_location_id'] else '',
                'country_code': code or '',
                'country': cname or '',
                'safety_group': group,
                'safety_group_default': by_default,
                'has_login': bool(r['user_id']),
            }
        return out

    @api.model
    def _matrix_data(self, filters=None, paged=True):
        filters = filters or {}
        today = fields.Date.today()
        Req = self.env['pb.training.requirement']
        reqs = self._live_requirements()
        cols = reqs.filtered(lambda r: not r._is_headcount())
        wanted = as_id(filters.get('requirement_id'))
        if wanted:
            cols = cols.filtered(lambda r: r.id == wanted)
        pack = filters.get('pack') or ''
        if pack:
            cols = cols.filtered(lambda r: r.pack_key == pack)
        cells = Req.evaluate(cols, today=today) if cols else {}
        emp_ids = sorted({emp for _rid, emp in cells})
        employees = self.env['hr.employee'].sudo().browse(emp_ids)
        facts = self._person_facts(employees) if emp_ids else {}

        dept = as_id(filters.get('department_id'))
        depts = set(self.env['hr.department'].sudo().search(
            [('id', 'child_of', dept)]).ids) if dept else set()
        job = as_id(filters.get('job_id'))
        site = as_id(filters.get('work_location_id'))
        country = (filters.get('country_code') or '').upper()
        group = str(filters.get('safety_group') or '')
        state = filters.get('state') or ''
        needle = fold(filters.get('q') or '')

        rows = []
        for emp_id in emp_ids:
            f = facts.get(emp_id) or {}
            if dept and f.get('department_id') not in depts:
                continue
            if job and f.get('job_id') != job:
                continue
            if site and f.get('site_id') != site:
                continue
            if country and f.get('country_code') != country:
                continue
            if group and f.get('safety_group') != group:
                continue
            if needle and needle not in fold(f.get('name')):
                continue
            row_cells = {}
            worst = 9
            for req in cols:
                cell = cells.get((req.id, emp_id))
                if not cell:
                    continue
                row_cells[str(req.id)] = {
                    'state': cell['state'], 'words': cell['words'],
                    'open_id': cell.get('open_id') or 0,
                }
                worst = min(worst, _ROW_RANK.get(cell['state'], 9))
            states = {c['state'] for c in row_cells.values()}
            if state and state not in states:
                continue
            word = tr(self.env, SAFETY_GROUP_LABEL.get(
                f.get('safety_group'), '')) if f.get('safety_group') else ''
            if word and f.get('safety_group_default'):
                # LD11: say it is the Vietnam default, not a group HR set.
                word = _("%s (by default)", word)
            rows.append(dict(f, employee_id=emp_id, cells=row_cells,
                             rank=worst, safety_group_word=word))
        rows.sort(key=lambda r: (r['rank'], fold(r['name'])))
        summary = self._matrix_summary(rows)
        total = len(rows)
        pages = max((total + ROW_CAP - 1) // ROW_CAP, 1)
        page = min(max(int(filters.get('page') or 1), 1), pages)
        shown = rows[(page - 1) * ROW_CAP:page * ROW_CAP] if paged else rows
        return {
            'columns': [self._column(r) for r in cols],
            'rows': shown,
            'summary': summary,
            'headline': self._matrix_headline(summary),
            'truncated': paged and total > ROW_CAP,
            'row_cap': ROW_CAP,
            'total': total,
            'page': page,
            'pages': pages,
            'shortfalls': self._safe(
                lambda: reqs.filtered(lambda r: r._is_headcount())
                ._shortfalls(today), default=[]),
            'facts': facts,
        }

    @api.model
    def _matrix_summary(self, rows):
        counts = {k: 0 for k in ('valid', 'expiring', 'missing',
                                 'in_progress', 'not_due')}
        cells = 0
        people_missing = 0
        for row in rows:
            any_missing = False
            for cell in row['cells'].values():
                key = cell['state']
                if key in ('exempt', 'unlinked'):
                    continue
                cells += 1
                counts[key] = counts.get(key, 0) + 1
                any_missing = any_missing or key == 'missing'
            people_missing += 1 if any_missing else 0
        measured = counts['valid'] + counts['expiring'] + counts['missing'] \
            + counts['in_progress']
        in_date = counts['valid'] + counts['expiring']
        return dict(counts, people=len(rows), cells=cells,
                    people_missing=people_missing,
                    percent=int(round(100.0 * in_date / measured))
                    if measured else None)

    @api.model
    def _matrix_headline(self, s):
        """"92% in date across 214 people · 12 expiring · 5 missing" —
        whole sentences, chosen for their counts (R117)."""
        if not s.get('people'):
            return _("Nobody is covered by a required-training rule yet.")
        people = s['people']
        if s.get('percent') is None:
            first = _("Nothing is due yet for the 1 person covered.") \
                if people == 1 else _("Nothing is due yet for the %s people "
                                      "covered.", people)
            return first
        first = _("%(pct)s%% in date across 1 person",
                  pct=s['percent']) if people == 1 else _(
            "%(pct)s%% in date across %(n)s people", pct=s['percent'],
            n=people)
        bits = [first]
        if s.get('expiring'):
            bits.append(_("%s expiring", s['expiring']))
        if s.get('missing'):
            bits.append(_("%s missing", s['missing']))
        if s.get('in_progress'):
            bits.append(_("%s under way", s['in_progress']))
        return ' · '.join(bits)

    @api.model
    def matrix(self, filters=None):
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'columns': []}
        data = self._matrix_data(filters or {})
        data.pop('facts', None)
        data.update({
            'allowed': True,
            'can_write': self._can_write(),
            'can_manage': self._can_manage(),
            'lists': self._safe(self._required_lists, default={}),
        })
        return data

    @api.model
    def _required_lists(self):
        comps = self.env.companies.ids
        Dept = self.env['hr.department'].sudo()
        Job = self.env['hr.job'].sudo()
        Loc = self.env['hr.work.location'].sudo()
        courses = self.env['slide.channel'].sudo().search_read(
            [('active', '=', True)], ['name'], limit=number(
                self.env, 'pb_training.course_limit', 200))
        countries = self.env['res.country'].sudo().search_read(
            [('code', 'in', ['VN', 'IN', 'ID', 'SG', 'MY', 'TH', 'KH', 'PH',
                             'AU'])], ['name', 'code'])
        return {
            'departments': sorted(
                [{'id': d['id'], 'name': d['complete_name'] or d['name']}
                 for d in Dept.search_read([('company_id', 'in', comps)],
                                           ['name', 'complete_name'])],
                key=lambda r: fold(r['name'])),
            'jobs': sorted([{'id': j['id'], 'name': j['name']}
                            for j in Job.search_read(
                                [('company_id', 'in', comps)], ['name'])],
                           key=lambda r: fold(r['name'])),
            'sites': sorted([{'id': s['id'], 'name': s['name']}
                             for s in Loc.search_read(
                                 [('company_id', 'in', comps)], ['name'])],
                            key=lambda r: fold(r['name'])),
            'courses': sorted([{'id': c['id'], 'name': c['name']}
                               for c in courses],
                              key=lambda r: fold(r['name'])),
            'countries': sorted([{'id': c['id'], 'code': c['code'],
                                  'name': c['name']} for c in countries],
                                key=lambda r: fold(r['name'])),
            'safety_groups': [{'key': k, 'label': tr(self.env, v)}
                              for k, v in SAFETY_GROUPS],
            'employee_types': [{'key': k, 'label': tr(self.env, v)}
                               for k, v in EMPLOYEE_TYPES],
            # LEARNING L3: a rule may require a learning path.
            'paths': sorted([{'id': p.id, 'name': p.name or ''}
                             for p in self.env['pb.training.path'].sudo()
                             .search([('company_id', 'in', comps)])],
                            key=lambda r: fold(r['name'])),
        }

    # =====================================================================
    #  the Rules / Day one / Comes round again tabs
    # =====================================================================
    @api.model
    def _rule_payload(self, req):
        col = self._column(req)
        col.update({
            'active': bool(req.active),
            'audience_words': self._audience_words(req),
            'code': req.code or '',
            'legacy': bool(req.rule_id or req.schedule_id),
            'values': {
                'id': req.id, 'name': req.name or '', 'kind': req.kind,
                'target': req.target,
                'channel_id': req.channel_id.id or 0,
                'refresher_channel_id': req.refresher_channel_id.id or 0,
                'name_pattern': req.name_pattern or '',
                'hours_required': req.hours_required or 0,
                'path_id': req.path_id.id or 0,
                'validity_months': req.validity_months,
                'due_days': req.due_days,
                'every_months': req.every_months,
                'department_ids': req.department_ids.ids,
                'job_ids': req.job_ids.ids,
                'work_location_ids': req.work_location_ids.ids,
                'country_ids': req.country_ids.ids,
                'employee_types': _csv(req.employee_types),
                'safety_groups': _csv(req.safety_groups),
                'include_contractors': bool(req.include_contractors),
                'auto_assign': bool(req.auto_assign),
                'counts_for_probation': bool(req.counts_for_probation),
                'note': req.note or '',
            },
        })
        return col

    @api.model
    def required_rules(self, filters=None):
        if not self._can_read():
            return {'allowed': False, 'rows': []}
        filters = filters or {}
        reqs = self._live_requirements(active=None)
        kind = filters.get('kind') or ''
        if kind:
            reqs = reqs.filtered(lambda r: r.kind == kind)
        pack = filters.get('pack') or ''
        if pack:
            reqs = reqs.filtered(lambda r: r.pack_key == pack)
        rows = [self._rule_payload(r) for r in reqs]
        rows.sort(key=lambda r: (not r['active'], r['pack'] or '',
                                 fold(r['name'])))
        converted_rules = set(reqs.mapped('rule_id').ids)
        converted_sched = set(reqs.mapped('schedule_id').ids)
        legacy_rules = [dict(r, converted=r['id'] in converted_rules)
                        for r in self._safe(self._rule_rows, default=[])]
        legacy_schedules = [
            dict(s, converted=s['id'] in converted_sched)
            for s in self._safe(lambda: self._schedule_rows(
                fields.Date.today()), default=[])]
        return {
            'allowed': True,
            'can_manage': self._can_manage(),
            'rows': rows,
            'legacy_rules': legacy_rules,
            'legacy_schedules': legacy_schedules,
            'lists': self._safe(self._required_lists, default={}),
            'day1': flag(self.env, P_DAY1_AUTO),
        }

    @api.model
    def _requirement(self, requirement_id):
        req = self.env['pb.training.requirement'].sudo().with_context(
            active_test=False).browse(as_id(requirement_id)).exists()
        if not req or req.company_id.id not in self.env.companies.ids:
            raise UserError(_("That rule is not here any more."))
        return req

    @api.model
    def save_requirement(self, payload=None):
        """Create or edit one rule from the drawer. Managers only."""
        self._require_manager()
        payload = payload or {}
        name = (payload.get('name') or '').strip()
        if not name:
            raise UserError(_("Give the rule a name people will recognise."))
        kind = payload.get('kind') or 'always'
        target = payload.get('target') or 'course'
        if kind not in ('always', 'day_one', 'recurring', 'statutory'):
            kind = 'always'
        if target not in ('course', 'certificate', 'licence', 'hours',
                          'path'):
            target = 'course'

        def ids(key, model):
            wanted = [as_id(v) for v in (payload.get(key) or []) if as_id(v)]
            return [(6, 0, self.env[model].sudo().browse(wanted).exists().ids)]

        def integer(key, default=0):
            try:
                return max(int(payload.get(key) or default), 0)
            except (TypeError, ValueError):
                return default

        channel = as_id(payload.get('channel_id'))
        if target == 'course' and not channel:
            raise UserError(_("Pick the course people must do."))
        path = as_id(payload.get('path_id')) if target == 'path' else 0
        if target == 'path':
            channel = 0
            if not self.env['pb.training.path'].sudo().search_count(
                    [('id', '=', path),
                     ('company_id', 'in', self.env.companies.ids)]):
                raise UserError(_("Pick the learning path people must "
                                  "finish."))
        pattern = (payload.get('name_pattern') or '').strip()[:200]
        if target in ('certificate', 'licence') and not pattern and \
                not channel:
            raise UserError(_("Say what the paper is called — the words on "
                              "it — or link the course that issues it."))
        try:
            hours = max(float(payload.get('hours_required') or 0), 0.0)
        except (TypeError, ValueError):
            hours = 0.0
        if target == 'hours' and not hours:
            raise UserError(_("Say how many hours."))
        vals = {
            'name': name[:200],
            'kind': kind,
            'target': target,
            'channel_id': channel or False,
            'path_id': path or False,
            'refresher_channel_id':
                as_id(payload.get('refresher_channel_id')) or False,
            'name_pattern': pattern,
            'hours_required': hours,
            'validity_months': integer('validity_months'),
            'due_days': integer('due_days', 30) or 30,
            'every_months': integer('every_months'),
            'department_ids': ids('department_ids', 'hr.department'),
            'job_ids': ids('job_ids', 'hr.job'),
            'work_location_ids': ids('work_location_ids', 'hr.work.location'),
            'country_ids': ids('country_ids', 'res.country'),
            'employee_types': ','.join(
                t for t in (payload.get('employee_types') or [])
                if t in dict(EMPLOYEE_TYPES)),
            'safety_groups': ','.join(
                g for g in (payload.get('safety_groups') or [])
                if g in SAFETY_GROUP_LABEL),
            'include_contractors': bool(payload.get('include_contractors',
                                                    True)),
            'auto_assign': bool(payload.get('auto_assign')),
            'counts_for_probation': bool(payload.get('counts_for_probation')),
            'note': (payload.get('note') or '')[:2000],
        }
        if target in ('certificate', 'licence'):
            cat = self.env['pb.training.certificate']._licence_category() \
                if target == 'licence' \
                else self.env['pb.training.certificate']._category()
            vals['document_category_id'] = cat.id if cat else False
        if kind == 'recurring' and not (vals['every_months']
                                        or vals['validity_months']):
            raise UserError(_("Say how often it comes round — one month or "
                              "more."))
        if kind == 'recurring' and not vals['validity_months']:
            vals['validity_months'] = vals['every_months']
        req_id = as_id(payload.get('id'))
        if req_id:
            req = self._requirement(req_id)
            req.write(vals)
            message = _("%s is saved.", req.name)
        else:
            vals['company_id'] = self.env.company.id
            req = self.env['pb.training.requirement'].sudo().create(vals)
            message = _("%s is now a required-training rule.", req.name)
        return {'id': req.id, 'message': message}

    @api.model
    def toggle_requirement_auto(self, requirement_id):
        self._require_manager()
        req = self._requirement(requirement_id)
        req.auto_assign = not req.auto_assign
        if req.auto_assign:
            return {'message': _("%s now assigns itself every morning to "
                                 "whoever is missing it.", req.name)}
        return {'message': _("%s no longer assigns itself.", req.name)}

    @api.model
    def archive_requirement(self, requirement_id):
        self._require_manager()
        req = self._requirement(requirement_id)
        req.write({'active': not req.active, 'pack_paused': False})
        if req.active:
            return {'message': _("%s is switched on.", req.name)}
        return {'message': _("%s is switched off. Nobody is measured against "
                             "it until it is switched on again.", req.name)}

    # =====================================================================
    #  acting from the matrix
    # =====================================================================
    @api.model
    def _assign_one(self, req, emp, cell, today):
        """(assignment, reason-word-if-not)."""
        if req.target == 'path':
            return self._enrol_one(req, emp, cell, today)
        channel = req.refresher_channel_id \
            if cell['state'] == 'expiring' and req.refresher_channel_id \
            else req.channel_id
        if not channel:
            return None, 'no_course'
        if not emp.user_id:
            return None, 'no_login'
        if cell.get('open_id'):
            return None, 'already'
        Assignment = self.env['pb.training.assignment'].sudo()
        if Assignment.search_count([('channel_id', '=', channel.id),
                                    ('employee_id', '=', emp.id),
                                    ('state', 'in', ('assigned',
                                                     'in_progress',
                                                     'overdue',
                                                     'excused'))]):
            return None, 'already'
        joins = self.env['pb.training.requirement']._join_dates(emp) \
            if req.kind == 'day_one' else {}
        vals = req._assignment_vals(emp, channel, today, joins.get(emp.id),
                                    cell)
        with self.env.cr.savepoint():
            row = Assignment.create(vals)
        return row, ''

    @api.model
    def _enrol_one(self, req, emp, cell, today):
        """LEARNING L3: a learning-path rule's "Assign now" puts the person on
        the path (reason Required). (enrolment, reason-word-if-not)."""
        if not req.path_id:
            return None, 'no_course'
        if not emp.user_id:
            return None, 'no_login'
        if cell.get('enrolment_id'):
            return None, 'already'
        res = self.env['pb.training.path.enrolment'].sudo()._enrol_people(
            req.path_id.id, [emp.id], reason='required')
        if res.get('made'):
            return self.env['pb.training.path.enrolment'].sudo().browse(
                res['made'][0]), ''
        if res.get('no_login'):
            return None, 'no_login'
        return None, 'already'

    @api.model
    def assign_from_cell(self, requirement_id, employee_id):
        self._require_write()
        req = self._requirement(requirement_id)
        emp = self.env['hr.employee'].sudo().browse(
            as_id(employee_id)).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            raise UserError(_("That person is not in your company."))
        today = fields.Date.today()
        cell = self.env['pb.training.requirement'].evaluate(
            req, employees=emp, today=today).get((req.id, emp.id))
        if not cell or cell['state'] == 'exempt':
            raise UserError(_("This rule is not about %s.", emp.name))
        if cell['state'] in ('valid',):
            raise UserError(_("%s already holds it.", emp.name))
        row, why = self._assign_one(req, emp, cell, today)
        if why == 'no_course':
            raise UserError(_("No course is linked to this rule yet — link "
                              "one in Rules."))
        if why == 'no_login':
            raise UserError(_("%s has no login yet, so there is nowhere for "
                              "the course to appear.", emp.name))
        if why == 'already':
            raise UserError(_("%s is already on the course.", emp.name))
        if req.target == 'path':
            return {'enrolment_id': row.id,
                    'message': _("%(who)s is on the path %(path)s, due "
                                 "%(when)s.", who=emp.name,
                                 path=row.path_id.name,
                                 when=_date_words(self.env, row.due_date))}
        return {'assignment_id': row.id,
                'message': _("%(who)s is on %(course)s, due %(when)s.",
                             who=emp.name, course=row.channel_id.name,
                             when=_date_words(self.env, row.due_date))}

    @api.model
    def bulk_assign_required(self, employee_ids, requirement_id=None):
        """Every missing or expiring cell of the picked people, at once."""
        self._require_write()
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        if not ids:
            raise UserError(_("Pick at least one person."))
        cap = number(self.env, 'pb_training.bulk_assign_cap', 200)
        if len(ids) > cap:
            raise UserError(_("That is %(n)s people at once. The most this "
                              "screen will do in one press is %(cap)s.",
                              n=len(ids), cap=cap))
        reqs = self._live_requirements(requirement_id) \
            if requirement_id else self._live_requirements()
        reqs = reqs.filtered(lambda r: not r._is_headcount())
        emps = self.env['hr.employee'].sudo().search(
            [('id', 'in', ids), ('company_id', 'in', self.env.companies.ids)])
        today = fields.Date.today()
        cells = self.env['pb.training.requirement'].evaluate(
            reqs, employees=emps, today=today)
        made = already = no_login = no_course = 0
        for emp in emps:
            for req in reqs:
                cell = cells.get((req.id, emp.id))
                if not cell or cell['state'] not in ('missing', 'expiring',
                                                     'not_due'):
                    continue
                try:
                    row, why = self._assign_one(req, emp, cell, today)
                except UserError:
                    row, why = None, 'already'
                if row:
                    made += 1
                elif why == 'no_login':
                    no_login += 1
                elif why == 'no_course':
                    no_course += 1
                else:
                    already += 1
        if not made:
            bits = [_("No course was put on.")]
        elif made == 1:
            bits = [_("1 course put on.")]
        else:
            bits = [_("%s courses put on.", made)]
        if already:
            bits.append(_("%s were already under way.", already))
        if no_login:
            bits.append(_("%s could not be put on — no login yet.",
                          no_login))
        if no_course:
            bits.append(_("%s have no course linked yet.", no_course))
        return {'made': made, 'message': ' '.join(bits),
                'type': 'success' if made else 'warning'}

    @api.model
    def set_safety_group(self, employee_ids, group):
        self._require_manager()
        group = str(group or '')
        if group and group not in SAFETY_GROUP_LABEL:
            raise UserError(_("There is no safety group %s.", group))
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        emps = self.env['hr.employee'].sudo().search(
            [('id', 'in', ids), ('company_id', 'in', self.env.companies.ids)])
        if not emps:
            raise UserError(_("Pick at least one person."))
        emps.write({'pb_safety_group': group or False})
        if not group:
            return {'message': _("The safety group is cleared for %s "
                                 "people.", len(emps)) if len(emps) != 1
                    else _("The safety group is cleared for %s.",
                           emps.name)}
        word = tr(self.env, SAFETY_GROUP_LABEL[group])
        if len(emps) == 1:
            return {'message': _("%(who)s is now in %(group)s.",
                                 who=emps.name, group=word)}
        return {'message': _("%(n)s people are now in %(group)s.",
                             n=len(emps), group=word)}

    # =====================================================================
    #  exports
    # =====================================================================
    @api.model
    def matrix_xlsx(self, filters=None):
        self._require_read()
        data = self._matrix_data(filters or {}, paged=False)
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(_("This system cannot build spreadsheets at the "
                              "moment. Ask an administrator to look at it."))
        wb = openpyxl.Workbook()
        head = Font(bold=True, color='FFFFFF')
        fill = PatternFill('solid', fgColor='5A4BB0')
        tint = {
            'valid': PatternFill('solid', fgColor='ECFDF5'),
            'expiring': PatternFill('solid', fgColor='FFFBEB'),
            'missing': PatternFill('solid', fgColor='FEF2F2'),
            'in_progress': PatternFill('solid', fgColor='EEF2FF'),
        }

        def header(ws, columns):
            for i, label in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=i, value=label)
                cell.font = head
                cell.fill = fill
                cell.alignment = Alignment(wrap_text=True, vertical='top')
                ws.column_dimensions[get_column_letter(i)].width = \
                    28 if i == 1 else 20
            ws.freeze_panes = 'B2'

        ws = wb.active
        ws.title = _('Required training')[:31]
        cols = data['columns']
        header(ws, [_('Person'), _('Department'), _('Job'), _('Site'),
                    _('Safety group')] + [c['name'] for c in cols])
        for r, row in enumerate(data['rows'], start=2):
            for c, value in enumerate(
                    [row['name'], row['department'], row['job'], row['site'],
                     row['safety_group_word']], start=1):
                ws.cell(row=r, column=c, value=value)
            for c, col in enumerate(cols, start=6):
                cell = row['cells'].get(str(col['id']))
                if not cell:
                    continue
                target = ws.cell(row=r, column=c, value=cell['words'])
                if cell['state'] in tint:
                    target.fill = tint[cell['state']]
        gaps = wb.create_sheet(_('Gaps')[:31])
        header(gaps, [_('Person'), _('Department'), _('Rule'),
                      _('Where it stands')])
        line = 2
        for row in data['rows']:
            for col in cols:
                cell = row['cells'].get(str(col['id']))
                if cell and cell['state'] in ('missing', 'expiring'):
                    for c, value in enumerate(
                            [row['name'], row['department'], col['name'],
                             cell['words']], start=1):
                        gaps.cell(row=line, column=c, value=value)
                    line += 1
        out = io.BytesIO()
        wb.save(out)
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.getvalue()).decode(),
            'filename': _('Required training %s.xlsx',
                          fields.Date.to_string(fields.Date.today())),
            'mimetype': ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'),
            'rows': len(data['rows']),
        }

    @api.model
    def matrix_pdf(self, filters=None):
        """The print-out, for at most PDF_MAX_PEOPLE people.

        FOUND LIVE: a printed page of 40 people is ~3.7 MB from the live PDF
        engine, so the whole demo company (4,547 people) came to 428 MB — a
        file no browser takes in one answer. An auditor prints a site or a
        department; the spreadsheet carries everybody."""
        self._require_read()
        filters = filters or {}
        total = self._matrix_data(filters, paged=False)['total']
        if total > PDF_MAX_PEOPLE:
            raise UserError(_(
                "That is %(n)s people. The print-out takes up to %(cap)s at a "
                "time — narrow it by department, site, job or rule. The "
                "spreadsheet has everybody.", n=total, cap=PDF_MAX_PEOPLE))
        return self.env['pb.training.matrix.export'].build(filters)

    # =====================================================================
    #  settings (Settings › HR › Required training)
    # =====================================================================
    @api.model
    def required_settings(self):
        if not self._can_read():
            return {'allowed': False}
        company = self.env.company
        Req = self.env['pb.training.requirement']
        packs = []
        for pack in PACKS:
            copies = Req.sudo().with_context(active_test=False).search(
                [('company_id', '=', company.id),
                 ('pack_key', '=', pack['key'])])
            templates = Req._templates(pack['key'])
            packs.append({
                'cc': pack['cc'],
                'key': pack['key'],
                'label': tr(self.env, pack['label']),
                'blurb': tr(self.env, pack['blurb']),
                'on': Req._pack_is_on(pack['cc'], company),
                'rules': len(templates),
                'unverified': len(templates.filtered('unverified')),
                'active': len(copies.filtered('active')),
                'note': _("Skills Development Levy (0.25% of monthly wages, "
                          "at least S$2 and at most S$11.25 a month) is "
                          "already worked out by payroll.")
                if pack['cc'] == 'sg' else (
                    _("Anyone with no safety group set counts as group 4. "
                      "Set another group on the person's record.")
                    if pack['cc'] == 'vn' else ''),
            })
        return {
            'allowed': True,
            'can_manage': self._can_manage(),
            'company': company.name,
            'renew_before': number(self.env, P_RENEW_BEFORE, 60),
            'enforce_cap': number(self.env, P_ENFORCE_CAP, 500),
            'day1': flag(self.env, P_DAY1_AUTO),
            'packs': packs,
        }

    @api.model
    def save_required_settings(self, payload=None):
        self._require_manager()
        payload = payload or {}
        icp = self.env['ir.config_parameter'].sudo()
        if 'renew_before' in payload:
            days = max(min(int(payload.get('renew_before') or 0), 365), 0)
            icp.set_param(P_RENEW_BEFORE, str(days))
        if 'enforce_cap' in payload:
            cap = max(min(int(payload.get('enforce_cap') or 0), 10000), 0)
            icp.set_param(P_ENFORCE_CAP, str(cap))
        if 'day1' in payload:
            icp.set_param(P_DAY1_AUTO, '1' if payload.get('day1') else '0')
        return {'message': _("Saved.")}

    @api.model
    def switch_pack(self, cc, on):
        self._require_manager()
        pack = PACK_BY_CC.get(cc or '')
        if not pack:
            raise UserError(_("There is no such country pack."))
        res = self.env['pb.training.requirement']._switch_pack(
            cc, self.env.company, bool(on))
        label = tr(self.env, pack['label'])
        if on:
            message = _("%(pack)s is on for %(company)s. Review the rules and "
                        "switch on Assign it by itself where you want it.",
                        pack=label, company=self.env.company.name)
        else:
            message = _("%(pack)s is off for %(company)s. Its rules are "
                        "archived, not deleted.", pack=label,
                        company=self.env.company.name)
        return dict(res, message=message)

    # =====================================================================
    #  the People drawer chip
    # =====================================================================
    @api.model
    def safety_chip(self, employee_id):
        user = self.env.user
        if not (self._can_read() or user.has_group('hr.group_hr_user')):
            return {'found': False}
        emp = self.env['hr.employee'].sudo().browse(
            as_id(employee_id)).exists()
        if not emp or emp.company_id.id not in self.env.companies.ids:
            return {'found': False}
        group, by_default = effective_safety_group(
            emp.pb_safety_group or '',
            emp.company_id.partner_id.country_id.code or '')
        site = emp.work_location_id.name or ''
        if not group and not site:
            return {'found': False}
        label = ''
        if group:
            label = _("Safety group %s (by default)", group) if by_default \
                else _("Safety group %s", group)
        return {
            'found': True,
            'group': group,
            'by_default': by_default,
            'label': label,
            'tooltip': tr(self.env, SAFETY_GROUP_LABEL.get(group, ''))
            if group else '',
            'site': site,
        }

    # =====================================================================
    #  what the Overview reads
    # =====================================================================
    @api.model
    def _required_overview(self):
        if not self._live_requirements():
            return {'has_rules': False, 'percent': None, 'missing': 0,
                    'expiring': 0, 'people_missing': 0, 'people': 0}
        data = self._matrix_data({}, paged=False)
        s = data['summary']
        return {'has_rules': True, 'percent': s['percent'],
                'missing': s['missing'], 'expiring': s['expiring'],
                'people_missing': s['people_missing'],
                'people': s['people'],
                'shortfalls': len(data['shortfalls'])}

    @api.model
    def _required_fragment(self, req):
        n = req.get('people_missing', 0)
        if not n:
            return ''
        if n == 1:
            return _("1 person is missing required training.")
        return _("%s people are missing required training.", n)

    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'assign_from_cell':
            return self.assign_from_cell(payload.get('requirement_id'),
                                         payload.get('employee_id'))
        if verb == 'bulk_assign_required':
            return self.bulk_assign_required(payload.get('employee_ids'),
                                             payload.get('requirement_id'))
        if verb == 'set_safety_group':
            return self.set_safety_group(payload.get('employee_ids'),
                                         payload.get('group'))
        if verb == 'save_requirement':
            return self.save_requirement(payload)
        if verb == 'toggle_requirement_auto':
            return self.toggle_requirement_auto(payload.get('requirement_id'))
        if verb == 'archive_requirement':
            return self.archive_requirement(payload.get('requirement_id'))
        if verb == 'switch_pack':
            return self.switch_pack(payload.get('cc'), payload.get('on'))
        if verb == 'save_required_settings':
            return self.save_required_settings(payload)
        return super().act(verb, payload)


class PbTrainingMatrixExport(models.TransientModel):
    """The matrix as pages an auditor can hold (cloned from
    `pb.budget.export`, handover F7)."""
    _name = 'pb.training.matrix.export'
    _description = 'Required training matrix export'

    filters_json = fields.Text(default='{}')

    #: People per printed page.
    PAGE_ROWS = 40

    @api.model
    def build(self, filters):
        rec = self.create({'filters_json': json.dumps(filters or {})})
        return rec._pdf()

    def data(self):
        """Rebuilt for the render, from the same facade, AS THE READER."""
        self.ensure_one()
        try:
            filters = json.loads(self.filters_json or '{}')
        except ValueError:
            filters = {}
        board = self.env['pb.training']._matrix_data(filters, paged=False)
        rows = board['rows']
        board['pages_rows'] = [rows[i:i + self.PAGE_ROWS]
                               for i in range(0, len(rows), self.PAGE_ROWS)] \
            or [[]]
        board['filter_words'] = self._filter_words(filters)
        board['today_words'] = _date_words(self.env, fields.Date.today())
        return board

    def _filter_words(self, filters):
        bits = []
        Env = self.env
        if filters.get('department_id'):
            bits.append(Env['hr.department'].sudo().browse(
                as_id(filters['department_id'])).display_name)
        if filters.get('job_id'):
            bits.append(Env['hr.job'].sudo().browse(
                as_id(filters['job_id'])).name)
        if filters.get('work_location_id'):
            bits.append(Env['hr.work.location'].sudo().browse(
                as_id(filters['work_location_id'])).name)
        if filters.get('safety_group'):
            bits.append(_("Safety group %s", filters['safety_group']))
        if filters.get('country_code'):
            bits.append(filters['country_code'])
        if filters.get('q'):
            bits.append('"%s"' % filters['q'])
        return ', '.join(b for b in bits if b) or _("Everybody")

    def _pdf(self):
        self.ensure_one()
        report = self.env.ref('pb_training.action_report_required_matrix',
                              raise_if_not_found=False)
        if not report:
            raise UserError(_("The matrix report is not installed on this "
                              "system."))
        # NOT `sudo()` (F7): the report re-reads the matrix while it renders,
        # and a superuser env would see every company.
        pdf, _ext = report.with_context(
            allowed_company_ids=self.env.companies.ids,
        )._render_qweb_pdf('pb_training.report_required_matrix',
                           res_ids=self.ids)
        return {
            'ok': True,
            'file_b64': base64.b64encode(pdf).decode(),
            'filename': _('Required training %s.pdf',
                          fields.Date.to_string(fields.Date.today())),
            'mimetype': 'application/pdf',
        }


def _num(value):
    value = float(value or 0.0)
    return ('%d' % value) if value == int(value) else ('%.1f' % value)


def _date_words(env, day):
    if not day:
        return ''
    try:
        from odoo.tools.misc import format_date
        return format_date(env, day, date_format='d MMM y')
    except Exception:                       # noqa: BLE001
        return fields.Date.to_string(day)
