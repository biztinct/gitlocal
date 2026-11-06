# -*- coding: utf-8 -*-
"""Build ``pb_blueprint/data/config_template_vn_complete.xml``.

Run it from the repository root::

    python3 pb_blueprint/tools/gen_vn_complete.py

Why a generator and not a hand-written data file: every formula in the starter
is produced by **the guided setup's own compiler**, from the same sentence the
Pay rules step will show. A starter whose Excel was typed by hand drifts from
the sentence the first time either is touched, and the person who finds out is
the one reading a payslip. Here they cannot drift: the file is the compiler's
output.

Two rules the template registry enforces at authoring time, and this script
therefore enforces here, where the message is useful:

* every code is capital letters and digits, no underscore;
* **no code contains another** — which is why the per-component helper inputs
  are named (``HRSWD``, not ``OTWDHRS``) and why the assessable-pay helper is
  ``ASSESSPAY`` and not ``TAXGROSS`` (``GROSS`` is inside it).

The certification expectations are filled in by ``tools/vn_complete_expect.py``,
which runs the five personas through the real engine on a live database. They
are never typed by hand.
"""
import json
import os
import sys
import types

# The compiler modules import `odoo` for their translation marker only. A stub
# keeps this script runnable without a server, which is what makes it a build
# step rather than a deployment.
if 'odoo' not in sys.modules:                              # pragma: no cover
    stub = types.ModuleType('odoo')
    stub._ = lambda text, *a, **kw: (text % kw if kw else (text % a if a else text))
    sys.modules['odoo'] = stub

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.normpath(os.path.join(HERE, '..', 'models'))


def _load(name):
    """Import one compiler module as if it were inside its package.

    The modules use relative imports, so they need a package to belong to; the
    package's own ``__init__`` pulls in the whole addon, which needs a server.
    A one-module namespace package is the smallest thing that satisfies both.
    """
    import importlib.util
    package = 'pbbp_compiler'
    if package not in sys.modules:
        shell = types.ModuleType(package)
        shell.__path__ = [MODELS]
        sys.modules[package] = shell
    full = '%s.%s' % (package, name)
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(
        full, os.path.join(MODELS, '%s.py' % name))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


_load('recipe_schema')
rc = _load('recipe_compiler')
validate_recipe = sys.modules['pbbp_compiler.recipe_schema'].validate_recipe

TEMPLATE_CODE = 'vn_complete_2026'
TEMPLATE_NAME = 'Vietnam · Complete'
VERSION = '2026.1'
EFFECTIVE = '2026-01-01'
PACK_VERSION = '2026.1'


# ======================================================================
#  Recipe shorthands
# ======================================================================
def R(group, kind, **rest):
    """A recipe with the parts that are almost always the same filled in."""
    amount = rest.pop('amount', {})
    treatment = rest.pop('treatment', {})
    recipe = {
        'v': 1, 'group': group, 'audience': rest.pop('audience', 'all'),
        'amount': dict(amount, kind=kind),
        'proration': rest.pop('proration', 'none'),
        'frequency': rest.pop('frequency', 'monthly'),
        'sign': rest.pop('sign', 1),
        'round': rest.pop('round', '0'),
        'treatment': treatment,
    }
    recipe.update(rest)
    return recipe


def earning(kind, tax='taxable', cash='cash', insurance='excluded', **rest):
    treatment = rest.pop('treatment', {})
    treatment.setdefault('cash', cash)
    treatment.setdefault('tax', tax)
    treatment.setdefault('insurance', insurance)
    return R('earning', kind, treatment=treatment, **rest)


def deduction(kind, pit_deductible='no', **rest):
    treatment = rest.pop('treatment', {})
    treatment.setdefault('cash', 'cash')
    treatment.setdefault('tax', 'exempt')
    treatment.setdefault('insurance', 'excluded')
    treatment.setdefault('pit_deductible', pit_deductible)
    return R('deduction', kind, treatment=treatment, **rest)


