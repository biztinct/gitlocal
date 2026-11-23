# -*- coding: utf-8 -*-
"""Shared tables of the employment contract documents.

Keys are stable identifiers stored in wording (`${key}`), in "Show only
when" rules and in the panel's chips: a key is never renamed. Labels are
written in English and translated where they are used (`env._(...)`).
Keys and labels sit in separate lists (ledger DS-5: the translation
extractor mistakes a key that follows a `_lt(...)` call for a sentence).
"""
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

#: The document kind ("letter type") this module adds to letter templates
#: ONLY (`selection_add` on `pb.hr.letter.letter_type` breaks the registry,
#: FACTS §1).
CONTRACT_TYPE = 'employment_contract'

#: The gallery group of employment contracts. The studio's own "Contract"
#: group holds the extension / make-permanent letters; this one is named in
#: full so the two never read alike.
CONTRACT_KIND = 'employment'

#: The vault category a saved contract is filed under.
VAULT_CATEGORY = 'pb_employee_vault.cat_labor_contract'

#: Shipped wording (data, noupdate). xml id -> what "Put back the built-in
#: wording" restores besides the words (the studio's own reset clears rules,
#: page and main language; the shipped "Show only when" paragraphs need
#: their rules back).
SHIPPED = {
    'pb_doc_contracts.contract_template_generic': {'main_lang': False},
    'pb_doc_contracts.contract_template_vn': {'main_lang': 'vi_VN'},
    'pb_doc_contracts.contract_template_id': {'main_lang': 'id_ID'},
}

#: The rules every shipped contract uses, by the id written in its wording
#: (`pbds-r-<id>`). Kept identical to the data file (a test compares them).
SHIPPED_RULES = {
    'rfixed': {'match': 'all', 'lines': [
        {'field': 'contract_term', 'op': 'is', 'value': 'fixed'}]},
    'ropen': {'match': 'all', 'lines': [
        {'field': 'contract_term', 'op': 'is', 'value': 'open'}]},
    'rtrial': {'match': 'all', 'lines': [
        {'field': 'trial_end', 'op': 'filled', 'value': None}]},
}

#: The page every shipped contract starts with: the letterhead, normal
#: margins, and NO signature block of the page — both parties sign in the
#: wording itself (a two-column table, editable like any other words).
#: Font "classic" (DejaVu Serif, a system font on the PDF server): the
#: web font of "clean" (Roboto) is fetched by the PDF engine and, when it
#: arrives late, bold labels are laid out with one font and drawn with
#: another (overlapping words after "The employer:"). A system font prints
#: the same every time, with every Vietnamese letter.
SHIPPED_PAGE = {
    'letterhead': True, 'margins': 'normal', 'font': 'classic', 'size': 11,
    'sign': 'off', 'sign_name': '', 'sign_title': '',
}

# ------------------------------------------------------------------ fields
#: "This document" fields of an employment contract, in list order:
#: (key, pay). Labels below, same order.
CONTRACT_FIELD_KEYS = [
    ('contract_ref', False),
    ('contract_end_text', False),
    ('trial_end', False),
    ('start_dmy', False),
    ('end_dmy', False),
    ('trial_end_dmy', False),
    ('today_dmy', False),
    ('working_schedule', False),
    ('weekly_hours', False),
    ('contract_job', False),
    ('contract_department', False),
    ('contract_location', False),
    ('pay_currency', False),
    ('pay_scheme', False),
    ('employer_rep', False),
    ('employer_rep_title', False),
    ('id_number', False),
    ('passport_number', False),
    ('home_address', False),
    ('birthday', False),
    ('birthday_dmy', False),
    ('nationality', False),
]
CONTRACT_FIELD_LABELS = [
    _lt('Contract reference'),
    _lt('End date, or "no end date"'),
    _lt('Trial period end date'),
    _lt('Start date (22/11/2026 style)'),
    _lt('End date (22/11/2026 style)'),
    _lt('Trial period end date (22/11/2026 style)'),
    _lt("Today's date (22/11/2026 style)"),
    _lt('Working schedule'),
    _lt('Hours per week'),
    _lt('Job on the contract'),
    _lt('Department on the contract'),
    _lt('Place of work'),
    _lt('Pay currency'),
    _lt('Pay scheme'),
    _lt('Employer representative'),
    _lt("Employer representative's title"),
    _lt('ID number'),
    _lt('Passport number'),
    _lt('Home address'),
    _lt('Date of birth'),
    _lt('Date of birth (22/11/2026 style)'),
    _lt('Nationality'),
]
CONTRACT_FIELDS = [(k, label, pay) for (k, pay), label in zip(CONTRACT_FIELD_KEYS, CONTRACT_FIELD_LABELS)]
CONTRACT_KEYS = tuple(k for k, _p in CONTRACT_FIELD_KEYS)

#: Where a value is changed, for the panel's amber chips: a term of the
#: contract panel (`pb_contracts` `_TERMS` field name) or the person.
#: Studio keys that read the contract are listed too.
JUMP = {
    'trial_end': ('term', 'trial_date_end'),
    'trial_end_dmy': ('term', 'trial_date_end'),
    'start_dmy': ('term', 'date_start'),
    'contract_start': ('term', 'date_start'),
    'end_dmy': ('term', 'date_end'),
    'contract_end': ('term', 'date_end'),
    'working_schedule': ('term', 'resource_calendar_id'),
    'weekly_hours': ('term', 'resource_calendar_id'),
    'contract_job': ('term', 'job_id'),
    'contract_department': ('term', 'department_id'),
    'contract_location': ('term', 'location'),
    'pay_scheme': ('term', 'struct_id'),
    'monthly_pay': ('term', 'wage'),
    'id_number': ('employee', None),
    'passport_number': ('employee', None),
    'home_address': ('employee', None),
    'birthday': ('employee', None),
    'birthday_dmy': ('employee', None),
    'nationality': ('employee', None),
    'manager_name': ('employee', None),
    'legal_name': ('employee', None),
    'employee_code': ('employee', None),
    'work_email': ('employee', None),
    'work_location': ('employee', None),
    'job_title': ('employee', None),
    'department': ('employee', None),
    'country_of_work': ('employee', None),
}
#: Rule fields -> where the fact behind them is changed.
RULE_JUMP = {
    'contract_term': ('term', 'date_end'),
    'trial_end': ('term', 'trial_date_end'),
    'contract_type': None,
    'pay_band': ('term', 'pb_band_id'),
}

# ------------------------------------------------------------------ rules
#: Conditions this module adds to "Show only when" (every document may use
#: them; they read the contract the document is made for).
TERM_VALUES = ['fixed', 'open']
TERM_LABELS = [_lt('Fixed term (has an end date)'), _lt('Open-ended (no end date)')]
