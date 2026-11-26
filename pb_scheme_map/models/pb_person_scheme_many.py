# -*- coding: utf-8 -*-
"""PSCHEME P2a — many people's pay schemes in ONE request.

P1 built one door, `person_set`, for one scheme from one date. Two screens of
this phase change many people at once and need more than that:

* "Set for everyone in this team" (ledger R8): one scheme, but TWO dates — the
  people without a pay scheme of their own from the first day of this month,
  and the people who are moved from the date the reader picks.
* "Give everyone their own pay scheme" (the one-time fill, ledger R3): every
  person keeps the scheme that pays them today, so one request carries many
  schemes, each with its own people.

Both go through `person_set_many(groups, …)`: a list of groups, each
`{employee_ids, config_id, advance_config_id, date_from}`. It is the same
route as every Mapping change (`pb.schememap.proposal`, kind `person_set`,
ledger R9): carried out at once where nobody else checks, "Sent for approval"
otherwise. The payload simply carries `groups`; the approval applies them
through `_person_groups_write`, which calls P1's one writer
(`_person_set_write`) once per group. Nothing here writes a row by itself and
nothing here touches a line on the map (FACTS T13: never `accept_draft`).

WHEN SOMEBODY CHANGED A PERSON WHILE THE REQUEST WAITED (test T4): the whole
request is refused with the person named (P1's `_approval_apply`). An approver
approved exactly this list; carrying out a part of it would write something
nobody approved as a whole. Asking again is one press — the drawers plan again
from what is there now.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_hr_payroll_formula.models.schememap_approval import (
    SCHEMEMAP_WRITE, PbSchemeMapProposal,
)

from .pb_person_scheme import SOURCES

_logger = logging.getLogger(__name__)

#: A fill or a team can be bigger than P1's single-change cap; the board's
#: roster is capped at 20,000 (`MAX_EMPLOYEES`), so is this.
MAX_GROUP_PEOPLE = 20000
MAX_GROUPS = 400
MAX_WAITING_SCAN = 60


def format_day(env, day):
    return format_date(env, day, date_format='d MMM y') if day else ''


class PbSchemeBoardMany(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    # ============================================================ the groups
    @api.model
    def _groups_clean(self, groups):
        """`[(employees, config, advance, day)]` — every group the payload
        names, empty ones dropped, each read the way `person_set` reads its
        arguments (same refusals, same sentences)."""
        out = []
        for group in (groups or [])[:MAX_GROUPS]:
            ids = [int(e) for e in (group.get('employee_ids') or []) if e]
            if not ids:
                continue
            Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
            employees = Employee.browse(ids[:MAX_GROUP_PEOPLE]).exists()
            if not employees:
                continue
            _e, config, advance, day = self._person_args(
                employees.ids[:1], group.get('config_id'),
                group.get('advance_config_id', 'keep'), group.get('date_from'))
            out.append((employees, config, advance, day))
        return out

    @api.model
    def _groups_plain(self, cleaned):
        """The JSON-plain payload of the cleaned groups (NH8)."""
        return [{
            'employee_ids': employees.ids,
            'config_id': config.id,
            'advance_config_id': advance if advance in ('keep', False) else advance.id,
            'date_from': fields.Date.to_string(day),
        } for employees, config, advance, day in cleaned]

    @api.model
    def _person_snapshot_groups(self, groups):
        """P1's snapshot, per group: each person's rows counting on the day
        THEIR group starts. Keys are employee ids, so P1's plain "somebody
        changed X's pay scheme" sentence works unchanged."""
        out = {}
        for group in groups or []:
            out.update(self._person_snapshot(group.get('employee_ids') or [],
                                             group.get('date_from')))
        return out

    # ============================================================== the door
    @api.model
    def person_set_many(self, groups, company_id=None, source='hand', note='',
                        title='', extra=None):
        """Change many people's pay schemes in ONE request (see the module
        docstring). Answers like `person_set`: the proposal's own answer
        (`saved` / `pending` / `message`), or `{'ok', 'applied', 'changed',
        'created'}` when it is written at once."""
        if not self._can_propose_person():
            raise AccessError(_(
                "Changing a person's pay scheme is for HR and payroll. Ask one "
                "of them to make the change."))
        cleaned = self._groups_clean(groups)
        if not cleaned:
            raise UserError(_("Nobody was ticked. Tick the people to change "
                              "first."))
        everyone = self.env['hr.employee'].sudo().browse()
        for employees, config, advance, _day in cleaned:
            self._person_check(employees, config,
                               advance if advance not in ('keep', False) else None)
            everyone |= employees
        companies = everyone.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_("These people work for more than one company. "
                              "Change one company's people at a time."))
        source = source if source in dict(SOURCES) else 'hand'
        company = companies[:1] or self.env.company
        if self._map_held():
            lane = self._person_lane(company)
            if lane in ('fast', 'none') and not self._can_carry_out_person():
                raise UserError(self._no_carry_out_sentence())
            if lane != 'none':
                return self._person_propose_many(cleaned, everyone, company,
                                                 source, note, title, extra)
        result = self.with_context(**{SCHEMEMAP_WRITE: True})._person_groups_write(
            cleaned, source=source, note=note, extra=extra)
        return dict(result, ok=True, applied=True, saved=True, pending=False,
                    message=_("Saved."))

    @api.model
    def _person_propose_many(self, cleaned, everyone, company, source, note,
                             title, extra):
        plain = self._groups_plain(cleaned)
        first = cleaned[0]
        if not title:
            title = _("Pay %(count)s people by %(scheme)s from %(date)s",
                      count=len(everyone), scheme=first[1].name or '',
                      date=self._day_words(first[3]))
        configs = {c.id for _e, c, _a, _d in cleaned}
        configs |= {a.id for _e, _c, a, _d in cleaned if a not in ('keep', False)}
        single = len(everyone) == 1
        proposal = self.env['pb.schememap.proposal'].with_company(company).propose(
            'person_set', title,
            payload={'groups': plain, 'employee_ids': everyone.ids,
                     'config_id': first[1].id,
                     'advance_config_id': plain[0]['advance_config_id'],
                     'date_from': min(g['date_from'] for g in plain),
                     'company_id': company.id, 'source': source,
                     'note': (note or '')[:200], 'extra': extra or {},
                     'asked_by': self.env.uid},
            snapshot=self._person_snapshot_groups(plain),
            facts={'employees_moved': {'value': len(everyone), 'unit': ''},
                   'schemes': {'value': len(configs), 'unit': ''}},
            target=everyone if single else first[1],
            company=company,
        )
        return self._person_answer_of(proposal)

    @api.model
    def _person_answer_of(self, proposal):
        """P1's three outcomes, in its words: saved, refused with the
        reason, or sent for approval (to whom)."""
        answer = proposal.answer()
        answer['saved'] = bool(answer.get('applied'))
        result = answer.get('result') or {}
        answer['changed'] = result.get('changed', 0)
        answer['created'] = result.get('created', 0)
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
    def _person_groups_write(self, cleaned, source='hand', note='', extra=None):
        """Every group through P1's one writer, in one transaction. Returns
        `{'changed', 'created', 'row_ids'}`; a fill (`source='fill'`) also
        writes its log, so "Undo this fill" knows exactly which rows it made."""
        Row = self.env['pb.person.scheme'].sudo().with_context(active_test=False)
        everyone = []
        for employees, _c, _a, _d in cleaned:
            everyone.extend(employees.ids)
        self.env.flush_all()
        before = set(Row.search([('employee_id', 'in', everyone)]).ids)
        changed = 0
        for employees, config, advance, day in cleaned:
            changed += self._person_set_write(employees, config, advance, day,
                                              source=source, note=note)
        self.env.flush_all()
        made = Row.search([('employee_id', 'in', everyone),
                           ('id', 'not in', list(before))], order='id')
        out = {'changed': changed, 'created': len(made), 'row_ids': made.ids}
        if source == 'fill':
            fill = self._fill_log(made, cleaned, extra or {})
            out['fill_id'] = fill.id if fill else 0
        return out

    @api.model
    def _fill_log(self, rows, cleaned, extra):
        """Overridden by the fill (`pb_person_scheme_fill.py`)."""
        return None

    # ===================================================== waiting requests
    @api.model
    def _person_waiting(self, employee):
        """P1 found a waiting request by its target (one person). A team or
        fill request targets the scheme, so it is found in the payload too
        (PSCHEME P2a A.3): the person's panel says it is waiting either way."""
        found = super()._person_waiting(employee)
        if found:
            return found
        Proposal = self.env.get('pb.schememap.proposal')
        if Proposal is None:
            return None
        pending = Proposal.sudo().search([
            ('kind', '=', 'person_set'), ('state', '=', 'pending'),
            ('company_id', '=', employee.company_id.id)],
            order='id desc', limit=MAX_WAITING_SCAN)
        for proposal in pending:
            payload = proposal.payload() or {}
            if employee.id not in (payload.get('employee_ids') or []):
                continue
            group = next((g for g in payload.get('groups') or []
                          if employee.id in (g.get('employee_ids') or [])), payload)
            config = self.env['hr.formula.config'].sudo().browse(
                int(group.get('config_id') or 0)).exists()
            day = fields.Date.to_date(group.get('date_from')) \
                if group.get('date_from') else None
            return {'reference': proposal.name or '',
                    'scheme': config.name or '',
                    'config_id': config.id,
                    'date': group.get('date_from') or '',
                    'date_words': self._day_words(day),
                    'with_whom': proposal.waiting_for() or '',
                    'many': True}
        return None

    @api.model
    def _waiting_by_person(self, company_id):
        """`{employee_id: config_id}` of every waiting pay scheme change of
        this company (team, fill and one-person requests) — one search."""
        Proposal = self.env.get('pb.schememap.proposal')
        if Proposal is None:
            return {}
        out = {}
        for proposal in Proposal.sudo().search([
                ('kind', '=', 'person_set'), ('state', '=', 'pending'),
                ('company_id', '=', int(company_id or 0))],
                order='id', limit=MAX_WAITING_SCAN):
            payload = proposal.payload() or {}
            groups = payload.get('groups') or [payload]
            for group in groups:
                for employee_id in group.get('employee_ids') or []:
                    out[int(employee_id)] = int(group.get('config_id') or 0)
        return out