def benefit(kind, tax='exempt', cash='cash', **rest):
    treatment = rest.pop('treatment', {})
    treatment.setdefault('cash', cash)
    treatment.setdefault('tax', tax)
    treatment.setdefault('insurance', 'excluded')
    treatment.setdefault('employer_share_pct', 100.0)
    return R('benefit', kind, treatment=treatment, **rest)


def total(kind, **rest):
    treatment = rest.pop('treatment', {})
    treatment.setdefault('cash', 'cash')
    treatment.setdefault('tax', 'exempt')
    treatment.setdefault('insurance', 'excluded')
    # A total never rounds: it adds up numbers that were already rounded when
    # they were worked out, and rounding a sum of rounded parts is how a
    # payslip stops adding up.
    rest.setdefault('round', 'none')
    return R('total', kind, treatment=treatment, **rest)


def plumbing(kind='input', **rest):
    treatment = rest.pop('treatment', {})
    treatment.setdefault('cash', 'cash')
    treatment.setdefault('tax', 'exempt')
    treatment.setdefault('insurance', 'excluded')
    return R('helper', kind, treatment=treatment, round='none', **rest)


def IN(code, name, fmt='currency', default=0.0, recipe=None, payslip=False):
    return {'code': code, 'name': name, 'type': 'input', 'number_format': fmt,
            'default_value': default, 'appears_on_payslip': payslip,
            'category': 'INPUT', 'recipe': recipe or plumbing()}


def CONST(code, name, value, fmt='currency', legis=None):
    row = {'code': code, 'name': name, 'type': 'constant',
           'constant_value': value, 'number_format': fmt,
           'appears_on_payslip': False, 'recipe': plumbing('manual')}
    if legis:
        row['legislation_code'] = legis
    return row


def COMP(code, name, recipe, category=None, fmt='currency', payslip=True):
    return {'code': code, 'name': name, 'type': 'formula', 'recipe': recipe,
            'category': category, 'number_format': fmt,
            'appears_on_payslip': payslip}


def GIVEN(code, name, recipe, category=None, fmt='currency', payslip=True):
    """A component the payroll is simply GIVEN — an approved amount.

    Shipped as an input rather than a formula: there is no calculation to do,
    and a starter may not ship the ``<CODE>IN`` companion an input-shaped
    formula would need (no code may contain another).
    """
    return {'code': code, 'name': name, 'type': 'input', 'recipe': recipe,
            'category': category, 'number_format': fmt, 'default_value': 0.0,
            'appears_on_payslip': payslip}


