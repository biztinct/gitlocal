# -*- coding: utf-8 -*-
"""From the sentence to the formula, and back through the whole configuration.

Two halves, deliberately separated:

* :func:`compile_recipe` is **pure**. Give it a recipe and a picture of the
  configuration (which codes exist, which column letter each one owns, which
  rate tables there are) and it hands back an Excel formula plus the list of
  helper inputs it would need. No database, no records, no side effects — which
  is what makes it testable in a fraction of a second and impossible to get
  half-applied.
* :func:`regenerate` walks a real configuration in dependency order and writes
  the formulas back, and it only ever rewrites a rule the sentence still owns
  (``bp_formula_source == 'generated'``). A formula somebody typed is left
  exactly as they typed it; only the record of what the sentence WOULD have
  produced is refreshed, so the editor can offer "restore the guided version".

Every reference the compiler emits is a **column letter** (BP-R4). Letters are
frozen for the life of a component, the converter resolves them first, and the
whole Vietnam rule pack is written that way. Codes are for people.
"""
import json
import logging

from odoo import _

from .recipe_schema import (
    DEFAULT_CONTRACT_CODE, HELPER_INPUTS, HELPER_SUFFIXES, RecipeError,
    helper_code, slot_code,
)

_logger = logging.getLogger(__name__)


def _num(value):
    """A literal the Excel to Python converter can read back exactly.

    Never scientific notation: the converter's tokeniser does not know it, and
    a salary cap written as 4.68e7 silently becomes nothing.
    """
    value = float(value or 0.0)
    if value == int(value):
        return str(int(value))
    return ('%.6f' % value).rstrip('0').rstrip('.')


class Ctx(dict):
    """What the compiler is allowed to know about a configuration.

    Keys: ``letters`` {CODE: 'AE'}, ``recipes`` {CODE: recipe}, ``groups``
    {CODE: group}, ``types`` {CODE: 'input'|'formula'|'constant'},
    ``order`` [CODE...] in grid order, ``rate_tables`` {CODE}, ``self_code``,
    ``contract_code``.
    """

    @property
    def letters(self):
        return self.get('letters') or {}

    @property
    def order(self):
        return self.get('order') or list(self.letters)


def _ref(code, ctx, needs):
    """The column letter for a code — or the code itself, recorded as missing.

    A sentence can name a helper input that has not been created yet (the
    person has just chosen "hours x hourly rate" and nothing has been saved).
    Rather than refusing, the compiler reports what it needs; the caller
    creates those inputs and compiles again, and the second pass is pure
    letters. `strict` callers (regeneration) never see this, because by then
    everything exists.
    """
    code = (code or '').upper()
    letter = ctx.letters.get(code)
    if letter:
        return letter
    if code not in needs:
        needs.append(code)
    return code


def _members(ctx, of):
    """Every included component the group filter in ``of`` matches, in grid order."""
    of = of or {}
    want_group = of.get('group')
    want_cash = of.get('cash') or 'any'
    want_ins = of.get('insurance') or 'any'
    want_tax = of.get('tax') or 'any'
    want_income_tax = of.get('income_tax') or 'any'
    want_deduct = of.get('pit_deductible') or 'any'
    excluded = {c.upper() for c in (of.get('exclude') or [])}
    me = (ctx.get('self_code') or '').upper()

    out = []
    for code in ctx.order:
        code = code.upper()
        if code == me or code in excluded:
            continue
        recipe = (ctx.get('recipes') or {}).get(code)
        group = (ctx.get('groups') or {}).get(code)
        if want_group and group != want_group:
            continue
        treat = (recipe or {}).get('treatment') or {}
        # A plan total is a roll-up of costs that are already in this list.
        # Counting it as well would charge the employer twice for the same
        # scheme, so it is never a member of any group sum — including its own.
        if treat.get('plan_total'):
            continue
        if want_cash != 'any' and (treat.get('cash') or 'cash') != want_cash:
            continue
        if want_ins != 'any' and (treat.get('insurance') or 'excluded') != want_ins:
            continue
        if want_tax != 'any' and (treat.get('tax') or 'taxable') != want_tax:
            continue
        is_tax = bool(treat.get('is_income_tax'))
        if want_income_tax == 'exclude' and is_tax:
            continue
        if want_income_tax == 'only' and not is_tax:
            continue
        if want_deduct != 'any' and (treat.get('pit_deductible') or 'no') != want_deduct:
            continue
        out.append(code)
    return out


