# -*- coding: utf-8 -*-
"""WDGAP W2-C — "Work back from take-home" (net to gross), the server half.

A customer agrees a take-home figure with a person ("12,000,000 net") and needs
the pay item value that produces it under the scheme's OWN tax and insurance
formulas. This file answers that question for ONE person and ONE pay item.

IT IS A CALCULATOR. Nothing here writes: the person's figures come from a
payslip's stored inputs (the Formula Studio real-pay preview reading) or from
their contract, every evaluation runs on the compiled read-only program
(``hr.formula.config._pb_formula_steps`` + ``formula_program.run_sample``, the
"fastest loop" of the PR facts §3) and take-home is read off in-memory payslip
lines (``.new()``, never saved) through THE one totals rule,
``hr.payslip.line.pb_pay_totals`` (memory ``one-pay-band-rule``). A wage that
the person chooses to use is copied into the OPEN contract form by the client
and saved, or sent for approval, the usual way — never from here.

The search lives in ``take_home_solver`` (no ORM, provably bounded). This layer:

* gates the call (pay team only; the person, payslip, contract and scheme
  must belong to one of the user's companies);
* builds ``net_of(x)`` — the scheme's take-home with the chosen pay item = x;
* refuses BEFORE solving when a formula that take-home depends on raises for
  this person. The compiled path turns every error into 0 (PR facts §3
  gotcha), and so does ``_run_formula`` (formula_rule.py ``_run_formula``
  returns 0.0 from its own except), so the ``errors=`` out-parameter of
  ``_evaluate_rules_with_dependencies`` is never filled on either path. The
  probe here re-runs each compiled formula ONCE with errors let through;
* turns the outcome into one plain sentence and a before/after payslip.
"""
import json
import logging
import time

from odoo import Command, _, api, models
from odoo.exceptions import AccessError

from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics
from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier

from . import take_home_solver as solver

_logger = logging.getLogger(__name__)

#: Who may use the calculator: the pay team. Formula users imply it.
PAY_TEAM_GROUP = 'om_hr_payroll.group_hr_payroll_user'

#: The input codes the no-file pay run fills from the contract wage
#: (`hr_payslip_formula._get_formula_input_values`, the `contract_mapping`
#: dict). A component mapped to the contract's wage field is the other way.
WAGE_CODES = ('BASIC', 'WAGE', 'BASE')

#: Band (pb_pay_band) -> what the card calls a line.
_BAND_KIND = {'GROSS': 'earning', 'BASIC': 'earning', 'ALW': 'earning',
              'DED': 'deduction', 'NET': 'net', 'ERCOST': 'employer'}