# ======================================================================
#  The starter, in order
# ======================================================================
def components():
    rows = []

    # ---- what the payroll is told -------------------------------------
    rows += [
        IN('BASIC', 'Contract salary', 'currency', 0.0),
        IN('DEPS', 'Registered dependants', 'integer', 0.0),
        IN('STDDAYS', 'Standard working days', 'integer', 26.0),
        IN('PAIDDAYS', 'Paid working days', 'integer', 26.0),
        IN('HOURSDAY', 'Hours in a working day', 'number', 8.0),
        IN('PAYMONTH', 'Month being paid (1 to 12)', 'integer', 1.0),
        IN('ISLOCAL', 'Local employee (1 = yes)', 'integer', 1.0),
        IN('ISINSURED', 'In the insurance scheme (1 = yes)', 'integer', 1.0),
        IN('ISUNION', 'Union member (1 = yes)', 'integer', 0.0),
        IN('ISRESIDENT', 'Tax resident (1 = yes)', 'integer', 1.0),
        IN('CONTRACTMTH', 'Months on this contract', 'integer', 12.0),
        IN('TAXCOMMIT', 'Signed the single-employer tax commitment (1 = yes)',
           'integer', 0.0),
        IN('ROLEGRADE', 'Pay grade (1, 2 or 3)', 'integer', 0.0),
        IN('SERVDAYS', 'Days of service this year', 'integer', 260.0),
        IN('ANNUALDAYS', 'Working days in a full year', 'integer', 260.0),
        IN('HRSWD', 'Weekday overtime — hours this run', 'number', 0.0),
        IN('HRSWE', 'Weekend overtime — hours this run', 'number', 0.0),
        IN('HRSHOL', 'Public-holiday overtime — hours this run', 'number', 0.0),
        IN('HRSNIGHT', 'Night work — hours this run', 'number', 0.0),
        IN('ENROLPREM', 'Enrolled in family health cover (1 = yes)', 'integer', 0.0),
        IN('ENROLHLTH', 'Enrolled in private health cover (1 = yes)', 'integer', 0.0),
        IN('ENROLDEP', "Dependants enrolled in private health cover (1 = yes)",
           'integer', 0.0),
        IN('PRIVINSAMT', 'Private insurance allowance approved', 'currency', 0.0),
        IN('HLTHEEAMT', 'Private health premium — employee', 'currency', 0.0),
        IN('HLTHDEPAMT', 'Private health premium — dependants', 'currency', 0.0),
        IN('ADJDEDAMT', 'Prior-period deduction approved', 'currency', 0.0),
        IN('PAIDVAR', 'Variable bonus approved this run (1 = yes)', 'integer', 0.0),
    ]

    # ---- the values the rule pack owns --------------------------------
    rows += [
        CONST('DEDUCTSELF', 'Personal relief', 15500000.0, 'currency', 'DEDUCTSELF'),
        CONST('DEDUCTDEP', 'Relief per registered dependant', 6200000.0,
              'currency', 'DEDUCTDEP'),
        CONST('SIRATE', 'Social insurance — employee', 0.08, 'percentage', 'EESI'),
        CONST('HIRATE', 'Health insurance — employee', 0.015, 'percentage', 'EEHI'),
        CONST('UIRATE', 'Unemployment insurance — employee', 0.01, 'percentage',
              'EEUI'),
        CONST('SIEMPR', 'Social insurance — employer', 0.175, 'percentage', 'ERSI'),
        CONST('HIEMPR', 'Health insurance — employer', 0.03, 'percentage', 'ERHI'),
        CONST('UIEMPR', 'Unemployment insurance — employer', 0.01, 'percentage',
              'ERUI'),
        CONST('CAPLO', 'Social and health insurance ceiling', 46800000.0,
              'currency', 'CAPLO'),
        CONST('CAPHI', 'Unemployment insurance ceiling', 99200000.0, 'currency',
              'CAPHI'),
        CONST('UNIONCAP', 'Union dues ceiling', 253000.0, 'currency'),
        CONST('UNIONRATE', 'Union dues — employee', 0.005, 'percentage'),
        CONST('UNIONEMPR', 'Union contribution — employer', 0.02, 'percentage'),
        CONST('NONRESRATE', 'Flat rate for people who are not tax resident', 0.2,
              'percentage'),
        CONST('SHORTRATE', 'Withholding rate on contracts under three months',
              0.1, 'percentage'),
        CONST('SHORTTHRESH', 'Payment at which withholding starts', 5000000.0,
              'currency'),
    ]

    # ---- what a person is paid ----------------------------------------
    rows += [
        COMP('SALARYPAID', 'Basic salary for the days worked',
             earning('contract', insurance='included', proration='working_days'),
             'BASIC'),
        GIVEN('UNIFORM', 'Uniform allowance',
              earning('input', tax='annual_cap', frequency='adhoc',
                      treatment={'cap': 5000000.0}), 'ALW'),
        GIVEN('SEVERSTAT', 'Statutory severance allowance',
              earning('input', tax='entitlement', frequency='adhoc'), 'ALW'),
        GIVEN('OTHEREXMP', 'Other exempt reimbursement',
              earning('input', tax='qualified', frequency='adhoc'), 'ALW'),
        GIVEN('ALENCASH', 'Unused annual-leave encashment',
              earning('input', tax='qualified', frequency='adhoc'), 'ALW'),
        GIVEN('TRANSPADD', 'Additional transportation',
              earning('input', tax='qualified', frequency='adhoc'), 'ALW'),
        COMP('TRANSPORT', 'Transportation allowance',
             earning('role', audience='role', proration='working_days',
                     amount={'grades': [1200000.0, 800000.0, 500000.0]}), 'ALW'),
        COMP('PHONEALLOW', 'Phone allowance',
             earning('fixed', proration='working_days',
                     amount={'value': 500000.0}), 'ALW'),
        COMP('PRIVINSALW', 'Private insurance allowance for expatriates',
             earning('input', audience='foreign', insurance='review',
                     inputs={'amount': 'PRIVINSAMT'}), 'ALW'),
        COMP('PREMINSALW', 'Premium health cover for family members',
             earning('linked', cash='noncash', audience='enrolled',
                     frequency='scheme', amount={'link': 'PRIVHLTHDEP'},
                     inputs={'enrol': 'ENROLPREM'}), 'ALW'),
        GIVEN('LOGISINC', 'Logistics incentive', earning('input'), 'ALW'),
        GIVEN('AGROINC', 'Season agronomy incentive',
              earning('input', frequency='scheme'), 'ALW'),
        GIVEN('LAUNCHINC', 'New product launch incentive',
              earning('input', frequency='adhoc'), 'ALW'),
        COMP('VARPAY', 'Variable bonus',
             earning('percent_contract', frequency='scheme',
                     amount={'percent': 10.0},
                     inputs={'run': 'PAIDVAR'}), 'ALW'),
        GIVEN('REFERINC', 'Referral incentive',
              earning('input', frequency='adhoc'), 'ALW'),
        GIVEN('OTHERTAX', 'Other taxable allowance',
              earning('input', frequency='adhoc'), 'ALW'),
        GIVEN('ADJADD', 'Prior-period addition',
              earning('input', tax='inherit', insurance='inherit',
                      frequency='adhoc',
                      treatment={'source_code': 'SALARYPAID'}), 'ALW'),
        COMP('ADJDEDUCT', 'Prior-period deduction adjustment',
             earning('input', tax='inherit', insurance='inherit', sign=-1,
                     frequency='adhoc', inputs={'amount': 'ADJDEDAMT'},
                     treatment={'source_code': 'SALARYPAID'}), 'ALW'),
        GIVEN('NONCASHBEN', 'Taxable non-cash benefit',
              earning('input', cash='noncash', frequency='adhoc'), 'ALW'),
        COMP('OTWD', 'Weekday overtime pay',
             earning('hourly', tax='qualified', amount={'rate_pct': 150.0},
                     inputs={'hours': 'HRSWD'}), 'OT'),
        COMP('OTWE', 'Weekend overtime pay',
             earning('hourly', tax='qualified', amount={'rate_pct': 200.0},
                     inputs={'hours': 'HRSWE'}), 'OT'),
        COMP('OTHOL', 'Public-holiday overtime pay',
             earning('hourly', tax='qualified', amount={'rate_pct': 300.0},
                     inputs={'hours': 'HRSHOL'}), 'OT'),
        COMP('NIGHTPREM', 'Night-work premium',
             earning('hourly', tax='qualified', amount={'rate_pct': 30.0},
                     inputs={'hours': 'HRSNIGHT'}), 'OT'),
        COMP('MONTH13', 'Thirteenth-month salary',
             earning('annual_ratio', frequency='annual',
                     amount={'payout_month': 1}), 'ALW'),
    ]

    # ---- the bases everything statutory is worked out from -------------
    rows += [
        COMP('SIBASE', 'Social and health insurance base',
             total('insurance_base', amount={'cap': 'CAPLO', 'basis': 'actual'}),
             'BASIC', payslip=False),
        COMP('UIBASE', 'Unemployment insurance base',
             total('insurance_base', amount={'cap': 'CAPHI', 'basis': 'actual'}),
             'BASIC', payslip=False),
    ]

    # ---- what comes off ------------------------------------------------
    rows += [
        COMP('SIDED', 'Social insurance deducted',
             deduction('percent_of', pit_deductible='yes', audience='insured',
                       amount={'base': 'SIBASE', 'rate_code': 'SIRATE'}), 'DED'),
        COMP('HIDED', 'Health insurance deducted',
             deduction('percent_of', pit_deductible='yes', audience='insured',
                       amount={'base': 'SIBASE', 'rate_code': 'HIRATE'}), 'DED'),
        COMP('UIDED', 'Unemployment insurance deducted',
             deduction('percent_of', pit_deductible='yes',
                       audience='local_insured',
                       amount={'base': 'UIBASE', 'rate_code': 'UIRATE'}), 'DED'),
        COMP('UNIONDUES', 'Union dues',
             deduction('percent_of', audience='union',
                       amount={'base': 'SIBASE', 'rate_code': 'UNIONRATE',
                               'max': 'UNIONCAP'}), 'DED'),
        COMP('EEDED', 'Insurance deducted from pay',
             total('sum_group', amount={'of': {'group': 'deduction',
                                               'pit_deductible': 'yes'}}),
             'DED'),
    ]

    # ---- income tax ------------------------------------------------------
    rows += [
        COMP('ASSESSPAY', 'Assessable pay before relief',
             total('taxable_base', amount={'deduct_contributions': False}),
             'GROSS', payslip=False),
        COMP('TAXABLE', 'Income the tax bands apply to',
             total('taxable_base',
                   amount={'relief_self': 'DEDUCTSELF',
                           'relief_dep': 'DEDUCTDEP', 'deps': 'DEPS'}),
             'GROSS', payslip=False),
        COMP('PIT', 'Personal income tax',
             deduction('pit_vn', round='none', treatment={'is_income_tax': True},
                       amount={'table': 'VNTAX', 'base': 'TAXABLE', 'routes': {
                           'nonres_rate': 'NONRESRATE',
                           'short_rate': 'SHORTRATE',
                           'short_threshold': 'SHORTTHRESH',
                           'resident_input': 'ISRESIDENT',
                           'months_input': 'CONTRACTMTH',
                           'commit_input': 'TAXCOMMIT',
                           'gross_base': 'ASSESSPAY'}}), 'TAX'),
        GIVEN('ADVANCE', 'Salary advance recovery',
              deduction('input', frequency='adhoc'), 'DED'),
        GIVEN('PRIORDED', 'Prior-period deduction',
              deduction('input', pit_deductible='source', frequency='adhoc',
                        treatment={'source_code': 'SALARYPAID'}), 'DED'),
        GIVEN('OTHERDED', 'Other deduction',
              deduction('input', frequency='adhoc'), 'DED'),
    ]

    # ---- what the employer pays on top ----------------------------------
    plan_excludes = ['PRIVHLTHEE', 'PRIVHLTHDEP', 'UNIONER', 'OTHERBEN']
    rows += [
        COMP('SICOMP', 'Social insurance — employer',
             benefit('percent_of', audience='insured',
                     amount={'base': 'SIBASE', 'rate_code': 'SIEMPR'}), 'COMP'),
        COMP('HICOMP', 'Health insurance — employer',
             benefit('percent_of', audience='insured',
                     amount={'base': 'SIBASE', 'rate_code': 'HIEMPR'}), 'COMP'),
        COMP('UICOMP', 'Unemployment insurance — employer',
             benefit('percent_of', audience='local_insured',
                     amount={'base': 'UIBASE', 'rate_code': 'UIEMPR'}), 'COMP'),
        COMP('PRIVHLTHEE', 'Private health cover — employee',
             benefit('input', tax='taxable', cash='noncash', audience='enrolled',
                     frequency='scheme',
                     inputs={'amount': 'HLTHEEAMT', 'enrol': 'ENROLHLTH'},
                     treatment={'tax_bearer': 'employer'}), 'COMP'),
        COMP('PRIVHLTHDEP', 'Private health cover — dependants',
             benefit('input', tax='taxable', cash='noncash', audience='enrolled',
                     frequency='scheme',
                     inputs={'amount': 'HLTHDEPAMT', 'enrol': 'ENROLDEP'},
                     treatment={'tax_bearer': 'employer'}), 'COMP'),
        COMP('UNIONER', 'Union contribution — employer',
             benefit('percent_of', audience='union',
                     amount={'base': 'SIBASE', 'rate_code': 'UNIONEMPR'}), 'COMP'),
        GIVEN('OTHERBEN', 'Other company benefits',
              benefit('input', tax='taxable', cash='noncash', frequency='adhoc',
                      treatment={'insurance': 'review'}), 'COMP'),
        COMP('SHUILOCAL', 'Statutory cover — local employees',
             benefit('sum_group', audience='local',
                     treatment={'plan_total': True},
                     amount={'of': {'group': 'benefit',
                                    'exclude': plan_excludes}}), 'COMP'),
        COMP('SHUIFOREIGN', 'Statutory cover — foreign employees',
             benefit('sum_group', audience='foreign',
                     treatment={'plan_total': True},
                     amount={'of': {'group': 'benefit',
                                    'exclude': plan_excludes}}), 'COMP'),
    ]

    # ---- the totals -------------------------------------------------------
    rows += [
        COMP('GROSS', 'Gross pay',
             total('sum_group', amount={'of': {'group': 'earning',
                                               'cash': 'cash'}}), 'GROSS'),
        COMP('BENEFITVAL', 'Value of benefits in kind',
             total('sum_group', amount={'of': {'group': 'earning',
                                               'cash': 'noncash'}}), 'GROSS'),
        COMP('NET', 'Take-home pay', total('net_total'), 'NET'),
        # PREMINSALW is the taxable VALUE to the employee of the dependants'
        # cover the employer already pays as PRIVHLTHDEP. Counting both would
        # charge the employer twice for one policy.
        COMP('ERCOST', 'Total employer cost',
             total('employer_total',
                   amount={'of': {'exclude': ['PREMINSALW']}}), 'COMP'),
    ]
    return rows