def _sum_of(codes, ctx, needs):
    """``(A+G+H)`` — a plain addition chain, never ``SUM(...)``.

    Semantically identical and one less moving part: ``SUM`` has to survive the
    converter's array-bracket rewrite, and a bare chain is exactly the shape the
    Vietnam rule pack's own totals are written in, so a regenerated total reads
    the same as the one it replaced.
    """
    if not codes:
        return '0'
    if len(codes) == 1:
        return _ref(codes[0], ctx, needs)
    return '(' + '+'.join(_ref(c, ctx, needs) for c in codes) + ')'


def _taxable_part(code, ctx, needs):
    """What a component contributes to taxable income.

    A component whose tax treatment is anything other than "all of it" or
    "none of it" gets a small helper rule beside it (``<CODE>TX``) that works
    out the taxable slice; when that helper exists the total uses it.
    """
    code = code.upper()
    tx = helper_code(code, 'TX')
    if tx in ctx.letters:
        return tx
    return code


def _audience_test(recipe, ctx, needs):
    audience = recipe.get('audience') or 'all'
    self_code = (ctx.get('self_code') or '').upper()
    if audience == 'all':
        return None
    if audience == 'local':
        return '%s=1' % _ref('ISLOCAL', ctx, needs)
    if audience == 'foreign':
        return '%s=0' % _ref('ISLOCAL', ctx, needs)
    if audience == 'insured':
        return '%s=1' % _ref('ISINSURED', ctx, needs)
    if audience == 'union':
        return '%s=1' % _ref('ISUNION', ctx, needs)
    if audience == 'enrolled':
        return '%s=1' % _ref(slot_code(recipe, 'enrol', self_code), ctx, needs)
    if audience == 'role':
        return '%s>0' % _ref('ROLEGRADE', ctx, needs)
    if audience == 'local_insured':
        return 'AND(%s=1,%s=1)' % (_ref('ISLOCAL', ctx, needs),
                                   _ref('ISINSURED', ctx, needs))
    return None


