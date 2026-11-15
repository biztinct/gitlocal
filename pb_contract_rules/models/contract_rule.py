# -*- coding: utf-8 -*-
"""`pb.contract.rule` — fixed-term contract rules, one row per country.

Owner ruling J3: when extending a fixed-term contract would go past the rule,
the decision shows a RED WARNING, a reason is required, and "Make it
permanent" is offered beside it. Never blocked.

THE RULE IS DATA, NOT A PACK. The rows ship as editable policy with the source
written on them and "to confirm with an adviser" (S8 facts §5); they are not
pay numbers and live outside `pb_pack_*` (ledger D2).

WHAT COUNTS (S8 facts §5, Q3). A contract counts when it has an end date and
is not a trial (probation) agreement. Contracts follow each other "in a row"
when one was renewed from the other (`pb_renewed_from_id`, the decision
board's own link) or when the next starts within the rule's gap after the
last ended — contracts made by hand or imported carry no link. A contract with
no end date ends the row. Contracts signed before the system are not on it:
HR types their number (and months) once on the person, and they are added.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)

#: Average month length used to turn a contract's days into months.
DAYS_PER_MONTH = 30.4375


class PbContractRule(models.Model):
    _name = 'pb.contract.rule'
    _description = 'Fixed-term contract rule'
    _order = 'sequence, id'

    name = fields.Char(string='Rule', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    country_id = fields.Many2one('res.country', string='Country',
                                 required=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty for every company in this country.')
    max_in_row = fields.Integer(
        string='Fixed-term contracts allowed in a row',
        help='How many fixed-term contracts may follow each other before the '
             'next one should be permanent. 0 = no limit on the number.')
    max_months_each = fields.Integer(
        string='Longest single contract (months)',
        help='0 = no limit on one contract.')
    max_months_total = fields.Integer(
        string='Longest time in a row (months)',
        help='All fixed-term contracts in a row together, extensions '
             'included. 0 = no limit.')
    gap_days = fields.Integer(
        string='A break longer than this starts a new row (days)',
        default=30,
        help='Contracts linked by a renewal always count as in a row. Other '
             'contracts count when the next one starts within this many days '
             'of the last one ending.')
    counts_note = fields.Text(
        string='What counts', translate=True,
        help='In plain words, for the people who decide contracts.')
    source_note = fields.Text(
        string='Where the rule comes from', translate=True,
        help='The law or policy, and who confirmed it.')

    @api.constrains('max_in_row', 'max_months_each', 'max_months_total',
                    'gap_days')
    def _check_numbers(self):
        for rule in self:
            if min(rule.max_in_row, rule.max_months_each,
                   rule.max_months_total, rule.gap_days) < 0:
                raise ValidationError(_(
                    "The numbers on a fixed-term rule cannot be below zero."))

    # ==================================================================
    # Which rule covers a person
    # ==================================================================
    @api.model
    def _employee_country(self, employee):
        """Where they work: work address, then the person, then the company —
        the same probe the trial-period rules use, so the two agree."""
        if not employee:
            return False
        addr = getattr(employee, 'address_id', False)
        if addr and getattr(addr, 'country_id', False):
            return addr.country_id.id
        country = getattr(employee, 'country_id', False)
        if country:
            return country.id
        company = employee.company_id or self.env.company
        return company.country_id.id if company.country_id else False

    @api.model
    def rule_for(self, employee):
        employee = employee.sudo() if employee else employee
        if not employee:
            return self.browse()
        country = self._employee_country(employee)
        if not country:
            return self.browse()
        company_id = (employee.company_id or self.env.company).id
        return self.sudo().search([
            ('active', '=', True), ('country_id', '=', country),
            ('company_id', 'in', [company_id, False])],
            order='company_id desc, sequence, id', limit=1)

    # ==================================================================
    # Counting
    # ==================================================================
    @api.model
    def _is_fixed(self, contract):
        if not contract or not contract.date_end or contract.state == 'cancel':
            return False
        if getattr(contract, 'vietnam_contract_type', False) == 'probation':
            return False
        if getattr(contract, 'pb_payroll_contract_type', False) == 'probation':
            return False
        return True

    @api.model
    def _months(self, contract):
        if not contract.date_start or not contract.date_end:
            return 0.0
        days = (contract.date_end - contract.date_start).days + 1
        return round(max(days, 0) / DAYS_PER_MONTH, 1)

    @api.model
    def chain(self, contract, rule=None):
        """`{contracts, count, months, before, months_before, rule}` — the
        fixed-term contracts in a row ending with `contract` (it included,
        when it is fixed-term), plus the ones typed on the person."""
        contract = contract.sudo() if contract else contract
        emp = contract.employee_id if contract else False
        rule = rule if rule is not None else self.rule_for(emp)
        gap = int(rule.gap_days) if rule else 30
        row = []
        if contract and self._is_fixed(contract):
            others = self.env['hr.contract'].sudo().search([
                ('employee_id', '=', emp.id), ('id', '!=', contract.id),
                ('state', '!=', 'cancel')], order='date_start desc, id desc')
            row = [contract]
            current = contract
            seen = {contract.id}
            while True:
                prev = current.pb_renewed_from_id if 'pb_renewed_from_id' in \
                    current._fields else False
                linked = bool(prev)
                if not prev:
                    earlier = [c for c in others if c.id not in seen and
                               c.date_start and current.date_start and
                               c.date_start < current.date_start]
                    prev = earlier[0] if earlier else False
                if not prev or prev.id in seen:
                    break
                if not self._is_fixed(prev):
                    break
                if not linked:
                    if not prev.date_end or not current.date_start or (
                            current.date_start - prev.date_end).days - 1 > gap:
                        break
                row.append(prev)
                seen.add(prev.id)
                current = prev
            row.reverse()
        before = int(emp.pb_fixed_term_before or 0) if emp else 0
        months_before = float(emp.pb_fixed_term_months_before or 0) \
            if emp else 0.0
        return {
            'contracts': row,
            'count': len(row) + before,
            'in_system': len(row),
            'months': round(sum(self._months(c) for c in row)
                            + months_before, 1),
            'before': before,
            'months_before': months_before,
            'rule': rule,
        }

    @api.model
    def check_extension(self, contract, months):
        """What extending `contract` by `months` would mean under the rule.

        `{'rule', 'rule_id', 'over', 'count_after', 'months_after',
          'sentence', 'lines', 'source', 'counts'}`; `over` False and no
        sentence when there is no rule or it stays within it."""
        contract = contract.sudo() if contract else contract
        if not contract:
            return {'over': False}
        emp = contract.employee_id
        rule = self.rule_for(emp)
        if not rule:
            return {'over': False, 'rule_id': 0}
        info = self.chain(contract, rule)
        span = max(1, int(months or 0))
        count_after = info['count'] + 1
        months_after = round(info['months'] + span, 1)
        lines = []
        over = False
        if rule.max_in_row and count_after > rule.max_in_row:
            over = True
            lines.append(_(
                "This would be fixed-term contract number %(n)s in a row. "
                "%(rule)s allows %(max)s, then the next one should be "
                "permanent.", n=count_after, rule=rule.name,
                max=rule.max_in_row))
        if rule.max_months_each and span > rule.max_months_each:
            over = True
            lines.append(_(
                "One contract of %(span)s months is longer than the "
                "%(max)s months %(rule)s allows.", span=span,
                max=rule.max_months_each, rule=rule.name))
        if rule.max_months_total and months_after > rule.max_months_total:
            over = True
            lines.append(_(
                "Fixed-term contracts in a row would come to %(total)s months, "
                "more than the %(max)s months %(rule)s allows.",
                total=('%g' % months_after), max=rule.max_months_total,
                rule=rule.name))
        counted = _("Counted: %(n)s fixed-term contract(s) in a row on the "
                    "system", n=info['in_system'])
        if info['before']:
            counted += _(", plus %s typed in as earlier ones",
                         info['before'])
        counted += '.'
        return {
            'over': over,
            'rule': rule.name,
            'rule_id': rule.id,
            'count_now': info['count'],
            'count_after': count_after,
            'months_after': months_after,
            'sentence': lines[0] if lines else '',
            'lines': lines,
            'counted': counted,
            'source': rule.source_note or '',
            'counts': rule.counts_note or '',
        }

    @api.model
    def summary(self, contract):
        """The one line on the decision drawer: "Fixed-term contract 2 in a
        row · Vietnam rule: 2, then permanent"."""
        contract = contract.sudo() if contract else contract
        if not contract or not self._is_fixed(contract):
            return {}
        rule = self.rule_for(contract.employee_id)
        info = self.chain(contract, rule)
        if not info['count']:
            return {}
        out = {
            'count': info['count'],
            'months': info['months'],
            'before': info['before'],
            'label': _("Fixed-term contract %(n)s in a row", n=info['count']),
            'rule': rule.name if rule else '',
            'rule_id': rule.id if rule else 0,
            'tone': '',
            'started': format_date(self.env, info['contracts'][0].date_start,
                                   date_format='d MMM y')
            if info['contracts'] and info['contracts'][0].date_start else '',
        }
        if rule:
            nxt = self.check_extension(contract, 12)
            if rule.max_in_row and info['count'] >= rule.max_in_row:
                out['tone'] = 'rose'
                out['next'] = _("The next one should be permanent under %s.",
                                rule.name)
            elif nxt.get('over'):
                out['tone'] = 'amber'
                out['next'] = nxt.get('sentence') or ''
        return out


class HrEmployeeFixedTerm(models.Model):
    _inherit = 'hr.employee'

    #: Contracts signed before the system was in use are not on it (facts §5):
    #: HR types them once. HR-only fields (ledger PRC-W1: an employee login can
    #: read its own employee record, so `groups=` is what keeps them HR's).
    pb_fixed_term_before = fields.Integer(
        string='Earlier fixed-term contracts (before this system)',
        groups='hr.group_hr_user',
        help='Fixed-term contracts this person had with you, in a row, before '
             'their contracts were kept here. They count towards the '
             'fixed-term rule.')
    pb_fixed_term_months_before = fields.Integer(
        string='Months on earlier fixed-term contracts (before this system)',
        groups='hr.group_hr_user',
        help='How long those earlier contracts ran in total, in months.')
