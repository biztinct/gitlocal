# -*- coding: utf-8 -*-
"""The sentence, as data — version 1.

A *recipe* is the machine-readable form of the plain sentence a person builds
on the Pay rules step: who it is for, how the amount is worked out, whether it
is prorated, how often it is paid, and how tax and insurance treat it. The
compiler turns it into an Excel formula; the client turns it back into English.
Both read this file, so neither can invent a word the other does not know.

Two rules that never bend:

* a recipe refers to components by **code**, never by column letter. Codes are
  what a person sees; letters are frozen plumbing (BP-R4).
* every value is checked HERE, on the server, before anything is written. A
  client that sends a word this file does not know gets a sentence back saying
  which choice was not understood — never a traceback, and never a silent
  default that quietly changes what somebody is paid.
"""
from odoo import _

VERSION = 1

#: Which part of pay a component belongs to. Drives both the group tabs on
#: screen and — far more importantly — which totals it is summed into.
GROUPS = ('earning', 'deduction', 'benefit', 'total', 'helper')

#: Groups whose components are part of every configuration and cannot be
#: switched off: the totals everything else feeds, and the plumbing.
LOCKED_GROUPS = ('total', 'helper')

#: Who the component applies to. ``local_insured`` is two conditions at once —
#: Vietnamese unemployment insurance is for local employees who are in the
#: scheme, and expressing that as one word beats asking somebody to nest two
#: sentences.
AUDIENCES = ('all', 'local', 'foreign', 'insured', 'union', 'enrolled', 'role',
             'local_insured')

#: How the amount is worked out.
KINDS = (
    'input',            # an approved amount typed in or fed from a source
    'fixed',            # the same amount every time
    'contract',         # the contract salary
    'percent_contract',  # a percentage of the contract salary
    'percent_of',       # a percentage of another component
    'role',             # a different amount per grade
    'hourly',           # hours x hourly rate x a percentage
    'annual_ratio',     # a yearly payment, prorated by service
    'linked',           # the same amount as another component
    'sum_group',        # everything in a group, added up
    'bracket',          # a progressive band table
    'insurance_base',   # insurable pay, capped
    'taxable_base',     # income the tax bands are applied to
    'net_total',        # take-home pay
    'employer_total',   # what the employer pays in total
    'pit_vn',           # the Vietnamese income-tax routes, in one component
    'manual',           # written as Excel; the recipe only records what it IS
)

PRORATION = ('none', 'working_days', 'calendar_days')
FREQUENCY = ('monthly', 'annual', 'adhoc', 'scheme')
CASH = ('cash', 'noncash')
TAX = ('taxable', 'exempt', 'qualified', 'annual_cap', 'entitlement', 'inherit')
INSURANCE = ('included', 'excluded', 'inherit', 'review')
BEARER = ('employee', 'employer')
PIT_DEDUCTIBLE = ('no', 'yes', 'source')
#: ``down`` always moves toward zero (``ROUNDDOWN``) — the choice a payroll
#: makes when it must never pay a fraction more than the rule allows.
ROUNDING = ('none', '0', '2', 'down')
#: Which components an insurance base is worked out from. ``actual`` adds up
#: every earning marked as counting; ``contract`` uses the contract salary
#: itself, whatever was actually paid this run.
INSURANCE_BASIS = ('actual', 'contract')
#: How a group sum treats the income-tax component itself.
INCOME_TAX_FILTER = ('any', 'exclude', 'only')

#: The kinds that need a partner value, and what that value is called.
NEEDS = {
    'fixed': ('value',),
    'percent_contract': ('percent',),
    'percent_of': ('base',),
    'role': ('grades',),
    'hourly': ('rate_pct',),
    'annual_ratio': ('payout_month',),
    'linked': ('link',),
    'bracket': ('table', 'base'),
    'pit_vn': ('table', 'base'),
    'insurance_base': ('cap',),
}

#: The helper inputs the Vietnamese income-tax routes need, and the name each
#: one is known by inside a ``pit_vn`` recipe.
PIT_VN_ROUTES = ('nonres_rate', 'short_rate', 'short_threshold',
                 'resident_input', 'months_input', 'commit_input', 'gross_base')

