# -*- coding: utf-8 -*-
"""PSCHEME P2a D.1 and E — what the person's panel says, and the contract
that follows the pay scheme.

D.1 THE AMBER LINE (ledger A14). `person_scheme` and `paid_by` answer
    `country_mismatch` when the pay scheme that pays the person's month is of
    another country than their Country of work, and no later row and no
    waiting change already fixes it. The screens print ONE amber line —
    "Putu works in Singapore but is paid by Vietnam Monthly." — with "Change
    pay scheme", the dialog preselected to the scheme that fits the country.
    The server never changes a scheme because a country changed (A7); this
    line is the net under every door that writes Country of work without a
    screen to ask (Records Desk, sheets, imports).

E.  THE CONTRACT FOLLOWS (FACTS T6, T7). A contract's currency follows the
    CONTRACT's own Country of work (`hr.contract.payroll_country`), not the
    person's pay scheme. So when a person's own pay scheme of a main kind
    takes effect — written for a day already reached, or reached by the daily
    boundary job — and its country differs from their running contract's:
      * the contract's country becomes the scheme's (its currency follows by
        the existing compute; no amount is converted or rewritten, NH3);
      * the new scheme's usual answers are filled in through the FILLIN path
        (missing codes only, never an overwrite; old component lines stay);
      * the contract carries "check the pay amounts" until its wage is edited
        or the note is dismissed: "Their contract is now in SGD. Check their
        pay amounts."
    The one-time fill never does this: it writes down who pays people today
    and changes nobody's pay.
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_scheme_map import MAIN_QUESTION, SKIP_PERSON

_logger = logging.getLogger(__name__)

MAIN_KINDS = ('regular', 'end_cycle')
FOLLOW_CONTEXT = 'pb_ps_contract_follow'


class HrContractPersonScheme(models.Model):
    _inherit = 'hr.contract'

    pb_ps_check_amounts = fields.Boolean(
        string='Pay amounts to check',
        help="Set when the contract's Country of work followed a new pay scheme "
             "of another country: the currency changed and the amounts were "
             "kept as typed. Cleared when the wage is edited.",
        readonly=True, copy=False)

    def write(self, vals):
        if 'wage' in vals and not self.env.context.get(FOLLOW_CONTEXT) \
                and any(self.mapped('pb_ps_check_amounts')):
            vals = dict(vals, pb_ps_check_amounts=False)
        return super().write(vals)


class PbPersonSchemeBoundary(models.Model):
    _inherit = 'pb.person.scheme'

    @api.model
    def _cron_mark_boundaries(self):
        marked = super()._cron_mark_boundaries()
        today = fields.Date.context_today(self)
        starting = self.sudo().search([
            ('active', '=', True), ('date_from', '=', today),
            ('cycle_type', 'in', list(MAIN_KINDS)), ('source', '!=', 'fill')])
        people = starting.mapped('employee_id')
        if people:
            try:
                self.env['pb.scheme.board'].sudo()._ps_follow(people)
            except Exception:   # noqa: BLE001 — the job must finish
                _logger.exception('Person pay schemes: contracts could not follow')
        return marked


class PbSchemeBoardFollow(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ====================================================== E. the contract
    @api.model
    def _contract_currency_for(self, country_code, company):
        """The currency a contract of `country_code` takes — read off the
        contract's own compute on an in-memory record (no second table)."""
        if not country_code or 'hr.contract' not in self.env:
            return ''
        Contract = self.env['hr.contract'].sudo()
        field = Contract._fields.get('payroll_country')
        if not field or country_code not in dict(field._description_selection(self.env)):
            return ''
        try:
            draft = Contract.new({'payroll_country': country_code,
                                  'company_id': company.id if company else False})
            return draft.currency_id.name or ''
        except Exception:       # noqa: BLE001
            return ''

    @api.model
    def _open_contracts(self, employees):
        if 'hr.contract' not in self.env or not employees:
            return self.env['hr.contract'].sudo().browse() if 'hr.contract' in self.env else None
        return self.env['hr.contract'].sudo().search([
            ('employee_id', 'in', employees.ids), ('state', '=', 'open')])

    @api.model
    def _ps_follow(self, employees):
        """E.1 — the running contracts of these people follow the country of
        the pay scheme that pays them TODAY from their own rows. Idempotent.
        Returns the ids of the people whose contract moved."""
        contracts = self._open_contracts(employees)
        if not contracts:
            return []
        allowed = dict(contracts._fields['payroll_country']._description_selection(self.env))
        Map = self.env['pb.scheme.map'].sudo()
        today = fields.Date.context_today(self)
        moved = []
        by_company = {}
        for employee in employees:
            by_company.setdefault(employee.company_id.id, []).append(employee.id)
        Config = self.env['hr.formula.config'].sudo()
        self.env.flush_all()
        for company_id, ids in by_company.items():
            cycle = self.env['hr.employee']._pb_main_cycle(company_id)
            answers = Map.with_context(**{MAIN_QUESTION: True}).resolve_many(
                ids, cycle, on_date=today)
            for contract in contracts.filtered(lambda c: c.employee_id.id in ids):
                answer = answers.get(contract.employee_id.id) or {}
                if answer.get('rung') != 'person':
                    continue
                config = Config.browse(answer.get('config_id') or 0).exists()
                code = config.country_code if config else ''
                if not code or code not in allowed or contract.payroll_country == code:
                    continue
                contract.with_context(**{FOLLOW_CONTEXT: True}).write({
                    'payroll_country': code, 'pb_ps_check_amounts': True})
                moved.append(contract.employee_id.id)
        if moved:
            Employee = self.env['hr.employee'].sudo()
            Employee._pb_recompute_paid_by(employee_ids=moved)
            # FILLIN, extended from "newly known" to "the scheme changed": the
            # new scheme's usual answers, missing codes only
            Employee._pb_fill_in_newly_known(moved)
        return moved

    @api.model
    def _person_set_write(self, employees, config, advance='keep', date_from=None,
                          source='hand', note=''):
        changed = super()._person_set_write(employees, config, advance, date_from,
                                            source=source, note=note)
        day = fields.Date.to_date(date_from) or fields.Date.context_today(self)
        if source != 'fill' and day <= fields.Date.context_today(self) \
                and config.cycle_type in MAIN_KINDS:
            try:
                with self.env.cr.savepoint():
                    self._ps_follow(employees)
            except Exception:   # noqa: BLE001 — a contract never blocks the change
                _logger.exception('Person pay scheme: the contract could not follow')
        return changed

    @api.model
    def contract_note_dismiss(self, contract_id):
        """"Got it" on "Their contract is now in SGD. Check their pay
        amounts." — for whoever may change the person's pay scheme."""
        if not self._can_propose_person():
            raise AccessError(_("Only HR and payroll can do this."))
        contract = self.env['hr.contract'].sudo().browse(int(contract_id or 0)).exists()
        if not contract:
            raise UserError(_("That contract is not there any more."))
        contract.with_context(**{FOLLOW_CONTEXT: True}).write({'pb_ps_check_amounts': False})
        return True

    # ============================================= the cards and the panel
    @api.model
    def _scheme_card(self, config, counts=None):
        card = super()._scheme_card(config, counts)
        company = config.company_id or self.env.company
        cache = self.env.context.get('pb_ps_currency_cache')
        key = config.country_code or ''
        if cache is not None and key in cache:
            card['contract_currency'] = cache[key]
        else:
            card['contract_currency'] = self._contract_currency_for(key, company)
            if cache is not None:
                cache[key] = card['contract_currency']
        return card

    @api.model
    def person_scheme(self, employee_id):
        # one in-memory contract per country for every card's currency
        res = super(PbSchemeBoardFollow, self.with_context(
            pb_ps_currency_cache={})).person_scheme(employee_id)
        if not res.get('found'):
            return res
        employee = self.env['hr.employee'].sudo().with_context(
            active_test=False).browse(int(employee_id))
        try:
            res['country_mismatch'] = self._person_mismatch(employee, res)
        except Exception:       # noqa: BLE001 — an extra line, never the panel
            _logger.warning('Pay scheme: the country check failed', exc_info=True)
            res['country_mismatch'] = None
        contract = self._open_contracts(employee)[:1] if employee else None
        res['contract'] = {
            'id': contract.id, 'country': contract.payroll_country or '',
            'currency': contract.currency_id.name or '',
        } if contract else None
        res['contract_note'] = {
            'contract_id': contract.id,
            'currency': contract.currency_id.name or '',
            'line': _("Their contract is now in %s. Check their pay amounts.",
                      contract.currency_id.name or ''),
        } if contract and contract.pb_ps_check_amounts else None
        return res

    @api.model
    def _person_mismatch(self, employee, res=None):
        """`{line, country, country_name, target_id, target, date}` or None."""
        code = employee.payroll_country or ''
        main = (res or {}).get('main') or {}
        if not code or not main or not main.get('country_code') \
                or main['country_code'] == code or main.get('kind') not in MAIN_KINDS:
            return None
        company_id = employee.company_id.id
        fixes = self._later_fixes([employee.id], company_id).get(employee.id) or set()
        Config = self.env['hr.formula.config'].sudo()
        if any(Config.browse(c).exists().country_code == code for c in fixes):
            return None
        Map = self.env['pb.scheme.map'].sudo()
        cycle = self.env['hr.employee']._pb_main_cycle(company_id)
        ladder = Map.with_context(**{SKIP_PERSON: True, MAIN_QUESTION: True}).resolve(
            employee.id, cycle)
        target = self._country_target(company_id, code, ladder)
        country_name = self._country_name(code)
        first_next = fields.Date.context_today(self).replace(day=1) + relativedelta(months=1)
        first = (employee.name or '').split(' ')[0]
        return {
            'line': _("%(name)s works in %(country)s but is paid by %(scheme)s.",
                      name=first, country=country_name, scheme=main.get('name') or ''),
            'country': code, 'country_name': country_name,
            'target_id': target,
            'target': Config.browse(target).name if target else '',
            'date': fields.Date.to_string(first_next),
        }

    @api.model
    def paid_by(self, employee_id):
        res = super().paid_by(employee_id)
        if not res.get('found') or not res.get('config_id'):
            return res
        employee = self.env['hr.employee'].sudo().browse(int(employee_id or 0)).exists()
        config = self.env['hr.formula.config'].sudo().browse(res['config_id']).exists()
        try:
            mismatch = self._person_mismatch(employee, {'main': {
                'country_code': config.country_code or '', 'kind': config.cycle_type,
                'name': config.name or ''}})
        except Exception:       # noqa: BLE001
            mismatch = None
        res['mismatch'] = mismatch['line'] if mismatch else ''
        res['mismatch_short'] = _("Works in %s", mismatch['country_name']) if mismatch else ''
        return res
