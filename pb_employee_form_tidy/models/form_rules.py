# -*- coding: utf-8 -*-
"""TIDY-E — which employee "Full details" boxes show, and to whom.

The table below is the FIELD AUDIT's verdict per box (2026-11-19,
`docs/handovers/formstudio/FIELD_AUDIT_FACTS.md`), as ruled by the owner
(FORMSTUDIO ledger R11/R12):

* ``REMOVE`` — the box leaves the employee form for everyone. The FIELD stays
  (column, values, import mappings, formula sources): this is screen-only.
  The 26 unused boxes, the 5 the audit was unsure about, and the old
  "Account Number" box (Payroll-ready now reads the approved bank account).
* a country code — the box shows only when the person's Country of Work
  (`hr.employee.payroll_country`) is that country. A person with no Country of
  Work sees no country box at all.

Everything not named here is untouched. The rules are applied to the combined
arch of `hr.view_employee_form` in `hr.employee._get_view` (see
`hr_employee.py`), not by one XML xpath per owning view: eight modules put
these boxes on the form and two of them (`pb_me_tax`,
`pb_payroll_mapping_vn`) are not installed on every database, so a fixed
xpath would fail to install where the box does not exist. A rule whose box is
absent simply does nothing.

Sections (groups, divs, pages) whose every box ends up hidden are hidden too —
for everyone when all their boxes are removed, or by the same country rule when
all their remaining boxes belong to one country.
"""

import ast

from lxml import etree

REMOVE = 'remove'

#: field name -> REMOVE or the ISO code of its Country of Work.
FORM_RULES = {
    # ---- Work tab › Location (pb_training) — required-training facts
    'pb_safety_group': 'VN',
    'pb_posh_ic_member': 'IN',
    'pb_sg_experienced': 'SG',

    # ---- Payroll Info (pb_hr_payroll_formula)
    'overtime_status': 'VN',
    'fire_prevention_officer': 'VN',
    'tham_gia_bhxh': 'VN',
    'subject_to_pit': 'VN',
    'insurance_code': 'VN',
    'level_of_health_compensation': REMOVE,
    'trade_union_participation': REMOVE,
    'funeral_fund_participation': REMOVE,
    'female_excluding_pregnant': REMOVE,
    'osh_worker_code': REMOVE,
    'trade_union_fee_code': REMOVE,
    'basic_overtime_electricity': REMOVE,
    'bd_phsk': REMOVE,
    'deduction_of_funeral_money': REMOVE,
    'different_subjects': REMOVE,
    'legal_entity_pays_salary': REMOVE,
    # R12: Payroll-ready reads the approved bank account; this box is not it.
    'account_number': REMOVE,

    # ---- Employment profile (pb_employee_vault)
    'pb_position_reference': REMOVE,          # audit: unsure -> owner: remove
    'pb_emergency_relationship': REMOVE,      # audit: unsure -> owner: remove
    'pb_npwp_number': 'ID',
    'pb_family_card_number': 'ID',
    'pb_bpjs_employment_number': 'ID',
    'pb_bpjs_health_number': 'ID',

    # ---- Tax details (pb_me_tax)
    'pb_vn_dependants_check': 'VN',
    'pb_id_ptkp_status': 'ID',
    'pb_in_pan_number': 'IN',
    'pb_in_tax_regime': 'IN',
    'pb_in_uan_number': 'IN',
    'pb_in_esi_number': 'IN',
    'pb_sg_tax_residency': 'SG',
    'pb_sg_shg_fund': 'SG',

    # ---- Insurance (BH) (pb_hr_payroll_vietnam)
    # The summary is a kept box, but it is Vietnam's: it already shows only
    # for Vietnam staff, and the rule lets the tab close for everyone else.
    'vn_payroll_insurance_summary': 'VN',
    'vn_insurance_policy_id': 'VN',
    'vn_work_region': 'VN',
    'vn_exempt_oa_od': 'VN',
    'vn_si_enrolled': 'VN',
    'vn_si_enrollment_status': 'VN',
    'vn_si_salary_base': 'VN',
    'vn_hi_enrolled': 'VN',
    'vn_hi_salary_base': 'VN',
    'vn_ui_enrolled': 'VN',
    'vn_ui_salary_base': 'VN',
    'vn_foreign_insurance_exempt': REMOVE,
    'vn_si_number': REMOVE,
    'vn_si_effective_date': REMOVE,
    'vn_hi_number': REMOVE,
    'vn_hi_effective_date': REMOVE,
    'vn_ui_number': REMOVE,
    'vn_ui_effective_date': REMOVE,
    'vn_employer_insurance_cost': REMOVE,
    'vn_employee_insurance_cost': REMOVE,
    'vn_total_insurance_contribution': REMOVE,

    # ---- Tax & Dependents (pb_hr_payroll_vietnam)
    'vn_payroll_tax_summary': 'VN',
    'vn_tax_regime': 'VN',
    'vn_residency_status': 'VN',
    'vn_dependent_record_count': 'VN',
    'vn_eligible_dependent_count': 'VN',
    'vn_dependent_ids': 'VN',
    'vn_tax_table_id': REMOVE,
    'vn_tax_effective_date': REMOVE,
    'vn_personal_tax_rate': REMOVE,
    'vn_monthly_tax_allowance': REMOVE,
    'vn_dependent_tax_allowance': REMOVE,

    # ---- Payroll facts (pb_payroll_mapping_vn; rize only)
    'pb_vn_is_local': 'VN',
    'pb_vn_tax_resident': 'VN',
    'pb_vn_tax_commitment': 'VN',
    'pb_vn_in_insurance': 'VN',
    'pb_vn_union_member': 'VN',
    'pb_vn_enrol_family_health': REMOVE,      # audit: unsure -> owner: remove
    'pb_vn_enrol_private_health': REMOVE,     # audit: unsure -> owner: remove
    'pb_vn_enrol_dep_health': REMOVE,         # audit: unsure -> owner: remove
}