def _amount_expr(recipe, ctx, needs):
    """The bare amount, before proration, frequency, audience and rounding."""
    amount = recipe.get('amount') or {}
    kind = amount.get('kind') or 'input'
    self_code = (ctx.get('self_code') or '').upper()
    contract = (ctx.get('contract_code') or DEFAULT_CONTRACT_CODE).upper()

    if kind == 'manual':
        return None
    if kind == 'input':
        if (ctx.get('types') or {}).get(self_code) == 'input':
            return None            # the component IS the input; no formula
        return _ref(slot_code(recipe, 'amount', self_code), ctx, needs)
    if kind == 'fixed':
        return _num(amount.get('value'))
    if kind == 'contract':
        if contract == self_code:
            raise RecipeError(_(
                "This component IS the contract salary, so it cannot also be "
                "worked out from it. Choose a different amount."))
        return _ref(contract, ctx, needs)
    if kind == 'percent_contract':
        return '(%s*%s/100)' % (_ref(contract, ctx, needs),
                                _num(amount.get('percent')))
    if kind == 'percent_of':
        base = _ref(amount.get('base'), ctx, needs)
        if amount.get('rate_code'):
            return '(%s*%s)' % (base, _ref(amount['rate_code'], ctx, needs))
        return '(%s*%s/100)' % (base, _num(amount.get('percent')))
    if kind == 'role':
        grade = _ref('ROLEGRADE', ctx, needs)
        g1, g2, g3 = [_num(g) for g in (amount.get('grades') or [0, 0, 0])]
        return 'IF(%(g)s=1,%(a)s,IF(%(g)s=2,%(b)s,IF(%(g)s=3,%(c)s,0)))' % {
            'g': grade, 'a': g1, 'b': g2, 'c': g3}
    if kind == 'hourly':
        hours = _ref(slot_code(recipe, 'hours', self_code), ctx, needs)
        rate = '(%s/(%s*%s))' % (_ref(contract, ctx, needs),
                                 _ref('STDDAYS', ctx, needs),
                                 _ref('HOURSDAY', ctx, needs))
        return '(%s*%s*%s/100)' % (hours, rate, _num(amount.get('rate_pct')))
    if kind == 'annual_ratio':
        base = _ref(contract, ctx, needs)
        month = int(amount.get('payout_month') or 1)
        return 'IF(%s=%d,MIN(%s,%s*%s/%s),0)' % (
            _ref('PAYMONTH', ctx, needs), month, base, base,
            _ref('SERVDAYS', ctx, needs), _ref('ANNUALDAYS', ctx, needs))
    if kind == 'linked':
        return _ref(amount.get('link'), ctx, needs)
    if kind == 'sum_group':
        return _sum_of(_members(ctx, amount.get('of')), ctx, needs)
    if kind == 'bracket':
        return 'BRACKET(%s,%s)' % ((amount.get('table') or '').upper(),
                                   _ref(amount.get('base'), ctx, needs))
    if kind == 'pit_vn':
        return _pit_vn_expr(amount, ctx, needs)
    if kind == 'insurance_base':
        # "Contractual eligible pay" is the salary the contract promises, so a
        # short month does not quietly reduce somebody's insurance. "Actual"
        # adds up what was really paid and marked as counting.
        if (amount.get('basis') or 'actual') == 'contract':
            body = _ref((amount.get('contract') or contract), ctx, needs)
        else:
            earnings = _members(ctx, {'group': 'earning', 'insurance': 'included'})
            body = _sum_of(earnings, ctx, needs)
        return 'MIN(%s,%s)' % (body, _ref(amount.get('cap'), ctx, needs))
    if kind == 'taxable_base':
        parts = _members(ctx, {'group': 'earning'})
        taxed = [_taxable_part(c, ctx, needs) for c in parts
                 if _taxable_slice_counts(c, ctx)]
        body = _sum_of(taxed, ctx, needs)
        allowed = (_members(ctx, {'group': 'deduction', 'pit_deductible': 'yes'})
                   if amount.get('deduct_contributions', True) else [])
        if allowed:
            body = '%s-%s' % (body, _sum_of(allowed, ctx, needs))
        if amount.get('relief_self'):
            body = '%s-%s' % (body, _ref(amount['relief_self'], ctx, needs))
        if amount.get('relief_dep') and amount.get('deps'):
            body = '%s-(%s*%s)' % (body, _ref(amount['deps'], ctx, needs),
                                   _ref(amount['relief_dep'], ctx, needs))
        return 'MAX(0,%s)' % body
    # A total may name components to leave out. The one that always has to be
    # named is a benefit MIRROR: the taxable value of a premium to the employee
    # is the same money the employer already pays as the premium itself, and
    # adding both charges the employer twice for one policy.
    skip = {'exclude': (amount.get('of') or {}).get('exclude') or []}
    if kind == 'net_total':
        earnings = _members(ctx, dict(skip, group='earning', cash='cash'))
        taken = _members(ctx, dict(skip, group='deduction'))
        body = _sum_of(earnings, ctx, needs)
        if taken:
            body = '%s-%s' % (body, _sum_of(taken, ctx, needs))
        return body
    if kind == 'employer_total':
        cash = _members(ctx, dict(skip, group='earning', cash='cash'))
        noncash = _members(ctx, dict(skip, group='earning', cash='noncash'))
        borne = _members(ctx, dict(skip, group='benefit'))
        body = _sum_of(cash, ctx, needs)
        if borne:
            body = '%s+%s' % (body, _sum_of(borne, ctx, needs))
        if noncash:
            body = '%s+%s' % (body, _sum_of(noncash, ctx, needs))
        return body
    raise RecipeError(_("That kind of amount is not available yet."))


