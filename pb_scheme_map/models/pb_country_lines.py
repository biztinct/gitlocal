# -*- coding: utf-8 -*-
"""PSCHEME P4 B — "Usual pay scheme by country" on Mapping › Who is paid by what.

THE SAFETY NET, MADE VISIBLE
----------------------------
Somebody who arrives WITHOUT a pay scheme of their own is caught, in order, by
their team's usual scheme (optional) and then by their country's usual scheme.
The second one has always existed — a rule line on the map whose whole domain
is "Country of work = X" — but no screen could show it, set it or take it off
(closeout §6, F1: the screen-twin gap). This file is its screen twin.

WHAT A COUNTRY LINE IS (B.1)
----------------------------
An active `hr.formula.scheme.assignment` with neither team nor division whose
domain is EXACTLY ``[('payroll_country', '=', X)]``, optionally with the
company term ``('company_id', '=', <the line's company>)`` that F1 and every
earlier rize rule wrote. Anything else with a domain — a list of named people,
any other condition — is an "other rule": shown read-only, set up by support.

HOW IT IS CHANGED (B.4)
-----------------------
One new approval kind, ``country_set`` on ``pb.schememap.proposal``: set,
change or remove one country line (and, under the same kind, remove an other
rule that reaches nobody a country line or an own row does not already cover).
Same route as every Mapping change, the fast lane where nobody else checks,
the same proposer rights as a person's pay scheme (HR and payroll) and the same
carry-out gate. The proposal re-reads the line when it is approved and refuses
in plain words when somebody changed it meanwhile.

A new line is written AFTER the company's other rules (`sequence`), so a
narrower named-people rule keeps winning; the write compares every affected
person's answer before and after and reports anybody whose answer moved for any
reason other than "nothing caught them before".
"""

import ast
import logging
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    SCHEMEMAP_WRITE, PbSchemeMapProposal,
)

from .pb_scheme_map import MAIN_QUESTION, SKIP_PERSON

_logger = logging.getLogger(__name__)

KIND = 'country_set'
MAIN_KINDS = ('regular', 'end_cycle')
TEAM_RUNGS = ('segment', 'department', 'division')
#: employee fields that make a domain "a list of named people"
NAMED_FIELDS = ('id', 'barcode', 'identification_id', 'pb_clock_code',
                'employee_id', 'name', 'work_email', 'registration_number')


def _terms(domain_text):
    """The domain as a plain list of 3-tuples, or None when it is anything
    but a flat AND of simple terms (a literal, never evaluated code)."""
    try:
        value = ast.literal_eval((domain_text or '').strip() or '[]')
    except (ValueError, SyntaxError):
        return None
    if not isinstance(value, (list, tuple)):
        return None
    out = []
    for term in value:
        if not isinstance(term, (list, tuple)) or len(term) != 3:
            return None
        out.append(tuple(term))
    return out


def line_country(row):
    """The Country of work a map line is the usual scheme of, or ''.

    Exactly ``[('payroll_country', '=', X)]``, with at most the company term
    of the line's own company beside it (B.1)."""
    if not row.domain or row.department_id or row.division_id:
        return ''
    terms = _terms(row.domain)
    if not terms:
        return ''
    country = [t for t in terms if t[0] == 'payroll_country' and t[1] == '='
               and isinstance(t[2], str) and t[2]]
    rest = [t for t in terms if t not in country]
    if len(country) != 1:
        return ''
    if rest:
        if len(rest) != 1:
            return ''
        field, op, value = rest[0]
        if field != 'company_id' or op != '=' or not row.company_id \
                or value != row.company_id.id:
            return ''
    return country[0][2]


