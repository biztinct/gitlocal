# -*- coding: utf-8 -*-
"""`pb.doc.studio` — the Document studio's one door (RPC facade).

Every public method checks, on the server, that the caller may change letter
templates (`_require`: write access on `pb.letter.template`). Nothing here
elevates rights to read a person: people are searched and read as the caller;
a pay figure is read through the ORM as the caller and, when that is refused,
the preview says "You may not see pay" and a real letter refuses to be made
(ledger DS-3: never "sudo to be safe" for pay).

Public methods (also the contract other phases call — see the F report):
    board()                         the gallery
    open(template_id)               everything the designer needs
    save(template_id, payload)      wording, versions, rules, page, picture
    copy_for(template_id, company_id, country_ids)
    reset(template_id) / undo_reset(template_id)
    set_active(template_id, active)
    create_blank(kind, name)
    preview(template_id, draft, employee_id, lang)
    sample_pdf(template_id, draft, employee_id, lang)
    people(term)
    catalogue(template_id) / condition_fields()
    upload_image(template_id, upload)
    page_styles() / page_values(page, lang)     (contract C3)
"""
import base64
import binascii
import datetime
import json
import logging
import re

from lxml import etree, html as lxml_html
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html_sanitize, is_html_empty
from odoo.tools.misc import format_amount, format_date

from .doc_common import (
    BASE_KEYS, DATE_OP_LABELS, DEFAULT_PAGE, FIELD_GROUPS, FONTS, FONT_KEYS,
    GENERIC_FIELDS, IMAGE_MARKER, IMAGE_MAX, IMAGE_MIMES, KIND_FIELDS, KINDS,
    KIND_KEYS, MAIN_LANG, MARGINS, MARGIN_KEYS, MAX_BODY, NOT_HERE_YET,
    OP_LABELS, OPS, SIGN_KEYS, SIGNS, SIZES, TYPE_FIELDS,
)
from .doc_render import BRACED_RE, RULE_ID_RE, field_keys
from .hr_letter import PayHidden

_logger = logging.getLogger(__name__)

#: Own-field types usable in "Show only when" rules, and how they compare.
OWN_RULE_TYPES = {
    'selection': 'choice', 'many2one': 'choice', 'boolean': 'bool',
    'char': 'text', 'date': 'date', 'datetime': 'date',
    'integer': 'number', 'float': 'number', 'monetary': 'number',
}
IMG_SRC_RE = re.compile(
    r'(<img\b[^>]*?\bsrc=")(/web/image/ir\.attachment/(\d+)/datas\?access_token=[^"]*)(")',
    re.I)
OWN_PREFIX = 'x_'