def _pit_vn_expr(amount, ctx, needs):
    """The three ways Vietnamese income tax can be worked out, in one component.

    A tax resident on a contract of three months or more is taxed on the
    progressive bands. Somebody who is not a tax resident pays a flat rate on
    the whole taxable payment. Somebody on a contract shorter than three months
    has tax withheld at a flat rate once the payment reaches a threshold —
    unless they have signed the commitment that says this is their only income.

    Every route beyond the bands is optional: a configuration that has not got
    the constants for them simply taxes everybody on the bands, which is
    exactly what the Essentials starter does.
    """
    table = (amount.get('table') or '').upper()
    bands = 'ROUND(BRACKET(%s,%s),0)' % (table, _ref(amount.get('base'), ctx, needs))
    routes = amount.get('routes') or {}
    gross = routes.get('gross_base')
    body = bands

    short_rate = routes.get('short_rate')
    months = routes.get('months_input')
    if gross and short_rate and months:
        threshold = routes.get('short_threshold')
        commit = routes.get('commit_input')
        withheld = 'ROUND(%s*%s,0)' % (_ref(gross, ctx, needs),
                                       _ref(short_rate, ctx, needs))
        tests = []
        if threshold:
            tests.append('%s>=%s' % (_ref(gross, ctx, needs),
                                     _ref(threshold, ctx, needs)))
        if commit:
            tests.append('%s=0' % _ref(commit, ctx, needs))
        if len(tests) > 1:
            short = 'IF(AND(%s),%s,0)' % (','.join(tests), withheld)
        elif tests:
            short = 'IF(%s,%s,0)' % (tests[0], withheld)
        else:
            short = withheld
        body = 'IF(%s<3,%s,%s)' % (_ref(months, ctx, needs), short, body)

    nonres = routes.get('nonres_rate')
    resident = routes.get('resident_input')
    if gross and nonres and resident:
        flat = 'ROUND(%s*%s,0)' % (_ref(gross, ctx, needs),
                                   _ref(nonres, ctx, needs))
        body = 'IF(%s=0,%s,%s)' % (_ref(resident, ctx, needs), flat, body)
    return body


def _taxable_slice_counts(code, ctx):
    """False for a component that is entirely tax free."""
    recipe = (ctx.get('recipes') or {}).get(code.upper()) or {}
    return ((recipe.get('treatment') or {}).get('tax') or 'taxable') != 'exempt'


def share_pct(recipe):
    """What percentage of a shared benefit the employer carries, 0 to 100."""
    treat = (recipe or {}).get('treatment') or {}
    try:
        pct = float(treat.get('employer_share_pct', 100.0))
    except (TypeError, ValueError):
        pct = 100.0
    return min(100.0, max(0.0, pct))