RATE_TABLES = [{
    'code': 'VNTAX',
    'name': 'Vietnam income tax (monthly, seven bands)',
    'note': "Progressive marginal schedule. Editable on the Tax and protection "
            "tab of the guided setup.",
    'legislation_ref': 'PIT Law 04/2007/QH12 (Circular 111/2013/TT-BTC schedule)',
    'brackets': [
        {'lower': 0, 'rate': 0.05},
        {'lower': 5000000, 'rate': 0.10},
        {'lower': 10000000, 'rate': 0.15},
        {'lower': 18000000, 'rate': 0.20},
        {'lower': 32000000, 'rate': 0.25},
        {'lower': 52000000, 'rate': 0.30},
        {'lower': 80000000, 'rate': 0.35},
    ],
}]

#: The five people this starter is proved against. Expected values are filled
#: in by the engine (see the module docstring), never typed.
PERSONAS = [
    {'name': 'Full month · local', 'inputs': {
        'BASIC': 30000000, 'DEPS': 1, 'STDDAYS': 26, 'PAIDDAYS': 26,
        'HOURSDAY': 8, 'PAYMONTH': 3, 'ISLOCAL': 1, 'ISINSURED': 1,
        'ISUNION': 0, 'ISRESIDENT': 1, 'CONTRACTMTH': 12}},
    {'name': 'Joined mid-month', 'inputs': {
        'BASIC': 30000000, 'DEPS': 1, 'STDDAYS': 26, 'PAIDDAYS': 13,
        'HOURSDAY': 8, 'PAYMONTH': 3, 'ISLOCAL': 1, 'ISINSURED': 1,
        'ISUNION': 0, 'ISRESIDENT': 1, 'CONTRACTMTH': 12}},
    {'name': 'Foreign · not tax resident', 'inputs': {
        'BASIC': 60000000, 'DEPS': 0, 'STDDAYS': 26, 'PAIDDAYS': 26,
        'HOURSDAY': 8, 'PAYMONTH': 3, 'ISLOCAL': 0, 'ISINSURED': 1,
        'ISUNION': 0, 'ISRESIDENT': 0, 'CONTRACTMTH': 12}},
    {'name': 'Short contract', 'inputs': {
        'BASIC': 6000000, 'DEPS': 0, 'STDDAYS': 26, 'PAIDDAYS': 26,
        'HOURSDAY': 8, 'PAYMONTH': 3, 'ISLOCAL': 1, 'ISINSURED': 0,
        'ISUNION': 0, 'ISRESIDENT': 1, 'CONTRACTMTH': 2, 'TAXCOMMIT': 0}},
    {'name': 'Enrolled in private health', 'inputs': {
        'BASIC': 30000000, 'DEPS': 1, 'STDDAYS': 26, 'PAIDDAYS': 26,
        'HOURSDAY': 8, 'PAYMONTH': 3, 'ISLOCAL': 1, 'ISINSURED': 1,
        'ISUNION': 0, 'ISRESIDENT': 1, 'CONTRACTMTH': 12,
        'ENROLDEP': 1, 'ENROLPREM': 1, 'HLTHDEPAMT': 2000000}},
]