class PbDocStudio(models.AbstractModel):
    _name = 'pb.doc.studio'
    _description = 'Document studio'

    # ============================================================ rights
    @api.model
    def _require(self):
        """The caller may change letter templates, or nothing here runs."""
        if not self.env['pb.letter.template'].has_access('write'):
            raise AccessError(self.env._(
                "Only people who may change letter wording can use the "
                "Document studio."))

    @api.model
    def _template(self, template_id, mode='write'):
        self._require()
        tmpl = self.env['pb.letter.template'].with_context(
            active_test=False).browse(int(template_id or 0)).exists()
        if not tmpl or tmpl.letter_type in NOT_HERE_YET:
            raise UserError(self.env._("This document no longer exists."))
        tmpl.check_access(mode)
        return tmpl

    # ============================================================ basics
    @api.model
    def _pbds_active_langs(self):
        return set(self.env['res.lang'].sudo().search([]).mapped('code'))

    @api.model
    def _pbds_lang_list(self):
        langs = self.env['res.lang'].sudo().search([])
        out = [{'code': l.code, 'name': l.name} for l in langs]
        out.sort(key=lambda r: (r['code'] != MAIN_LANG, r['name']))
        if not any(r['code'] == MAIN_LANG for r in out):
            out.insert(0, {'code': MAIN_LANG, 'name': 'English (US)'})
        return out

    @api.model
    def _pbds_long_date(self, value, lang):
        if not value:
            return ''
        try:
            return format_date(self.env, value, lang_code=lang, date_format='long')
        except Exception:                              # noqa: BLE001
            return fields.Date.to_string(value)

    @api.model
    def _pbds_country_of_work(self, employees):
        """{employee id: res.country id or False} — the person's Country of
        Work (the box `payroll_country`, country codes, the same one the Form
        builder and the People list read), else their company's country."""
        out = {}
        emps = employees.sudo()
        has_box = 'payroll_country' in emps._fields
        codes = {(e.payroll_country or '').upper() for e in emps if has_box and e.payroll_country}
        by_code = {}
        if codes:
            for c in self.env['res.country'].sudo().search([('code', 'in', list(codes))]):
                by_code[(c.code or '').upper()] = c.id
        for emp in emps:
            cid = False
            if has_box and emp.payroll_country:
                cid = by_code.get(emp.payroll_country.upper(), False)
            out[emp.id] = cid or emp.company_id.country_id.id or False
        return out

    @api.model
    def _pbds_contract(self, employee):
        """The person's current contract, or the latest one; empty if none or
        if the caller may not read it."""
        if 'hr.contract' not in self.env or not employee:
            return self.env['hr.contract'] if 'hr.contract' in self.env else None
        Contract = self.env['hr.contract']
        try:
            contract = employee.contract_id if 'contract_id' in employee._fields else Contract
            if not contract:
                contract = Contract.search(
                    [('employee_id', '=', employee.id), ('state', '!=', 'cancel')],
                    order='date_start desc, id desc', limit=1)
            return contract
        except AccessError:
            return Contract

    # ============================================================ own fields
    @api.model
    def _pbds_own_specs(self):
        """Form builder fields of the employee and the contract the caller may
        read: [{key, model, name, label, type, options}]. No dependency on the
        Form builder: probed."""
        if 'pb.form.studio' not in self.env:
            return []
        Studio = self.env['pb.form.studio']
        out, taken = [], set()
        for model in ('hr.employee', 'hr.contract'):
            if model not in self.env:
                continue
            try:
                specs = Studio.fields_for(model, 'all')
            except Exception:                          # noqa: BLE001
                _logger.info('pb_doc_studio: own fields of %s unavailable', model)
                continue
            for spec in specs:
                name = spec.get('name')
                if not name or not re.match(r'^[_a-zA-Z][_a-zA-Z0-9]*$', name):
                    continue
                key = name if name not in taken else 'contract_%s' % name
                taken.add(key)
                out.append({'key': key, 'model': model, 'name': name,
                            'label': spec.get('label') or name,
                            'type': spec.get('type'),
                            'options': spec.get('options') or [],
                            'comodel': spec.get('comodel') or False})
        return out

    @api.model
    def _pbds_own_values(self, employee, contract, specs):
        """{key: display text} of the own fields, read with the current env."""
        out = {}
        if not specs or 'pb.form.studio' not in self.env:
            return out
        Studio = self.env['pb.form.studio']
        for model, rec in (('hr.employee', employee), ('hr.contract', contract)):
            mine = [s for s in specs if s['model'] == model]
            if not mine or not rec:
                continue
            try:
                vals = Studio._pbfs_values_for(rec, 'all').get(rec.id, {})
            except Exception:                          # noqa: BLE001
                _logger.info('pb_doc_studio: own values of %s unreadable', model)
                vals = {}
            for spec in mine:
                cell = vals.get(spec['name']) or {}
                out[spec['key']] = cell.get('display') or ''
        return out

    @api.model
    def _pbds_own_raw(self, employee, contract, specs):
        """{key: raw value} for rules (many2one = id)."""
        out = {}
        for model, rec in (('hr.employee', employee), ('hr.contract', contract)):
            for spec in specs:
                if spec['model'] != model or not rec or spec['name'] not in rec._fields:
                    continue
                try:
                    value = rec[spec['name']]
                except AccessError:
                    continue
                if spec['type'] == 'many2one':
                    value = value.id or False
                out[spec['key']] = value
        return out

    # ============================================================ values
    @api.model
    def _pbds_generic_values(self, employee, company, lang, keys):
        """`({key: escaped text}, blocked keys)` for the keys this module
        works out (`NEW_KEYS`) and the Form builder's own fields.

        `monthly_pay` is read through the ORM as the caller (never sudo): when
        that is refused the key is returned in `blocked`."""
        env = self.with_context(lang=lang).env
        keys = list(keys or [])
        out, blocked = {}, set()
        if not employee:
            return {}, set()
        emp = employee
        company = company or emp.company_id or env.company
        contract = None

        def get_contract():
            nonlocal contract
            if contract is None:
                contract = self._pbds_contract(emp)
            return contract

        def safe(fn):
            try:
                return fn() or ''
            except AccessError:
                return ''

        for key in keys:
            val = None
            if key == 'legal_name':
                val = safe(lambda: emp.legal_name or emp.name)
            elif key == 'employee_code':
                val = safe(lambda: emp.barcode or emp.identification_id)
            elif key == 'work_email':
                val = safe(lambda: emp.work_email)
            elif key == 'country_of_work':
                cid = self._pbds_country_of_work(emp).get(emp.id)
                val = env['res.country'].sudo().browse(cid).with_context(lang=lang).name if cid else ''
            elif key == 'manager_name':
                val = safe(lambda: emp.parent_id.name)
            elif key == 'work_location':
                val = safe(lambda: emp.work_location_id.name)
            elif key == 'contract_start':
                c = get_contract()
                val = safe(lambda: self._pbds_long_date(c.date_start, lang)) if c else ''
            elif key == 'contract_end':
                c = get_contract()
                val = safe(lambda: self._pbds_long_date(c.date_end, lang)) if c else ''
            elif key == 'contract_type':
                c = get_contract()
                val = safe(lambda: c.contract_type_id.with_context(lang=lang).name) \
                    if c and 'contract_type_id' in c._fields else ''
            elif key == 'monthly_pay' and self._pbds_is_own_record(emp):
                # F-b ruling 2: a person may always get their OWN pay on
                # their OWN document — read the way the salary certificate
                # reads it, for that one person only.
                val = self._pbds_own_pay(emp, company, lang)
                if val is None:
                    blocked.add(key)
                    val = ''
            elif key == 'monthly_pay':
                c = get_contract()
                if c:
                    try:
                        # As the caller, and explicitly: a value already in
                        # the cache (read under sudo by the caller of the
                        # letter) is returned without any check otherwise.
                        plain = c.with_env(self.env(su=False))
                        plain.check_access('read')
                        plain._check_field_access(plain._fields['wage'], 'read')
                        wage = plain.wage
                        currency = plain.currency_id if 'currency_id' in plain._fields \
                            and plain.currency_id else company.currency_id
                        val = format_amount(env, wage or 0.0, currency, lang_code=lang)
                    except AccessError:
                        blocked.add(key)
                        val = ''
                else:
                    val = ''
            elif key == 'company_address':
                partner = company.sudo().partner_id
                lines = [ln.strip() for ln in (partner._display_address(
                    without_company=True) or '').splitlines() if ln.strip()]
                val = ', '.join(lines)
            elif key == 'today_long':
                val = self._pbds_long_date(fields.Date.context_today(self), lang)
            elif key == 'joining_date_long':
                val = safe(lambda: self._pbds_long_date(
                    env['pb.hr.letter']._joining_date(emp), lang))
            if val is not None:
                out[key] = str(escape(val))
        own_keys = [k for k in keys if k not in out]
        if own_keys:
            specs = [s for s in self._pbds_own_specs() if s['key'] in own_keys]
            if specs:
                own = self.with_context(lang=lang)._pbds_own_values(
                    emp, get_contract(), specs)
                out.update({k: str(escape(v)) for k, v in own.items()})
        return out, blocked

    # ============================================================ own pay
    @api.model
    def _pbds_is_own_record(self, employee):
        """Is the letter's person the calling user's own employee record?
        `env.uid` stays the real user under sudo, so a sudo caller (the
        certificate flow) is still recognised and nobody else is."""
        if not employee:
            return False
        emp = employee.sudo()
        return bool(emp.user_id) and emp.user_id.id == self.env.uid

    @api.model
    def _pbds_running_contract(self, employee):
        """The person's running contract — the salary certificate's own
        rule (`pb.me.certificate._pb_running_contract`) when that module is
        installed, the same rule here otherwise."""
        if 'pb.me.certificate' in self.env:
            return self.env['pb.me.certificate']._pb_running_contract(employee)
        if 'hr.contract' not in self.env:
            return None
        today = fields.Date.context_today(self)
        contracts = employee.sudo().contract_ids.filtered(
            lambda c: c.state == 'open'
            and (not c.date_start or c.date_start <= today)
            and (not c.date_end or c.date_end >= today))
        return contracts.sorted(lambda c: c.date_start or today, reverse=True)[:1]

    @api.model
    def _pbds_own_pay(self, employee, company, lang):
        """The caller's OWN current monthly pay (F-b ruling 2), read the way
        the salary certificate reads it (`pb_me_letters` `_pb_values`: the
        running contract's wage under sudo). Refuses anybody else's record.
        → formatted text, '' when there is no running contract, None when the
        site's access rules still refuse it (Access Studio, ledger DS-3)."""
        if not self._pbds_is_own_record(employee):
            raise AccessError(self.env._("This is not your own record."))
        contract = self._pbds_running_contract(employee.sudo())
        if not contract:
            return ''
        try:
            contract = contract.sudo()
            wage = contract.wage
            currency = contract.currency_id if 'currency_id' in contract._fields \
                and contract.currency_id else (company or employee.company_id).currency_id
        except AccessError:
            return None
        return format_amount(self.with_context(lang=lang).env, wage or 0.0, currency,
                             lang_code=lang)

    # ============================================================ catalogue
    @api.model
    def _pbds_type_fields(self, letter_type, kind=None):
        """"This document" fields of a letter type: [(key, label, pay)].
        Other modules extend this hook to add theirs."""
        rows = list(TYPE_FIELDS.get(letter_type) or [])
        rows += KIND_FIELDS.get(kind or '', [])
        return rows

    @api.model
    def _pbds_catalogue(self, tmpl):
        """(groups, {key: field}) — every field this document can print."""
        _ = self.env._
        flat = {}
        groups = {g: [] for g, _l in FIELD_GROUPS}
        for key, label, group, pay in GENERIC_FIELDS:
            flat[key] = {'key': key, 'label': _(label), 'group': group,
                         'pay': bool(pay)}
        letter_type = tmpl.letter_type if tmpl else False
        kind = tmpl.pbds_kind if tmpl else False
        for key, label, pay in self._pbds_type_fields(letter_type, kind):
            flat[key] = {'key': key, 'label': _(label), 'group': 'document',
                         'pay': bool(pay), 'later': True}
        flat['extra']['later'] = True
        for spec in self._pbds_own_specs():
            flat.setdefault(spec['key'], {'key': spec['key'], 'label': spec['label'],
                                          'group': 'own', 'pay': False, 'own': True})
        # A field the document already uses that no list knows: one the
        # letter's caller hands over (kept, filled in when the letter is made)
        # or an own field that was removed (amber, rail R3).
        if tmpl:
            for key in self._pbds_used_keys(tmpl):
                if key in flat:
                    continue
                if key.startswith(OWN_PREFIX):
                    flat[key] = {'key': key, 'label': key[len(OWN_PREFIX):].replace('_', ' ').strip().capitalize() or key,
                                 'group': 'own', 'pay': False, 'missing': True}
                else:
                    flat[key] = {'key': key, 'label': key.replace('_', ' ').strip().capitalize(),
                                 'group': 'document', 'pay': False, 'later': True}
        for spec in flat.values():
            groups.setdefault(spec['group'], []).append(spec)
        out = [{'key': g, 'label': _(label), 'fields': groups.get(g, [])}
               for g, label in FIELD_GROUPS if groups.get(g)]
        return out, flat

    @api.model
    def _pbds_used_keys(self, tmpl):
        keys = []
        bodies = [tmpl.with_context(lang=MAIN_LANG).body_html or '']
        bodies += [v.body_html or '' for v in tmpl.sudo().pbds_version_ids]
        for body in bodies:
            for key in field_keys(str(body)):
                if key not in keys:
                    keys.append(key)
        return keys

    @api.model
    def _pbds_missing(self, tmpl, flat=None):
        if flat is None:
            _g, flat = self._pbds_catalogue(tmpl)
        return [k for k, spec in flat.items() if spec.get('missing')]

    @api.model
    def catalogue(self, template_id):
        tmpl = self._template(template_id, 'read')
        groups, _flat = self._pbds_catalogue(tmpl)
        return groups

    # ============================================================ conditions
    @api.model
    def _pbds_condition_meta(self):
        """[{key, label, type, options}] — what a "Show only when" rule can
        ask about. Options are `{value, label}` with string values."""
        _ = self.env._
        env = self.env
        out = []
        Emp = env['hr.employee']

        def records(model, domain=None, limit=300):
            if model not in env:
                return []
            try:
                recs = env[model].search(domain or [], limit=limit)
                return [{'value': str(r.id), 'label': r.display_name} for r in recs]
            except AccessError:
                return []

        # Country of work: the box's own choices, as countries.
        codes = []
        if 'payroll_country' in Emp._fields:
            codes = [str(k).upper() for k, _l in
                     Emp._fields['payroll_country']._description_selection(env) if k]
        countries = env['res.country'].sudo().search([('code', 'in', codes)]) if codes \
            else env.companies.mapped('country_id')
        out.append({'key': 'country_of_work', 'label': _('Country of work'), 'type': 'choice',
                    'options': sorted(({'value': str(c.id), 'label': c.name} for c in countries),
                                      key=lambda o: o['label'])})
        out.append({'key': 'company', 'label': _('Company'), 'type': 'choice',
                    'options': [{'value': str(c.id), 'label': c.name} for c in env.user.company_ids]})
        out.append({'key': 'department', 'label': _('Department'), 'type': 'choice',
                    'options': records('hr.department')})
        out.append({'key': 'job', 'label': _('Job position'), 'type': 'choice',
                    'options': records('hr.job')})
        if 'hr.contract.type' in env:
            out.append({'key': 'contract_type', 'label': _('Contract type'), 'type': 'choice',
                        'options': records('hr.contract.type')})
        if 'employee_type' in Emp._fields:
            out.append({'key': 'employee_type', 'label': _('Employment type'), 'type': 'choice',
                        'options': [{'value': k, 'label': l} for k, l in
                                    Emp._fields['employee_type']._description_selection(env)]})
        out.append({'key': 'work_location', 'label': _('Work location'), 'type': 'choice',
                    'options': records('hr.work.location')})
        if 'sex' in Emp._fields:
            out.append({'key': 'gender', 'label': _('Gender'), 'type': 'choice',
                        'options': [{'value': k, 'label': l} for k, l in
                                    Emp._fields['sex']._description_selection(env)]})
        if 'hr.contract' in env and 'pb_band_id' in env['hr.contract']._fields:
            comodel = env['hr.contract']._fields['pb_band_id'].comodel_name
            out.append({'key': 'pay_band', 'label': _('Pay band'), 'type': 'choice',
                        'options': records(comodel)})
        for spec in self._pbds_own_specs():
            kind = OWN_RULE_TYPES.get(spec['type'])
            if not kind:
                continue
            options = []
            if spec['type'] == 'selection':
                options = [{'value': str(o['value']), 'label': o['label']} for o in spec['options']]
            elif spec['type'] == 'many2one' and spec.get('comodel'):
                options = records(spec['comodel'], limit=200)
            out.append({'key': spec['key'], 'label': spec['label'], 'type': kind,
                        'options': options, 'own': True})
        return out

    @api.model
    def condition_fields(self):
        self._require()
        meta = self._pbds_condition_meta()
        ops = {kind: [{'value': op, 'label': self._pbds_op_label(kind, op)} for op in kind_ops]
               for kind, kind_ops in OPS.items()}
        return {'fields': meta, 'ops': ops}

    @api.model
    def _pbds_op_label(self, kind, op):
        dated = DATE_OP_LABELS.get(op) if kind == 'date' else None
        return self.env._(dated or OP_LABELS.get(op, OP_LABELS['is']))

    @api.model
    def _pbds_facts(self, employee):
        """`(facts, meta)` of a person for the rules. Read with the current
        env; anything unreadable is simply not known (the rule then says
        "is empty")."""
        meta = {}
        for spec in self._pbds_condition_meta_light():
            meta[spec['key']] = spec
        facts = {}
        if not employee:
            return facts, meta
        emp = employee

        def read(fn):
            try:
                return fn()
            except AccessError:
                return False

        facts['country_of_work'] = self._pbds_country_of_work(emp).get(emp.id) or False
        facts['company'] = emp.company_id.id or False
        facts['department'] = read(lambda: emp.department_id.id)
        facts['job'] = read(lambda: emp.job_id.id)
        facts['employee_type'] = read(lambda: emp.employee_type) if 'employee_type' in emp._fields else False
        facts['work_location'] = read(lambda: emp.work_location_id.id)
        facts['gender'] = read(lambda: emp.sex) if 'sex' in emp._fields else False
        contract = self._pbds_contract(emp)
        if contract is not None and contract:
            if 'contract_type_id' in contract._fields:
                facts['contract_type'] = read(lambda: contract.contract_type_id.id)
            if 'pb_band_id' in contract._fields:
                facts['pay_band'] = read(lambda: contract.pb_band_id.id)
        specs = self._pbds_own_specs()
        if specs:
            facts.update(self._pbds_own_raw(emp, contract, specs))
        return facts, meta

    @api.model
    def _pbds_condition_meta_light(self):
        """Keys and types only (no option lists) — what the renderer needs."""
        Emp = self.env['hr.employee']
        out = [{'key': k, 'type': 'choice'} for k in
               ('country_of_work', 'company', 'department', 'job', 'work_location')]
        if 'hr.contract.type' in self.env:
            out.append({'key': 'contract_type', 'type': 'choice'})
        if 'employee_type' in Emp._fields:
            out.append({'key': 'employee_type', 'type': 'choice'})
        if 'sex' in Emp._fields:
            out.append({'key': 'gender', 'type': 'choice'})
        if 'hr.contract' in self.env and 'pb_band_id' in self.env['hr.contract']._fields:
            out.append({'key': 'pay_band', 'type': 'choice'})
        for spec in self._pbds_own_specs():
            kind = OWN_RULE_TYPES.get(spec['type'])
            if kind:
                out.append({'key': spec['key'], 'type': kind})
        return out

    @api.model
    def _pbds_rule_sentence(self, rule, meta_full=None):
        """"Only when Country of work is Indonesia" — the pill on a block."""
        _ = self.env._
        meta_full = meta_full or {m['key']: m for m in self._pbds_condition_meta()}
        parts = []
        for line in (rule or {}).get('lines') or []:
            spec = meta_full.get(line.get('field'))
            if not spec:
                parts.append(_('a field that no longer exists'))
                continue
            op = line.get('op')
            kind = spec['type']
            op_label = self._pbds_op_label(kind, op)
            labels = {o['value']: o['label'] for o in spec.get('options') or []}
            val = line.get('value')
            if op in ('empty', 'filled'):
                parts.append('%s %s' % (spec['label'], op_label))
                continue
            if kind == 'bool':
                parts.append('%s %s %s' % (spec['label'], op_label, _('Yes') if val else _('No')))
                continue
            vals = val if isinstance(val, list) else [val]
            shown = ', '.join(labels.get(str(v), str(v)) for v in vals if v not in (None, ''))
            parts.append('%s %s %s' % (spec['label'], op_label, shown))
        joiner = _(' or ') if (rule or {}).get('match') == 'any' else _(' and ')
        return _('Only when %s', joiner.join(parts)) if parts else ''

    # ============================================================ page (C3)
    @api.model
    def page_styles(self):
        """The page settings a document can use (contract C3)."""
        _ = self.env._
        return [
            {'key': 'letterhead', 'label': _('Letterhead'), 'type': 'bool',
             'default': DEFAULT_PAGE['letterhead']},
            {'key': 'margins', 'label': _('Margins'), 'type': 'choice',
             'default': DEFAULT_PAGE['margins'],
             'options': [{'value': k, 'label': _(l), 'mm': {'top': m[0], 'bottom': m[1], 'left': m[2], 'right': m[3]}}
                         for k, l, m in MARGINS]},
            {'key': 'font', 'label': _('Font'), 'type': 'choice',
             'default': DEFAULT_PAGE['font'],
             'options': [{'value': k, 'label': _(l), 'css': css} for k, l, css in FONTS]},
            {'key': 'size', 'label': _('Text size'), 'type': 'choice',
             'default': DEFAULT_PAGE['size'],
             'options': [{'value': s, 'label': str(s)} for s in SIZES]},
            {'key': 'sign', 'label': _('Signature block'), 'type': 'choice',
             'default': DEFAULT_PAGE['sign'],
             'options': [{'value': k, 'label': _(l)} for k, l in SIGNS]},
            {'key': 'sign_name', 'label': _('Signed by'), 'type': 'text',
             'default': ''},
            {'key': 'sign_title', 'label': _('Their title'), 'type': 'text',
             'default': ''},
        ]

    @api.model
    def _pbds_clean_page(self, page):
        """A page dict with every key, every value allowed (never trusts the
        browser)."""
        page = page if isinstance(page, dict) else {}
        out = dict(DEFAULT_PAGE)
        if 'letterhead' in page:
            out['letterhead'] = bool(page['letterhead'])
        if page.get('margins') in MARGIN_KEYS:
            out['margins'] = page['margins']
        if page.get('font') in FONT_KEYS:
            out['font'] = page['font']
        try:
            size = int(page.get('size') or out['size'])
            out['size'] = size if size in SIZES else out['size']
        except (TypeError, ValueError):
            pass
        if page.get('sign') in SIGN_KEYS:
            out['sign'] = page['sign']
        for key in ('sign_name', 'sign_title'):
            out[key] = str(page.get(key) or '')[:120].strip()
        return out

    @api.model
    def page_values(self, page, lang=None):
        """What `pb_doc_studio.page_frame` needs to draw `page` (C3)."""
        page = self._pbds_clean_page(page)
        lang = lang or self.env.lang or MAIN_LANG
        margins = dict((k, m) for k, _l, m in MARGINS)[page['margins']]
        font_css = dict((k, css) for k, _l, css in FONTS)[page['font']]
        local = self.with_context(lang=lang).env
        style = 'font-family: %s; font-size: %spx; line-height: 1.6;' % (
            font_css, page['size'])
        screen_pad = '%smm %smm %smm %smm' % (
            max(margins[0] - 18, 14), margins[3], max(margins[1] - 10, 12), margins[2])
        return dict(page, **{
            'font_css': font_css,
            'style': style,
            'screen_padding': screen_pad,
            'sign_title': page['sign_title'] or local._('Authorised signatory'),
            'css': Markup(PAGE_CSS),
        })

    @api.model
    def _pbds_report(self, page):
        page = self._pbds_clean_page(page)
        return self.env.ref('pb_doc_studio.action_report_doc_%s' % page['margins'],
                            raise_if_not_found=False)

    @api.model
    def _pbds_sign_uri(self, tmpl):
        if not tmpl or not tmpl.sudo().pbds_sign_image:
            return False
        from odoo.tools.image import image_data_uri
        try:
            return image_data_uri(tmpl.sudo().pbds_sign_image)
        except Exception:                              # noqa: BLE001
            return False

    @api.model
    def _pbds_inline_images(self, html, tmpl):
        """The PDF engine fetches nothing: pictures added in the studio are
        put into the page itself. Only this module's pictures."""
        if not html or '/web/image/ir.attachment/' not in html:
            return html
        Att = self.env['ir.attachment'].sudo()

        def swap(mo):
            att = Att.browse(int(mo.group(3))).exists()
            if not att or att.description != IMAGE_MARKER or att.res_model != 'pb.letter.template':
                return mo.group(0)
            data = att.datas
            if not data:
                return mo.group(0)
            data = data.decode() if isinstance(data, bytes) else data
            return '%sdata:%s;base64,%s%s' % (mo.group(1), att.mimetype or 'image/png', data, mo.group(4))

        return IMG_SRC_RE.sub(swap, html)

    # ============================================================ gallery
    @api.model
    def _pbds_templates(self):
        Template = self.env['pb.letter.template'].with_context(active_test=False)
        return Template.search([('letter_type', 'not in', list(NOT_HERE_YET))])

    @api.model
    def _pbds_card(self, tmpl, flat=None):
        _ = self.env._
        lang_names = {l['code']: l['name'] for l in self._pbds_lang_list()}
        root = tmpl.pbds_replaces_id
        main = tmpl.with_context(lang=MAIN_LANG)
        text = ''
        try:
            body = str(main.body_html or '')
            if body:
                text = lxml_html.fromstring('<div>%s</div>' % body).text_content()
        except (etree.ParserError, ValueError):
            text = ''
        text = BRACED_RE.sub('…', re.sub(r'\s+', ' ', text)).strip()
        versions = tmpl.sudo().pbds_version_ids
        main_lang = tmpl._pbds_main_lang()
        langs = [main_lang] + [v.lang for v in versions if v.lang != main_lang]
        missing = self._pbds_missing(tmpl, flat)
        type_label = dict(tmpl._fields['letter_type']._description_selection(self.env)).get(
            tmpl.letter_type, '')
        builtin = not tmpl.pbds_kind_set and not root
        return {
            'id': tmpl.id,
            'name': tmpl.name or '',
            'subject': main.subject or '',
            'kind': tmpl.pbds_kind,
            'type_label': type_label,
            'edited': bool(tmpl.pbds_edited),
            'studio': tmpl._pbds_is_studio(),
            'builtin': builtin,
            'can_reset': bool(tmpl.pbds_edited and tmpl.pbds_original_json),
            'active': bool(tmpl.active),
            'company': tmpl.company_id.name or False,
            'company_id': tmpl.company_id.id or False,
            'countries': tmpl.pbds_country_ids.mapped('name'),
            'langs': [{'code': c, 'name': lang_names.get(c, c)} for c in langs],
            'changed_by': tmpl.pbds_changed_by.name or False,
            'changed_on': fields.Datetime.to_string(tmpl.pbds_changed_on) if tmpl.pbds_changed_on else False,
            'missing': len(missing),
            'variant_of': {'id': root.id, 'name': root.name} if root else False,
            'variants': len(tmpl.pbds_variant_ids),
            'snippet': text[:220],
            'rules': len(tmpl.pbds_rules or {}),
            'page': bool(tmpl.pbds_page),
        }

    @api.model
    def board(self):
        """The gallery: every document grouped by kind."""
        self._require()
        _ = self.env._
        templates = self._pbds_templates()
        cards = []
        for tmpl in templates:
            try:
                cards.append(self._pbds_card(tmpl))
            except AccessError:
                continue
        # Copies sit right after the document they copy.
        order = {c['id']: i for i, c in enumerate(cards)}
        cards.sort(key=lambda c: (KIND_KEYS.index(c['kind']) if c['kind'] in KIND_KEYS else 99,
                                  order.get((c['variant_of'] or {}).get('id', c['id']), 0),
                                  bool(c['variant_of']), c['id']))
        return {
            'cards': cards,
            'kinds': [{'key': k, 'label': _(l)} for k, l in KINDS],
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.user.company_ids],
            'countries': self._pbds_condition_meta_countries(),
            'langs': self._pbds_lang_list(),
            'coach': not any(c['edited'] for c in cards),
            'multi_company': len(self.env.user.company_ids) > 1,
        }

    @api.model
    def _pbds_condition_meta_countries(self):
        Emp = self.env['hr.employee']
        codes = []
        if 'payroll_country' in Emp._fields:
            codes = [str(k).upper() for k, _l in
                     Emp._fields['payroll_country']._description_selection(self.env) if k]
        countries = self.env['res.country'].sudo().search([('code', 'in', codes)]) if codes \
            else self.env.companies.mapped('country_id')
        return sorted(({'id': c.id, 'name': c.name, 'code': c.code} for c in countries),
                      key=lambda r: r['name'])

    # ============================================================ designer
    @api.model
    def _pbds_company_card(self, company):
        company = (company or self.env.company).sudo()
        partner = company.partner_id
        lines = [ln.strip() for ln in (partner._display_address(without_company=True) or '').splitlines()
                 if ln.strip()]
        contact = ' · '.join(x for x in (company.phone, company.email, company.website) if x)
        return {
            'id': company.id,
            'name': company.name or '',
            'address': ', '.join(lines),
            'contact': contact,
            'logo': '/web/image/res.company/%s/logo' % company.id if company.logo else False,
        }

    @api.model
    def _pbds_sample_person(self, tmpl):
        Emp = self.env['hr.employee']
        domain = [('company_id', 'in', self.env.companies.ids)]
        if tmpl.company_id:
            domain = [('company_id', '=', tmpl.company_id.id)]
        try:
            # Somebody with a contract and a job shows the most real values.
            emp = Emp.browse()
            if 'contract_id' in Emp._fields:
                emp = Emp.search(domain + [('job_id', '!=', False), ('contract_id', '!=', False)], limit=1)
            emp = emp or Emp.search(domain + [('job_id', '!=', False)], limit=1) \
                or Emp.search(domain, limit=1) or Emp.search([], limit=1)
        except AccessError:
            return False
        return self._pbds_person(emp) if emp else False

    @api.model
    def _pbds_person(self, emp):
        lang_names = {l['code']: l['name'] for l in self._pbds_lang_list()}
        try:
            job = emp.job_title or emp.job_id.name or ''
        except AccessError:
            job = ''
        lang = self.env['pb.hr.letter']._pbds_default_lang(None, emp)
        return {'id': emp.id, 'name': emp.name or '', 'job': job,
                'company': emp.company_id.name or '', 'lang': lang,
                'lang_name': lang_names.get(lang, lang),
                'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id}

    @api.model
    def open(self, template_id):
        tmpl = self._template(template_id, 'read')
        main = tmpl.with_context(lang=MAIN_LANG)
        groups, flat = self._pbds_catalogue(tmpl)
        langs = self._pbds_lang_list()
        versions = {v.lang: {'subject': v.subject or '', 'body': str(v.body_html or '')}
                    for v in tmpl.sudo().pbds_version_ids}
        # A wording shipped in another language (term translation of the
        # template, e.g. the certificates in Vietnamese) can start a version.
        translated = {}
        main_body = str(main.body_html or '')
        main_lang = tmpl._pbds_main_lang()
        for lang in langs:
            code = lang['code']
            if code in (MAIN_LANG, main_lang) or code in versions:
                continue
            local = str(tmpl.with_context(lang=code).body_html or '')
            if local and local != main_body:
                translated[code] = {'subject': tmpl.with_context(lang=code).subject or '',
                                    'body': local}
        meta_full = {m['key']: m for m in self._pbds_condition_meta()}
        rules = tmpl.pbds_rules or {}
        can_write = tmpl.has_access('write')
        return {
            'id': tmpl.id,
            'name': tmpl.name or '',
            'subject': main.subject or '',
            'body': main_body,
            'versions': versions,
            'translated': translated,
            'rules': rules,
            'sentences': {rid: self._pbds_rule_sentence(r, meta_full) for rid, r in rules.items()},
            'page': self._pbds_clean_page(tmpl.pbds_page),
            'page_set': bool(tmpl.pbds_page),
            'sign_image': bool(tmpl.pbds_sign_image),
            'sign_image_url': ('/web/image/pb.letter.template/%s/pbds_sign_image' % tmpl.id)
            if tmpl.pbds_sign_image else False,
            'kind': tmpl.pbds_kind,
            'type_label': dict(tmpl._fields['letter_type']._description_selection(self.env)).get(
                tmpl.letter_type, ''),
            'edited': bool(tmpl.pbds_edited),
            'can_reset': bool(tmpl.pbds_edited and tmpl.pbds_original_json),
            'can_write': can_write,
            'active': bool(tmpl.active),
            'company': self._pbds_company_card(tmpl.company_id),
            'for_company': tmpl.company_id.name or False,
            'for_countries': tmpl.pbds_country_ids.mapped('name'),
            'variant_of': {'id': tmpl.pbds_replaces_id.id, 'name': tmpl.pbds_replaces_id.name}
            if tmpl.pbds_replaces_id else False,
            'catalogue': groups,
            'missing': [k for k, s in flat.items() if s.get('missing')],
            'conditions': self.condition_fields(),
            'page_styles': self.page_styles(),
            'langs': langs,
            'main_lang': main_lang,
            'person': self._pbds_sample_person(tmpl),
            'revision': fields.Datetime.to_string(tmpl.write_date) if tmpl.write_date else '',
            'changed_by': tmpl.pbds_changed_by.name or False,
            'changed_on': fields.Datetime.to_string(tmpl.pbds_changed_on) if tmpl.pbds_changed_on else False,
        }

    # ------------------------------------------------------------ cleaning
    @api.model
    def _pbds_clean_rules(self, rules, bodies):
        """Keep the rules the bodies use, each checked against the table."""
        rules = rules if isinstance(rules, dict) else {}
        used = set()
        for body in bodies:
            for rid in re.findall(r'pbds-r-([a-z][a-z0-9]{0,15})', body or ''):
                used.add(rid)
        meta = {m['key']: m for m in self._pbds_condition_meta_light()}
        out = {}
        for rid, rule in rules.items():
            if rid not in used or not RULE_ID_RE.match(str(rid)) or not isinstance(rule, dict):
                continue
            lines = []
            for line in (rule.get('lines') or [])[:12]:
                if not isinstance(line, dict):
                    continue
                key, op = line.get('field'), line.get('op')
                spec = meta.get(key)
                if not spec or op not in OPS.get(spec['type'], ()):
                    raise UserError(self.env._(
                        "A \"Show only when\" rule is not complete. Open it, pick a "
                        "field and a condition, then save again."))
                value = line.get('value')
                if op in ('empty', 'filled'):
                    value = None
                elif op == 'in':
                    value = [str(v)[:200] for v in (value if isinstance(value, list) else [value])
                             if v not in (None, '')][:100]
                    if not value:
                        raise UserError(self.env._(
                            "A \"Show only when\" rule needs at least one value to compare with."))
                elif spec['type'] == 'bool':
                    value = bool(value)
                elif value in (None, ''):
                    raise UserError(self.env._(
                        "A \"Show only when\" rule needs a value to compare with."))
                else:
                    value = str(value)[:200] if spec['type'] in ('choice', 'text', 'date') else value
                    if spec['type'] == 'number':
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            raise UserError(self.env._("Use a number in this rule."))
                lines.append({'field': key, 'op': op, 'value': value})
            if lines:
                out[rid] = {'match': 'any' if rule.get('match') == 'any' else 'all',
                            'lines': lines}
        return out

    @api.model
    def _pbds_clean_body(self, tmpl, body):
        body = str(body or '')
        if len(body.encode('utf-8')) > MAX_BODY:
            raise UserError(self.env._(
                "This wording is too long to save (more than 600 KB). Split it, "
                "or use smaller pictures."))
        # The fields sanitize on write (`body_html` of the template and of a
        # version are both `sanitize=True`): no second pass here (rail R7).
        return self._pbds_lift_inline_images(tmpl, body)

    @api.model
    def _pbds_lift_inline_images(self, tmpl, body):
        """A picture pasted straight into the page arrives as data: store it
        as a file and point at it (rail R7: never inline in the stored body)."""
        if 'data:image' not in body:
            return body
        pattern = re.compile(r'src="data:(image/[a-z+.-]+);base64,([A-Za-z0-9+/=\s]+)"', re.I)

        def lift(mo):
            mime = mo.group(1).lower()
            if mime not in IMAGE_MIMES:
                return 'src=""'
            res = self._pbds_store_image(tmpl, 'Picture', mime, re.sub(r'\s+', '', mo.group(2)))
            return 'src="%s"' % res['url'] if res.get('ok') else 'src=""'

        return pattern.sub(lift, body)

    @api.model
    def _pbds_store_image(self, tmpl, name, mime, data):
        _ = self.env._
        if mime not in IMAGE_MIMES:
            return {'ok': False, 'msg': _("Use a PNG, JPEG, WebP or GIF picture.")}
        try:
            raw = base64.b64decode(str(data or ''), validate=True)
        except (binascii.Error, ValueError, TypeError):
            return {'ok': False, 'msg': _("The picture could not be read.")}
        if not raw:
            return {'ok': False, 'msg': _("The picture is empty.")}
        if len(raw) > IMAGE_MAX:
            return {'ok': False, 'msg': _("The picture must be 4 MB or smaller.")}
        signatures = {
            'image/png': raw[:8] == b'\x89PNG\r\n\x1a\n',
            'image/jpeg': raw[:3] == b'\xff\xd8\xff',
            'image/gif': raw[:6] in (b'GIF87a', b'GIF89a'),
            'image/webp': raw[:4] == b'RIFF' and raw[8:12] == b'WEBP',
        }
        if not signatures.get(mime):
            return {'ok': False, 'msg': _("The file is not the kind of picture it says it is.")}
        clean = re.sub(r'[\x00-\x1f\\/]+', ' ', str(name or 'Picture')).strip()[:128] or 'Picture'
        att = self.env['ir.attachment'].sudo().create({
            'name': clean,
            'datas': base64.b64encode(raw),
            'mimetype': mime,
            'res_model': 'pb.letter.template',
            'res_id': tmpl.id,
            'description': IMAGE_MARKER,
        })
        att.generate_access_token()
        return {'ok': True, 'id': att.id, 'name': clean,
                'url': '/web/image/ir.attachment/%s/datas?access_token=%s' % (att.id, att.access_token)}

    @api.model
    def upload_image(self, template_id, upload):
        tmpl = self._template(template_id)
        upload = upload if isinstance(upload, dict) else {}
        return self._pbds_store_image(tmpl, upload.get('name'), str(upload.get('mime') or '').lower(),
                                      upload.get('data'))

    # ------------------------------------------------------------ save
    @api.model
    def _pbds_snapshot_original(self, tmpl):
        """Write ONCE, before the first studio change, what the template is
        now — the raw stored value of every translated column, so "Put back
        the built-in wording" restores it byte for byte (rail R6)."""
        if tmpl.pbds_original_json:
            return
        # Raw SQL on a table the ORM may still owe a write to: flush first.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT name, subject, body_html FROM pb_letter_template WHERE id = %s',
            (tmpl.id,))
        name, subject, body = self.env.cr.fetchone()
        tmpl.sudo().write({
            'pbds_original_json': {'name': name, 'subject': subject, 'body_html': body},
            'pbds_original_html': tmpl.with_context(lang=MAIN_LANG).body_html or '',
        })

    @api.model
    def save(self, template_id, payload):
        """Save the designer: wording, language versions, rules, page,
        signature picture. → the fresh designer data."""
        tmpl = self._template(template_id)
        _ = self.env._
        payload = payload if isinstance(payload, dict) else {}
        main = tmpl.with_context(lang=MAIN_LANG)
        body = self._pbds_clean_body(tmpl, payload.get('body', main.body_html or ''))
        versions_in = payload.get('versions') if isinstance(payload.get('versions'), dict) else {}
        active = self._pbds_active_langs()
        # F-b ruling 3: the main wording says which language it is written in.
        main_lang = payload.get('main_lang') or tmpl._pbds_main_lang()
        if main_lang not in active:
            main_lang = tmpl._pbds_main_lang()
        clean_versions = {}
        for lang, ver in versions_in.items():
            if lang == main_lang or lang not in active:
                continue
            if ver is None:
                clean_versions[lang] = None
                continue
            ver = ver if isinstance(ver, dict) else {}
            clean_versions[lang] = {
                'subject': str(ver.get('subject') or '')[:300],
                'body': self._pbds_clean_body(tmpl, ver.get('body') or ''),
            }
        # A separate wording in the main wording's own language is never read.
        if any(v.lang == main_lang for v in tmpl.sudo().pbds_version_ids):
            clean_versions[main_lang] = None
        all_bodies = [body] + [v['body'] for v in clean_versions.values() if v] + [
            str(v.body_html or '') for v in tmpl.sudo().pbds_version_ids
            if v.lang not in clean_versions]
        rules = self._pbds_clean_rules(payload.get('rules', tmpl.pbds_rules or {}), all_bodies)
        page = self._pbds_clean_page(payload.get('page', tmpl.pbds_page or DEFAULT_PAGE))
        # The name box shows the name in the screen's language (as the
        # gallery card does); an unchanged box writes nothing.
        shown = str(tmpl.name or '').strip()[:200]
        name = str(payload.get('name') or shown or main.name or '').strip()[:200]
        if not name:
            raise UserError(_("Give the document a name."))
        if is_html_empty(body):
            raise UserError(_("The main wording is empty. Write the letter, then save."))
        self._pbds_snapshot_original(tmpl)
        # A new name goes into the screen's language when the document has a
        # name of its own in it (a shipped translation), else into the main
        # name, as before.
        own_name = (self.env.lang or MAIN_LANG) != MAIN_LANG and \
            (tmpl.name or '') != (main.name or '')
        vals = {
            'subject': str(payload.get('subject', main.subject) or '')[:300],
            'body_html': body,
            'pbds_rules': rules or False,
            'pbds_page': page,
            'pbds_main_lang': main_lang if main_lang != MAIN_LANG else False,
            'pbds_edited': True,
            'pbds_changed_by': self.env.uid,
            'pbds_changed_on': fields.Datetime.now(),
            'pbds_undo': False,
        }
        sign = payload.get('sign_image', None)
        if sign is False:
            vals['pbds_sign_image'] = False
        elif isinstance(sign, dict) and sign.get('data'):
            mime = str(sign.get('mime') or '').lower()
            stored = self._pbds_check_picture(mime, sign['data'])
            vals['pbds_sign_image'] = stored
        main.write(vals)
        if name != shown:
            (tmpl if own_name else main).write({'name': name})
        Version = self.env['pb.doc.version']
        existing = {v.lang: v for v in tmpl.pbds_version_ids}
        for lang, ver in clean_versions.items():
            if ver is None:
                if lang in existing:
                    existing[lang].unlink()
                continue
            if lang in existing:
                existing[lang].write({'subject': ver['subject'], 'body_html': ver['body']})
            else:
                Version.create({'template_id': tmpl.id, 'lang': lang,
                                'subject': ver['subject'], 'body_html': ver['body']})
        return self._pbds_saved(tmpl)

    @api.model
    def _pbds_saved(self, tmpl):
        """What the designer needs back after a save (not the whole `open`:
        a save of a long letter stays well under a second, rail R7)."""
        _groups, flat = self._pbds_catalogue(tmpl)
        groups = _groups
        return {
            'id': tmpl.id,
            'name': tmpl.name or '',
            'revision': fields.Datetime.to_string(tmpl.write_date) if tmpl.write_date else '',
            'edited': bool(tmpl.pbds_edited),
            'can_reset': bool(tmpl.pbds_edited and tmpl.pbds_original_json),
            'catalogue': groups,
            'missing': [k for k, s in flat.items() if s.get('missing')],
            'rules': tmpl.pbds_rules or {},
            'page': self._pbds_clean_page(tmpl.pbds_page),
            'page_set': bool(tmpl.pbds_page),
            'main_lang': tmpl._pbds_main_lang(),
            'versions': {v.lang: {'subject': v.subject or '', 'body': str(v.body_html or '')}
                         for v in tmpl.sudo().pbds_version_ids},
            'sign_image': bool(tmpl.pbds_sign_image),
            'sign_image_url': ('/web/image/pb.letter.template/%s/pbds_sign_image' % tmpl.id)
            if tmpl.pbds_sign_image else False,
            'changed_by': tmpl.pbds_changed_by.name or False,
            'changed_on': fields.Datetime.to_string(tmpl.pbds_changed_on) if tmpl.pbds_changed_on else False,
        }

    @api.model
    def _pbds_check_picture(self, mime, data):
        res_ok = self._pbds_picture_ok(mime, data)
        if not res_ok[0]:
            raise UserError(res_ok[1])
        return data

    @api.model
    def _pbds_picture_ok(self, mime, data):
        _ = self.env._
        if mime not in ('image/png', 'image/jpeg'):
            return False, _("Use a PNG or JPEG picture for the signature.")
        try:
            raw = base64.b64decode(str(data), validate=True)
        except (binascii.Error, ValueError, TypeError):
            return False, _("The picture could not be read.")
        if not raw or len(raw) > 2 * 1024 * 1024:
            return False, _("The signature picture must be 2 MB or smaller.")
        if mime == 'image/png' and raw[:8] != b'\x89PNG\r\n\x1a\n':
            return False, _("The file is not the kind of picture it says it is.")
        if mime == 'image/jpeg' and raw[:3] != b'\xff\xd8\xff':
            return False, _("The file is not the kind of picture it says it is.")
        return True, ''

    # ------------------------------------------------------------ copies
    @api.model
    def copy_for(self, template_id, company_id=False, country_ids=None):
        """Make a copy of a document for one company and/or countries of
        work. From then on letters for those people use the copy, whatever
        made them (F7)."""
        tmpl = self._template(template_id, 'read')
        _ = self.env._
        root = tmpl.pbds_replaces_id or tmpl
        company = self.env['res.company'].browse(int(company_id or 0)).exists() \
            if company_id else self.env['res.company']
        if company and company not in self.env.user.company_ids:
            raise AccessError(_("You do not work in that company."))
        countries = self.env['res.country'].browse(
            [int(c) for c in (country_ids or []) if c]).exists()
        if not company and not countries:
            raise UserError(_("Choose a company, one or more countries of work, or both."))
        Template = self.env['pb.letter.template'].with_context(active_test=False)
        twin = Template.search([('pbds_replaces_id', '=', root.id),
                                ('company_id', '=', company.id or False)])
        twin = twin.filtered(lambda t: set(t.pbds_country_ids.ids) == set(countries.ids))[:1]
        if twin:
            return {'id': twin.id, 'existing': True}
        Template.browse().check_access('create')
        src = tmpl.with_context(lang=MAIN_LANG)
        place = ', '.join(([company.name] if company else []) + countries.mapped('name'))
        new = Template.with_context(lang=MAIN_LANG).create({
            'name': '%s — %s' % (root.with_context(lang=MAIN_LANG).name, place),
            'sequence': root.sequence,
            'letter_type': root.letter_type,
            'subject': src.subject,
            'body_html': src.body_html,
            'vault_category_id': root.vault_category_id.id,
            'company_id': company.id or False,
            'pbds_replaces_id': root.id,
            'pbds_country_ids': [(6, 0, countries.ids)],
            'pbds_rules': tmpl.pbds_rules or False,
            'pbds_page': tmpl.pbds_page or dict(DEFAULT_PAGE),
            'pbds_main_lang': tmpl.pbds_main_lang or False,
            'pbds_sign_image': tmpl.sudo().pbds_sign_image or False,
            'pbds_kind_set': root.pbds_kind if root.pbds_kind != 'other' else root.pbds_kind_set,
            'pbds_edited': True,
            'pbds_changed_by': self.env.uid,
            'pbds_changed_on': fields.Datetime.now(),
        })
        # The copy's "built-in wording" is the wording it started from.
        self._pbds_snapshot_original(new)
        for ver in tmpl.sudo().pbds_version_ids:
            self.env['pb.doc.version'].create({'template_id': new.id, 'lang': ver.lang,
                                               'subject': ver.subject, 'body_html': ver.body_html})
        return {'id': new.id, 'existing': False}

    # ------------------------------------------------------------ reset
    @api.model
    def reset(self, template_id):
        """Put back the built-in wording: the wording, every language, rules,
        page design and signature go; one step of undo is kept (R6)."""
        tmpl = self._template(template_id)
        if not tmpl.pbds_original_json:
            raise UserError(self.env._("This document still has its built-in wording."))
        # Raw SQL on a table the ORM may still owe a write to: flush first.
        self.env.flush_all()
        self.env.cr.execute(
            'SELECT name, subject, body_html FROM pb_letter_template WHERE id = %s', (tmpl.id,))
        name, subject, body = self.env.cr.fetchone()
        sign = tmpl.sudo().pbds_sign_image
        undo = {
            'at': fields.Datetime.to_string(fields.Datetime.now()),
            'raw': {'name': name, 'subject': subject, 'body_html': body},
            'versions': [{'lang': v.lang, 'subject': v.subject, 'body_html': str(v.body_html or '')}
                         for v in tmpl.sudo().pbds_version_ids],
            'rules': tmpl.pbds_rules or False,
            'page': tmpl.pbds_page or False,
            'main_lang': tmpl.pbds_main_lang or False,
            'sign_image': sign.decode() if isinstance(sign, bytes) else (sign or False),
            'changed_by': tmpl.pbds_changed_by.id or False,
            'changed_on': fields.Datetime.to_string(tmpl.pbds_changed_on) if tmpl.pbds_changed_on else False,
        }
        self._pbds_write_raw(tmpl, tmpl.pbds_original_json)
        tmpl.sudo().pbds_version_ids.unlink()
        tmpl.sudo().write({
            'pbds_rules': False, 'pbds_page': False, 'pbds_sign_image': False,
            'pbds_main_lang': False, 'pbds_edited': False, 'pbds_undo': undo,
            'pbds_changed_by': self.env.uid, 'pbds_changed_on': fields.Datetime.now(),
        })
        return {'ok': True}

    @api.model
    def undo_reset(self, template_id):
        tmpl = self._template(template_id)
        undo = tmpl.pbds_undo
        if not undo:
            raise UserError(self.env._("There is nothing to undo."))
        self._pbds_write_raw(tmpl, undo['raw'])
        for ver in undo.get('versions') or []:
            self.env['pb.doc.version'].create({'template_id': tmpl.id, 'lang': ver['lang'],
                                               'subject': ver['subject'],
                                               'body_html': ver['body_html']})
        tmpl.sudo().write({
            'pbds_rules': undo.get('rules') or False,
            'pbds_page': undo.get('page') or False,
            'pbds_main_lang': undo.get('main_lang') or False,
            'pbds_sign_image': undo.get('sign_image') or False,
            'pbds_edited': True, 'pbds_undo': False,
            'pbds_changed_by': undo.get('changed_by') or self.env.uid,
            'pbds_changed_on': undo.get('changed_on') or fields.Datetime.now(),
        })
        return {'ok': True}

    @api.model
    def _pbds_write_raw(self, tmpl, raw):
        """Write the stored jsonb of the translated columns back exactly
        (it came from this database, never from the browser)."""
        def dump(value):
            return json.dumps(value) if value is not None else None
        # Raw SQL on a table the ORM may still owe a write to: flush first.
        self.env.flush_all()
        self.env.cr.execute(
            'UPDATE pb_letter_template SET name = %s::jsonb, subject = %s::jsonb, '
            'body_html = %s::jsonb, write_uid = %s, write_date = now() at time zone \'UTC\' '
            'WHERE id = %s',
            (dump(raw.get('name')), dump(raw.get('subject')), dump(raw.get('body_html')),
             self.env.uid, tmpl.id))
        tmpl.invalidate_recordset(['name', 'subject', 'body_html', 'write_uid', 'write_date'])

    # ------------------------------------------------------------ others
    @api.model
    def set_active(self, template_id, active):
        tmpl = self._template(template_id)
        tmpl.write({'active': bool(active)})
        return {'ok': True, 'active': bool(tmpl.active)}

    @api.model
    def create_blank(self, kind, name=None):
        self._require()
        _ = self.env._
        kind = kind if kind in KIND_KEYS else 'other'
        name = str(name or '').strip()[:200] or _('New letter')
        self.env['pb.letter.template'].browse().check_access('create')
        body = '<p>%s</p><p><br></p><p>%s</p>' % (
            _('Dear ${employee_name},'), _('Kind regards,'))
        tmpl = self.env['pb.letter.template'].with_context(lang=MAIN_LANG).create({
            'name': name,
            'letter_type': 'custom',
            'subject': name,
            'body_html': body,
            'company_id': False,
            'pbds_kind_set': kind,
            'pbds_page': dict(DEFAULT_PAGE),
            'pbds_edited': True,
            'pbds_changed_by': self.env.uid,
            'pbds_changed_on': fields.Datetime.now(),
        })
        self._pbds_snapshot_original(tmpl)
        return {'id': tmpl.id}

    @api.model
    def people(self, term=''):
        """People the caller may see (their own rights, no sudo)."""
        self._require()
        term = str(term or '').strip()[:80]
        domain = [('company_id', 'in', self.env.companies.ids)]
        if term:
            domain += ['|', ('name', 'ilike', term), ('job_title', 'ilike', term)]
        try:
            emps = self.env['hr.employee'].search(domain, limit=12, order='name')
        except AccessError:
            return []
        return [self._pbds_person(e) for e in emps]

    # ------------------------------------------------------------ preview
    @api.model
    def _pbds_draft_parts(self, tmpl, draft, lang):
        """(body, heading, rules, page, lang it reads in) of the UNSAVED draft
        for a reader of `lang` — the same order as a real letter
        (`pb.hr.letter._pbds_source`)."""
        draft = draft if isinstance(draft, dict) else {}
        versions = draft.get('versions') if isinstance(draft.get('versions'), dict) else {}
        main_lang = draft.get('main_lang') if draft.get('main_lang') in self._pbds_active_langs() \
            else tmpl._pbds_main_lang()
        saved_main = str(tmpl.with_context(lang=MAIN_LANG).body_html or '')
        draft_main = draft.get('body') if draft.get('body') is not None else saved_main
        main_heading = draft.get('subject') if draft.get('subject') is not None else \
            tmpl.with_context(lang=MAIN_LANG).subject or ''
        ver = versions.get(lang) if lang != main_lang else None
        if lang != main_lang and lang not in versions:
            saved = tmpl.sudo().pbds_version_ids.filtered(lambda v: v.lang == lang)[:1]
            if saved:
                ver = {'body': str(saved.body_html or ''), 'subject': saved.subject or ''}
        read_lang = lang
        if lang == main_lang:
            body, heading = draft_main, main_heading
        elif isinstance(ver, dict) and not is_html_empty(ver.get('body') or ''):
            body, heading = ver.get('body') or '', ver.get('subject') or ''
        elif main_lang != MAIN_LANG:
            body, heading, read_lang = draft_main, main_heading, main_lang
        elif draft_main == saved_main:
            # No wording of its own: the letter reads the template in that
            # language — a translation shipped with the product, else the
            # main wording. Exactly what a real letter does (`_pbds_source`).
            local = tmpl.with_context(lang=lang)
            body, heading = str(local.body_html or ''), local.subject or ''
            if draft.get('subject') is not None and \
                    local.subject == tmpl.with_context(lang=MAIN_LANG).subject:
                heading = draft.get('subject')
        else:
            body, heading = draft_main, main_heading
        body = str(body or '')
        if len(body.encode('utf-8')) > MAX_BODY:
            raise UserError(self.env._("This wording is too long to preview."))
        rules = draft.get('rules') if isinstance(draft.get('rules'), dict) else (tmpl.pbds_rules or {})
        page = self._pbds_clean_page(draft.get('page') if isinstance(draft.get('page'), dict)
                                     else tmpl.pbds_page)
        return html_sanitize(body), heading, rules, page, read_lang

    @api.model
    def _pbds_draft_sign(self, tmpl, draft):
        """The signature picture of the draft: a new one (checked), none, or
        the saved one."""
        sign = (draft or {}).get('sign_image') if isinstance(draft, dict) else None
        if sign is False:
            return False
        if isinstance(sign, dict) and sign.get('data'):
            mime = str(sign.get('mime') or '').lower()
            ok, _msg = self._pbds_picture_ok(mime, sign['data'])
            return 'data:%s;base64,%s' % (mime, sign['data']) if ok else False
        return self._pbds_sign_uri(tmpl)

    @api.model
    def _pbds_preview_letter(self, tmpl, employee):
        return self.env['pb.hr.letter'].new({
            'employee_id': employee.id,
            'template_id': tmpl.id,
            'company_id': employee.company_id.id,
        })

    @api.model
    def _pbds_person_for(self, employee_id):
        emp = self.env['hr.employee'].browse(int(employee_id or 0)).exists()
        if not emp:
            raise UserError(self.env._("Choose a person to preview with."))
        emp.check_access('read')
        return emp

    @api.model
    def _pbds_preview_lang(self, tmpl, employee, draft, lang):
        """The language the preview opens in for this person while nobody
        has picked one (context `pbds_preview_auto`): `lang`, the language
        their letter is made in. A kind of document whose real print picks
        differently (contracts) overrides this."""
        return lang

    @api.model
    def preview(self, template_id, draft, employee_id, lang=None):
        """The finished page for one real person, from the UNSAVED draft.
        → {html, hidden, missing, values, lang}. Nothing is stored."""
        tmpl = self._template(template_id, 'read')
        _ = self.env._
        emp = self._pbds_person_for(employee_id)
        active = self._pbds_active_langs()
        lang = lang if lang in active else self.env['pb.hr.letter']._pbds_default_lang(tmpl, emp)
        if self.env.context.get('pbds_preview_auto'):
            lang = self._pbds_preview_lang(tmpl, emp, draft, lang)
        asked = lang
        body, heading, rules, page, lang = self._pbds_draft_parts(tmpl, draft, lang)
        _groups, flat = self._pbds_catalogue(tmpl)
        letter = self._pbds_preview_letter(tmpl, emp)
        missing = []

        def chip(key, blocked):
            spec = flat.get(key) or {}
            label = spec.get('label') or key
            if blocked:
                text, cls = _('You may not see pay'), 'pbds-miss pbds-pay'
            elif spec.get('later'):
                text, cls = _('%s — filled in when the letter is made', label), 'pbds-later'
            elif spec.get('missing') or not spec:
                text, cls = _('A field that no longer exists'), 'pbds-miss'
            else:
                text, cls = _('No %s on this person', label.lower() if label else label), 'pbds-miss'
            missing.append({'key': key, 'label': label, 'why': cls, 'text': text})
            return '<span class="%s">%s</span>' % (cls, escape(text))

        def wrap(key, value):
            if value in (None, ''):
                return value
            return '<span class="pbds-v pbds-k-%s">%s</span>' % (key, value)

        try:
            html, hidden = letter.with_context(pbds_rules_override=rules)._pbds_render(
                body, lang, ghost=True, missing=chip, wrap=wrap)
        except AccessError:
            raise UserError(_("You may not read everything this person's letter shows."))
        values_raw, _blocked = letter._pbds_values(lang, list(flat.keys()))
        values = {}
        for key, val in values_raw.items():
            if key in flat and val not in (None, ''):
                try:
                    values[key] = lxml_html.fromstring('<div>%s</div>' % val).text_content()
                except (etree.ParserError, ValueError):
                    values[key] = str(val)
        company = emp.company_id or self.env.company
        when = fields.Date.context_today(self)
        frame = self.env['ir.qweb']._render('pb_doc_studio.page_frame', {
            'page': page,
            'company': company.sudo(),
            'body': Markup(html_sanitize(html)),
            'subject': heading or tmpl.with_context(lang=lang).name,
            'date_text': self._pbds_long_date(when, lang),
            'sign_image': self._pbds_draft_sign(tmpl, draft) if page['sign'] == 'image' else False,
            'mode': 'screen',
            # `lang` is not a safe name in a QWeb call (the engine sets its
            # own): the page's language travels as `doc_lang`.
            'doc_lang': lang,
            'company_card': self._pbds_company_card(company),
            'env': self.env,
        })
        seen = set()
        unique_missing = []
        for row in missing:
            if row['key'] in seen:
                continue
            seen.add(row['key'])
            unique_missing.append(row)
        return {'html': str(frame), 'hidden': hidden, 'missing': unique_missing,
                'values': values, 'lang': asked, 'read_lang': lang}

    @api.model
    def sample_pdf(self, template_id, draft, employee_id, lang=None):
        """The true PDF for one person from the draft — no letter is created
        and nothing is filed. → {ok, name, data (base64)} or {ok: False, msg}."""
        tmpl = self._template(template_id, 'read')
        _ = self.env._
        emp = self._pbds_person_for(employee_id)
        active = self._pbds_active_langs()
        lang = lang if lang in active else self.env['pb.hr.letter']._pbds_default_lang(tmpl, emp)
        if self.env.context.get('pbds_preview_auto'):
            lang = self._pbds_preview_lang(tmpl, emp, draft, lang)
        body, heading, rules, page, lang = self._pbds_draft_parts(tmpl, draft, lang)
        letter = self._pbds_preview_letter(tmpl, emp)
        try:
            html, _hidden = letter.with_context(pbds_rules_override=rules)._pbds_render(body, lang)
        except AccessError:
            return {'ok': False, 'msg': _("You may not read everything this person's letter shows.")}
        except PayHidden:
            return {'ok': False, 'msg': _(
                "This letter shows pay, and you may not see this person's pay. "
                "Pick someone else, or ask someone who may see pay.")}
        company = (emp.company_id or self.env.company).sudo()
        sample = [{
            'record': False,
            'company': company,
            'page': page,
            'lang': lang,
            'subject': heading or tmpl.with_context(lang=lang).name or '',
            'date_text': self._pbds_long_date(fields.Date.context_today(self), lang),
            'body': Markup(self._pbds_inline_images(html_sanitize(html), tmpl)),
            'sign_image': self._pbds_draft_sign(tmpl, draft) if page['sign'] == 'image' else False,
        }]
        report = self._pbds_report(page)
        try:
            pdf, _ext = report.with_context(lang=lang)._render_qweb_pdf(
                report, res_ids=None, data={'pbds_sample': sample})
        except Exception:                              # noqa: BLE001
            _logger.exception('pb_doc_studio: sample PDF of template %s failed', tmpl.id)
            return {'ok': False, 'msg': _(
                "The PDF could not be made right now. Try again in a moment; "
                "the preview on screen is exactly what will print.")}
        name = '%s — %s.pdf' % (tmpl.with_context(lang=lang).name or _('Letter'), emp.name)
        return {'ok': True, 'name': name.replace('/', '-'),
                'data': base64.b64encode(pdf).decode()}


