# -*- coding: utf-8 -*-
"""`pb.report.builder` — the facade behind Insights › Build a report.

THE ONE RULE: every read happens AS THE PERSON READING, through the ORM.
There is no superuser switch and no raw SQL anywhere in this module (a test greps
for both). Record rules, multi-company rules, field groups and Access Studio
(`biz_access/models/studio_policy.py` — which overrides `_has_field_access`
and refuses protected fields even under sudo, ledger DS-3) all apply exactly
as they do on the normal screens, so a shared report can never show anybody
more than they could already see.

A REPORT is a spec (a small dict). Every call cleans it against the registry
FOR THE CURRENT READER (`_clean_spec`): a key the registry does not know is
refused; a key the registry knows but this reader may not see is dropped
with a plain note ("2 columns are hidden because you may not see them") —
never an error and never the value. No domain and no field name from the
client reaches the ORM: domains are BUILT here from registry paths and
type-checked values.

Spec::

    {'subject': 'people',
     'columns': ['name', 'department', 'person.job', 'count.leave_days', ...],
     'sort': {'key': 'name', 'dir': 'asc'} | None,
     'filters': [{'key': 'department', 'op': 'in', 'value': [3, 4]}, ...],
     'period': {'preset': 'this_year', 'from': None, 'to': None, 'date': 'start_date'},
     'group_by': ['department'],                # at most two
     'totals': {'days': 'sum', 'name': 'count'},
     'summary': False}
"""
import base64
import calendar
import io
import logging
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, format_datetime, formatLang

try:  # the tenant's own name for the product (WHITELABEL)
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

from .subjects import PAY_GROUP

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ access
#: Who may open "Build a report": the three analytics tiers the Insights hub
#: already gates on, HR officers, and settings administrators. Each SUBJECT
#: then asks the model itself (`has_access('read')`).
_GATE_GROUPS = (
    'pb_hr_payroll_base.group_payroll_base_manager',
    'pb_hr_payroll_base.group_payroll_analytics_user',
    'pb_hr_payroll_base.group_payroll_super_admin',
    'hr.group_hr_user',
    'base.group_system',
)

# ------------------------------------------------------------------- caps
PAGE = 50
PAGE_MAX = 200
EXPORT_CAP = 10000
MAX_COLUMNS = 40
MAX_FILTERS = 20
MAX_GROUP_BY = 2
GROUP_CAP = 500
MAX_IN = 200
TEXT_MAX = 200
READ_BATCH = 1000

SPEC_KEYS = ('subject', 'columns', 'sort', 'filters', 'period', 'group_by', 'totals',
             'summary')
PRESETS = ('any', 'this_month', 'last_month', 'this_quarter', 'this_year',
           'last_12', 'next_30', 'next_60', 'next_90', 'custom')
OPS = ('is', 'is_not', 'contains', 'in', 'empty', 'not_empty', 'between')
KIND_OPS = {
    'text': ('contains', 'is', 'is_not', 'empty', 'not_empty'),
    'choice': ('in', 'is', 'is_not', 'empty', 'not_empty'),
    'link': ('in', 'is', 'is_not', 'contains', 'empty', 'not_empty'),
    'number': ('between', 'is', 'is_not', 'empty', 'not_empty'),
    'money': ('between', 'is', 'is_not', 'empty', 'not_empty'),
    'date': ('between', 'is', 'empty', 'not_empty'),
    'datetime': ('between', 'empty', 'not_empty'),
    'bool': ('is',),
}
TYPE_KIND = {
    'char': 'text', 'text': 'text', 'selection': 'choice', 'many2one': 'link',
    'integer': 'number', 'float': 'number', 'monetary': 'money', 'date': 'date',
    'datetime': 'datetime', 'boolean': 'bool',
}
#: The C1 contract's column types (DOCSTUDIO ledger C1).
KIND_C1 = {
    'text': 'text', 'choice': 'text', 'link': 'text', 'number': 'number',
    'money': 'money', 'date': 'date', 'datetime': 'datetime', 'bool': 'bool',
    'count': 'number',
}
TOTALS = ('sum', 'avg', 'count')
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#: A cell starting with one of these is read as a formula by a spreadsheet.
FORMULA_START = ('=', '+', '-', '@', '\t', '\r')
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
_KEY_RE = re.compile(r'^[a-z0-9_.]{1,120}$')
HIDDEN = object()          # a value on a record the reader may not open


class SpecError(UserError):
    """A spec that names something the registry does not know (R4)."""


def _set_text(cell, text):
    """Write `text` as a plain string — never a formula, whatever it starts
    with (cloned from `pb_filter_kit/models/filter_mixin.py` `_set_text`)."""
    cell.value = text
    cell.data_type = 's'
    if text.startswith(FORMULA_START):
        cell.quotePrefix = True


def _safe_file_name(name):
    name = re.sub(r'[\\/:*?"<>|\[\]]+', ' ', name or '').strip()
    return ' '.join(name.split())[:60] or 'Report'


def _sheet_title(name):
    title = re.sub(r'[\[\]:*?/\\]+', ' ', name or '').strip()
    return (' '.join(title.split())[:31]) or 'Report'


