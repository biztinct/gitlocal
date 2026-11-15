# -*- coding: utf-8 -*-
"""WDGAP S8-A — "Build from a total": from a yearly (or monthly) total package
to the contract's pay lines, worked out through the scheme's OWN formulas.

The India case ("cost to company"): the person agrees ₹12,00,000 a year; HR
needs basic, the allowances that ride on it, and the one balancing item
("special allowance") so that 12 × (gross pay + the employer's contributions)
IS the total. This is not a one-unknown search the person has to set up:

* basic is chosen (a share of the monthly total, or a fixed amount);
* everything the scheme derives from basic (HRA = x% of basic, provident fund
  on min(basic, ceiling), insurance) is worked out by the scheme itself;
* ONE balancing item takes the rest — found with the W2-C search
  (`pb_formula_studio.take_home_solver.solve`, reused as-is), whose function
  is "monthly total of an in-memory payslip with the balancing item = x".

THE TOTAL IS DEFINED FROM THE ONE TOTALS RULE (`pb_pay_totals` bands): gross
pay + the employer-contribution band. A scheme whose "employer cost" line
already ADDS gross (the India pack's ``ERCOST = GROSS + EPFCOMP + ESICOMP``)
would count gross twice if that line carried the employer-contribution role,
so an employer line that reaches gross pay is a TOTAL line, not a
contribution, and is left out of the sum (said on screen, pinned by a test).

IT IS A CALCULATOR (read-only, like W2-C): engine runs on the compiled
read-only program and in-memory payslip lines. "Use these figures" stages the
wage and the pay lines in the OPEN contract drawer; they are written by the
drawer's own Save, through the contract's normal approval.
"""
import logging
import time

from odoo import _, api, models

from odoo.addons.pb_formula_studio.models import take_home_solver as solver
from odoo.addons.pb_formula_studio.models.take_home import _Engine, _num
from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics

_logger = logging.getLogger(__name__)

#: Bands that make up gross pay and the employer's side.
GROSS_BANDS = ('GROSS', 'BASIC', 'ALW')
EMPLOYER_BAND = 'ERCOST'
#: Words that usually name the balancing item.
BALANCE_WORDS = ('SPECIAL', 'SPL', 'BALANC', 'FLEX', 'OTHER ALLOW')


