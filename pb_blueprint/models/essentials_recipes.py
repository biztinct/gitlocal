# -*- coding: utf-8 -*-
"""The Vietnam - Essentials starter, written as sentences.

The starter already works: 37 components, a seven-band tax table and a
certification suite that passes. What it did not have was any account of WHY
each component is what it is — so on the Pay rules step every row read "Written
as Excel" and the guided editor had nothing to show.

This file supplies the missing half. Each component gets the sentence it always
implied, and the compiler regenerates the formula from it. The whole point is
that the regenerated formulas produce the SAME NUMBERS: the starter's own
certification tests are the proof, and they are run in the test suite before
and after the backfill.

Two deliberate choices:

* ``round`` is ``none`` throughout. The starter's arithmetic is exact and its
  certification expectations were computed from it; introducing rounding here
  would move numbers by up to half a dong for no reason a person asked for.
  New components a person adds DO round, because a payslip line with six
  decimal places is not a payslip line.
* the hourly-rate and overtime components stay ``manual``. Their Excel is
  correct, short and readable, and the guided sentence for "hours x rate" is
  built for ONE overtime component, not for a single line that folds three
  multipliers together. Their recipes record what they ARE — a helper and a
  cash earning — so the totals still know where to put them.
"""

#: group / audience / amount / proration / frequency / sign / round / treatment
#: for every component of `vn_standard_2026`, keyed by code.
ESSENTIALS_TEMPLATE_KEY = 'vn_standard_2026'


def _earning(kind, **amount):
    return {
        'group': 'earning',
        'amount': dict(amount, kind=kind),
        'treatment': {'cash': 'cash', 'tax': 'taxable', 'insurance': 'excluded'},
    }


def _helper(kind='manual', **amount):
    return {
        'group': 'helper',
        'amount': dict(amount, kind=kind),
        'treatment': {'cash': 'cash', 'tax': 'exempt', 'insurance': 'excluded'},
    }


def _total(kind, **amount):
    return {
        'group': 'total',
        'amount': dict(amount, kind=kind),
        'treatment': {'cash': 'cash', 'tax': 'exempt', 'insurance': 'excluded'},
    }


def _deduction(kind, pit_deductible='no', is_income_tax=False, **amount):
    return {
        'group': 'deduction',
        'amount': dict(amount, kind=kind),
        'treatment': {'cash': 'cash', 'tax': 'exempt', 'insurance': 'excluded',
                      'pit_deductible': pit_deductible,
                      'is_income_tax': is_income_tax},
    }


def _benefit(kind, **amount):
    return {
        'group': 'benefit',
        'amount': dict(amount, kind=kind),
        'treatment': {'cash': 'cash', 'tax': 'exempt', 'insurance': 'excluded',
                      'employer_share_pct': 100.0},
    }


def _base():
    return {
        'v': 1, 'audience': 'all', 'proration': 'none',
        'frequency': 'monthly', 'sign': 1, 'round': 'none',
    }


def essentials_recipes():
    """``{code: recipe}`` for the Vietnam - Essentials starter."""
    out = {}

    def add(code, recipe):
        merged = _base()
        merged.update(recipe)
        out[code] = merged

    # ---- what a person is paid --------------------------------------
    basic = _earning('input')
    basic['treatment']['insurance'] = 'included'
    add('BASIC', basic)
    add('BONUS', _earning('input'))
    add('ALLOWIN', _earning('input'))
    add('OTPAY', _earning('manual'))

    # ---- the numbers the run is given --------------------------------
    for code in ('DEPS', 'STDDAYS', 'OTHRS15', 'OTHRS20', 'OTHRS30'):
        add(code, _helper('input'))
    for code in ('DEDUCTSELF', 'DEDUCTDEP', 'SIRATE', 'HIRATE', 'UIRATE',
                 'SIEMPR', 'HIEMPR', 'UIEMPR', 'CAPLO', 'CAPHI',
                 'MULT15', 'MULT20', 'MULT30'):
        add(code, _helper('manual'))
    add('HOURRATE', _helper('manual'))

    # ---- the totals everything feeds ---------------------------------
    add('GROSS', _total('sum_group', of={'group': 'earning', 'cash': 'cash'}))
    add('SIBASE', _total('insurance_base', cap='CAPLO'))
    add('UIBASE', _total('insurance_base', cap='CAPHI'))
    add('EEDED', _total('sum_group',
                        of={'group': 'deduction', 'income_tax': 'exclude'}))
    add('TAXABLE', _total('taxable_base', relief_self='DEDUCTSELF',
                          relief_dep='DEDUCTDEP', deps='DEPS'))
    add('NET', _total('net_total'))
    add('ERCOST', _total('employer_total'))

    # ---- what comes off ----------------------------------------------
    add('SIDED', _deduction('percent_of', pit_deductible='yes',
                            base='SIBASE', rate_code='SIRATE'))
    add('HIDED', _deduction('percent_of', pit_deductible='yes',
                            base='SIBASE', rate_code='HIRATE'))
    add('UIDED', _deduction('percent_of', pit_deductible='yes',
                            base='UIBASE', rate_code='UIRATE'))
    add('PIT', _deduction('bracket', is_income_tax=True,
                          table='VNTAX', base='TAXABLE'))

    # ---- what the employer pays on top --------------------------------
    add('SICOMP', _benefit('percent_of', base='SIBASE', rate_code='SIEMPR'))
    add('HICOMP', _benefit('percent_of', base='SIBASE', rate_code='HIEMPR'))
    add('UICOMP', _benefit('percent_of', base='UIBASE', rate_code='UIEMPR'))
    return out


ESSENTIALS_RECIPES = essentials_recipes()