class PbSchemeBoardCountry(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ============================================================ reading
    @api.model
    def _country_labels(self):
        return dict(self.env['hr.employee']._fields['payroll_country']
                    ._description_selection(self.env))

    @api.model
    def _map_rules(self, company_id):
        """Every rule line answering this company today, in the ladder's own
        order (sequence, id), split into country lines and other rules."""
        Map = self.env['pb.scheme.map'].sudo()
        rows = Map._map_rows([company_id])
        rules = [r for r in rows if r.domain and not r.department_id
                 and not r.division_id and r.company_id.id == company_id]
        country, other = defaultdict(list), []
        for row in rules:
            code = line_country(row)
            if code:
                country[code].append(row)
            else:
                other.append(row)
        return country, other

    @api.model
    def _country_facts(self, company_id):
        """Who works where, who has a row of their own, and what catches
        everybody else today — read once for the whole company."""
        Map = self.env['pb.scheme.map'].sudo().with_company(company_id).with_context(
            allowed_company_ids=[company_id])
        roster = Map._departments_for(company_ids=[company_id])
        ids = sorted(roster)
        own = set(Map._person_schemes(ids)) if ids else set()
        countries = {}
        if ids:
            for rec in self.env['hr.employee'].sudo().search_read(
                    [('id', 'in', ids)], ['payroll_country']):
                countries[rec['id']] = rec['payroll_country'] or ''
        main_kind = self.env['hr.employee']._pb_main_cycle(company_id)
        free = [i for i in ids if i not in own]
        answers = Map.with_context(**{SKIP_PERSON: True, MAIN_QUESTION: True}).resolve_many(
            free, main_kind) if free else {}
        return {'ids': ids, 'own': own, 'countries': countries,
                'answers': answers, 'main_kind': main_kind}

    @api.model
    def country_lines(self, company_id=None):
        """The section's payload (B.2 / B.3). Writes nothing."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this company's people."))
        company_id = self._pick_company(company_id)
        Config = self.env['hr.formula.config'].sudo()
        labels = self._country_labels()
        country_rows, other_rows = self._map_rules(company_id)
        facts = self._country_facts(company_id)
        people_by = defaultdict(int)
        rely_by, hole_by, other_by = defaultdict(int), defaultdict(int), defaultdict(int)
        for employee_id in facts['ids']:
            code = facts['countries'].get(employee_id, '')
            if not code:
                continue
            people_by[code] += 1
            if employee_id in facts['own']:
                continue
            answer = facts['answers'].get(employee_id) or {}
            if answer.get('rung') in TEAM_RUNGS:
                continue
            rely_by[code] += 1
            if not answer.get('config_id'):
                hole_by[code] += 1
            elif answer.get('rung') == 'rule':
                line = (country_rows.get(code) or [None])[0]
                if not line or answer.get('config_id') != line.config_id.id:
                    other_by[code] += 1
        schemes = Config.search([
            ('state', '=', 'active'), ('cycle_type', 'in', MAIN_KINDS),
            '|', ('company_id', '=', False), ('company_id', '=', company_id)],
            order='name, id')
        scheme_codes = {c.country_code for c in schemes if c.country_code}
        codes = sorted(set(people_by) | scheme_codes | set(country_rows),
                       key=lambda c: (-people_by.get(c, 0), labels.get(c, c)))
        rows = []
        for code in codes:
            options = schemes.filtered(lambda c, code=code: c.country_code == code)
            line = (country_rows.get(code) or [None])[0]
            state = 'set' if line else ('not_set' if options else 'no_scheme')
            rows.append({
                'country': code,
                'country_name': labels.get(code) or code,
                'people': people_by.get(code, 0),
                'rely': rely_by.get(code, 0),
                'holes': hole_by.get(code, 0) if not line else 0,
                'by_other_rule': other_by.get(code, 0),
                'state': state,
                'line': ({'id': line.id, 'config_id': line.config_id.id,
                          'config': line.config_id.name or '',
                          'currency': line.config_id.currency_id.name or '',
                          'kind_words': self._kind_words(line.config_id.cycle_type),
                          'other_country': bool(line.config_id.country_code
                                                and line.config_id.country_code != code),
                          'extra_lines': len(country_rows[code]) - 1}
                         if line else None),
                'options': [{'id': c.id, 'name': c.name or '',
                             'currency': c.currency_id.name or '',
                             'kind_words': self._kind_words(c.cycle_type)}
                            for c in options],
            })
        others = self._other_rules(company_id, other_rows, country_rows, facts)
        company = self.env['res.company'].sudo().browse(company_id)
        holes = sum(r['holes'] for r in rows)
        return {
            'company_id': company_id,
            'rows': rows,
            'others': others,
            'holes': holes,
            'set': len([r for r in rows if r['state'] == 'set']),
            'other_schemes': [{'id': c.id, 'name': c.name or '',
                               'country': c.country_code or '',
                               'country_name': labels.get(c.country_code or '', '') or '',
                               'currency': c.currency_id.name or '',
                               'kind_words': self._kind_words(c.cycle_type)}
                              for c in schemes],
            'can_propose': self._can_propose_person(),
            'lane': self._person_lane(company),
            'blocked': self._person_blocked(company),
        }

    @api.model
    def _other_rules(self, company_id, other_rows, country_rows, facts):
        """B.3 — every other rule, in plain words, with whom it reaches today
        and whether taking it off would leave anybody uncaught."""
        Employee = self.env['hr.employee'].sudo()
        out = []
        for row in other_rows:
            terms = _terms(row.domain) or []
            named = next((t for t in terms if t[0] in NAMED_FIELDS and t[1] == 'in'
                          and isinstance(t[2], (list, tuple))), None)
            try:
                reached = Employee.search([('id', 'in', facts['ids'])]
                                          + row._employee_domain())
            except Exception:       # noqa: BLE001 — a broken rule is listed, never fatal
                _logger.warning('Scheme map: rule %s could not be read', row.id)
                reached = Employee
            uncovered = 0
            for employee in reached:
                if employee.id in facts['own']:
                    continue
                code = facts['countries'].get(employee.id, '')
                line = (country_rows.get(code) or [None])[0]
                if not line or line.config_id != row.config_id:
                    uncovered += 1
            if named:
                words = _("A list of %(count)s named people", count=len(named[2]))
            else:
                words = _("People matching a special rule")
            out.append({
                'id': row.id,
                'words': words,
                'config': row.config_id.name or '',
                'reaches': len(reached),
                'uncovered': uncovered,
                'removable': not uncovered,
                'why_not': ((_("1 of them has no pay scheme of their own and no "
                               "country line that pays them the same way.")
                             if uncovered == 1 else
                             _("%(count)s of them have no pay scheme of their own "
                               "and no country line that pays them the same way.",
                               count=uncovered)) if uncovered else ''),
            })
        return out

    @api.model
    def _from_words(self, answer, employee, since, today):
        """A person caught by their country's line reads "From the usual pay
        scheme of Vietnam" on their panel, not "from a rule on the map"."""
        if answer.get('rung') == 'rule' and employee.payroll_country:
            lines = self._map_rules(employee.company_id.id)[0].get(employee.payroll_country) or []
            if lines and lines[0].config_id.id == answer.get('config_id'):
                return _("From the usual pay scheme of %s",
                         self._country_labels().get(employee.payroll_country, ''))
        return super()._from_words(answer, employee, since, today)

    # ============================================================ the door
    @api.model
    def _country_check(self, company_id, country_code, config, confirm_other):
        labels = self._country_labels()
        if country_code not in labels:
            raise UserError(_("That country of work is not one this system knows. "
                              "Reload the screen and try again."))
        if not config:
            return
        if config.state != 'active':
            raise UserError(_("%s is not active. Switch it on first, or choose an "
                              "active pay scheme.", config.name or ''))
        if config.company_id and config.company_id.id != company_id:
            raise UserError(_("%s belongs to another company, so it cannot pay "
                              "people here.", config.name or ''))
        if config.cycle_type == 'mid_cycle':
            raise UserError(_("%s is a mid-month advance. A country's usual pay "
                              "scheme is the one that pays the month.", config.name or ''))
        if config.cycle_type not in MAIN_KINDS:
            raise UserError(_("%s is not a monthly pay scheme, so it cannot be a "
                              "country's usual pay scheme.", config.name or ''))
        if config.country_code and config.country_code != country_code \
                and not confirm_other:
            raise UserError(_(
                "%(scheme)s is a pay scheme of %(other)s. Tick \"This pay scheme is "
                "of another country\" to use it for %(country)s.",
                scheme=config.name or '', other=labels.get(config.country_code, ''),
                country=labels.get(country_code, '')))

    @api.model
    def country_set(self, company_id, country_code, config_id=False,
                    confirm_other=False):
        """Set, change (`config_id`) or remove (`config_id` False) a country's
        usual pay scheme — through the Mapping route (B.4)."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing who pays people is for HR and payroll. Ask one of them "
                "to make the change."))
        company_id = self._pick_company(company_id)
        company = self.env['res.company'].sudo().browse(company_id)
        config = self.env['hr.formula.config'].sudo().browse(int(config_id or 0)).exists()
        self._country_check(company_id, country_code, config, confirm_other)
        country_rows, _other = self._map_rules(company_id)
        current = (country_rows.get(country_code) or [None])[0]
        if not config and not current:
            raise UserError(_("%s has no usual pay scheme to remove.",
                              self._country_labels().get(country_code, '')))
        if config and current and current.config_id == config \
                and len(country_rows.get(country_code)) == 1:
            raise UserError(_("%s is already this country's usual pay scheme.",
                              config.name or ''))
        payload = {'action': 'set', 'company_id': company_id, 'country': country_code,
                   'config_id': config.id if config else 0}
        title = (_("Pay people in %(country)s without a pay scheme of their own by %(scheme)s",
                   country=self._country_labels().get(country_code, ''), scheme=config.name or '')
                 if config else
                 _("Remove the usual pay scheme of %s", self._country_labels().get(country_code, '')))
        return self._country_route(company, payload, title,
                                   {'line': current.config_id.id if current else 0})

    @api.model
    def other_rule_remove(self, assignment_id, company_id=None):
        """B.3 — take off an other rule, only when it reaches nobody that a
        country line or an own row does not already cover."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing who pays people is for HR and payroll. Ask one of them "
                "to make the change."))
        company_id = self._pick_company(company_id)
        company = self.env['res.company'].sudo().browse(company_id)
        country_rows, other_rows = self._map_rules(company_id)
        row = next((r for r in other_rows if r.id == int(assignment_id or 0)), None)
        if not row:
            raise UserError(_("That rule is not on this company's map any more. "
                              "Reload the screen."))
        facts = self._country_facts(company_id)
        info = self._other_rules(company_id, [row], country_rows, facts)[0]
        if not info['removable']:
            raise UserError(_("This rule cannot be taken off yet: %s", info['why_not']))
        payload = {'action': 'remove_rule', 'company_id': company_id,
                   'assignment_id': row.id}
        return self._country_route(
            company, payload, _("Take off the rule that pays %(who)s by %(scheme)s",
                                who=info['words'], scheme=row.config_id.name or ''),
            {'rule': row.config_id.id})

    @api.model
    def _country_route(self, company, payload, title, snapshot):
        if self._map_held():
            lane = self._person_lane(company)
            if lane in ('fast', 'none') and not self._can_carry_out_person():
                raise UserError(self._no_carry_out_sentence())
            if lane != 'none':
                proposal = self.env['pb.schememap.proposal'].with_company(company).propose(
                    KIND, title, payload=payload, snapshot=snapshot,
                    facts={'employees_moved': {'value': 0, 'unit': ''},
                           'schemes': {'value': 1 if payload.get('config_id') else 0,
                                       'unit': ''}},
                    company=company)
                answer = proposal.answer()
                answer['saved'] = bool(answer.get('applied'))
                if answer['saved']:
                    answer['message'] = _("Saved.")
                    answer.update(proposal.result() or {})
                elif answer.get('block_note'):
                    answer['ok'] = False
                    answer['message'] = answer['block_note']
                else:
                    answer['message'] = _("Sent for approval to %s.", answer['with_whom']) \
                        if answer.get('with_whom') else _("Sent for approval.")
                return answer
        result = self.with_context(**{SCHEMEMAP_WRITE: True})._country_write(payload)
        return dict(result, ok=True, applied=True, saved=True, pending=False,
                    message=_("Saved."))

    # ============================================================ the write
    @api.model
    def _country_live(self, payload):
        """What the proposal is about, re-read now (the re-check)."""
        company_id = int(payload.get('company_id') or 0)
        country_rows, other_rows = self._map_rules(company_id)
        if payload.get('action') == 'remove_rule':
            row = next((r for r in other_rows
                        if r.id == int(payload.get('assignment_id') or 0)), None)
            return {'rule': row.config_id.id if row else 0}
        current = (country_rows.get(payload.get('country')) or [None])[0]
        return {'line': current.config_id.id if current else 0}

    @api.model
    def _country_write(self, payload):
        """The approved write. Never touches team lines, person rows or any
        other rule; answers who moved (B.4)."""
        if not self.env.context.get(SCHEMEMAP_WRITE) and not self.env.su \
                and self._map_held():
            raise AccessError(_("A change to who pays people goes through approval."))
        Assign = self.env['hr.formula.scheme.assignment'].sudo()
        company_id = int(payload.get('company_id') or 0)
        facts = self._country_facts(company_id)
        before = facts['answers']
        country_rows, other_rows = self._map_rules(company_id)
        code = payload.get('country') or ''
        if payload.get('action') == 'remove_rule':
            row = Assign.browse(int(payload.get('assignment_id') or 0)).exists()
            if row:
                row.active = False
        else:
            config = self.env['hr.formula.config'].sudo().browse(
                int(payload.get('config_id') or 0)).exists()
            lines = country_rows.get(code) or []
            if config:
                if lines:
                    lines[0].config_id = config.id
                    for extra in lines[1:]:
                        extra.active = False
                else:
                    sequences = [r.sequence for r in other_rows] + \
                        [r.sequence for rs in country_rows.values() for r in rs]
                    after_others = (max(r.sequence for r in other_rows) + 1) \
                        if other_rows else max(sequences or [10])
                    Assign.create({
                        'config_id': config.id,
                        'domain': "[('company_id', '=', %s), ('payroll_country', '=', '%s')]"
                                  % (company_id, code),
                        'cycle_type': config.cycle_type if config.cycle_type in MAIN_KINDS
                        else 'any',
                        'sequence': after_others,
                        'source': 'manual',
                        'note': _("Usual pay scheme of a country"),
                    })
            else:
                for line in lines:
                    line.active = False
        self.env.flush_all()
        after = self._country_facts(company_id)['answers']
        caught = moved = lost = 0
        for employee_id, was in before.items():
            now = after.get(employee_id) or {}
            if (was or {}).get('config_id') == now.get('config_id'):
                continue
            if not (was or {}).get('config_id'):
                caught += 1
            elif not now.get('config_id'):
                lost += 1
            else:
                moved += 1
        if moved:
            _logger.warning('Scheme map: a country line change moved %s people '
                            'who were paid by another line (company %s, %s)',
                            moved, company_id, code)
        return {'caught': caught, 'moved': moved, 'lost': lost}


