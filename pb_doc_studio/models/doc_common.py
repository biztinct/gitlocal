# -*- coding: utf-8 -*-
"""Shared tables of the Document studio.

Everything a person reads is written here in English and translated where it
is used (`env._(...)` on the lazy value). Keys are stable identifiers: they
are stored in letter bodies (`${key}`), in "Show only when" rules and in the
page design, so a key is never renamed.
"""
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

#: The language every template's own `body_html` is written in. Odoo keeps the
#: SOURCE value of a translated field in en_US; the studio writes the main
#: wording there and keeps the other languages as separate versions
#: (`pb.doc.version`, ledger DS-1).
MAIN_LANG = 'en_US'

# ------------------------------------------------------------------ kinds
#: Gallery groups, in the order they are shown.
# Keys and labels in two lists: the translation extractor mistakes a key that
# follows a `_lt(...)` call inside the same brackets for a sentence.
KIND_KEYS = ['joining', 'trial', 'contract', 'pay', 'job', 'leaving', 'certificates', 'other']
KINDS = list(zip(KIND_KEYS, [
    _lt('Joining'), _lt('Trial period'), _lt('Contract'), _lt('Pay'),
    _lt('Job changes'), _lt('Leaving'), _lt('Certificates'), _lt('Other'),
]))
#: The same list for a selection field (labels must be plain text there;
#: they are translated as selection labels).
KIND_SELECTION = [
    ('joining', 'Joining'), ('trial', 'Trial period'), ('contract', 'Contract'),
    ('pay', 'Pay'), ('job', 'Job changes'), ('leaving', 'Leaving'),
    ('certificates', 'Certificates'), ('other', 'Other'),
]

#: Which gallery group a letter type belongs to.
TYPE_KIND = {
    'probation_pass': 'trial', 'probation_extend': 'trial',
    'probation_fail': 'trial',
    'incentive': 'pay', 'pay_review': 'pay', 'pay_change': 'pay',
    'pay_scale_raise': 'pay',
    'promotion': 'job', 'transfer': 'job', 'job_change': 'job',
    'experience': 'leaving', 'ff_cover': 'leaving',
    'employment_cert': 'certificates', 'salary_cert': 'certificates',
    'pip': 'other', 'custom': 'other',
}

#: Templates shipped by these modules belong to this group whatever their type
#: (the contract extension / permanent letters are type `custom`).
MODULE_KIND = {'pb_contract_lifecycle': 'contract'}

#: Letter types the studio does not offer yet. Offer letters are rendered by
#: Hiring itself, not by the letter engine (FACTS §1 callers), so wording made
#: here would not reach them — wave 2 (A1) brings them in.
NOT_HERE_YET = ('offer',)

#: Letter types whose caller chooses the language itself (certificates: the
#: employee asks for one in a language). The studio keeps that choice.
CALLER_CHOOSES_LANG = ('employment_cert', 'salary_cert')

# ------------------------------------------------------------------ fields
#: Group order of the field list.
FIELD_GROUPS = list(zip(['employee', 'job', 'contract', 'company', 'dates', 'document', 'own'], [
    _lt('Employee'), _lt('Job'), _lt('Contract'), _lt('Company'), _lt('Dates'),
    _lt('This document'), _lt('Your own fields'),
]))

#: (key, label, group, pay). The first seven are the letter engine's own
#: placeholders (`pb_lifecycle/models/letter.py` PLACEHOLDERS) and keep working
#: forever; the rest are resolved by this module.
GENERIC_FIELDS = [
    ('employee_name', _lt('Full name'), 'employee', False),
    ('legal_name', _lt('Legal name'), 'employee', False),
    ('employee_code', _lt('Employee code'), 'employee', False),
    ('work_email', _lt('Work email'), 'employee', False),
    ('country_of_work', _lt('Country of work'), 'employee', False),
    ('job_title', _lt('Job title'), 'job', False),
    ('department', _lt('Department'), 'job', False),
    ('manager_name', _lt('Manager'), 'job', False),
    ('work_location', _lt('Work location'), 'job', False),
    ('contract_start', _lt('Contract start'), 'contract', False),
    ('contract_end', _lt('Contract end'), 'contract', False),
    ('contract_type', _lt('Contract type'), 'contract', False),
    ('monthly_pay', _lt('Monthly pay'), 'contract', True),
    ('company', _lt('Company name'), 'company', False),
    ('company_address', _lt('Company address'), 'company', False),
    ('today_long', _lt("Today's date"), 'dates', False),
    ('joining_date_long', _lt('Joining date'), 'dates', False),
    ('date', _lt("Today's date (2026-11-22 style)"), 'dates', False),
    ('joining_date', _lt('Joining date (2026-11-22 style)'), 'dates', False),
    ('extra', _lt('Extra wording given when the letter is made'), 'document', False),
]
BASE_KEYS = ('employee_name', 'job_title', 'department', 'company', 'date',
             'joining_date', 'extra')
#: Keys this module works out (the letter engine does not know them).
NEW_KEYS = tuple(k for k, _l, _g, _p in GENERIC_FIELDS if k not in BASE_KEYS)

_PROBATION = [
    ('strengths', _lt('What went well'), False),
    ('improvements', _lt('What to improve'), False),
    ('trial_end', _lt('Trial period end date'), False),
    ('new_trial_end', _lt('New trial period end date'), False),
]
_JOB = [
    ('effective_date', _lt('Effective date'), False),
    ('changes', _lt('What changes'), False),
    ('pay_line', _lt('Pay line'), True),
    ('reason', _lt('Reason'), False),
]
_PAY = [
    ('old_pay', _lt('Pay before'), True),
    ('new_pay', _lt('New pay'), True),
    ('increase_pct', _lt('Increase in percent'), True),
    ('effective_date', _lt('Effective date'), False),
    ('reason', _lt('Reason'), False),
]
_CERT = [
    ('certificate_no', _lt('Certificate number'), False),
    ('purpose', _lt('Purpose'), False),
]