class PbReportBuilder(models.AbstractModel):
    _inherit = 'pb.report.builder'

    # ================================================================ gates
    @api.model
    def _can_open(self):
        who = self.env.user
        for xmlid in _GATE_GROUPS:
            if self.env.ref(xmlid, raise_if_not_found=False) and who.has_group(xmlid):
                return True
        return False

    @api.model
    def can_open(self):
        """The hub tab's probe."""
        return self._can_open()

    @api.model
    def _require(self):
        if not self._can_open():
            raise AccessError(self.env._(
                "Building reports is for HR and the people who can open Insights. "
                "Ask your administrator if you believe you should."))

    @api.model
    def _pay_ok(self):
        """Contract pay is shown only to the pay groups — the same test the
        contract panel uses to unmask the wage (`pb_contracts`
        `_cd_unmask_wage`), reused when that module is here."""
        Contracts = self.env.get('pb.contracts')
        if Contracts is not None and hasattr(Contracts, '_cd_unmask_wage'):
            try:
                return bool(Contracts._cd_unmask_wage())
            except Exception:  # noqa: BLE001 — a question, not a crash
                _logger.debug('pb_report_builder: pay test fell back', exc_info=True)
        who = self.env.user
        return bool(who.has_group(PAY_GROUP) if self.env.ref(PAY_GROUP, raise_if_not_found=False)
                    else False) or who._is_admin()

    # ============================================================ resolving
    @api.model
    def _sqlable(self, Model, field):
        """Can the database sort and group on this field? The platform's own
        answer (what the list views' column headers use): stored, inherited,
        or a related field it can join to."""
        try:
            return bool(field._description_sortable(self.env)
                        and field._description_groupable(self.env))
        except Exception:  # noqa: BLE001 — "no" is the safe answer
            return False

    @api.model
    def _searchable(self, field):
        try:
            return bool(field._description_searchable)
        except Exception:  # noqa: BLE001
            return False

    @api.model
    def _resolve(self, model, path, check=True):
        """(field, model name of the field, sqlable, searchable) for a dotted
        registry path, or None when it does not resolve on this database —
        or, with `check`, when the reader may not read a hop of it."""
        M = self.env[model]
        hops = path.split('.')
        sql = True
        search = True
        for i, name in enumerate(hops):
            field = M._fields.get(name)
            if field is None:
                return None
            if check and not M._has_field_access(field, 'read'):
                return None
            sql = sql and self._sqlable(M, field)
            search = search and self._searchable(field)
            if i < len(hops) - 1:
                if field.type != 'many2one':
                    return None
                M = self.env[field.comodel_name]
                if check and not M.has_access('read'):
                    return None
        return field, M._name, sql, search

    @api.model
    def _subject_open(self, subject):
        """(open?, why) — may this reader open a subject at all?"""
        Model = self.env[subject['model']]
        groups = subject.get('groups') or ()
        if groups and not any(self.env.ref(g, raise_if_not_found=False)
                              and self.env.user.has_group(g) for g in groups):
            return False, subject.get('why') or ''
        if not Model.has_access('read'):
            return False, subject.get('why') or ''
        return True, ''

    @api.model
    def _std_labels(self, model):
        """The customer's own names for standard fields (Form builder), so a
        report reads in their words. {} when the Form builder is absent."""
        if 'pb.form.studio' not in self.env:
            return {}
        try:
            rules = self.env['pb.form.studio']._pbfs_std_rules(model) or {}
        except Exception:  # noqa: BLE001 — renames are a nicety
            _logger.debug('pb_report_builder: standard labels unavailable', exc_info=True)
            return {}
        return {name: r.get('label') for name, r in rules.items()
                if isinstance(r, dict) and r.get('label')}

    @api.model
    def _own_fields(self, model):
        """[(name, label)] of the customer's own fields on `model` marked
        "Show in lists", that THIS reader may read (Form builder)."""
        if 'pb.form.studio' not in self.env:
            return []
        try:
            items = self.env['pb.form.studio'].fields_for(model, 'list') or []
        except Exception:  # noqa: BLE001
            _logger.debug('pb_report_builder: own fields unavailable', exc_info=True)
            return []
        return [(i['name'], i.get('label') or i['name']) for i in items
                if isinstance(i, dict) and i.get('name')]

    @api.model
    def _column(self, subject, key, path, label, section, extra=None, check=True):
        """One column for this reader, or None."""
        extra = extra or {}
        if extra.get('pay') and check and not self._pay_ok():
            return None
        resolved = self._resolve(subject['model'], path, check=check)
        if not resolved:
            return None
        field, fmodel, sql, search = resolved
        kind = TYPE_KIND.get(field.type)
        if not kind:
            return None
        col = {
            'key': key, 'label': label, 'section': section, 'path': path, 'kind': kind,
            'sql': sql, 'search': search, 'pay': bool(extra.get('pay')),
            'field_model': fmodel, 'field_name': field.name, 'currency': None,
        }
        if kind == 'choice':
            try:
                col['options'] = [[str(k), str(v)] for k, v in
                                  field._description_selection(self.env)]
            except Exception:  # noqa: BLE001
                col['options'] = []
        if kind == 'link':
            col['comodel'] = field.comodel_name
        if kind == 'money':
            prefix = path.rsplit('.', 1)[0] + '.' if '.' in path else ''
            cur = extra.get('currency')
            if cur:
                cur = prefix + cur
            elif field.currency_field:
                cur = prefix + field.currency_field
            cur_res = self._resolve(subject['model'], cur, check=False) if cur else None
            if not cur_res or cur_res[0].type != 'many2one':
                kind = col['kind'] = 'number'
            else:
                col['currency'] = cur
                col['currency_sql'] = cur_res[2]
        return col

    @api.model
    def _subject_columns(self, subject, check=True):
        """Every column of a subject for this reader: {key: column}, in the
        order the field list shows them."""
        _ = self.env._
        cols = {}
        model = subject['model']
        own_label = self._std_labels(model)
        for key, path, label, extra in subject['fields']:
            label = own_label.get(path) if '.' not in path and own_label.get(path) else label
            col = self._column(subject, key, path, label, 'own', extra, check)
            if col:
                cols[key] = col
        if subject.get('own_host'):
            for name, label in (self._own_fields(subject['own_host']) if check else []):
                col = self._column(subject, 'own.' + name, name, label, 'ownfields', {}, check)
                if col:
                    cols[col['key']] = col
        emp = subject.get('employee_path')
        if emp:
            Employee = self.env['hr.employee']
            if not check or Employee.has_access('read'):
                person_label = self._std_labels('hr.employee')
                for key, path, label, extra in self._pbrb_people_fields():
                    if key == 'name':
                        continue
                    label = person_label.get(path) if '.' not in path and person_label.get(path) \
                        else label
                    col = self._column(subject, 'person.' + key, emp + '.' + path, label,
                                       'person', extra, check)
                    if col:
                        cols[col['key']] = col
                for name, label in (self._own_fields('hr.employee') if check else []):
                    col = self._column(subject, 'person.own.' + name, emp + '.' + name, label,
                                       'person', {}, check)
                    if col:
                        cols[col['key']] = col
        if subject.get('counts'):
            for count in self._pbrb_counts():
                Other = self.env[count['model']]
                if check and not Other.has_access('read'):
                    continue
                if check and self._resolve(count['model'], count['employee']) is None:
                    continue
                cols['count.' + count['key']] = {
                    'key': 'count.' + count['key'], 'label': count['label'],
                    'section': 'counts', 'path': None, 'kind': 'count', 'sql': False,
                    'search': False, 'pay': False, 'count': count, 'currency': None,
                    'dated': bool(count.get('date')),
                }
        return cols

    @api.model
    def _subjects_for_reader(self):
        """[(subject, open, why)] in registry order. A subject whose model
        is not on this database is never listed (an override may add one)."""
        out = []
        for subject in self._pbrb_subjects().values():
            if subject.get('model') not in self.env:
                continue
            ok, why = self._subject_open(subject)
            out.append((subject, ok, why))
        return out

    @api.model
    def _subject(self, key):
        subjects = self._pbrb_subjects()
        if not isinstance(key, str) or key not in subjects or \
                subjects[key].get('model') not in self.env:
            raise SpecError(self.env._("This report is about something this system does "
                                       "not have."))
        return subjects[key]

    # ============================================================= public
    @api.model
    def _public_column(self, col):
        out = {
            'key': col['key'], 'label': col['label'], 'section': col['section'],
            'kind': col['kind'],
            'sortable': bool(col['sql']),
            'groupable': bool(col['sql']) and col['kind'] in (
                'text', 'choice', 'link', 'bool', 'date', 'datetime', 'number'),
            'filterable': bool(col['search']),
            'totals': self._totals_for(col),
            'pay': col['pay'],
        }
        if col.get('options') is not None:
            out['options'] = col['options']
        if col['kind'] == 'count':
            out['dated'] = col.get('dated', False)
        return out

    @api.model
    def _totals_for(self, col):
        if col['kind'] == 'count':
            return ['sum', 'avg']
        if col['kind'] in ('number',) and col['sql'] and '.' not in col['path']:
            return ['sum', 'avg', 'count']
        if col['kind'] == 'money' and col['sql'] and '.' not in col['path'] \
                and col.get('currency_sql'):
            return ['sum', 'avg', 'count']
        return ['count'] if col['search'] else []

    @api.model
    def _presets(self):
        _ = self.env._
        return [
            {'key': 'any', 'label': _("Any time")},
            {'key': 'this_month', 'label': _("This month")},
            {'key': 'last_month', 'label': _("Last month")},
            {'key': 'this_quarter', 'label': _("This quarter")},
            {'key': 'this_year', 'label': _("This year")},
            {'key': 'last_12', 'label': _("Last 12 months")},
            {'key': 'next_30', 'label': _("Next 30 days")},
            {'key': 'next_60', 'label': _("Next 60 days")},
            {'key': 'next_90', 'label': _("Next 90 days")},
            {'key': 'custom', 'label': _("Pick dates")},
        ]

    @api.model
    def _op_words(self):
        _ = self.env._
        return {
            'is': _("is"), 'is_not': _("is not"), 'contains': _("contains"),
            'in': _("is one of"), 'empty': _("is empty"), 'not_empty': _("is not empty"),
            'between': _("between"),
        }

    @api.model
    def _section_words(self, subject):
        _ = self.env._
        return {
            'own': _("%(subject)s fields", subject=subject['label']),
            'person': _("About the person"),
            'counts': _("Counts from other areas"),
            'ownfields': _("Your own fields"),
        }

    @api.model
    def schema(self):
        """Everything the screen needs to draw the field list: the subjects
        this reader may open (and the ones they may not, with the reason),
        their fields by section, the periods and the filter words."""
        _ = self.env._
        if not self._can_open():
            return {'allowed': False, 'why': _(
                "Building reports is for HR and the people who can open Insights. "
                "Ask your administrator if you believe you should.")}
        subjects = []
        for subject, ok, why in self._subjects_for_reader():
            entry = {'key': subject['key'], 'label': subject['label'],
                     'hint': subject.get('hint') or '',
                     'icon': subject.get('icon') or 'table', 'locked': not ok, 'why': why}
            if ok:
                cols = self._subject_columns(subject)
                words = self._section_words(subject)
                sections = []
                for sec in ('own', 'person', 'counts', 'ownfields'):
                    items = [self._public_column(c) for c in cols.values()
                             if c['section'] == sec]
                    if items:
                        sections.append({'key': sec, 'label': words[sec], 'fields': items})
                entry.update({
                    'sections': sections,
                    'dates': [{'key': k, 'label': lab} for k, path, lab, _x in subject['dates']
                              if self._resolve(subject['model'], path)],
                    'date_optional': bool(subject.get('date_optional')),
                    'person': bool(subject.get('employee_path') is not None),
                })
            subjects.append(entry)
        return {
            'allowed': True,
            'subjects': subjects,
            'presets': self._presets(),
            'ops': {kind: [{'key': op, 'label': self._op_words()[op]} for op in ops]
                    for kind, ops in KIND_OPS.items()},
            'note': self._visibility_note() or '',
            'page': PAGE,
            'export_cap': EXPORT_CAP,
        }

    # ============================================================ cleaning
    @api.model
    def _clean_spec(self, spec, strict=True):
        """(clean spec, subject, {key: column}, notes).

        A key the registry does not know at all is REFUSED (SpecError) when
        `strict`; a key it knows that this reader may not see is DROPPED with
        a note. A stored report (`strict=False`) drops both, so a report
        never stops opening because a module was removed."""
        _ = self.env._
        if not isinstance(spec, dict):
            raise SpecError(_("This report could not be read."))
        unknown = [k for k in spec if k not in SPEC_KEYS]
        if unknown and strict:
            raise SpecError(_("This report asks for something the report builder does not "
                              "know."))
        subject = self._subject(spec.get('subject'))
        ok, why = self._subject_open(subject)
        if not ok:
            raise AccessError(why or _("You cannot open this kind of report."))
        cols = self._subject_columns(subject)
        every = None   # the registry for ANY reader, built only when needed

        def known(key):
            nonlocal every
            if every is None:
                every = self._subject_columns(subject, check=False)
                # the customer's own fields (made with the Form builder) are
                # known whoever reads; any other field name is not
                if subject.get('own_host'):
                    for name, field in self.env[subject['own_host']]._fields.items():
                        if getattr(field, 'manual', False):
                            every.setdefault('own.' + name, None)
                if subject.get('employee_path'):
                    for name, field in self.env['hr.employee']._fields.items():
                        if getattr(field, 'manual', False):
                            every.setdefault('person.own.' + name, None)
            return key in every

        hidden = []
        refused = []

        def take(key):
            if not isinstance(key, str) or not _KEY_RE.match(key):
                refused.append(key)
                return None
            if key in cols:
                return key
            if known(key):
                hidden.append(key)
            else:
                refused.append(key)
            return None

        columns = []
        raw_cols = spec.get('columns') or []
        if not isinstance(raw_cols, list):
            raise SpecError(_("This report could not be read."))
        for key in raw_cols[:MAX_COLUMNS]:
            key = take(key)
            if key and key not in columns:
                columns.append(key)

        sort = None
        raw_sort = spec.get('sort')
        if isinstance(raw_sort, dict) and raw_sort.get('key'):
            key = take(raw_sort.get('key'))
            if key and cols[key]['sql']:
                sort = {'key': key, 'dir': 'desc' if raw_sort.get('dir') == 'desc' else 'asc'}
        elif raw_sort not in (None, False, {}) and strict:
            raise SpecError(_("This report's order could not be read."))

        filters = []
        dropped_filters = 0
        raw_filters = spec.get('filters') or []
        if not isinstance(raw_filters, list):
            raise SpecError(_("This report's filters could not be read."))
        for flt in raw_filters[:MAX_FILTERS]:
            if not isinstance(flt, dict):
                raise SpecError(_("This report's filters could not be read."))
            key = take(flt.get('key'))
            if not key:
                dropped_filters += 1
                continue
            col = cols[key]
            if not col['search']:
                dropped_filters += 1
                continue
            op = flt.get('op')
            if op not in KIND_OPS.get(col['kind'], ()):
                if strict:
                    raise SpecError(_("A filter in this report cannot be used on that field."))
                dropped_filters += 1
                continue
            value = self._clean_value(col, op, flt.get('value'), strict)
            filters.append({'key': key, 'op': op, 'value': value})

        period = self._clean_period(subject, spec.get('period'), strict)

        group_by = []
        raw_group = spec.get('group_by') or []
        if not isinstance(raw_group, list):
            raise SpecError(_("This report's groups could not be read."))
        for key in raw_group[:MAX_GROUP_BY]:
            key = take(key)
            if key and key not in group_by and self._public_column(cols[key])['groupable']:
                group_by.append(key)

        totals = {}
        raw_totals = spec.get('totals') or {}
        if not isinstance(raw_totals, dict):
            raise SpecError(_("This report's totals could not be read."))
        for key, how in list(raw_totals.items())[:MAX_COLUMNS]:
            key = take(key)
            if not key:
                continue
            if how not in TOTALS:
                if strict:
                    raise SpecError(_("A total in this report cannot be worked out."))
                continue
            if how in self._totals_for(cols[key]):
                totals[key] = how

        if refused and strict:
            raise SpecError(_("This report asks for a field the report builder does not "
                              "know."))
        notes = []
        hidden_cols = len({k for k in hidden if k in set(raw_cols)})
        if hidden_cols:
            notes.append(_("%(count)s columns are hidden because you may not see them.",
                           count=hidden_cols) if hidden_cols > 1 else
                         _("1 column is hidden because you may not see it."))
        hidden_filters = dropped_filters
        if hidden_filters:
            notes.append(_("%(count)s filters were left out because they use fields you may "
                           "not see, so the result may be wider than the saved report.",
                           count=hidden_filters) if hidden_filters > 1 else
                         _("1 filter was left out because it uses a field you may not see, "
                           "so the result may be wider than the saved report."))
        clean = {
            'subject': subject['key'], 'columns': columns, 'sort': sort, 'filters': filters,
            'period': period, 'group_by': group_by, 'totals': totals,
            'summary': bool(spec.get('summary')) and bool(group_by),
        }
        return clean, subject, cols, notes

    @api.model
    def _clean_value(self, col, op, value, strict=True):
        """The filter value, type-checked for the column. Anything that does
        not fit is refused (strict) — nothing unchecked reaches a domain."""
        _ = self.env._
        bad = SpecError(_("A filter value in this report could not be read."))
        kind = col['kind']
        if op in ('empty', 'not_empty'):
            return None
        if kind == 'bool':
            if not isinstance(value, bool):
                raise bad
            return value
        if op == 'between':
            if not isinstance(value, dict):
                raise bad
            lo = self._scalar(kind, value.get('from'), bad, allow_none=True)
            hi = self._scalar(kind, value.get('to'), bad, allow_none=True)
            if lo is None and hi is None:
                raise bad
            return {'from': lo, 'to': hi}
        if op == 'in':
            if not isinstance(value, list) or not value or len(value) > MAX_IN:
                raise bad
            return [self._scalar(kind, v, bad) for v in value]
        if op == 'contains':
            if not isinstance(value, str) or not value.strip() or len(value) > TEXT_MAX:
                raise bad
            return value.strip()
        return self._scalar(kind, value, bad)

    @api.model
    def _scalar(self, kind, value, bad, allow_none=False):
        if value in (None, '') and allow_none:
            return None
        if kind == 'link':
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise bad
            return value
        if kind == 'choice':
            if not isinstance(value, str) or len(value) > TEXT_MAX:
                raise bad
            return value
        if kind == 'text':
            if not isinstance(value, str) or len(value) > TEXT_MAX:
                raise bad
            return value
        if kind in ('number', 'money'):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise bad
            return value
        if kind in ('date', 'datetime'):
            if not isinstance(value, str):
                raise bad
            try:
                return fields.Date.to_string(fields.Date.to_date(value[:10]))
            except (ValueError, TypeError):
                raise bad from None
        raise bad

    @api.model
    def _clean_period(self, subject, period, strict=True):
        _ = self.env._
        bad = SpecError(_("This report's period could not be read."))
        dates = [k for k, path, lab, _x in subject['dates'] if self._resolve(subject['model'], path)]
        default_date = '' if subject.get('date_optional') else (dates[0] if dates else '')
        if not period:
            return {'preset': 'any', 'from': None, 'to': None, 'date': default_date}
        if not isinstance(period, dict):
            raise bad
        preset = period.get('preset') or 'any'
        if preset not in PRESETS:
            if strict:
                raise bad
            preset = 'any'
        date_key = period.get('date')
        if date_key in (None, ''):
            date_key = default_date
        if date_key and date_key not in dates:
            if strict and date_key not in [d[0] for d in subject['dates']]:
                raise bad
            date_key = default_date
        start = end = None
        if preset == 'custom':
            try:
                start = fields.Date.to_string(fields.Date.to_date(period.get('from'))) \
                    if period.get('from') else None
                end = fields.Date.to_string(fields.Date.to_date(period.get('to'))) \
                    if period.get('to') else None
            except (ValueError, TypeError):
                raise bad from None
            if not start and not end:
                preset = 'any'
        return {'preset': preset, 'from': start, 'to': end, 'date': date_key}

    # ============================================================= domains
    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _period_range(self, period):
        """(first day, last day) or (None, None) for 'any'."""
        today = self._today()
        preset = period['preset']
        if preset == 'this_month':
            return today.replace(day=1), today.replace(
                day=calendar.monthrange(today.year, today.month)[1])
        if preset == 'last_month':
            first = today.replace(day=1) - relativedelta(months=1)
            return first, today.replace(day=1) - timedelta(days=1)
        if preset == 'this_quarter':
            q0 = 3 * ((today.month - 1) // 3) + 1
            first = today.replace(month=q0, day=1)
            return first, first + relativedelta(months=3) - timedelta(days=1)
        if preset == 'this_year':
            return date(today.year, 1, 1), date(today.year, 12, 31)
        if preset == 'last_12':
            return today - relativedelta(months=12) + timedelta(days=1), today
        if preset in ('next_30', 'next_60', 'next_90'):
            return today, today + timedelta(days=int(preset[5:]))
        if preset == 'custom':
            return (fields.Date.to_date(period['from']) if period.get('from') else None,
                    fields.Date.to_date(period['to']) if period.get('to') else None)
        return None, None

    @api.model
    def _utc(self, day, end=False):
        """The first moment of `day` (or of the next day, when `end`) in the
        reader's time zone, as a naive UTC datetime string."""
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        moment = datetime.combine(day + timedelta(days=1) if end else day, time.min)
        return fields.Datetime.to_string(tz.localize(moment).astimezone(pytz.UTC)
                                         .replace(tzinfo=None))

    @api.model
    def _range_domain(self, path, ftype, start, end):
        out = []
        if ftype == 'datetime':
            if start:
                out.append((path, '>=', self._utc(start)))
            if end:
                out.append((path, '<', self._utc(end, end=True)))
        else:
            if start:
                out.append((path, '>=', fields.Date.to_string(start)))
            if end:
                out.append((path, '<=', fields.Date.to_string(end)))
        return out

    @api.model
    def _filter_domain(self, col, op, value):
        path = col['path']
        kind = col['kind']
        if op == 'empty':
            return [(path, '=', False)]
        if op == 'not_empty':
            return [(path, '!=', False)]
        if kind == 'bool':
            return [(path, '=', bool(value))]
        if op == 'contains':
            return [(path, 'ilike', value)]
        if op == 'in':
            return [(path, 'in', value)]
        if op == 'between':
            if kind in ('date', 'datetime'):
                lo = fields.Date.to_date(value['from']) if value.get('from') else None
                hi = fields.Date.to_date(value['to']) if value.get('to') else None
                return self._range_domain(path, kind, lo, hi)
            out = []
            if value.get('from') is not None:
                out.append((path, '>=', value['from']))
            if value.get('to') is not None:
                out.append((path, '<=', value['to']))
            return out
        if kind == 'date' and op == 'is':
            return [(path, '=', value)]
        return [(path, '=' if op == 'is' else '!=', value)]

    @api.model
    def _domain(self, clean, subject, cols):
        """The ONE domain a report reads with: the reader's scope, the
        subject's own limits, the filters and the period — every piece
        built here from registry paths."""
        domain = []
        company_path = subject.get('company_path')
        if company_path and self._resolve(subject['model'], company_path, check=False):
            cids = self._visible_companies(self.env.companies.ids or [self.env.company.id])
            domain += ['|', (company_path, '=', False), (company_path, 'in', cids)]
        dept_path = subject.get('department_path')
        departments = self._visible_departments()
        if departments and dept_path and self._resolve(subject['model'], dept_path, check=False):
            domain.append((dept_path, 'in', departments))
        if subject.get('archived'):
            asks_active = any(f['key'] == 'active' for f in clean['filters'])
            leaving = clean['period']['date'] == 'leaving_date' \
                and clean['period']['preset'] != 'any'
            if not asks_active and not leaving:
                domain.append(('active', '=', True))
        for flt in clean['filters']:
            domain += self._filter_domain(cols[flt['key']], flt['op'], flt['value'])
        period = clean['period']
        if period['date'] and period['preset'] != 'any':
            path = dict((d[0], d[1]) for d in subject['dates'])[period['date']]
            res = self._resolve(subject['model'], path, check=False)
            start, end = self._period_range(period)
            domain += self._range_domain(path, res[0].type, start, end)
        return domain

    @api.model
    def _model(self, subject):
        Model = self.env[subject['model']]
        if subject.get('archived'):
            Model = Model.with_context(active_test=False)
        return Model

    # ============================================================== reading
    @api.model
    def _read_safe(self, Model, ids, fnames):
        """{id: {fname: value}} as the reader. Records the reader may not
        open are left out (their cells read as hidden), never raised."""
        ids = [i for i in ids if i]
        out = {}
        for start in range(0, len(ids), READ_BATCH):
            chunk = Model.browse(ids[start:start + READ_BATCH])
            try:
                rows = chunk.read(fnames)
            except AccessError:
                rows = chunk._filtered_access('read').read(fnames)
            for row in rows:
                out[row['id']] = row
        return out

    @api.model
    def _path_values(self, records, path):
        """{record id: python value | HIDDEN} for a registry path, read hop
        by hop as the reader. many2one → (id, name); others → the value. A
        record the reader may not open reads as HIDDEN all the way down."""
        Model = records.with_context(active_test=False).browse()
        return self._path_values_from(Model, {rid: rid for rid in records.ids},
                                      path.split('.'))

    @api.model
    def _path_values_from(self, Model, current, hops):
        """The values of `hops` from `Model`, for a {row id: record id} map."""
        for i, name in enumerate(hops):
            data = self._read_safe(Model, list(set(current.values()) - {False, None}), [name])
            last = i == len(hops) - 1
            nxt = {}
            for rid, cid in current.items():
                if cid in (False, None):
                    nxt[rid] = None if last else False
                    continue
                row = data.get(cid)
                if row is None:
                    nxt[rid] = HIDDEN
                    continue
                value = row[name]
                nxt[rid] = value if last else (value[0] if value else False)
            if last:
                return nxt
            hidden = {rid for rid, v in nxt.items() if v is HIDDEN}
            Model = self.env[Model._fields[name].comodel_name].with_context(active_test=False)
            current = {rid: (None if v is HIDDEN else v) for rid, v in nxt.items()}
            if hidden:
                rest = self._path_values_from(Model, current, hops[i + 1:])
                for rid in hidden:
                    rest[rid] = HIDDEN
                return rest
        return {}

    @api.model
    def _count_values(self, count, emp_ids, period):
        """{employee id: number} for one "Counts from other areas" column,
        ONE `_read_group` on the other model, as the reader."""
        Other = self.env[count['model']]
        emp = count['employee']
        domain = list(count.get('domain') or []) + [(emp, 'in', list(emp_ids))]
        domain += self._count_period_domain(count, period)
        out = defaultdict(float)
        if count['agg'] == 'days':
            for emp_rec, _day, _n in Other._read_group(
                    domain, [emp, count['date'] + ':day'], ['__count']):
                out[emp_rec.id] += 1
        else:
            for emp_rec, value in Other._read_group(domain, [emp], [count['agg']]):
                out[emp_rec.id] += value or 0
        return out

    @api.model
    def _count_period_domain(self, count, period):
        if not count.get('date') or period['preset'] == 'any':
            return []
        start, end = self._period_range(period)
        field = self.env[count['model']]._fields.get(count['date'])
        return self._range_domain(count['date'], field.type if field else 'date', start, end)

    @api.model
    def _currency_map(self, records, col):
        """{record id: res.currency} for a money column."""
        values = self._path_values(records, col['currency'])
        ids = {v[0] for v in values.values() if v and v is not HIDDEN}
        currencies = {c.id: c for c in self.env['res.currency'].browse(list(ids))}
        return {rid: (currencies.get(v[0]) if v and v is not HIDDEN else None)
                for rid, v in values.items()}

    @api.model
    def _values(self, records, keys, cols, period):
        """{key: {record id: python value | HIDDEN}} plus {key: currency map}."""
        values, currencies = {}, {}
        for key in keys:
            col = cols[key]
            if col['kind'] == 'count':
                counted = self._count_values(col['count'], records.ids, period)
                values[key] = {rid: counted.get(rid, 0) for rid in records.ids}
                continue
            values[key] = self._path_values(records, col['path'])
            if col['kind'] == 'money' and col.get('currency'):
                currencies[key] = self._currency_map(records, col)
        return values, currencies

    # ============================================================ displays
    @api.model
    def _num(self, value, kind='number'):
        if value is None or value is False:
            return ''
        digits = 0
        if isinstance(value, float):
            if abs(value - round(value)) > 1e-9:
                digits = 1 if abs(value * 10 - round(value * 10)) < 1e-9 else 2
        return formatLang(self.env, value, digits=digits)

    @api.model
    def _money(self, value, currency):
        if value is None or value is False:
            return ''
        if currency:
            return formatLang(self.env, value, currency_obj=currency)
        return self._num(value)

    @api.model
    def _display(self, col, value, currency=None):
        """What a cell shows on screen. Never the value of a record the
        reader may not open."""
        _ = self.env._
        if value is HIDDEN:
            return '•••'
        kind = col['kind']
        if kind == 'bool':
            return _("Yes") if value else _("No")
        if value in (None, False, '') and kind not in ('number', 'money', 'count'):
            return ''
        if kind == 'link':
            return value[1] if isinstance(value, (list, tuple)) else str(value or '')
        if kind == 'choice':
            return dict(col.get('options') or []).get(str(value), str(value))
        if kind == 'date':
            return format_date(self.env, value)
        if kind == 'datetime':
            return format_datetime(self.env, value, tz=self.env.user.tz or False,
                                   dt_format='short')
        if kind == 'money':
            return self._money(value, currency)
        if kind in ('number', 'count'):
            return self._num(value)
        return str(value)

    @api.model
    def _python(self, col, value):
        """The C1 python value of a cell (`_pbxl_table`)."""
        if value is HIDDEN:
            return None
        kind = col['kind']
        if kind == 'bool':
            return bool(value)
        if value in (None, False, ''):
            return 0 if kind == 'count' else None
        if kind == 'link':
            return value[1] if isinstance(value, (list, tuple)) else str(value)
        if kind == 'choice':
            return dict(col.get('options') or []).get(str(value), str(value))
        if kind == 'date':
            return fields.Date.to_date(value)
        if kind == 'datetime':
            tz = pytz.timezone(self.env.user.tz or 'UTC')
            moment = fields.Datetime.to_datetime(value)
            return pytz.UTC.localize(moment).astimezone(tz).replace(tzinfo=None)
        if kind in ('number', 'money', 'count'):
            return value
        return str(value)

    # ============================================================== order
    @api.model
    def _ordered(self, Model, domain, clean, cols, offset, limit):
        """The records of one page, in the report's order. A sort on a
        field one or more links away is done by the database through a
        one-row-per-record `_read_group`, so paging stays exact."""
        sort = clean['sort']
        terms = []
        dotted = False
        for key in clean['group_by']:
            col = cols[key]
            direction = sort['dir'] if sort and sort['key'] == key else 'asc'
            spec = self._order_spec(col, grouped=True)
            terms.append((col['path'], spec, direction))
            dotted = dotted or '.' in col['path'] or spec != col['path']
        if sort and sort['key'] not in clean['group_by'] and cols[sort['key']]['sql']:
            col = cols[sort['key']]
            spec = self._order_spec(col)
            terms.append((col['path'], spec, sort['dir']))
            dotted = dotted or '.' in col['path'] or spec != col['path']
        if not terms:
            return Model.search(domain, offset=offset, limit=limit)
        if not dotted:
            order = ', '.join('%s %s' % (path, d) for path, spec, d in terms) + ', id'
            return Model.search(domain, order=order, offset=offset, limit=limit)
        groupby = [spec for path, spec, d in terms] + ['id']
        order = ', '.join('%s %s' % (spec, d) for path, spec, d in terms) + ', id'
        rows = Model._read_group(domain, groupby, [], order=order, offset=offset, limit=limit)
        # grouping by 'id' answers the record itself
        return Model.browse([row[-1].id if isinstance(row[-1], models.BaseModel) else row[-1]
                             for row in rows])

    @api.model
    def _order_spec(self, col, grouped=False):
        """How the database orders a column. A link one or more steps away
        is ordered by the linked record's NAME (the platform would order it
        by its id); dates by day, or by month when they are a group."""
        if col['kind'] in ('date', 'datetime'):
            return col['path'] + (':month' if grouped else ':day')
        if col['kind'] == 'link' and '.' in col['path']:
            Comodel = self.env[col['comodel']]
            for rec in (Comodel._rec_name, 'name'):
                field = Comodel._fields.get(rec) if rec else None
                try:
                    usable = bool(field and field._description_groupable(self.env))
                except Exception:  # noqa: BLE001
                    usable = False
                if usable:
                    return '%s.%s' % (col['path'], rec)
        return col['path']

    @api.model
    def _group_spec(self, col):
        if col['kind'] in ('date', 'datetime'):
            return col['path'] + ':month'
        return col['path']

    # ============================================================== groups
    @api.model
    def _group_value_json(self, col, value):
        """A group's value as the screen sends it back to open that group."""
        if col['kind'] == 'link':
            return value.id if value else False
        if col['kind'] in ('date', 'datetime'):
            return fields.Date.to_string(value) if value else False
        if col['kind'] == 'bool':
            return bool(value)
        return value if value not in (None, '') else False

    @api.model
    def _group_label(self, col, value):
        _ = self.env._
        if col['kind'] == 'bool':
            return _("Yes") if value else _("No")
        if value in (None, False, ''):
            return _("Not set")
        if col['kind'] == 'link':
            try:
                return value.display_name or _("Not set")
            except AccessError:
                return _("Not visible to you")
        if col['kind'] == 'choice':
            return dict(col.get('options') or []).get(str(value), str(value))
        if col['kind'] in ('date', 'datetime'):
            return format_date(self.env, value, date_format='MMMM yyyy')
        if col['kind'] == 'number':
            return self._num(value)
        return str(value)

    @api.model
    def _group_domain(self, col, value):
        """The domain of ONE group of a column, from the value the screen
        sent back — type-checked like a filter value."""
        _ = self.env._
        bad = SpecError(_("This group could not be opened."))
        path = col['path']
        kind = col['kind']
        if value is False or value is None:
            if kind == 'bool':
                return [(path, '=', False)]
            return [(path, '=', False)]
        if kind == 'link':
            if isinstance(value, bool) or not isinstance(value, int):
                raise bad
            return [(path, '=', value)]
        if kind in ('date', 'datetime'):
            try:
                first = fields.Date.to_date(value).replace(day=1)
            except (ValueError, TypeError, AttributeError):
                raise bad from None
            last = first + relativedelta(months=1) - timedelta(days=1)
            return self._range_domain(path, kind, first, last)
        if kind == 'bool':
            if not isinstance(value, bool):
                raise bad
            return [(path, '=', value)]
        if kind == 'number':
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise bad
            return [(path, '=', value)]
        if not isinstance(value, str) or len(value) > 500:
            raise bad
        return [(path, '=', value)]

    @api.model
    def _aggregates(self, Model, domain, clean, cols, groupby):
        """{group tuple: {key: display text}} and {group tuple: {key: python}}
        of the report's totals, one `_read_group` per kind of total. Money
        is grouped by currency as well: never one sum over two currencies."""
        texts = defaultdict(dict)
        values = defaultdict(dict)
        n = len(groupby)
        simple = [(k, how) for k, how in clean['totals'].items()
                  if cols[k]['kind'] == 'number' and how in ('sum', 'avg')]
        if simple:
            aggs = ['%s:%s' % (cols[k]['path'], how) for k, how in simple]
            for row in Model._read_group(domain, groupby, aggs):
                gkey, vals = row[:n], row[n:]
                for (k, how), v in zip(simple, vals):
                    values[gkey][k] = v or 0
                    texts[gkey][k] = self._num(v or 0)
        for k, how in clean['totals'].items():
            col = cols[k]
            if col['kind'] == 'money' and how in ('sum', 'avg'):
                per = defaultdict(list)
                for row in Model._read_group(domain, groupby + [col['currency']],
                                             ['%s:%s' % (col['path'], how)]):
                    gkey, currency, v = row[:n], row[n], row[n + 1]
                    per[gkey].append((currency, v or 0))
                for gkey, items in per.items():
                    items.sort(key=lambda x: (x[0].name or '') if x[0] else '')
                    values[gkey][k] = [(c.name if c else '', v) for c, v in items]
                    texts[gkey][k] = ' · '.join(self._money(v, c) for c, v in items)
            elif how == 'count' and col['kind'] != 'count':
                extra = [(col['path'], '=', True)] if col['kind'] == 'bool' \
                    else [(col['path'], '!=', False)]
                for row in Model._read_group(domain + extra, groupby, ['__count']):
                    values[row[:n]][k] = row[n]
                    texts[row[:n]][k] = self._num(row[n])
            elif col['kind'] == 'count' and how in ('sum', 'avg'):
                self._count_aggregates(Model, domain, clean, col, groupby, how, values, texts)
        return texts, values

    @api.model
    def _count_aggregates(self, Model, domain, clean, col, groupby, how, values, texts):
        """Totals of a "Counts from other areas" column per group of people:
        the other model grouped by the person's own group fields."""
        count = col['count']
        Other = self.env[count['model']]
        emp = count['employee']
        n = len(groupby)
        other_groupby = ['%s.%s' % (emp, g) for g in groupby]
        people = Model._search(domain)
        odomain = list(count.get('domain') or []) + [(emp, 'in', people)]
        odomain += self._count_period_domain(count, clean['period'])
        sums = defaultdict(float)
        if count['agg'] == 'days':
            for row in Other._read_group(odomain, other_groupby + [emp, count['date'] + ':day'],
                                         ['__count']):
                sums[row[:n]] += 1
        else:
            for row in Other._read_group(odomain, other_groupby, [count['agg']]):
                sums[row[:n]] += row[n] or 0
        if how == 'avg':
            heads = {row[:n]: row[n] for row in Model._read_group(domain, groupby, ['__count'])}
            for gkey, head in heads.items():
                v = (sums.get(gkey, 0) / head) if head else 0
                values[gkey][col['key']] = v
                texts[gkey][col['key']] = self._num(round(v, 2))
        else:
            heads = {row[:n] for row in Model._read_group(domain, groupby, ['__count'])} \
                if groupby else {()}
            for gkey in heads:
                values[gkey][col['key']] = sums.get(gkey, 0)
                texts[gkey][col['key']] = self._num(sums.get(gkey, 0))

    @api.model
    def _groups(self, Model, domain, clean, cols):
        """The group tree with counts and subtotals (at most GROUP_CAP at
        each level; the screen says so when there are more)."""
        gcols = [cols[k] for k in clean['group_by']]
        specs = [self._group_spec(c) for c in gcols]
        texts, values = self._aggregates(Model, domain, clean, cols, specs)
        rows = Model._read_group(domain, specs, ['__count'])
        tree = []
        index = {}
        capped = False
        for row in rows:
            gvals, count = row[:-1], row[-1]
            top = gvals[:1]
            node = index.get(top)
            if node is None:
                if len(tree) >= GROUP_CAP:
                    capped = True
                    continue
                node = {'key': [self._group_value_json(gcols[0], top[0])],
                        'label': self._group_label(gcols[0], top[0]),
                        'count': 0, 'totals': {}, 'children': [], '_g': top}
                index[top] = node
                tree.append(node)
            node['count'] += count
            if len(gcols) > 1:
                if len(node['children']) >= GROUP_CAP:
                    capped = True
                    continue
                node['children'].append({
                    'key': node['key'] + [self._group_value_json(gcols[1], gvals[1])],
                    'label': self._group_label(gcols[1], gvals[1]),
                    'count': count, 'totals': texts.get(tuple(gvals), {}),
                    '_g': tuple(gvals), '_v': values.get(tuple(gvals), {}),
                })
        if len(gcols) > 1:
            top_texts, top_values = self._aggregates(Model, domain, clean, cols, specs[:1])
        else:
            top_texts, top_values = texts, values
        for node in tree:
            node['totals'] = top_texts.get(node['_g'], {})
            node['_v'] = top_values.get(node['_g'], {})

        def order(col, depth):
            def key(node):
                value = node['_g'][depth]
                empty = value in (None, False, '') or (
                    isinstance(value, models.BaseModel) and not value)
                if col['kind'] in ('date', 'datetime', 'number') and not empty:
                    return (0, value, '')
                return (1 if empty else 0, 0 if col['kind'] in ('date', 'datetime', 'number')
                        else 0, (node['label'] or '').lower())
            return key
        tree.sort(key=order(gcols[0], 0))
        if len(gcols) > 1:
            for node in tree:
                node['children'].sort(key=order(gcols[1], 1))
        return tree, capped

    @api.model
    def _strip(self, tree):
        out = []
        for node in tree:
            item = {k: v for k, v in node.items() if not k.startswith('_')}
            if node.get('children'):
                item['children'] = self._strip(node['children'])
            out.append(item)
        return out

    # ================================================================= run
    @api.model
    def run(self, spec, offset=0, limit=PAGE, group=None):
        """One page of the report for the screen.

        {ok, spec, columns, rows, ids, total, offset, has_more, groups,
         totals, notes}. With `group` (the key list of one group, as the
        groups came back) only that group's rows are answered."""
        self._require()
        _ = self.env._
        clean, subject, cols, notes = self._clean_spec(spec)
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE), PAGE_MAX))
        except (TypeError, ValueError):
            raise SpecError(_("This page of the report could not be read.")) from None
        Model = self._model(subject)
        domain = self._domain(clean, subject, cols)
        columns = [self._public_column(cols[k]) for k in clean['columns']]
        answer = {'ok': True, 'spec': clean, 'columns': columns, 'notes': notes,
                  'subject': subject['key'], 'groups': None, 'totals': {},
                  'filter_words': self._filter_words(clean, cols)}
        if group is not None:
            if not isinstance(group, list) or not group or len(group) > len(clean['group_by']):
                raise SpecError(_("This group could not be opened."))
            for key, value in zip(clean['group_by'], group):
                domain = domain + self._group_domain(cols[key], value)
        total = Model.search_count(domain)
        answer['total'] = total
        if group is None:
            texts, _values = self._aggregates(Model, domain, clean, cols, [])
            answer['totals'] = texts.get((), {})
            if clean['group_by']:
                tree, capped = self._groups(Model, domain, clean, cols)
                answer['groups'] = self._strip(tree)
                if capped:
                    notes.append(_("Only the first %(cap)s groups are shown. Add a filter to "
                                   "see the others.", cap=GROUP_CAP))
                answer.update({'rows': [], 'ids': [], 'offset': 0, 'has_more': False})
                return answer
        records = self._ordered(Model, domain, clean, cols, offset, limit) \
            if clean['columns'] else Model.browse()
        values, currencies = self._values(records, clean['columns'], cols, clean['period'])
        rows = []
        for rec in records:
            rows.append([self._display(cols[k], values[k].get(rec.id),
                                       currencies.get(k, {}).get(rec.id))
                         for k in clean['columns']])
        answer.update({'rows': rows, 'ids': records.ids, 'offset': offset,
                       'has_more': offset + len(records) < total})
        return answer

    @api.model
    def _filter_words(self, clean, cols):
        """Each filter as a sentence for its chip ("Department is one of
        Sales, IT"), names read as the reader."""
        _ = self.env._
        words = self._op_words()
        out = []
        for flt in clean['filters']:
            col = cols[flt['key']]
            op, value = flt['op'], flt['value']
            if op in ('empty', 'not_empty'):
                out.append('%s %s' % (col['label'], words[op]))
                continue
            if col['kind'] == 'bool':
                out.append('%s: %s' % (col['label'], _("Yes") if value else _("No")))
                continue
            if op == 'between':
                lo, hi = value.get('from'), value.get('to')
                show = (lambda v: format_date(self.env, v)) if col['kind'] in (
                    'date', 'datetime') else self._num
                if lo is not None and hi is not None:
                    text = _("%(field)s from %(low)s to %(high)s", field=col['label'],
                             low=show(lo), high=show(hi))
                elif lo is not None:
                    text = _("%(field)s from %(low)s", field=col['label'], low=show(lo))
                else:
                    text = _("%(field)s up to %(high)s", field=col['label'], high=show(hi))
                out.append(text)
                continue
            items = value if isinstance(value, list) else [value]
            if col['kind'] == 'link' and op != 'contains':
                names = {}
                try:
                    for rec in self.env[col['comodel']].browse(items).exists():
                        names[rec.id] = rec.display_name
                except AccessError:
                    names = {}
                shown = [names.get(i, '…') for i in items]
            elif col['kind'] == 'choice':
                options = dict(col.get('options') or [])
                shown = [options.get(str(i), str(i)) for i in items]
            elif col['kind'] == 'date':
                shown = [format_date(self.env, i) for i in items]
            elif col['kind'] in ('number', 'money'):
                shown = [self._num(i) for i in items]
            else:
                shown = ['“%s”' % i if op == 'contains' else str(i) for i in items]
            listed = ', '.join(shown[:3]) + (_(" and %(count)s more", count=len(shown) - 3)
                                             if len(shown) > 3 else '')
            out.append('%s %s %s' % (col['label'], words[op], listed))
        return out

    @api.model
    def values_for(self, subject_key, key, search=''):
        """Choices for an "is one of" filter on a linked field: up to 20
        names matching `search`, read as the reader."""
        self._require()
        subject = self._subject(subject_key)
        ok, _why = self._subject_open(subject)
        if not ok:
            return []
        cols = self._subject_columns(subject)
        col = cols.get(key) if isinstance(key, str) else None
        if not col or col['kind'] != 'link':
            raise SpecError(self.env._("That field has no list of choices."))
        Comodel = self.env[col['comodel']]
        text = search if isinstance(search, str) else ''
        try:
            found = Comodel.name_search(text[:TEXT_MAX], limit=20)
        except AccessError:
            return []
        return [{'id': rid, 'label': name} for rid, name in found]

    # =========================================================== the table
    @api.model
    def _pbrb_table(self, spec, title='', strict=False):
        """The finished table (ledger C1 shape) for Excel and for any
        exporter: python values, every row up to EXPORT_CAP, as the reader.

        Summary mode answers one row per group. A money column is followed
        by a "currency" column so a number never loses its money."""
        _ = self.env._
        clean, subject, cols, notes = self._clean_spec(spec, strict=strict)
        Model = self._model(subject)
        domain = self._domain(clean, subject, cols)
        out_cols = []
        if clean['summary'] and clean['group_by']:
            tree, capped = self._groups(Model, domain, clean, cols)
            gcols = [cols[k] for k in clean['group_by']]
            for c in gcols:
                out_cols.append({'key': c['key'], 'label': c['label'], 'type': 'text'})
            out_cols.append({'key': '__count', 'label': _("Rows"), 'type': 'number'})
            total_keys = [k for k in clean['columns'] if k in clean['totals']]
            for k in total_keys:
                self._c1_columns(cols[k], out_cols, total=clean['totals'][k])
            rows = []

            def emit(node, labels):
                row = labels + [''] * (len(gcols) - len(labels)) + [node['count']]
                for k in total_keys:
                    row += self._c1_total(cols[k], node.get('_v', {}).get(k))
                rows.append(row)

            for node in tree:
                if node.get('children'):
                    for child in node['children']:
                        emit(child, [node['label'], child['label']])
                else:
                    emit(node, [node['label']])
            if capped:
                notes.append(_("Only the first %(cap)s groups are included.", cap=GROUP_CAP))
            return {'title': title or subject['label'], 'columns': out_cols, 'rows': rows,
                    'truncated': capped, 'note': ' '.join(notes),
                    '_groups': len(gcols), '_summary': True}
        # a grouped report's file leads with its group fields, so every
        # subtotal row can say which group it closes
        keys = [k for k in clean['group_by'] if k not in clean['columns']] + clean['columns'] \
            if clean['columns'] else []
        for k in keys:
            self._c1_columns(cols[k], out_cols)
        total = Model.search_count(domain)
        records = self._ordered(Model, domain, clean, cols, 0, EXPORT_CAP) if keys \
            else Model.browse()
        rows = []
        for start in range(0, len(records), READ_BATCH):
            chunk = records[start:start + READ_BATCH]
            values, currencies = self._values(chunk, keys, cols, clean['period'])
            for rec in chunk:
                row = []
                for k in keys:
                    col = cols[k]
                    row.append(self._python(col, values[k].get(rec.id)))
                    if col['kind'] == 'money' and col.get('currency'):
                        cur = currencies.get(k, {}).get(rec.id)
                        row.append(cur.name if cur else None)
                rows.append(row)
        truncated = total > len(records)
        if truncated:
            notes.append(_("This report has %(total)s rows; the first %(cap)s are included.",
                           total=formatLang(self.env, total, digits=0),
                           cap=formatLang(self.env, EXPORT_CAP, digits=0)))
        return {'title': title or subject['label'], 'columns': out_cols, 'rows': rows,
                'truncated': truncated, 'note': ' '.join(notes),
                '_group_idx': [keys.index(k) for k in clean['group_by'] if k in keys],
                '_totals': {k: how for k, how in clean['totals'].items() if k in keys},
                '_keys': keys, '_cols': cols}

    @api.model
    def _c1_columns(self, col, out, total=None):
        _ = self.env._
        label = col['label']
        if total:
            words = {'sum': _("total"), 'avg': _("average"), 'count': _("count")}
            label = '%s (%s)' % (col['label'], words[total])
        ctype = KIND_C1[col['kind']] if not (total == 'count') else 'number'
        out.append({'key': col['key'], 'label': label, 'type': ctype})
        if col['kind'] == 'money' and col.get('currency') and total != 'count':
            out.append({'key': col['key'] + '__currency',
                        'label': _("%(field)s currency", field=col['label']), 'type': 'text'})

    @api.model
    def _c1_total(self, col, value):
        """A summary row's cells for one total (money: amount + currency;
        several currencies are joined in words, never added)."""
        if col['kind'] == 'money' and col.get('currency') and isinstance(value, list):
            if len(value) == 1:
                return [value[0][1], value[0][0]]
            return [' · '.join('%s %s' % (formatLang(self.env, v, digits=2), c)
                               for c, v in value), None]
        if col['kind'] == 'money' and col.get('currency'):
            return [value, None]
        return [value]

    # ================================================================ Excel
    @api.model
    def export_xlsx(self, spec, name=''):
        """The full report as an Excel file (cap EXPORT_CAP rows, said
        plainly when hit). {ok, file_b64, filename, mimetype, rows,
        truncated, note}."""
        self._require()
        _ = self.env._
        name = ' '.join(str(name or '').split())[:80]
        table = self._pbrb_table(spec, title=name, strict=True)
        try:
            data = self._xlsx_bytes(table)
        except ImportError:
            return {'ok': False, 'msg': _("Spreadsheets cannot be written on this server yet. "
                                          "Ask an administrator to install the spreadsheet "
                                          "library.")}
        day = fields.Date.to_string(self._today())
        return {
            'ok': True,
            'file_b64': base64.b64encode(data).decode('ascii'),
            'filename': '%s %s %s.xlsx' % (_safe_file_name(product_label(self.env)),
                                           _safe_file_name(table['title']), day),
            'mimetype': XLSX_MIME,
            'rows': len(table['rows']),
            'truncated': table['truncated'],
            'note': table['note'],
        }

    @api.model
    def _xlsx_bytes(self, table):
        """One sheet: heading row, rows, subtotal rows under each group
        (worked out from the rows in the file), a grand total row, then the
        note. Text is always written as text (formula-injection safe)."""
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        _ = self.env._

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _sheet_title(table['title'])
        head_font = Font(bold=True, color='241F52')
        head_fill = PatternFill('solid', fgColor='EDEAF8')
        sub_font = Font(bold=True, color='241F52')
        sub_fill = PatternFill('solid', fgColor='F5F6FA')
        columns = table['columns']
        widths = []
        for idx, col in enumerate(columns, start=1):
            label = _CONTROL_RE.sub('', str(col['label']))
            cell = ws.cell(row=1, column=idx)
            _set_text(cell, label)
            cell.font = head_font
            cell.fill = head_fill
            cell.alignment = Alignment(vertical='center')
            widths.append(min(max(len(label) + 2, 10), 48))
        yes, no = _("Yes"), _("No")

        def put(r, idx, value, ctype, font=None, fill=None):
            cell = ws.cell(row=r, column=idx)
            if font:
                cell.font = font
            if fill:
                cell.fill = fill
            if value is None or value == '':
                return
            if isinstance(value, bool):
                _set_text(cell, yes if value else no)
            elif isinstance(value, (int, float)):
                cell.value = value
                cell.number_format = '#,##0.##' if isinstance(value, float) else '#,##0'
            elif isinstance(value, datetime):
                cell.value = value
                cell.number_format = 'dd mmm yyyy hh:mm'
            elif isinstance(value, date):
                cell.value = value
                cell.number_format = 'dd mmm yyyy'
            else:
                text = _CONTROL_RE.sub('', str(value))
                if text:
                    _set_text(cell, text)
                    widths[idx - 1] = min(max(widths[idx - 1], len(text) + 2), 48)

        r = 2
        types = [c['type'] for c in columns]
        if table.get('_summary'):
            for row in table['rows']:
                for idx, value in enumerate(row, start=1):
                    put(r, idx, value, types[idx - 1])
                r += 1
        else:
            r = self._xlsx_rows(table, put, sub_font, sub_fill)
        if table.get('note'):
            r += 1
            cell = ws.cell(row=r, column=1)
            _set_text(cell, _CONTROL_RE.sub('', table['note']))
            cell.font = Font(italic=True, color='64748B')
        for idx, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = w
        ws.freeze_panes = 'A2'
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    @api.model
    def _xlsx_rows(self, table, put, sub_font, sub_fill):
        """Detail rows, with a subtotal row each time a group ends and a
        grand total at the bottom when the report has totals. Returns the
        next free row."""
        _ = self.env._
        cols = table['_cols']
        keys = table['_keys']
        totals = table['_totals']
        # position of each key's value (and currency) in a row
        pos, i = {}, 0
        for k in keys:
            pos[k] = i
            i += 1
            if cols[k]['kind'] == 'money' and cols[k].get('currency'):
                i += 1
        group_idx = [pos[keys[j]] for j in table['_group_idx']]
        r = 2

        def total_row(rows, label, r):
            if not totals:
                return r
            first_text = 0
            put(r, first_text + 1, label, 'text', sub_font, sub_fill)
            for k, how in totals.items():
                col = cols[k]
                p = pos[k]
                vals = [row[p] for row in rows]
                if how == 'count':
                    put(r, p + 1, sum(1 for v in vals if v not in (None, '', False)) if
                        col['kind'] != 'bool' else sum(1 for v in vals if v), 'number',
                        sub_font, sub_fill)
                    continue
                if col['kind'] == 'money' and col.get('currency'):
                    per = defaultdict(list)
                    for row in rows:
                        if row[p] is not None:
                            per[row[p + 1] or ''].append(row[p])
                    if len(per) == 1:
                        (cur, nums), = per.items()
                        put(r, p + 1, sum(nums) if how == 'sum' else sum(nums) / len(nums),
                            'number', sub_font, sub_fill)
                        put(r, p + 2, cur, 'text', sub_font, sub_fill)
                    elif per:
                        words = ' · '.join(
                            '%s %s' % (formatLang(self.env, sum(n) if how == 'sum'
                                                  else sum(n) / len(n), digits=2), c)
                            for c, n in sorted(per.items()))
                        put(r, p + 1, words, 'text', sub_font, sub_fill)
                    continue
                nums = [v for v in vals if isinstance(v, (int, float)) and
                        not isinstance(v, bool)]
                if nums:
                    put(r, p + 1, sum(nums) if how == 'sum' else round(sum(nums) / len(nums), 2),
                        'number', sub_font, sub_fill)
            return r + 1

        rows = table['rows']
        if group_idx and totals:
            current, bucket = None, []
            for row in rows:
                gkey = tuple(row[g] for g in group_idx[:1])
                if current is not None and gkey != current:
                    r = total_row(bucket, _("Total %(group)s", group=self._xl_label(current[0])),
                                  r)
                    bucket = []
                current = gkey
                for idx, value in enumerate(row, start=1):
                    put(r, idx, value, None)
                bucket.append(row)
                r += 1
            if bucket:
                r = total_row(bucket, _("Total %(group)s", group=self._xl_label(current[0])), r)
        else:
            for row in rows:
                for idx, value in enumerate(row, start=1):
                    put(r, idx, value, None)
                r += 1
        if totals and rows:
            r = total_row(rows, _("Grand total"), r)
        return r

    @api.model
    def _xl_label(self, value):
        _ = self.env._
        if value in (None, ''):
            return _("Not set")
        if isinstance(value, bool):
            return _("Yes") if value else _("No")
        if isinstance(value, date):
            return format_date(self.env, value)
        return str(value)
