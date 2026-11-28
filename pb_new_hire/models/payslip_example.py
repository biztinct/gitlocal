# -*- coding: utf-8 -*-
"""NEWHIRE P4 Part B — "A month's payslip · example" (the right panel).

FACTS_CORE §F verdict, followed as written: the example is worked out over
REAL records inside a savepoint that is always rolled back, so it is exactly
what the product would do for this person and it never leaves a trace.

    1. the employee and the contract are made through the SAME create path a
       real studio hire takes (`pb.people.onboard.wizard.create_employee`
       under NEWHIRE_WRITE, extended in `create_ext.py`), with the draft's
       values built by the same `_values` — only in "preview" mode
       (`PREVIEW_CTX`), which skips every welcome leg and the proposal. So the
       Country of work, the currency, the fill-in of the usual answers and the
       person's own changes are what a real hire gets;
    2. a draft `hr.payslip` for ONE full calendar month (the month of the
       first day) on the resolved scheme, worked days from the product's own
       `onchange_employee_id`;
    3. the inputs from `_get_formula_input_values` (the batch-free resolver,
       with its provenance), evaluated with the read-only sample kernel —
       NEVER `compute_sheet`, which writes on the shared scheme rules; one
       in-memory `hr.payslip.line` per payslip line the real compute would
       create (`_create_payslip_lines_from_formulas` mirrored: same filter,
       same fields), totals from `pb_pay_totals()` (the one pay-band rule);
    4. plain values copied out, then the savepoint is rolled back
       (`_Rollback`, the pb_blueprint precedent) and the cache dropped.

Honesty rules (handover B.3) live in `_notes` and in the refusals: the
example is always for a FULL month, from the scheme's usual values; no
proration is shown that the engine did not produce.
"""
import copy
import json
import logging
import time
from collections import OrderedDict
from calendar import monthrange

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models import pay_period
from odoo.addons.pb_people_advanced.models.newhire_approval import NEWHIRE_WRITE
from .studio import _advance_arg

from .studio import _int
from .create_ext import PREVIEW_CTX            # "for the example only": no welcome leg

_logger = logging.getLogger(__name__)

try:                                            # the payslip-line rail (VALUEKIND)
    from odoo.addons.pb_hr_payroll_formula.models import value_kind_classifier as _vk
except ImportError:                             # pragma: no cover — always installed
    _vk = None


#: The draft keys that can change a payslip. Everything else (welcome,
#: documents, sign-in) is left out of the preview create on purpose.
EXAMPLE_KEYS = (
    'name', 'date_start', 'department_id', 'job_id', 'job_title', 'payroll_country',
    'country_id', 'wage', 'contract_kind', 'date_end', 'trial_on', 'usual', 'type_id',
    'late_group', 'pb_scale_pin_reason', 'work_location_id',
    'scheme_id',                    # P8: the pay scheme picked by hand
    'advance_scheme_id',            # PSCHEME P1: the mid-month advance
)

#: The values keys the preview create drops (welcome legs, the bank, the
#: org chart's "fill this role"). The MANAGER too: with a manager who signs
#: in, the stock time-off create adds that user to the approvers group, and a
#: group write clears every worker's caches (`clear_cache('stable')`), which
#: no rollback undoes (NH51). A manager changes nothing on a payslip.
_PREVIEW_DROP = (
    'parent_id', 'own_fields', 'pb_clock_code', 'week_id', 'buddy_id', 'equipment', 'letter',
    'fill_job_id', 'bank_name', 'account_number', 'account_holder', 'pb_nh_details',
    'pb_nh_papers', 'pb_nh_asks', 'private_email', 'private_phone', 'work_email',
)

#: Sources that mean "this value arrives with the monthly pay data file" /
#: "from the connected system" (`hr.formula.rule.declared_sources`).
_FILE_KINDS = ('excel',)
_FEED_KINDS = ('feed', 'rule')


#: B.4 P6: the numbers of one example are kept 5 minutes, newest 256 per
#: database (an in-memory LRU on the registry; every worker has its own).
CACHE_SECONDS = 300
CACHE_SIZE = 256