def compile_recipe(recipe, ctx, share_side='employer'):
    """``(excel_formula_with_letters_or_None, needs)``.

    ``None`` means "this component has no formula of its own" — an input, a
    fixed value, or one somebody wrote in Excel. ``needs`` lists the helper
    input codes the formula names that do not exist yet; compile again once
    they do and the result is pure column letters.

    ``share_side`` decides which half of a cost-shared benefit is being asked
    for. A private health plan the employee pays 30% of is TWO lines on a
    payslip — the employer's 70% under benefits and the employee's 30% under
    deductions — and both come from the one sentence, so the two halves can
    never drift apart.
    """
    ctx = ctx if isinstance(ctx, Ctx) else Ctx(ctx or {})
    needs = []
    body = _amount_expr(recipe, ctx, needs)
    if body is None:
        return None, needs

    ceiling = (recipe.get('amount') or {}).get('max')
    if ceiling:
        body = 'MIN(%s,%s)' % (body, _ref(ceiling, ctx, needs))

    pct = share_pct(recipe)
    if share_side == 'employee':
        if pct >= 100.0:
            return None, needs
        body = '(%s*%s/100)' % (body, _num(100.0 - pct))
    elif pct < 100.0:
        body = '(%s*%s/100)' % (body, _num(pct))

    proration = recipe.get('proration') or 'none'
    if proration == 'working_days':
        body = '(%s*(%s/%s))' % (body, _ref('PAIDDAYS', ctx, needs),
                                 _ref('STDDAYS', ctx, needs))
    elif proration == 'calendar_days':
        body = '(%s*(%s/%s))' % (body, _ref('PAIDCALD', ctx, needs),
                                 _ref('MTHDAYS', ctx, needs))

    amount = recipe.get('amount') or {}
    if recipe.get('frequency') == 'annual' and amount.get('kind') != 'annual_ratio':
        month = int(amount.get('payout_month') or 1)
        body = 'IF(%s=%d,%s,0)' % (_ref('PAYMONTH', ctx, needs), month, body)
    # A payment "the scheme decides" that is worked out from a salary would
    # otherwise be paid EVERY run — a variable bonus of 10% of salary, every
    # month, for ever. When the rule names the switch the run is told about,
    # the payment waits to be told.
    if recipe.get('frequency') == 'scheme':
        switch = (recipe.get('inputs') or {}).get('run')
        if switch:
            body = 'IF(%s=1,%s,0)' % (_ref(switch, ctx, needs), body)

    test = _audience_test(recipe, ctx, needs)
    if test:
        body = 'IF(%s,%s,0)' % (test, body)

    rounding = str(recipe.get('round', '0'))
    if rounding == 'down':
        body = 'ROUNDDOWN(%s,0)' % body
    elif rounding != 'none':
        body = 'ROUND(%s,%s)' % (body, rounding)

    if int(recipe.get('sign') or 1) < 0 and share_side != 'employee':
        body = '-(%s)' % body

    return '=' + body, needs


def employee_share_formula(recipe, ctx):
    """The employee's half of a cost-shared benefit, or ``(None, [])``."""
    return compile_recipe(recipe, ctx, share_side='employee')


def taxable_helper_formula(recipe, ctx):
    """The formula for a component's ``<CODE>TX`` helper, or None.

    Only a component whose tax treatment is conditional needs one: everything
    else is either fully taxable (use the component) or fully exempt (use
    nothing), and a helper that always equals its parent is a rule somebody has
    to read and understand for no reason.
    """
    ctx = ctx if isinstance(ctx, Ctx) else Ctx(ctx or {})
    needs = []
    treat = (recipe or {}).get('treatment') or {}
    tax = treat.get('tax') or 'taxable'
    self_code = (ctx.get('self_code') or '').upper()
    if tax in ('taxable', 'exempt'):
        return None, needs
    me = _ref(self_code, ctx, needs)
    if tax == 'qualified':
        flag = _ref(slot_code(recipe, 'qual', self_code), ctx, needs)
        return '=IF(%s=1,0,%s)' % (flag, me), needs
    if tax == 'annual_cap':
        ytd = _ref(slot_code(recipe, 'ytd', self_code), ctx, needs)
        cap = _num(treat.get('cap'))
        return '=MAX(0,%s-MAX(0,%s-%s))' % (me, cap, ytd), needs
    if tax == 'entitlement':
        ent = _ref(slot_code(recipe, 'ent', self_code), ctx, needs)
        return '=MAX(0,%s-%s)' % (me, ent), needs
    if tax == 'inherit':
        # "Taxed the same way as the original" is about the TREATMENT, never
        # about the amount. Returning the source's own value here was a real
        # bug: a correction to last month's salary would have added the whole
        # of this month's salary to taxable income a second time.
        source = (treat.get('source_code') or '').upper()
        if not source:
            return None, needs
        source_tax = ((ctx.get('recipes') or {}).get(source) or {}) \
            .get('treatment', {}).get('tax') or 'taxable'
        if source_tax == 'exempt':
            return '=0', needs
        # Fully taxable, or conditional on evidence the correction does not
        # carry: either way the whole correction is taxed, which is the safe
        # answer, and `review_items` asks somebody to confirm the original.
        return None, needs
    return None, needs


