# -*- coding: utf-8 -*-
"""SCHEMECTX P2 — which components belong to the person in front of you.

THE DEFECT THIS ANSWERS. `hr.contract.create` used to give every new contract
one line per row of `hr.contract.advantage.template`, and that catalogue is a
flat list keyed by `code` with no country and no scheme on it. Add an India
scheme to a tenant that already runs a Vietnamese one and every Vietnamese
person's contract grows a handful of Indian components — and the other way
round. The owner reported nineteen of them on one demo contract.

THE SHAPE OF THE ANSWER. The catalogue stays flat (binding non-goal): a code
may legitimately belong to two schemes. What decides is the PERSON — the
scheme(s) that pay them, which `pb_scheme_map` already works out and stores on
the employee — and then the scheme's own component RULES say which codes are
its own. So the question is asked once, here, and the drawer, the pay package
card and the clean-up script all read the same answer.

THREE STATES, AND WHY THE THIRD IS NOT AN ERROR.

* ``known=True`` with schemes — the normal answer.
* ``known=True`` with none — the scheme map is installed and nobody's map
  covers this person. Callers show an empty state with a way out; they must
  NOT fall back to "show everything", because that is the defect.
* ``known=False`` — `pb_scheme_map` is not installed on this database at all.
  There is no question to answer, so every caller behaves exactly as it did
  before this phase. A tenant that never mapped anybody sees no change.

THIS IS A READ (ledger rule 8). Nothing in this file writes. When the stored
"Paid by" is marked stale the authoritative resolver is asked instead of the
stale value — `pb.scheme.map.resolve_many` is itself a pure read — and the
refreshed answer is deliberately NOT written back: a drawer opening is not a
reason to start a write transaction, and the module's own cron settles the
stored value on its own schedule.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class HrFormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    # ------------------------------------------------------------- the person
    @api.model
    def _sc_employee(self, employee):
        """One `hr.employee`, whether a record or a bare id arrived.

        A public helper reached over JSON-RPC gets an integer where the caller
        wrote a record (the R43/R52 trap `pb_comp_ben` already carries).
        """
        Employee = self.env['hr.employee']
        if isinstance(employee, models.BaseModel):
            return employee[:1]
        try:
            employee_id = int(employee or 0)
        except (TypeError, ValueError):
            return Employee.browse()
        return Employee.browse(employee_id).exists() if employee_id \
            else Employee.browse()

    @api.model
    def schemes_for_employee(self, employee):
        """The scheme(s) that pay this person — regular first, then advance.

        An empty recordset when `pb_scheme_map` is absent, or when it is there
        and nobody's map reaches this person. Use
        :meth:`component_scope_for_employee` when you need to tell those two
        apart.
        """
        record = self._sc_employee(employee)
        if not record:
            return self.browse()
        Employee = self.env['hr.employee']
        if 'pb_paid_by_id' not in Employee._fields:
            return self.browse()

        person = record.sudo()
        ordered = []
        for name in ('pb_paid_by_id', 'pb_paid_by_advance_id'):
            if name not in Employee._fields:
                continue
            config = person[name]
            if config and config.id not in ordered:
                ordered.append(config.id)

        stale = bool(person.pb_paid_by_stale) \
            if 'pb_paid_by_stale' in Employee._fields else False
        if (stale or not ordered) and 'pb.scheme.map' in self.env:
            ordered = self._sc_resolve(person) or ordered

        return self.sudo().browse(ordered).exists()

    @api.model
    def _sc_resolve(self, person):
        """Ask the map itself. Never raises, never writes, never guesses."""
        Employee = self.env['hr.employee']
        try:
            Map = self.env['pb.scheme.map'].sudo()
            main_cycle = 'any'
            if hasattr(Employee, '_pb_main_cycle'):
                main_cycle = Employee.sudo()._pb_main_cycle(
                    person.company_id.id)
            found = []
            main = Map.resolve(person, main_cycle) or {}
            if main.get('config_id'):
                found.append(int(main['config_id']))
            second = Map.resolve(person, 'mid_cycle') or {}
            # The same narrowing `_pb_recompute_paid_by` applies: "the only
            # scheme in this company" answering the advance question would make
            # the end-of-month scheme pay the advance too.
            if second.get('rung') in ('segment', 'department', 'division',
                                      'rule') \
                    and second.get('config_id') \
                    and int(second['config_id']) not in found:
                found.append(int(second['config_id']))
            return found
        except Exception:       # noqa: BLE001 — a map that cannot be read must
            # never stop a drawer opening; the caller falls back to the stored
            # value, or to "nobody covers this person".
            _logger.warning('Component scope: the scheme map could not be '
                            'read for employee %s', person.id, exc_info=True)
            return []

    # ----------------------------------------------------------- the codes
    def component_rule_codes(self):
        """The component codes these schemes own. Called ON a recordset.

        TWO HALVES, AND THE SECOND ONE IS A SAFETY MARGIN.

        1. The DECLARED contract components — the same domain the Records Desk
           uses (`pb_records._component_rules`): a rule marked as living on the
           contract, whether it holds an amount or a piece of text. Refactoring
           the desk to call this would mean making `pb_records` depend on this
           module for a two-line search, so the domain is stated twice on
           purpose and this comment is the link between them.
        2. Any OTHER rule of these schemes whose code the contract catalogue
           already carries a row for. In live data this adds nothing: the
           catalogue only ever gets a row through
           `_get_or_create_advantage_template`, which is fed by the declared
           contract components and by nothing else. It matters when the two
           have drifted — a rule that was a contract component once, a template
           made by hand — and there the safe answer is to SHOW the component,
           because this list decides what a contract is allowed to display and
           the one thing it must never do is hide a component the scheme has a
           rule for.
        """
        if not self:
            return set()
        Rule = self.env.get('hr.formula.rule')
        if Rule is None:
            return set()
        rules = Rule.sudo().search(
            [('config_id', 'in', self.ids),
             '|', ('is_contract_component', '=', True),
             ('is_text_component', '=', True)], order='id asc')
        codes = {(rule.code or '').strip() for rule in rules if rule.code}

        rest = {(row['code'] or '').strip()
                for row in Rule.sudo().search_read(
                    [('config_id', 'in', self.ids)], ['code'])
                if row.get('code')} - codes
        if rest:
            Template = self.env['hr.contract.advantage.template'].sudo()
            for template in Template.search([('code', 'in', sorted(rest))]):
                if template.code:
                    codes.add(template.code.strip())
        return {code for code in codes if code}

    @api.model
    def component_scope_for_employee(self, employee):
        """`{'known', 'schemes', 'codes'}` — the one answer, for one person."""
        Employee = self.env['hr.employee']
        known = 'pb_paid_by_id' in Employee._fields
        if not known:
            return {'known': False, 'schemes': [], 'codes': set()}

        schemes = self.schemes_for_employee(employee)
        rows = []
        for index, config in enumerate(schemes):
            rows.append({
                'id': config.id,
                'name': config.name or config.display_name or '',
                'country_code': config.country_code or '',
                'country_name': config.country_id.name or '',
                'currency': config.currency_id.name or '',
                'currency_symbol': config.currency_id.symbol or '',
                # Which of the two questions this scheme answered. The drawer
                # labels them; it is not a second way of ordering them.
                'role': 'regular' if index == 0 else 'advance',
            })
        return {'known': True, 'schemes': rows,
                'codes': schemes.component_rule_codes()}