class PbPayPackage(models.AbstractModel):
    _name = 'pb.pay.package'
    _description = 'Build pay from a total package'

    @api.model
    def _studio(self):
        return self.env['pb.formula.studio']

    # ============================================================== totals
    @api.model
    def _totals(self, engine, results, decimals):
        """``{gross, employer, total, net, left_out: [names]}`` for one
        evaluation. Employer lines that reach gross pay are totals of their
        own and are left out (the definition hazard above)."""
        lines = engine.lines(results)
        totals = lines.pb_pay_totals()
        gross = totals.get('gross', 0.0) or 0.0
        unit = 10.0 ** (-int(decimals or 0))
        employer, left_out = 0.0, []
        for line in lines:
            if not line.pb_counts_in_totals() or line.pb_pay_band() != EMPLOYER_BAND:
                continue
            amount = abs(line.total or 0.0)
            if gross > 0 and amount >= gross - unit:
                left_out.append(line.name or line.code)
                continue
            employer += amount
        return {'gross': gross, 'employer': employer, 'total': gross + employer,
                'net': totals.get('net', 0.0) or 0.0, 'left_out': left_out}

    @api.model
    def _default_balance(self, items, basic):
        for rule in items:
            if rule.code == basic:
                continue
            text = ('%s %s' % (rule.code or '', rule.name or '')).upper()
            if any(word in text for word in BALANCE_WORDS):
                return rule.code
        return False

    @api.model
    def _subject(self, contract_id, config_id=False):
        subject, refusal = self._studio()._th_subject(config_id or False, False, contract_id)
        if refusal and refusal.get('reason') == 'no_scheme':
            # The shared refusal speaks of take-home; this card builds a total.
            refusal = dict(refusal, msg=_(
                "No pay scheme pays this person yet, so there is nothing to build "
                "the total with. Put their team on a pay scheme first."))
        return subject, refusal

    # ================================================================ open
    @api.model
    def package_open(self, contract_id, config_id=False):
        """What the dialog needs before anything is typed. Read-only."""
        Studio = self._studio()
        subject, refusal = self._subject(contract_id, config_id)
        if refusal:
            return refusal
        config = subject['config']
        currency = config.scheme_currency()
        decimals = int(currency.get('decimals') or 0)
        items = Studio._th_items(config)
        if len(items) < 2:
            return Studio._th_refusal('no_items', _(
                "This pay scheme does not have the pay items a total can be "
                "split into (it needs at least a basic pay and one item that "
                "takes the rest)."))
        engine = _Engine(self.env, config)
        if not any(s['band'] in GROSS_BANDS for s in engine.specs):
            return Studio._th_refusal('no_gross', _(
                "This pay scheme has no gross pay line, so a total package "
                "cannot be worked out on it."))
        results = engine.evaluate(subject['inputs'])
        now = self._totals(engine, results, decimals)
        basic = Studio._th_default_item(config, subject['wage_codes'])
        schemes = [{'id': s.id, 'name': s.display_name or s.name or ''}
                   for s in Studio._th_schemes_for(subject['contract'])] \
            if subject['contract'] else []
        return {
            'ok': True,
            'who': subject['employee'].display_name or _('Employee'),
            'scheme': {'id': config.id, 'name': config.display_name or config.name or ''},
            'schemes': schemes,
            'currency': currency,
            'items': [{'code': r.code, 'name': r.name or r.code,
                       'current': _num(results.get(r.code, 0.0)),
                       'is_wage': r.code in subject['wage_codes']} for r in items],
            'basic': basic,
            'balance': self._default_balance(items, basic),
            'basic_share': 50,
            'now': dict(now, year=now['total'] * 12),
            'source_label': Studio._th_source_label(subject),
        }

    # =============================================================== solve
    @api.model
    def package_solve(self, contract_id, total=0.0, period='year', basic_mode='share',
                      basic_value=50.0, basic_code=False, balance_code=False,
                      config_id=False):
        """Find the balancing item so that the monthly total equals the
        target, with basic fixed. Read-only; the answer is evaluated once more
        on its own before it is reported."""
        started = time.monotonic()
        Studio = self._studio()
        subject, refusal = self._subject(contract_id, config_id)
        if refusal:
            return refusal
        config = subject['config']
        currency = config.scheme_currency()
        decimals = int(currency.get('decimals') or 0)
        money = lambda v: Studio._th_money(v, currency)     # noqa: E731
        items = {r.code: r for r in Studio._th_items(config)}
        basic = items.get(basic_code or '')
        balance = items.get(balance_code or '')
        if not basic:
            return Studio._th_refusal('no_basic', _("Pick the pay item that is basic pay."))
        if not balance:
            return Studio._th_refusal('no_balance', _("Pick the pay item that takes the rest."))
        if basic.code == balance.code:
            return Studio._th_refusal('same', _(
                "Basic pay and the item that takes the rest must be two different pay items."))
        try:
            total = float(total)
        except (TypeError, ValueError):
            total = 0.0
        if total <= 0:
            return Studio._th_refusal('bad_target', _(
                "Type the total package, as an amount above zero."))
        monthly = total / 12.0 if period == 'year' else total
        monthly = excel_semantics.excel_round(monthly, decimals)
        try:
            basic_value = float(basic_value or 0.0)
        except (TypeError, ValueError):
            basic_value = 0.0
        if basic_mode == 'share':
            if not 0 < basic_value <= 100:
                return Studio._th_refusal('bad_share', _(
                    "Basic pay is a share of the total from 1% to 100%."))
            basic_amount = excel_semantics.excel_round(monthly * basic_value / 100.0, decimals)
        else:
            if basic_value <= 0:
                return Studio._th_refusal('bad_basic', _("Type basic pay as an amount above zero."))
            basic_amount = excel_semantics.excel_round(basic_value, decimals)

        engine = _Engine(self.env, config)
        inputs = dict(subject['inputs'])
        names = {r.code: (r.name or r.code) for r in engine.rules}
        feeding = engine.upstream([s['code'] for s in engine.specs
                                   if s['band'] in GROSS_BANDS + (EMPLOYER_BAND,)])

        def broken(results):
            errs = engine.diagnose(results)
            hit = sorted(code for code in errs if code in feeding)
            return (hit[0], errs) if hit else (None, errs)

        before_results = engine.evaluate(inputs)
        bad, errs = broken(before_results)
        if bad:
            return Studio._th_refusal('formula_error', _(
                "The total cannot be worked out: the formula for “%(name)s” has "
                "an error for this person (%(why)s). Fix it in Formula Studio first.",
                name=names.get(bad, bad), why=Studio._th_why(errs[bad])))

        base = dict(inputs)
        base[basic.code] = basic_amount
        for code in subject['wage_codes']:
            if code == basic.code:
                base[code] = basic_amount

        def total_of(x):
            trial = dict(base)
            trial[balance.code] = x
            return self._totals(engine, engine.evaluate(trial), decimals)['total']

        found = solver.solve(total_of, monthly, decimals=decimals)
        outcome = found['outcome']
        out = {
            'ok': True, 'outcome': outcome, 'currency': currency,
            'target': monthly, 'target_year': monthly * 12, 'evals': found['evals'],
            'basic': {'code': basic.code, 'name': basic.name or basic.code, 'value': basic_amount},
            'balance': {'code': balance.code, 'name': balance.name or balance.code},
            'rows': [], 'lines': [], 'before': {}, 'after': {}, 'note': '',
            'can_use': False, 'use': None,
        }
        bname, xname = basic.name or basic.code, balance.name or balance.code
        if outcome == solver.GARBAGE:
            out.update(ok=False, reason='garbage', msg=_(
                "This scheme does not give a total that is a number for this "
                "person, so nothing can be worked out."))
            return out

        value = found.get('value')
        if value is not None and outcome in (solver.EXACT, solver.CLOSEST, solver.LIMIT):
            after_inputs = dict(base)
            after_inputs[balance.code] = value
            after_results = engine.evaluate(after_inputs)
            bad, errs = broken(after_results)
            if bad:
                return Studio._th_refusal('formula_error', _(
                    "The total cannot be worked out: the formula for “%(name)s” "
                    "has an error at %(value)s (%(why)s). Fix it in Formula Studio first.",
                    name=names.get(bad, bad), value=money(value), why=Studio._th_why(errs[bad])))
            before = self._totals(engine, before_results, decimals)
            after = self._totals(engine, after_results, decimals)
            out['before'] = dict(before, year=before['total'] * 12)
            out['after'] = dict(after, year=after['total'] * 12)
            out['value'] = value
            out['lines'] = Studio._th_lines(engine, before_results, after_results, decimals)
            unit = 10.0 ** (-decimals)
            for code in sorted(set(engine.rules.filtered(
                    lambda r: r.column_type == 'input').mapped('code')) & set(items)):
                b = _num(before_results.get(code, 0.0))
                a = _num(after_results.get(code, 0.0))
                if abs(a - b) >= unit / 2.0 or code in (basic.code, balance.code):
                    out['rows'].append({'code': code, 'name': names.get(code, code),
                                        'before': b, 'after': a,
                                        'changed': abs(a - b) >= unit / 2.0})
            if after['left_out']:
                out['note'] = _(
                    "“%(names)s” already adds gross pay, so it is a total of its "
                    "own and is not counted again.", names=', '.join(after['left_out']))
            if found.get('below'):
                out['below'] = found['below']

        target_text = money(monthly)
        year_text = money(monthly * 12)
        if outcome == solver.EXACT:
            out['sentence'] = _(
                "A total of %(year)s a year (%(month)s a month) needs %(item)s of "
                "%(value)s, with %(basic)s at %(basic_value)s.",
                year=year_text, month=target_text, item=xname, value=money(value),
                basic=bname, basic_value=money(basic_amount))
        elif outcome == solver.CLOSEST:
            below = found['below']
            out['sentence'] = _(
                "%(month)s a month cannot be reached exactly: the scheme's "
                "rounding jumps over it. Closest: %(item)s %(v1)s gives %(n1)s; "
                "%(item)s %(v2)s gives %(n2)s.", month=target_text, item=xname,
                v1=money(below['value']), n1=money(below['net']),
                v2=money(value), n2=money(found['net']))
        elif outcome == solver.LIMIT:
            out['sentence'] = _("Stopped after %(n)s tries without settling on a figure.",
                                n=solver.MAX_EVALS)
        elif outcome == solver.BAD_TARGET:
            out.update(ok=False, msg=_("Type the total package, as an amount above zero."))
        else:
            why = found.get('why')
            if why == solver.WHY_ABOVE:
                out['sentence'] = _(
                    "%(basic)s at %(basic_value)s and what the scheme adds to it "
                    "already cost %(now)s a month, more than %(month)s. Lower the "
                    "share for basic pay.", basic=bname, basic_value=money(basic_amount),
                    now=money(found['net']), month=target_text)
            elif why == solver.WHY_FLAT:
                out['sentence'] = _(
                    "The total does not change when %(item)s changes, so it cannot "
                    "take the rest. Pick another pay item.", item=xname)
            elif why == solver.WHY_DOWN:
                out['sentence'] = _(
                    "The total goes down when %(item)s goes up, so it cannot take "
                    "the rest. Pick a pay item that adds to pay.", item=xname)
            else:
                out['sentence'] = _(
                    "Even with %(item)s at %(value)s the total is %(now)s a month, "
                    "below %(month)s.", item=xname, value=money(found['value']),
                    now=money(found['net']), month=target_text)

        if outcome in (solver.EXACT, solver.CLOSEST) and value is not None \
                and subject['contract']:
            wage = basic_amount if basic.code in subject['wage_codes'] else None
            use_items = [{'code': balance.code, 'name': xname, 'amount': value}]
            if basic.code not in subject['wage_codes']:
                use_items.insert(0, {'code': basic.code, 'name': bname, 'amount': basic_amount})
            # A pay item the contract does not hold (not a contract pay line in
            # this scheme) cannot be put on the contract: say so, offer nothing.
            off = [it['name'] for it in use_items
                   if not getattr(items[it['code']], 'is_contract_component', True)]
            if off:
                out['note'] = ((out['note'] + ' ') if out['note'] else '') + _(
                    "%(items)s is not kept on the contract in this pay scheme, so "
                    "these figures cannot be filled in from here.", items=', '.join(off))
            else:
                out['use'] = {'wage': wage, 'items': use_items}
                out['can_use'] = True
        out['ms'] = int((time.monotonic() - started) * 1000)
        return out