#: Styles of the page — one copy for the PDF and the preview (the same frame
#: draws both). Plain CSS that the PDF engine (an old WebKit) understands.
PAGE_CSS = """
.pbds-page { color: #1f2430; word-wrap: break-word; }
/* PDF only: keep the space before a bold or italic word (DOCSTUDIO PDFFIX,
   doc_common.pdf_body normalises the whitespace first) */
.pbds-pdf .pbds-body { white-space: pre-wrap; }
.pbds-pdf .pbds-keep { page-break-inside: avoid; }
.pbds-page p { margin: 0 0 0.75em; }
.pbds-page h1, .pbds-page h2, .pbds-page h3, .pbds-page h4, .pbds-page th, .pbds-page td { font-family: inherit; }
.pbds-page h1 { font-size: 1.6em; margin: 0.4em 0 0.5em; font-weight: 700; }
.pbds-page h2 { font-size: 1.3em; margin: 0.4em 0 0.5em; font-weight: 700; }
.pbds-page h3 { font-size: 1.12em; margin: 0.4em 0 0.4em; font-weight: 700; }
.pbds-page ul, .pbds-page ol { margin: 0 0 0.75em 1.4em; padding: 0; }
.pbds-page table { border-collapse: collapse; width: 100%; margin: 0.4em 0 0.9em; }
.pbds-page td, .pbds-page th { border: 1px solid #c9ced8; padding: 5px 8px; vertical-align: top; text-align: left; }
.pbds-page th { background: #f3f4f8; font-weight: 700; }
.pbds-page img { max-width: 100%; height: auto; }
.pbds-date { text-align: right; color: #64748b; font-size: 0.92em; }
.pbds-subject { margin: 14px 0 18px; font-weight: 700; font-size: 1.12em; }
.pbds-sign { margin-top: 42px; page-break-inside: avoid; }
.pbds-sign-space { height: 46px; }
.pbds-sign-img { max-height: 70px; max-width: 220px; display: block; margin-bottom: 4px; }
.pbds-sign-line { border-top: 1px solid #94a3b8; width: 240px; padding-top: 6px; }
.pbds-sign-title { color: #64748b; }
.pbds-lh { display: table; width: 100%; padding-bottom: 12px; margin-bottom: 22px; border-bottom: 2px solid #e2e4ee; }
.pbds-lh-logo { display: table-cell; width: 70px; vertical-align: middle; }
.pbds-lh-logo img { max-height: 48px; max-width: 64px; }
.pbds-lh-id { display: table-cell; vertical-align: middle; }
.pbds-lh-name { font-weight: 700; font-size: 1.08em; display: block; }
.pbds-lh-ad, .pbds-lh-ct { color: #64748b; font-size: 0.86em; display: block; }
.pbds-lf { margin-top: 36px; padding-top: 8px; border-top: 1px solid #e2e4ee; color: #94a3b8; font-size: 0.8em; text-align: center; }
.pbds-miss { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; border-radius: 999px; padding: 0 8px; font-size: 0.86em; white-space: nowrap; }
.pbds-later { background: #edeaf8; color: #4a3d96; border: 1px solid #cbc2ee; border-radius: 999px; padding: 0 8px; font-size: 0.86em; }
.pbds-ghost { display: none; }
.pbds-show-ghosts .pbds-ghost { display: block; opacity: 0.38; outline: 1px dashed #a59bd8; outline-offset: 3px; }
.pbds-v { border-radius: 4px; transition: background-color 1.2s ease; }
.pbds-v.pbds-flash { background-color: #ddd6f2; }
"""
