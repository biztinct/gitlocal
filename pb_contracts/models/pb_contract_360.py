# -*- coding: utf-8 -*-
"""CD-1 — the contract drawer's server side: one payload, one save path.

Four RPC methods on the `pb.contracts` facade:

  * ``get_contract_360``    — everything the drawer paints, in ONE round trip.
  * ``save_contract_360``   — the ONLY write path, returning the fresh payload.
  * ``preview_contract_360``— the same judgement with nothing written.
  * ``lookup_contract_m2o`` — a whitelisted picker feed.

House server contract (RECORDS_PHASE_R2_DESK.md:129): every method is
``@api.model``, returns plain dicts, and NEVER raises to the client for a user
mistake — a mistake is ``{'ok': False, 'msg': …}`` or a refusal entry carrying a
plain sentence. ``UserError`` is reserved for "you have no access at all".

Owner ruling (2026-08-29, `pb_records/__manifest__.py`): contract fields are
written IN PLACE on the existing contract. No new contract version, ever. A
component whose rule carries ``requires_new_contract`` is still written in
place; the payload merely flags it so the drawer can warn.

Validation lives in ONE private helper (`_cd_judge`) shared by save and
preview — two copies of a predicate are two answers the day one is edited.
"""

import logging
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_contracts import NEXT, STATE_LABEL, _initials

_logger = logging.getLogger(__name__)

# --- access (§1.7) --------------------------------------------------------
_HR_GROUP = 'hr.group_hr_user'
_OFFICER_GROUP = 'pb_hr_payroll_base.group_payroll_base_officer'
_CONTRACT_MGR_GROUP = 'hr_contract.group_hr_contract_manager'
# wage visibility mirrors the employee drawer exactly
# (`pb_employee_vault/models/pb_people_360.py:38`)
_PAYROLL_MGR_GROUP = 'om_hr_payroll.group_hr_payroll_manager'

_HISTORY_CAP = 120
_MASKED = '••••••'

# An open `comodel` argument is a data-exfiltration hole: the picker may only
# name the comodels the terms payload itself produces.
_M2O_WHITELIST = {
    'hr.payroll.structure', 'hr.contract.type', 'resource.calendar',
    'hr.department', 'hr.job', 'res.users', 'wfp.pay.grade', 'account.journal',
}

_TERM_GROUPS = [
    ('money', "The money"),
    ('dates', "Dates"),
    ('place', "Where they sit"),
    ('rules', "Payroll rules"),
]

# The terms table, in payload order. `optional` means the field arrives with a
# module that may not be installed (safety rail 8) — it is skipped, not guessed.
_TERMS = [
    ('money', 'wage', "Monthly wage", 'money',
     "Gross, before deductions.", False),
    ('money', 'struct_id', "Salary structure", 'm2o', False, False),
    ('money', 'type_id', "Employee category", 'm2o', False, False),
    ('money', 'schedule_pay', "Paid", 'select', False, False),
    ('money', 'grade_id', "Pay grade", 'm2o', False, True),
    ('money', 'compa_ratio', "Where the wage sits in the grade", 'readonly',
     "100 means the middle of the band.", True),
    ('money', 'journal_id', "Salary journal", 'm2o', False, True),

    ('dates', 'date_start', "Contract starts", 'date', False, False),
    ('dates', 'date_end', "Contract ends", 'date',
     "Leave empty for an open-ended contract.", False),
    ('dates', 'trial_date_end', "Trial ends", 'date', False, False),
    ('dates', 'resource_calendar_id', "Working schedule", 'm2o', False, False),

    ('place', 'department_id', "Department", 'm2o', False, False),
    ('place', 'job_id', "Job position", 'm2o', False, False),
    ('place', 'location', "Location", 'text', False, False),
    ('place', 'costcenter', "Cost centre", 'text', False, False),
    ('place', 'hr_responsible_id', "HR responsible", 'm2o', False, False),

    ('rules', 'hirestatus', "Employment status", 'select', False, False),
    ('rules', 'tupart', "Union participation", 'toggle', False, False),
    ('rules', 'shuipart', "Social insurance participation", 'toggle', False,
     False),
    ('rules', 'dependents', "Dependants", 'integer', False, False),
    ('rules', 'tax_identification_number', "Tax number", 'text', False, False),
]

# A required term emptied on purpose gets a sentence that names the thing on
# the screen, not the field.
_REQUIRED_SENTENCE = {
    'resource_calendar_id': "A contract must always have a working schedule — "
                            "pick one before saving.",
    'type_id': "A contract must always have an employee category — pick one "
               "before saving.",
    'date_start': "A contract must always have a start date — pick one before "
                  "saving.",
    'wage': "A contract must always have a monthly wage — type one before "
            "saving.",
}

# `change_source` → the sentence a payroll administrator reads.
_SOURCE_SENTENCE = {
    'manual': "Typed in Payobook",
    'import': "From a pay data file",
    'import_default': "Filled from the component's default",
}
_FEED_SENTENCE = "From the connected system"


def _dlabel(value):
    """'01 Jun 2026' from a date, or an empty string."""
    if not value:
        return ''
    if isinstance(value, datetime):
        value = value.date()
    try:
        return value.strftime('%d %b %Y')
    except Exception:       # noqa: BLE001 — a display helper never breaks a read
        return str(value)