class PbSchemeMapProposalCountry(models.Model):
    """The approval side of `country_set` — here, beside the board that
    answers it, so the formula engine keeps no dependency on this module."""
    _inherit = 'pb.schememap.proposal'

    _proposal_kind_labels = dict(
        PbSchemeMapProposal._proposal_kind_labels,
        country_set="Set a country's usual pay scheme")

    def _proposal_kind_label(self, kind=None):
        if (kind or self.kind) == KIND:
            return _("Set a country's usual pay scheme")
        return super()._proposal_kind_label(kind)

    def _live_snapshot(self):
        self.ensure_one()
        if self.kind == KIND:
            board = self._person_board()
            return board._country_live(self.payload() or {}) if board is not None else {}
        return super()._live_snapshot()

    def _proposal_moved(self):
        self.ensure_one()
        if self.kind != KIND:
            return super()._proposal_moved()
        if (self.snapshot() or {}) == (self._live_snapshot() or {}):
            return []
        payload = self.payload() or {}
        if payload.get('action') == 'remove_rule':
            return [_("that rule")]
        board = self._person_board()
        label = board._country_labels().get(payload.get('country'), '') if board is not None else ''
        return [_("the usual pay scheme of %s", label)]

    def _apply_country_set(self):
        board = self._board()
        return board._country_write(self.payload() or {})

    def _proposal_rows(self):
        self.ensure_one()
        if self.kind != KIND:
            return super()._proposal_rows()
        payload = self.payload() or {}
        board = self._person_board()
        if payload.get('action') == 'remove_rule':
            return [(_('Rule to take off'), '', self._row_label(
                'hr.formula.scheme.assignment', payload.get('assignment_id'))),
                (_('What happens'), '', _('Everybody it reached is paid by their own '
                                          'pay scheme or their country line'))]
        label = board._country_labels().get(payload.get('country'), '') if board is not None else ''
        before = self._row_label('hr.formula.config', (self.snapshot() or {}).get('line')) \
            or _('None')
        after = self._row_label('hr.formula.config', payload.get('config_id')) or _('None')
        return [(_('Country of work'), '', label),
                (_('Usual pay scheme'), before, after)]