# ======================================================================
#  The ORM half — one pass over a real configuration
# ======================================================================
def build_ctx(config, self_code=None, extra_recipes=None):
    """Everything :func:`compile_recipe` may know about ``config``."""
    letters, recipes, groups, types, order = {}, {}, {}, {}, []
    for rule in config.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
        code = (rule.code or '').upper()
        if not code:
            continue
        order.append(code)
        letters[code] = rule.column_letter or ''
        types[code] = rule.column_type
        recipe = rule.bp_recipe()
        if extra_recipes and code in extra_recipes:
            recipe = extra_recipes[code]
        recipes[code] = recipe
        groups[code] = derived_group(rule, recipe)
    return Ctx({
        'letters': {c: l for c, l in letters.items() if l},
        'recipes': recipes,
        'groups': groups,
        'types': types,
        'order': order,
        'rate_tables': {(t.code or '').upper() for t in config.rate_table_ids},
        'self_code': (self_code or '').upper(),
        'contract_code': DEFAULT_CONTRACT_CODE
        if DEFAULT_CONTRACT_CODE in letters else _guess_contract(letters, types),
    })


def _guess_contract(letters, types):
    for code in ('BASIC', 'BASICSALARY', 'SALARY', 'CONTRACTPAY'):
        if code in letters:
            return code
    for code, kind in types.items():
        if kind == 'input':
            return code
    return DEFAULT_CONTRACT_CODE


#: Codes that are a total whatever a configuration calls its groups.
_TOTAL_CODES = {'NET', 'GROSS', 'TAXABLE', 'EEDED', 'ERCOST', 'SIBASE', 'UIBASE'}


def derived_group(rule, recipe=None):
    """Which part of pay a component belongs to.

    The recipe answers when there is one. Otherwise the engine's own net-pay
    classification does, and finally the shape of the component itself — so a
    workbook imported with nobody's naming still lands in sensible tabs
    instead of one undifferentiated list.
    """
    if recipe and recipe.get('group'):
        return recipe['group']
    # Anything the guided setup created for its own plumbing is plumbing: it
    # must never be summed into a total it was invented to help work out.
    if getattr(rule, 'bp_template_key', '') == 'helper':
        return 'helper'
    code = (rule.code or '').upper()
    if rule.column_type in ('input', 'constant'):
        return 'helper'
    if code in _TOTAL_CODES:
        return 'total'
    role = getattr(rule, 'net_role', False)
    if role == 'net':
        return 'total'
    if role == 'deduction':
        return 'deduction'
    if role == 'employer_cost':
        return 'benefit'
    return 'earning'


def dependency_order(codes, ctx):
    """Codes sorted so that anything a recipe names comes first.

    A cycle is refused by name — "PIT needs TAXABLE, which needs PIT" is a
    sentence somebody can act on; a formula that quietly computes zero is not.
    """
    deps = {}
    for code in codes:
        recipe = (ctx.get('recipes') or {}).get(code) or {}
        deps[code] = {d for d in recipe_references(recipe, ctx) if d in codes}
    order, state = [], {}

    def visit(code, path):
        mark = state.get(code)
        if mark == 'done':
            return
        if mark == 'open':
            cycle = path[path.index(code):] + [code]
            raise RecipeError(_(
                "These components depend on each other, so no number can be "
                "worked out: %s.", ' -> '.join(cycle)))
        state[code] = 'open'
        for dep in sorted(deps.get(code, ())):
            visit(dep, path + [code])
        state[code] = 'done'
        order.append(code)

    for code in codes:
        visit(code, [])
    return order