#: The canonical helper inputs the compiler provisions on demand, and the value
#: each one starts at. Their labels live in :func:`helper_label` so that the
#: translation extractor sees a real literal (a module-level ``_()`` runs at
#: import time, before any language is known).
HELPER_INPUTS = {
    'PAIDDAYS': 26.0,
    'STDDAYS': 26.0,
    'MTHDAYS': 30.0,
    'PAIDCALD': 30.0,
    'HOURSDAY': 8.0,
    'PAYMONTH': 1.0,
    'ISLOCAL': 1.0,
    'ISINSURED': 1.0,
    'ISUNION': 1.0,
    'ISRESIDENT': 1.0,
    'CONTRACTMTH': 12.0,
    'TAXCOMMIT': 0.0,
    'ROLEGRADE': 0.0,
    'SERVDAYS': 260.0,
    'ANNUALDAYS': 260.0,
}

#: Per-component helper suffixes and the value each one starts at.
HELPER_SUFFIXES = {
    'IN': 0.0,
    'HRS': 0.0,
    'ENR': 0.0,
    'QUAL': 1.0,
    'YTD': 0.0,
    'ENT': 0.0,
}


#: A recipe may name the input it reads instead of taking the conventional
#: ``<CODE><SUFFIX>`` name. A starter has to: the template registry refuses any
#: code that contains another, so a starter cannot ship ``OTWDHRS`` beside
#: ``OTWD``. On a live configuration the convention is used and nothing changes.
INPUT_SLOTS = {
    'amount': 'IN',
    'hours': 'HRS',
    'enrol': 'ENR',
    'qual': 'QUAL',
    'ytd': 'YTD',
    'ent': 'ENT',
    # "Paid when the scheme says so" is only true if something SAYS so. A rule
    # that names this slot is switched on per run; one that does not is paid
    # every run, exactly as before.
    'run': 'RUN',
}


def slot_code(recipe, slot, self_code):
    """The input code a recipe reads for one slot — named, or conventional."""
    named = ((recipe or {}).get('inputs') or {}).get(slot)
    if named:
        return str(named).strip().upper()
    return helper_code(self_code, INPUT_SLOTS[slot])


def helper_label(code):
    """The words on the screen for one shared helper input."""
    return {
        'PAIDDAYS': _("Paid working days"),
        'STDDAYS': _("Standard working days"),
        'MTHDAYS': _("Days in the month"),
        'PAIDCALD': _("Paid calendar days"),
        'HOURSDAY': _("Hours in a working day"),
        'PAYMONTH': _("Month being paid (1 to 12)"),
        'ISLOCAL': _("Local employee (1 = yes)"),
        'ISINSURED': _("In the insurance scheme (1 = yes)"),
        'ISUNION': _("Union member (1 = yes)"),
        'ISRESIDENT': _("Tax resident (1 = yes)"),
        'CONTRACTMTH': _("Months on this contract"),
        'TAXCOMMIT': _("Signed the single-employer tax commitment (1 = yes)"),
        'ROLEGRADE': _("Pay grade (1, 2 or 3)"),
        'SERVDAYS': _("Days of service this year"),
        'ANNUALDAYS': _("Working days in a full year"),
    }.get(code, code)


def helper_suffix_label(suffix, component_name):
    """"Uniform allowance — approved amount this run"."""
    tail = {
        'IN': _("approved amount this run"),
        'HRS': _("hours this run"),
        'ENR': _("enrolled (1 = yes)"),
        'QUAL': _("has the evidence (1 = yes)"),
        'YTD': _("already exempt this year"),
        'ENT': _("approved entitlement"),
    }.get(suffix, suffix)
    return '%s — %s' % (component_name, tail)

#: The component that carries the contract salary, when the configuration uses
#: the usual naming. Overridable through the compiling context.
DEFAULT_CONTRACT_CODE = 'BASIC'

MAX_CODE_LEN = 12


class RecipeError(ValueError):
    """A choice the server did not understand, in words a person can act on."""


def _one_of(value, allowed, what, default=None):
    if value is None and default is not None:
        return default
    if value not in allowed:
        raise RecipeError(_(
            "“%(value)s” is not something %(what)s can be. Choose one of: "
            "%(allowed)s.", value=value, what=what, allowed=', '.join(allowed)))
    return value


def _number(value, what, default=0.0):
    if value in (None, ''):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        raise RecipeError(_("%(what)s has to be a number.", what=what))