#: The codes each persona is checked on. Everything a payslip shows.
CHECK_CODES = ['SALARYPAID', 'GROSS', 'SIBASE', 'SIDED', 'HIDED', 'UIDED',
               'EEDED', 'ASSESSPAY', 'TAXABLE', 'PIT', 'NET', 'SICOMP',
               'HICOMP', 'UICOMP', 'SHUILOCAL', 'SHUIFOREIGN', 'BENEFITVAL',
               'ERCOST']

LEGISLATION_REFS = [
    {'ref': 'Resolution 110/2025/UBTVQH15',
     'title': 'Family-circumstance deductions (self 15.5M / dependant 6.2M)',
     'url': '', 'effective_date': '2026-01-01'},
    {'ref': 'PIT Law 04/2007/QH12',
     'title': 'Personal income tax — seven-band progressive schedule',
     'url': '', 'effective_date': '2009-01-01'},
    {'ref': 'Law on Social Insurance 58/2014/QH13',
     'title': 'Social, health and unemployment insurance rates, caps and ceilings',
     'url': '', 'effective_date': '2016-01-01'},
    {'ref': 'Circular 111/2013/TT-BTC',
     'title': 'Withholding on contracts under three months and on people who '
              'are not tax resident',
     'url': '', 'effective_date': '2013-10-01'},
]