#: the field the country rules read (stored Selection on hr.employee).
COUNTRY_FIELD = 'payroll_country'

#: elements that only group other elements: hidden when all they hold is hidden.
_CONTAINERS = ('group', 'div', 'page', 'span', 'p', 'h1', 'h2', 'h3', 'h4',
               'h5', 'h6', 'strong', 'b', 'section')

#: never a box, never a reason to keep a section open
_DECOR = ('separator', 'newline', 'br', 'i', 'img', 'hr', 'a')
#: not a box, but something a person can press: its section stays
_ACTIVE = ('button', 'widget', 'label')

# per-node verdicts while walking the arch
_IGNORE = 'ignore'        # nothing that is a box (text, a helper field, a button…)
_SHOWN = 'shown'          # holds at least one box this phase does not hide
_ALWAYS = 'always'        # every box inside is removed


def country_expr(code):
    """The `invisible` expression of a box that belongs to one country."""
    return "%s != '%s'" % (COUNTRY_FIELD, code)


def _or(old, new):
    old = (old or '').strip()
    if not old or old in ('0', 'False', 'false'):
        return new
    if old in ('1', 'True', 'true'):
        return old
    if new in ('1', 'True'):
        return new
    return '(%s) or (%s)' % (old, new)


def _is_static_hidden(node):
    return (node.get('invisible') or '').strip() in ('1', 'True', 'true')


def _walk(node, changed):
    """Apply the rules under ``node``; return its verdict.

    A verdict is `_IGNORE`, `_SHOWN`, `_ALWAYS` or a country code. Fields are
    leaves: a field's own sub-view (an x2many list) belongs to another model
    and is never walked.
    """
    tag = node.tag if isinstance(node.tag, str) else ''
    if tag == 'field':
        name = node.get('name')
        rule = FORM_RULES.get(name)
        if rule == REMOVE:
            node.set('invisible', '1')
            changed.append(name)
            return _ALWAYS
        if rule:
            node.set('invisible', _or(node.get('invisible'), country_expr(rule)))
            changed.append(name)
            return rule
        if _is_static_hidden(node):
            return _IGNORE          # a helper the form needs, never a box
        return _SHOWN
    if tag == 'label' and node.get('for'):
        return _IGNORE              # follows its field (see apply_rules)
    if not tag or tag in _DECOR:
        return _IGNORE
    if tag in _ACTIVE:
        return _SHOWN               # a button or widget keeps its section
    verdicts = [_walk(child, changed) for child in node]
    if tag not in _CONTAINERS:
        # sheet, notebook, …: walked, never hidden
        return _SHOWN if any(v != _IGNORE for v in verdicts) else _IGNORE
    if _is_static_hidden(node):
        return _IGNORE
    kinds = {v for v in verdicts if v != _IGNORE}
    if not kinds or _SHOWN in kinds:
        return _SHOWN if kinds else _IGNORE
    countries = kinds - {_ALWAYS}
    if not countries:
        node.set('invisible', '1')
        return _ALWAYS
    if len(countries) == 1:
        code = next(iter(countries))
        node.set('invisible', _or(node.get('invisible'), country_expr(code)))
        return code
    return _SHOWN                   # several countries: each box decides


def apply_rules(arch):
    """Apply `FORM_RULES` to a combined employee form arch, in place.

    Returns the names of the boxes it touched (for tests and logs).
    """
    changed = []
    sheet = arch.find('.//sheet')
    root = sheet if sheet is not None else arch
    _walk(root, changed)
    # A label written beside its field (`<label for="x"/>`) follows the field.
    for label in arch.iter('label'):
        rule = FORM_RULES.get(label.get('for'))
        if rule == REMOVE:
            label.set('invisible', '1')
        elif rule:
            label.set('invisible', _or(label.get('invisible'), country_expr(rule)))
    return changed


# ---------------------------------------------------------------- dates
_DATE_TYPES = ('date', 'datetime')


def _numeric_options(raw):
    """`options` with `numeric` switched on, or None when it cannot be read."""
    raw = (raw or '').strip()
    if not raw:
        return "{'numeric': True}"
    try:
        opts = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if not isinstance(opts, dict) or 'numeric' in opts:
        return None
    opts['numeric'] = True
    return repr(opts)


def show_full_dates(arch, env, model_name):
    """Every date box on the form shows the year (FIELD AUDIT §5).

    The stock date display drops the year when it is the current one ("May
    11"); `numeric` shows the language's own date format, year included.
    Sub-views (an x2many list) are walked with their own model.
    """
    def walk(node, model):
        for child in node:
            if not isinstance(child.tag, str):
                continue
            if child.tag == 'field':
                field = model._fields.get(child.get('name')) if model is not None else None
                if field is not None and field.type in _DATE_TYPES and not child.get('widget'):
                    opts = _numeric_options(child.get('options'))
                    if opts:
                        child.set('options', opts)
                comodel = env.get(field.comodel_name) if field is not None and \
                    getattr(field, 'comodel_name', None) else None
                walk(child, comodel)
            else:
                walk(child, model)
    walk(arch, env[model_name])
    return arch


def arch_string(arch):
    return etree.tostring(arch, encoding='unicode')