#: "This document" fields: what each caller hands the letter when it makes it
#: (FACTS §1 callers table, "Extra keys"). Filled in when the letter is made,
#: never by this module. Other modules add theirs with `_pbds_type_fields`.
TYPE_FIELDS = {
    'probation_pass': _PROBATION,
    'probation_extend': _PROBATION,
    'probation_fail': _PROBATION,
    'promotion': _JOB,
    'transfer': _JOB,
    'job_change': _JOB,
    'pay_review': _PAY,
    'pay_change': _PAY,
    'pay_scale_raise': _PAY + [
        ('scale', _lt('Pay scale'), False),
        ('grade', _lt('Grade'), False),
        ('step', _lt('Step'), False),
    ],
    'incentive': [],
    'pip': [
        ('plan_start', _lt('Plan start date'), False),
        ('plan_end', _lt('Plan end date'), False),
        ('objectives', _lt('Objectives'), False),
        ('checkin_freq', _lt('How often you meet'), False),
        ('hr_owner', _lt('HR contact'), False),
    ],
    'experience': [
        ('last_working_day', _lt('Last working day'), False),
    ],
    'ff_cover': [
        ('last_working_day', _lt('Last working day'), False),
        ('settlement_date', _lt('Settlement date'), False),
        ('net_payable', _lt('Net amount payable'), True),
        ('total_earnings', _lt('Total earnings'), True),
        ('total_deductions', _lt('Total deductions'), True),
    ],
    'employment_cert': _CERT,
    'salary_cert': _CERT + [('salary', _lt('Salary'), True)],
}
#: Contract letters are type `custom`; they are recognised by their group.
KIND_FIELDS = {
    'contract': [
        ('new_start', _lt('New start date'), False),
        ('new_end', _lt('New end date'), False),
    ],
}

# ------------------------------------------------------------------ rules
#: Operators per value type. Fixed table: rules compare typed values, nothing
#: is ever evaluated (rail R2).
OPS = {
    'choice': ('is', 'is_not', 'in', 'empty', 'filled'),
    'text': ('is', 'is_not', 'in', 'empty', 'filled'),
    'number': ('is', 'is_not', 'gt', 'lt', 'empty', 'filled'),
    'date': ('is', 'is_not', 'gt', 'lt', 'empty', 'filled'),
    'bool': ('is',),
}
OP_LABELS = {
    'is': _lt('is'),
    'is_not': _lt('is not'),
    'in': _lt('is one of'),
    'empty': _lt('is empty'),
    'filled': _lt('is filled in'),
    'gt': _lt('is more than'),
    'lt': _lt('is less than'),
}
DATE_OP_LABELS = {'gt': _lt('is after'), 'lt': _lt('is before')}

# ------------------------------------------------------------------ page
# key, label, (top, bottom, left, right) in mm
MARGINS = list(zip(['normal', 'narrow', 'wide'],
                   [_lt('Normal'), _lt('Narrow'), _lt('Wide')],
                   [(40, 28, 20, 20), (32, 22, 12, 12), (46, 32, 30, 30)]))
MARGIN_KEYS = [m[0] for m in MARGINS]

#: Fonts that exist on the printing server WITH Vietnamese letters: Roboto,
#: Open Sans and Montserrat ship with the web client (`web/static/fonts/
#: google`, declared in `web.report_assets_common`); DejaVu is the system
#: font every fontconfig install carries (and the payslip fonts,
#: `pb_hr_payroll_formula/static/fonts/dejavu`).
FONTS = list(zip(
    ['clean', 'friendly', 'classic', 'modern'],
    [_lt('Clean'), _lt('Friendly'), _lt('Classic serif'), _lt('Modern')],
    ["Roboto, 'DejaVu Sans', Arial, sans-serif",
     "'Open_Sans', 'Open Sans', 'DejaVu Sans', Arial, sans-serif",
     "'DejaVu Serif', 'Noto Serif', Georgia, 'Times New Roman', serif",
     "Montserrat, 'DejaVu Sans', Arial, sans-serif"],
))
FONT_KEYS = [f[0] for f in FONTS]
SIZES = (10, 11, 12, 13, 14)
SIGNS = list(zip(['off', 'text', 'image'], [
    _lt('No signature block'), _lt('Name and title'), _lt('With a signature image'),
]))
SIGN_KEYS = [s[0] for s in SIGNS]

#: The page every letter printed before this module had: the company
#: letterhead, the default paper, 13 px text and the "Authorised signatory"
#: block (`pb_lifecycle/report/hr_letter_report.xml`). A document opened in the
#: studio starts from it, so the first save prints what it printed before.
DEFAULT_PAGE = {
    'letterhead': True,
    'margins': 'normal',
    'font': 'clean',
    'size': 13,
    'sign': 'text',
    'sign_name': '',
    'sign_title': '',
}

#: Body size guard (rail R7 speaks of ~200 KB; refuse well above it).
MAX_BODY = 600 * 1024
#: Pictures added to a letter.
IMAGE_MIMES = ('image/png', 'image/jpeg', 'image/webp', 'image/gif')
IMAGE_MAX = 4 * 1024 * 1024
IMAGE_MARKER = 'pb_doc_studio:image'