class PbSchemeMapProposalMany(models.Model):
    """The approval side of many-person requests and of "Undo this fill" —
    added here, beside the board that answers them, so the formula engine
    keeps no dependency on this module (dependency rail)."""
    _inherit = 'pb.schememap.proposal'

    _proposal_kind_labels = dict(
        PbSchemeMapProposal._proposal_kind_labels,
        person_unfill='Undo a pay scheme fill')

    def _proposal_kind_label(self, kind=None):
        if (kind or self.kind) == 'person_unfill':
            return _("Undo a pay scheme fill")
        return super()._proposal_kind_label(kind)

    def _live_snapshot(self):
        self.ensure_one()
        payload = self.payload() or {}
        if self.kind == 'person_set' and payload.get('groups'):
            board = self._person_board()
            return board._person_snapshot_groups(payload['groups']) if board is not None else {}
        if self.kind == 'person_unfill':
            # Nothing to compare: the undo itself keeps every person somebody
            # changed since and names them (PSCHEME P2a C.5).
            return {}
        return super()._live_snapshot()

    def _apply_person_set(self):
        payload = self.payload() or {}
        if not payload.get('groups'):
            return super()._apply_person_set()
        result = self._board().person_set_many(
            payload['groups'], payload.get('company_id'),
            payload.get('source') or 'hand', payload.get('note') or '',
            extra=dict(payload.get('extra') or {},
                       asked_by=payload.get('asked_by') or self.user_id.id,
                       reference=self.name or ''))
        return {'changed': (result or {}).get('changed', 0),
                'created': (result or {}).get('created', 0),
                'fill_id': (result or {}).get('fill_id', 0),
                'employee_ids': payload.get('employee_ids') or []}

    def _apply_person_unfill(self):
        payload = self.payload() or {}
        result = self._board().fill_undo_write(payload.get('fill_id'),
                                               asked_by=self.user_id.id)
        return {'removed': (result or {}).get('removed', 0),
                'people': (result or {}).get('people', 0),
                'kept': (result or {}).get('kept', 0)}

    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        if self.kind == 'person_unfill':
            fill = self.env['pb.person.scheme.fill'].sudo().browse(
                int(payload.get('fill_id') or 0)).exists() \
                if 'pb.person.scheme.fill' in self.env else None
            if not fill:
                return [(_('What happens'), '', _('The fill is not there any more'))]
            return [
                (_('Undo'), '', fill.display_words()),
                (_('What happens'), '', _(
                    "The pay schemes this fill gave are taken off again. People "
                    "somebody changed since keep theirs.")),
            ]
        if self.kind != 'person_set' or not payload.get('groups'):
            return super()._proposal_rows()
        ids = [int(e) for e in payload.get('employee_ids') or [] if e]
        people = self.env['hr.employee'].sudo().with_context(
            active_test=False).browse(ids).exists()
        names = ', '.join(people[:6].mapped('name'))
        if len(people) > 6:
            names = _('%(names)s and %(count)s more', names=names,
                      count=len(people) - 6)
        rows = [(_('Who'), '', names)]
        Config = self.env['hr.formula.config'].sudo().with_context(active_test=False)
        for group in payload['groups'][:6]:
            config = Config.browse(int(group.get('config_id') or 0)).exists()
            day = fields.Date.to_date(group.get('date_from')) \
                if group.get('date_from') else None
            count = len(group.get('employee_ids') or [])
            advance = group.get('advance_config_id')
            words = _("%(count)s people from %(date)s", count=count,
                      date=format_day(self.env, day))
            if advance and advance != 'keep':
                words = _("%(words)s, with the mid-month advance %(advance)s",
                          words=words,
                          advance=Config.browse(int(advance)).exists().name or '')
            rows.append((config.name or _('Pay scheme'), '', words))
        if len(payload['groups']) > 6:
            rows.append((_('Pay scheme'), '', _('and %s more pay schemes',
                                                len(payload['groups']) - 6)))
        return rows
