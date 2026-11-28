# -*- coding: utf-8 -*-
"""PSCHEME P1 D — changing the pay scheme of a PERSON, and reading it back.

Two doors on the board the "Who is paid by what" screen already talks to:

* `person_set(...)` — the only way a row of `pb.person.scheme` is written.
  It asks through the same route as every other Mapping change
  (`pb.schememap.proposal`, kind `person_set`, ledger R9): carried out at once
  where no second person checks (the fast lane), "Sent for approval"
  otherwise. HR officers and HR managers may ASK; carrying it out keeps
  today's gate (`_proposal_gate_groups`, a payroll manager).
* `person_scheme(employee_id)` — everything the person's "Pay scheme" panel
  and the "Change pay scheme" dialog show, in screen words.

THE WRITE (`_person_set_write`, ledger D.2) is one transaction and idempotent:
for the main kind the row in force on the start date is ended the day before
(a row that started on or after that date never took effect and is removed);
a new row starts on the date; the same scheme already in force writes
nothing. A main scheme of another kind (regular <-> end of month) ends the old
kind too, so nobody keeps two main schemes. The advance: a scheme gets the same
treatment, `False` ends it (R7: no advance unless given one), `'keep'` leaves it.
"""

import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    SCHEMEMAP_WRITE,
)

from .pb_person_scheme import SOURCES
from .pb_scheme_map import ADVANCE_RUNGS, MAIN_QUESTION

_logger = logging.getLogger(__name__)

#: Who may ASK for a person's pay scheme to change (ledger R9 / D.3): HR
#: officers and managers, and the payroll roles. Carrying it out is the
#: proposal's own gate, unchanged.
PROPOSE_GROUPS = (
    'hr.group_hr_user',
    'hr.group_hr_manager',
    'pb_hr_payroll_formula.group_formula_user',
    'pb_hr_payroll_formula.group_formula_manager',
    'om_hr_payroll.group_hr_payroll_user',
    'om_hr_payroll.group_hr_payroll_manager',
)
MAIN_KINDS = ('regular', 'end_cycle')
MAX_PEOPLE = 2000
MAX_HISTORY = 40
MAX_CHOICES = 80


def _first_of_next_month(day):
    return (day.replace(day=1) + relativedelta(months=1))