class PbContracts(models.AbstractModel):
    _inherit = 'pb.contracts'

    # =================================================================
    # Gates
    # =================================================================
    @api.model
    def _cd_may_read(self):
        user = self.env.user
        return (user.has_group(_HR_GROUP)
                or user.has_group(_OFFICER_GROUP)
                or user._is_admin())

    @api.model
    def _cd_require_read(self):
        # The ONE place a raise is right: not a mistake, an absence of access.
        if not self._cd_may_read():
            raise UserError(_(
                "You do not have access to contracts. Ask an administrator "
                "for the HR or Payroll Officer role."))

    @api.model
    def _cd_may_write(self):
        """Asked ONCE and turned into a lock hint, so a field this person could
        never save is read-only on screen instead of raising an access dialog
        after they have typed into it (the `_may_write` precedent,
        `pb_records/models/pb_records_desk.py:91`)."""
        if not self._cd_may_read():
            return False
        if not self.env.user.has_group(_CONTRACT_MGR_GROUP):
            return False
        try:
            self.env['hr.contract'].check_access('write')
            return True
        except Exception:   # noqa: BLE001 — an ACL question, not a crash
            return False

    @api.model
    def _cd_unmask_wage(self):
        user = self.env.user
        return user.has_group(_PAYROLL_MGR_GROUP) or user._is_admin()

    # =================================================================
    # Small shared helpers
    # =================================================================
    @api.model
    def _cd_num(self, value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return ''
        if abs(number - round(number)) < 1e-6:
            return '{:,.0f}'.format(number)
        return '{:,.2f}'.format(number)

    @api.model
    def _cd_money(self, value, symbol):
        """Money is formatted server-side, once (safety rail 6)."""
        return '%s%s' % (symbol or '', self._cd_num(value))

    @api.model
    def _cd_contract(self, contract_id):
        """The contract, read with the CALLING user's rights so record rules
        apply (safety rail 3). `None` when it is gone or not theirs."""
        try:
            contract = self.env['hr.contract'].browse(int(contract_id or 0))
        except (TypeError, ValueError):
            return None
        if not contract.exists():
            return None
        try:
            contract.check_access('read')
            contract.mapped('name')
        except Exception:   # noqa: BLE001 — invisible reads as absent
            return None
        return contract

    @api.model
    def _cd_gone(self):
        return {'ok': False, 'error': _("That contract is no longer here.")}

    @api.model
    def _cd_rule_by_code(self, codes):
        """The string-code join onto `hr.formula.rule` — the same one
        `_get_or_create_advantage_template` uses. The rules module may be
        absent, and then every component is simply an amount (rail 7/8)."""
        out = {}
        codes = [c for c in (codes or []) if c]
        Rule = self.env.get('hr.formula.rule')
        if Rule is None or not codes:
            return out
        try:
            for rule in Rule.sudo().search([('code', 'in', codes)], order='id'):
                out.setdefault(rule.code, rule)
        except Exception:   # noqa: BLE001
            _logger.debug("Contract drawer: component rules unavailable",
                          exc_info=True)
        return out

    # =================================================================
    # 2.1 — the bundled read
    # =================================================================
    @api.model
    def get_contract_360(self, contract_id):
        self._cd_require_read()
        contract = self._cd_contract(contract_id)
        if contract is None:
            return self._cd_gone()
        try:
            return self._cd_payload(contract)
        except Exception:   # noqa: BLE001 — a drawer that cannot open is not
                            # allowed to become a traceback dialog
            _logger.exception("Contract drawer: payload failed for %s",
                              contract_id)
            return {'ok': False,
                    'error': _("Payobook could not open this contract just "
                               "now. Try again in a moment.")}

    @api.model
    def _cd_payload(self, contract):
        can_write = self._cd_may_write()
        unmask = self._cd_unmask_wage()
        symbol = ((contract.company_id or self.env.company)
                  .currency_id.symbol or '')
        return {
            'ok': True,
            'error': False,
            'currency': symbol,
            'can_write': can_write,
            'unmask_wage': unmask,
            'header': self._cd_header(contract, symbol, unmask),
            'terms': self._cd_terms(contract, symbol, can_write, unmask),
            'readiness': self._cd_readiness(contract),
            'components': self._safe(
                lambda: self._cd_components(contract, symbol, can_write,
                                            unmask),
                default={'rows': [], 'count': 0, 'total': 0.0, 'addable': []}),
            'history': self._safe(
                lambda: self._cd_history(contract, symbol, unmask),
                default={'rows': [], 'total': 0, 'shown': 0}),
        }

    # ------------------------------------------------------------- header
    @api.model
    def _cd_header(self, contract, symbol, unmask):
        # Names shown in the header are labels, not data (see `_cd_field_entry`)
        employee = contract.employee_id.sudo()
        department = contract.department_id.sudo()
        today = date.today()

        # the three-step rail, reused from `get_contract_detail` (§1.1)
        rail_state = {'draft': 'draft', 'open': 'running', 'close': 'expired',
                      'cancel': 'expired'}.get(contract.state, 'draft')
        order = ['draft', 'running', 'expired']
        current = order.index(rail_state)
        pipeline = [{'key': step, 'label': step.capitalize(),
                     'done': index < current, 'current': index == current}
                    for index, step in enumerate(order)]

        ends_label, ends_tone = self._cd_ends(contract, today)
        return {
            'contract_id': contract.id,
            'reference': contract.name or '—',
            'employee': employee.name if employee else '—',
            'employee_id': employee.id if employee else False,
            'initials': _initials(employee.name if employee else ''),
            'avatar': (('/web/image/hr.employee/%s/avatar_128' % employee.id)
                       if employee else False),
            'job': (employee.job_id.name if (employee and employee.job_id)
                    else (contract.job_id.sudo().name if contract.job_id
                          else '')),
            'dept': department.name if department else '',
            'state': contract.state,
            'state_label': STATE_LABEL.get(contract.state, contract.state),
            'wage': (contract.wage or 0.0) if unmask else False,
            'wage_masked': not unmask,
            'ends_label': ends_label,
            'ends_tone': ends_tone,
            'pipeline': pipeline,
            'next_actions': [{'method': m, 'label': l, 'icon': i, 'kind': k}
                             for (m, l, i, k) in NEXT.get(contract.state, [])],
        }

    @api.model
    def _cd_ends(self, contract, today):
        if contract.state in ('close', 'cancel'):
            if contract.date_end:
                return _("Ended %s") % _dlabel(contract.date_end), 'muted'
            return _("Not running"), 'muted'
        if not contract.date_end:
            return _("Open-ended"), 'ok'
        days = (contract.date_end - today).days
        if days < 0:
            return _("Ended %s days ago") % abs(days), 'err'
        if days == 0:
            return _("Ends today"), 'err'
        if days <= 60:
            return _("Ends in %s days") % days, 'warn'
        return _("Ends in %s days") % days, 'ok'

    # -------------------------------------------------------------- terms
    @api.model
    def _cd_terms(self, contract, symbol, can_write, unmask):
        Contract = self.env['hr.contract']
        buckets = {key: [] for key, _label in _TERM_GROUPS}
        for group, name, label, kind, hint, optional in _TERMS:
            field = Contract._fields.get(name)
            if field is None:
                # the module that carries it is not installed (rail 8)
                continue
            if name == 'compa_ratio' and not getattr(contract, 'grade_id',
                                                     False):
                continue
            entry = self._cd_field_entry(contract, field, name, label, kind,
                                         hint, symbol, can_write, unmask)
            if entry:
                buckets[group].append(entry)
        return [{'key': key, 'label': label, 'fields': buckets[key]}
                for key, label in _TERM_GROUPS]

    @api.model
    def _cd_field_entry(self, contract, field, name, label, kind, hint,
                        symbol, can_write, unmask):
        raw = contract[name]
        # Odoo already sets `readonly` on a computed field that has no inverse,
        # so one test carries both halves of the rule.
        writable = bool(can_write and not field.readonly and kind != 'readonly')
        entry = {
            'name': name,
            'label': label,
            'kind': kind,
            'value': False,
            'display': '',
            'required': bool(field.required),
            'writable': writable,
            'hint': hint or False,
            'tone': None,
        }

        if kind == 'money':
            masked = (name == 'wage' and not unmask)
            entry['value'] = False if masked else (raw or 0.0)
            entry['display'] = _MASKED if masked else self._cd_money(raw or 0.0,
                                                                    symbol)
            if masked:
                entry['writable'] = False
        elif kind == 'readonly':
            entry['value'] = raw if isinstance(raw, (int, float)) else False
            entry['display'] = self._cd_num(raw) if isinstance(
                raw, (int, float)) else (str(raw) if raw else '')
        elif kind == 'integer':
            entry['value'] = int(raw or 0)
            entry['display'] = str(int(raw or 0))
        elif kind == 'number':
            entry['value'] = float(raw or 0.0)
            entry['display'] = self._cd_num(raw or 0.0)
        elif kind == 'date':
            entry['value'] = str(raw) if raw else False
            entry['display'] = _dlabel(raw) or '—'
            if name == 'date_end' and raw and raw < date.today() \
                    and contract.state == 'open':
                entry['tone'] = 'warn'
        elif kind in ('select', 'toggle'):
            pairs = field._description_selection(self.env)
            entry['options'] = [{'value': key, 'label': text}
                                for key, text in pairs]
            entry['value'] = raw or False
            entry['display'] = dict(pairs).get(raw, '') if raw else '—'
        elif kind == 'm2o':
            entry['comodel'] = field.comodel_name
            entry['value'] = raw.id if raw else False
            # The NAME of a department or a schedule is a label, not data: read
            # it with `sudo()` so a reader who may see the contract but not the
            # catalogue behind it still gets a readable drawer instead of an
            # access error (rail 7 — one sub-read may not sink the payload).
            entry['value_label'] = (raw.sudo().display_name or '') if raw else ''
            entry['display'] = entry['value_label'] or '—'
        else:                                   # text
            entry['value'] = raw or ''
            entry['display'] = raw or '—'
        return entry

    # ---------------------------------------------------------- readiness
    @api.model
    def _cd_readiness(self, contract):
        Contract = self.env['hr.contract']
        chips = [
            {'key': 'structure', 'label': _("Salary structure"),
             'ok': bool(getattr(contract, 'struct_id', False)
                        or contract.structure_type_id)},
            {'key': 'schedule', 'label': _("Working schedule"),
             'ok': bool(contract.resource_calendar_id)},
        ]
        if 'tax_identification_number' in Contract._fields:
            chips.append({'key': 'tax', 'label': _("Tax number"),
                          'ok': bool(contract.tax_identification_number)})
        chips.append({'key': 'category', 'label': _("Employee category"),
                      'ok': bool(getattr(contract, 'type_id', False))})
        return chips

    # --------------------------------------------------------- components
    @api.model
    def _cd_components(self, contract, symbol, can_write, unmask):
        Advantage = self.env['hr.contract.advantage']
        Template = self.env['hr.contract.advantage.template']
        typed = 'value_type' in Advantage._fields

        # Read with the caller's own rights (rail 3). `_order` is NOT declared
        # on this model, so the payload sorts explicitly by code (§1.4) — the
        # id order is template-creation order and looks random on screen.
        lines = Advantage.search([('contract_id', '=', contract.id)])
        lines = lines.sorted(
            key=lambda l: ((l.advantage_template_code or '').upper(), l.id))

        rules = self._cd_rule_by_code(
            [l.advantage_template_code for l in lines])

        rows = []
        total = 0.0
        for line in lines:
            code = line.advantage_template_code or ''
            template = line.advantage_template_id
            value_type = (line.value_type or 'amount') if typed else 'amount'
            lower = line.advantage_lower_bound or 0.0
            upper = line.advantage_upper_bound or 0.0
            bounded = not (lower == 0 and upper == 0)
            rule = rules.get(code)
            if value_type == 'text':
                text_value = (line.text_value or '') if typed else ''
                display = text_value or '—'
            else:
                text_value = False
                display = self._cd_money(line.amount or 0.0, symbol)
                total += line.amount or 0.0
            rows.append({
                'id': line.id,
                'code': code,
                'name': template.name or code or '—',
                'value_type': value_type,
                'amount': line.amount or 0.0,
                'text_value': text_value,
                'display': display,
                'lower': lower,
                'upper': upper,
                'bounded': bounded,
                'bounds_hint': (self._cd_bounds_hint(lower, upper, symbol)
                                if (bounded and value_type != 'text') else False),
                'value_kind': (rule.value_kind if rule else 'money') or 'money',
                'requires_new_contract': bool(
                    rule.requires_new_contract) if rule else False,
                'template_id': template.id or False,
                'writable': can_write,
            })

        used = set(lines.mapped('advantage_template_id').ids)
        addable = []
        for template in Template.sudo().search([], order='code, id'):
            if template.id in used:
                continue
            addable.append({
                'template_id': template.id,
                'code': template.code or '',
                'name': template.name or template.code or '',
                'value_type': (template.value_type or 'amount') if
                'value_type' in Template._fields else 'amount',
                'lower': template.lower_bound or 0.0,
                'upper': template.upper_bound or 0.0,
                'default': template.default_value or 0.0,
            })

        return {'rows': rows, 'count': len(rows),
                'total': total if unmask else False,
                'addable': addable}

    @api.model
    def _cd_bounds_hint(self, lower, upper, symbol):
        return _("Between %(low)s and %(high)s.") % {
            'low': self._cd_money(lower, symbol),
            'high': self._cd_money(upper, symbol)}

    # ------------------------------------------------------------ history
    @api.model
    def _cd_history(self, contract, symbol, unmask):
        rows = []
        rows += self._safe(
            lambda: self._cd_history_components(contract, symbol), default=[])
        rows += self._safe(
            lambda: self._cd_history_fields(contract, unmask, symbol),
            default=[])
        rows += self._safe(
            lambda: self._cd_history_retro(contract, symbol), default=[])
        rows.sort(key=lambda r: r.get('_sort') or '', reverse=True)
        total = len(rows)
        rows = rows[:_HISTORY_CAP]
        for row in rows:
            row.pop('_sort', None)
        return {'rows': rows, 'total': total, 'shown': len(rows)}

    @api.model
    def _cd_history_components(self, contract, symbol):
        Change = self.env.get('hr.contract.advantage.change')
        if Change is None:
            return []
        out = []
        for change in Change.sudo().search(
                [('contract_id', '=', contract.id)], limit=_HISTORY_CAP * 2):
            template = change.advantage_template_id
            is_text = (template.value_type == 'text') if (
                template and 'value_type' in template._fields) else bool(
                change.old_text_value or change.new_text_value)
            if is_text:
                old = change.old_text_value or False
                new = change.new_text_value or False
            else:
                old = self._cd_money(change.old_amount or 0.0, symbol)
                new = self._cd_money(change.new_amount or 0.0, symbol)
            when = change.changed_at or change.create_date
            out.append({
                '_sort': fields.Datetime.to_string(when) if when else '',
                'kind': 'component',
                'when': fields.Datetime.to_string(when) if when else '',
                'when_label': _dlabel(change.effective_date or (
                    when.date() if when else False)),
                'title': template.name or change.advantage_template_code or '—',
                'from': old,
                'to': new,
                'source': self._cd_change_sentence(change),
                'actor': change.changed_by.name or False,
                'tone': 'indigo',
            })
        return out

    @api.model
    def _cd_change_sentence(self, change):
        source = change.change_source or 'import'
        if source == 'import':
            batch = change.import_batch_id
            # `api_data_store` is the value a batch carries when the rows came
            # from the connected system rather than a dropped file
            # (`payroll_import_batch.py:920`).
            if batch and getattr(batch, 'source_type', '') == 'api_data_store':
                return _FEED_SENTENCE
        return _SOURCE_SENTENCE.get(source, _SOURCE_SENTENCE['import'])

    @api.model
    def _cd_history_fields(self, contract, unmask, symbol=''):
        Entry = self.env.get('biz.audit.entry')
        if Entry is None:
            return []
        # The audit trail stores `str(value)`, so a wage change reads
        # "12500000.0 → 72000000.0" on a live tenant. Money is formatted once,
        # server-side (rail 6), and the row is titled with the drawer's own
        # word for the field rather than the model's.
        money_fields = {'wage'}
        labels = {name: label for _g, name, label, _k, _h, _o in _TERMS}
        out = []
        for entry in Entry.sudo().search(
                [('model_name', '=', 'hr.contract'),
                 ('res_id', '=', contract.id)], limit=_HISTORY_CAP * 2):
            masked = (entry.field_name == 'wage' and not unmask)
            is_money = entry.field_name in money_fields
            out.append({
                '_sort': fields.Datetime.to_string(entry.stamp)
                if entry.stamp else '',
                'kind': 'field',
                'when': fields.Datetime.to_string(entry.stamp)
                if entry.stamp else '',
                'when_label': _dlabel(entry.stamp),
                'title': (labels.get(entry.field_name)
                          or entry.field_label or entry.field_name or '—'),
                'from': False if masked else self._cd_history_value(
                    entry.old_value, is_money, symbol),
                'to': False if masked else self._cd_history_value(
                    entry.new_value, is_money, symbol),
                'source': _("Changed on the contract"),
                'actor': entry.user_id.name or False,
                'tone': 'teal',
            })
        return out

    @api.model
    def _cd_history_value(self, stored, is_money, symbol):
        if not stored:
            return False
        if not is_money:
            return stored
        try:
            return self._cd_money(float(stored), symbol)
        except (TypeError, ValueError):
            return stored

    @api.model
    def _cd_history_retro(self, contract, symbol):
        Retro = self.env.get('hr.payroll.retro.adjustment')
        if Retro is None:
            return []
        out = []
        for retro in Retro.sudo().search(
                [('contract_id', '=', contract.id)], limit=_HISTORY_CAP * 2):
            when = retro.create_date
            out.append({
                '_sort': fields.Datetime.to_string(when) if when else '',
                'kind': 'retro',
                'when': fields.Datetime.to_string(when) if when else '',
                'when_label': _dlabel(retro.change_effective_date
                                      or retro.period_from
                                      or (when.date() if when else False)),
                'title': (retro.component_id.name or retro.component_code
                          or _("Back pay")),
                'from': self._cd_money(retro.old_amount or 0.0, symbol),
                'to': self._cd_money(retro.new_amount or 0.0, symbol),
                'source': _("Back pay worked out for an earlier period"),
                'actor': False,
                'tone': 'amber',
            })
        return out

    # =================================================================
    # 2.2 / 2.3 — one judgement, two callers
    # =================================================================
    @api.model
    def _cd_writable_map(self, contract, symbol, can_write, unmask):
        """`{field name: payload entry}` for the terms this person may send."""
        out = {}
        for group in self._cd_terms(contract, symbol, can_write, unmask):
            for entry in group['fields']:
                out[entry['name']] = entry
        return out

    @api.model
    def _cd_judge(self, contract, terms, components, symbol, can_write, unmask):
        """Everything `save_` and `preview_` both have to decide.

        Returns `(term_vals, plan, refusals)` and writes NOTHING. `plan` is
        `{'edits': [...], 'adds': [...], 'removes': [...]}`, already resolved
        into records so the caller only has to write them.
        """
        refusals = []
        term_vals = {}
        offered = self._cd_writable_map(contract, symbol, can_write, unmask)

        for name, value in (terms or {}).items():
            entry = offered.get(name)
            # Silently dropping a key is wrong — it reads as saved (§2.2.2).
            if entry is None:
                refusals.append({
                    'scope': 'term', 'key': name,
                    'why': _("That is not something this screen can change, "
                             "so it was left alone.")})
                continue
            if not entry['writable']:
                refusals.append({
                    'scope': 'term', 'key': name,
                    'why': _("%s cannot be changed here — it is read-only on "
                             "this contract.") % entry['label']})
                continue
            coerced, why = self._cd_coerce_term(contract, entry, value)
            if why:
                refusals.append({'scope': 'term', 'key': name, 'why': why})
                continue
            term_vals[name] = coerced

        plan = self._cd_judge_components(contract, components or {}, symbol,
                                         can_write, refusals)
        return term_vals, plan, refusals

    @api.model
    def _cd_coerce_term(self, contract, entry, value):
        """`(coerced, why)` — `why` is a plain sentence and means refused.

        The sentences are DELIBERATELY identical to the Records Desk's
        (`pb_records/models/pb_records_desk.py:791 _coerce`), so a person meets
        one voice whichever screen they are on. That method needs a desk card
        and an import probe, neither of which exists here, so the shapes are
        re-stated rather than called.
        """
        name = entry['name']
        kind = entry['kind']
        # `False` IS an explicit clear (the drawer's "empty this") and `0` is
        # NOT — `isinstance(False, int)` is True, so the two are separated by
        # identity, never by truthiness.
        empty = (value is None or value is False
                 or (isinstance(value, str) and not value.strip()))

        if empty:
            if entry['required']:
                return None, _REQUIRED_SENTENCE.get(name) or _(
                    "%s cannot be left empty — fill it in before saving."
                ) % entry['label']
            if kind in ('money', 'number'):
                return 0.0, None
            if kind == 'integer':
                return 0, None
            if kind == 'text':
                return False, None
            return False, None

        if kind in ('money', 'number'):
            try:
                return float(str(value).replace(',', '').strip()), None
            except (TypeError, ValueError):
                return None, _("'%(value)s' is not a number — type an amount "
                               "like 1500000.") % {'value': value}

        if kind == 'integer':
            try:
                return int(float(str(value).replace(',', '').strip())), None
            except (TypeError, ValueError):
                return None, _("'%(value)s' is not a whole number — type a "
                               "number like 2.") % {'value': value}

        if kind == 'date':
            try:
                return fields.Date.to_date(value), None
            except Exception:   # noqa: BLE001
                return None, _("'%(value)s' is not a date — type it as "
                               "2026-06-01.") % {'value': value}

        if kind in ('select', 'toggle'):
            pairs = entry.get('options') or []
            keys = {p['value'] for p in pairs}
            text = str(value).strip()
            if text in keys:
                return text, None
            lowered = {}
            for pair in pairs:
                lowered.setdefault(pair['label'].strip().lower(), pair['value'])
                lowered.setdefault(pair['value'].strip().lower(), pair['value'])
            if text.lower() in lowered:
                return lowered[text.lower()], None
            shown = ", ".join(p['label'] for p in pairs[:12])
            return None, _("'%(value)s' is not one of the choices — use "
                           "%(list)s") % {'value': value, 'list': shown}

        if kind == 'm2o':
            comodel = self.env.get(entry.get('comodel'))
            if comodel is None:
                return None, _("%s cannot be changed here.") % entry['label']
            if isinstance(value, dict):
                value = value.get('id')
            try:
                rec_id = int(value)
            except (TypeError, ValueError):
                return None, _("Pick %s from the list.") % entry['label'].lower()
            target = comodel.sudo().browse(rec_id).exists()
            if not target:
                return None, _("That choice no longer exists.")
            return target.id, None

        return str(value).strip(), None

    @api.model
    def _cd_judge_components(self, contract, components, symbol, can_write,
                             refusals):
        plan = {'edits': [], 'adds': [], 'removes': []}
        if not components:
            return plan
        Advantage = self.env['hr.contract.advantage']
        Template = self.env['hr.contract.advantage.template']
        typed = 'value_type' in Advantage._fields

        if not can_write:
            # the caller already refused the whole call; nothing to plan
            return plan

        lines = Advantage.sudo().search([('contract_id', '=', contract.id)])
        by_id = {line.id: line for line in lines}
        used_templates = set(lines.mapped('advantage_template_id').ids)

        # ---- edits
        for raw_id, payload in (components.get('edits') or {}).items():
            try:
                line = by_id[int(raw_id)]
            except (TypeError, ValueError, KeyError):
                refusals.append({
                    'scope': 'component', 'key': raw_id,
                    'why': _("That component is no longer on this contract.")})
                continue
            label = line.advantage_template_id.name \
                or line.advantage_template_code or _("This component")
            value_type = (line.value_type or 'amount') if typed else 'amount'
            payload = payload or {}

            if value_type == 'text':
                if 'amount' in payload:
                    refusals.append({
                        'scope': 'component', 'key': line.id,
                        'why': _("%s holds text, not an amount — type the "
                                 "words instead.") % label})
                    continue
                if not typed:
                    continue
                text = '' if payload.get('text_value') is None \
                    else str(payload.get('text_value')).strip()
                if text == (line.text_value or ''):
                    continue
                plan['edits'].append({
                    'line': line, 'vals': {'text_value': text or False},
                    'old_text': line.text_value or '', 'new_text': text,
                    'old_amount': 0.0, 'new_amount': 0.0, 'is_text': True})
                continue

            if 'text_value' in payload:
                refusals.append({
                    'scope': 'component', 'key': line.id,
                    'why': _("%s holds an amount, not text — type a number "
                             "instead.") % label})
                continue
            try:
                amount = float(str(payload.get('amount')).replace(',', '').strip())
            except (TypeError, ValueError):
                refusals.append({
                    'scope': 'component', 'key': line.id,
                    'why': _("'%(value)s' is not a number — type an amount "
                             "like 1500000.") % {'value': payload.get('amount')}})
                continue
            why = self._cd_bounds_refusal(
                label, amount, line.advantage_lower_bound or 0.0,
                line.advantage_upper_bound or 0.0, symbol)
            if why:
                refusals.append({'scope': 'component', 'key': line.id,
                                 'why': why})
                continue
            if abs(amount - (line.amount or 0.0)) < 1e-9:
                continue
            plan['edits'].append({
                'line': line, 'vals': {'amount': amount},
                'old_amount': line.amount or 0.0, 'new_amount': amount,
                'old_text': '', 'new_text': '', 'is_text': False})

        # ---- adds
        for item in (components.get('adds') or []):
            item = item or {}
            try:
                template = Template.sudo().browse(
                    int(item.get('template_id'))).exists()
            except (TypeError, ValueError):
                template = None
            if not template:
                refusals.append({
                    'scope': 'component', 'key': item.get('template_id'),
                    'why': _("That component no longer exists.")})
                continue
            label = template.name or template.code or _("This component")
            if template.id in used_templates:
                refusals.append({
                    'scope': 'component', 'key': template.id,
                    'why': _("This contract already has %s.") % label})
                continue
            value_type = (template.value_type or 'amount') if \
                'value_type' in Template._fields else 'amount'
            vals = {'contract_id': contract.id,
                    'advantage_template_id': template.id}
            if value_type == 'text':
                text = item.get('text_value')
                vals['text_value'] = (str(text).strip() or False) if text \
                    else False
                plan['adds'].append({'template': template, 'vals': vals,
                                     'is_text': True,
                                     'new_text': vals['text_value'] or '',
                                     'new_amount': 0.0})
            else:
                if item.get('amount') in (None, ''):
                    amount = template.default_value or 0.0
                else:
                    try:
                        amount = float(str(item['amount']).replace(',', '').strip())
                    except (TypeError, ValueError):
                        refusals.append({
                            'scope': 'component', 'key': template.id,
                            'why': _("'%(value)s' is not a number — type an "
                                     "amount like 1500000.")
                            % {'value': item['amount']}})
                        continue
                why = self._cd_bounds_refusal(
                    label, amount, template.lower_bound or 0.0,
                    template.upper_bound or 0.0, symbol)
                if why:
                    refusals.append({'scope': 'component', 'key': template.id,
                                     'why': why})
                    continue
                vals['amount'] = amount
                plan['adds'].append({'template': template, 'vals': vals,
                                     'is_text': False, 'new_text': '',
                                     'new_amount': amount})
            used_templates.add(template.id)

        # ---- removes
        for raw_id in (components.get('removes') or []):
            try:
                line = by_id[int(raw_id)]
            except (TypeError, ValueError, KeyError):
                refusals.append({
                    'scope': 'component', 'key': raw_id,
                    'why': _("That component is no longer on this contract.")})
                continue
            label = line.advantage_template_id.name \
                or line.advantage_template_code or _("This component")
            if self._cd_is_filled_by_mapping(line.advantage_template_code):
                refusals.append({
                    'scope': 'component', 'key': line.id,
                    'why': _("%s is filled automatically from a mapping, so "
                             "it cannot be removed here.") % label})
                continue
            plan['removes'].append(line)

        return plan

    @api.model
    def _cd_bounds_refusal(self, label, amount, lower, upper, symbol):
        """The model's own window rule, checked FIRST so the person reads this
        sentence instead of a raised constraint (§2.2.6). Mirrors
        `om_hr_payroll/models/hr_contract.py:35` exactly: a zero amount and a
        both-zero window are both unbounded."""
        if not amount or amount == 0.0:
            return None
        if upper == 0 and lower == 0:
            return None
        if amount > upper or amount < lower:
            return _("%(name)s must be between %(low)s and %(high)s.") % {
                'name': label, 'low': self._cd_money(lower, symbol),
                'high': self._cd_money(upper, symbol)}
        return None

    @api.model
    def _cd_is_filled_by_mapping(self, code):
        """Is this component the landing place of a scheme's column?

        Two ways it can be: the scheme's rule is marked a contract component,
        or a mapping row points at that rule. Either way the value comes back
        on the next pay data file, so removing the line here is a lie.
        """
        if not code:
            return False
        Rule = self.env.get('hr.formula.rule')
        if Rule is None:
            return False
        try:
            rules = Rule.sudo().search([('code', '=', code)])
            if any(r.is_contract_component for r in rules):
                return True
            Mapping = self.env.get('hr.payslip.import.mapping')
            if Mapping is not None and rules:
                return bool(Mapping.sudo().search_count(
                    [('component_id', 'in', rules.ids)]))
        except Exception:   # noqa: BLE001
            _logger.debug("Contract drawer: mapping check failed for %s", code,
                          exc_info=True)
        return False

    # =================================================================
    # 2.2 — the one write path
    # =================================================================
    @api.model
    def save_contract_360(self, contract_id, terms=None, components=None,
                          note=None):
        self._cd_require_read()
        contract = self._cd_contract(contract_id)
        if contract is None:
            return {'ok': False, 'saved': 0, 'refusals': [],
                    'msg': _("That contract is no longer here."),
                    'detail': self._cd_gone()}

        can_write = self._cd_may_write()
        unmask = self._cd_unmask_wage()
        symbol = ((contract.company_id or self.env.company)
                  .currency_id.symbol or '')
        if not can_write:
            return {'ok': False, 'saved': 0, 'refusals': [],
                    'msg': _("You can look at contracts but not change them. "
                             "Ask an HR manager to make this change."),
                    'detail': self._cd_payload(contract)}

        term_vals, plan, refusals = self._cd_judge(
            contract, terms, components, symbol, can_write, unmask)

        saved = 0
        # ---- the terms, written IN PLACE on this contract (owner ruling §1.8)
        if term_vals:
            try:
                with self.env.cr.savepoint():
                    contract.write(term_vals)
                saved += len(term_vals)
            except Exception as error:   # noqa: BLE001
                _logger.exception("Contract drawer: write refused on %s",
                                  contract.id)
                reason = self._cd_reason(error)
                for name in term_vals:
                    refusals.append({'scope': 'term', 'key': name,
                                     'why': reason})

        # ---- the components. The satellite tables are written with `sudo()`
        # and ONLY here, after the contract write right is proved (rail 3, W97:
        # `hr.contract.advantage` has no `company_id`, so it inherits its
        # owner's record rule and one unreadable row takes the table with it).
        for edit in plan['edits']:
            try:
                with self.env.cr.savepoint():
                    edit['line'].sudo().write(edit['vals'])
                    self._cd_log_component(
                        contract, edit['line'].advantage_template_id,
                        edit, note)
                saved += 1
            except Exception as error:   # noqa: BLE001
                _logger.exception("Contract drawer: component write refused")
                refusals.append({'scope': 'component',
                                 'key': edit['line'].id,
                                 'why': self._cd_reason(error)})

        for add in plan['adds']:
            try:
                with self.env.cr.savepoint():
                    line = self.env['hr.contract.advantage'].sudo().create(
                        add['vals'])
                    self._cd_log_component(
                        contract, add['template'],
                        {'is_text': add['is_text'], 'old_amount': 0.0,
                         'new_amount': add['new_amount'], 'old_text': '',
                         'new_text': add['new_text']}, note)
                saved += 1
            except Exception as error:   # noqa: BLE001
                _logger.exception("Contract drawer: component add refused")
                refusals.append({'scope': 'component',
                                 'key': add['template'].id,
                                 'why': self._cd_reason(error)})

        for line in plan['removes']:
            line_id = line.id
            try:
                with self.env.cr.savepoint():
                    line.sudo().unlink()
                saved += 1
            except Exception as error:   # noqa: BLE001
                _logger.exception("Contract drawer: component remove refused")
                refusals.append({'scope': 'component', 'key': line_id,
                                 'why': self._cd_reason(error)})

        return {'ok': True, 'saved': saved, 'refusals': refusals,
                'msg': self._cd_msg(saved, len(refusals)),
                'detail': self._cd_payload(contract)}

    @api.model
    def _cd_reason(self, error):
        """A raised constraint turned into a sentence. Nothing partially
        written may be reported as saved (§2.2.8)."""
        text = str(getattr(error, 'name', None) or error or '').strip()
        if not text or len(text) > 240:
            return _("Payobook could not save this change. Nothing was "
                     "changed for it.")
        return text

    @api.model
    def _cd_msg(self, saved, refused):
        if saved and refused:
            return _("%(saved)s saved, %(refused)s left alone.") % {
                'saved': _("1 change") if saved == 1 else _("%s changes")
                % saved,
                'refused': _("1") if refused == 1 else str(refused)}
        if saved:
            return _("1 change saved.") if saved == 1 else _(
                "%s changes saved.") % saved
        if refused:
            return _("Nothing was saved — %s could not be used.") % (
                _("one change") if refused == 1 else _("%s changes") % refused)
        return _("Nothing to save.")

    @api.model
    def _cd_log_component(self, contract, template, entry, note=None):
        """The component audit row, filed exactly the way the Records Desk
        files it (`pb_records/models/pb_records_desk.py:1246-1256`)."""
        Change = self.env.get('hr.contract.advantage.change')
        if Change is None or not template:
            return
        Change.sudo().create({
            'contract_id': contract.id,
            'advantage_template_id': template.id,
            'old_amount': 0.0 if entry.get('is_text') else (
                entry.get('old_amount') or 0.0),
            'new_amount': 0.0 if entry.get('is_text') else (
                entry.get('new_amount') or 0.0),
            'old_text_value': (entry.get('old_text') or False)
            if entry.get('is_text') else False,
            'new_text_value': (entry.get('new_text') or False)
            if entry.get('is_text') else False,
            'effective_date': fields.Date.context_today(self),
            'change_source': 'manual',
            'changed_by': self.env.user.id,
            'changed_at': fields.Datetime.now(),
            'notes': note or _("Changed on the contract screen"),
        })

    # =================================================================
    # 2.3 — the same judgement, nothing written
    # =================================================================
    @api.model
    def preview_contract_360(self, contract_id, terms=None, components=None):
        self._cd_require_read()
        contract = self._cd_contract(contract_id)
        if contract is None:
            return {'ok': False, 'refusals': [], 'accept': 0,
                    'msg': _("That contract is no longer here.")}
        can_write = self._cd_may_write()
        unmask = self._cd_unmask_wage()
        symbol = ((contract.company_id or self.env.company)
                  .currency_id.symbol or '')
        if not can_write:
            return {'ok': True, 'refusals': [], 'accept': 0,
                    'msg': _("You can look at contracts but not change them. "
                             "Ask an HR manager to make this change.")}
        term_vals, plan, refusals = self._cd_judge(
            contract, terms, components, symbol, can_write, unmask)
        accept = (len(term_vals) + len(plan['edits']) + len(plan['adds'])
                  + len(plan['removes']))
        return {'ok': True, 'refusals': refusals, 'accept': accept}

    # =================================================================
    # 2.4 — the picker feed
    # =================================================================
    @api.model
    def lookup_contract_m2o(self, comodel, term='', limit=12):
        self._cd_require_read()
        if comodel not in _M2O_WHITELIST:
            # An open comodel argument is a data-exfiltration hole (§2.4).
            return []
        Model = self.env.get(comodel)
        if Model is None:
            return []
        key = 'name' if 'name' in Model._fields else (
            'display_name' if 'display_name' in Model._fields else None)
        if key is None:
            return []
        domain = []
        if 'company_id' in Model._fields and self.env.companies:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', 'in', self.env.companies.ids)]
        if term:
            domain.append((key, 'ilike', term))
        try:
            records = Model.sudo().search(domain, limit=int(limit or 12))
        except Exception:   # noqa: BLE001
            return []
        return [{'id': record.id, 'label': record.display_name or ''}
                for record in records]