DESCRIPTION = (
    "Everything a Vietnamese monthly payroll normally needs, with a plain "
    "sentence behind every line: paid salary and proration, allowances and "
    "incentives, four kinds of overtime, thirteenth-month pay, social, health "
    "and unemployment insurance for employee and employer, union dues, private "
    "health cover, prior-period corrections, and income tax by the route that "
    "applies to the person. Statutory values come from the Vietnam rule pack "
    "and can be reviewed and changed during setup."
)


# ======================================================================
#  Letters, checks and compilation
# ======================================================================
def letters_for(count):
    out, i = [], 0
    while len(out) < count:
        n, name = i, ''
        while True:
            name = chr(ord('A') + n % 26) + name
            n = n // 26 - 1
            if n < 0:
                break
        out.append(name)
        i += 1
    return out


def assert_codes(codes):
    """The template registry's own contract, checked where it is fixable."""
    for code in codes:
        if '_' in code or not code.isalnum() or not code[0].isalpha() \
                or code.upper() != code:
            raise SystemExit("Bad code %r: capitals and digits only." % code)
    for a in codes:
        for b in codes:
            if a != b and a in b:
                raise SystemExit(
                    "Code %r is inside %r. The converter would rewrite the "
                    "shorter one and compute zero. Rename one of them." % (a, b))