def _code(value, what):
    text = (value or '').strip().upper()
    if not text:
        raise RecipeError(_("%s has to name a component.", what))
    if not text.isalnum() or not text[0].isalpha():
        raise RecipeError(_(
            "“%(code)s” is not a component code. Use capital letters and "
            "digits only, starting with a letter.", code=text))
    return text


def default_recipe(group='earning'):
    """The sentence a brand-new component starts from."""
    return {
        'v': VERSION,
        'group': group if group in GROUPS else 'earning',
        'audience': 'all',
        'amount': {'kind': 'input'},
        'proration': 'none',
        'frequency': 'monthly',
        'sign': -1 if group == 'deduction' else 1,
        'round': '0',
        'treatment': {
            'cash': 'cash',
            'tax': 'taxable' if group != 'deduction' else 'exempt',
            'insurance': 'excluded',
            'tax_bearer': 'employee',
            'pit_deductible': 'no',
            'employer_share_pct': 100.0,
            'is_income_tax': False,
        },
    }


def validate_recipe(recipe, ctx=None):
    """Return a clean, complete recipe — or raise :class:`RecipeError`.

    ``ctx`` (optional) carries what exists in the configuration right now:
    ``{'codes': set(), 'rate_tables': set(), 'self_code': 'X'}``. When it is
    given, every component and rate table a recipe names has to be there, and a
    component may not refer to itself.
    """
    if not isinstance(recipe, dict):
        raise RecipeError(_("The rule could not be read. Try again."))
    ctx = ctx or {}
    codes = {c.upper() for c in (ctx.get('codes') or set())}
    tables = {t.upper() for t in (ctx.get('rate_tables') or set())}
    me = (ctx.get('self_code') or '').upper()

    def known(code, what):
        if codes and code not in codes:
            raise RecipeError(_(
                "There is no component called %(code)s in this configuration, "
                "so %(what)s cannot use it.", code=code, what=what))
        if me and code == me:
            raise RecipeError(_(
                "A component cannot be worked out from itself. Choose a "
                "different component for %s.", what))
        return code

    out = {
        'v': VERSION,
        'group': _one_of(recipe.get('group'), GROUPS, _("a pay group")),
        'audience': _one_of(recipe.get('audience') or 'all', AUDIENCES,
                            _("an audience")),
        'proration': _one_of(recipe.get('proration') or 'none', PRORATION,
                             _("proration")),
        'frequency': _one_of(recipe.get('frequency') or 'monthly', FREQUENCY,
                             _("how often it is paid")),
        'sign': -1 if int(recipe.get('sign') or 1) < 0 else 1,
        'round': _one_of(str(recipe.get('round', '0')), ROUNDING,
                         _("rounding")),
    }

    raw_inputs = recipe.get('inputs') or {}
    if not isinstance(raw_inputs, dict):
        raise RecipeError(_("The inputs this rule reads could not be read."))
    named = {}
    for slot, code in raw_inputs.items():
        if slot not in INPUT_SLOTS:
            raise RecipeError(_(
                "“%(slot)s” is not something a rule can read. Choose one of: "
                "%(allowed)s.", slot=slot, allowed=', '.join(INPUT_SLOTS)))
        if code:
            named[slot] = _code(code, _("an input"))
    if named:
        out['inputs'] = named

    raw_amount = recipe.get('amount') or {}
    if not isinstance(raw_amount, dict):
        raise RecipeError(_("The amount could not be read."))
    kind = _one_of(raw_amount.get('kind') or 'input', KINDS, _("an amount"))
    amount = {'kind': kind}

    for key in NEEDS.get(kind, ()):
        if key in ('value', 'percent', 'rate_pct'):
            continue
        if raw_amount.get(key) in (None, '', []):
            raise RecipeError(_(
                "That kind of amount needs one more choice before it can be "
                "saved. Fill in every part of the sentence."))

    if kind == 'fixed':
        amount['value'] = _number(raw_amount.get('value'), _("the amount"))
    if kind == 'percent_contract':
        amount['percent'] = _number(raw_amount.get('percent'), _("the percentage"))
    if kind == 'percent_of':
        amount['base'] = known(_code(raw_amount.get('base'), _("the base")),
                               _("this rule"))
        if raw_amount.get('rate_code'):
            amount['rate_code'] = known(
                _code(raw_amount.get('rate_code'), _("the rate")), _("this rule"))
        else:
            amount['percent'] = _number(raw_amount.get('percent'),
                                        _("the percentage"))
    if kind == 'role':
        grades = raw_amount.get('grades') or []
        if not isinstance(grades, (list, tuple)) or len(grades) != 3:
            raise RecipeError(_("A grade-based amount needs three amounts."))
        amount['grades'] = [_number(g, _("a grade amount")) for g in grades]
    if kind == 'hourly':
        amount['rate_pct'] = _number(raw_amount.get('rate_pct'),
                                     _("the hourly percentage"), 100.0)
    if kind == 'annual_ratio':
        month = int(_number(raw_amount.get('payout_month'), _("the month"), 1))
        if not 1 <= month <= 12:
            raise RecipeError(_("Choose a month between 1 and 12."))
        amount['payout_month'] = month
    if kind == 'linked':
        amount['link'] = known(_code(raw_amount.get('link'), _("the linked component")),
                               _("this rule"))
    if kind == 'bracket':
        table = _code(raw_amount.get('table'), _("the band table"))
        if tables and table not in tables:
            raise RecipeError(_(
                "There is no band table called %s in this configuration.", table))
        amount['table'] = table
        amount['base'] = known(_code(raw_amount.get('base'), _("the income")),
                               _("this rule"))
    if kind == 'pit_vn':
        table = _code(raw_amount.get('table'), _("the band table"))
        if tables and table not in tables:
            raise RecipeError(_(
                "There is no band table called %s in this configuration.", table))
        amount['table'] = table
        amount['base'] = known(_code(raw_amount.get('base'), _("the income")),
                               _("this rule"))
        routes = raw_amount.get('routes') or {}
        if not isinstance(routes, dict):
            raise RecipeError(_("The tax routes could not be read."))
        clean_routes = {}
        for key in PIT_VN_ROUTES:
            if routes.get(key):
                clean_routes[key] = known(
                    _code(routes[key], _("a tax route")), _("this rule"))
        if clean_routes:
            amount['routes'] = clean_routes
    if kind == 'insurance_base':
        amount['cap'] = known(_code(raw_amount.get('cap'), _("the cap")),
                              _("this rule"))
        amount['basis'] = _one_of(raw_amount.get('basis') or 'actual',
                                  INSURANCE_BASIS, _("an insurance basis"))
        if amount['basis'] == 'contract' and raw_amount.get('contract'):
            amount['contract'] = known(
                _code(raw_amount.get('contract'), _("the contract salary")),
                _("this rule"))
    if kind == 'taxable_base':
        for key in ('relief_self', 'relief_dep', 'deps'):
            if raw_amount.get(key):
                amount[key] = known(_code(raw_amount.get(key), _("a relief")),
                                    _("this rule"))
        # The income the bands are applied to has the person's own insurance
        # taken off first; the income a flat rate is applied to does not. One
        # kind of amount, one flag, two honest answers.
        amount['deduct_contributions'] = bool(
            raw_amount.get('deduct_contributions', True))
    # A ceiling on the amount itself — union dues stop at a monthly maximum
    # however large the salary is.
    if raw_amount.get('max'):
        amount['max'] = known(_code(raw_amount.get('max'), _("the maximum")),
                              _("this rule"))
    if kind in ('sum_group', 'net_total', 'employer_total'):
        of = raw_amount.get('of') or {}
        clean = {}
        if of.get('group'):
            clean['group'] = _one_of(of.get('group'), GROUPS, _("a pay group"))
        if of.get('cash'):
            clean['cash'] = _one_of(of.get('cash'), CASH + ('any',), _("cash or not"))
        if of.get('insurance'):
            clean['insurance'] = _one_of(of.get('insurance'),
                                         INSURANCE + ('any',), _("an insurance choice"))
        if of.get('tax'):
            clean['tax'] = _one_of(of.get('tax'), TAX + ('any',), _("a tax choice"))
        if of.get('income_tax'):
            clean['income_tax'] = _one_of(of.get('income_tax'), INCOME_TAX_FILTER,
                                          _("how income tax is counted"))
        if of.get('pit_deductible'):
            clean['pit_deductible'] = _one_of(
                of.get('pit_deductible'), PIT_DEDUCTIBLE + ('any',),
                _("what counts against income tax"))
        if of.get('exclude'):
            clean['exclude'] = [_code(c, _("an excluded component"))
                                for c in of.get('exclude')]
        amount['of'] = clean
    out['amount'] = amount

    raw_treat = recipe.get('treatment') or {}
    if not isinstance(raw_treat, dict):
        raise RecipeError(_("The tax and insurance choices could not be read."))
    treatment = {
        'cash': _one_of(raw_treat.get('cash') or 'cash', CASH, _("cash or not")),
        'tax': _one_of(raw_treat.get('tax') or 'taxable', TAX, _("a tax choice")),
        'insurance': _one_of(raw_treat.get('insurance') or 'excluded', INSURANCE,
                             _("an insurance choice")),
        'tax_bearer': _one_of(raw_treat.get('tax_bearer') or 'employee', BEARER,
                              _("who pays the tax")),
        'pit_deductible': _one_of(raw_treat.get('pit_deductible') or 'no',
                                  PIT_DEDUCTIBLE,
                                  _("what counts against income tax")),
        'employer_share_pct': _number(raw_treat.get('employer_share_pct'),
                                      _("the employer share"), 100.0),
        'is_income_tax': bool(raw_treat.get('is_income_tax')),
        # A plan total adds up other employer costs so a person can see one
        # number for a scheme. It is a VIEW of costs already counted, so it is
        # never itself summed into anything (see `_members`).
        'plan_total': bool(raw_treat.get('plan_total')),
    }
    if not 0.0 <= treatment['employer_share_pct'] <= 100.0:
        raise RecipeError(_(
            "The employer share is a percentage between 0 and 100."))
    if treatment['tax'] == 'annual_cap':
        treatment['cap'] = _number(raw_treat.get('cap'), _("the yearly limit"))
    if treatment['tax'] == 'inherit' or treatment['insurance'] == 'inherit' \
            or treatment['pit_deductible'] == 'source':
        if not raw_treat.get('source_code'):
            raise RecipeError(_(
                "Choose the original component this one follows."))
        treatment['source_code'] = known(
            _code(raw_treat.get('source_code'), _("the original component")),
            _("this rule"))
    elif raw_treat.get('source_code'):
        treatment['source_code'] = _code(raw_treat.get('source_code'),
                                         _("the original component"))
    out['treatment'] = treatment
    return out


