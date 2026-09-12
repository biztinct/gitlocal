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

#: Caps on anything a caller controls — reachable over JSON-RPC.
MAX_CARDS = 120
MAX_TEXT = 2000

#: The four tabs, and nothing else is accepted.
TABS = ('mine', 'all', 'returned', 'done')

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

    # ============================================================ the cards
    @api.model
    def list_requests(self, tab='mine', filters=None, cursor=None):
        """Everything this person may see, in the four piles they think in."""
        tab = tab if tab in TABS else 'mine'
        filters = filters or {}
        Request = self.env['biz.approval.request']

        domain = []
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
            'cards': cards,
            'counts': self._counts(),
            'areas': self._areas(),
            'can_config': self._can_config(),
            'me': {'id': self.env.uid, 'name': self.env.user.name},
            'covering_for': self._covering_for(),
            'covered_by': self._covered_by(),
            'money': self._money(cards),
            'cursor': cards[-1]['id'] if len(rows) == MAX_CARDS else 0,
        }

    def _counts(self):
        """The number on each tab. Four cheap searches, not four page loads."""
        Request = self.env['biz.approval.request']
        open_domain = [('state', 'in', ('pending', 'blocked'))]
        mine = Request.search(
            open_domain + [('seat_ids.acting_user_id', '=', self.env.uid)],
            limit=MAX_CARDS)
        return {
            'mine': sum(1 for r in mine if self._is_mine(r)),
            'all': Request.search_count(open_domain),
            'returned': Request.search_count([('state', '=', 'returned')]),
            'done': Request.search_count([
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
    def get_request(self, request_id):
        """The whole drawer: frozen facts, evidence, the route and my options."""
        request = self.env['biz.approval.request'].browse(int(request_id))
        request.check_access('read')
        if not request.exists():
            raise UserError(_("That request no longer exists."))
        payload = self._card(request)
        step = self._current_step(request)
        conflict = self._conflict_for_me(request, step)

        payload.update({
            'facts': self._facts(request),
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

    def _card_count(self, request):
        """The one number that says how big this request is, in plain words."""
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
