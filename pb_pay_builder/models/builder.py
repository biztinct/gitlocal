import calendar
import math
from time import perf_counter

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import format_date
from odoo.addons.pb_formula_studio.models import take_home_solver as solver
from odoo.addons.pb_hr_payroll_formula.models import pay_period

from odoo.addons.pb_scheme_map.models.pb_scheme_map import MAIN_QUESTION

from .formula_words import describe


def amount(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _pbpb_step(currency, period):
    if period == 'year' and currency.name == 'INR':
        return 1000
    if currency.name in ('VND', 'IDR', 'KHR') or not currency.decimal_places:
        return 10000
    return 1 if period == 'month' else 100


class PayBuilder(models.AbstractModel):
    _name = 'pb.pay.builder'
    _description = 'Pay Builder'

    @api.model
    def _subject(self, home, ref):
        """Home adapters return trusted records. A client cannot opt into another home's rights."""
        if home != 'studio' or 'pb.new.hire' not in self.env:
            raise AccessError(_("You can look at this person but not at their pay."))
        studio = self.env['pb.new.hire']
        studio._gate()
        config = studio._scheme(ref.get('scheme_id'))
        if ref.get('scheme_id') and (not config or config.state != 'active'):
            raise AccessError(_("You can look at this person but not at their pay."))
        currency = config.currency_id if config else self.env.company.currency_id
        if not config:
            country = self.env['res.country'].sudo().search([('code', '=', ref.get('country') or '')], limit=1)
            currency = country.currency_id or currency
        return {'config': config, 'currency': currency, 'base': {}, 'existing': False,
                'day': fields.Date.to_date(ref.get('date_start')) or fields.Date.context_today(self),
                'name': str(ref.get('name') or '').strip().partition(' ')[0],
                'can_edit': self.env['hr.contract'].has_access('write'), 'can_open': self._can_open(),
                'seat': studio._seat_refusal() if config else None}

    def _contract_subject(self, contract, day):
        """The host already checked this contract. Missing amounts are zero in payroll."""
        contract.ensure_one()
        emp = contract.employee_id
        ladder = self.env['pb.scheme.map'].sudo().with_company(contract.company_id).with_context(**{MAIN_QUESTION: True})
        mapped = ladder.resolve_many(emp.ids, emp._pb_main_cycle(contract.company_id.id), on_date=day)
        cfg = self.env['hr.formula.config'].sudo().browse(mapped.get(emp.id, {}).get('config_id') or [])
        if cfg and cfg.company_id and cfg.company_id != contract.company_id:
            cfg = cfg.browse()
        base = {line.advantage_template_id.code: line.amount for line in contract.advantages_ids}
        base['wage'] = contract.wage
        return {'contract': contract, 'config': cfg, 'currency': cfg.currency_id or contract.company_id.currency_id,
                'base': base, 'existing': True, 'day': day, 'name': emp.name.partition(' ')[0],
                'can_edit': False, 'can_open': False}

    def _can_open(self):
        return self.env.user.has_group('pb_hr_payroll_formula.group_formula_user')

    @api.model
    def _pbpb_offer_values(self, offer):
        return {}

    def _refusal(self, reason, fix=None):
        return {'ok': False, 'reason': reason, 'fix': fix or _('Ask a payroll manager.')}

    @api.model
    def work_out(self, home, ref, values, tries=None, open_codes=None):
        try:
            subject = self._subject(home, ref if isinstance(ref, dict) else {})
            return self._answer(subject, values, tries, open_codes)
        except (AccessError, UserError) as exc:
            return self._refusal(str(exc))
        except (ValueError, OverflowError, TypeError):
            return self._refusal(_('The month could not be worked out.'), _('Check the amounts and the first day, then try again.'))

    def _prepare(self, subject, values, tries):
        config, cur = subject['config'], subject['currency']
        engine, layout = config._pbpb_program()
        head = layout['head']
        typed = values if isinstance(values, dict) else {}
        attempts = tries if isinstance(tries, dict) else {}
        base = subject['base']
        each = {r['code'] for r in layout['rows'] if r['kind'] == 'each'}
        rules = engine.rules.filtered(lambda r: r.column_type == 'input')
        inputs = {}
        tentative = {}
        for rule in rules:
            key = rule.code
            if rule.is_text_component:
                inputs[key] = ''
            elif rule.is_contract_component:
                usual = base.get(key, 0) if subject['existing'] else rule.default_value or 0
                val = amount(typed.get(key))
                inputs[key] = usual if val is None else val
            elif key in each and amount(attempts.get(key)) is not None:
                inputs[key] = tentative[key] = amount(attempts[key])
            else:
                inputs[key] = rule.default_value or 0
        head_value = amount(typed.get(head['code']))
        if head_value is None:
            head_value = base.get(head['code']) if subject['existing'] else None
        if head_value is None and not head['is_wage']:
            head_value = inputs.get(head['code']) or None
        wage = cur.round((head_value or 0) / 12) if head['period'] == 'year' else head_value or 0
        if not head['is_wage']:
            inputs[head['code']] = head_value or 0
        for code in layout['wages']:
            if code != head['code'] or head['is_wage']:
                inputs[code] = wage
        day = subject['day']
        first = day.replace(day=1)
        last = day.replace(day=calendar.monthrange(day.year, day.month)[1])
        std = pay_period.default_standard_work_days(first, last)
        unbound = {r.code for r in rules if not r.is_contract_component} - set(tentative) - set(layout['wages'])
        for code in unbound:
            if code.startswith('WD_'):
                inputs[code] = std
            elif code.startswith('HOURS'):
                inputs[code] = std * 8
        rules._pbpb_fill_preview_days(inputs, unbound, std)
        wired = pay_period.fill_wired_inputs(inputs, unbound, rules.pay_run_wires(), first, last, std)
        pay_period.fill_period_inputs(inputs, unbound - {code for code, _key in wired}, first, last, std)
        return engine, layout, inputs, tentative, head_value, wage

    def _answer(self, subject, values, tries=None, open_codes=None):
        started = perf_counter()
        config, currency = subject['config'], subject['currency']
        day = subject['day']
        null_totals = dict.fromkeys(('gross', 'net', 'deductions', 'employer_cost', 'cost'))
        values = values if isinstance(values, dict) else {}
        answer = {'ok': True, 'scheme': {'id': config.id, 'name': config.name} if config else False,
                  'month_label': format_date(self.env, day, date_format='MMMM yyyy'),
                  'currency': {'name': currency.name, 'symbol': currency.symbol, 'position': currency.position,
                               'decimals': currency.decimal_places, 'step': _pbpb_step(currency, 'month')},
                  'head': {'code': 'wage', 'name': _('Monthly wage'), 'is_wage': True, 'value': amount(values.get('wage')),
                           'period': 'month', 'required': True}, 'asks': [], 'sections': [], 'notes': [],
                  'totals': null_totals, 'annual': null_totals.copy(), 'explains': {}, 'can_edit': subject['can_edit'],
                  'has_net': False, 'state': 'no_scheme', 'took_ms': 0}
        if not config:
            answer['notes'] = [_('No pay scheme pays this person yet, so the month cannot be worked out.')]
            return answer
        engine, layout, inputs, tried, hv, wage = self._prepare(subject, values, tries)
        head = dict(layout['head'], value=hv, monthly=wage,
                    annual=(wage or 0) * 12 if layout['head']['is_wage'] or layout['head']['period'] == 'month' else hv)
        answer.update(head=head, state='waiting', has_net=layout['has_net'], typed_codes=[r.code for r in config._pbpb_person_rules()])
        answer['currency']['step'] = _pbpb_step(currency, head['period'])
        def line_data(row):
            key = row['code']
            value = inputs.get(key, 0)
            return dict(row, value=value, changed=value != row['usual'],
                        from_offer=key in subject.get('from_offer', ()))
        answer['asks'] = [line_data(row) for row in layout['asks']]
        if subject.get('seat'):
            return dict(answer, state='refused', notes=[subject['seat']['reason'], subject['seat']['fix']])
        if not hv or hv <= 0:
            return answer
        results = engine.evaluate(inputs)
        errors = engine.diagnose(results)
        totals = engine.totals(results)
        if not layout['has_net']:
            totals['net'] = None
        labels = {'earn': _('Gross pay'), 'ded': _('Total deductions'), 'er': _('On top of gross pay')}
        keys = {'earn': 'gross', 'ded': 'deductions', 'er': 'employer_cost'}
        sources = {'excel': _('the pay data file'), 'rule': _('the connected system'),
                   'feed': _('the connected system'), 'pay_run': _('the timesheet')}
        all_errors = set(errors)
        if errors and engine.upstream([s['code'] for s in engine.net_specs[:1]]) & all_errors:
            totals['net'] = None
        for group, total_key in keys.items():
            rows = []
            total_code = layout['total_codes'].get(group)
            for row in layout['rows']:
                if row['section'] != group:
                    continue
                key = row['code']
                failed = errors.get(key, False)
                if all_errors and engine.upstream([key]) & all_errors:
                    failed = failed or 'other'
                    if not row['detail'] or key == total_code:
                        totals[total_key] = None
                if key == total_code:
                    continue
                val = results.get(key) or 0
                data = line_data(row)
                rows.append(dict(data, amount=None if failed else val, failed=failed, zero=not val and not failed,
                                 in_bar=row['kind'] == 'set' and not row['usual'] and not val,
                                 source=sources.get(row['source_kind'], ''), tried=key in tried, was=None))
            if rows or total_code:
                answer['sections'].append({'key': group, 'total': totals[total_key], 'total_name': labels[group], 'lines': rows})
        totals['cost'] = totals['gross'] + totals['employer_cost'] if None not in (totals['gross'], totals['employer_cost']) else None
        allowed = {r['code']: r for s in answer['sections'] for r in s['lines'] if r['kind'] in ('calc', 'wage')}
        wanted = set(x for x in (open_codes or []) if isinstance(x, str)) & allowed.keys()
        for rule in engine.rules.filtered(lambda r: r.code in wanted):
            if allowed[rule.code]['kind'] == 'wage':
                answer['explains'][rule.code] = {'code': rule.code, 'name': rule.name, 'sentence': _('The monthly wage, as typed above.'),
                    'parts': [{'t':'ref', 'code':'wage', 'name':head['name'], 'amount':wage}], 'long':False, 'uses':[],
                    'result':wage, 'ladder':None, 'failed':False, 'failed_words':'', 'studio':{'can_open':False}}
            else:
                answer['explains'][rule.code] = describe(rule, results, allowed[rule.code]['failed'], currency, subject['can_open'])
        notes = [_('A full month, with each-month lines at their usual amount.')]
        if tried:
            notes[0] = _('A full month, including the example amounts you are trying.')
        if day.day != 1:
            notes.append(_('%(first)s starts on %(day)s, so the first pay may be less.',
                           first=subject.get('name') or _('This person'), day=format_date(self.env, day, date_format='d MMMM')))
        if 'excel' in layout['sources']:
            notes.append(_('Some values on this scheme come from the monthly pay data file; the example uses the usual ones.'))
        if {'feed', 'rule'}.intersection(layout['sources']):
            notes.append(_('Some values on this scheme come from the connected system; the example uses the usual ones.'))
        if not layout['has_net']:
            notes.append(_('This pay scheme has no take-home line.'))
        if layout['file_only']:
            notes.append(_('This pay scheme takes its amounts from the pay data file each month.'))
        answer.update(state='ok', totals=totals, annual={k: v * 12 if v is not None else None for k,v in totals.items()},
                      has_failed=bool(errors), notes=notes, took_ms=round((perf_counter()-started)*1000))
        return answer

    @api.model
    def explain(self, home, ref, values, tries, code):
        answer = self.work_out(home, ref, values, tries, [code])
        return answer.get('explains', {}).get(code) or (answer if not answer.get('ok') else
            self._refusal(_('This line has no sum to show.'), _('Choose a worked-out line.')))

    @api.model
    def work_back(self, home, ref, values, tries, target):
        try:
            subject = self._subject(home, ref if isinstance(ref, dict) else {})
        except (ValueError, OverflowError, TypeError):
            return self._refusal(_('Check the amounts and the first day, then try again.'))
        except (AccessError, UserError) as exc:
            return self._refusal(str(exc))
        if not subject['can_edit']:
            return self._refusal(_('You can look at this person but not change their pay.'))
        target = amount(target)
        if not target or target <= 0:
            return self._refusal(_('Type the take-home you want first.'), '')
        if not subject['config']:
            return self._refusal(_('This pay scheme has no take-home line, so it cannot be worked back.'))
        engine, layout, inputs, _tried, _value, _wage = self._prepare(subject, values, tries)
        if not engine.net_specs:
            return self._refusal(_('This pay scheme has no take-home line, so it cannot be worked back.'))
        head = layout['head']
        cur = subject['currency']
        net_uses = engine.upstream([engine.net_specs[0]['code']])
        def net_of(x):
            if not head['is_wage']:
                inputs[head['code']] = x
            for code in layout['wages']:
                if code != head['code'] or head['is_wage']:
                    inputs[code] = cur.round(x / 12) if head['period'] == 'year' else x
            result = engine.evaluate(inputs)
            if net_uses.intersection(engine.diagnose(result)):
                return None
            return engine.net(result)
        found = solver.solve(net_of, target, cur.decimal_places)
        if found['outcome'] == solver.LIMIT:
            return self._refusal(_('Working back took too long. Type the pay and adjust it instead.'), '')
        step = _pbpb_step(cur, head['period'])
        if found['outcome'] in (solver.EXACT, solver.CLOSEST):
            x = math.ceil(found['value'] / step) * step
            net = net_of(x)
            if net is not None and net >= target:
                return {'ok': True, 'head_value': x, 'net': net, 'evals': found['evals'] + 1}
        closest = found.get('net')
        if closest is None:
            return self._refusal(_('This pay scheme could not work out take-home.'))
        from odoo.tools import format_amount
        return self._refusal(_('No pay gives that take-home on this scheme. The closest is %s.',
                               format_amount(self.env, closest, cur)), '')