def build():
    rows = components()
    codes = [r['code'] for r in rows] + [t['code'] for t in RATE_TABLES]
    assert_codes(codes)

    letters = dict(zip([r['code'] for r in rows], letters_for(len(rows))))
    known = {r['code'] for r in rows}
    tables = {t['code'] for t in RATE_TABLES}

    recipes, groups, types, order = {}, {}, {}, []
    for row in rows:
        clean = validate_recipe(row['recipe'], {
            'codes': known, 'rate_tables': tables, 'self_code': row['code']})
        row['recipe'] = clean
        recipes[row['code']] = clean
        groups[row['code']] = clean['group']
        types[row['code']] = row['type']
        order.append(row['code'])

    ctx = rc.Ctx({'letters': letters, 'recipes': recipes, 'groups': groups,
                  'types': types, 'order': order, 'rate_tables': tables,
                  'self_code': '', 'contract_code': 'BASIC'})

    for row in rows:
        if row['type'] != 'formula':
            continue
        ctx['self_code'] = row['code']
        formula, needs = rc.compile_recipe(row['recipe'], ctx)
        ctx['self_code'] = ''
        if needs:
            raise SystemExit(
                "%s wants inputs the starter does not ship: %s"
                % (row['code'], ', '.join(needs)))
        if not formula:
            raise SystemExit("%s produced no formula." % row['code'])
        row['excel_formula'] = formula

    for row in rows:
        row['column_letter'] = letters[row['code']]
    return rows