def review_items(recipe, included=None):
    """Decisions this rule still needs from a person, in plain words.

    Returned per rule so the list can show an amber dot with a reason instead
    of a green one that quietly hides an unanswered question.
    """
    items = []
    if not recipe:
        return items
    treat = recipe.get('treatment') or {}
    amount = recipe.get('amount') or {}
    included = {c.upper() for c in (included or set())}
    if treat.get('insurance') == 'review':
        items.append({'code': 'insurance',
                      'text': _("Choose the insurance treatment")})
    if (treat.get('tax') == 'inherit' or treat.get('insurance') == 'inherit') \
            and not treat.get('source_code'):
        items.append({'code': 'source',
                      'text': _("Choose the original component")})
    link = (amount.get('link') or '').upper()
    if amount.get('kind') == 'linked' and link and included and link not in included:
        items.append({'code': 'link',
                      'text': _("Restore or replace the linked benefit")})
    if recipe.get('frequency') == 'annual' and not amount.get('payout_month'):
        items.append({'code': 'month',
                      'text': _("Choose the month it is paid in")})
    # The employer paying somebody's tax on a benefit changes what the tax
    # itself is (the top-up is taxable in its turn). This version taxes the
    # value to the employee and says so, rather than quietly getting it wrong.
    if treat.get('tax_bearer') == 'employer' and treat.get('tax') != 'exempt':
        items.append({'code': 'employer_tax', 'text': _(
            "The employer pays the tax on this: the value is taxed to the "
            "employee for now, and the employer's top-up is not worked out yet")})
    if amount.get('kind') == 'hourly' and treat.get('tax') == 'qualified':
        items.append({'code': 'ot_scope', 'text': _(
            "Confirm which part of overtime is tax free — the whole payment is "
            "treated as tax free while the evidence is held")})
    return items


def helper_code(base, suffix):
    """``UNIFORM`` + ``QUAL`` -> ``UNIFORMQUAL``, trimmed to fit.

    Component codes are capped at 12 characters, so a long base has to give way
    to the suffix — the suffix is the part that says what the helper IS.
    """
    base = (base or '').strip().upper()
    suffix = (suffix or '').strip().upper()
    room = MAX_CODE_LEN - len(suffix)
    if room < 3:
        room = 3
    return (base[:room] + suffix)[:MAX_CODE_LEN]
