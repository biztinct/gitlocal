# -*- coding: utf-8 -*-
"""What a tax detail is, per country — the one table every part reads.

Sources (published rules, checked 2026-11-18; see the S2-D report):

* Vietnam — personal tax code: 10 digits (Circular 105/2020/TT-BTC); from
  1 July 2025 the 12-digit personal identification number on the chip ID card
  is used as the personal tax code (Circular 86/2024/TT-BTC, art. 35).
* Indonesia — NPWP: 15 digits, or the 16-digit NIK used as NPWP for residents
  (PMK 112/PMK.03/2022). PTKP status TK/K/K-I with 0-3 dependants
  (UU PPh art. 7; PMK 101/PMK.010/2016; PER-16/PJ/2016).
* India — PAN: 5 letters, 4 digits, 1 letter (Income-tax Rules, rule 114);
  tax regime new (default) or old, chosen by the employee each year
  (Income-tax Act s. 115BAC, CBDT Circular 04/2023).
* Singapore — self-help group funds CDAC, ECF, MBMF, SINDA, collected with CPF
  through payroll; an employee may opt out (CPF Board, "Self-Help Groups").

Nothing here is read by a payslip. A pay scheme can read an approved detail
only through the application sources in `formula_sources.py`, and no scheme
reads one until somebody maps it.
"""

import re

#: Countries My Payobook shows tax details for (owner ruling G1).
SUPPORTED = ('VN', 'ID', 'IN', 'SG')

#: The kinds of request this module adds to `pb.me.detail.request`.
TAX_KINDS = ('tax_number', 'tax_status', 'tax_regime', 'tax_fund')
KIND_SELECTION = [
    ('tax_number', 'Tax number'),
    ('tax_status', 'PTKP status'),
    ('tax_regime', 'Tax regime'),
    ('tax_fund', 'Self-help group fund'),
]

#: Which kinds a person may ask for, by the country of the scheme that pays
#: them.
KINDS_BY_COUNTRY = {
    'VN': ('tax_number',),
    'ID': ('tax_number', 'tax_status'),
    'IN': ('tax_number', 'tax_regime'),
    'SG': ('tax_fund',),
}

#: A proof file is required for these (handover S2-D item 3).
PROOF_REQUIRED = ('tax_number', 'tax_status', 'tax_regime')

#: The employee field each tax number is kept in (existing fields first).
NUMBER_FIELD = {
    'VN': 'vietnam_tax_code',        # pb_hr_payroll_vietnam
    'ID': 'pb_npwp_number',          # pb_employee_vault
    'IN': 'pb_in_pan_number',        # this module
}

#: (kind, country) -> the employee field a choice is kept in.
CHOICE_FIELD = {
    ('tax_status', 'ID'): 'pb_id_ptkp_status',
    ('tax_regime', 'IN'): 'pb_in_tax_regime',
    ('tax_fund', 'SG'): 'pb_sg_shg_fund',
}

#: The request field that carries the proposed choice, per kind.
REQUEST_FIELD = {
    'tax_status': 't_ptkp',
    'tax_regime': 't_regime',
    'tax_fund': 't_fund',
}

PTKP = [
    ('TK/0', 'TK/0 · Not married, no dependants'),
    ('TK/1', 'TK/1 · Not married, 1 dependant'),
    ('TK/2', 'TK/2 · Not married, 2 dependants'),
    ('TK/3', 'TK/3 · Not married, 3 dependants'),
    ('K/0', 'K/0 · Married, no dependants'),
    ('K/1', 'K/1 · Married, 1 dependant'),
    ('K/2', 'K/2 · Married, 2 dependants'),
    ('K/3', 'K/3 · Married, 3 dependants'),
    ('K/I/0', "K/I/0 · Married, spouse's income added, no dependants"),
    ('K/I/1', "K/I/1 · Married, spouse's income added, 1 dependant"),
    ('K/I/2', "K/I/2 · Married, spouse's income added, 2 dependants"),
    ('K/I/3', "K/I/3 · Married, spouse's income added, 3 dependants"),
]

REGIMES = [
    ('new', 'New tax regime'),
    ('old', 'Old tax regime'),
]

SG_FUNDS = [
    ('cdac', 'CDAC (Chinese Development Assistance Council)'),
    ('ecf', 'ECF (Eurasian Community Fund)'),
    ('mbmf', 'MBMF (Mosque Building and Mendaki Fund)'),
    ('sinda', 'SINDA (Singapore Indian Development Association)'),
    ('none', 'I do not give to a self-help group fund'),
]

SG_RESIDENCY = [
    ('resident', 'Tax resident'),
    ('non_resident', 'Not a tax resident'),
]

_SEPARATORS = re.compile(r'[\s.\-/]')
_PAN = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')


def normalise_number(country, raw):
    """`(value, problem)` — the number as it is kept, or the reason it is
    not a valid number for that country (`problem` is a key, the caller
    words it)."""
    text = _SEPARATORS.sub('', str(raw or '')).upper()
    if not text:
        return '', 'empty'
    if country == 'VN':
        return (text, None) if text.isdigit() and len(text) in (10, 12) \
            else (text, 'vn')
    if country == 'ID':
        return (text, None) if text.isdigit() and len(text) in (15, 16) \
            else (text, 'id')
    if country == 'IN':
        return (text, None) if _PAN.match(text) else (text, 'in')
    return text, 'country'


def mask(text):
    """The last four characters only (S2-D item 2)."""
    text = str(text or '').strip()
    if len(text) <= 4:
        return text
    return '•••• ' + text[-4:]