class PbSchemeBoardPerson(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ================================================================ gates
    @api.model
    def _can_propose_person(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=name: user.has_group(n), default=False)
                   for name in PROPOSE_GROUPS)

    @api.model
    def _can_carry_out_person(self):
        """The proposal's own carry-out gate, read the way the proposal reads
        it (`_proposal_check_gate`): superuser, or one of its groups."""
        Proposal = self.env.get('pb.schememap.proposal')
        user = self.env.user
        if user._is_superuser():
            return True
        groups = tuple(Proposal._proposal_gate_groups or ()) \
            if Proposal is not None else ('pb_hr_payroll_formula.group_formula_manager',)
        if not groups:
            return True
        return any(self._safe(lambda n=x: user.has_group(n), default=False)
                   for x in groups)

    @api.model
    def _person_lane(self, company):
        """`'fast'` (carried out at once), `'route'` (a second person
        approves) or `'none'` (no route at all: written at once by a person
        who may carry it out)."""
        if not self._map_held():
            return 'fast'
        Proposal = self.env['pb.schememap.proposal']
        try:
            return Proposal.sudo().with_company(company).route_mode(
                company, 'person_set')
        except Exception:       # noqa: BLE001 — a screen question, never fatal
            _logger.debug('person scheme: no route mode', exc_info=True)
            return 'route'

    # ============================================================= the words
    @api.model
    def _kind_words(self, cycle_type):
        return self.env['pb.scheme.map'].cycle_words(cycle_type)

    @api.model
    def _day_words(self, day):
        # "1 Dec 2026" in the reader's language — never a numeric date
        return format_date(self.env, day, date_format='d MMM y') if day else ''

    @api.model
    def _month_words(self, day):
        return format_date(self.env, day, date_format='MMMM y') if day else ''

    @api.model
    def _source_words(self, source):
        labels = {
            'fill': _("Filled in once"),
            'hire': _("Add employee"),
            'hand': _("Changed by hand"),
            'team': _("Set for the whole team"),
            'import': _("Pay data file"),
            'sheet': _("Upload sheet"),
            'job_change': _("Job change"),
        }
        return labels.get(source) or dict(SOURCES).get(source, '')

    @api.model
    def _scheme_card(self, config, counts=None):
        currency = config.currency_id
        return {
            'id': config.id,
            'name': config.name or '',
            'currency': currency.name or '' if currency else '',
            'symbol': currency.symbol or '' if currency else '',
            'kind': config.cycle_type or '',
            'kind_words': self._kind_words(config.cycle_type),
            'country_code': config.country_code or '',
            'country_name': self._country_name(config.country_code),
            'people': (counts or {}).get(config.id, 0),
        }

    @api.model
    def _country_name(self, code):
        if not code:
            return ''
        Config = self.env['hr.formula.config']
        labels = dict(Config._fields['country_code']._description_selection(
            self.env))
        return labels.get(code) or code

    # ====================================================== the snapshot
    @api.model
    def _person_snapshot(self, employee_ids, date_from):
        """`{employee_id: [[config_id, kind, from, until], …]}` — each person's
        rows counting on `date_from`, the proposal's "how it looked"."""
        day = fields.Date.to_date(date_from) or fields.Date.context_today(self)
        Map = self.env['pb.scheme.map'].sudo()
        rows = self.env['pb.person.scheme'].sudo().search([
            ('employee_id', 'in', [int(e) for e in employee_ids or []]),
            ('active', '=', True)], order='date_from, id')
        by_person = {}
        for row in rows:
            by_person.setdefault(row.employee_id.id, []).append(row)
        out = {}
        for employee_id in [int(e) for e in employee_ids or []]:
            counting, _ended = Map._person_rows_for(by_person.get(employee_id, []), day)
            out[str(employee_id)] = sorted(
                [[r.config_id.id, kind, fields.Date.to_string(r.date_from),
                  fields.Date.to_string(r.date_to) if r.date_to else '']
                 for kind, r in counting.items()])
        return out

    @api.model
    def _person_moved_words(self, before, now):
        """The proposal's "somebody changed this since" sentence, per person,
        in plain words (never a key or an id)."""
        out = []
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        Config = self.env['hr.formula.config'].sudo().with_context(active_test=False)

        def words(rows):
            names = [Config.browse(r[0]).exists().name or '' for r in rows or []]
            return ', '.join(n for n in names if n) or _("no pay scheme of their own")
        for key in sorted(set(before or {}) | set(now or {})):
            was, is_now = (before or {}).get(key) or [], (now or {}).get(key) or []
            if was == is_now:
                continue
            person = Employee.browse(int(key)).exists()
            out.append(_("%(person)s's pay scheme (was %(was)s, now %(now)s)",
                         person=person.name or '', was=words(was),
                         now=words(is_now)))
        return out

    # ============================================================== checks
    @api.model
    def _person_check(self, employees, config, advance):
        """Every refusal of ledger D.2, as one plain sentence each."""
        if not config:
            raise UserError(_("Pick the pay scheme first."))
        if config.state != 'active':
            raise UserError(_(
                "%(scheme)s is not switched on, so it cannot pay anybody. "
                "Switch it on first, or pick another pay scheme.",
                scheme=config.name or ''))
        if config.cycle_type == 'full_final':
            raise UserError(_(
                "%(scheme)s is a final settlement scheme. A person is not "
                "given one of their own: final settlements are worked out when "
                "somebody leaves.", scheme=config.name or ''))
        if config.cycle_type == 'mid_cycle':
            raise UserError(_(
                "%(scheme)s is a mid-month advance. Pick the pay scheme that "
                "pays the month, then add the advance with the switch below "
                "it.", scheme=config.name or ''))
        if advance:
            if advance.cycle_type != 'mid_cycle':
                raise UserError(_(
                    "%(scheme)s is not a mid-month advance, so it cannot pay "
                    "one. Pick a mid-month advance, or switch the advance off.",
                    scheme=advance.name or ''))
            if advance.state != 'active':
                raise UserError(_(
                    "%(scheme)s is not switched on, so it cannot pay anybody. "
                    "Switch it on first, or pick another pay scheme.",
                    scheme=advance.name or ''))
        for employee in employees:
            if not employee.active:
                raise UserError(_(
                    "%(person)s is archived, so their pay scheme cannot "
                    "change. Bring them back first.", person=employee.name or ''))
            for scheme in (config, advance):
                if scheme and scheme.company_id \
                        and scheme.company_id != employee.company_id:
                    raise UserError(_(
                        "%(scheme)s belongs to %(company)s, so it cannot pay "
                        "%(person)s.", scheme=scheme.name or '',
                        company=scheme.company_id.name or '',
                        person=employee.name or ''))
        return True

    @api.model
    def _person_args(self, employee_ids, config_id, advance_config_id,
                     date_from):
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        Config = self.env['hr.formula.config'].sudo()
        ids = [int(e) for e in (employee_ids or []) if e][:MAX_PEOPLE]
        employees = Employee.browse(ids).exists()
        if not employees:
            raise UserError(_("Nobody was given to change. Reload the screen "
                              "and try again."))
        config = Config.browse(int(config_id or 0)).exists()
        if advance_config_id == 'keep':
            advance = 'keep'
        elif advance_config_id:
            advance = Config.browse(int(advance_config_id)).exists()
            if not advance:
                raise UserError(_("That mid-month advance is not there any "
                                  "more. Reload the screen and try again."))
        else:
            advance = False
        day = fields.Date.to_date(date_from) if date_from else \
            _first_of_next_month(fields.Date.context_today(self))
        return employees, config, advance, day

    # =============================================================== the door
    @api.model
    def person_set(self, employee_ids, config_id, advance_config_id='keep',
                   date_from=None, company_id=None, source='hand', note=''):
        """Change these people's pay scheme from a date (ledger D.1 / D.2).

        Goes through the route every Mapping change goes through; the answer
        is the proposal's own `answer()` (plus `saved` / `pending`), or, where
        the change is written at once, `{'ok', 'applied', 'message'}`.
        """
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        employees, config, advance, day = self._person_args(
            employee_ids, config_id, advance_config_id, date_from)
        self._person_check(employees, config,
                           advance if advance not in ('keep', False) else None)
        source = source if source in dict(SOURCES) else 'hand'
        company = employees[:1].company_id or self.env.company
        if self._map_held():
            lane = self._person_lane(company)
            if lane in ('fast', 'none') and not self._can_carry_out_person():
                raise UserError(self._no_carry_out_sentence())
            if lane != 'none':
                return self._person_propose(employees, config, advance, day,
                                            company, source, note)
        # PSCHEME P2a: lane 'none' (no route at all) reached here with the map
        # still "held", and the writer's own guard refused the write — the
        # carry-out right was checked above, so this IS the approved write.
        changed = self.with_context(**{SCHEMEMAP_WRITE: True})._person_set_write(
            employees, config, advance, day, source=source, note=note)
        return {'ok': True, 'applied': True, 'pending': False,
                'changed': changed, 'message': _("Saved.")}

    @api.model
    def _no_carry_out_sentence(self):
        return _("A payroll manager carries out pay scheme changes here, and "
                 "nobody is set up to approve one. Ask a payroll manager to "
                 "make this change.")

    @api.model
    def _person_propose(self, employees, config, advance, day, company,
                        source, note):
        advance_value = advance if advance in ('keep', False) else advance.id
        if len(employees) == 1:
            title = _("Pay %(person)s by %(scheme)s from %(date)s",
                      person=employees.name or '', scheme=config.name or '',
                      date=self._day_words(day))
        else:
            title = _("Pay %(count)s people by %(scheme)s from %(date)s",
                      count=len(employees), scheme=config.name or '',
                      date=self._day_words(day))
        proposal = self.env['pb.schememap.proposal'].with_company(company).propose(
            'person_set', title,
            payload={'employee_ids': employees.ids, 'config_id': config.id,
                     'advance_config_id': advance_value,
                     'date_from': fields.Date.to_string(day),
                     'company_id': company.id, 'source': source,
                     'note': (note or '')[:200]},
            snapshot=self._person_snapshot(employees.ids, day),
            facts={'employees_moved': {'value': len(employees), 'unit': ''},
                   'schemes': {'value': 1 + (1 if advance not in ('keep', False)
                                             else 0), 'unit': ''}},
            target=employees[:1] if len(employees) == 1 else config,
            company=company,
        )
        answer = proposal.answer()
        answer['saved'] = bool(answer.get('applied'))
        if answer['saved']:
            answer['message'] = _("Saved.")
        elif answer.get('block_note') or (proposal.approval_request_id
                                          and proposal.approval_request_id.block_reason):
            answer['ok'] = False
            answer['message'] = answer.get('block_note') or \
                proposal.approval_request_id.block_reason
        else:
            answer['message'] = _("Sent for approval.")
            if answer.get('with_whom'):
                answer['message'] = _("Sent for approval to %s.",
                                      answer['with_whom'])
        return answer

    # ============================================================= the write
    @api.model
    def _person_set_write(self, employees, config, advance='keep', date_from=None,
                          source='hand', note=''):
        """The rows of ledger D.2, for every person, in one transaction.
        Idempotent. Returns how many rows were created, ended or removed."""
        if not self.env.context.get(SCHEMEMAP_WRITE) and not self.env.su \
                and self._map_held():
            # The ONLY callers are `person_set` (lane checked) and the hire's
            # own apply (sudo); anything else is a bypass of the route.
            raise AccessError(_("A pay scheme change goes through approval."))
        self._person_check(employees, config,
                           advance if advance not in ('keep', False) else None)
        day = fields.Date.to_date(date_from) or fields.Date.context_today(self)
        Row = self.env['pb.person.scheme'].sudo()
        self.env.flush_all()
        changed = 0
        for employee in employees:
            changed += self._person_set_kind(Row, employee, config, day, source, note)
            for kind in MAIN_KINDS:
                if kind != (config.cycle_type or 'regular'):
                    changed += self._person_end_kind(Row, employee, kind, day)
            if advance == 'keep':
                continue
            if advance:
                changed += self._person_set_kind(Row, employee, advance, day,
                                                 source, note)
            else:
                changed += self._person_end_kind(Row, employee, 'mid_cycle', day)
        self.env.flush_all()
        return changed

    @api.model
    def _person_kind_rows(self, Row, employee, kind):
        return Row.search([('employee_id', '=', employee.id),
                           ('cycle_type', '=', kind), ('active', '=', True)],
                          order='date_from, id')

    @api.model
    def _person_end_kind(self, Row, employee, kind, day):
        """No row of this kind counts from `day` on: the one in force ends the
        day before; one that starts on or after `day` never took effect."""
        changed = 0
        for row in self._person_kind_rows(Row, employee, kind):
            if row.date_from >= day:
                row.unlink()
                changed += 1
            elif not row.date_to or row.date_to >= day:
                row.date_to = day - timedelta(days=1)
                changed += 1
        return changed

    @api.model
    def _person_set_kind(self, Row, employee, config, day, source, note):
        kind = config.cycle_type or 'regular'
        rows = self._person_kind_rows(Row, employee, kind)
        in_force = rows.filtered(lambda r: r.date_from < day
                                 and (not r.date_to or r.date_to >= day))[-1:]
        if in_force and in_force.config_id == config:
            changed = 0
            for row in rows.filtered(lambda r: r.date_from >= day):
                row.unlink()
                changed += 1
            if in_force.date_to:
                in_force.date_to = False
                changed += 1
            return changed
        same_day = rows.filtered(lambda r: r.date_from == day)
        if same_day and len(same_day) == 1 and same_day.config_id == config \
                and not same_day.date_to \
                and not rows.filtered(lambda r: r.date_from > day):
            return 0            # already exactly this, from this day
        changed = self._person_end_kind(Row, employee, kind, day)
        Row.create({'employee_id': employee.id, 'config_id': config.id,
                    'date_from': day, 'source': source,
                    'note': (note or '')[:200] or False})
        return changed + 1

    # ============================================================== the read
    @api.model
    def person_scheme(self, employee_id):
        """Everything the person's "Pay scheme" panel and the "Change pay
        scheme" dialog show (ledger D.4). Screen words only."""
        if not self._can_read():
            raise AccessError(_("You cannot see who pays this person."))
        employee = self.env['hr.employee'].sudo().with_context(
            active_test=False).browse(int(employee_id or 0)).exists()
        if not employee:
            return {'found': False}
        company = employee.company_id
        today = fields.Date.context_today(self)
        Map = self.env['pb.scheme.map'].sudo()
        Config = self.env['hr.formula.config'].sudo()
        main_cycle = self.env['hr.employee']._pb_main_cycle(company.id)
        main = Map.with_context(**{MAIN_QUESTION: True}).resolve(
            employee.id, main_cycle, on_date=today)
        second = Map.resolve(employee.id, 'mid_cycle', on_date=today)
        code = employee.payroll_country or ''

        # ---- the schemes of their Country of work, then the others
        counts = {}
        if 'pb_paid_by_id' in employee._fields:
            for config, n in self.env['hr.employee'].sudo()._read_group(
                    [('company_id', '=', company.id), ('active', '=', True),
                     ('pb_paid_by_id', '!=', False)],
                    ['pb_paid_by_id'], ['__count']):
                counts[config.id] = n
        every = Config.search([
            ('state', '=', 'active'), ('cycle_type', 'in', MAIN_KINDS),
            '|', ('company_id', '=', False), ('company_id', '=', company.id)],
            order='name, id', limit=MAX_CHOICES)
        mine = Map._country_schemes(company.id, code).filtered(
            lambda c: c.cycle_type in MAIN_KINDS) if code else Config
        choices = [self._scheme_card(c, counts) for c in mine]
        others = [self._scheme_card(c, counts) for c in every if c not in mine]

        # ---- the rows
        rows = self.env['pb.person.scheme'].sudo().search(
            [('employee_id', '=', employee.id), ('active', '=', True)],
            order='date_from desc, id desc', limit=MAX_HISTORY)
        counting, _ended = Map._person_rows_for(list(rows), today)
        later = rows.filtered(lambda r: r.date_from > today
                              and r not in counting.values())
        upcoming = later.sorted(lambda r: (r.date_from, r.cycle_type == 'mid_cycle',
                                           r.id))[:1]

        def block(answer, kind_ok):
            config = Config.browse(answer.get('config_id') or 0).exists()
            if not config or not kind_ok:
                return None
            card = self._scheme_card(config, counts)
            own = answer.get('rung') == 'person'
            since = fields.Date.to_date(answer.get('date_from')) if own else None
            card.update({
                'own': own,
                'since': fields.Date.to_string(since) if since else '',
                'since_words': self._day_words(since),
                'from_words': self._from_words(answer, employee, since, today),
            })
            return card

        current = block(main, True)
        advance = block(second, second.get('rung') in ADVANCE_RUNGS)
        if advance and current and advance['id'] == current['id']:
            advance = None
        waiting = self._person_waiting(employee)
        return {
            'found': True,
            'employee': {'id': employee.id, 'name': employee.name or '',
                         'first_name': (employee.name or '').split(' ')[0],
                         'active': bool(employee.active),
                         'country_code': code,
                         'country_name': self._country_name(code)},
            'company_id': company.id,
            'main': current,
            'advance': advance,
            'none_words': '' if current else (main.get('via') or ''),
            'next': {
                'scheme': upcoming.config_id.name or '',
                'kind_words': self._kind_words(upcoming.cycle_type),
                'advance': upcoming.cycle_type == 'mid_cycle',
                'date': fields.Date.to_string(upcoming.date_from),
                'date_words': self._day_words(upcoming.date_from),
            } if upcoming else None,
            'waiting': waiting,
            'history': [{
                'id': r.id,
                'scheme': r.config_id.name or '',
                'kind_words': self._kind_words(r.cycle_type),
                'advance': r.cycle_type == 'mid_cycle',
                'from_words': self._day_words(r.date_from),
                'until_words': self._day_words(r.date_to),
                'source_words': self._source_words(r.source),
                'now': r in counting.values(),
            } for r in rows],
            'choices': choices,
            'others': others,
            'advances': self._advance_pairs([c['id'] for c in choices + others]),
            'can_propose': self._can_propose_person(),
            'can_carry_out': self._can_carry_out_person(),
            'lane': self._person_lane(company),
            'blocked': self._person_blocked(company),
            'default_date': fields.Date.to_string(_first_of_next_month(today)),
            'today': fields.Date.to_string(today),
            'old_month_words': self._month_words(today),
        }

    @api.model
    def _person_blocked(self, company):
        lane = self._person_lane(company)
        if lane in ('fast', 'none') and not self._can_carry_out_person():
            return self._no_carry_out_sentence()
        return ''

    @api.model
    def _from_words(self, answer, employee, since, today):
        rung = answer.get('rung')
        if rung == 'person':
            if since and since > today:
                return _("Their own pay scheme from %s", self._day_words(since))
            return _("Their own pay scheme since %s", self._day_words(since))
        if rung == 'department':
            team = employee.department_id
            return _("From %s's usual pay scheme", team.name or '') if team \
                else _("From their team's usual pay scheme")
        if rung == 'division':
            return _("From their division's usual pay scheme")
        if rung == 'rule':
            return _("From a rule on the map")
        if rung == 'only':
            return _("The only pay scheme in this company")
        return answer.get('via') or ''

    @api.model
    def _person_waiting(self, employee):
        Proposal = self.env.get('pb.schememap.proposal')
        if Proposal is None:
            return None
        proposal = Proposal.sudo().search([
            ('kind', '=', 'person_set'), ('state', '=', 'pending'),
            ('target_model', '=', 'hr.employee'),
            ('target_id', '=', employee.id)], order='id desc', limit=1)
        if not proposal:
            return None
        payload = proposal.payload() or {}
        config = self.env['hr.formula.config'].sudo().browse(
            int(payload.get('config_id') or 0)).exists()
        day = fields.Date.to_date(payload.get('date_from')) \
            if payload.get('date_from') else None
        return {'reference': proposal.name or '',
                'scheme': config.name or '',
                'date': payload.get('date_from') or '',
                'date_words': self._day_words(day),
                'with_whom': proposal.waiting_for() or ''}

    @api.model
    def _advance_pairs(self, config_ids):
        """`{str(main_id): [{id, name}]}` — the mid-month advances paired to
        each scheme (`hr.payroll.cycle.component.mapping`). The screen ticks
        the advance by default only when there is exactly ONE."""
        if not config_ids or 'hr.payroll.cycle.component.mapping' not in self.env:
            return {}
        rows = self.env['hr.payroll.cycle.component.mapping'].sudo().search([
            ('end_cycle_config_id', 'in', list(config_ids)),
            ('active', '=', True)])
        out = {}
        for row in rows:
            advance = row.mid_cycle_config_id
            if not advance or advance.state != 'active' \
                    or advance.cycle_type != 'mid_cycle':
                continue
            bucket = out.setdefault(str(row.end_cycle_config_id.id), [])
            if all(a['id'] != advance.id for a in bucket):
                bucket.append({'id': advance.id, 'name': advance.name or ''})
        return out
