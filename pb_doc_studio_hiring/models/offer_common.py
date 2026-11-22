# -*- coding: utf-8 -*-
"""Shared tables of offer letters in the Document studio.

Keys are the offer's own placeholders (`pb_hiring/models/offer.py`
`_placeholder_values` + `${lines}`): they are already written in every offer
letter a company has, so they are never renamed. Keys and labels live in
separate lists (ledger DS-5: the translation extractor mistakes a key that
follows a `_lt(...)` call inside the same brackets for a sentence).
"""
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

#: The letter type Hiring adds to the letter library.
OFFER = 'offer'
#: The gallery group of offer letters (`pb.letter.template.pbds_kind`).
HIRING = 'hiring'
#: Context key the facade sets while it works on an offer document: the
#: "Show only when" conditions are then the offer's ones. Never a security
#: decision (rules only choose paragraphs of a wording the caller may edit).
KIND_CTX = 'pbds_doc_kind'

#: Field groups of an offer letter, in the order the designer lists them.
GROUP_KEYS = ['candidate', 'job', 'company', 'pay', 'dates', 'document']
GROUP_LABELS = [_lt('Candidate'), _lt('Job'), _lt('Company'), _lt('Pay'),
                _lt('Dates'), _lt('This document')]

#: (key, group) of every field an offer letter can print, with its label in
#: the list below (same order).
FIELD_KEYS = [
    ('candidate_name', 'candidate'),
    ('job_title', 'job'),
    ('department', 'job'),
    ('location', 'job'),
    ('manager', 'job'),
    ('company', 'company'),
    ('monthly_total', 'pay'),
    ('annual_total', 'pay'),
    ('currency', 'pay'),
    ('lines', 'pay'),
    ('start_date', 'dates'),
    ('date', 'dates'),
]
FIELD_LABELS = [
    _lt('Candidate name'),
    _lt('Job title'),
    _lt('Department'),
    _lt('Where they will be based'),
    _lt('Who they will report to'),
    _lt('Company name'),
    _lt('Monthly total'),
    _lt('Yearly total'),
    _lt('Currency'),
    _lt('Pay lines table'),
    _lt('Start date'),
    _lt("Today's date"),
]
#: Fields that are a whole block on the page, never a word in a sentence.
BLOCK_KEYS = ('lines',)

#: "Show only when" conditions an offer can use: the employee conditions of
#: the studio that mean something for a role, relabelled for an offer.
COND_KEYS = ['country_of_work', 'company', 'department', 'job', 'contract_type']
COND_LABELS = [_lt('Country'), _lt('Company'), _lt('Department'), _lt('Job position'),
               _lt('Employment type')]