def _num(value):
    """A component value as a number for a payslip line (text reads as 0)."""
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class _Engine:
    """One scheme, compiled once; evaluated as many times as the search asks.

    Holds no state between requests. Built inside an ORM call and dropped at
    its end.
    """

    def __init__(self, env, config):
        from odoo.addons.pb_hr_payroll_formula.models import formula_program
        self.env = env
        self.config = config
        self.rules = config.rule_ids
        self._run = formula_program.run_sample
        # Compiled ONCE: topological order, Excel -> Python, safety check.
        self.steps = config._pb_formula_steps(self.rules)
        self.Slip = env['hr.payslip'].sudo()
        # The lines a real payslip gets — the same filter as
        # `_create_payslip_lines_from_formulas`: on the payslip, and a number.
        specs = []
        for rule in self.rules.sorted(lambda r: (r.sequence, r.id)):
            if not rule.code or not rule.appears_on_payslip:
                continue
            if not value_kind_classifier.wants_number(
                    getattr(rule, 'value_kind', None)):
                continue
            specs.append({
                'code': rule.code,
                'name': rule.name or rule.code,
                'category_id': rule.category_id.id or False,
                'component_detail': bool(rule.net_role_detail),
                'pay_role': rule.net_role or False,
            })
        # Each line's band is asked of the product's own helper, once, on an
        # in-memory line: the classification is never re-derived here.
        for spec in specs:
            probe = self._line(spec, 0.0)
            spec['band'] = probe.pb_pay_band() or False
            spec['counts'] = bool(probe.pb_counts_in_totals())
        self.specs = specs
        self.net_specs = [s for s in specs if s['band'] == 'NET']

    # ---------------------------------------------------------------- lines
    @staticmethod
    def _line_vals(spec, amount):
        return {
            'name': spec['name'], 'code': spec['code'],
            'category_id': spec['category_id'],
            'amount': amount, 'quantity': 1.0, 'rate': 100.0,
            'component_detail': spec['component_detail'],
            'pay_role': spec['pay_role'],
        }

    def _line(self, spec, amount):
        return self._slip_lines([self._line_vals(spec, amount)])

    def _slip_lines(self, vals_list):
        """Lines of an in-memory payslip (``.new()``, never saved).

        The lines must BELONG to a payslip: pb_payruns' `pb_pay_totals`
        totals per `slip_id` and answers 0 for lines that have none (and so
        did the offer calculator's subtotals — see the W2-C report).
        """
        slip = self.Slip.new({'line_ids': [Command.create(v) for v in vals_list]})
        return slip.line_ids

    def lines(self, results, specs=None):
        return self._slip_lines([
            self._line_vals(spec, _num(results.get(spec['code'], 0.0)))
            for spec in (self.specs if specs is None else specs)])

    # ----------------------------------------------------------- evaluating
    def evaluate(self, inputs):
        return self._run(self.steps, inputs, None)

    def net(self, results):
        """Take-home, read the one way the product reads it."""
        return self.lines(results, self.net_specs).pb_pay_totals()['net']

    def totals(self, results):
        return self.lines(results).pb_pay_totals()

    # ------------------------------------------------------------- the probe
    def diagnose(self, results):
        """``{code: why}`` for every formula that RAISES on these figures.

        Re-runs each compiled formula once against the final figures, the way
        `formula_program._evaluate` does, but lets the exception through
        instead of answering 0. A formula whose text cannot be converted at
        all is reported too ('unreadable'). `why` is a word, never the raw
        exception, so no technical text reaches a person.
        """
        coerce = excel_semantics.coerce_value
        coerced = {k: coerce(v) for k, v in results.items()}
        errors = {}
        for step in self.steps:
            # step = (rule, code, column_type, letter, default, constant,
            #         excel_formula, compiled, globals_template) — build_steps.
            if step[2] != 'formula':
                continue
            entry = step[7]
            if not entry or entry[0] != 'ok':
                if (step[6] or '').strip().strip('='):
                    errors[step[1]] = 'unreadable'
                continue
            scope = dict(step[8])
            scope['values'] = dict(coerced)
            scope['raw_values'] = dict(results)
            try:
                eval(entry[1], scope)       # noqa: S307 — compiled + checked by build_steps
            except ZeroDivisionError:
                errors[step[1]] = 'zero'
            except Exception:               # noqa: BLE001
                errors[step[1]] = 'other'
        return errors

    def upstream(self, codes):
        """Every component take-home depends on (inclusive), by code.

        From each formula's stored dependency list, which over-reports (it
        also lists words that look like codes) — over-reporting only makes
        the error refusal stricter, never laxer.
        """
        by_code = {r.code: r for r in self.rules if r.code}
        by_letter = {(r.column_letter or '').upper(): r.code
                     for r in self.rules if r.column_letter and r.code}
        seen, todo = set(), list(codes)
        while todo:
            code = todo.pop()
            if code in seen or code not in by_code:
                continue
            seen.add(code)
            for token in (by_code[code].formula_dependencies or '').split(','):
                token = token.strip().upper()
                if not token:
                    continue
                ref = by_letter.get(token) or (token if token in by_code else None)
                if ref and ref not in seen:
                    todo.append(ref)
        return seen