def recipe_references(recipe, ctx):
    """Every component code a recipe names, directly or through a group."""
    amount = (recipe or {}).get('amount') or {}
    out = set()
    for key in ('base', 'link', 'cap', 'rate_code', 'relief_self',
                'relief_dep', 'deps', 'contract', 'max'):
        if amount.get(key):
            out.add(str(amount[key]).upper())
    for code in ((recipe or {}).get('inputs') or {}).values():
        if code:
            out.add(str(code).upper())
    for code in (amount.get('routes') or {}).values():
        if code:
            out.add(str(code).upper())
    treat = (recipe or {}).get('treatment') or {}
    if treat.get('source_code'):
        out.add(str(treat['source_code']).upper())
    kind = amount.get('kind')
    filters = {
        'sum_group': (amount.get('of') or {},),
        'insurance_base': ()
        if (amount.get('basis') or 'actual') == 'contract'
        else ({'group': 'earning', 'insurance': 'included'},),
        'taxable_base': ({'group': 'earning'},
                         {'group': 'deduction', 'pit_deductible': 'yes'}),
        'net_total': ({'group': 'earning'}, {'group': 'deduction'}),
        'employer_total': ({'group': 'earning'}, {'group': 'benefit'}),
    }.get(kind)
    if kind in ('net_total', 'employer_total'):
        skip = (amount.get('of') or {}).get('exclude') or []
        filters = tuple(dict(one, exclude=skip) for one in filters)
    for one in (filters or ()):
        out |= set(_members(ctx, one))
    return out


def regenerate(env, config, reason='refactor', extra_recipes=None):
    """Rewrite every generated formula in ``config``. -> report dict.

    Returns ``{'changed': [codes], 'problems': [{'code', 'message'}]}``. A
    formula the engine's own checker refuses is NOT written: the previous one
    stays and the refusal is reported by name, because a component that stops
    computing is worse than one that is out of date.
    """
    Studio = env['pb.formula.studio']
    ctx = build_ctx(config, extra_recipes=extra_recipes)
    by_code = {(r.code or '').upper(): r for r in config.rule_ids if r.code}
    with_recipes = [c for c in ctx.order if (ctx.get('recipes') or {}).get(c)]
    ordered = dependency_order(with_recipes, ctx)

    changed, problems = [], []
    seen = set()
    for code in ordered:
        rule = by_code.get(code)
        if not rule or rule.column_type != 'formula':
            continue
        recipe = (ctx.get('recipes') or {})[code]
        try:
            ctx['self_code'] = code
            formula, needs = compile_recipe(recipe, ctx)
        except RecipeError as exc:
            problems.append({'code': code, 'message': str(exc)})
            continue
        finally:
            ctx['self_code'] = ''
        if formula is None:
            continue
        if needs:
            problems.append({'code': code, 'message': _(
                "This rule needs an input that does not exist yet: %s.",
                ', '.join(needs))})
            continue
        ok, message = Studio._check_formula(config, formula, exclude_id=rule.id)
        if not ok:
            problems.append({'code': code, 'message': message or _(
                "The engine could not read the formula this rule produces.")})
            continue
        normalised = rule._normalize_excel_formula(formula)
        current = rule._normalize_excel_formula(rule.excel_formula or '')
        vals = {'bp_generated_formula': formula}
        if rule.bp_formula_source == 'generated' and normalised != current:
            vals['excel_formula'] = formula
            # `bp_formula_source` is passed EXPLICITLY, and it has to be. The
            # rule's own write() guard flips anything that writes a formula
            # other than `bp_generated_formula` to "manual" — and on the very
            # first pass `bp_generated_formula` is still empty, so without this
            # line regeneration marks its own output as somebody's hand-written
            # Excel and never touches it again.
            vals['bp_formula_source'] = 'generated'
            vals['bp_generated_revision'] = (rule.bp_generated_revision or 0) + 1
            changed.append(code)
        rule.with_context(formula_version_reason=reason,
                          formula_version_seen=seen).write(vals)

    try:
        config.action_regenerate_formulas()
        config.action_validate_formulas()
    except Exception as exc:                    # pragma: no cover - advisory
        _logger.info("Guided setup: post-regeneration pass reported: %s", exc)
    config.invalidate_recordset(['has_errors', 'has_circular_refs'])
    return {'changed': changed, 'problems': problems}


def helper_defaults(code):
    """The value a helper input starts at, whatever kind of helper it is."""
    code = (code or '').upper()
    if code in HELPER_INPUTS:
        return HELPER_INPUTS[code]
    for suffix, value in HELPER_SUFFIXES.items():
        if code.endswith(suffix):
            return value
    return 0.0


def dumps(recipe):
    return json.dumps(recipe, sort_keys=True)