def sample_tests(expected=None):
    expected = expected or {}
    out = []
    for persona in PERSONAS:
        out.append({
            'name': persona['name'],
            'pack_version': PACK_VERSION,
            'inputs': persona['inputs'],
            'expected': expected.get(persona['name'], {}),
            'tol': 1.0,
        })
    return out


def payload(rows, expected=None):
    """The five JSON fields, exactly as the registry stores them."""
    comps = []
    for row in rows:
        comp = {'code': row['code'], 'name': row['name'], 'type': row['type'],
                'number_format': row.get('number_format') or 'currency',
                'appears_on_payslip': bool(row.get('appears_on_payslip')),
                'column_letter': row['column_letter'],
                'recipe': row['recipe']}
        for key in ('category', 'excel_formula', 'legislation_code'):
            if row.get(key):
                comp[key] = row[key]
        for key in ('constant_value', 'default_value'):
            if row.get(key):
                comp[key] = float(row[key])
        comps.append(comp)
    return {
        'components_json': json.dumps(comps),
        'rate_tables_json': json.dumps(RATE_TABLES),
        'sample_tests_json': json.dumps(sample_tests(expected)),
        'legislation_refs_json': json.dumps(LEGISLATION_REFS),
    }


def escape(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def render(rows, expected=None):
    data = payload(rows, expected)
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<odoo>',
        '    <!-- Vietnam · Complete — the guided setup\'s full starter.',
        '         GENERATED by pb_blueprint/tools/gen_vn_complete.py: every',
        '         formula below is the guided compiler\'s own output for the',
        '         sentence stored beside it, so the starter and the sentence',
        '         can never drift. Edit the generator and regenerate. -->',
        '    <data noupdate="1">',
        '        <record id="tpl_vn_complete_2026" model="hr.formula.config.template">',
        '            <field name="code">%s</field>' % TEMPLATE_CODE,
        '            <field name="name">%s</field>' % escape(TEMPLATE_NAME),
        '            <field name="country_code">VN</field>',
        '            <field name="flag">🇻🇳</field>',
        '            <field name="version">%s</field>' % VERSION,
        '            <field name="effective_date">%s</field>' % EFFECTIVE,
        '            <field name="state">draft</field>',
        '            <field name="sequence">5</field>',
        '            <field name="description">%s</field>' % escape(DESCRIPTION),
    ]
    for key in ('components_json', 'rate_tables_json', 'sample_tests_json',
                'legislation_refs_json'):
        lines.append('            <field name="%s">%s</field>'
                     % (key, escape(data[key])))
    lines += ['        </record>', '    </data>', '</odoo>', '']
    return '\n'.join(lines)


def main():
    expected = {}
    path = os.path.join(HERE, 'vn_complete_expected.json')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as handle:
            expected = json.load(handle)
    rows = build()
    target = os.path.join(HERE, '..', 'data', 'config_template_vn_complete.xml')
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as handle:
        handle.write(render(rows, expected))
    print("%d components, %d with a formula -> %s"
          % (len(rows), sum(1 for r in rows if r['type'] == 'formula'),
             os.path.normpath(target)))
    if not expected:
        print("No certification expectations yet: run tools/vn_complete_expect.py "
              "on a database, save its output as tools/vn_complete_expected.json, "
              "and regenerate.")


if __name__ == '__main__':
    main()