class _Rollback(Exception):
    """Unwinds the example's savepoint. Never reaches a person."""


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _num(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class PbNewHireExample(models.AbstractModel):
    _inherit = 'pb.new.hire'

    # ============================================================ the call
    @api.model
    def payslip_example(self, draft):
        """`{ok, month_label, lines:[{name, amount, band}], gross, deductions,
        net, employer_cost, currency:{symbol, position, decimals}, scheme,
        notes:[str], took_ms}` or `{ok: False, reason, fix, step}`.

        Display only. It never leaves a trace (B.4 P1)."""
        self._gate()
        started = time.perf_counter()
        d = {k: v for k, v in (draft or {}).items() if k in EXAMPLE_KEYS} \
            if isinstance(draft, dict) else {}
        try:
            out = self._example(d)
        except AccessError:
            raise
        except Exception:                       # noqa: BLE001 — the panel never breaks
            _logger.exception('new hire: the payslip example failed')
            self.env.invalidate_all()
            out = self._no(_("An example cannot be shown right now."),
                           _("The hire is not affected. Try again in a moment."))
        out['took_ms'] = int((time.perf_counter() - started) * 1000)
        _logger.info('new hire: payslip example in %s ms (ok=%s, cached=%s, busy=%s, scheme=%s)',
                     out['took_ms'], out.get('ok'), bool(out.get('cached')), bool(out.get('busy')),
                     out.get('scheme_id') or '-')
        return out

    @api.model
    def _no(self, reason, fix='', step=False, **extra):
        return dict({'ok': False, 'reason': reason, 'fix': fix or '', 'step': step or False},
                    **extra)

    # ============================================================ checks
    @api.model
    def _example_refusal(self, d):
        """What is missing before an example can be worked out (the screen
        asks only once name, team, country and wage exist; this is the
        server's own check of the same)."""
        if not (d.get('name') or '').strip():
            return self._no(_("Type the person's name to see an example."), '', 'who')
        if not self._day(d.get('date_start')):
            return self._no(_("Choose the first day to see an example."), '', 'who')
        if not self._team(d.get('department_id')):
            return self._no(_("Choose the team to see an example."), '', 'role')
        if d.get('payroll_country') not in dict(self._countries()):
            return self._no(_("Choose the country of work to see an example."), '', 'role')
        config, main, wage = self._pbpb_pay(d)
        if main and (wage is None or wage <= 0):
            name = config._pbpb_layout()['head']['name']
            return self._no(_("Type the %s.", name[:1].lower() + name[1:]), '', 'pay')
        if not main and (wage is None or wage <= 0) and not self._scale_amount(d):
            return self._no(_("Type the monthly wage to see an example."), '', 'pay')
        if (d.get('contract_kind') or 'permanent') == 'fixed':
            end = self._day(d.get('date_end'))
            if not end or end <= self._day(d.get('date_start')):
                return self._no(_("Choose when the contract ends to see an example."), '', 'pay')
        return None

    @api.model
    def _num_or_none(self, value):
        if value is None or value is False or value is True or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @api.model
    def _example_lock(self, company):
        """The calendar copy takes a transaction-wide advisory lock on (company,
        calendar) (FACTS_CORE §F risk a). Take it first WITHOUT waiting: a
        second example in flight answers "busy" (the screen retries quietly)
        instead of queueing behind the first one."""
        calendar = company.resource_calendar_id
        if not calendar:
            return True
        self.env.cr.execute('SELECT pg_try_advisory_xact_lock(%s, %s)', (company.id, calendar.id))
        return bool(self.env.cr.fetchone()[0])

    @api.model
    def _seat_refusal(self):
        """At the plan's employee limit the preview create would be refused
        (NH7). A real send still goes: the approved hire is then held with
        the reason on its request (engine `_run_apply`, state approved with a
        block reason) until a place is free and it is retried from Approvals
        (`retry_apply`) — test P4b proves the sentence."""
        Emp = self.env['hr.employee'].sudo()
        if not hasattr(Emp, '_pb_check_seats'):
            return None
        try:
            Emp._pb_check_seats(1)
        except UserError:
            return self._no(
                _("An example cannot be shown because your plan has no free employee place."),
                _("You can still send the hire: once it is approved, it waits in Approvals until "
                  "a place is free."))
        return None

    # ============================================================ the work
    @api.model
    def _example(self, d):
        refused = self._example_refusal(d)
        if refused:
            return refused
        company = self._company()
        code = d['payroll_country']
        team = self._team(d.get('department_id'))
        start = self._day(d.get('date_start'))
        kind = 'fixed' if d.get('contract_kind') == 'fixed' else 'permanent'
        decided = self.decides(team.id, code, fields.Date.to_string(start), kind,
                               _int(d.get('scheme_id')) or False, _int(d.get('job_id')) or False,
                               _advance_arg(d))
        scheme = decided.get('scheme') or {}
        config = self._scheme(scheme.get('id'))
        if not config:
            return self._no(_("No pay scheme for this person yet."),
                            _("Pick a Country of work that has a pay scheme, or add one in Mapping, "
                              "then the example appears here."),
                            'role')
        first = start.replace(day=1)
        last = start.replace(day=monthrange(start.year, start.month)[1])
        key = self._example_key(d, config, company)
        data = self._cache_get(key)
        cached = data is not None
        if not cached:
            seat = self._seat_refusal()
            if seat:
                return seat
            if not self._example_lock(company):
                return self._no(_("Working it out."), '', False, busy=True)
            vals, _decided = self._values(dict(d, login_mode='none', open_case=False, letter=False))
            for drop in _PREVIEW_DROP:
                vals.pop(drop, None)
            vals.update(login_mode='none', open_case=False, letter=False)
            errors = {}
            try:
                with self.env.cr.savepoint():
                    data = self._example_inside(config, vals, first, last, errors)
                    raise _Rollback()
            except _Rollback:
                pass
            except UserError as exc:
                self.env.invalidate_all()
                text = exc.args[0] if exc.args else ''
                return self._no(_("An example cannot be shown: %s", self._sentence(text)),
                                _("The hire is not affected."))
            finally:
                self.env.invalidate_all()
            if errors:
                code_, message = next(iter(errors.items()))
                return self._no(
                    _("%(scheme)s could not work out an example: %(why)s",
                      scheme=config.name or '', why=self._error_words(data.get('names') or {},
                                                                      code_, message)),
                    _("The hire is not affected. Check the scheme in Mapping."))
            self._cache_put(key, data)
        currency = decided.get('currency') or self._company_currency()
        decimals = currency.get('decimals') if currency.get('decimals') is not None else 2
        notes = self._notes(d, config, decided, start, first, data)
        net = data.get('net')
        return {
            'ok': True,
            'month_label': format_date(self.env, first, date_format='MMMM y'),
            'month': fields.Date.to_string(first),
            'lines': [dict(line, amount=round(line['amount'], decimals))
                      for line in data.get('lines') or []],
            'gross': round(data.get('gross') or 0.0, decimals),
            'deductions': round(data.get('deductions') or 0.0, decimals),
            'net': round(net, decimals) if net is not None else None,
            'employer_cost': round(data.get('employer_cost') or 0.0, decimals),
            'currency': {'symbol': currency.get('symbol') or currency.get('name') or '',
                         'name': currency.get('name') or '',
                         'position': currency.get('position') or 'after',
                         'decimals': decimals},
            'scheme': config.name or '',
            'scheme_id': config.id,
            'notes': notes,
            'cached': cached,
        }

    # ============================================================ the cache
    @api.model
    def _example_key(self, d, config, company):
        """Everything the NUMBERS depend on (B.4 P6): the scheme and the
        newest change to it, the company, and every draft key except the
        name (the name only changes the words, which are built per call)."""
        self.env.flush_all()
        # write_date alone is not enough: inside one transaction it does not
        # move, so the rules' own content is hashed too (300 rules: ~1 ms)
        self.env.cr.execute("""
            SELECT count(*), max(write_date), md5(string_agg(concat_ws('|', id, code, column_type,
                   default_value, constant_value, excel_formula, net_role, net_role_detail,
                   appears_on_payslip, sequence, value_kind, is_contract_component, application_source_key),
                   ',' ORDER BY id))
              FROM hr_formula_rule WHERE config_id = %s""", (config.id,))
        count, newest, digest = self.env.cr.fetchone()
        draft = {k: v for k, v in d.items() if k != 'name'}
        return json.dumps([self.env.cr.dbname, company.id, config.id, str(config.write_date),
                           count, str(newest), digest, draft], sort_keys=True, default=str)

    @api.model
    def _cache(self):
        cache = getattr(self.pool, '_pb_nh_example_cache', None)
        if cache is None:
            cache = self.pool._pb_nh_example_cache = OrderedDict()
        return cache

    @api.model
    def _cache_get(self, key):
        cache = self._cache()
        hit = cache.get(key)
        if not hit or time.monotonic() - hit[0] > CACHE_SECONDS:
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return copy.deepcopy(hit[1])

    @api.model
    def _cache_put(self, key, data):
        cache = self._cache()
        cache[key] = (time.monotonic(), copy.deepcopy(data))
        cache.move_to_end(key)
        while len(cache) > CACHE_SIZE:
            cache.popitem(last=False)

    @api.model
    def _example_inside(self, config, vals, first, last, errors):
        """Inside the savepoint: the person, the contract, one draft payslip,
        the scheme's evaluation. Returns plain Python values only."""
        env = self.env(su=True, context=dict(
            self.env.context, tracking_disable=True, mail_notrack=True,
            mail_create_nolog=True, mail_create_nosubscribe=True,
            **{PREVIEW_CTX: True, NEWHIRE_WRITE: True}))
        res = env['pb.people.onboard.wizard'].create_employee(vals)
        employee = env['hr.employee'].browse(_int(res.get('employee_id'))).exists()
        contract = env['hr.contract'].browse(_int(res.get('contract_id'))).exists()
        if not employee or not contract:
            raise UserError(res.get('error') or _("the person could not be made."))
        env.flush_all()                         # NH4: the map reads with raw SQL
        config = config.with_env(env)
        Slip = env['hr.payslip']
        day_from, day_to = fields.Date.to_string(first), fields.Date.to_string(last)
        change = (Slip.onchange_employee_id(day_from, day_to, employee.id, contract.id) or {}) \
            .get('value') or {}
        slip_vals = {
            'employee_id': employee.id, 'contract_id': contract.id,
            'date_from': day_from, 'date_to': day_to,
            'company_id': employee.company_id.id or self._company().id,
            'formula_config_id': config.id, 'calculation_method': 'formula',
            'name': change.get('name') or _("Example payslip"),
        }
        if change.get('struct_id'):
            slip_vals['struct_id'] = change['struct_id']
        worked = [w for w in change.get('worked_days_line_ids') or [] if isinstance(w, dict)]
        if worked:
            slip_vals['worked_days_line_ids'] = [(0, 0, w) for w in worked]
        slip = Slip.create(slip_vals)
        provenance = {}
        inputs = slip._get_formula_input_values(config, provenance=provenance)
        # A new hire has no pay file yet. Only supply full-month day counts
        # when the real reader found no answer. A resolved zero is an answer.
        unresolved = {code for code, source in provenance.items() if source.get('src') == 'none'}
        config.rule_ids._pbpb_fill_preview_days(inputs, unresolved, pay_period.default_standard_work_days(first, last))
        probe = env['hr.formula.sample.data'].new({'config_id': config.id})
        values = probe._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
        lines = self._example_lines(slip, config, values or {})
        totals = lines.pb_pay_totals()
        has_net = any(line.pb_pay_band() == 'NET' for line in lines)
        shown = []
        for line in lines.sorted(lambda l: (l.sequence, l.code or '')):
            band = line.pb_pay_band()
            amount = line.total or 0.0
            if band in ('GROSS', 'BASIC', 'ALW'):
                kind = 'earning'
            elif band == 'DED':
                kind = 'deduction'
                amount = abs(amount)
            else:
                continue
            if abs(amount) < 0.005:
                continue                        # zero lines hidden
            if not line.pb_counts_in_totals():
                kind = 'info'                   # already inside another total
            shown.append({'name': line.name or line.code or '', 'amount': amount, 'band': kind})
        rules = config.rule_ids
        return {
            'lines': shown,
            'gross': totals.get('gross') or 0.0,
            'deductions': totals.get('deductions') or 0.0,
            'net': (totals.get('net') or 0.0) if has_net else None,
            'employer_cost': totals.get('employer_cost') or 0.0,
            'names': {r.code: r.name or r.code for r in rules if r.code},
            'from_file': self._from_outside(rules, provenance, _FILE_KINDS),
            'from_feed': self._from_outside(rules, provenance, _FEED_KINDS),
        }

    @api.model
    def _example_lines(self, slip, config, values):
        """In-memory payslip lines, one per line `_create_payslip_lines_from_
        formulas` would create (same filter: appears on the payslip, a
        number; same fields). Nothing is saved."""
        Line = self.env['hr.payslip.line'].with_env(slip.env)
        other = self.env['hr.salary.rule.category'].sudo().search([('code', '=', 'OTH')], limit=1)
        lines = Line.browse()
        for rule in config.rule_ids.sorted(lambda r: r.sequence):
            if not rule.appears_on_payslip:
                continue
            if _vk is not None and not _vk.wants_number(getattr(rule, 'value_kind', None)):
                continue
            lines |= Line.new({
                'slip_id': slip.id,
                'name': rule.name,
                'code': rule.code,
                'category_id': (rule.category_id or other).id or False,
                'sequence': rule.sequence,
                'amount': _num(values.get(rule.code, 0.0)),
                'quantity': 1.0,
                'rate': 100.0,
                'contract_id': slip.contract_id.id,
                'employee_id': slip.employee_id.id,
                'component_detail': bool(getattr(rule, 'net_role_detail', False)),
                'pay_role': getattr(rule, 'net_role', False) or False,
            })
        return lines

    @api.model
    def _from_outside(self, rules, provenance, kinds):
        """An input the scheme declares comes from the pay data file / the
        connected system that this example did NOT read from there: no pay
        data file exists before the first run, so the usual value (or the
        contract's line) stood in for it."""
        for rule in rules.filtered(lambda r: r.column_type == 'input'):
            entry = provenance.get(rule.code) or {}
            if (entry.get('src') or 'none') in kinds:
                continue                        # it really came from there
            try:
                declared = rule.declared_sources() if hasattr(rule, 'declared_sources') else []
            except Exception:                   # noqa: BLE001 — a note, not a gate
                declared = []
            if any((s.get('kind') if isinstance(s, dict) else None) in kinds for s in declared):
                return True
        return False

    # ============================================================ words
    @api.model
    def _sentence(self, text):
        text = str(text or '').strip()
        if not text:
            return _("the person could not be made.")
        text = text[0].lower() + text[1:] if len(text) > 1 and not text[:2].isupper() else text
        return text if text.endswith(('.', '!', '?')) else text + '.'

    @api.model
    def _error_words(self, names, code, message):
        name = names.get(code) or code or ''
        if 'division by zero' in str(message or '').lower() or 'divide' in str(message or '').lower():
            return _("the formula for %s divides by zero.", name)
        return _("the formula for %s could not be worked out.", name)

    @api.model
    def _notes(self, d, config, decided, start, first, data):
        month = format_date(self.env, first, date_format='MMMM')
        notes = [_("Worked out by %(scheme)s for a full %(month)s, from the scheme's usual values.",
                   scheme=config.name or '', month=month)]
        if start.day != 1:
            first_name = ' '.join(str(d.get('name') or '').split()).split(' ')[0]
            notes.append(_("%(first)s starts on %(day)s. Whether the first pay is reduced for the "
                           "part month depends on how this pay scheme counts days.",
                           first=first_name, day=format_date(self.env, start, date_format='d MMMM')))
        if data.get('from_file'):
            notes.append(_("Some values on this scheme come from the monthly pay data file; the "
                           "example uses the usual ones."))
        if data.get('from_feed'):
            notes.append(_("Some values on this scheme come from the connected system; the example "
                           "uses the usual ones."))
        scheme = decided.get('scheme') or {}
        if scheme and decided.get('problem') and (not scheme.get('match') or not scheme.get('honoured')):
            # P8: the pay run would not use this scheme for them yet - say so beside the example
            notes.append(decided['problem'])
        if data.get('net') is None:
            notes.append(_("This pay scheme has no take-home line, so take-home is not shown."))
        return notes

