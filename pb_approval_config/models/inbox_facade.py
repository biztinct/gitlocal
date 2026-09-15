# -*- coding: utf-8 -*-
"""`pb.approval.inbox` — the only server surface the one inbox talks to.

EVERY METHOD HERE IS A SHAPER, NOT A GATE. Whether this person may see a
request is the record rule's answer; whether they may decide a step is
`biz.approval.engine.decide`'s, which re-checks the seat, the account, the
record's own access and the independence rule on every call. Nothing in this
file may be the thing that permits an action, and nothing in it uses `sudo()`
to make a path work — the two `sudo()` calls it does make are the reads the
audit-console pattern already allows: a person's name and their picture.

"MY TURN" IS A SEAT, NOT A GROUP. A card is mine when an OPEN seat on the step
that is waiting names me as the person who decides it — my own seat, or one I
am covering. It is never "somebody in my team", and never "anybody in HR".
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_approval_workflow.models import definition as D

_logger = logging.getLogger(__name__)

CONFIG_GROUP = 'biz_approval_workflow.group_approval_config'
ADMIN_GROUP = 'biz_approval_workflow.group_approval_admin'

#: Caps on anything a caller controls — reachable over JSON-RPC.
MAX_CARDS = 120
MAX_TEXT = 2000

#: The four tabs, and nothing else is accepted.
TABS = ('mine', 'all', 'returned', 'done')

#: WHOSE QUEUE IS BEING ASKED FOR.
#:  * 'me'   — everything I may see (the record rules decide, as always);
#:  * 'team' — everything waiting about somebody who works for me, whether or
#:             not I am the one who has to decide it. This is the Workforce
#:             screen a manager used to have, and it is a READ: deciding still
#:             goes through the engine, which re-checks the seat every time;
#:  * 'org'  — everything in the companies I work in, for the people whose job
#:             is to keep approvals moving.
SCOPES = ('me', 'team', 'org')

#: Who may ask for the whole organisation's queue.
ORG_GROUPS = ('biz_approval_workflow.group_approval_config',
              'hr.group_hr_manager',
              'om_hr_payroll.group_hr_payroll_manager')

#: How long a reason has to be before it is worth writing down. An exception is
#: a sentence somebody will read in an audit a year later; a send-back only has
#: to say what to change.
MIN_EXCEPTION_REASON = 12
MIN_REASON = 6


def _clip(text, size=MAX_TEXT):
    return (text or '')[:size]


class PbApprovalInbox(models.AbstractModel):
    _name = 'pb.approval.inbox'
    _description = 'Approvals inbox data'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=None):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            _logger.debug('Approvals inbox figure failed: %s', exc)
            return default

    @api.model
    def _can_config(self):
        user = self.env.user
        return (self.env.su or user._is_admin()
                or self._safe(lambda: user.has_group(CONFIG_GROUP),
                              default=False))

    @api.model
    def _engine(self):
        return self.env['biz.approval.engine']

    @api.model
    def _company(self):
        return self.env.user.company_id

    @api.model
    def _my_company_ids(self):
        """The companies this PERSON works in — never the top bar's.

        A wider queue is read under `sudo()`, so the company boundary has to
        be written into the domain by hand; taking it from the top bar would
        mean the answer changed when somebody ticked a box, which is exactly
        what the static contract here forbids.
        """
        return self.env.user.company_ids.ids or [self.env.user.company_id.id]

    # ---------------------------------------------------------- whose queue
    @api.model
    def _my_team_user_ids(self):
        """Everybody who works for me, however far down.

        Worked out from the employee tree — the same answer the Workforce
        team screen gave, kept when that screen was retired. `child_of` walks
        the whole branch, so a manager of managers sees their whole area.
        """
        employees = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)])
        if not employees:
            return []
        team = self.env['hr.employee'].sudo().search(
            [('id', 'child_of', employees.ids), ('id', 'not in',
                                                 employees.ids)])
        return sorted(set(team.mapped('user_id').ids))

    @api.model
    def _can_org(self):
        user = self.env.user
        if self.env.su or user._is_admin():
            return True
        for xmlid in ORG_GROUPS:
            if self._safe(lambda x=xmlid: user.has_group(x), default=False):
                return True
        return False

    @api.model
    def _scoped(self, scope):
        """(model to search with, extra domain) for one scope.

        A wider scope is a READ of what this person's own people are doing,
        collected the way the audit console collects (gated first, then
        `sudo()`), and never a permission: every decision still goes through
        `biz.approval.engine.decide`, which re-checks the seat, the account
        and the record's own access.
        """
        Request = self.env['biz.approval.request']
        if scope == 'team':
            # "MY TEAM" IS DEFINED IN LOGINS, AND MOST OF THE PEOPLE A LINE
            # MANAGER APPROVES FOR DO NOT HAVE ONE.
            #
            # `subject_user_ids` is filled from the subjects' USER accounts,
            # and a person who clocks in on a badge has none (ledger AM50 says
            # the same thing from the other side — "their manager" cannot be
            # resolved through a login either). So a supervisor whose whole
            # team punches a clock opened the dock and found it empty, while
            # their own seat sat on every one of those requests.
            #
            # The queue is therefore "about somebody who works for me, OR
            # waiting on a seat of mine" — which is also the debt AM103 wrote
            # down from the other end, where a request waiting on YOU was
            # filed under "Other requests" because the person it is about does
            # not report to you. It is still a READ and only a read: every
            # decision goes through the engine, which re-checks the seat, the
            # account and the record's own access.
            team = self._my_team_user_ids()
            waiting = [('seat_ids.acting_user_id', '=', self.env.uid),
                       ('seat_ids.status', '=', 'open')]
            company = [('company_id', 'in', self._my_company_ids())]
            if not team:
                return Request.sudo(), waiting + company
            return Request.sudo(), (
                ['|', ('subject_user_ids', 'in', team)]
                + ['&'] + waiting + company)
        if scope == 'org':
            if not self._can_org():
                raise AccessError(_(
                    "Only somebody who looks after approvals can see every "
                    "request in the company."))
            return Request.sudo(), [
                ('company_id', 'in', self._my_company_ids())]
        return Request, []

    # ============================================================ the cards
    @api.model
    def list_requests(self, tab='mine', filters=None, cursor=None,
                      scope='me'):
        """Everything this person may see, in the four piles they think in."""
        tab = tab if tab in TABS else 'mine'
        scope = scope if scope in SCOPES else 'me'
        filters = filters or {}
        Request, domain = self._scoped(scope)
        if tab == 'returned':
            domain.append(('state', '=', 'returned'))
        elif tab == 'done':
            domain.append(('state', 'in',
                           ('approved', 'applied', 'rejected', 'cancelled')))
        else:
            domain.append(('state', 'in', ('pending', 'blocked')))
        if tab == 'mine':
            domain.append(('seat_ids.acting_user_id', '=', self.env.uid))
        if filters.get('area'):
            domain.append(('process_id.area', '=', filters['area']))
        if filters.get('process_key'):
            domain.append(('process_id.key', '=', filters['process_key']))
        if filters.get('due') == 'today':
            domain += [('due_at', '!=', False),
                       ('due_at', '<=', fields.Datetime.to_string(
                           fields.Datetime.end_of(
                               fields.Datetime.now(), 'day')))]
        elif filters.get('due') == 'late':
            domain += [('due_at', '!=', False),
                       ('due_at', '<', fields.Datetime.now())]
        if cursor:
            domain.append(('id', '<', int(cursor)))

        rows = Request.search(domain, limit=MAX_CARDS,
                              order='submitted_at desc, id desc')
        cards = [self._card(row) for row in rows]
        if tab == 'mine':
            cards = [c for c in cards if c['mine']]

        return {
            'tab': tab,
            'scope': scope,
            'scope_label': self._scope_label(scope),
            'cards': cards,
            'counts': self._counts(scope),
            'areas': self._areas(),
            'can_config': self._can_config(),
            'can_org': self._can_org(),
            'has_team': bool(self._my_team_user_ids()),
            'me': {'id': self.env.uid, 'name': self.env.user.name},
            'covering_for': self._covering_for(),
            'covered_by': self._covered_by(),
            'money': self._money(cards),
            'cursor': cards[-1]['id'] if len(rows) == MAX_CARDS else 0,
        }

    def _scope_label(self, scope):
        return {
            'me': _('Everything I am part of'),
            'team': _('My team'),
            'org': _('The whole company'),
        }.get(scope, '')

    def _counts(self, scope='me'):
        """The number on each tab. Four cheap searches, not four page loads."""
        Request, base = self._scoped(scope)
        open_domain = base + [('state', 'in', ('pending', 'blocked'))]
        mine = self.env['biz.approval.request'].search(
            [('state', 'in', ('pending', 'blocked')),
             ('seat_ids.acting_user_id', '=', self.env.uid)],
            limit=MAX_CARDS)
        return {
            'mine': sum(1 for r in mine if self._is_mine(r)),
            'all': Request.search_count(open_domain),
            'returned': Request.search_count(
                base + [('state', '=', 'returned')]),
            'done': Request.search_count(base + [
                ('state', 'in', ('approved', 'applied', 'rejected',
                                 'cancelled'))]),
        }

    def _areas(self):
        labels = self.env['biz.approval.process']._area_labels()
        icons = self.env['biz.approval.process'].AREA_ICONS
        return [{'key': key, 'label': label,
                 'icon': icons.get(key, 'inbox')}
                for key, label in labels.items()]

    def _covering_for(self):
        """People whose seats I am holding right now."""
        rows = self.env['biz.approval.delegation'].sudo().search([
            ('delegate_user_id', '=', self.env.uid),
            ('state', 'in', ('draft', 'active')),
            ('date_from', '<=', fields.Date.context_today(self)),
            ('date_to', '>=', fields.Date.context_today(self)),
        ])
        return [{'name': r.principal_user_id.name,
                 'until': fields.Date.to_string(r.date_to) or ''}
                for r in rows]

    def _covered_by(self):
        """Whoever is holding my seats right now."""
        rows = self.env['biz.approval.delegation'].sudo().search([
            ('principal_user_id', '=', self.env.uid),
            ('state', 'in', ('draft', 'active')),
            ('date_from', '<=', fields.Date.context_today(self)),
            ('date_to', '>=', fields.Date.context_today(self)),
        ])
        return [{'name': r.delegate_user_id.name,
                 'until': fields.Date.to_string(r.date_to) or ''}
                for r in rows]

    def _money(self, cards):
        """Amounts, grouped by the money they are in — never added across."""
        totals = {}
        for card in cards:
            if not card['mine'] or not card['amount']:
                continue
            totals.setdefault(card['currency'], 0.0)
            totals[card['currency']] += card['amount']
        return [{'currency': name, 'amount': value}
                for name, value in sorted(totals.items()) if name]

    # --------------------------------------------------------------- a card
    def _current_step(self, request):
        return request.step_ids.filtered(
            lambda s: s.status in ('active', 'blocked')).sorted('sequence')[:1]

    def _is_mine(self, request):
        if request.state not in ('pending',):
            return False
        step = self._current_step(request)
        if not step or step.status != 'active':
            return False
        return bool(step.seat_ids.filtered(
            lambda s: s.status == 'open'
            and s.acting_user_id.id == self.env.uid))

    def _card(self, request):
        step = self._current_step(request)
        mine = self._is_mine(request)
        waiting = ''
        if step and request.state == 'blocked':
            waiting = step.block_reason or request.block_reason or ''
        elif step:
            names = []
            for seat in step.seat_ids.filtered(lambda s: s.status == 'open'):
                if seat.acting_user_id != seat.user_id and seat.user_id:
                    names.append(_('%(who)s, covering for %(whose)s',
                                   who=seat.acting_user_id.name,
                                   whose=seat.user_id.name))
                else:
                    names.append(seat.acting_user_id.name or '')
            # `_()` returns a lazy translation object, so the separator is
            # resolved to real text before anything is joined on it.
            separator = '%s' % (_(' and ') if step.kind == 'joint'
                                else _(' or '))
            waiting = separator.join(names)

        badges = []
        if step and step.kind == 'joint':
            done = len(step.seat_ids.filtered(
                lambda s: s.status == 'approved'))
            badges.append(_('%(done)s of %(total)s approvals received',
                            done=done, total=len(step.seat_ids)))
        if request.decision_ids.filtered('exception_grant_id'):
            badges.append(_('An exception was used'))

        return {
            'id': request.id,
            'process': request.process_id.name,
            'process_key': request.process_id.key,
            'area': request.process_id.area or 'other',
            'icon': request.process_id._area_icon(),
            'title': request.title,
            'sub': request.scope_label or request.company_id.name,
            'amount': request.amount or 0.0,
            'currency': request.currency_id.name or '',
            # HOW BIG IS THIS, IN THE UNITS THE THING IS COUNTED IN. A pay run
            # is a number of payslips; something else will be a number of
            # something else. Read off the frozen facts rather than named here,
            # so the card learns a new process's own count without this file
            # knowing what that process is.
            'count': self._card_count(request),
            'kind': self._kind_label(request),
            'workflow': _('%(name)s · v%(rev)s',
                          name=request.version_id.workflow_id.name or '',
                          rev=request.version_id.revision),
            'submitted_by': request.submitter_uid.name or '',
            'submitted_at': fields.Datetime.to_string(
                request.submitted_at) or '',
            'due_at': fields.Datetime.to_string(request.due_at) or '',
            'late': bool(request.due_at
                         and request.due_at < fields.Datetime.now()
                         and request.state in ('pending', 'blocked')),
            'state': request.state,
            'state_label': dict(
                request._fields['state'].selection).get(request.state, ''),
            'mine': mine,
            'blocked': request.state == 'blocked',
            'block_reason': request.block_reason or '',
            'return_note': request.return_note or '',
            'waiting_for': waiting,
            'badges': badges,
            'route': [{
                'title': s.title or '',
                'status': ('done' if s.status == 'done'
                           else 'current' if s.status == 'active'
                           else 'bad' if s.status in ('blocked', 'returned')
                           else 'skipped' if s.status == 'skipped'
                           else 'next'),
            } for s in request.step_ids.sorted('sequence')],
        }

    # ========================================================== one request
    @api.model
    def _readable(self, request_id, scope='me'):
        """The request, read as myself — or, in a wider queue, as the reader
        of my own people's business. Never a permission to decide."""
        request = self.env['biz.approval.request'].browse(int(request_id))
        scope = scope if scope in SCOPES else 'me'
        if scope == 'me':
            request.check_access('read')
            return request
        Request, domain = self._scoped(scope)
        found = Request.search(domain + [('id', '=', request.id)], limit=1)
        if not found:
            # not in the wider queue either: answer the ordinary way, so the
            # refusal is the ORM's own and says the same thing it always did
            request.check_access('read')
            return request
        return found

    @api.model
    def get_request(self, request_id, scope='me'):
        """The whole drawer: frozen facts, evidence, the route and my options."""
        request = self._readable(request_id, scope)
        if not request.exists():
            raise UserError(_("That request no longer exists."))
        payload = self._card(request)
        step = self._current_step(request)
        conflict = self._conflict_for_me(request, step)
        move = self.can_move_it(request.id)

        payload.update({
            'facts': self._facts(request),
            'detail': self._detail(request),
            'evidence': self._evidence(request),
            'steps': [self._step_payload(request, s)
                      for s in request.step_ids.sorted('sequence')],
            'decisions': [{
                'who': d.user_id.name or '',
                'action': d.action,
                'action_label': self._action_label(d.action),
                'step': d.step_key or '',
                'reason': d.reason or '',
                'when': fields.Datetime.to_string(d.stamp) or '',
                'exception': bool(d.exception_grant_id),
                'acting_for': d.acting_for_uid.name or '',
            } for d in request.decision_ids.sorted('stamp')],
            'confirmations': request.confirmations or [],
            'lock_revision': request.lock_revision,
            'conflict': conflict,
            'can_decide': bool(payload['mine']),
            'can_repair': bool(request.state == 'blocked'
                               and self._can_config()),
            # WHAT THE APP WANTS TO SAY ABOUT WHO WAS ASKED. A backup took a
            # seat because the holder sent it in, or nobody can approve it
            # yet — warnings, never refusals, above the steps where a reader
            # meets them before they wonder.
            'seat_notes': [n.get('msg') or ''
                           for n in (request.seat_notes or [])],
            'can_move_it': move,
            'move_people': self._move_candidates(request) if move['can']
                           else [],
            'can_cancel': bool(request.state in ('pending', 'blocked')
                               and (request.submitter_uid.id == self.env.uid
                                    or self._can_config())),
            'submitted_note': _(
                "Approving records your name, the time, and exactly the facts "
                "above as they were when this was sent in."),
        })
        return payload

    def _action_label(self, action):
        return {
            'approve': _('approved'),
            'return': _('sent it back'),
            'reject': _('turned it down'),
            'reassign': _('moved it to somebody else'),
            'cancel': _('withdrew it'),
        }.get(action, action or '')

    def _record_of(self, request):
        """The business record, or an empty recordset. Never raises.

        `sudo()` because this is used only to ASK the adapter how to phrase a
        number the reader is already allowed to see (the record rules on the
        request itself decided that); nothing here is a grant.
        """
        model = request.res_model
        if not (model and model in self.env and request.res_id):
            return None
        record = self.env[model].sudo().browse(request.res_id).exists()
        return record or None

    def _card_count(self, request):
        """The one number that says how big this request is, in plain words.

        The adapter gets the first word: hours, litres and headcount are not
        things this file can be taught one process at a time.
        """
        record = self._record_of(request)
        if record is not None and hasattr(record, '_approval_card_count'):
            said = self._safe(
                lambda: record._approval_card_count(request), default='')
            if said:
                return said
        facts = request.facts or {}

        def _value(key):
            raw = facts.get(key)
            if raw is None:
                return None
            value = raw.get('value') if isinstance(raw, dict) else raw
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        payslips = _value('payslip_count')
        if payslips is not None:
            return _('%s payslip', payslips) if payslips == 1 \
                else _('%s payslips', payslips)
        people = _value('employee_count')
        if people is not None:
            return _('%s person', people) if people == 1 \
                else _('%s people', people)
        return request.scope_label or ''

    def _kind_label(self, request):
        """What kind of thing this is, in the adapter's own words."""
        key = request.kind_key or 'any'
        if key == 'any':
            return ''
        process = request.process_id
        model = process.model_name
        if not (model and model in self.env
                and getattr(self.env[model], '_approval_process_key', None)):
            return ''
        caps = self._safe(
            lambda: self.env[model]._approval_capabilities(), default={}) or {}
        for row in (caps.get('kinds') or []):
            if isinstance(row, dict) and row.get('key') == key:
                return row.get('label') or ''
        return ''

    def _facts(self, request):
        """The facts, exactly as they were frozen — never as they are today."""
        labels, choices = {}, {}
        process = request.process_id
        model = process.model_name
        caps = {}
        if model and model in self.env \
                and getattr(self.env[model], '_approval_process_key', None):
            caps = self._safe(
                lambda: self.env[model]._approval_capabilities(),
                default={}) or {}
            labels = {key: (spec or {}).get('label') or key
                      for key, spec in (caps.get('facts') or {}).items()}
            # the kinds an adapter declares are key-and-label pairs, and the
            # frozen fact holds the KEY. Nobody should have to read one.
            choices = {row.get('key'): row.get('label')
                       for row in (caps.get('kinds') or [])
                       if isinstance(row, dict)}
        rows = []
        for key, raw in (request.facts or {}).items():
            value = raw.get('value') if isinstance(raw, dict) else raw
            unit = raw.get('unit') if isinstance(raw, dict) else ''
            if isinstance(value, bool):
                shown = _('Yes') if value else _('No')
            elif isinstance(value, (int, float)):
                shown = '{:,.2f}'.format(float(value)).rstrip('0').rstrip('.')
            else:
                shown = str(value if value is not None else '')
                shown = choices.get(shown, shown)
            # A UNIT IS A WORD, NOT A TYPE. Adapters put the shape of a fact in
            # the same slot as its unit ('bool', 'decimal'), and a screen that
            # prints "No bool" beside a yes/no answer is showing the reader the
            # machinery. Only a real unit survives.
            if (unit or '').lower() in D.FACT_TYPES:
                unit = ''
            rows.append({'key': key, 'label': labels.get(key, key),
                         'value': shown, 'unit': unit or ''})
        if request.amount:
            rows.insert(0, {
                'key': '_amount', 'label': _('Amount'),
                'value': '{:,.0f}'.format(float(request.amount)),
                'unit': request.currency_id.name or ''})
        return rows

    def _detail(self, request):
        """The optional small table an adapter offers under the facts.

        Shape-checked here rather than trusted: the drawer draws whatever comes
        back, and a malformed payload from a future adapter must degrade to
        "nothing more to show" rather than to a blank screen.
        """
        record = self._record_of(request)
        if record is None or not hasattr(record, '_approval_detail'):
            return None
        payload = self._safe(lambda: record._approval_detail(request),
                             default=None)
        # ROWS OR CHIPS. A detail with neither is nothing to show; a detail
        # with chips and no rows is a real answer — "everybody in this pay run
        # is in the file", with the bank and the filename beside it — and
        # dropping it left the drawer silent on exactly the reassuring case.
        if not isinstance(payload, dict) \
                or not (payload.get('rows') or payload.get('chips')):
            return None
        rows = []
        for row in payload['rows'][:40]:
            if not isinstance(row, dict):
                continue
            rows.append({
                'head': _clip(str(row.get('head') or ''), 40),
                'sub': _clip(str(row.get('sub') or ''), 40),
                'cells': [_clip(str(cell or ''), 40)
                          for cell in (row.get('cells') or [])[:6]],
                'tone': 'off' if row.get('tone') == 'off' else 'on',
            })
        chips = [{'label': _clip(str(chip.get('label') or ''), 60),
                  'value': _clip(str(chip.get('value') or ''), 40)}
                 for chip in (payload.get('chips') or [])[:8]
                 if isinstance(chip, dict)]
        if not rows and not chips:
            return None
        return {
            'title': _clip(str(payload.get('title') or ''), 120),
            'columns': [_clip(str(column or ''), 40)
                        for column in (payload.get('columns') or [])[:6]],
            'rows': rows,
            'chips': chips,
            'note': _clip(str(payload.get('note') or ''), 240),
        }

    def _evidence(self, request):
        """What the route asked to be attached, and whether it is."""
        definition = D.normalise(request.version_id.definition)
        rows = []
        for item in (definition['safeguards'].get('evidence') or []):
            if not isinstance(item, dict):
                continue
            rows.append({
                'name': item.get('name') or item.get('n') or '',
                'when': item.get('when') or '',
                'ok': bool(item.get('ok', True)),
                'required': bool(item.get('on', True)),
            })
        return rows

    def _step_payload(self, request, step):
        return {
            'key': step.key,
            'title': step.title or '',
            'kind': step.kind or '',
            'included': bool(step.included),
            'reason': step.include_reason or '',
            'status': step.status,
            'status_label': ('done' if step.status == 'done'
                             else 'current' if step.status == 'active'
                             else 'bad' if step.status in ('blocked',
                                                           'returned')
                             else 'skipped' if step.status == 'skipped'
                             else 'next'),
            'block_reason': step.block_reason or '',
            'due_at': fields.Datetime.to_string(step.due_at) or '',
            'joint': step.kind == 'joint',
            'seats': [{
                'key': seat.key,
                'name': seat.acting_user_id.name or '',
                'avatar': '/web/image/res.users/%s/avatar_128'
                          % seat.acting_user_id.id,
                'covering_for': (seat.user_id.name
                                 if seat.acting_user_id != seat.user_id
                                 else ''),
                'via': seat.resolved_via or '',
                'status': seat.status,
                'decided': seat.status in ('approved', 'returned', 'rejected'),
                'mine': seat.acting_user_id.id == self.env.uid,
            } for seat in step.seat_ids],
        }

    def _conflict_for_me(self, request, step):
        """Am I too close to this to decide it, and is there a way through?"""
        if not step or step.status != 'active':
            return None
        seat = step.seat_ids.filtered(
            lambda s: s.status == 'open'
            and s.acting_user_id.id == self.env.uid)[:1]
        if not seat:
            return None
        safeguards = D.normalise(request.version_id.definition)['safeguards']
        if not safeguards.get('independent'):
            return None
        ctx = {'submitter_uid': request.submitter_uid.id,
               'maker_uids': request.maker_uids or [],
               'subject_uids': request.subject_uids or []}
        kind = self._engine()._conflict_kind(self.env.uid, ctx) \
            or self._engine()._conflict_kind(seat.user_id.id, ctx)
        if not kind:
            return None
        grant = self.env['biz.approval.exception.grant'].sudo().search([
            ('company_id', '=', request.company_id.id),
            ('process_id', '=', request.process_id.id),
            ('state', '=', 'active')])
        allowed = grant.filtered(
            lambda g: g.permits(request, step, self.env.user, kind))[:1]
        return {
            'kind': kind,
            'text': {
                'submitter': _("You sent this in."),
                'maker': _("You prepared this."),
                'subject': _("This is about you."),
            }.get(kind, ''),
            'grant_id': allowed.id if allowed else 0,
            'grant_name': allowed.reason if allowed else '',
            'blocked': not allowed,
            'note': (_("With a written reason you may still approve it, and "
                       "the decision is marked in the trail.") if allowed
                     else _("Somebody else has to decide this one. Whoever "
                            "looks after approvals can arrange an exception "
                            "if that is not possible.")),
        }

    # ============================================================= the acts
    def _can_move_at_all(self):
        """Group membership only — this reads no record of any kind.

        `has_group` answers from the user's own groups, so it is safe to ask
        before a request has been touched. Keep it that way: anything added
        here that browses a record puts the team queue back in the dock.
        """
        user = self.env.user
        if self.env.su or user._is_admin():
            return True
        return self._safe(
            lambda: (user.has_group(CONFIG_GROUP)
                     or user.has_group(ADMIN_GROUP)),
            default=False)

    @api.model
    def can_move_it(self, request_id):
        """May this person move the live step to somebody else?

        `biz.approval.engine.reassign` has existed since Phase 1 and had no
        door: the only way to mend a request whose one seat belongs to the
        person who sent it in was a shell. That is the wrong end of the walk's
        commonest dead end — the seat is swapped to the backup at build time
        now, and this is what is left when there is no backup either.
        """
        # ASK THE CHEAP QUESTION FIRST, AND READ NOTHING AT ALL IF THE ANSWER
        # IS NO.
        #
        # Everybody who may open the drawer runs this — a line manager
        # reading what is waiting on a seat of theirs included — and a
        # request reached through the TEAM queue is served with `sudo()`,
        # because a supervisor is allowed to see what is happening to their
        # people without being allowed to read the record itself. Two earlier
        # cuts still touched the record before the gate (first the workflow
        # owner, then `check_access`) and handed that supervisor "you have
        # stumbled upon some top-secret records" in the middle of a queue
        # they were invited into.
        #
        # Moving a live step to somebody else is set-up work, so the only
        # question worth asking is group membership — which reads nothing —
        # and every read after it is `sudo()`. A route owner who does not
        # look after approvals is not a case: building a route needs these
        # rights in the first place.
        if not self._can_move_at_all():
            return {'can': False, 'step_key': '', 'seats': []}
        request = self.env['biz.approval.request'].sudo().browse(
            int(request_id or 0))
        if not request.exists():
            return {'can': False, 'step_key': '', 'seats': []}
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        return {
            'can': bool(step),
            'step_key': step.key if step else '',
            'seats': [{'key': seat.key,
                       'name': seat.acting_user_id.name or '',
                       'user_id': seat.acting_user_id.id}
                      for seat in step.seat_ids if seat.status == 'open'],
        }

    def _move_candidates(self, request):
        """Whom a stuck step could be handed to.

        The people who already hold a responsibility in this company, minus
        whoever is on the step now. Deliberately NOT every internal user: a
        list of four hundred logins is not a choice, it is a search box with
        no question.
        """
        request = request.sudo()
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        on_it = set(step.seat_ids.mapped('acting_user_id').ids)
        held = self.env['biz.approval.responsibility'].sudo().search(
            [('company_id', '=', request.company_id.id), ('active', '=', True)])
        people = held.mapped('user_id') | held.mapped('backup_user_id')
        return [{'id': u.id, 'name': u.name or ''}
                for u in people.sorted('name')
                if u.active and u.id not in on_it]

    @api.model
    def move_it(self, request_id, seat_key, user_id, reason=None):
        """Hand one seat to somebody else, with a reason, in the trail."""
        # Same gate as the button that offers this, asked the same cheap way.
        if not self._can_move_at_all():
            raise UserError(_(
                "Moving a step to somebody else is something whoever looks "
                "after approvals does."))
        request = self.env['biz.approval.request'].sudo().browse(
            int(request_id or 0))
        if not request.exists():
            raise UserError(_("That request no longer exists."))
        reason = _clip(reason)
        if len(reason.strip()) < MIN_REASON:
            raise UserError(_(
                "Say why you are moving this to somebody else. It is kept "
                "with the request, and the person who gets it reads it."))
        self.env['biz.approval.engine'].reassign(
            request, seat_key, int(user_id or 0), reason)
        return self.get_request(request.id)

    @api.model
    def decide(self, request_id, step_key, action, reason=None,
               expected_lock_revision=None, idempotency_key=None,
               use_exception=False):
        """Record one decision. The engine is what allows or refuses it."""
        if action not in ('approve', 'return', 'reject'):
            raise UserError(_("That is not something you can do here."))
        request = self.env['biz.approval.request'].browse(int(request_id))
        request.check_access('read')
        if not request.exists():
            raise UserError(_("That request no longer exists."))
        reason = _clip(reason)
        if action in ('return', 'reject') \
                and len(reason.strip()) < MIN_REASON:
            raise UserError(_(
                "Write what should change. The person reading this is the one "
                "who has to fix it."))

        grant_id = None
        if action == 'approve' and use_exception:
            step = request.step_ids.filtered(
                lambda s: s.key == step_key and s.status == 'active')[:1]
            conflict = self._conflict_for_me(request, step)
            if not conflict or not conflict['grant_id']:
                raise UserError(_(
                    "There is no exception that lets you approve this one."))
            if len(reason.strip()) < MIN_EXCEPTION_REASON:
                raise UserError(_(
                    "Write why you are approving something you were part of. "
                    "It is kept with the decision."))
            grant_id = conflict['grant_id']

        self._engine().decide(
            request.id, step_key, action, reason,
            expected_lock_revision, idempotency_key, grant_id)
        return self.get_request(request.id)

    @api.model
    def repair(self, request_id):
        """Try again to find the people a stuck request could not find."""
        request = self.env['biz.approval.request'].browse(int(request_id))
        request.check_access('read')
        self._engine().repair(request.id)
        return self.get_request(request.id)

    @api.model
    def cancel(self, request_id, reason=None):
        request = self.env['biz.approval.request'].browse(int(request_id))
        request.check_access('read')
        self._engine().cancel(request.id, _clip(reason))
        return self.get_request(request.id)

    # ==================================================================
    # THE AMBIENT DOCK
    #
    # The Workforce workspace carries a dock down the side: everything
    # waiting, oldest first, approvable where it is. It used to read a queue
    # of its own that knew four kinds of request by name and could disagree
    # with the inbox about any of them. It reads this instead — the same
    # requests, the same seats, the same engine — so it now shows EVERY kind
    # of request and can never be out of step with the screen beside it.
    #
    # The shape is the dock's, kept exactly, so the dock did not have to be
    # rewritten to gain eleven more kinds of request.
    # ==================================================================
    #: Which of the dock's four identities a process wears. Anything else is
    #: "other" — the point of the phase is that the dock stopped being a list
    #: of four things somebody remembered to add.
    DOCK_SOURCES = {
        'overtime': 'ot',
        'trip': 'trip',
        'correction': 'correction',
        'leave': 'leave',
    }
    DOCK_CAP = 20

    @api.model
    def get_team_data(self, recursive=True, scope='team', queues_only=True):
        """Everything waiting, for the dock. A read, and only a read."""
        scope = 'org' if (scope == 'org' and self._can_org()) else 'team'
        Request, domain = self._scoped(scope)
        open_domain = domain + [('state', 'in', ('pending', 'blocked'))]
        rows = Request.search(open_domain, order='submitted_at, id',
                              limit=self.DOCK_CAP * 5)
        items, counts, seen = [], {}, {}
        for request in rows:
            source = self.DOCK_SOURCES.get(request.process_id.key, 'other')
            counts[source] = counts.get(source, 0) + 1
            seen[source] = seen.get(source, 0) + 1
            if seen[source] > self.DOCK_CAP:
                continue
            items.append(self._dock_item(request, source))
        total = Request.search_count(open_domain)
        return {
            'has_team': bool(self._my_team_user_ids()),
            'is_hr': self._can_org(),
            'can_org': self._can_org(),
            'scope': scope,
            'queues': {
                'items': items,
                'counts': counts,
                'total': total,
                'has_more': {key: value > self.DOCK_CAP
                             for key, value in counts.items()},
            },
        }

    def _dock_item(self, request, source):
        record = self._record_of(request)
        mine = self._is_mine(request)
        employee = self.env['hr.employee']
        for uid in (request.subject_uids or []):
            employee = self.env['hr.employee'].sudo().search(
                [('user_id', '=', uid)], limit=1)
            if employee:
                break
        age = 0
        if request.submitted_at:
            age = max(0, (fields.Datetime.now() - request.submitted_at).days)
        return {
            'model': request.res_model,
            'res_id': request.res_id,
            'request_id': request.id,
            'source': source,
            'title': request.title or request.process_id.name or '',
            'subtitle': request.process_id.name or '',
            'when': fields.Datetime.to_string(request.submitted_at) or '',
            'when_iso': fields.Datetime.to_string(request.submitted_at) or '',
            'employee': {
                'id': employee.id,
                'name': employee.name or request.submitter_uid.name or '',
                'avatar_url': '/web/image/hr.employee/%s/avatar_128'
                              % employee.id if employee else '',
                'department': employee.department_id.name if employee else '',
            },
            'age': age,
            'can_approve': mine,
            'can_refuse': mine,
            # The engine keeps the reason with the decision, for every kind of
            # request. The old queue had to say which four of them stored one.
            'takes_note': True,
            'is_clean': bool(
                mine and record is not None
                and self._safe(lambda: record._approval_batch_safe(request),
                               default=False)),
        }

    @api.model
    def act(self, model, res_id, action, note=False):
        """The dock's one verb, answered by the engine.

        Deliberately the same signature the retired Workforce queue had, so
        the dock keeps its optimistic removal, its note box and its batch
        press. Nothing here decides anything: `decide` re-checks the seat, the
        account, the record's own access and the independence rule.
        """
        if action not in ('approve', 'refuse'):
            raise UserError(_("That is not something you can do here."))
        request = self.env['biz.approval.request'].sudo().search([
            ('res_model', '=', model), ('res_id', '=', int(res_id)),
            ('state', 'in', ('pending', 'blocked')),
        ], order='attempt desc, id desc', limit=1)
        if not request:
            raise UserError(_("This is no longer waiting for a decision."))
        step = request.step_ids.filtered(
            lambda s: s.status == 'active').sorted('sequence')[:1]
        if not step:
            raise UserError(_("No step is waiting for a decision on this."))
        self.decide(request.id, step.key,
                    'approve' if action == 'approve' else 'reject',
                    note or (_("Refused") if action == 'refuse' else ''))
        request.invalidate_recordset()
        # APPROVED IS NOT THE SAME AS DONE. A guard on the record itself — a
        # locked week, a ceiling, a permission the last approver has not got —
        # leaves the request approved and uncarried-out, with the reason on it.
        # A queue that reported that as a success would take the row off the
        # screen and leave the thing undone.
        blocked = request.block_reason if request.state == 'approved' else ''
        return {'ok': not blocked, 'error': blocked or '',
                'model': model, 'res_id': int(res_id),
                'state': request.state}

    # ------------------------------------------------- ask for a sign-off
    @api.model
    def ask_options(self):
        """What the "ask for a sign-off" form needs to draw itself."""
        company = self._company()
        options = []
        matrix = self.env['pb.approval.matrix']
        if matrix._can_config():
            levels = matrix._approval_scope_options(
                self.env['biz.approval.process']._by_key('generic'), company)
            for level in levels:
                options += level.get('options') or []
        return {
            'company_id': company.id,
            'company_name': company.name,
            'currency_id': company.currency_id.id,
            'currency_name': company.currency_id.name or '',
            'areas': options,
        }

    @api.model
    def ask(self, vals):
        """Ask anybody for a sign-off on anything, and send it in at once."""
        vals = vals or {}
        name = _clip(vals.get('name'), 240).strip()
        if not name:
            raise UserError(_("Say what you are asking for."))
        company = self._company()
        record = self.env['biz.approval.generic.request'].create({
            'name': name,
            'description': _clip(vals.get('description')),
            'company_id': company.id,
            'requester_user_id': self.env.uid,
            'amount': float(vals.get('amount') or 0.0),
            'currency_id': company.currency_id.id,
            'area_key': _clip(vals.get('area_key'), 80) or False,
            'area_label': _clip(vals.get('area_label'), 120) or False,
            'urgent': bool(vals.get('urgent')),
        })
        try:
            self._engine().submit(record)
        except (UserError, AccessError):
            # The draft is kept: the person wrote it, and the reason it could
            # not go anywhere is a setup problem somebody else has to mend.
            raise
        return {'request_id': record.approval_request_id.id,
                'record_id': record.id}