class PbFormulaStudioTakeHome(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    # =================================================================
    # gates
    # =================================================================
    @api.model
    def _th_may_use(self):
        user = self.env.user
        return bool(user.has_group(PAY_TEAM_GROUP) or user._is_admin())

    @api.model
    def _th_refusal(self, reason, msg):
        return {'ok': False, 'reason': reason, 'msg': msg}

    @api.model
    def _th_in_my_companies(self, *records):
        allowed = self.env.companies
        for record in records:
            if not record:
                continue
            company = record.sudo().company_id
            if company and company not in allowed:
                return False
        return True

    # =================================================================
    # the subject: whose figures, which scheme
    # =================================================================
    @api.model
    def _th_subject(self, config_id=False, payslip_id=False, contract_id=False):
        """``(subject, refusal)``. Exactly one of the two is set.

        subject = {config, inputs, employee, contract, slip, source, wage}.
        """
        if not self._th_may_use():
            return None, self._th_refusal('rights', _(
                "Working back from take-home is for the pay team. Ask an "
                "administrator for a payroll role."))
        # Read under sudo AFTER the gate: the rights question this calculator
        # asks is "pay team, in one of my companies" (checked explicitly
        # below), not whether the scheme's own ACL happens to cover a payroll
        # officer who never edits formulas.
        Config = self.env['hr.formula.config'].sudo()
        slip = self.env['hr.payslip'].sudo()
        contract = self.env['hr.contract'].sudo()
        try:
            if payslip_id:
                slip = slip.browse(int(payslip_id)).exists()
                if not slip:
                    return None, self._th_refusal('gone', _(
                        "That payslip is no longer there."))
            if contract_id:
                contract = contract.browse(int(contract_id)).exists()
                if not contract:
                    return None, self._th_refusal('gone', _(
                        "That contract is no longer there."))
            employee = (slip.employee_id if slip else contract.employee_id).sudo()
            if not self._th_in_my_companies(slip, contract, employee):
                return None, self._th_refusal('company', _(
                    "This person belongs to a company you do not work in."))

            config = Config.browse(int(config_id)).exists() if config_id else Config
            if not config and slip:
                config = slip.formula_config_id
            if not config and contract:
                config = self._th_schemes_for(contract)[:1]
            if not config:
                return None, self._th_refusal('no_scheme', _(
                    "No pay scheme pays this person yet, so there is no "
                    "take-home to work back from."))
            if not self._th_in_my_companies(config):
                return None, self._th_refusal('company', _(
                    "This pay scheme belongs to a company you do not work in."))
        except AccessError:
            return None, self._th_refusal('company', _(
                "You cannot see this person's pay."))

        inputs, source, slip_used = {}, 'contract', slip
        if not slip_used and contract:
            # The person's latest payslip from THIS scheme carries every other
            # figure (hours, allowances, dependants) — the truest "everything
            # else stays as it is". A person never paid by it starts from the
            # scheme's defaults and the contract's own amounts.
            slip_used = self.env['hr.payslip'].sudo().search([
                ('employee_id', '=', contract.employee_id.id),
                ('formula_config_id', '=', config.id),
                ('state', '!=', 'cancel'),
                ('formula_input_values', '!=', False),
            ], order='date_to desc, id desc', limit=1)
        if slip_used:
            try:
                inputs = json.loads(slip_used.formula_input_values or '{}')
            except (TypeError, ValueError):
                inputs = {}
            if not isinstance(inputs, dict):
                inputs = {}
            source = 'payslip'
        elif contract:
            try:
                Batch = self.env['hr.payroll.import.batch'].sudo()
                inputs = dict(Batch._contract_component_values(contract, config=config) or {})
            except Exception:       # noqa: BLE001 — a calculator never breaks on this
                _logger.warning("W2-C: contract amounts unreadable for %s",
                                contract.id, exc_info=True)
                inputs = {}
        wage_codes = self._th_wage_codes(config)
        if contract:
            for code in wage_codes:
                inputs[code] = contract.wage or 0.0
        return {
            'config': config, 'inputs': inputs, 'employee': employee,
            'contract': contract, 'slip': slip_used, 'source': source,
            'wage_codes': wage_codes,
        }, None

    @api.model
    def _th_schemes_for(self, contract):
        Config = self.env['hr.formula.config']
        schemes = Config.browse()
        if hasattr(Config, 'schemes_for_employee'):
            try:
                schemes = Config.schemes_for_employee(contract.employee_id)
            except Exception:       # noqa: BLE001
                schemes = Config.browse()
        if not schemes:
            last = self.env['hr.payslip'].sudo().search([
                ('employee_id', '=', contract.employee_id.id),
                ('formula_config_id', '!=', False),
                ('state', '!=', 'cancel'),
            ], order='date_to desc, id desc', limit=1)
            schemes = last.formula_config_id
        return schemes.sudo()

    # =================================================================
    # the pay items
    # =================================================================
    @api.model
    def _th_items(self, config):
        """The pay items a person can change: number inputs, in scheme order."""
        out = []
        for rule in config.rule_ids.sorted(lambda r: (r.sequence, r.id)):
            if rule.column_type != 'input' or not rule.code:
                continue
            if rule.is_text_component or not value_kind_classifier.wants_number(
                    getattr(rule, 'value_kind', None)):
                continue
            out.append(rule)
        return out

    @api.model
    def _th_wage_codes(self, config):
        """The input codes a pay run fills from the CONTRACT's wage.

        Two ways, both read the same way the pay run reads them: the no-file
        path's fixed codes, and a mapping of a component onto the contract's
        wage field (the record lane).
        """
        codes = [r.code for r in self._th_items(config)
                 if (r.code or '').upper() in WAGE_CODES]
        Mapping = self.env.get('hr.payslip.import.mapping')
        if Mapping is not None:
            try:
                rows = Mapping.sudo().search([
                    ('salary_structure_id', '=', config.id),
                    ('destination_type', '=', 'field'),
                    ('target_model_id.model', '=', 'hr.contract'),
                    ('target_field_id.name', '=', 'wage'),
                    ('component_id', '!=', False),
                ])
                for row in rows:
                    code = row.component_id.code
                    if code and code not in codes and row.component_id.column_type == 'input':
                        codes.append(code)
            except Exception:       # noqa: BLE001 — optional lane
                _logger.debug("W2-C: wage mappings unreadable", exc_info=True)
        return codes

    @api.model
    def _th_default_item(self, config, wage_codes):
        items = self._th_items(config)
        if not items:
            return False
        for code in wage_codes:
            if any(r.code == code for r in items):
                return code
        is_base = getattr(config, '_net_role_is_base_pay', None)
        if is_base:
            for rule in items:
                try:
                    if is_base(rule):
                        return rule.code
                except Exception:       # noqa: BLE001
                    break
        return False

    # =================================================================
    # money in a sentence
    # =================================================================
    @api.model
    def _th_money(self, amount, currency):
        decimals = int(currency.get('decimals') or 0)
        value = excel_semantics.excel_round(amount or 0.0, decimals)
        text = '{:,.{d}f}'.format(abs(value), d=decimals)
        sign = '-' if value < 0 else ''
        symbol = currency.get('symbol') or ''
        if not symbol:
            return sign + text
        if currency.get('position') == 'before':
            return '%s%s%s' % (sign, symbol, text)
        return '%s%s %s' % (sign, text, symbol)

    @api.model
    def _th_why(self, why):
        if why == 'zero':
            return _("it divides by zero")
        if why == 'unreadable':
            return _("the formula cannot be read")
        return _("it cannot be worked out")

    # =================================================================
    # public: open the card
    # =================================================================
    @api.model
    def take_home_open(self, config_id=False, payslip_id=False, contract_id=False):
        """What the card needs to draw itself before anything is typed."""
        subject, refusal = self._th_subject(config_id, payslip_id, contract_id)
        if refusal:
            return refusal
        config = subject['config']
        currency = config.scheme_currency()
        items = self._th_items(config)
        if not items:
            return self._th_refusal('no_items', _(
                "This scheme has no pay item that can be changed, so there is "
                "nothing to work back."))
        engine = _Engine(self.env, config)
        results = engine.evaluate(subject['inputs'])
        totals = engine.totals(results) if engine.net_specs else {}
        schemes = []
        if subject['contract']:
            for scheme in self._th_schemes_for(subject['contract']):
                schemes.append({'id': scheme.id, 'name': scheme.display_name or scheme.name or ''})
        return {
            'ok': True,
            'who': subject['employee'].display_name or _('Employee'),
            'source': subject['source'],
            'source_label': self._th_source_label(subject),
            'scheme': {'id': config.id, 'name': config.display_name or config.name or ''},
            'schemes': schemes,
            'currency': currency,
            'items': [{'code': r.code, 'name': r.name or r.code,
                       'current': _num(results.get(r.code, 0.0))} for r in items],
            'item': self._th_default_item(config, subject['wage_codes']),
            'wage_codes': subject['wage_codes'],
            'has_net': bool(engine.net_specs),
            'current': {'net': totals.get('net', 0.0),
                        'gross': totals.get('gross', 0.0)},
        }

    @api.model
    def _th_source_label(self, subject):
        slip = subject['slip']
        if subject['source'] == 'payslip' and slip:
            from odoo.tools.misc import format_date
            when = format_date(self.env, slip.date_from) if slip.date_from else ''
            return _("Everything else as on the payslip of %s", when) if when \
                else _("Everything else as on the latest payslip")
        return _("Everything else from the contract and the scheme's usual values")

    # =================================================================
    # public: solve
    # =================================================================
    @api.model
    def take_home_solve(self, config_id=False, target=0.0, item_code=False,
                        payslip_id=False, contract_id=False):
        """Find the value of ``item_code`` that gives take-home ``target``.

        Read-only (R1). The answer is snapped to the currency and evaluated
        once more, so the take-home reported is the real take-home of the
        figure reported (R2).
        """
        started = time.monotonic()
        subject, refusal = self._th_subject(config_id, payslip_id, contract_id)
        if refusal:
            return refusal
        config = subject['config']
        currency = config.scheme_currency()
        decimals = int(currency.get('decimals') or 0)
        money = lambda v: self._th_money(v, currency)       # noqa: E731

        items = {r.code: r for r in self._th_items(config)}
        item = items.get(item_code or '')
        if not item:
            return self._th_refusal('no_item', _(
                "Pick the pay item to change."))
        item_name = item.name or item.code
        try:
            target = float(target)
        except (TypeError, ValueError):
            target = 0.0

        engine = _Engine(self.env, config)
        if not engine.net_specs:
            return self._th_refusal('no_net', _(
                "This scheme has no take-home line, so there is nothing to "
                "work back from."))
        inputs = dict(subject['inputs'])
        before_value = _num(inputs.get(item.code, item.default_value or 0.0))

        # -- refuse on a formula that raises for this person (FACTS §3 gotcha)
        feeding = engine.upstream([s['code'] for s in engine.net_specs])
        names = {r.code: (r.name or r.code) for r in engine.rules}

        def broken(results):
            errs = engine.diagnose(results)
            hit = sorted(code for code in errs if code in feeding)
            return hit[0] if hit else None, errs

        before_results = engine.evaluate(inputs)
        bad, _errs = broken(before_results)
        if bad:
            return self._th_refusal('formula_error', _(
                "Take-home cannot be worked back: the formula for “%(name)s” "
                "has an error for this person (%(why)s). Fix it in Formula "
                "Studio first.", name=names.get(bad, bad),
                why=self._th_why(_errs[bad])))

        def net_of(x):
            trial = dict(inputs)
            trial[item.code] = x
            return engine.net(engine.evaluate(trial))

        found = solver.solve(net_of, target, decimals=decimals)
        outcome = found['outcome']
        out = {
            'ok': True, 'outcome': outcome,
            'target': excel_semantics.excel_round(target, decimals),
            'item': {'code': item.code, 'name': item_name},
            'currency': currency, 'evals': found['evals'],
            'note': '', 'lines': [], 'before': {}, 'after': {},
        }

        if outcome == solver.BAD_TARGET:
            out.update(ok=False, reason='bad_target', msg=_(
                "Type the take-home you want, as an amount above zero."))
            return out
        if outcome == solver.GARBAGE:
            out.update(ok=False, reason='garbage', msg=_(
                "This scheme does not give a take-home that is a number for "
                "this person, so nothing can be worked back."))
            return out

        value = found.get('value')
        if value is not None and outcome in (solver.EXACT, solver.CLOSEST, solver.LIMIT):
            # R2 — the figure reported, evaluated once more on its own.
            after_inputs = dict(inputs)
            after_inputs[item.code] = value
            after_results = engine.evaluate(after_inputs)
            bad, _errs = broken(after_results)
            if bad:
                return self._th_refusal('formula_error', _(
                    "Take-home cannot be worked back: the formula for “%(name)s” "
                    "has an error at %(value)s (%(why)s). Fix it in Formula "
                    "Studio first.", name=names.get(bad, bad), value=money(value),
                    why=self._th_why(_errs[bad])))
            before_totals = engine.totals(before_results)
            after_totals = engine.totals(after_results)
            out['net'] = after_totals['net']
            out['value'] = value
            out['before'] = dict(before_totals, value=before_value)
            out['after'] = dict(after_totals, value=value)
            out['lines'] = self._th_lines(engine, before_results, after_results, decimals)
            out['changed'] = sum(1 for line in out['lines'] if line['changed'])
        if found.get('below'):
            out['below'] = found['below']

        target_text = money(out['target'])
        if outcome == solver.EXACT:
            out['sentence'] = _("To take home %(target)s, %(item)s must be %(value)s.",
                                target=target_text, item=item_name, value=money(value))
        elif outcome == solver.CLOSEST:
            below = found['below']
            out['sentence'] = _(
                "%(target)s cannot be reached exactly — the scheme's rounding "
                "or a tax step jumps over it. Closest: %(item)s %(v1)s gives "
                "%(n1)s; %(item)s %(v2)s gives %(n2)s.",
                target=target_text, item=item_name,
                v1=money(below['value']), n1=money(below['net']),
                v2=money(value), n2=money(out['net']))
        elif outcome == solver.LIMIT:
            out['sentence'] = _(
                "Stopped after %(n)s tries without settling on a figure.",
                n=solver.MAX_EVALS)
            if value is not None:
                out['sentence'] += ' ' + _(
                    "The closest found: %(item)s %(value)s gives %(net)s.",
                    item=item_name, value=money(value), net=money(out['net']))
        elif outcome == solver.NOT_POSSIBLE:
            why = found.get('why')
            if why == solver.WHY_FLAT:
                out['sentence'] = _(
                    "Take-home does not change when %(item)s changes, so it "
                    "cannot be worked back from %(item)s. Pick the pay item "
                    "that feeds take-home.", item=item_name)
            elif why == solver.WHY_ABOVE:
                out['sentence'] = _(
                    "Take-home is already %(net)s with %(item)s at 0, which is "
                    "above %(target)s.", net=money(found['net']),
                    item=item_name, target=target_text)
            else:
                out['sentence'] = _(
                    "Take-home never reaches %(target)s: even with %(item)s at "
                    "%(value)s, take-home is %(net)s.", target=target_text,
                    item=item_name, value=money(found['value']),
                    net=money(found['net']))
        falls = found.get('falls')
        if falls and outcome in (solver.EXACT, solver.CLOSEST, solver.LIMIT):
            out['note'] = _(
                "Take-home goes down at one point as %(item)s rises (between "
                "%(x1)s and %(x2)s), so this is the lowest %(item)s found that "
                "reaches the target.", item=item_name,
                x1=money(falls['from'][0]), x2=money(falls['to'][0]))
        # Only the scheme's wage item may be copied into the contract wage.
        out['can_use'] = bool(subject['contract']) and item.code in subject['wage_codes'] \
            and outcome in (solver.EXACT, solver.CLOSEST) and value is not None
        out['ms'] = int((time.monotonic() - started) * 1000)
        _logger.debug("W2-C: solved in %s evaluations, %s ms", out['evals'], out['ms'])
        return out

    @api.model
    def _th_lines(self, engine, before, after, decimals):
        unit = 10.0 ** (-decimals)
        before_lines = {l.code: l.total or 0.0 for l in engine.lines(before)}
        after_lines = {l.code: l.total or 0.0 for l in engine.lines(after)}
        rows = []
        for spec in engine.specs:
            b = before_lines.get(spec['code'], 0.0)
            a = after_lines.get(spec['code'], 0.0)
            rows.append({
                'code': spec['code'], 'name': spec['name'],
                'kind': _BAND_KIND.get(spec['band'] or '', 'info'),
                'counts': spec['counts'],
                'before': b, 'after': a,
                'changed': abs(a - b) >= unit / 2.0,
            })
        return rows
